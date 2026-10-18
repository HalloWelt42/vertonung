"""Ein gesprochenes Stück prüfen (Regeln der alten App, belegt): leer oder deutlich zu kurz heißt Aussetzer, bei
kurzem Text deutlich zu lang heißt Echo (der Dienst wiederholt oder plappert). Gemessen an der Länge des Textes."""

from __future__ import annotations

from typing import Literal

Befund = Literal["gut", "aussetzer", "echo"]
MIN_ZEICHEN_JE_S = 25.0      # schneller kann niemand sprechen: kürzer als Zeichen/25 s ist ein Aussetzer
MAX_S_JE_ZEICHEN = 1 / 1.8   # langsamer als 1,8 Zeichen je Sekunde ist bei kurzem Text ein Echo
KURZ = 25                    # bis hierher wird auf Echo geprüft, ab hier auf zu kurz


def befund(text: str, dauer_s: float, spitze: float) -> Befund:
    zeichen = len(text.strip())
    if dauer_s < 0.05 or spitze < 1e-3:
        return "aussetzer"
    if zeichen >= KURZ and dauer_s < zeichen / MIN_ZEICHEN_JE_S:
        return "aussetzer"
    if zeichen <= KURZ and dauer_s > zeichen * MAX_S_JE_ZEICHEN + 1.0:
        return "echo"
    return "gut"
