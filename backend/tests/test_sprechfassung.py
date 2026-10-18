"""Sprechfassung: Zahlen, Jahre, Uhrzeiten, Daten, Prozente, Beträge, Einheiten, Versionen und Spannen werden
sprechbar; Wörter mit Ziffern und Anglizismen bleiben."""

import pytest

from app.sprechfassung import regeln


@pytest.mark.parametrize("text, gesprochen", [
    ("Seine Entwicklung begann 1986 an der UC Berkeley.", "Seine Entwicklung begann neunzehnhundertsechsundachtzig an der UC Berkeley."),
    ("Es hat 1200 Zeilen.", "Es hat tausendzweihundert Zeilen."),
    ("Um 10:30 und um 9:00", "Um zehn Uhr dreißig und um neun Uhr"),
    ("am 12.3.2026", "am zwölften März zweitausendsechsundzwanzig"),
    ("Der 3.10.1990 war ein Mittwoch", "Der dritte Oktober neunzehnhundertneunzig war ein Mittwoch"),
    ("50 % schneller, 3,5 % mehr", "fünfzig Prozent schneller, drei Komma fünf Prozent mehr"),
    ("kostet 5 $ oder 4,99 €", "kostet fünf Dollar oder vier Komma neun neun Euro"),
    ("16 GB RAM und 500 ms", "sechzehn Gigabyte RAM und fünfhundert Millisekunden"),
    ("PostgreSQL 16.2 ist da", "PostgreSQL sechzehn Punkt zwei ist da"),
    ("1.234 Nutzer", "tausendzweihundertvierunddreißig Nutzer"),
    ("10-20 Minuten", "zehn bis zwanzig Minuten"),
    ("Qwen3 und MP3 bleiben", "Qwen3 und MP3 bleiben"),
    ("ACID-konforme Snapshots", "ACID-konforme Snapshots"),
])
def test_regeln(text, gesprochen):
    assert regeln(text) == gesprochen
