"""Kern ohne Netz: Sätze und Stücke, Pläne aus Text, Dialog, Transkript und Untertiteln, Stand je Abschnitt,
Prüfen auf Aussetzer, Zeitlage, Fügen."""

import pytest

from app.modell.plan import StimmWahl
from app.planen import Segment, aus_dialog, aus_segmenten, aus_text, segmente_aus_untertiteln, zusammenfassen
from app.saetze import GRENZE, saetze, stuecke
from app.werk.pruefen import befund
from app.werk.zeitlage import Fenster, legen

SERENA = StimmWahl(art="katalog", name="serena")
AIDEN = StimmWahl(art="katalog", name="aiden")


def test_saetze_mit_abkuerzungen_und_absaetzen():
    text = ("Sehr geehrte Damen und Herren, die Abrechnung kam am 12. September. Das sind z. B. Grundsteuer, Müll usw. "
            "und anderes! Bitte prüfen Sie das bis Nr. 5?\n\nMit freundlichen Grüßen")
    s = saetze(text)
    assert [x.text for x in s] == [
        "Sehr geehrte Damen und Herren, die Abrechnung kam am 12. September.",
        "Das sind z. B. Grundsteuer, Müll usw. und anderes!",
        "Bitte prüfen Sie das bis Nr. 5?",
        "Mit freundlichen Grüßen"]
    assert [x.absatz_ende for x in s] == [False, False, True, True]


def test_stuecke_teilen_ohne_verlust():
    satz = ("Die Nachzahlung ist fast doppelt so hoch wie im Vorjahr, und aus der Abrechnung geht nicht hervor, welche "
            "Posten gestiegen sind, obwohl sich an der Wohnung und ihrer Nutzung nichts geändert hat - auch nicht an der "
            "Zahl der Bewohner, die seit Jahren gleich ist; das bitte ich zu berücksichtigen.")
    teile = stuecke(satz)
    assert len(teile) > 1 and all(len(t) <= GRENZE for t in teile)
    assert " ".join(teile) == satz
    lang = " ".join(["Donaudampfschifffahrtsgesellschaft"] * 12)
    assert all(len(t) <= 40 for t in stuecke(lang, 40)) and "".join(stuecke(lang, 40)).replace(" ", "") == lang.replace(" ", "")
    assert stuecke("kurz") == ["kurz"] and stuecke("  ") == []


def test_plan_vorlesen_und_stand():
    plan = aus_text("Brief", "Erster Satz. Zweiter Satz.\n\nDritter.", SERENA)
    assert [a.text for a in plan.abschnitte] == ["Erster Satz.", "Zweiter Satz.", "Dritter."]
    assert [a.pause_danach_s for a in plan.abschnitte] == [0.35, 0.8, 0.8]
    a = plan.abschnitte[0]
    assert plan.stand(a) == "offen"
    a.gesprochen_als = a.soll(plan.rolle("r1"), plan.sprache)
    assert plan.stand(a) == "gesprochen" and len(plan.zu_sprechen()) == 2
    plan.rollen[0].stimme = AIDEN                  # Stimme getauscht: der gesprochene gilt als geändert
    assert plan.stand(a) == "geaendert" and len(plan.zu_sprechen()) == 3
    with pytest.raises(ValueError):
        aus_text("leer", "  \n ", SERENA)


def test_plan_dialog():
    text = "Erzähler: Es ist kurz nach Mitternacht.\nMara: Hast du das gehört?\nDa war jemand.\nJonas: Das war der Wind."
    plan = aus_dialog("Szene", text, {"Mara": AIDEN}, SERENA)
    assert [(r.kennung, r.name, r.stimme.name) for r in plan.rollen] == [("r1", "Erzähler", "serena"), ("r2", "Mara", "aiden"),
                                                                         ("r3", "Jonas", "serena")]
    assert [(a.rolle, a.text) for a in plan.abschnitte] == [("r1", "Es ist kurz nach Mitternacht."),
                                                            ("r2", "Hast du das gehört? Da war jemand."),
                                                            ("r3", "Das war der Wind.")]
    with pytest.raises(ValueError):
        aus_dialog("x", "ohne Namen am Anfang", {}, SERENA)


def test_zusammenfassen_nach_den_regeln():
    s = [Segment(0.0, 2.0, "Guten Tag,", "Anna"), Segment(2.3, 4.0, "ich komme wegen der Abrechnung.", "Anna"),
         Segment(4.2, 6.0, "Das verstehe ich.", "Krüger"), Segment(6.5, 7.0, "Gut.", "Krüger"),
         Segment(10.0, 12.0, "Neuer Gedanke nach langer Pause", "Krüger"), Segment(12.1, 13.0, "der weitergeht.", "Krüger")]
    g = zusammenfassen(s)
    assert [(x.sprecher, x.text, x.start, x.ende) for x in g] == [
        ("Anna", "Guten Tag, ich komme wegen der Abrechnung.", 0.0, 4.0),
        ("Krüger", "Das verstehe ich. Gut.", 4.2, 7.0),            # kurz und gleicher Sprecher: angehängt
        ("Krüger", "Neuer Gedanke nach langer Pause der weitergeht.", 10.0, 13.0)]


