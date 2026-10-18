"""Pläne: anlegen (Vorlesen aus Text oder Datei, Dialog, zeitgenau aus Transkript oder Untertiteln), lesen mit Stand
je Abschnitt, ändern nur mit dem zuletzt gelesenen Stand, vertonen als Auftrag, in den Papierkorb."""

from __future__ import annotations

import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from appkern.anmeldung import Konto
from appkern.app import von
from appkern.auftraege import Auftrag
from appkern.kellerwolke import Knoten

from .. import planen
from ..arten import VertonenEingabe
from ..modell.plan import Plan, Quelle, Stand, StimmWahl, Ziel
from ..teile import Teile
from ..verzeichnis import Eintrag, Seite
from ..werk.zeitlage import mit_hinweis

UNTERTITEL = (".srt", ".vtt")


class PlanAnlegen(BaseModel):
    art: Literal["vorlesen", "dialog", "zeitgenau"]
    name: str = Field("", max_length=200)
    text: str | None = Field(None, max_length=200_000)     # Vorlesen und Dialog: neuer Text in Texte
    quelle_id: UUID | None = None                          # Text, Transkript oder Untertitel in der Kellerwolke
    anfrage_id: UUID | None = None                         # Quelle außerhalb der App (aus der Kellerwolke angefragt)
    stimme: StimmWahl | None = None                        # Vorlesen; im Dialog und zeitgenau die Vorgabe
    stimmen: dict[str, StimmWahl] = Field(default_factory=dict)   # Rolle (Name) -> Stimme
    sprache: str | None = None
    format: Literal["mp3", "wav", "flac", "ogg"] | None = None


class AbschnittStand(BaseModel):
    nr: int
    stand: Stand
    hinweis: bool


class PlanAntwort(BaseModel):
    id: UUID
    stand: str
    plan: Plan
    staende: list[AbschnittStand]
    haupt_id: UUID
    haupt_pfad: str


class PlanAendern(BaseModel):
    plan: Plan
    stand: str


class VerzeichnisAntwort(Seite):
    zahlen: dict[str, int]


def _antwort(plan: Plan, knoten: Knoten, haupt: Knoten) -> PlanAntwort:
    staende = [AbschnittStand(nr=a.nr, stand=plan.stand(a),
                              hinweis=bool(a.bericht and mit_hinweis(a.bericht.stauchung, a.bericht.versatz_s, a.bericht.ersatz)))
               for a in plan.abschnitte]
    return PlanAntwort(id=knoten.id, stand=knoten.etag or "", plan=plan, staende=staende, haupt_id=haupt.id, haupt_pfad=haupt.pfad)


