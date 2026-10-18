"""Übersetzen für die Vertonung (Regeln des Nutzers): vollständig und sinngetreu, nichts weglassen, nichts hinzufügen,
natürliche gesprochene Sprache. Jeder Abschnitt hat ein Zeichenbudget aus seinem Zeitfenster (gesprochen werden etwa
15 Zeichen je Sekunde); knapper formulieren ist erlaubt, kürzen des Inhalts nie. Übersetzt wird in Fenstern mit den
vorigen Abschnitten als Zusammenhang, über die Leitstelle (Kette der App: das große Sprachmodell). Jede Antwort wird
geprüft; fehlt ein Abschnitt, wird er gezielt noch einmal angefragt."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from appkern.leitstelle import Leitstelle, Nachricht

from .modell.plan import Plan, uebersetzungssumme

ZEICHEN_JE_S = 15.0
FENSTER = 12
ZUSAMMENHANG = 4
VERSUCHE = 3
SPRACHEN = {"de": "Deutsch", "en": "Englisch", "fr": "Französisch", "es": "Spanisch", "it": "Italienisch", "nl": "Niederländisch",
            "pt": "Portugiesisch", "pl": "Polnisch", "ru": "Russisch", "tr": "Türkisch", "ja": "Japanisch", "zh": "Chinesisch"}
_GERADE = {chr(0x201C): '"', chr(0x201D): '"', chr(0x201E): '"', chr(0x00AB): '"', chr(0x00BB): '"', chr(0x2018): "'",
           chr(0x2019): "'", chr(0x201A): "'", chr(0x2013): "-", chr(0x2014): "-", chr(0x2026): "..."}
SCHEMA = {"type": "json_schema", "json_schema": {"name": "uebersetzung", "strict": True, "schema": {
    "type": "object", "additionalProperties": False, "required": ["abschnitte"],
    "properties": {"abschnitte": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["nr", "text"],
        "properties": {"nr": {"type": "integer"}, "text": {"type": "string"}}}}}}}}


class UebersetzungFehlt(Exception):
    """Abschnitte blieben nach allen Versuchen unübersetzt (lieber kein Ergebnis als fremde Sprache mit falscher Stimme)."""


@dataclass(frozen=True)
class Stueck:
    nr: int
    original: str
    budget: int            # Zeichen, die in das Zeitfenster passen


def glaetten(text: str) -> str:
    for alt, neu in _GERADE.items():
        text = text.replace(alt, neu)
    return re.sub(r"\s+", " ", text).strip()


def budgets(plan: Plan) -> dict[int, int]:
    """Zeichenbudget je Abschnitt aus dem Zeitfenster bis zum nächsten Abschnitt (zeitgenau), sonst ohne Grenze."""
    aus: dict[int, int] = {}
    a = plan.abschnitte
    for i, x in enumerate(a):
        if x.start is None or x.ende is None:
            aus[x.nr] = 0
            continue
        bis = a[i + 1].start if i + 1 < len(a) and a[i + 1].start is not None else (plan.quelle_dauer_s or x.ende)
        aus[x.nr] = max(10, int((max(bis, x.ende) - x.start) * ZEICHEN_JE_S))
    return aus


def anweisung(von: str, nach: str) -> str:
    q, z = SPRACHEN.get(von, von), SPRACHEN.get(nach, nach)
    return (f"Du übersetzt gesprochene Sprache aus dem {q}en ins {z}e für eine Vertonung. Regeln: Übersetze vollständig "
            f"und sinngetreu; lass nichts weg und füge nichts hinzu. Schreibe natürliche gesprochene Sprache, wie man sie "
            f"in einem {z}en Film oder einer Doku hört, mit korrekten Umlauten. Eigennamen, Marken und Titel bleiben. "
            f"Jeder Abschnitt hat ein Zeichenbudget: so viele Zeichen passen in seine Zeit. Bleib möglichst darunter, "
            f"indem du knapp formulierst; den Inhalt kürzt du nie. Die Abschnitte gehören zusammen: Bezüge, Anreden und "
            f"Begriffe bleiben über die Abschnitte gleich. Antworte nur mit JSON: je Abschnitt seine Nummer und den "
            f"übersetzten Text.")


def anfrage_text(stuecke: list[Stueck], davor: list[tuple[str, str]]) -> str:
    teile = []
    if davor:
        teile.append("Zusammenhang (schon übersetzt, nicht noch einmal übersetzen):")
        teile += [f"- {o}  =>  {u}" for o, u in davor]
        teile.append("")
    teile.append("Zu übersetzen:")
    for s in stuecke:
        teile.append(json.dumps({"nr": s.nr, "budget": s.budget or None, "text": s.original}, ensure_ascii=False))
    return "\n".join(teile)


async def fenster_uebersetzen(ls: Leitstelle, stuecke: list[Stueck], davor: list[tuple[str, str]], von: str, nach: str,
                              titel: str) -> dict[int, str]:
    offen = {s.nr: s for s in stuecke}
    fertig: dict[int, str] = {}
    for _ in range(VERSUCHE):
        if not offen:
            break
        antwort = await ls.chat([Nachricht.system(anweisung(von, nach)), Nachricht.nutzer(anfrage_text(list(offen.values()), davor))],
                                titel=titel, response_format=SCHEMA, temperature=0.2)
        try:
            daten = json.loads(antwort.text)
        except json.JSONDecodeError:
            continue
        for e in daten.get("abschnitte") or []:
            nr, text = e.get("nr"), glaetten(str(e.get("text") or ""))
            if nr in offen and text:
                fertig[nr] = text
                del offen[nr]
    if offen:
        raise UebersetzungFehlt(f"Abschnitte {', '.join(str(n) for n in sorted(offen))} blieben unübersetzt")
    return fertig


async def plan_uebersetzen(plan: Plan, ls: Leitstelle, *, fortschritt: Callable[[float, str], Awaitable[None]],
                           pruefen: Callable[[], Awaitable[None]], merken: Callable[[Plan], Awaitable[None]]) -> Plan:
    """Übersetzt alle Abschnitte, deren Original sich seit der letzten Übersetzung geändert hat; nach jedem Fenster wird
    der Plan gemerkt (fortsetzbar)."""
    von, nach = plan.ausgangssprache or "en", plan.sprache
    offen = plan.zu_uebersetzen()
    if not offen:
        return plan
    budget = budgets(plan)
    nach_nr = {a.nr: a for a in plan.abschnitte}
    for i in range(0, len(offen), FENSTER):
        await pruefen()
        await fortschritt(i / len(offen), f"Übersetzen {i + 1} bis {min(i + FENSTER, len(offen))} von {len(offen)}")
        fenster = offen[i:i + FENSTER]
        erstes = plan.abschnitte.index(fenster[0])
        davor = [(a.original or "", a.text) for a in plan.abschnitte[max(0, erstes - ZUSAMMENHANG):erstes]
                 if a.original and not a.uebersetzung_noetig(nach)]
        ergebnis = await fenster_uebersetzen(ls, [Stueck(a.nr, a.original or "", budget.get(a.nr, 0)) for a in fenster], davor,
                                             von, nach, titel=f"Vertonung: {plan.name} übersetzen")
        for nr, text in ergebnis.items():
            a = nach_nr[nr]
            a.text, a.uebersetzt_aus = text, uebersetzungssumme(a.original or "", nach)
        await merken(plan)
    return plan
