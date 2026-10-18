"""Stimmen: Angaben einer Klonstimme (Datei `<Name>.stimme.json` neben der Referenz in der Kellerwolke) und der Eintrag
im Verzeichnis. Private Stimmen gehören Menschen aus dem Umfeld des Nutzers; fremde sind öffentliche Sprecher; der
Katalog sind die festen Stimmen des Sprechdienstes (ohne Dateien)."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Bereich = Literal["privat", "fremd"]
StimmBereich = Literal["privat", "fremd", "katalog"]
BEREICHE: dict[str, str] = {"privat": "Privat", "fremd": "Fremd", "katalog": "Katalog"}


class Herkunft(BaseModel):
    art: Literal["aufnahme", "hochgeladen", "aufgenommen", "uebernommen"]
    knoten_id: UUID | None = None
    pfad: str | None = None
    start: float | None = Field(None, ge=0)
    ende: float | None = Field(None, ge=0)


class StimmAngaben(BaseModel):
    format: Literal["stimme/1"] = "stimme/1"
    name: str = Field(min_length=1, max_length=80)
    bekannt_als: list[str] = Field(default_factory=list, max_length=20)
    bereich: Bereich
    sprache: str = "de"
    referenztext: str = Field("", max_length=2000)
    herkunft: Herkunft | None = None
    sprecherprofil: str | None = None      # Kennung des Sprecherprofils in der Transkription (dieselbe Person)
    notiz: str = Field("", max_length=2000)


class Stimme(BaseModel):
    """Eintrag im Verzeichnis und in der Schnittstelle. `id` ist der Knoten der Referenz oder `katalog:<name>`."""

    id: str
    name: str
    bereich: StimmBereich
    angaben: StimmAngaben | None = None
    pfad: str | None = None
    dauer_s: float | None = None
