"""Dienstablage: fällig ist nur, was nicht bleiben soll und dessen Frist um ist."""

from datetime import UTC, datetime
from uuid import uuid4

from appkern.datenbank import Datenbank

from app.dienstablage import FRIST, DienstAblage


async def test_faellig_nur_nicht_behalten_nach_der_frist(tmp_path):
    db = Datenbank(tmp_path / "d.sqlite")
    await db.oeffnen()
    try:
        d = DienstAblage(db)
        await d.einrichten()
        await d.eintragen("a1", uuid4(), "Nachvertoner", behalten=False)
        await d.eintragen("a2", uuid4(), "Nachvertoner", behalten=True)
        plan = uuid4()
        await d.plan_merken("a1", plan)
        assert (await d.eine("a1")).transkription_anfrage is None
        await d.transkription_merken("a1", "anfrage-1")
        assert (await d.eine("a1")).transkription_anfrage == "anfrage-1"
        assert await d.faellige() == []
        spaeter = datetime.now(UTC) + FRIST * 1.01
        assert [(a.auftrag_id, a.plan_id) for a in await d.faellige(spaeter)] == [("a1", plan)]
        await d.austragen("a1")
        assert await d.faellige(spaeter) == [] and await d.eine("a1") is None and (await d.eine("a2")).behalten
    finally:
        await db.schliessen()
