"""Übersetzen ohne Netz: Budget aus Zeitfenstern und Sprechtempo, Glätten der Antwort, ein ausgelassener Abschnitt wird
gezielt nachgefragt, ein zu langer knapper erbeten, nur Geändertes wird neu übersetzt, und was nach allen Versuchen
fehlt, bricht ab statt fremd zu sprechen. Gesprochenes, das trotz Stauchen nicht passt, wird zum Nachfassen erkannt."""

import json
from types import SimpleNamespace

import pytest

from app.modell.plan import StimmWahl
from app.planen import Segment, aus_segmenten
from app.uebersetzen import Budget, UebersetzungFehlt, budgets, glaetten, plan_uebersetzen, zu_lang

SERENA = StimmWahl(art="katalog", name="serena")


class Modell:
    """Übersetzt mit "DE: " davor; `auslassen` fehlen in der ersten Antwort, `nie` immer, `lang` kommen zu lang (fünfmal
    der Text) und werden auf Bitte knapper ("kurz <nr>")."""

    def __init__(self, auslassen=(), nie=(), lang=()):
        self.anfragen: list[list[int]] = []
        self.knapper: list[list[int]] = []
        self.auslassen, self.nie, self.lang = set(auslassen), set(nie), set(lang)

    async def chat(self, nachrichten, **_):
        stuecke = [json.loads(z) for z in nachrichten[-1].inhalt.splitlines() if z.startswith("{")]
        if nachrichten[0].inhalt.startswith("Du überarbeitest"):
            self.knapper.append([s["nr"] for s in stuecke])
            return SimpleNamespace(text=json.dumps({"abschnitte": [{"nr": s["nr"], "text": f"kurz {s['nr']}"} for s in stuecke]}))
        self.anfragen.append([s["nr"] for s in stuecke])
        aus = [{"nr": s["nr"], "text": f"DE: {s['text'] * (5 if s['nr'] in self.lang else 1)}" + chr(0x2013)} for s in stuecke
               if s["nr"] not in self.nie and not (s["nr"] in self.auslassen and len(self.anfragen) == 1)]
        return SimpleNamespace(text=json.dumps({"abschnitte": aus}))


async def _nichts(*_):
    return None


TEMPO = {"r1": 10.0, "r2": 10.0}


async def uebersetzen(p, m, merken=_nichts):
    return await plan_uebersetzen(p, m, zeichen_je_s=TEMPO, komfort=1.15, hoechstens=1.5, fortschritt=_nichts,
                                  pruefen=_nichts, merken=merken)


def plan():
    seg = [Segment(0.0, 2.0, "Hello everyone.", "A"), Segment(2.5, 5.0, "Welcome to the show.", "B"),
           Segment(6.0, 9.0, "Today we talk about rent.", "A")]
    return aus_segmenten("Show", seg, {}, SERENA, quelle=None, quelle_dauer_s=12.0, sprache="de", ausgangssprache="en")


def test_budget_und_glaetten():
    p = plan()
    assert p.ausgangssprache == "en" and [a.original for a in p.abschnitte] == [a.text for a in p.abschnitte]
    # Fenster bis zum nächsten Abschnitt (2,5 / 3,5 / 6 s, der letzte bis zum Ende der Quelle) mal 10 Zeichen je Sekunde
    assert budgets(p, TEMPO, 1.15, 1.5) == {1: Budget(28, 37), 2: Budget(40, 52), 3: Budget(69, 90)}
    assert glaetten(f"{chr(0x201E)}Ja{chr(0x201C)} {chr(0x2013)} gut{chr(0x2026)}") == '"Ja" - gut...'


async def test_uebersetzen_mit_nachfrage_und_nur_geaendertes():
    p = plan()
    m = Modell(auslassen={2})
    gemerkt = []

    async def merken(x):
        gemerkt.append(len(x.zu_uebersetzen()))

    assert await uebersetzen(p, m, merken) == [1, 2, 3]
    assert m.anfragen == [[1, 2, 3], [2]] and m.knapper == []   # der ausgelassene gezielt noch einmal
    assert [a.text for a in p.abschnitte] == ["DE: Hello everyone.-", "DE: Welcome to the show.-", "DE: Today we talk about rent.-"]
    assert p.zu_uebersetzen() == [] and gemerkt == [0]
    p.abschnitte[1].original = "Welcome back to the show."
    m2 = Modell()
    assert await uebersetzen(p, m2, merken) == [2]
    assert m2.anfragen == [[2]] and p.abschnitte[1].text == "DE: Welcome back to the show.-"


async def test_fehlende_uebersetzung_bricht_ab():
    with pytest.raises(UebersetzungFehlt):
        await uebersetzen(plan(), Modell(nie={3}))


async def test_zu_lange_uebersetzung_wird_knapper_erbeten():
    p = plan()
    m = Modell(lang={1})
    await uebersetzen(p, m)
    assert m.knapper == [[1]] and p.abschnitte[0].text == "kurz 1"      # 79 Zeichen über der Grenze von 37


def test_zu_lang_gesprochenes_wird_erkannt():
    p = plan()
    for a, dauer in zip(p.abschnitte, (5.0, 3.6, 4.0)):
        a.text, a.dauer_s = "x" * 50, dauer
    lang = zu_lang(p, {1, 2, 3}, 1.5)
    # 5 s in 2,5 s braucht zweifach: knapper auf 50 * 1,5 / 2 * 0,95 Zeichen; 3,6 s in 3,5 s und 4 s in 6 s passen
    assert [(f.nr, f.grenze) for f in lang] == [(1, 35)]
    assert zu_lang(p, {2, 3}, 1.5) == []                                 # nur Abschnitte, die dieser Lauf übersetzt hat
