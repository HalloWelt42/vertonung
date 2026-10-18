"""Vertonung als Dienst für andere Apps (App-Schlüssel der Kellerwolke): eine Aufnahme hochladen, auf Wunsch mit
Segmenten (Start, Ende, Text, Sprecher), Sprachen und Stimme; zurück kommt der Auftrag. Sein Ergebnis nennt den Plan;
der Ton liegt dann unter /api/v1/inhalt/plaene/<plan>/ergebnis (zeitgenau, so lang wie die Aufnahme)."""

from __future__ import annotations

import json
import shutil
import uuid
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import TypeAdapter, ValidationError

from appkern.anmeldung import Konto
from appkern.app import von
from appkern.auftraege import Auftrag

from ..dienst import DienstEingabe, DienstSegment, ablegen
from ..modell.plan import StimmWahl
from ..teile import Teile

SEGMENTE = TypeAdapter(list[DienstSegment])


def router(teile: Teile) -> APIRouter:
    g = teile.geruest
    r = APIRouter(prefix="/api/v1", tags=["dienst"], dependencies=[g.pflicht])

    @r.post("/dienst/vertonen", response_model=Auftrag, status_code=201)
    async def vertonen(datei: UploadFile = File(...), name: str = Form(..., max_length=200),
                       sprache: str = Form("de"), ausgangssprache: str | None = Form(None),
                       stimme: str | None = Form(None, description='JSON wie {"art": "katalog", "name": "serena"}'),
                       segmente: str | None = Form(None, description="JSON-Liste mit start, ende, text, sprecher"),
                       format: Literal["wie_quelle", "m4a"] = Form("m4a"), konto: Konto = g.pflicht) -> Auftrag:
        try:
            wahl = StimmWahl.model_validate_json(stimme) if stimme else None
            stuecke = SEGMENTE.validate_json(segmente) if segmente else None
        except (ValidationError, json.JSONDecodeError) as f:
            raise HTTPException(422, f"Stimme oder Segmente nicht lesbar: {f}") from f
        if wahl is not None:
            await teile.stimme_pruefen(wahl, konto)
        endung = ("." + datei.filename.rsplit(".", 1)[1].lower()) if datei.filename and "." in datei.filename else ".wav"
        ordner = teile.arbeit / f"dienst-{uuid.uuid4().hex}"
        ordner.mkdir(parents=True, exist_ok=True)
        try:
            roh = ordner / f"aufnahme{endung}"
            with open(roh, "wb") as ziel:
                while stueck := await datei.read(1024 * 1024):
                    ziel.write(stueck)
            haupt = await ablegen(teile, konto.app or "Direkt", name, endung, roh, stuecke, ausgangssprache)
        finally:
            shutil.rmtree(ordner, ignore_errors=True)
        eingabe = DienstEingabe(haupt_id=haupt.id, name=name, ausgangssprache=ausgangssprache, sprache=sprache, stimme=wahl,
                                format=format, von=von(konto))
        return await g.auftraege.einreihen("dienst_vertonen", eingabe, titel=f"{name} ({konto.app or 'direkt'})")

    return r
