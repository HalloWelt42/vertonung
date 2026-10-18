"""Ausspracheprüfung: das Gesprochene eines Abschnitts wird über den Hördienst zurückgehört und Wort für Wort mit dem
Text verglichen (Wortfehlerquote und die abweichenden Stellen). Das Hören kann selbst irren; die Quote ist ein Hinweis
und eine Messgröße für die Optimierung, kein Urteil. Verglichen wird ohne Satzzeichen und ohne Groß- und Kleinschreibung.
Geprüft wird nur, was dieser Lauf neu gesprochen hat."""

from __future__ import annotations

import re
import shutil
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from appkern.ton import Ton, Tonformat

from .modell.plan import Plan
from .werk.werk import RATE, abschnitt_datei

HOEREN = Tonformat(rate=16000, kanaele=1, kodierung="pcm_s16le")    # was der Hördienst ohnehin rechnet
HOECHSTENS_ABWEICHUNGEN = 8
_ZEICHEN = re.compile(r"[^\w\s]", re.UNICODE)

Hoeren = Callable[[Path, str], Awaitable[str]]


@dataclass(frozen=True)
class Abgleich:
    quote: float                 # (ersetzt + fehlend + zusätzlich) / Wörter im Text
    abweichungen: list[str]      # "soll -> gehört", "soll -> (fehlt)", "(zusätzlich) -> gehört"


def woerter(text: str) -> list[str]:
    text = text.lower().replace("-", " ").replace("/", " ")
    return [w for w in _ZEICHEN.sub(" ", text).split() if w]


def abgleichen(soll: str, gehoert: str) -> Abgleich:
    a, b = woerter(soll), woerter(gehoert)
    if not a:
        return Abgleich(0.0, [])
    fehler, abweichungen = 0, []
    for art, i1, i2, j1, j2 in SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if art == "equal":
            continue
        fehler += max(i2 - i1, j2 - j1)
        links, rechts = " ".join(a[i1:i2]) or "(zusätzlich)", " ".join(b[j1:j2]) or "(fehlt)"
        abweichungen.append(f"{links} -> {rechts}")
    return Abgleich(round(min(fehler / len(a), 1.0), 3), abweichungen[:HOECHSTENS_ABWEICHUNGEN])


async def pruefen(vorher: Plan, gelaufen: Plan, speicher: Path, arbeit: Path, ton: Ton, hoeren: Hoeren) -> int:
    """Prüft die frisch gesprochenen Abschnitte von `gelaufen` (Prüfsumme anders als in `vorher`) und trägt das Ergebnis
    in ihren Bericht ein; liefert die Zahl der geprüften."""
    alt = {a.nr: a.gesprochen_als for a in vorher.abschnitte}
    arbeit.mkdir(parents=True, exist_ok=True)
    geprueft = 0
    try:
        for a in gelaufen.abschnitte:
            if not a.gesprochen_als or a.gesprochen_als == alt.get(a.nr) or a.bericht is None:
                continue
            quelle = abschnitt_datei(speicher, a.nr, a.gesprochen_als)
            if not quelle.is_file():
                continue
            datei = arbeit / f"hoeren-{a.nr:05d}.wav"
            await ton.schreiben(await ton.lesen(quelle, RATE), RATE, datei, HOEREN)
            abgleich = abgleichen(a.text, await hoeren(datei, gelaufen.sprache))
            a.bericht = a.bericht.model_copy(update={"aussprache": abgleich.quote, "abweichungen": abgleich.abweichungen})
            geprueft += 1
    finally:
        shutil.rmtree(arbeit, ignore_errors=True)
    return geprueft
