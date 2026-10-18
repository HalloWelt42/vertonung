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


ALTE_SPRACHEN = {"german": "de", "english": "en", "french": "fr", "spanish": "es", "italian": "it", "dutch": "nl"}
ALTE_HERKUNFT = {"extracted": "aus einer Aufnahme gewonnen", "uploaded": "hochgeladen", "recorded": "aufgenommen"}


def aus_alter_app(daten: dict, bereich: Bereich) -> StimmAngaben:
    """Angaben der alten Stimmenausgabe (`stimme-alt/1`) im heutigen Format; den Bereich gibt der Ordner vor. Der Zusatz
    "(Katalog)" der alten Namen fällt weg, die alte Herkunft steht in der Notiz."""
    name = str(daten.get("name") or "Stimme").removesuffix(" (Katalog)").strip() or "Stimme"
    herkunft = ALTE_HERKUNFT.get(str(daten.get("herkunft") or ""), str(daten.get("herkunft") or ""))
    notiz = "Aus der alten Stimmenausgabe übernommen" + (f" ({herkunft})" if herkunft else "")
    if daten.get("beschreibung"):
        notiz += f". {daten['beschreibung']}"
    sprache = str(daten.get("sprache") or "de").lower()
    return StimmAngaben(name=name[:80], bereich=bereich, sprache=ALTE_SPRACHEN.get(sprache, sprache[:5] or "de"),
                        referenztext=str(daten.get("referenztext") or "")[:2000], herkunft=Herkunft(art="uebernommen"),
                        notiz=notiz[:2000])
