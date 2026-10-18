"""Inhalte zum Anhören (auch mit dem Inhalts-Cookie für `<audio>`): Probe einer Stimme, ein gesprochener Abschnitt aus
dem Zwischenspeicher, das Ergebnis eines Plans."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response

from appkern.anmeldung import Konto
from appkern.app import inhalt_reichen

from ..teile import Teile
from ..werk.werk import SPEICHERFASSUNG


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
        """Ein gesprochener Abschnitt zum Anhören: die Datei des Zwischenspeichers selbst (WAV 16 Bit, spielt jeder
        Browser)."""
        datei = next(iter(sorted(teile.speicher(plan_id).glob(f"{nr:05d}-*.{SPEICHERFASSUNG}.wav"))), None)
        if datei is None:
            raise HTTPException(404, "Dieser Abschnitt ist noch nicht gesprochen")
        return FileResponse(datei, media_type="audio/wav")

    @r.get("/plaene/{plan_id}/ergebnis")
    async def ergebnis(plan_id: UUID, request: Request, anfrage: UUID | None = None, konto: Konto = g.lesen) -> Response:
        plan, _ = await teile.plaene_fuer(anfrage).lesen(plan_id)
        if plan.ergebnis is None:
            raise HTTPException(404, "Noch kein Ergebnis")
        kw = teile.zugang(anfrage)
        return await inhalt_reichen(kw, await kw.knoten(plan.ergebnis.knoten_id), request)

    return r
