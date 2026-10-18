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
