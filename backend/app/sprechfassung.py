"""Sprechfassung (Transferschicht): was gesprochen wird, wenn der Text Zahlen, Uhrzeiten, Daten, Ordnungszahlen,
Prozente, Geldbeträge, Einheiten, Abkürzungen oder Versionsnummern enthält. Das Sprachmodell liest Ziffern, Zeichen und
Abkürzungen sonst unzuverlässig vor. Hier stehen nur feste Regeln für Deutsch; der Text bleibt, wie er ist, gesprochen
wird seine Sprechfassung. Anglizismen, englische Fachwörter und Wörter mit Ziffern (Qwen3, MP3) bleiben unverändert
(Nutzer 18.10.2026: "englische Anglizismen zulassen").

Die eine Stelle dafür in der Vertonung: Pläne (`Abschnitt.gesprochen`), `/sprechen` und der Strom `/sprechen/strom`.
Dieselben Regeln gelten beim Zurückhören (Ausspracheprüfung): gehörte Ziffern werden ebenso ausgeschrieben, damit
"42" und "zweiundvierzig" gleich zählen.

Die Reihenfolge der Regeln zählt: Abkürzungen zuerst, dann Uhrzeit und Datum, dann Beträge und Einheiten vor den
nackten Zahlen; was eine Regel umschreibt, sieht die nächste schon als Wort. Typografische Zeichen stehen über ihre
Nummer."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from num2words import num2words

MINUS = chr(0x2212)
HALBGEVIERT = chr(0x2013)          # Strich zwischen den Grenzen einer Spanne ("10 bis 20")

MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November",
          "Dezember"]
MONATSKURZ = {"Jan": 1, "Feb": 2, "Mär": 3, "Apr": 4, "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9, "Sept": 9, "Okt": 10,
              "Nov": 11, "Dez": 12}

# Wörter vor einer Ordnungszahl. Nach "der", "die", "das" endet sie auf -e ("der dritte September"), nach Artikel oder
# Präposition im Dativ und Akkusativ auf -en ("am dritten September"); ohne solches Wort steht vor einem Monat die
# starke Form auf -er ("Montag, dritter September"). Vor einem Monat ist jede Zahl mit Punkt eine Ordnungszahl; sonst
# nur nach einem Artikel (`ARTIKEL`, "im 3. Stock"), denn "bis 5. Dann" ist ein Satzende. Die Satzzerlegung
# (saetze.py) kennt dieselben Artikel, damit "im 3. Stock" kein Satzende ist.
ENDUNG_E = {"der", "die", "das"}
ENDUNG_EN = {"am", "im", "vom", "zum", "zur", "beim", "dem", "den", "des", "ab", "seit", "bis", "vor", "nach", "für",
             "gegen", "um", "über", "dieses", "diesem", "diesen"}
ARTIKEL = {"der", "die", "das", "den", "dem", "des", "am", "im", "vom", "zum", "zur", "beim"}


@dataclass(frozen=True)
class Einheit:
    mehrzahl: str
    einzahl: str = ""              # nur wo sie sich unterscheidet ("eine Sekunde")
    weiblich: bool = False         # "eine Sekunde", "eine Tonne"


EINHEITEN: dict[str, Einheit] = {
    "TB": Einheit("Terabyte"), "GB": Einheit("Gigabyte"), "MB": Einheit("Megabyte"), "KB": Einheit("Kilobyte"),
    "kB": Einheit("Kilobyte"), "Mbit/s": Einheit("Megabit pro Sekunde"), "Gbit/s": Einheit("Gigabit pro Sekunde"),
    "km/h": Einheit("Kilometer pro Stunde"), "m/s": Einheit("Meter pro Sekunde"),
    "km²": Einheit("Quadratkilometer"), "m²": Einheit("Quadratmeter"), "cm²": Einheit("Quadratzentimeter"),
    "qm": Einheit("Quadratmeter"), "m³": Einheit("Kubikmeter"),
    "km": Einheit("Kilometer"), "cm": Einheit("Zentimeter"), "mm": Einheit("Millimeter"), "m": Einheit("Meter"),
    "kg": Einheit("Kilogramm"), "mg": Einheit("Milligramm"), "g": Einheit("Gramm"), "t": Einheit("Tonnen", "Tonne", True),
    "ml": Einheit("Milliliter"), "l": Einheit("Liter"),
    "ms": Einheit("Millisekunden", "Millisekunde", True), "min": Einheit("Minuten", "Minute", True),
    "h": Einheit("Stunden", "Stunde", True), "s": Einheit("Sekunden", "Sekunde", True),
    "GHz": Einheit("Gigahertz"), "MHz": Einheit("Megahertz"), "kHz": Einheit("Kilohertz"), "Hz": Einheit("Hertz"),
    "kWh": Einheit("Kilowattstunden", "Kilowattstunde", True), "Wh": Einheit("Wattstunden", "Wattstunde", True),
    "kW": Einheit("Kilowatt"), "W": Einheit("Watt"), "V": Einheit("Volt"), "hPa": Einheit("Hektopascal"),
    "°C": Einheit("Grad Celsius"), "°F": Einheit("Grad Fahrenheit"), "°": Einheit("Grad"),
    "%": Einheit("Prozent"), chr(0x2030): Einheit("Promille"),
}


@dataclass(frozen=True)
class Waehrung:
    name: str
    unter: str                     # Name der Untereinheit ("Cent")


WAEHRUNGEN: dict[str, Waehrung] = {
    "€": Waehrung("Euro", "Cent"), "EUR": Waehrung("Euro", "Cent"), "Euro": Waehrung("Euro", "Cent"),
    "$": Waehrung("Dollar", "Cent"),
    "USD": Waehrung("Dollar", "Cent"), "£": Waehrung("Pfund", "Pence"), "CHF": Waehrung("Franken", "Rappen"),
}

# Abkürzungen: Leerzeichen nach den Punkten sind beliebig ("z. B." wie "z.B."); beginnt eine klein, gilt sie am
# Satzanfang auch groß ("Z. B." wird "Zum Beispiel").
ABKUERZUNGEN: dict[str, str] = {
    "z. B.": "zum Beispiel", "d. h.": "das heißt", "u. a.": "unter anderem", "v. a.": "vor allem",
    "z. T.": "zum Teil", "u. U.": "unter Umständen", "i. d. R.": "in der Regel", "o. Ä.": "oder Ähnliches",
    "o. ä.": "oder Ähnliches", "u. Ä.": "und Ähnliches", "u. ä.": "und Ähnliches", "s. o.": "siehe oben",
    "s. u.": "siehe unten", "usw.": "und so weiter", "etc.": "et cetera", "bzw.": "beziehungsweise", "ca.": "circa",
    "ggf.": "gegebenenfalls", "evtl.": "eventuell", "inkl.": "inklusive", "exkl.": "exklusive", "zzgl.": "zuzüglich",
    "vgl.": "vergleiche", "sog.": "sogenannte", "bspw.": "beispielsweise", "insb.": "insbesondere",
    "bzgl.": "bezüglich", "max.": "maximal", "mind.": "mindestens", "Nr.": "Nummer", "Dr.": "Doktor",
    "Prof.": "Professor", "Hr.": "Herr", "Fr.": "Frau", "Str.": "Straße", "Tel.": "Telefon", "Mio.": "Millionen",
    "Mrd.": "Milliarden", "Tsd.": "Tausend", "Jh.": "Jahrhundert", "Std.": "Stunden", "Min.": "Minuten",
    "Sek.": "Sekunden",
}
NUR_KLEIN = {"max."}               # groß ist es ein Name ("Max.")
VOR_ZAHL = {"S.": "Seite", "Abs.": "Absatz", "Kap.": "Kapitel", "Bd.": "Band", "Art.": "Artikel"}   # nur vor Ziffern

_ZAHL = r"\d+(?:\.\d{3})*(?:,\d+)?"
_FREI_VORN = r"(?<![\wÄÖÜäöüß.,])"           # keine Ziffern mitten in Wörtern wie Qwen3 oder MP3
_FREI_HINTEN = r"(?![\wÄÖÜäöüß]|[.,]\d)"
_JAHR_DANACH = r"(?=\s*(?:$|[.,;:!?)]|[a-zäöüß]))"   # ein Jahr steht vor Satzzeichen oder kleinem Wort, eine Anzahl vor einem Nomen
_STRICH = f"[-{HALBGEVIERT}]"


def _alternativen(woerter) -> str:
    """Regex-Alternativen, längste zuerst (sonst träfe "m" vor "m²")."""
    return "|".join(sorted(map(re.escape, woerter), key=len, reverse=True))


# --- Zahlwörter ----------------------------------------------------------------------------------------------------

def _ganz(text: str | int) -> str:
    """Zahl als Wort; "eintausend" und "einhundert" am Anfang so, wie man spricht ("tausend", "hundert")."""
    wort = num2words(int(text), lang="de")
    for alt in ("eintausend", "einhundert"):
        if wort.startswith(alt):
            return wort[len("ein"):]
    return wort


def vor_nomen(wort: str, weiblich: bool = False) -> str:
    """Ein Zahlwort vor einem Nomen: "eins" am Ende wird "ein" oder "eine" ("ein Euro", "hundertein Meter")."""
    return wort[:-len("eins")] + ("eine" if weiblich else "ein") if wort.endswith("eins") else wort


def zahl(text: str) -> str:
    """Deutsch geschriebene Zahl ("1.234,5", "42") als Wörter; Nachkommastellen einzeln."""
    roh = text.replace(".", "")
    if "," in roh:
        vorn, hinten = roh.split(",", 1)
        return f"{_ganz(vorn)} Komma {' '.join(_ganz(z) for z in hinten)}"
    return _ganz(roh)


def jahr(text: str) -> str:
    return num2words(int(text), lang="de", to="year")


def ordnungszahl(n: int, endung: str) -> str:
    """Ordnungszahl mit Endung an der Grundform ("dritte" + "n" = "dritten")."""
    return num2words(n, lang="de", to="ordinal") + endung


def endung_nach(vorher: str) -> str:
    """Endung einer Ordnungszahl nach dem Text davor: -e nach "der/die/das", -en nach Präposition oder Artikel im
    Dativ und Akkusativ, sonst die starke Form -er (vor einem Monat: "Montag, dritter September")."""
    wort = re.search(r"(\w+)\W*$", vorher)
    w = wort.group(1).lower() if wort else ""
    if w in ENDUNG_E:
        return ""
    if w in ENDUNG_EN:
        return "n"
    return "r"


# --- Regeln --------------------------------------------------------------------------------------------------------

def _abkuerzung_muster(kurz: str) -> str:
    teile = [t for t in kurz.replace(" ", "").split(".") if t]
    erstes = teile[0]
    if erstes[0].islower() and kurz not in NUR_KLEIN:
        erstes = f"[{erstes[0]}{erstes[0].upper()}]{re.escape(erstes[1:])}"
    else:
        erstes = re.escape(erstes)
    return r"\.\s?".join([erstes, *map(re.escape, teile[1:])]) + r"\."


_ABKUERZUNG = re.compile(r"(?<![\wÄÖÜäöüß.])(?:" + "|".join(
    f"(?P<a{i}>{_abkuerzung_muster(k)})" for i, k in enumerate(ABKUERZUNGEN)) + ")")
_ABKUERZUNG_LANG = list(ABKUERZUNGEN.values())


def _abkuerzung(m: re.Match) -> str:
    i = int(m.lastgroup[1:])
    lang = _ABKUERZUNG_LANG[i]
    if m[0][0].isupper() and lang[0].islower():
        lang = lang[0].upper() + lang[1:]
    return lang + ("." if m.end() == len(m.string) else "")     # am Ende des Textes bleibt der Satzpunkt


def _uhrzeit(m: re.Match) -> str:
    stunde = vor_nomen(_ganz(m["h"]))
    minute = int(m["m"]) if m["m"] else 0
    return f"{stunde} Uhr" + (f" {_ganz(minute)}" if minute else "")


def _tag_monat(m: re.Match) -> str:
    """Datum mit Monatsnamen, auf Wunsch als Spanne ("vom 3. bis 5. September") und mit Jahr."""
    monat = m["mo"].rstrip(".")
    monat = MONATE[MONATSKURZ[monat] - 1] if monat in MONATSKURZ else monat
    endung = endung_nach(m.string[:m.start()])
    vorn = ""
    if m["t0"]:
        if not 1 <= int(m["t0"]) <= 31:
            return m[0]
        vorn = f"{ordnungszahl(int(m['t0']), endung)} bis "
        endung = "n" if "zum" in m["bis"] else endung
    if not 1 <= int(m["t"]) <= 31:
        return m[0]
    aus = f"{vorn}{ordnungszahl(int(m['t']), endung)} {monat}"
    return aus + (f" {jahr(m['j'])}" if m["j"] else "")


def _datum(m: re.Match) -> str:
    tag, monat = int(m["t"]), int(m["mo"])
    if not (1 <= tag <= 31 and 1 <= monat <= 12):
        return m[0]
    aus = f"{ordnungszahl(tag, endung_nach(m.string[:m.start()]))} {MONATE[monat - 1]}"
    return aus + (f" {jahr(m['j'])}" if m["j"] else "")


def _ordnung(m: re.Match) -> str:
    """Ordnungszahl nach einem Begleiter: "im 3. Stock" wird "im dritten Stock"."""
    endung = "" if m["b"].lower() in ENDUNG_E else "n"
    return f"{m['b']} {ordnungszahl(int(m['n']), endung)}"


def _betrag(m: re.Match) -> str:
    """Geldbetrag wie gesprochen: "13.439,16 €" wird "dreizehntausendvierhundertneununddreißig Euro sechzehn",
    "0,50 €" wird "fünfzig Cent"."""
    w = WAEHRUNGEN[m["w"]]
    roh = m["z"].replace(".", "")
    ganz, _, rest = roh.partition(",")
    if len(rest) > 2:                                  # mehr als Cent: als Kommazahl
        return f"{zahl(m['z'])} {w.name}"
    unter = int(rest.ljust(2, "0")) if rest else 0
    if int(ganz) == 0 and unter:
        return f"{vor_nomen(_ganz(unter))} {w.unter}"
    aus = f"{vor_nomen(_ganz(ganz))} {w.name}"
    return aus + (f" {_ganz(unter)}" if unter else "")


def _einheit(m: re.Match) -> str:
    e = EINHEITEN[m["e"]]
    if m["z"] == "1":
        return f"{vor_nomen('eins', e.weiblich)} {e.einzahl or e.mehrzahl}"
    return f"{vor_nomen(zahl(m['z']), e.weiblich)} {e.mehrzahl}"


def _version(m: re.Match) -> str:
    teile = m[0].split(".")
    if all(len(t) == 3 for t in teile[1:]):          # 1.234 ist eine Tausenderzahl, keine Version
        return zahl(m[0])
    return " Punkt ".join(_ganz(teil) for teil in teile)


_MONATSNAME = _alternativen(MONATE + ["Jänner"]) + "|" + "|".join(re.escape(k) + r"\." for k in MONATSKURZ)
_WAEHRUNG = _alternativen(WAEHRUNGEN)

Regel = tuple[re.Pattern, Callable[[re.Match], str]]
REGELN: list[Regel] = [
    (_ABKUERZUNG, _abkuerzung),
    (re.compile(rf"(?<![\wÄÖÜäöüß])(?P<k>{_alternativen(VOR_ZAHL)})\s?(?=\d)"), lambda m: f"{VOR_ZAHL[m['k']]} "),
    (re.compile(r"\s?&\s?"), lambda m: " und "),
    (re.compile(r"§§\s?"), lambda m: "Paragrafen "),
    (re.compile(r"§\s?"), lambda m: "Paragraf "),
    # Uhrzeit: 14:30 (Uhr), 14.30 Uhr, 14 Uhr
    (re.compile(r"(?<![\d.,:])(?P<h>[01]?\d|2[0-4]):(?P<m>[0-5]\d)(?![\d:])(?:\s?Uhr\b)?"), _uhrzeit),
    (re.compile(r"(?<![\d.,:])(?P<h>[01]?\d|2[0-4])\.(?P<m>[0-5]\d)\s?Uhr\b"), _uhrzeit),
    (re.compile(r"(?<![\d.,:])(?P<h>[01]?\d|2[0-4])(?P<m>)\s?Uhr\b"), _uhrzeit),
    # Datum: 3. September (2026), vom 3. bis 5. September, 12.3.2026
    (re.compile(rf"(?<![\d.,])(?:(?P<t0>\d{{1,2}})\.\s?(?P<bis>bis zum|bis|{_STRICH})\s?)?(?P<t>\d{{1,2}})\.\s?"
                rf"(?P<mo>{_MONATSNAME})(?![\wÄÖÜäöüß])(?:\s(?P<j>\d{{4}})(?!\d))?"), _tag_monat),
    (re.compile(r"(?<![\d.,])(?P<t>\d{1,2})\.(?P<mo>\d{1,2})\.(?P<j>\d{4})?(?!\d)"), _datum),
    # Ordnungszahl nach Begleiter: der 2. Versuch, im 3. Stock
    (re.compile(rf"(?<![\wÄÖÜäöüß])(?P<b>(?i:{_alternativen(ARTIKEL)}))\s(?P<n>\d{{1,4}})\.(?=\s[A-ZÄÖÜ])"), _ordnung),
    # Geld: 13.439,16 €, € 5, 5 EUR; ein übrig gebliebenes Zeichen ("2 Millionen €")
    (re.compile(rf"(?P<z>{_ZAHL})\s?(?P<w>{_WAEHRUNG})(?![\wÄÖÜäöüß])"), _betrag),
    (re.compile(rf"(?<![\wÄÖÜäöüß])(?P<w>{_WAEHRUNG})\s?(?P<z>{_ZAHL})"), _betrag),
    (re.compile(r"\s?(?P<w>[€£])"), lambda m: f" {WAEHRUNGEN[m['w']].name}"),
    # Vorzeichen: -5 °C (nicht "10 -20" und nicht in einer Spanne "10-20")
    (re.compile(rf"(?:^|(?<=[\s(]))(?<!\d\s)[-{MINUS}](?=\d)"), lambda m: "minus "),
    (re.compile(rf"(?P<z>{_ZAHL})\s?(?P<e>{_alternativen(EINHEITEN)})(?![\wÄÖÜäöüß²³])"), _einheit),
    (re.compile(rf"{_FREI_VORN}(?P<a>{_ZAHL})\s?{_STRICH}\s?(?P<b>{_ZAHL}){_FREI_HINTEN}"),
     lambda m: f"{zahl(m['a'])} bis {zahl(m['b'])}"),
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
    return re.sub(r"\s+([,.;:!?])", r"\1", re.sub(r"\s+", " ", text)).strip()


def hat_worte(text: str) -> bool:
    """Ob ein Text überhaupt etwas zu sprechen hat (nicht nur Satzzeichen)."""
    return any(z.isalnum() for z in text)
