"""Pläne und Ergebnisse in der Kellerwolke: der Plan als Begleiter seiner Hauptdatei (Rolle vertonung), das Ergebnis
ebenso (Rolle sprache, Zusatz nach Format). Freie Texte und Dialoge der App liegen in `Texte`. Lesen mit Stand,
schreiben nur mit dem zuletzt gelesenen Stand (sonst `StandVeraltet`). Liegt die Hauptdatei außerhalb der App, arbeitet
`fuer(zugang)` mit dem Zugang der Anfrage."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from appkern.kellerwolke import Kellerwolke, Knoten, StandVeraltet

from ..modell.plan import Plan
from . import orte
from .stimmen import zugang


class Unlesbar(Exception):
    """Die Datei ist kein lesbarer Vertonungsplan."""


def _plan(inhalt: bytes, name: str) -> Plan:
    try:
        return Plan.model_validate_json(inhalt)
    except ValidationError as f:
        raise Unlesbar(f"{name} ist kein lesbarer Plan ({f.errors()[0]['msg']})") from None


def _inhalt(p: Plan) -> bytes:
    return p.model_dump_json(indent=1, exclude_none=True).encode("utf-8")


class Plaene:
    def __init__(self, kellerwolke: Callable[[], Kellerwolke | None]) -> None:
        self._kw = kellerwolke

    @property
    def kw(self) -> Kellerwolke:
        return zugang(self._kw)

    def fuer(self, kw: Kellerwolke) -> Plaene:
        return Plaene(lambda: kw)

    async def texte(self) -> Knoten:
        kw = self.kw
        return await kw.ordner(orte.ort((await kw.ich()).zweig, orte.TEXTE))

    async def text_anlegen(self, name: str, text: str) -> Knoten:
        """Einen freien Text oder Dialog in `Texte` ablegen; ist der Name vergeben, mit Zähler dahinter."""
        kw = self.kw
        ordner = await self.texte()
        stamm = orte.dateiname(name)
        for n in range(1, 100):
            versuch = stamm if n == 1 else f"{stamm} ({n})"
            try:
                return await kw.schreiben(f"{ordner.pfad}/{versuch}.md", text.encode("utf-8"), nur_neu=True,
                                          inhaltstyp="text/markdown")
            except StandVeraltet:
                continue
        raise ValueError("Kein freier Name für den Text")

    async def zur_quelle(self, haupt_id: UUID | str) -> Knoten | None:
        return next((b for b in await self.kw.begleiter(haupt_id) if b.rolle == orte.ROLLE_PLAN), None)

    async def speichern(self, haupt_id: UUID | str, plan: Plan) -> Knoten:
        """Plan neben die Hauptdatei: neu, oder eine neue Version des vorhandenen."""
        vorhanden = await self.zur_quelle(haupt_id)
        return await self.kw.begleiter_schreiben(haupt_id, orte.ROLLE_PLAN, orte.ZUSATZ_PLAN, _inhalt(plan),
                                                 stand=vorhanden.etag if vorhanden else None, nur_neu=vorhanden is None,
                                                 inhaltstyp=orte.JSON)

    async def lesen(self, plan_id: UUID | str) -> tuple[Plan, Knoten]:
        kw = self.kw
        knoten = await kw.knoten(plan_id)
        return _plan(await kw.lesen_ganz(plan_id), knoten.name), knoten

    async def schreiben(self, plan_id: UUID | str, plan: Plan, stand: str) -> Knoten:
        return await self.kw.neue_version(plan_id, _inhalt(plan), stand=stand, inhaltstyp=orte.JSON)

    async def ergebnis_ablegen(self, haupt_id: UUID | str, datei: Path) -> Knoten:
        """Ergebnis neben die Hauptdatei: gleiches Format als neue Version, ein anderes ersetzt das bisherige (das geht in
        den Papierkorb, die Gruppe bleibt beieinander)."""
        kw = self.kw
        endung = datei.suffix.lower()
        zusatz = orte.zusatz_sprache(endung)
        vorhanden = next((b for b in await kw.begleiter(haupt_id) if b.rolle == orte.ROLLE_SPRACHE), None)
        if vorhanden is not None and not vorhanden.name.lower().endswith(zusatz):
            await kw.loeschen(vorhanden.id)
            vorhanden = None
        return await kw.begleiter_schreiben(haupt_id, orte.ROLLE_SPRACHE, zusatz, datei,
                                            stand=vorhanden.etag if vorhanden else None, nur_neu=vorhanden is None,
                                            inhaltstyp=orte.TONTYPEN.get(endung, "application/octet-stream"))

    async def ergebnis(self, haupt_id: UUID | str) -> Knoten | None:
        return next((b for b in await self.kw.begleiter(haupt_id) if b.rolle == orte.ROLLE_SPRACHE), None)
