"""Vertonung als Dienst für andere Apps (vor allem TubeVault über ihren Nachvertoner): eine Aufnahme kommt mit Sprachen,
Stimme und auf Wunsch schon mit Segmenten; sie liegt danach in der Kellerwolke unter `Dienst/<App>` im Zweig der
Vertonung, Segmente als Transkript daneben. Ein Auftrag erledigt den Rest: fehlt der Text, gibt er das Transkribieren
an die Transkription weiter und wartet auf ihr Transkript; dann Plan zeitgenau (mit Übersetzung, wenn die Sprachen
abweichen), sprechen, Ergebnis neben die Aufnahme."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from appkern.auftraege import Kontext

from . import planen
from .ablage import orte
from .modell.plan import Quelle, StimmWahl, Ziel
from .teile import Teile

TEXTROLLEN = ("transkript", "untertitel", "untertitel_vtt")
WARTEN_S = 15
HOECHSTENS_WARTEN_S = 6 * 3600


class DienstSegment(BaseModel):
    start: float = Field(ge=0)
    ende: float = Field(ge=0)
    text: str
    sprecher: str | None = None


class DienstEingabe(BaseModel):
    haupt_id: UUID
    name: str
    ausgangssprache: str | None = None
    sprache: str = "de"
    stimme: StimmWahl | None = None             # eine Stimme für alle Sprecher (ohne: die Stimme ab Werk)
    format: Literal["wie_quelle", "m4a"] = "m4a"
    von: str | None = None


def transkript_aus_segmenten(name: str, haupt_id: UUID, pfad: str, segmente: list[DienstSegment], sprache: str | None,
                             app: str) -> bytes:
    """Ein Transkript im Format der Transkription (`transkript/1`), damit es auch dort lesbar ist."""
    namen = list(dict.fromkeys(s.sprecher or "Sprecher" for s in segmente))
    kennung = {n: f"s{i + 1}" for i, n in enumerate(namen)}
    jetzt = datetime.now(UTC).isoformat()
    t = {"format": "transkript/1", "name": name, "quelle": {"knoten_id": str(haupt_id), "pfad": pfad},
         "sprache": sprache or "auto", "dauer_s": max((s.ende for s in segmente), default=0.0),
         "erstellt_am": jetzt, "geaendert_am": jetzt,
         "sprecher": [{"kennung": kennung[n], "name": n} for n in namen],
         "segmente": [{"start": s.start, "ende": max(s.ende, s.start), "sprecher": kennung[s.sprecher or "Sprecher"], "text": s.text}
                      for s in segmente if s.text.strip()],
         "erzeugt_mit": {"dienst": app}, "aenderung": {"was": f"von {app} mitgegeben", "app": app}}
    return json.dumps(t, ensure_ascii=False, indent=1).encode("utf-8")


async def dienst_ausfuehren(teile: Teile, k: Kontext) -> dict:
    from .arten import plan_ausfuehren       # spät: arten bindet diesen Ablauf als Art ein

    e: DienstEingabe = k.eingabe
    kw = teile.zugang()
    plaene = teile.plaene
    await k.fortschritt(0.0, "Text suchen", phase="vorbereiten")
    haupt = await kw.knoten(e.haupt_id)
    text = next((b for b in await kw.begleiter(haupt.id) if b.rolle in TEXTROLLEN), None)
    if text is None:
        if "weitergegeben" not in k.zwischenstand:
            neu = await kw.weitergeben(teile.einstellungen.transkription_app, "transkribieren", haupt.id,
                                       {"sprache": e.ausgangssprache or "auto"})
            await k.merken(weitergegeben=str(neu.anfrage.id), seit=time.time())
        seit = float(k.zwischenstand.get("seit", time.time()))
        while text is None:
            await k.pruefen()
            if time.time() - seit > HOECHSTENS_WARTEN_S:
                raise TimeoutError("Die Transkription hat in sechs Stunden kein Transkript geliefert")
            await k.fortschritt(None, "Wartet auf das Transkript der Transkription", phase="vorbereiten")
            await asyncio.sleep(WARTEN_S)
            text = next((b for b in await kw.begleiter(haupt.id) if b.rolle in TEXTROLLEN), None)
    plan_id = k.zwischenstand.get("plan_id")
    if plan_id is None:
        inhalt = (await kw.lesen_ganz(text.id)).decode("utf-8", "replace")
        ausgang = e.ausgangssprache
        if text.name.lower().endswith((".srt", ".vtt")):
            segmente = planen.segmente_aus_untertiteln(inhalt)
        else:
            transkript = json.loads(inhalt)
            segmente = planen.segmente_aus_transkript(transkript)
            if ausgang is None and transkript.get("sprache") not in (None, "", "auto"):
                ausgang = transkript["sprache"]
        stimme = e.stimme or StimmWahl(art="katalog", name=teile.einstellungen.stimme_vorgabe)
        dauer = haupt.felder.get("dauer_s")
        plan = planen.aus_segmenten(e.name, segmente, {}, stimme, quelle=Quelle(knoten_id=haupt.id, pfad=haupt.pfad, etag=haupt.etag),
                                    quelle_dauer_s=float(dauer) if isinstance(dauer, (int, float)) else None, sprache=e.sprache,
                                    ziel=Ziel(format=e.format), ausgangssprache=ausgang)
        knoten = await plaene.speichern(haupt.id, plan)
        await teile.verzeichnis.eintragen(plan, knoten.id, haupt.id, haupt.pfad,
                                          await teile.stimmen_namen([r.stimme for r in plan.rollen]))
        plan_id = str(knoten.id)
        await k.merken(plan_id=plan_id)
        await teile.dienstablage.plan_merken(k.auftrag_id, plan_id)
    ergebnis = await plan_ausfuehren(teile, k, UUID(plan_id), None)
    return {**ergebnis, "plan_id": plan_id}


async def ablegen(teile: Teile, app: str, name: str, endung: str, datei, segmente: list[DienstSegment] | None,
                  ausgangssprache: str | None):
    """Aufnahme (und Segmente als Transkript) nach Dienst/<App>/ im Zweig der Vertonung; liefert den Knoten."""
    kw = teile.zugang()
    zweig = (await kw.ich()).zweig
    ordner = await kw.ordner(orte.ort(zweig, orte.DIENST, orte.dateiname(app)))
    stamm = orte.dateiname(name)
    haupt = None
    for n in range(1, 100):
        versuch = stamm if n == 1 else f"{stamm} ({n})"
        if await kw.finden(f"{ordner.pfad}/{versuch}{endung}") is None:
            haupt = await kw.schreiben(f"{ordner.pfad}/{versuch}{endung}", datei, nur_neu=True)
            break
    if haupt is None:
        raise ValueError("Kein freier Name für die Aufnahme")
    if segmente:
        await kw.begleiter_schreiben(haupt.id, "transkript", ".transkript.json",
                                     transkript_aus_segmenten(name, haupt.id, haupt.pfad, segmente, ausgangssprache, app),
                                     nur_neu=True, inhaltstyp=orte.JSON)
    return haupt
