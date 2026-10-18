"""Sprechtempo je Stimme und Sprache, gemessen statt geschätzt: Zeichen je Sekunde bei Tempo 1, vor dem Stauchen. Nach
jedem Sprechen kommen die frisch gesprochenen Abschnitte dazu; ältere Messungen verblassen (gemittelt wird über rund
zehn Minuten Gesprochenes). Damit rechnet das Zeichenbudget der Übersetzung. Bis eine Stimme genug gesprochen hat, gilt
die Vorgabe aus den Einstellungen (gemessen am 18.10.2026: Katalogstimme serena auf Deutsch 10,1 bis 12,8)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from appkern.datenbank import Datenbank

STUFEN = ["""
CREATE TABLE IF NOT EXISTS sprechtempo (
  stimme TEXT NOT NULL, sprache TEXT NOT NULL, zeichen REAL NOT NULL, sekunden REAL NOT NULL, geaendert_am TEXT NOT NULL,
  PRIMARY KEY (stimme, sprache)
);
"""]
GEDAECHTNIS_S = 600.0        # so viel Gesprochenes zählt; was darüber hinausgeht, verblasst anteilig
MINDESTENS_S = 20.0          # erst ab so viel Gesprochenem gilt die Messung statt der Vorgabe


@dataclass(frozen=True)
class Probe:
    stimme: str              # Schlüssel der Stimmwahl (katalog:<name> oder klon:<knoten>)
    sprache: str
    zeichen: int
    sekunden: float          # bei Tempo 1 (gesprochene Dauer mal Tempo der Rolle)


class Sprechtempo:
    def __init__(self, db: Datenbank, vorgabe: Callable[[], float]) -> None:
        self.db = db
        self.vorgabe = vorgabe

    async def einrichten(self) -> None:
        await self.db.einrichten("sprechtempo", STUFEN)

    async def messen(self, proben: list[Probe]) -> None:
        summen: dict[tuple[str, str], list[float]] = {}
        for p in proben:
            if p.zeichen > 0 and p.sekunden > 0:
                s = summen.setdefault((p.stimme, p.sprache), [0.0, 0.0])
                s[0] += p.zeichen
                s[1] += p.sekunden
        jetzt = datetime.now(UTC).isoformat()
        for (stimme, sprache), (zeichen, sekunden) in summen.items():
            alt = await self.db.zeile("SELECT zeichen, sekunden FROM sprechtempo WHERE stimme = ? AND sprache = ?",
                                      (stimme, sprache))
            if alt:
                zeichen, sekunden = zeichen + alt["zeichen"], sekunden + alt["sekunden"]
            if sekunden > GEDAECHTNIS_S:
                anteil = GEDAECHTNIS_S / sekunden
                zeichen, sekunden = zeichen * anteil, sekunden * anteil
            await self.db.ausfuehren(
                "INSERT INTO sprechtempo (stimme, sprache, zeichen, sekunden, geaendert_am) VALUES (?,?,?,?,?) "
                "ON CONFLICT(stimme, sprache) DO UPDATE SET zeichen=excluded.zeichen, sekunden=excluded.sekunden, "
                "geaendert_am=excluded.geaendert_am", (stimme, sprache, zeichen, sekunden, jetzt))

    async def zeichen_je_s(self, stimme: str, sprache: str) -> float:
        z = await self.db.zeile("SELECT zeichen, sekunden FROM sprechtempo WHERE stimme = ? AND sprache = ?",
                                (stimme, sprache))
        if z and z["sekunden"] >= MINDESTENS_S:
            return z["zeichen"] / z["sekunden"]
        return self.vorgabe()
