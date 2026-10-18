"""Inhalte zum Anhören (auch mit dem Inhalts-Cookie für `<audio>`): Probe einer Stimme, ein gesprochener Abschnitt aus
dem Zwischenspeicher, das Ergebnis eines Plans."""

from __future__ import annotations

import shutil
import uuid
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response

from appkern.anmeldung import Konto
from appkern.app import inhalt_reichen
from appkern.ton import Tonformat
from starlette.background import BackgroundTask

from ..teile import Teile
from ..werk.werk import RATE


def router(teile: Teile) -> APIRouter:
    g = teile.geruest
    r = APIRouter(prefix="/api/v1/inhalt", tags=["inhalt"])

    @r.get("/stimmen/{stimme_id}/probe")
    async def probe(stimme_id: UUID, request: Request, konto: Konto = g.lesen) -> Response:
        s = await teile.stimmen.lesen(stimme_id)
        if s.bereich == "privat" and not teile.darf_privat(konto):
            raise HTTPException(403, "Private Stimmen sind dieser App nicht erlaubt")
        kw = teile.zugang()
        return await inhalt_reichen(kw, await kw.knoten(stimme_id), request)

    @r.get("/plaene/{plan_id}/abschnitte/{nr}")
    async def abschnitt(plan_id: UUID, nr: int, konto: Konto = g.lesen) -> FileResponse:
        """Ein gesprochener Abschnitt zum Anhören, als WAV 16 Bit (das Arbeitsformat Gleitkomma spielt nicht jeder
        Browser); gewandelt ohne Änderung der Rate."""
        datei = next(iter(sorted(teile.speicher(plan_id).glob(f"{nr:05d}-*.wav"))), None)
        if datei is None:
            raise HTTPException(404, "Dieser Abschnitt ist noch nicht gesprochen")
        ordner = teile.arbeit / f"anhoeren-{uuid.uuid4().hex}"
        ordner.mkdir(parents=True, exist_ok=True)
        ziel = await teile.ton_jetzt.wandeln(datei, ordner / "abschnitt.wav", Tonformat(rate=RATE, kanaele=1, kodierung="pcm_s16le"))
        return FileResponse(ziel, media_type="audio/wav", background=BackgroundTask(shutil.rmtree, ordner, True))

    @r.get("/plaene/{plan_id}/ergebnis")
    async def ergebnis(plan_id: UUID, request: Request, anfrage: UUID | None = None, konto: Konto = g.lesen) -> Response:
        plan, _ = await teile.plaene_fuer(anfrage).lesen(plan_id)
        if plan.ergebnis is None:
            raise HTTPException(404, "Noch kein Ergebnis")
        kw = teile.zugang(anfrage)
        return await inhalt_reichen(kw, await kw.knoten(plan.ergebnis.knoten_id), request)

    return r
