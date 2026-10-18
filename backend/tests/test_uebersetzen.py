"""Übersetzen ohne Netz: Budget aus den Zeitfenstern, Glätten der Antwort, ein ausgelassener Abschnitt wird gezielt
nachgefragt, nur Geändertes wird neu übersetzt, und was nach allen Versuchen fehlt, bricht ab statt fremd zu sprechen."""

import json
from types import SimpleNamespace

import pytest

from app.modell.plan import StimmWahl
from app.planen import Segment, aus_segmenten
from app.uebersetzen import UebersetzungFehlt, budgets, glaetten, plan_uebersetzen

SERENA = StimmWahl(art="katalog", name="serena")


class Modell:
    """Übersetzt mit "DE: " davor; `auslassen` fehlen in der ersten Antwort, `nie` immer."""

    def __init__(self, auslassen=(), nie=()):
        self.anfragen: list[list[int]] = []
        self.auslassen, self.nie = set(auslassen), set(nie)

    async def chat(self, nachrichten, **_):
        stuecke = [json.loads(z) for z in nachrichten[-1].inhalt.splitlines() if z.startswith("{")]
        self.anfragen.append([s["nr"] for s in stuecke])
        aus = [{"nr": s["nr"], "text": f"DE: {s['text']}" + chr(0x2013)} for s in stuecke
               if s["nr"] not in self.nie and not (s["nr"] in self.auslassen and len(self.anfragen) == 1)]
        return SimpleNamespace(text=json.dumps({"abschnitte": aus}))


async def _nichts(*_):
    return None


def plan():
    seg = [Segment(0.0, 2.0, "Hello everyone.", "A"), Segment(2.5, 5.0, "Welcome to the show.", "B"),
           Segment(6.0, 9.0, "Today we talk about rent.", "A")]
    return aus_segmenten("Show", seg, {}, SERENA, quelle=None, quelle_dauer_s=12.0, sprache="de", ausgangssprache="en")


def test_budget_und_glaetten():
    p = plan()
    assert p.ausgangssprache == "en" and [a.original for a in p.abschnitte] == [a.text for a in p.abschnitte]
    assert budgets(p) == {1: 37, 2: 52, 3: 90}          # bis zum nächsten Abschnitt, der letzte bis zum Ende der Quelle
    assert glaetten(f"{chr(0x201E)}Ja{chr(0x201C)} {chr(0x2013)} gut{chr(0x2026)}") == '"Ja" - gut...'


async def test_uebersetzen_mit_nachfrage_und_nur_geaendertes():
    p = plan()
    m = Modell(auslassen={2})
    gemerkt = []

    async def merken(x):
        gemerkt.append(len(x.zu_uebersetzen()))

    p = await plan_uebersetzen(p, m, fortschritt=_nichts, pruefen=_nichts, merken=merken)
    assert m.anfragen == [[1, 2, 3], [2]]                   # der ausgelassene gezielt noch einmal
    assert [a.text for a in p.abschnitte] == ["DE: Hello everyone.-", "DE: Welcome to the show.-", "DE: Today we talk about rent.-"]
    assert p.zu_uebersetzen() == [] and gemerkt == [0]
    p.abschnitte[1].original = "Welcome back to the show."
    m2 = Modell()
    p = await plan_uebersetzen(p, m2, fortschritt=_nichts, pruefen=_nichts, merken=merken)
    assert m2.anfragen == [[2]] and p.abschnitte[1].text == "DE: Welcome back to the show.-"


async def test_fehlende_uebersetzung_bricht_ab():
    with pytest.raises(UebersetzungFehlt):
        await plan_uebersetzen(plan(), Modell(nie={3}), fortschritt=_nichts, pruefen=_nichts, merken=_nichts)
