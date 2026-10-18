"""Sofort sprechen für Kunden mit kurzen Texten (Rufzeichen, Fundus, Bombel, Zusage, Medienpool): Ton als WAV, 16 Bit,
24 kHz mono, wie die alte Sprachausgabe; die Dauer steht im Kopf `X-Dauer`. Längere Texte gehen über einen Plan."""

from __future__ import annotations

import shutil
import uuid

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from appkern.anmeldung import Konto
from appkern.ton import Lage, Legen, Tonformat

from ..modell.plan import StimmWahl
from ..saetze import saetze
from ..sprechen import mit_modus
from ..teile import Teile
from ..werk.werk import GRENZE_PEGEL, RAND_MS, RATE

PAUSE_S = 0.3
WAV = Tonformat(rate=RATE, kanaele=1, kodierung="pcm_s16le")


class SprechenAnfrage(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    stimme: StimmWahl | None = None          # ohne: die Stimme ab Werk
    sprache: str | None = None
    tempo: float = Field(1.0, ge=0.5, le=2.0)


def router(teile: Teile) -> APIRouter:
    g = teile.geruest
    r = APIRouter(prefix="/api/v1", tags=["sprechen"], dependencies=[g.pflicht])

    @r.post("/sprechen", response_class=FileResponse)
    async def sprechen(a: SprechenAnfrage, konto: Konto = g.pflicht) -> FileResponse:
        e = teile.einstellungen
        wahl = a.stimme or StimmWahl(art="katalog", name=e.stimme_vorgabe)
        await teile.stimme_pruefen(wahl, konto)
        gewaehlt = await teile.gewaehlt(wahl)
        werk = teile.werk()
        ordner = teile.arbeit / f"sprechen-{uuid.uuid4().hex}"
        ordner.mkdir(parents=True, exist_ok=True)
        try:
            dateien, lagen, beginn = [], [], 0.0
            for i, s in enumerate(saetze(a.text)):
                wie = mit_modus(gewaehlt, "auto", a.sprache or e.sprache, e.klonen_sprachfremd)
                g_ = await werk.abschnitt_sprechen(s.text, wie, a.sprache or e.sprache, a.tempo, ordner / f"satz-{i}.wav",
                                                   titel="Sprechen")
                dateien.append(g_.datei)
                lagen.append(Lage(datei=i, beginn_s=round(beginn, 4)))
                beginn += g_.dauer_s + PAUSE_S
            gelegt = await teile.ton.legen(dateien, Legen(rate=RATE, lagen=lagen, rand_ms=RAND_MS, spitze=GRENZE_PEGEL,
                                                          format=WAV), ordner / "sprache.wav", titel="Sprechen, fügen")
        except BaseException:
            shutil.rmtree(ordner, ignore_errors=True)
            raise
        return FileResponse(ordner / "sprache.wav", media_type="audio/wav", headers={"X-Dauer": f"{gelegt.datei.dauer_s:.3f}"},
                            background=BackgroundTask(shutil.rmtree, ordner, True))

    return r
