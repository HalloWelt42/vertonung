"""Sprechfassung: Zahlen, Jahre, Uhrzeiten, Daten, Ordnungszahlen, Prozente, Beträge, Einheiten, Abkürzungen,
Versionen und Spannen werden sprechbar; Wörter mit Ziffern und Anglizismen bleiben. Grundlage sind auch die Fälle der
Vorlese-Fassung von Rufzeichen (dort "dritte September" ohne Artikel, hier richtig "dritter" und "am dritten")."""

import pytest

from app.sprechfassung import hat_worte, regeln, sprechbar


@pytest.mark.parametrize("text, gesprochen", [
    # Zahlen und Jahre
    ("Seine Entwicklung begann 1986 an der UC Berkeley.", "Seine Entwicklung begann neunzehnhundertsechsundachtzig an der UC Berkeley."),
    ("Es hat 1200 Zeilen.", "Es hat tausendzweihundert Zeilen."),
    ("1.234 Nutzer", "tausendzweihundertvierunddreißig Nutzer"),
    ("17 mal 23 ergibt 391", "siebzehn mal dreiundzwanzig ergibt dreihunderteinundneunzig"),
    ("genau 1,5 Liter", "genau eins Komma fünf Liter"),
    ("im Jahr 2026", "im Jahr zweitausendsechsundzwanzig"),
    ("Im Jahr 2026 kam er.", "Im Jahr zweitausendsechsundzwanzig kam er."),
    ("seit 2020 gibt es", "seit zweitausendzwanzig gibt es"),
    ("10-20 Minuten", "zehn bis zwanzig Minuten"),
    ("10" + chr(0x2013) + "20 Minuten", "zehn bis zwanzig Minuten"),
    ("-5 °C bis 10 °C", "minus fünf Grad Celsius bis zehn Grad Celsius"),
    # Uhrzeit
    ("Um 10:30 und um 9:00", "Um zehn Uhr dreißig und um neun Uhr"),
    ("14:30 Uhr", "vierzehn Uhr dreißig"),
    ("um 14:57 Uhr", "um vierzehn Uhr siebenundfünfzig"),
    ("um 14.30 Uhr", "um vierzehn Uhr dreißig"),
    ("um 1:00 und um 9 Uhr", "um ein Uhr und um neun Uhr"),
    # Datum und Ordnungszahlen
    ("am 3. September", "am dritten September"),
    ("der 3. September 2026", "der dritte September zweitausendsechsundzwanzig"),
    ("Montag, 3. September", "Montag, dritter September"),
    ("Montag, den 3. September", "Montag, den dritten September"),
    ("am 1. Mai", "am ersten Mai"),
    ("vom 3. bis 5. Okt. 2026", "vom dritten bis fünften Oktober zweitausendsechsundzwanzig"),
    ("bis zum 24. Dezember", "bis zum vierundzwanzigsten Dezember"),
    ("am 12.3.2026", "am zwölften März zweitausendsechsundzwanzig"),
    ("Der 3.10.1990 war ein Mittwoch", "Der dritte Oktober neunzehnhundertneunzig war ein Mittwoch"),
    ("im 3. Stock", "im dritten Stock"),
    ("der 2. Weltkrieg", "der zweite Weltkrieg"),
    ("Das 20. Jahrhundert", "Das zwanzigste Jahrhundert"),
    ("zur 5. Sitzung", "zur fünften Sitzung"),
    # Prozent, Geld
    ("50 % schneller, 3,5 % mehr", "fünfzig Prozent schneller, drei Komma fünf Prozent mehr"),
    ("3,5 %", "drei Komma fünf Prozent"),
    ("1 % Zins", "ein Prozent Zins"),
    ("13.439,16 €", "dreizehntausendvierhundertneununddreißig Euro sechzehn"),
    ("aus 10.000 Euro wurden 13.439,16 Euro", "aus zehntausend Euro wurden dreizehntausendvierhundertneununddreißig Euro sechzehn"),
    ("kostet 5 $ oder 4,99 €", "kostet fünf Dollar oder vier Euro neunundneunzig"),
    ("€ 12,50 und 0,50 €", "zwölf Euro fünfzig und fünfzig Cent"),
    ("1 € und 21,00 EUR", "ein Euro und einundzwanzig Euro"),
    ("2 Mio. € Umsatz", "zwei Millionen Euro Umsatz"),
    ("$5 und 5 USD", "fünf Dollar und fünf Dollar"),
    # Einheiten
    ("12 km/h", "zwölf Kilometer pro Stunde"),
    ("1.000 m²", "tausend Quadratmeter"),
    ("16 GB RAM und 500 ms", "sechzehn Gigabyte RAM und fünfhundert Millisekunden"),
    ("heute 22,0 °C", "heute zweiundzwanzig Komma null Grad Celsius"),
    ("1 s, 1 h und 1,5 h", "eine Sekunde, eine Stunde und eins Komma fünf Stunden"),
    ("101 m", "hundertein Meter"),
    ("1013 hPa", "tausenddreizehn Hektopascal"),
    # Abkürzungen und Zeichen
    ("Das ist z. B. wichtig.", "Das ist zum Beispiel wichtig."),
    ("Z.B. so", "Zum Beispiel so"),
    ("d.h. und u. a.", "das heißt und unter anderem."),   # am Ende bleibt der Satzpunkt
    ("Äpfel, Birnen usw.", "Äpfel, Birnen und so weiter."),
    ("Nr. 5", "Nummer fünf"),
    ("für Dr. Meier, ca. 3 Tage", "für Doktor Meier, circa drei Tage"),
    ("§ 3 Abs. 2", "Paragraf drei Absatz zwei"),
    ("siehe S. 12", "siehe Seite zwölf"),
    ("Fisch & Chips", "Fisch und Chips"),
    ("max. 5 Leute", "maximal fünf Leute"),
    ("Max. Er ging.", "Max. Er ging."),
    # bleibt
    ("PostgreSQL 16.2 ist da", "PostgreSQL sechzehn Punkt zwei ist da"),
    ("Fassung 0.12.0", "Fassung null Punkt zwölf Punkt null"),
    ("Qwen3 und MP3 bleiben", "Qwen3 und MP3 bleiben"),
    ("ACID-konforme Snapshots", "ACID-konforme Snapshots"),
    ("Ein Satz ohne Zahlen.", "Ein Satz ohne Zahlen."),
])
def test_regeln(text, gesprochen):
    assert regeln(text) == gesprochen


def test_nur_deutsch_und_leeres():
    assert sprechbar("It costs 5 $", "en") == "It costs 5 $"
    assert sprechbar("Es kostet 5 $", "de") == "Es kostet fünf Dollar"
    assert regeln("") == "" and regeln("   ") == ""


def test_hat_worte():
    assert hat_worte("Ja.") and hat_worte("42")
    assert not hat_worte("...") and not hat_worte(" - ")
