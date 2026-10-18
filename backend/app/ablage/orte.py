"""Orte im Zweig der App und Namen der Begleitdateien. Einzige Stelle für Ordner-, Datei- und Rollennamen.

Stimmen liegen nach Bereich getrennt (`Stimmen/Privat`, `Stimmen/Fremd`): die Referenz `<Name>.wav` mit den
Begleitern `<Name>.stimme.json` (Angaben) und auf Wunsch `<Name>.quelle.<endung>` (Originalaufnahme). Freie Texte
und Dialoge liegen in `Texte`. Pläne und Ergebnisse sind Begleiter ihrer Hauptdatei (Text oder Aufnahme)."""

from __future__ import annotations

import re
import unicodedata

from appkern.kellerwolke import Knoten, pfad_aus

STIMMEN = "Stimmen"
BEREICH_ORDNER = {"privat": "Privat", "fremd": "Fremd"}
TEXTE = "Texte"

ROLLE_STIMME, ZUSATZ_STIMME = "stimme", ".stimme.json"
ROLLE_QUELLE = "quelle"
ROLLE_PLAN, ZUSATZ_PLAN = "vertonung", ".vertonung.json"
ROLLE_SPRACHE = "sprache"
JSON = "application/json"
TONTYPEN = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".flac": "audio/flac", ".ogg": "audio/ogg"}
TEXTTYPEN = ("text/plain", "text/markdown")

_UNERLAUBT = re.compile(r'[/\\:*?"<>|\x00-\x1f]+')


def ort(zweig: str, *teile: str) -> str:
    return pfad_aus(zweig, *teile)


def zusatz_sprache(endung: str) -> str:
    return f".sprache{endung}"


def dateiname(name: str) -> str:
    """Ein Name, der als Dateiname taugt (in NFC, ohne Pfadzeichen)."""
    sauber = _UNERLAUBT.sub(" ", unicodedata.normalize("NFC", name)).strip(" .")
    return re.sub(r"\s+", " ", sauber)[:120] or "Ohne Namen"


def ist_ton(k: Knoten) -> bool:
    return not k.ist_ordner and ((k.inhaltstyp or "").startswith("audio/") or k.name.lower().endswith(tuple(TONTYPEN)))
