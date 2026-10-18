"""Vergleich der Übersetzungsmodelle (docs/OPTIMIERUNG.md, Strecke 1): dieselben Abschnitte eines Plans mit denselben
Anweisungen und Budgets je Modell übersetzen. Gemessen werden Dauer, Abschnitte über der Zeichengrenze, wie oft knapper
nachgefragt wurde und die Vollständigkeit (ein Gutachter-Modell prüft je Abschnitt, ob etwas fehlt oder hinzugedichtet
ist). Läuft im Container der App; Adresse und Schlüssel der Leitstelle kommen aus der Umgebung der App.

    python -m app.messung.vergleich <plan.json> --modelle qwen/qwen3-next-80b,qwen/qwen3.8-27b --tempo 17 \\
        [--gutachter qwen/qwen3-next-80b] [--aus ergebnis.json]
    python -m app.messung.vergleich <plan.json> --begutachten ergebnis.json --gutachter qwen/qwen3.6-35b-a3b

Ein Gutachter, der seine eigene Übersetzung prüft, sieht eigene Kürzungen nicht (Messung 18.10.2026); daher lässt sich
eine fertige Messung mit einem anderen Gutachter erneut begutachten.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

from appkern.leitstelle import Leitstelle, Nachricht

from ..einstellungen import AppEinstellungen
from ..modell.plan import Plan
from ..uebersetzen import FENSTER, SPIELRAUM, Stueck, budgets, fenster_uebersetzen, glaetten

GUTACHTEN = {"type": "json_schema", "json_schema": {"name": "gutachten", "strict": True, "schema": {
    "type": "object", "additionalProperties": False, "required": ["abschnitte"],
    "properties": {"abschnitte": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["nr", "vollstaendig", "fehlt", "hinzu"],
        "properties": {"nr": {"type": "integer"}, "vollstaendig": {"type": "boolean"}, "fehlt": {"type": "string"},
                       "hinzu": {"type": "string"}}}}}}}}


class Zaehler:
    """Reicht an die Leitstelle durch und zählt Übersetzungs- und Knapper-Anfragen."""

    def __init__(self, ls: Leitstelle) -> None:
        self.ls, self.uebersetzen, self.knapper = ls, 0, 0

    async def chat(self, nachrichten, **weiter):
        if nachrichten[0].inhalt.startswith("Du überarbeitest"):
            self.knapper += 1
        else:
            self.uebersetzen += 1
        return await self.ls.chat(nachrichten, **weiter)


async def gutachten(ls: Leitstelle, modell: str | None, paare: list[tuple[int, str, str]]) -> dict[int, dict]:
    system = ("Du prüfst Übersetzungen aus dem Englischen ins Deutsche für eine Vertonung. Knapper formulieren ist "
              "erlaubt. Prüfe je Abschnitt nur: Fehlt eine Aussage des Originals (fehlt), oder steht etwas da, das im "
              "Original nicht vorkommt (hinzu)? Nenne beides kurz, sonst leer. vollstaendig ist true, wenn nichts "
              "Inhaltliches fehlt und nichts hinzugedichtet ist. Antworte nur mit JSON.")
    nutzer = "\n".join(json.dumps({"nr": nr, "original": o, "uebersetzung": u}, ensure_ascii=False) for nr, o, u in paare)
    antwort = await ls.chat([Nachricht.system(system), Nachricht.nutzer(nutzer)], titel="Vertonung: Gutachten",
                            modell=modell, response_format=GUTACHTEN, temperature=0.0)
    return {e["nr"]: e for e in json.loads(antwort.text).get("abschnitte") or []}


async def messen(plan: Plan, ls: Leitstelle, modell: str, tempo: float, einst: AppEinstellungen) -> dict:
    je_s = {r.kennung: tempo * r.tempo for r in plan.rollen}
    budget = budgets(plan, je_s, einst.komfort, einst.hoechstens)
    z = Zaehler(ls)
    texte: dict[int, str] = {}
    beginn = time.monotonic()
    abschnitte = [a for a in plan.abschnitte if a.original]
    for i in range(0, len(abschnitte), FENSTER):
        fenster = abschnitte[i:i + FENSTER]
        davor = [(a.original or "", texte[a.nr]) for a in abschnitte[max(0, i - 4):i] if a.nr in texte]
        texte |= await fenster_uebersetzen(z, [Stueck(a.nr, a.original or "", budget.get(a.nr)) for a in fenster], davor,
                                           plan.ausgangssprache or "en", plan.sprache, f"Vergleich {modell}", modell=modell)
    dauer = time.monotonic() - beginn
    ueber = [a.nr for a in abschnitte if budget.get(a.nr) and len(texte[a.nr]) > budget[a.nr].grenze * SPIELRAUM]
    return {"modell": modell, "dauer_s": round(dauer, 1), "abschnitte": len(abschnitte), "ueber_grenze": ueber,
            "anfragen": z.uebersetzen, "knapper": z.knapper,
            "zeichen_zu_grenze": round(sum(len(texte[a.nr]) / budget[a.nr].grenze for a in abschnitte if budget.get(a.nr))
                                       / max(1, len(abschnitte)), 3),
            "texte": {a.nr: glaetten(texte[a.nr]) for a in abschnitte}}


async def begutachten(plan: Plan, ls: Leitstelle, datei: Path, gutachter: str) -> None:
    originale = {a.nr: a.original or "" for a in plan.abschnitte}
    ergebnisse = json.loads(datei.read_text())
    for e in ergebnisse:
        if not e.get("texte"):
            continue
        texte = {int(nr): t for nr, t in e["texte"].items()}
        g = await gutachten(ls, gutachter, [(nr, originale[nr], t) for nr, t in texte.items()])
        voll = round(sum(1 for x in g.values() if x.get("vollstaendig")) / max(1, len(texte)), 3)
        e.setdefault("gutachten", {})[gutachter] = {"vollstaendig": voll, "maengel": {
            nr: {"fehlt": x.get("fehlt"), "hinzu": x.get("hinzu")} for nr, x in g.items() if not x.get("vollstaendig")}}
        print(f"{e['modell']:28} nach {gutachter}: vollständig {voll:.0%}", flush=True)
    datei.write_text(json.dumps(ergebnisse, ensure_ascii=False, indent=1))


async def haupt(args) -> None:
    plan = Plan.model_validate(json.loads(Path(args.plan).read_text())["plan"])
    einst = AppEinstellungen()
    ls = Leitstelle(os.environ["VERTONUNG_LEITSTELLE_ADRESSE"], os.environ["VERTONUNG_LEITSTELLE_SCHLUESSEL"], "Vertonung")
    if args.begutachten:
        try:
            await begutachten(plan, ls, Path(args.begutachten), args.gutachter)
        finally:
            await ls.schliessen()
        return
    try:
        ergebnisse = []
        for modell in args.modelle.split(","):
            try:
                e = await messen(plan, ls, modell.strip(), args.tempo, einst)
            except Exception as f:  # noqa: BLE001 - ein Modell, das scheitert, ist selbst ein Messergebnis
                e = {"modell": modell.strip(), "fehler": f"{type(f).__name__}: {f}"}
                print(f"{e['modell']:28} gescheitert: {e['fehler'][:150]}", flush=True)
            else:
                # Scheitert der Gutachter, bleibt die Übersetzung (begutachten lässt sich später mit --begutachten)
                try:
                    originale = {a.nr: a.original or "" for a in plan.abschnitte}
                    g = await gutachten(ls, args.gutachter, [(nr, originale[nr], t) for nr, t in e["texte"].items()])
                    e["vollstaendig"] = round(sum(1 for x in g.values() if x.get("vollstaendig")) / max(1, len(e["texte"])), 3)
                    e["maengel"] = {nr: {"fehlt": x.get("fehlt"), "hinzu": x.get("hinzu")} for nr, x in g.items()
                                    if not x.get("vollstaendig")}
                except Exception as f:  # noqa: BLE001
                    e["gutachten_fehler"] = f"{type(f).__name__}: {f}"[:300]
                voll = f"vollständig {e['vollstaendig']:.0%}" if "vollstaendig" in e else "Gutachten gescheitert"
                print(f"{e['modell']:28} {e['dauer_s']:7.1f} s  über Grenze {len(e['ueber_grenze'])}/{e['abschnitte']}  "
                      f"knapper {e['knapper']}  Zeichen/Grenze {e['zeichen_zu_grenze']:.2f}  {voll}", flush=True)
            ergebnisse.append(e)
            if args.aus:
                Path(args.aus).write_text(json.dumps(ergebnisse, ensure_ascii=False, indent=1))
    finally:
        await ls.schliessen()


def main() -> None:
    p = argparse.ArgumentParser(description="Übersetzungsmodelle vergleichen")
    p.add_argument("plan")
    p.add_argument("--modelle", help="Modelle zum Übersetzen, durch Kommas getrennt")
    p.add_argument("--tempo", type=float, default=17.0, help="Sprechtempo der Stimme in Zeichen je Sekunde")
    p.add_argument("--begutachten", help="nur eine fertige Messung (JSON) mit --gutachter erneut begutachten")
    p.add_argument("--gutachter", default="qwen/qwen3-next-80b")
    p.add_argument("--aus")
    args = p.parse_args()
    if not (args.modelle or args.begutachten):
        p.error("--modelle oder --begutachten angeben")
    asyncio.run(haupt(args))


if __name__ == "__main__":
    main()
