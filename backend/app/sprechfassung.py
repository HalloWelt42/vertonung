"""Sprechfassung (Transferschicht): was gesprochen wird, wenn der Text Zahlen, Uhrzeiten, Daten, Prozente, Beträge,
Einheiten oder Versionsnummern enthält. Das Sprachmodell liest Ziffern und Zeichen sonst unzuverlässig vor. Hier stehen
nur feste Regeln für Deutsch; der Text des Plans bleibt, wie er ist, gesprochen wird seine Sprechfassung. Anglizismen und
englische Fachwörter bleiben unverändert (Nutzer 18.10.2026: "englische Anglizismen zulassen").

Dieselben Regeln gelten beim Zurückhören (Ausspracheprüfung): gehörte Ziffern werden ebenso ausgeschrieben, damit
"42" und "zweiundvierzig" gleich zählen."""

from __future__ import annotations

import re

from num2words import num2words

MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November",
          "Dezember"]
EINHEITEN = {
    "TB": "Terabyte", "GB": "Gigabyte", "MB": "Megabyte", "KB": "Kilobyte", "kB": "Kilobyte",
    "km": "Kilometer", "cm": "Zentimeter", "mm": "Millimeter", "m": "Meter", "kg": "Kilogramm", "g": "Gramm",
    "ms": "Millisekunden", "min": "Minuten", "h": "Stunden", "s": "Sekunden",
    "GHz": "Gigahertz", "MHz": "Megahertz", "kHz": "Kilohertz", "Hz": "Hertz",
    "kW": "Kilowatt", "W": "Watt", "V": "Volt", "°C": "Grad Celsius",
}
WAEHRUNGEN = {"€": "Euro", "$": "Dollar", "£": "Pfund"}

_ZAHL = r"\d+(?:\.\d{3})*(?:,\d+)?"
_FREI_VORN = r"(?<![\wÄÖÜäöüß.,])"           # keine Ziffern mitten in Wörtern wie Qwen3 oder MP3
_FREI_HINTEN = r"(?![\wÄÖÜäöüß]|[.,]\d)"
_JAHR_DANACH = r"(?=\s*(?:$|[.,;:!?)]|[a-zäöüß]))"   # ein Jahr steht vor Satzzeichen oder kleinem Wort, eine Anzahl vor einem Nomen


def _ganz(text: str) -> str:
    """Zahl als Wort; "eintausend" und "einhundert" am Anfang so, wie man spricht ("tausend", "hundert")."""
    wort = num2words(int(text), lang="de")
    for alt in ("eintausend", "einhundert"):
        if wort.startswith(alt):
            return wort[len("ein"):]
    return wort


def zahl(text: str) -> str:
    """Deutsch geschriebene Zahl ("1.234,5", "42") als Wörter."""
    roh = text.replace(".", "")
    if "," in roh:
        vorn, hinten = roh.split(",", 1)
        return f"{_ganz(vorn)} Komma {' '.join(_ganz(z) for z in hinten)}"
    return _ganz(roh)


def jahr(text: str) -> str:
    return num2words(int(text), lang="de", to="year")


def _uhrzeit(m: re.Match) -> str:
    stunde, minute = int(m["h"]), int(m["m"])
    return f"{_ganz(str(stunde))} Uhr" + (f" {_ganz(str(minute))}" if minute else "")


def _datum(m: re.Match) -> str:
    tag, monat = int(m["t"]), int(m["mo"])
    if not (1 <= tag <= 31 and 1 <= monat <= 12):
        return m[0]
    ordnung = num2words(tag, lang="de", to="ordinal")
    if m.string[:m.start()].rstrip().lower().endswith(("am", "vom", "zum", "bis zum")):
        ordnung += "n"                                # am zwölften März
    aus = f"{ordnung} {MONATE[monat - 1]}"
    return aus + (f" {jahr(m['j'])}" if m["j"] else "")


def _version(m: re.Match) -> str:
    teile = m[0].split(".")
    if all(len(t) == 3 for t in teile[1:]):          # 1.234 ist eine Tausenderzahl, keine Version
        return zahl(m[0])
    return " Punkt ".join(_ganz(teil) for teil in teile)


REGELN: list[tuple[re.Pattern, object]] = [
    (re.compile(r"\b(?P<h>[01]?\d|2[0-3]):(?P<m>[0-5]\d)\b"), _uhrzeit),
    (re.compile(r"\b(?P<t>\d{1,2})\.(?P<mo>\d{1,2})\.(?P<j>\d{4})?(?!\d)"), _datum),
    (re.compile(rf"(?P<z>{_ZAHL})\s?%"), lambda m: f"{zahl(m['z'])} Prozent"),
    (re.compile(rf"(?P<w>[€$£])\s?(?P<z>{_ZAHL})"), lambda m: f"{zahl(m['z'])} {WAEHRUNGEN[m['w']]}"),
    (re.compile(rf"(?P<z>{_ZAHL})\s?(?P<w>[€$£])"), lambda m: f"{zahl(m['z'])} {WAEHRUNGEN[m['w']]}"),
    (re.compile(rf"(?P<z>{_ZAHL})\s?(?P<e>{'|'.join(sorted(map(re.escape, EINHEITEN), key=len, reverse=True))})(?![\wÄÖÜäöüß])"),
     lambda m: f"{zahl(m['z'])} {EINHEITEN[m['e']]}"),
    (re.compile(rf"{_FREI_VORN}(?P<a>{_ZAHL})\s?-\s?(?P<b>{_ZAHL}){_FREI_HINTEN}"), lambda m: f"{zahl(m['a'])} bis {zahl(m['b'])}"),
    (re.compile(rf"{_FREI_VORN}\d+(?:\.\d+){{1,3}}{_FREI_HINTEN}"), _version),
    (re.compile(rf"{_FREI_VORN}(?:1[1-9]|20)\d{{2}}{_FREI_HINTEN}{_JAHR_DANACH}"), lambda m: jahr(m[0])),
    (re.compile(rf"{_FREI_VORN}{_ZAHL}{_FREI_HINTEN}"), lambda m: zahl(m[0])),
]


def sprechbar(text: str, sprache: str) -> str:
    """Sprechfassung eines Textes in `sprache`; Regeln gibt es bisher für Deutsch, sonst bleibt der Text."""
    return regeln(text) if sprache == "de" else text


def regeln(text: str) -> str:
    """Feste Regeln der Reihe nach; was eine Regel umschreibt, sieht die nächste schon als Wort."""
    for muster, ersatz in REGELN:
        text = muster.sub(ersatz, text)
    return re.sub(r"\s+", " ", text).strip()
