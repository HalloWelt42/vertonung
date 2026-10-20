"""Sofort sprechen für Kunden mit kurzen Texten (Rufzeichen, Fundus, Bombel, Zusage, Medienpool, Assistent).

- `POST /api/v1/sprechen`: Ton als WAV, 16 Bit, 24 kHz mono, wie die alte Sprachausgabe; die Dauer steht im Kopf
  `X-Dauer`.
- `POST /api/v1/sprechen/strom`: Satz für Satz als NDJSON (`application/x-ndjson`), je Zeile eine `StromZeile`; der
  erste Satz kommt, sobald er gesprochen ist. Bricht der Kunde ab, endet die Arbeit (Starlette bricht den Strom ab,
  kein weiterer Satz geht an den Sprechdienst).

Beide teilen mit `saetze` und schreiben auf Wunsch mit `sprechbar` aus (eine Stelle für beides); dieselbe Stimmprüfung
(nur Katalog und freigegebene private Stimmen). Längere Texte gehen über einen Plan."""

from __future__ import annotations

import base64
import logging
import shutil
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

from appkern.anmeldung import Konto
from appkern.ton import Lage, Legen, Tonformat

from ..modell.plan import StimmWahl
from ..modell.sprechen import SprechenAnfrage, StromAnfrage, StromEnde, StromFehler, StromSatz, StromZeile
from ..saetze import Satz, saetze
from ..sprechen import Gewaehlt, mit_modus
from ..sprechfassung import hat_worte, sprechbar
from ..teile import Teile
from ..werk.werk import GRENZE_PEGEL, RAND_MS, RATE, Gesprochen, Werk

PAUSE_S = 0.3
WAV = Tonformat(rate=RATE, kanaele=1, kodierung="pcm_s16le")
log = logging.getLogger("vertonung")


class NdjsonAntwort(StreamingResponse, JSONResponse):
    """Strom aus JSON-Zeilen. Gesendet wird wie bei `StreamingResponse`; als `JSONResponse` gekennzeichnet, damit das
    Schema der App den Vertrag der Zeilen (`StromZeile`) unter `application/x-ndjson` zeigt statt "Text"."""
    media_type = "application/x-ndjson"


@dataclass(frozen=True)
class Sprechauftrag:
    """Was für ein Sofortsprechen feststeht, bevor gesprochen wird (Stimme geprüft und geholt)."""
    werk: Werk
    stimme: Gewaehlt
    sprache: str
    tempo: float
    ausschreiben: bool

    def sprechtext(self, satz: Satz) -> str:
        return sprechbar(satz.text, self.sprache) if self.ausschreiben else satz.text

    async def sprechen(self, text: str, ziel: Path, titel: str) -> Gesprochen:
        return await self.werk.abschnitt_sprechen(text, self.stimme, self.sprache, self.tempo, ziel, titel=titel)


def _zeile(z: BaseModel) -> bytes:
    return z.model_dump_json().encode() + b"\n"


def router(teile: Teile) -> APIRouter:
    g = teile.geruest
    r = APIRouter(prefix="/api/v1", tags=["sprechen"], dependencies=[g.pflicht])

    async def vorbereiten(a: SprechenAnfrage, konto: Konto) -> Sprechauftrag:
        e = teile.einstellungen
        wahl = a.stimme or StimmWahl(art="katalog", name=e.stimme_vorgabe)
        await teile.stimme_pruefen(wahl, konto)
        sprache = a.sprache or e.sprache
        stimme = mit_modus(await teile.gewaehlt(wahl), "auto", sprache, e.klonen_sprachfremd)
        return Sprechauftrag(teile.werk(), stimme, sprache, a.tempo, a.ausschreiben)

    def arbeitsordner() -> Path:
        ordner = teile.arbeit / f"sprechen-{uuid.uuid4().hex}"
        ordner.mkdir(parents=True, exist_ok=True)
        return ordner

    @r.post("/sprechen", response_class=FileResponse)
    async def sprechen(a: SprechenAnfrage, konto: Konto = g.pflicht) -> FileResponse:
        auftrag = await vorbereiten(a, konto)
        ordner = arbeitsordner()
        try:
            dateien, lagen, beginn = [], [], 0.0
            for s in saetze(a.text):
                text = auftrag.sprechtext(s)
                if not hat_worte(text):
                    continue
                g_ = await auftrag.sprechen(text, ordner / f"satz-{len(dateien)}.wav", "Sprechen")
                lagen.append(Lage(datei=len(dateien), beginn_s=round(beginn, 4)))
                dateien.append(g_.datei)
                beginn += g_.dauer_s + PAUSE_S
            gelegt = await teile.ton.legen(dateien, Legen(rate=RATE, lagen=lagen, rand_ms=RAND_MS, spitze=GRENZE_PEGEL,
                                                          format=WAV), ordner / "sprache.wav", titel="Sprechen, fügen")
        except BaseException:
            shutil.rmtree(ordner, ignore_errors=True)
            raise
        return FileResponse(ordner / "sprache.wav", media_type="audio/wav", headers={"X-Dauer": f"{gelegt.datei.dauer_s:.3f}"},
                            background=BackgroundTask(shutil.rmtree, ordner, True))

    @r.post("/sprechen/strom", response_class=NdjsonAntwort,
            responses={200: {"model": StromZeile, "description": "Je Zeile ein JSON-Objekt (`art`: satz, ende, fehler)"}})
    async def sprechen_strom(a: StromAnfrage, konto: Konto = g.pflicht) -> NdjsonAntwort:
        """Satz für Satz: je gesprochenem Satz eine Zeile `satz` mit Ton, am Ende `ende`; scheitert das Sprechen mitten
        im Strom, eine Zeile `fehler` und Schluss. Stimme und Anmeldung werden vorher geprüft (Fehler als HTTP)."""
        auftrag = await vorbereiten(a, konto)
        return NdjsonAntwort(strom(a.text, auftrag, arbeitsordner()), headers={"Cache-Control": "no-cache"})

    return r


async def strom(eingabe: str, auftrag: Sprechauftrag, ordner: Path) -> AsyncIterator[bytes]:
    """Die Zeilen des Stroms. Abbruch durch den Kunden kommt als Abbruch (kein `Exception`) an und beendet die Arbeit;
    der Arbeitsordner geht in jedem Fall weg."""
    nr, gesamt_ms = 0, 0
    try:
        for s in saetze(eingabe):
            text = auftrag.sprechtext(s)
            if not hat_worte(text):
                continue
            datei = ordner / f"satz-{nr}.wav"
            gesprochen = await auftrag.sprechen(text, datei, "Sprechen, Strom")
            ton = base64.b64encode(datei.read_bytes()).decode("ascii")
            datei.unlink(missing_ok=True)
            dauer_ms = round(gesprochen.dauer_s * 1000)
            yield _zeile(StromSatz(nr=nr, text=eingabe[s.von:s.bis], gesprochen=text, von_zeichen=s.von,
                                   bis_zeichen=s.bis, dauer_ms=dauer_ms, ton=ton))
            nr += 1
            gesamt_ms += dauer_ms
        yield _zeile(StromEnde(saetze=nr, dauer_ms=gesamt_ms))
    except Exception as fehler:  # noqa: BLE001 - mitten im Strom geht kein HTTP-Fehler mehr, nur die Zeile
        log.warning("Sprechen als Strom gescheitert nach %d Sätzen", nr, exc_info=True)
        yield _zeile(StromFehler(meldung=str(fehler) or "Sprechen gescheitert"))
    finally:
        shutil.rmtree(ordner, ignore_errors=True)
