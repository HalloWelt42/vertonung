"""Übersetzen für die Vertonung (Regeln des Nutzers): vollständig und sinngetreu, nichts weglassen, nichts hinzufügen,
natürliche gesprochene Sprache. Jeder Abschnitt hat ein Zeichenbudget aus seinem Zeitfenster und dem gemessenen
Sprechtempo seiner Stimme: ein Ziel (passt mit unauffälligem Stauchen) und eine Grenze (passt mit dem stärksten
Stauchen). Knapper formulieren ist erlaubt, kürzen des Inhalts nie. Übersetzt wird in Fenstern mit den vorigen
Abschnitten als Zusammenhang, über die Leitstelle (Kette der App: das große Sprachmodell). Jede Antwort wird geprüft;
fehlt ein Abschnitt, wird er gezielt noch einmal angefragt, ist einer über der Grenze, wird er knapper erbeten (das
geht auch nach dem Sprechen, wenn ein Abschnitt trotz Stauchen nicht in seine Zeit passt)."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from appkern.leitstelle import Leitstelle, Nachricht

from .modell.plan import Plan, uebersetzungssumme

FENSTER = 12
ZUSAMMENHANG = 4
VERSUCHE = 3
KNAPPER_RUNDEN = 2           # so oft wird ein Abschnitt über der Grenze knapper erbeten
SPIELRAUM = 1.05             # so weit darf eine Antwort über der Grenze liegen, ohne dass nachgefragt wird
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
class Budget:
    ziel: int              # so viele Zeichen passen mit unauffälligem Stauchen
    grenze: int            # mehr passt auch mit dem stärksten Stauchen nicht


@dataclass(frozen=True)
class Stueck:
    nr: int
    original: str
    budget: Budget | None  # ohne Zeitfenster keine Grenze


@dataclass(frozen=True)
class Fassung:
    """Ein Abschnitt, der knapper werden soll."""

    nr: int
    original: str
    text: str
    grenze: int


def glaetten(text: str) -> str:
    for alt, neu in _GERADE.items():
        text = text.replace(alt, neu)
    return re.sub(r"\s+", " ", text).strip()


def zeitfenster(plan: Plan) -> dict[int, float]:
    """Zeit je Abschnitt bis zum nächsten (zeitgenau; so legt ihn auch die Zeitlage), ohne Zeiten kein Eintrag."""
    aus: dict[int, float] = {}
    a = plan.abschnitte
    for i, x in enumerate(a):
        if x.start is None or x.ende is None:
            continue
        bis = a[i + 1].start if i + 1 < len(a) and a[i + 1].start is not None else (plan.quelle_dauer_s or x.ende)
        aus[x.nr] = max(bis, x.ende) - x.start
    return aus


def budgets(plan: Plan, zeichen_je_s: dict[str, float], komfort: float, hoechstens: float) -> dict[int, Budget]:
    """Zeichenbudget je Abschnitt: Zeitfenster mal Sprechtempo seiner Rolle (je Rolle schon mit ihrem Tempo)."""
    aus: dict[int, Budget] = {}
    fenster = zeitfenster(plan)
    for x in plan.abschnitte:
        sekunden = fenster.get(x.nr)
        if sekunden is None:
            continue
        je_s = zeichen_je_s[x.rolle]
        aus[x.nr] = Budget(ziel=max(10, int(sekunden * je_s * komfort)), grenze=max(12, int(sekunden * je_s * hoechstens)))
    return aus


def anweisung(von: str, nach: str) -> str:
    q, z = SPRACHEN.get(von, von), SPRACHEN.get(nach, nach)
    return (f"Du übersetzt gesprochene Sprache aus dem {q}en ins {z}e für eine Vertonung. Regeln: Übersetze vollständig "
            f"und sinngetreu; lass nichts weg und füge nichts hinzu. Schreibe natürliche gesprochene Sprache, wie man sie "
            f"in einem {z}en Film oder einer Doku hört, mit korrekten Umlauten. Eigennamen, Marken und Titel bleiben. "
            f"Jeder Abschnitt nennt, wie viele Zeichen in seine Zeit passen: ziel_zeichen klingt natürlich, mehr als "
            f"grenze_zeichen passt nicht. Bleib unter der Grenze und möglichst nahe am Ziel, indem du knapp und "
            f"gesprochen formulierst (kurze Wörter, keine Füllwörter, Nebensätze straffen); den Inhalt kürzt du nie. "
            f"Die Abschnitte gehören zusammen: Bezüge, Anreden und "
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
        b = s.budget
        teile.append(json.dumps({"nr": s.nr, "ziel_zeichen": b.ziel if b else None, "grenze_zeichen": b.grenze if b else None,
                                 "text": s.original}, ensure_ascii=False))
    return "\n".join(teile)


def knapper_anweisung(von: str, nach: str) -> str:
    q, z = SPRACHEN.get(von, von), SPRACHEN.get(nach, nach)
    return (f"Du überarbeitest Übersetzungen aus dem {q}en ins {z}e für eine Vertonung. Jede ist zu lang für ihre Zeit. "
            f"Formuliere sie knapper, bis sie unter grenze_zeichen liegt: kurze Wörter, keine Füllwörter, Nebensätze "
            f"straffen, Wiederholungen zusammenziehen. Der Inhalt des Originals bleibt vollständig und sinngetreu; nichts "
            f"weglassen, nichts hinzufügen. Natürliche gesprochene Sprache mit korrekten Umlauten; Eigennamen, Marken und "
            f"Titel bleiben. Antworte nur mit JSON: je Abschnitt seine Nummer und den neuen Text.")


def knapper_text(fassungen: list[Fassung]) -> str:
    return "\n".join(json.dumps({"nr": f.nr, "grenze_zeichen": f.grenze, "jetzt_zeichen": len(f.text), "original": f.original,
                                 "uebersetzung": f.text}, ensure_ascii=False) for f in fassungen)


async def _antworten(ls: Leitstelle, system: str, nutzer: str, titel: str, gesucht: set[int]) -> dict[int, str]:
    """Eine Anfrage mit festem Antwortschema; liefert die Texte der gesuchten Nummern, die gekommen sind."""
    antwort = await ls.chat([Nachricht.system(system), Nachricht.nutzer(nutzer)], titel=titel, response_format=SCHEMA,
                            temperature=0.2)
    try:
        daten = json.loads(antwort.text)
    except json.JSONDecodeError:
        return {}
    aus: dict[int, str] = {}
    for e in daten.get("abschnitte") or []:
        nr, text = e.get("nr"), glaetten(str(e.get("text") or ""))
        if nr in gesucht and text:
            aus[nr] = text
    return aus


async def knapper_fassen(ls: Leitstelle, fassungen: list[Fassung], von: str, nach: str, titel: str) -> dict[int, str]:
    """Zu lange Abschnitte knapper erbitten (höchstens KNAPPER_RUNDEN Runden); geliefert wird je Abschnitt die kürzeste
    Fassung, die kürzer ist als die bisherige. Was nicht kürzer wird, fehlt im Ergebnis (dann bleibt der alte Text)."""
    beste: dict[int, str] = {}
    offen = {f.nr: f for f in fassungen}
    for _ in range(KNAPPER_RUNDEN):
        if not offen:
            break
        neu = await _antworten(ls, knapper_anweisung(von, nach), knapper_text(list(offen.values())), titel, set(offen))
        for nr, text in neu.items():
            f = offen[nr]
            if len(text) < len(beste.get(nr, f.text)):
                beste[nr] = text
            if len(beste.get(nr, f.text)) <= f.grenze * SPIELRAUM:
                del offen[nr]
            else:
                offen[nr] = Fassung(f.nr, f.original, beste.get(nr, f.text), f.grenze)
    return beste


async def fenster_uebersetzen(ls: Leitstelle, stuecke: list[Stueck], davor: list[tuple[str, str]], von: str, nach: str,
                              titel: str) -> dict[int, str]:
    offen = {s.nr: s for s in stuecke}
    fertig: dict[int, str] = {}
    for _ in range(VERSUCHE):
        if not offen:
            break
        neu = await _antworten(ls, anweisung(von, nach), anfrage_text(list(offen.values()), davor), titel, set(offen))
        for nr, text in neu.items():
            fertig[nr] = text
            del offen[nr]
    if offen:
        raise UebersetzungFehlt(f"Abschnitte {', '.join(str(n) for n in sorted(offen))} blieben unübersetzt")
    zu_lang = [Fassung(s.nr, s.original, fertig[s.nr], s.budget.grenze) for s in stuecke
               if s.budget and len(fertig[s.nr]) > s.budget.grenze * SPIELRAUM]
    if zu_lang:
        fertig |= await knapper_fassen(ls, zu_lang, von, nach, titel)
    return fertig


def zu_lang(plan: Plan, nummern: set[int], hoechstens: float) -> list[Fassung]:
    """Übersetzte Abschnitte, die gesprochen trotz stärkstem Stauchen nicht in ihre Zeit passen; die Grenze rechnet mit
    dem Tempo, in dem genau dieser Abschnitt gesprochen wurde (etwas Luft für Schwankungen beim nächsten Sprechen)."""
    fenster = zeitfenster(plan)
    aus: list[Fassung] = []
    for a in plan.abschnitte:
        sekunden = fenster.get(a.nr)
        if a.nr not in nummern or not a.original or not a.dauer_s or not sekunden:
            continue
        noetig = a.dauer_s / sekunden
        if noetig > hoechstens * SPIELRAUM:
            aus.append(Fassung(a.nr, a.original, a.text, max(12, int(len(a.text) * hoechstens / noetig * 0.95))))
    return aus


async def plan_uebersetzen(plan: Plan, ls: Leitstelle, *, zeichen_je_s: dict[str, float], komfort: float, hoechstens: float,
                           fortschritt: Callable[[float, str], Awaitable[None]], pruefen: Callable[[], Awaitable[None]],
                           merken: Callable[[Plan], Awaitable[None]]) -> list[int]:
    """Übersetzt alle Abschnitte, deren Original sich seit der letzten Übersetzung geändert hat; nach jedem Fenster wird
    der Plan gemerkt (fortsetzbar). Liefert die Nummern der übersetzten Abschnitte. `zeichen_je_s` je Rolle."""
    von, nach = plan.ausgangssprache or "en", plan.sprache
    offen = plan.zu_uebersetzen()
    if not offen:
        return []
    budget = budgets(plan, zeichen_je_s, komfort, hoechstens)
    nach_nr = {a.nr: a for a in plan.abschnitte}
    for i in range(0, len(offen), FENSTER):
        await pruefen()
        await fortschritt(i / len(offen), f"Übersetzen {i + 1} bis {min(i + FENSTER, len(offen))} von {len(offen)}")
        fenster = offen[i:i + FENSTER]
        erstes = plan.abschnitte.index(fenster[0])
        davor = [(a.original or "", a.text) for a in plan.abschnitte[max(0, erstes - ZUSAMMENHANG):erstes]
                 if a.original and not a.uebersetzung_noetig(nach)]
        ergebnis = await fenster_uebersetzen(ls, [Stueck(a.nr, a.original or "", budget.get(a.nr)) for a in fenster], davor,
                                             von, nach, titel=f"Vertonung: {plan.name} übersetzen")
        for nr, text in ergebnis.items():
            a = nach_nr[nr]
            a.text, a.uebersetzt_aus = text, uebersetzungssumme(a.original or "", nach)
        await merken(plan)
    return [a.nr for a in offen]
