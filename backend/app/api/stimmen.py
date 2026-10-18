"""Stimmen: privat, fremd und der Katalog des Sprechdienstes; anlegen aus einer hochgeladenen Probe, Angaben ändern
(ein anderer Bereich zieht um), in den Papierkorb. Private sieht nur, wer sie nutzen darf."""

from __future__ import annotations

import shutil
import uuid
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from appkern.anmeldung import Konto

from ..ablage.stimmen import probe_aufbereiten
from ..modell.stimme import Bereich, Herkunft, StimmAngaben, Stimme
from ..teile import KeinRechtAufStimme, Teile


def router(teile: Teile) -> APIRouter:
    g = teile.geruest
    r = APIRouter(prefix="/api/v1", tags=["stimmen"], dependencies=[g.pflicht])

    @r.get("/stimmen", response_model=list[Stimme])
    async def liste(bereich: Literal["privat", "fremd", "katalog"] = "fremd", suche: str = "",
                    konto: Konto = g.pflicht) -> list[Stimme]:
        if bereich == "privat" and not teile.darf_privat(konto):
            raise KeinRechtAufStimme("Private Stimmen sind dieser App nicht erlaubt")
        if bereich == "katalog":
            alle = [Stimme(id=f"katalog:{n}", name=n, bereich="katalog") for n in await teile.dienst.katalog()]
        else:
            alle = await teile.stimmen.alle(bereich)
        s = suche.strip().lower()
        return [x for x in alle if not s or s in x.name.lower() or any(s in b.lower() for b in (x.angaben.bekannt_als if x.angaben else []))]

    @r.get("/stimmen/{stimme_id}", response_model=Stimme)
    async def eine(stimme_id: UUID, konto: Konto = g.pflicht) -> Stimme:
        s = await teile.stimmen.lesen(stimme_id)
        if s.bereich == "privat" and not teile.darf_privat(konto):
            raise KeinRechtAufStimme("Private Stimmen sind dieser App nicht erlaubt")
        return s

    @r.patch("/stimmen/{stimme_id}", response_model=Stimme)
    async def aendern(stimme_id: UUID, angaben: StimmAngaben, konto: Konto = g.mensch) -> Stimme:
        return await teile.stimmen.aendern(stimme_id, angaben)

    @r.delete("/stimmen/{stimme_id}", status_code=204)
    async def loeschen(stimme_id: UUID, konto: Konto = g.mensch) -> Response:
        await teile.stimmen.loeschen(stimme_id)
        return Response(status_code=204)

    @r.post("/stimmen", response_model=Stimme, status_code=201)
    async def hochladen(request: Request, name: str, bereich: Bereich, sprache: str = "de", referenztext: str = "",
                        endung: str = ".wav", konto: Konto = g.mensch) -> Stimme:
        """Eine Probe als Körper (gestreamt); sie wird aufbereitet, das Original kommt als Begleiter mit."""
        if not endung.startswith(".") or len(endung) > 6:
            raise HTTPException(422, "Endung wie .wav, .mp3, .m4a")
        ordner = teile.arbeit / f"stimme-{uuid.uuid4().hex}"
        ordner.mkdir(parents=True, exist_ok=True)
        try:
            roh = ordner / f"original{endung.lower()}"
            with open(roh, "wb") as datei:
                async for stueck in request.stream():
                    datei.write(stueck)
            referenz = ordner / "referenz.wav"
            dauer, zugeschnitten = await probe_aufbereiten(teile.ton_jetzt, roh, referenz, teile.einstellungen.probe_min_s,
                                                           lambda d: teile.hoeren_woerter(d, sprache))
            # zugeschnitten: der Text genau dieser Stelle; ganz geblieben: der angegebene oder (beim Sprechen) gehörte
            angaben = StimmAngaben(name=name, bereich=bereich, sprache=sprache, referenztext=zugeschnitten or referenztext,
                                   herkunft=Herkunft(art="hochgeladen"))
            return await teile.stimmen.anlegen(angaben, referenz, dauer, original=roh)
        finally:
            shutil.rmtree(ordner, ignore_errors=True)

    return r
