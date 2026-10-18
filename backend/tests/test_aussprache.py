"""Ausspracheprüfung: Vergleich ohne Satzzeichen und Groß- und Kleinschreibung, Quote aus ersetzten, fehlenden und
zusätzlichen Wörtern, die Abweichungen lesbar."""

from app.aussprache import abgleichen, woerter
from app.modell.plan import AUSSPRACHE_HINWEIS, Bericht


def test_gleich_ist_null():
    assert woerter("Open-Source, SQL/NoSQL!") == ["open", "source", "sql", "nosql"]
    assert abgleichen("PostgreSQL ist schnell.", "postgresql ist schnell").quote == 0.0


def test_abweichungen_und_quote():
    a = abgleichen("Er nutzt zweiundvierzig Tabellen heute", "er nutzt 42 tabellen")
    assert a.quote == 0.4 and a.abweichungen == ["zweiundvierzig -> 42", "heute -> (fehlt)"]
    assert abgleichen("", "irgendwas").quote == 0.0
    assert abgleichen("die objektrelationale Datenbank mit Auto Scaling", "die objekt relationale datenbank mit autoscaling").quote == 0.0


def test_hinweis_ab_der_schwelle():
    assert not Bericht(aussprache=AUSSPRACHE_HINWEIS).mit_hinweis
    assert Bericht(aussprache=AUSSPRACHE_HINWEIS + 0.01).mit_hinweis and Bericht(versatz_s=0.4).mit_hinweis


def test_spannen_und_hoerstuecke():
    from app.aussprache import stuecke
    from app.werk.zeitlage import spannen
    from app.modell.plan import Bericht
    from app.planen import Segment, aus_segmenten
    from app.modell.plan import StimmWahl
    seg = [Segment(0.0, 10.0, "Eins.", "A"), Segment(200.0, 210.0, "Zwei.", "A"), Segment(400.0, 405.0, "Drei.", "A")]
    p = aus_segmenten("P", seg, {}, StimmWahl(art="katalog", name="serena"), quelle=None, quelle_dauer_s=420.0)
    for a, (dauer, stauchung, versatz) in zip(p.abschnitte, [(12.0, 1.2, 0.0), (8.0, 1.0, 0.5), (5.0, 1.0, 0.0)]):
        a.dauer_s, a.bericht = dauer, Bericht(stauchung=stauchung, versatz_s=versatz)
    sp = spannen(p)
    assert [(s.von, s.bis) for s in sp] == [(0.0, 10.0), (200.5, 208.5), (400.0, 405.0)]
    assert stuecke(sp, 420.0) == [(0.0, 200.5), (200.5, 420.0)]          # je höchstens 300 s, am Abschnittsbeginn
    assert stuecke(sp[:1], 700.0) == [(0.0, 300.0), (300.0, 600.0), (600.0, 700.0)]   # lange Stille: nach 300 s


def test_gesamtquote_nach_woertern_gewichtet():
    """K3c: ein verhörter Einwurf aus einem Wort trieb das einfache Mittel hoch; gewichtet zählt er ein Wort."""
    from app.modell.plan import Abschnitt, Plan, Rolle, StimmWahl

    def abschnitt(nr: int, quote: float, woerter: int | None) -> Abschnitt:
        return Abschnitt(nr=nr, rolle="r1", text="x", bericht=Bericht(aussprache=quote, woerter=woerter))

    rollen = [Rolle(kennung="r1", name="A", stimme=StimmWahl(art="katalog", name="serena"))]

    plan = Plan(art="vorlesen", name="Probe", rollen=rollen,
                abschnitte=[abschnitt(1, 0.0, 40), abschnitt(2, 1.0, 1), abschnitt(3, 0.05, 20)])
    bild = plan.aussprache
    assert bild is not None and bild.quote == round((0 + 1 + 1) / 61, 3) and bild.auffaellig == 1 and bild.geprueft == 3
    assert plan.model_dump(mode="json")["aussprache"]["quote"] == bild.quote, "geht mit an die Oberfläche"
    assert abgleichen("Ja genau", "ja genau").woerter == 2
    alt = Plan(art="vorlesen", name="Alt", rollen=rollen, abschnitte=[abschnitt(1, 0.2, None), abschnitt(2, 0.0, None)])
    assert alt.aussprache.quote == 0.1, "ältere Berichte ohne Wortzahl zählen je Abschnitt einmal"
    assert Plan(art="vorlesen", name="Leer", rollen=rollen).aussprache is None