def test_plan_zeitgenau_aus_untertiteln():
    srt = "1\n00:00:01,000 --> 00:00:03,500\n<i>Hallo zusammen,</i>\n\n2\n00:00:03,700 --> 00:00:06,000\nwillkommen zur Sendung.\n"
    seg = segmente_aus_untertiteln(srt)
    assert [(s.start, s.ende, s.text) for s in seg] == [(1.0, 3.5, "Hallo zusammen,"), (3.7, 6.0, "willkommen zur Sendung.")]
    plan = aus_segmenten("Sendung", seg, {}, SERENA, quelle=None, quelle_dauer_s=8.0)
    assert plan.art == "zeitgenau" and plan.ziel.format == "wie_quelle"
    assert [(a.start, a.ende, a.text) for a in plan.abschnitte] == [(1.0, 6.0, "Hallo zusammen, willkommen zur Sendung.")]
    vtt = "WEBVTT\n\n00:01.000 --> 00:02.500\nKurz.\n"
    assert segmente_aus_untertiteln(vtt)[0].ende == 2.5


def test_befund():
    assert befund("Hallo", 0.0, 0.5) == "aussetzer"
    assert befund("x" * 100, 2.0, 0.5) == "aussetzer"         # 100 Zeichen in 2 s geht nicht
    assert befund("Ja.", 9.0, 0.5) == "echo"
    assert befund("Das ist ein ganz normaler Satz mit etwas Länge.", 3.1, 0.4) == "gut"


def test_zeitlage():
    f = [Fenster(1.0, 3.0, 1.5),       # passt ins eigene Fenster
         Fenster(4.0, 5.0, 1.9),       # nutzt die Stille bis 6,0
         Fenster(6.0, 7.0, 2.3),       # 2,3 s bis 8,0 (minus Abstand): gestaucht
         Fenster(8.0, 9.0, 4.0),       # bis 10,0 höchstens 1,5: läuft hinüber
         Fenster(10.0, 11.0, 0.8)]     # muss warten: geschoben
    l = legen(f, quelle_ende=12.0)
    assert [x.weg for x in l] == ["frei", "luecke", "gestaucht", "gestaucht", "geschoben"]
    assert l[2].stauchung == pytest.approx(2.3 / 1.95, abs=1e-3) and l[3].stauchung == 1.5
    assert l[4].beginn == pytest.approx(8.0 + 4.0 / 1.5, abs=1e-3) and l[4].versatz_s > 0.6
    for a, b, fa in zip(l, l[1:], f):           # nie überlappend
        assert a.beginn + fa.dauer_s / a.stauchung <= b.beginn + 1e-6


def test_angaben_der_alten_stimmenausgabe_werden_umgestellt():
    from app.modell.stimme import aus_alter_app
    alt = {"format": "stimme-alt/1", "name": "Kerstin (Katalog)", "sprache": "german", "referenztext": "Guten Tag.",
           "herkunft": "extracted", "beschreibung": "", "alte_kennung": "abc"}
    a = aus_alter_app(alt, "fremd")
    assert (a.format, a.name, a.bereich, a.sprache, a.referenztext) == ("stimme/1", "Kerstin", "fremd", "de", "Guten Tag.")
    assert a.herkunft.art == "uebernommen" and "aus einer Aufnahme gewonnen" in a.notiz


async def test_gescheiterte_transkription_beendet_das_warten():
    import time
    from types import SimpleNamespace

    import pytest

    from app.dienst import TranskriptionGescheitert, transkript_abwarten

    class Kw:
        def __init__(self, zustaende):
            self.zustaende = zustaende

        async def begleiter(self, _):
            return []

        async def anfrage(self, _):
            return SimpleNamespace(zustand=self.zustaende.pop(0), meldung="Hördienst nicht erreichbar")

    async def nichts(*_, **__):
        return None
    k = SimpleNamespace(pruefen=nichts, fortschritt=nichts)
    with pytest.raises(TranskriptionGescheitert, match="Hördienst nicht erreichbar"):
        await transkript_abwarten(Kw(["laeuft", "fehler"]), "h", "a", time.time(), k, takt_s=0)


def test_klonmodus_nach_sprache_der_stimme():
    from pathlib import Path

    from app.sprechen import Katalogstimme, Klonstimme, mit_modus
    englisch = Klonstimme(referenz=Path("r.wav"), referenztext="Hello there.", sprache="en")
    assert mit_modus(englisch, "auto", "en", "abdruck").modus == "icl"          # gleiche Sprache: mit Referenztext
    assert mit_modus(englisch, "auto", "de", "abdruck").modus == "abdruck"      # fremde Sprache: nach Einstellung
    assert mit_modus(englisch, "icl", "de", "abdruck").modus == "icl"           # ausdrücklich gewählt
    ohne_text = Klonstimme(referenz=Path("r.wav"), referenztext=" ", sprache="de")
    assert mit_modus(ohne_text, "icl", "de", "icl").modus == "abdruck"          # ohne Text nie ICL
    assert mit_modus(Katalogstimme("serena"), "abdruck", "de", "icl") == Katalogstimme("serena")


def test_ohne_satzzeichen_keine_riesenabschnitte():
    from app.planen import ZUSAMMEN_HOECHSTENS_S, Segment, zusammenfassen
    segmente = [Segment(i * 20.0, i * 20.0 + 20.0, f"teil {i} ohne satzende", "s1") for i in range(10)]
    gruppen = zusammenfassen(segmente)
    assert len(gruppen) == 10 and all(g.ende - g.start <= ZUSAMMEN_HOECHSTENS_S for g in gruppen)
    kurz = [Segment(i * 4.0, i * 4.0 + 4.0, f"stück {i}", "s1") for i in range(10)]    # 40 s in Stücken von 4 s
    assert [round(g.ende - g.start) for g in zusammenfassen(kurz)] == [24, 16]
