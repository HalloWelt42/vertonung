"""Verzeichnis der Vertonungen (SQLite, nur ein Index): je Plan Name, Art, Hauptdatei, Rollen und Stimmen, Stand
(offen, Hinweise) und Ergebnis. Die Wahrheit sind die Dateien in der Kellerwolke; nach jedem Schreiben eines Plans
wird sein Eintrag neu geschrieben."""

from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from appkern.datenbank import Datenbank

from .modell.plan import Art, Plan
from .werk.zeitlage import mit_hinweis

STUFEN = ["""
CREATE TABLE IF NOT EXISTS plan (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, art TEXT NOT NULL, haupt_id TEXT NOT NULL, haupt_pfad TEXT NOT NULL,
  anfrage_id TEXT, rollen TEXT NOT NULL, abschnitte INTEGER NOT NULL, offen INTEGER NOT NULL, hinweise INTEGER NOT NULL,
  ergebnis_id TEXT, ergebnis_pfad TEXT, dauer_s REAL, geaendert_am TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS plan_geaendert ON plan (geaendert_am DESC);
"""]


class RolleKurz(BaseModel):
    name: str
    stimme: str


class Eintrag(BaseModel):
    id: UUID
    name: str
    art: Art
    haupt_id: UUID
    haupt_pfad: str
    anfrage_id: UUID | None = None
    rollen: list[RolleKurz]
    abschnitte: int
    offen: int
    hinweise: int
    ergebnis_id: UUID | None = None
    ergebnis_pfad: str | None = None
    dauer_s: float | None = None
    geaendert_am: datetime


class Seite(BaseModel):
    gesamt: int
    eintraege: list[Eintrag]


class Verzeichnis:
    def __init__(self, db: Datenbank) -> None:
        self.db = db

    async def einrichten(self) -> None:
        await self.db.einrichten("verzeichnis", STUFEN)

    async def eintragen(self, plan: Plan, plan_id: UUID, haupt_id: UUID, haupt_pfad: str, stimmen_namen: dict[str, str],
                        anfrage_id: UUID | None = None) -> None:
        rollen = [RolleKurz(name=r.name, stimme=stimmen_namen.get(r.stimme.schluessel, r.stimme.name or "Klonstimme"))
                  for r in plan.rollen]
        hinweise = sum(1 for a in plan.abschnitte if a.bericht and mit_hinweis(a.bericht.stauchung, a.bericht.versatz_s,
                                                                               a.bericht.ersatz))
        e = plan.ergebnis
        await self.db.ausfuehren(
            "INSERT INTO plan (id, name, art, haupt_id, haupt_pfad, anfrage_id, rollen, abschnitte, offen, hinweise, "
            "ergebnis_id, ergebnis_pfad, dauer_s, geaendert_am) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, art=excluded.art, haupt_id=excluded.haupt_id, "
            "haupt_pfad=excluded.haupt_pfad, anfrage_id=excluded.anfrage_id, rollen=excluded.rollen, "
            "abschnitte=excluded.abschnitte, offen=excluded.offen, hinweise=excluded.hinweise, "
            "ergebnis_id=excluded.ergebnis_id, ergebnis_pfad=excluded.ergebnis_pfad, dauer_s=excluded.dauer_s, "
            "geaendert_am=excluded.geaendert_am",
            (str(plan_id), plan.name, plan.art, str(haupt_id), haupt_pfad, str(anfrage_id) if anfrage_id else None,
             json.dumps([r.model_dump() for r in rollen], ensure_ascii=False), len(plan.abschnitte), len(plan.zu_sprechen()),
             hinweise, str(e.knoten_id) if e else None, e.pfad if e else None, e.dauer_s if e else None,
             plan.geaendert_am.isoformat()))

    def _eintrag(self, z) -> Eintrag:
        return Eintrag(**{**dict(z), "rollen": json.loads(z["rollen"])})

    async def seite(self, *, art: str | None = None, suche: str = "", ab: int = 0, anzahl: int = 50) -> Seite:
        bed, werte = [], []
        if art:
            bed.append("art = ?")
            werte.append(art)
        if suche.strip():
            bed.append("(name LIKE ? OR haupt_pfad LIKE ?)")
            werte += [f"%{suche.strip()}%"] * 2
        wo = f" WHERE {' AND '.join(bed)}" if bed else ""
        gesamt = (await self.db.zeile(f"SELECT COUNT(*) AS n FROM plan{wo}", tuple(werte)))["n"]
        zeilen = await self.db.zeilen(f"SELECT * FROM plan{wo} ORDER BY geaendert_am DESC LIMIT ? OFFSET ?",
                                      (*werte, anzahl, ab))
        return Seite(gesamt=gesamt, eintraege=[self._eintrag(z) for z in zeilen])

    async def zaehlen(self) -> dict[str, int]:
        zeilen = await self.db.zeilen("SELECT art, COUNT(*) AS n FROM plan GROUP BY art")
        return {z["art"]: z["n"] for z in zeilen}

    async def eintrag(self, plan_id: UUID | str) -> Eintrag | None:
        z = await self.db.zeile("SELECT * FROM plan WHERE id = ?", (str(plan_id),))
        return self._eintrag(z) if z else None

    async def entfernen(self, plan_id: UUID | str) -> None:
        await self.db.ausfuehren("DELETE FROM plan WHERE id = ?", (str(plan_id),))