def router(teile: Teile) -> APIRouter:
    g = teile.geruest
    r = APIRouter(prefix="/api/v1", tags=["plaene"], dependencies=[g.pflicht])

    async def eintragen(plan: Plan, knoten: Knoten, haupt: Knoten, anfrage: UUID | None) -> None:
        await teile.verzeichnis.eintragen(plan, knoten.id, haupt.id, haupt.pfad,
                                          await teile.stimmen_namen([x.stimme for x in plan.rollen]), anfrage)

    @r.get("/plaene", response_model=VerzeichnisAntwort)
    async def verzeichnis(art: str | None = None, suche: str = "", ab: int = 0, anzahl: int = 50) -> VerzeichnisAntwort:
        seite = await teile.verzeichnis.seite(art=art, suche=suche, ab=ab, anzahl=min(anzahl, 200))
        return VerzeichnisAntwort(**seite.model_dump(), zahlen=await teile.verzeichnis.zaehlen())

    @r.post("/plaene", response_model=PlanAntwort, status_code=201)
    async def anlegen(a: PlanAnlegen, konto: Konto = g.pflicht) -> PlanAntwort:
        e = teile.einstellungen
        kw = teile.zugang(a.anfrage_id)
        plaene = teile.plaene_fuer(a.anfrage_id)
        vorgabe = a.stimme or StimmWahl(art="katalog", name=e.stimme_vorgabe)
        for w in [vorgabe, *a.stimmen.values()]:
            await teile.stimme_pruefen(w, konto)
        sprache = a.sprache or e.sprache
        ziel = Ziel(format=a.format or e.format)
        try:
            if a.art in ("vorlesen", "dialog"):
                if a.text is not None:
                    haupt = await plaene.text_anlegen(a.name or "Text", a.text)
                    text = a.text
                elif a.quelle_id is not None:
                    haupt = await kw.knoten(a.quelle_id)
                    text = (await kw.lesen_ganz(haupt.id)).decode("utf-8", "replace")
                else:
                    raise ValueError("Text oder Datei angeben")
                name = a.name or haupt.name.rsplit(".", 1)[0]
                plan = (planen.aus_text(name, text, vorgabe, sprache=sprache, ziel=ziel) if a.art == "vorlesen"
                        else planen.aus_dialog(name, text, a.stimmen, vorgabe, sprache=sprache, ziel=ziel))
            else:
                if a.quelle_id is None:
                    raise ValueError("Zeitgenau braucht ein Transkript oder Untertitel")
                textquelle = await kw.knoten(a.quelle_id)
                inhalt = (await kw.lesen_ganz(textquelle.id)).decode("utf-8", "replace")
                if textquelle.name.lower().endswith(UNTERTITEL):
                    segmente = planen.segmente_aus_untertiteln(inhalt)
                else:
                    segmente = planen.segmente_aus_transkript(json.loads(inhalt))
                haupt = await kw.knoten(textquelle.haupt_id) if textquelle.haupt_id else textquelle
                plan = planen.aus_segmenten(a.name or haupt.name.rsplit(".", 1)[0], segmente, a.stimmen, vorgabe,
                                            quelle=Quelle(knoten_id=haupt.id, pfad=haupt.pfad, etag=haupt.etag),
                                            quelle_dauer_s=haupt.felder.get("dauer_s"), sprache=sprache)
        except (ValueError, json.JSONDecodeError) as f:
            raise HTTPException(422, str(f)) from f
        if plan.quelle is None:
            plan.quelle = Quelle(knoten_id=haupt.id, pfad=haupt.pfad, etag=haupt.etag)
        knoten = await plaene.speichern(haupt.id, plan)
        await eintragen(plan, knoten, haupt, a.anfrage_id)
        return _antwort(plan, knoten, haupt)

    @r.get("/plaene/{plan_id}", response_model=PlanAntwort)
    async def lesen(plan_id: UUID, anfrage: UUID | None = None) -> PlanAntwort:
        plan, knoten = await teile.plaene_fuer(anfrage).lesen(plan_id)
        haupt = await teile.zugang(anfrage).knoten(knoten.haupt_id or plan.quelle.knoten_id)
        return _antwort(plan, knoten, haupt)

    @r.patch("/plaene/{plan_id}", response_model=PlanAntwort)
    async def aendern(plan_id: UUID, a: PlanAendern, anfrage: UUID | None = None, konto: Konto = g.pflicht) -> PlanAntwort:
        for rolle in a.plan.rollen:
            await teile.stimme_pruefen(rolle.stimme, konto)
        plaene = teile.plaene_fuer(anfrage)
        knoten = await plaene.schreiben(plan_id, a.plan, a.stand)
        haupt = await teile.zugang(anfrage).knoten(knoten.haupt_id or a.plan.quelle.knoten_id)
        await eintragen(a.plan, knoten, haupt, anfrage)
        return _antwort(a.plan, knoten, haupt)

    @r.post("/plaene/{plan_id}/vertonen", response_model=Auftrag, status_code=201)
    async def vertonen(plan_id: UUID, anfrage: UUID | None = None, konto: Konto = g.pflicht) -> Auftrag:
        plan, _ = await teile.plaene_fuer(anfrage).lesen(plan_id)
        for rolle in plan.rollen:
            await teile.stimme_pruefen(rolle.stimme, konto)
        eingabe = VertonenEingabe(plan_id=plan_id, anfrage_id=anfrage, von=von(konto))
        return await g.auftraege.einreihen("vertonen", eingabe, titel=plan.name)

    @r.delete("/plaene/{plan_id}", status_code=204)
    async def loeschen(plan_id: UUID, anfrage: UUID | None = None, konto: Konto = g.mensch) -> Response:
        await teile.plaene_fuer(anfrage).kw.loeschen(plan_id)
        await teile.verzeichnis.entfernen(plan_id)
        return Response(status_code=204)

    @r.get("/plaene/{plan_id}/eintrag", response_model=Eintrag | None)
    async def eintrag(plan_id: UUID) -> Eintrag | None:
        return await teile.verzeichnis.eintrag(plan_id)

    return r
