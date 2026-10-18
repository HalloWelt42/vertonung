"""Zeitlage für zeitgenaues Sprechen (Regeln des Nutzers): ein Abschnitt beginnt an seiner Zeit in der Quelle; reicht
sein Fenster nicht, nutzt er erst die Stille bis zum nächsten Abschnitt, dann wird maßvoll gestaucht (bis `komfort`
unauffällig, höchstens `hoechstens`), was dann noch fehlt, wird geschoben. Nie gekürzt, nie abgeschnitten; die
Abschnitte überlappen nie (der nächste beginnt frühestens, wenn der vorige endet)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..modell.plan import Weg

KOMFORT = 1.15
HOECHSTENS = 1.5
ABSTAND_S = 0.05             # kleiner Atemzug vor dem nächsten Abschnitt


@dataclass(frozen=True)
class Fenster:
    start: float
    ende: float
    dauer_s: float           # Länge des Gesprochenen, ungestaucht


@dataclass(frozen=True)
class Lage:
    beginn: float
    stauchung: float
    weg: Weg
    versatz_s: float

    def laenge(self, dauer_s: float) -> float:
        return dauer_s / self.stauchung


def legen(fenster: list[Fenster], *, quelle_ende: float | None = None, komfort: float = KOMFORT,
          hoechstens: float = HOECHSTENS) -> list[Lage]:
    lagen: list[Lage] = []
    frei_ab = 0.0
    for i, f in enumerate(fenster):
        beginn = max(f.start, frei_ab)
        naechster = fenster[i + 1].start if i + 1 < len(fenster) else (quelle_ende if quelle_ende else math.inf)
        verfuegbar = naechster - beginn - (ABSTAND_S if i + 1 < len(fenster) else 0.0)
        stauchung = 1.0
        if f.dauer_s <= f.ende - beginn:
            weg: Weg = "frei"
        elif f.dauer_s <= verfuegbar:
            weg = "luecke"
        else:
            stauchung = min(f.dauer_s / max(verfuegbar, 1e-3), hoechstens)
            weg = "gestaucht"
        versatz = round(beginn - f.start, 3)
        if versatz > 0.01:                    # später als in der Quelle: der vorige reichte hinein
            weg = "geschoben"
        lagen.append(Lage(beginn=round(beginn, 3), stauchung=round(stauchung, 4), weg=weg, versatz_s=max(versatz, 0.0)))
        frei_ab = beginn + f.dauer_s / stauchung
    return lagen
