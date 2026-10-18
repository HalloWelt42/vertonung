"""Stimmen in der Kellerwolke: Referenz und Angaben je Stimme, nach Bereich getrennt. Eine neue Referenz wird
aufbereitet wie in der alten App (belegt): Stille an den Rändern weg, über 10 s die mittleren 8 s, Kanten 15 ms
geblendet, 40 ms Vorlauf und 60 ms Nachlauf (sonst übernimmt der Klon einen Knacks am Sprechbeginn), WAV 16 Bit,
24 kHz mono; kürzer als die Mindestlänge gibt keine Stimme. Die Referenz wird für das Werk einmal je Stand geholt."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from uuid import UUID

import json

import numpy as np
from pydantic import ValidationError

from appkern.kellerwolke import Kellerwolke, Knoten, NichtGefunden
from appkern.ton import Ton, Tonformat

from ..modell.stimme import Bereich, StimmAngaben, Stimme, aus_alter_app
from ..referenz import WortZeit, beste
from ..werk import fuegen
from . import orte

RATE = 24000
REFERENZ = Tonformat(rate=RATE, kanaele=1, kodierung="pcm_s16le")
LANG_S = 7.5                # bis hierhin bleibt eine Probe ganz; länger wird die beste Stelle gewählt (referenz.py)
KANTE_MS, VORLAUF_MS, NACHLAUF_MS = 15, 40, 60


class ProbeZuKurz(ValueError):
    pass


class KeineKellerwolke(Exception):
    """Die App ist noch nicht mit einer Kellerwolke verbunden."""


def zugang(liefern: Callable[[], Kellerwolke | None]) -> Kellerwolke:
    kw = liefern()
    if kw is None:
        raise KeineKellerwolke("Keine Kellerwolke eingerichtet")
    return kw


async def probe_aufbereiten(ton: Ton, roh: Path, ziel: Path, mindestens_s: float,
                            woerter: Callable[[Path], Awaitable[list[WortZeit]]]) -> tuple[float, str | None]:
    """Referenz aus einer Probe (Nutzer 18.10.2026: 5 bis 7 Sekunden, nie ein harter Schnitt im Wort). Bis LANG_S bleibt
    die Probe ganz; länger wird sie gehört (`woerter`) und die beste Stelle mit Pausen an beiden Rändern gewählt. Liefert
    die Dauer und, wenn zugeschnitten wurde, den Referenztext genau dieser Stelle."""
    werte = await ton.lesen(roh, RATE)
    sprache = fuegen.stille_kuerzen(werte, RATE).size / RATE
    if sprache < mindestens_s:
        raise ProbeZuKurz(f"Die Probe hat nur {sprache:.1f} s Sprache; nötig sind mindestens {mindestens_s:.0f} s")
    text = None
    if werte.size / RATE > LANG_S:
        gehoert = await woerter(roh)
        k = beste(werte, RATE, gehoert, None)
        if k is None:
            raise ProbeZuKurz("In der Probe gibt es keine Stelle von 5 bis 7 Sekunden mit Pausen davor und danach; "
                              "bitte eine Aufnahme mit natürlichen Sprechpausen")
        werte, text = werte[int(k.von * RATE): int(k.bis * RATE)], k.text
    werte = fuegen.raender(werte, RATE, KANTE_MS)
    werte = np.concatenate([np.zeros(int(RATE * VORLAUF_MS / 1000), np.float32), werte,
                            np.zeros(int(RATE * NACHLAUF_MS / 1000), np.float32)])
    await ton.schreiben(werte, RATE, ziel, REFERENZ)
    return round(werte.size / RATE, 2), text


def _angaben(inhalt: bytes, name: str) -> StimmAngaben:
    try:
        return StimmAngaben.model_validate_json(inhalt)
    except ValidationError as f:
        raise ValueError(f"{name}: keine lesbaren Stimmangaben ({f.errors()[0]['msg']})") from None


def _bereich_aus_pfad(pfad: str) -> Bereich | None:
    teile = pfad.split("/")
    for bereich, ordner in orte.BEREICH_ORDNER.items():
        if len(teile) >= 3 and teile[-3] == orte.STIMMEN and teile[-2] == ordner:
            return bereich
    return None


class Stimmen:
    def __init__(self, kellerwolke: Callable[[], Kellerwolke | None], speicher: Path) -> None:
        """`speicher`: Ordner für geholte Referenzen (je Stand eine Datei)."""
        self._kw = kellerwolke
        self.speicher = speicher
        self._gelesen: dict[str, StimmAngaben] = {}     # etag der Angaben -> Angaben

    @property
    def kw(self) -> Kellerwolke:
        return zugang(self._kw)

    async def ordner(self, bereich: Bereich) -> Knoten:
        kw = self.kw
        return await kw.ordner(orte.ort((await kw.ich()).zweig, orte.STIMMEN, orte.BEREICH_ORDNER[bereich]))

    async def _angaben_lesen(self, k: Knoten) -> StimmAngaben:
        if k.etag and k.etag in self._gelesen:
            return self._gelesen[k.etag]
        inhalt = await self.kw.lesen_ganz(k.id)
        a = await self._alte_umstellen(k, inhalt) or _angaben(inhalt, k.name)
        if k.etag:
            self._gelesen[k.etag] = a
        return a

    async def _alte_umstellen(self, k: Knoten, inhalt: bytes) -> StimmAngaben | None:
        """Übernommene Angaben der alten Stimmenausgabe: einmal ins heutige Format umstellen und so zurückschreiben
        (eine neue Version, die alte bleibt in der Kellerwolke). Andere Angaben: None."""
        try:
            daten = json.loads(inhalt)
        except ValueError:
            return None
        bereich = _bereich_aus_pfad(k.pfad)
        if not isinstance(daten, dict) or daten.get("format") != "stimme-alt/1" or bereich is None:
            return None
        a = aus_alter_app(daten, bereich)
        await self.kw.neue_version(k.id, a.model_dump_json(indent=1).encode(), stand=k.etag or "", inhaltstyp=orte.JSON)
        return a

    def _stimme(self, haupt: Knoten, angaben: StimmAngaben) -> Stimme:
        dauer = haupt.felder.get("dauer_s")
        return Stimme(id=str(haupt.id), name=angaben.name, bereich=angaben.bereich, angaben=angaben, pfad=haupt.pfad,
                      dauer_s=float(dauer) if isinstance(dauer, (int, float)) else None)

    async def alle(self, bereich: Bereich) -> list[Stimme]:
        kinder = [k async for k in self.kw.alle_kinder((await self.ordner(bereich)).id)]
        angaben = {k.haupt_id: k for k in kinder if k.haupt_id and k.rolle == orte.ROLLE_STIMME}
        aus = []
        for haupt in kinder:
            if haupt.haupt_id is None and orte.ist_ton(haupt) and haupt.id in angaben:
                aus.append(self._stimme(haupt, await self._angaben_lesen(angaben[haupt.id])))
        return sorted(aus, key=lambda s: s.name.lower())

    async def _angaben_knoten(self, stimme_id: UUID | str) -> Knoten:
        k = next((b for b in await self.kw.begleiter(stimme_id) if b.rolle == orte.ROLLE_STIMME), None)
        if k is None:
            raise NichtGefunden("Zu dieser Datei gibt es keine Stimmangaben")
        return k

    async def lesen(self, stimme_id: UUID | str) -> Stimme:
        haupt = await self.kw.knoten(stimme_id)
        return self._stimme(haupt, await self._angaben_lesen(await self._angaben_knoten(stimme_id)))

    async def anlegen(self, angaben: StimmAngaben, referenz: Path, dauer_s: float, original: Path | None = None) -> Stimme:
        """Referenz (schon aufbereitet) und Angaben anlegen; ein vergebener Name ist ein Konflikt der Kellerwolke."""
        kw = self.kw
        ordner = await self.ordner(angaben.bereich)
        name = orte.dateiname(angaben.name)
        haupt = await kw.schreiben(f"{ordner.pfad}/{name}.wav", referenz, nur_neu=True, inhaltstyp="audio/wav")
        await kw.felder_setzen(haupt.id, {"dauer_s": dauer_s})
        await kw.begleiter_schreiben(haupt.id, orte.ROLLE_STIMME, orte.ZUSATZ_STIMME, angaben.model_dump_json(indent=1).encode(),
                                     nur_neu=True, inhaltstyp=orte.JSON)
        if original is not None:
            await kw.begleiter_schreiben(haupt.id, orte.ROLLE_QUELLE, f".quelle{original.suffix.lower() or '.wav'}", original,
                                         nur_neu=True)
        return await self.lesen(haupt.id)

    async def aendern(self, stimme_id: UUID | str, angaben: StimmAngaben) -> Stimme:
        """Neue Angaben; ein anderer Bereich zieht die Stimme samt Begleitern um, ein anderer Name benennt sie um."""
        kw = self.kw
        haupt = await kw.knoten(stimme_id)
        k = await self._angaben_knoten(stimme_id)
        bisher = await self._angaben_lesen(k)
        await kw.neue_version(k.id, angaben.model_dump_json(indent=1).encode(), stand=k.etag or "", inhaltstyp=orte.JSON)
        if angaben.bereich != bisher.bereich or angaben.name != bisher.name:
            ziel = await self.ordner(angaben.bereich)
            await kw.umziehen(haupt.id, ziel.id, f"{orte.dateiname(angaben.name)}.wav")
        return await self.lesen(stimme_id)

    async def loeschen(self, stimme_id: UUID | str) -> None:
        """In den Papierkorb der Kellerwolke; Angaben und Originalaufnahme gehen mit."""
        await self.kw.loeschen(stimme_id)

    async def referenz(self, stimme_id: UUID | str) -> tuple[Path, str]:
        """Die Referenz als Datei (einmal je Stand geholt) und ihr Referenztext."""
        kw = self.kw
        haupt = await kw.knoten(stimme_id)
        angaben = await self._angaben_lesen(await self._angaben_knoten(stimme_id))
        self.speicher.mkdir(parents=True, exist_ok=True)
        datei = self.speicher / f"{haupt.id}-{(haupt.etag or 'ohne')[:16]}.wav"
        if not datei.is_file():
            for alt in self.speicher.glob(f"{haupt.id}-*.wav"):
                alt.unlink(missing_ok=True)
            await kw.herunterladen(haupt.id, datei)
        return datei, angaben.referenztext
