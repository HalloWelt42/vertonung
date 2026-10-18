"""Ausspracheprüfung: das Gesprochene eines Abschnitts wird über den Hördienst zurückgehört und Wort für Wort mit dem
Text verglichen (Wortfehlerquote und die abweichenden Stellen). Das Hören kann selbst irren; die Quote ist ein Hinweis
und eine Messgröße für die Optimierung, kein Urteil. Verglichen wird ohne Satzzeichen und ohne Groß- und Kleinschreibung.
Gehört wird das fertige Ergebnis, nicht der einzelne Abschnitt; die Hör-Stücke schneidet der Tondienst in einem Aufruf."""

from __future__ import annotations

import re
import shutil
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from appkern.ton import HOEREN, Aufbereiten, Ausgabe, Tonarbeit

from .modell.plan import Plan
from .werk.zeitlage import Spanne, spannen
from .sprechfassung import sprechbar

SPITZE = 0.98         # ein übersteuertes Stück wird leiser, damit der Hördienst sauberen Ton bekommt
HOECHSTENS_ABWEICHUNGEN = 8
_ZEICHEN = re.compile(r"[^\w\s]", re.UNICODE)



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
        if art == "equal" or "".join(a[i1:i2]) == "".join(b[j1:j2]):   # nur getrennt oder zusammen geschrieben
            continue
        fehler += max(i2 - i1, j2 - j1)
        links, rechts = " ".join(a[i1:i2]) or "(zusätzlich)", " ".join(b[j1:j2]) or "(fehlt)"
        abweichungen.append(f"{links} -> {rechts}")
    return Abgleich(round(min(fehler / len(a), 1.0), 3), abweichungen[:HOECHSTENS_ABWEICHUNGEN])


STUECK_S = 300.0      # so viel Ergebnis je Hör-Anfrage (geteilt an Abschnittsgrenzen)
RAND_S = 0.15         # Spielraum, mit dem ein Wort an den Rändern eines Abschnitts noch zu ihm zählt


def stuecke(span: list[Spanne], gesamt_s: float, hoechstens_s: float = STUECK_S) -> list[tuple[float, float]]:
    """Das Ergebnis in Hör-Stücke von höchstens `hoechstens_s`: geschnitten am spätesten Abschnittsbeginn, der noch
    hineinpasst, sonst (lange Stille) nach `hoechstens_s`."""
    beginne = [s.von for s in span]
    aus, anfang = [], 0.0
    while gesamt_s - anfang > hoechstens_s:
        passend = [v for v in beginne if anfang < v <= anfang + hoechstens_s]
        schnitt = max(passend) if passend else anfang + hoechstens_s
        aus.append((anfang, schnitt))
        anfang = schnitt
    aus.append((anfang, gesamt_s))
    return aus


async def pruefen(gelaufen: Plan, ergebnis: Path, dauer_s: float, arbeit: Path, ton: Tonarbeit,
                  hoeren: Callable[[Path, str], Awaitable[list]]) -> int:
    """Hört das fertige Ergebnis (das, was man tatsächlich hört, samt Stauchung) in wenigen Stücken, ordnet die Wörter
    über ihre Zeit den Abschnitten zu und trägt je Abschnitt Quote und Abweichungen in seinen Bericht ein. Wenige große
    Anfragen statt einer je Abschnitt: der Hördienst hat ein Fach, jede Anfrage wartet sonst einzeln (K3, 18.10.2026)."""
    span = spannen(gelaufen)
    if not span:
        return 0
    sprache = gelaufen.sprache
    arbeit.mkdir(parents=True, exist_ok=True)
    woerter: dict[int, list[str]] = {s.nr: [] for s in span}
    try:
        teile = stuecke(span, dauer_s)
        dateien = [arbeit / f"hoeren-{i}.wav" for i in range(len(teile))]
        await ton.aufbereiten(ergebnis, Aufbereiten(ausgaben=[Ausgabe(format=HOEREN, beginn_s=von, ende_s=bis, spitze=SPITZE)
                                                              for von, bis in teile]),
                              dateien, titel=f"{gelaufen.name}, zum Hören schneiden")
        for (von, _), datei in zip(teile, dateien):
            for w in await hoeren(datei, sprache):
                mitte = von + (w.start + w.ende) / 2
                nr = next((s.nr for s in span if s.von - RAND_S <= mitte <= s.bis + RAND_S), None)
                if nr is not None:
                    woerter[nr].append(w.wort)
    finally:
        shutil.rmtree(arbeit, ignore_errors=True)
    geprueft = 0
    for a in gelaufen.abschnitte:
        if a.nr in woerter and a.bericht is not None:
            # verglichen wird mit dem Gesprochenen; gehörte Ziffern werden nach denselben Regeln ausgeschrieben
            abgleich = abgleichen(a.gesprochen(sprache), sprechbar(" ".join(woerter[a.nr]), sprache))
            a.bericht = a.bericht.model_copy(update={"aussprache": abgleich.quote, "abweichungen": abgleich.abweichungen})
            geprueft += 1
    return geprueft
