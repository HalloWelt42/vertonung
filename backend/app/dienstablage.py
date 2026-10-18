"""Was der Dienst für andere Apps in der Kellerwolke ablegt (Aufnahme, Transkript, Plan und Ergebnis unter Dienst/<App>):
der Sender bestimmt beim Hochladen, ob es bleibt (Nutzer 18.10.2026). Bleibt es nicht, kommt die Aufnahme samt ihren
Begleitern in den Papierkorb der Kellerwolke (wiederherstellbar), sobald der Sender das Abholen meldet, spätestens nach
der Frist, falls er sich nicht mehr meldet. Hier steht nur, was wem gehört und bis wann; weggeräumt wird in Teile."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from appkern.datenbank import Datenbank

STUFEN = ["""
CREATE TABLE IF NOT EXISTS dienst_ablage (
  auftrag_id TEXT PRIMARY KEY, haupt_id TEXT NOT NULL, app TEXT NOT NULL, behalten INTEGER NOT NULL,
  plan_id TEXT, frist_bis TEXT NOT NULL, erstellt_am TEXT NOT NULL
);
"""]
FRIST = timedelta(hours=48)      # reicht für langes Warten auf die Transkription (bis 6 Stunden) und das Abholen


@dataclass(frozen=True)
class Ablage:
    auftrag_id: str
    haupt_id: UUID
    app: str
    behalten: bool
    plan_id: UUID | None
    frist_bis: datetime


def _ablage(z: dict) -> Ablage:
    return Ablage(auftrag_id=z["auftrag_id"], haupt_id=UUID(z["haupt_id"]), app=z["app"], behalten=bool(z["behalten"]),
                  plan_id=UUID(z["plan_id"]) if z["plan_id"] else None, frist_bis=datetime.fromisoformat(z["frist_bis"]))


class DienstAblage:
    def __init__(self, db: Datenbank) -> None:
        self.db = db

    async def einrichten(self) -> None:
        await self.db.einrichten("dienst_ablage", STUFEN)

    async def eintragen(self, auftrag_id: str, haupt_id: UUID, app: str, behalten: bool) -> None:
        jetzt = datetime.now(UTC)
        await self.db.ausfuehren(
            "INSERT INTO dienst_ablage (auftrag_id, haupt_id, app, behalten, frist_bis, erstellt_am) VALUES (?,?,?,?,?,?)",
            (auftrag_id, str(haupt_id), app, int(behalten), (jetzt + FRIST).isoformat(), jetzt.isoformat()))

    async def plan_merken(self, auftrag_id: str, plan_id: UUID | str) -> None:
        await self.db.ausfuehren("UPDATE dienst_ablage SET plan_id = ? WHERE auftrag_id = ?", (str(plan_id), auftrag_id))

    async def eine(self, auftrag_id: str) -> Ablage | None:
        z = await self.db.zeile("SELECT * FROM dienst_ablage WHERE auftrag_id = ?", (auftrag_id,))
        return _ablage(z) if z else None

    async def faellige(self, jetzt: datetime | None = None) -> list[Ablage]:
        """Was nicht bleiben soll und dessen Frist um ist."""
        zeilen = await self.db.zeilen("SELECT * FROM dienst_ablage WHERE behalten = 0 AND frist_bis < ?",
                                      ((jetzt or datetime.now(UTC)).isoformat(),))
        return [_ablage(z) for z in zeilen]

    async def austragen(self, auftrag_id: str) -> None:
        await self.db.ausfuehren("DELETE FROM dienst_ablage WHERE auftrag_id = ?", (auftrag_id,))
