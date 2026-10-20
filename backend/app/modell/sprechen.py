"""Vertrag des Sofortsprechens: `POST /api/v1/sprechen` (ganze WAV) und `POST /api/v1/sprechen/strom` (Satz für Satz
als NDJSON, je Zeile eine `StromZeile`, unterschieden am Feld `art`). Die Modelle stehen im Schema der App, ein Kunde
liest den Vertrag dort."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .plan import StimmWahl


class SprechenAnfrage(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    stimme: StimmWahl | None = None          # ohne: die Stimme ab Werk
    sprache: str | None = None               # ohne: die Sprache der App
    tempo: float = Field(1.0, ge=0.5, le=2.0)
    ausschreiben: bool = True                # Zahlen, Einheiten, Abkürzungen, Datum und Uhrzeit sprechbar machen


class StromAnfrage(SprechenAnfrage):
    text: str = Field(min_length=1, max_length=8000)


class _Zeile(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)   # `art` steht im Schema als Pflicht


class StromSatz(_Zeile):
    """Ein gesprochener Satz, sobald er fertig ist."""
    art: Literal["satz"] = "satz"
    nr: int = Field(ge=0, description="Nummer des Satzes, ab 0, ohne Lücken")
    text: str = Field(description="Der Satz wie im Eingabetext: eingabe[von_zeichen:bis_zeichen]")
    gesprochen: str = Field(description="Was gesprochen wurde (mit `ausschreiben` die Sprechfassung)")
    von_zeichen: int = Field(ge=0, description="Lage im Eingabetext in Zeichen (Unicode-Codepunkte, ab 0), zum Mitlesen")
    bis_zeichen: int = Field(ge=0, description="Ende im Eingabetext, ausschließlich")
    dauer_ms: int = Field(ge=0)
    ton: str = Field(description="Base64 einer WAV, PCM 16 Bit, 24 kHz mono")


class StromEnde(_Zeile):
    """Letzte Zeile, wenn alles gesprochen ist."""
    art: Literal["ende"] = "ende"
    saetze: int = Field(ge=0)
    dauer_ms: int = Field(ge=0, description="Summe der Sätze, ohne Pausen")


class StromFehler(_Zeile):
    """Letzte Zeile, wenn das Sprechen mitten im Strom scheitert."""
    art: Literal["fehler"] = "fehler"
    meldung: str


StromZeile = Annotated[StromSatz | StromEnde | StromFehler, Field(discriminator="art")]
