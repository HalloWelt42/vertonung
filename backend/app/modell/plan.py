"""Der Vertonungsplan (Datei `<Stamm>.vertonung.json`, Format `vertonung/1`): Rollen mit Stimmen und Abschnitte mit
Text, auf Wunsch mit Zeitfenster. Ein einziges Werk führt jeden Plan aus; die Arten unterscheiden sich nur darin, wie
der Plan entsteht. Ob ein Abschnitt neu gesprochen werden muss, entscheidet seine Prüfsumme (Text, Stimme, Tempo,
Sprache) gegen die, mit der er zuletzt gesprochen wurde."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

Art = Literal["vorlesen", "dialog", "zeitgenau"]
ARTEN: dict[str, str] = {"vorlesen": "Vorlesen", "dialog": "Dialog", "zeitgenau": "Zeitgenau"}
Zielformat = Literal["mp3", "wav", "flac", "ogg", "wie_quelle"]
Stand = Literal["offen", "gesprochen", "geaendert"]
Weg = Literal["frei", "luecke", "gestaucht", "geschoben"]


class StimmWahl(BaseModel):
    art: Literal["klon", "katalog"]
    knoten_id: UUID | None = None          # Referenz der Klonstimme
    name: str | None = None                # feste Stimme des Sprechdienstes

    @model_validator(mode="after")
    def _vollstaendig(self) -> StimmWahl:
        if self.art == "klon" and self.knoten_id is None:
            raise ValueError("Klonstimme ohne Referenz")
        if self.art == "katalog" and not self.name:
            raise ValueError("Katalogstimme ohne Namen")
        return self

    @property
    def schluessel(self) -> str:
        return f"klon:{self.knoten_id}" if self.art == "klon" else f"katalog:{self.name}"


class Rolle(BaseModel):
    kennung: str = Field(pattern=r"^r[0-9]{1,3}$")
    name: str = Field(min_length=1, max_length=80)
    stimme: StimmWahl
    tempo: float = Field(1.0, ge=0.5, le=2.0)


class Bericht(BaseModel):
    """Wie ein Abschnitt entstand: Versuche, Ersatzstimme, Teilstücke; zeitgenau auch Lage, Stauchung und Versatz."""

    versuche: int = 1
    ersatz: bool = False
    stuecke: int = 1
    weg: Weg | None = None
    stauchung: float = 1.0
    versatz_s: float = 0.0


class Abschnitt(BaseModel):
    nr: int = Field(ge=1)
    rolle: str
    text: str = Field(min_length=1, max_length=5000)        # was gesprochen wird (bei Übersetzung: die Übersetzung)
    original: str | None = Field(None, max_length=5000)     # Text in der Sprache der Quelle, wenn übersetzt wird
    uebersetzt_aus: str | None = None                       # Prüfsumme von Original und Zielsprache der Übersetzung
    start: float | None = Field(None, ge=0)
    ende: float | None = Field(None, ge=0)
    pause_danach_s: float = Field(0.35, ge=0, le=10)
    gesprochen_als: str | None = None      # Prüfsumme beim letzten Sprechen
    dauer_s: float | None = None           # Länge des Gesprochenen (vor dem Stauchen)
    bericht: Bericht | None = None

    def soll(self, rolle: Rolle, sprache: str) -> str:
        roh = "\x1f".join([self.text.strip(), rolle.stimme.schluessel, f"{rolle.tempo:.3f}", sprache])
        return hashlib.sha256(roh.encode("utf-8")).hexdigest()[:20]

    def uebersetzung_noetig(self, sprache: str) -> bool:
        return self.original is not None and self.uebersetzt_aus != uebersetzungssumme(self.original, sprache)

    def stand(self, rolle: Rolle, sprache: str) -> Stand:
        if self.gesprochen_als is None:
            return "offen"
        return "gesprochen" if self.gesprochen_als == self.soll(rolle, sprache) else "geaendert"


def uebersetzungssumme(original: str, sprache: str) -> str:
    return hashlib.sha256(f"{original.strip()}\x1f{sprache}".encode("utf-8")).hexdigest()[:20]


class Quelle(BaseModel):
    knoten_id: UUID
    pfad: str
    etag: str | None = None


class Ziel(BaseModel):
    format: Zielformat = "mp3"


class Ergebnis(BaseModel):
    knoten_id: UUID
    pfad: str
    dauer_s: float
    erstellt_am: datetime
    wellenform: list[int] = Field(default_factory=list)   # 0 bis 100 je Punkt, für den Spieler


class Plan(BaseModel):
    format: Literal["vertonung/1"] = "vertonung/1"
    art: Art
    name: str = Field(min_length=1, max_length=200)
    quelle: Quelle | None = None
    quelle_dauer_s: float | None = None    # zeitgenau: Länge der Aufnahme, das Ergebnis wird mindestens so lang
    sprache: str = "de"                    # in dieser Sprache wird gesprochen
    ausgangssprache: str | None = None     # Sprache der Quelle, wenn übersetzt wird
    rollen: list[Rolle] = Field(min_length=1)
    abschnitte: list[Abschnitt] = Field(default_factory=list)
    ziel: Ziel = Field(default_factory=Ziel)
    ergebnis: Ergebnis | None = None
    geaendert_am: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _stimmig(self) -> Plan:
        kennungen = [r.kennung for r in self.rollen]
        if len(set(kennungen)) != len(kennungen):
            raise ValueError("Rollen doppelt")
        for a in self.abschnitte:
            if a.rolle not in kennungen:
                raise ValueError(f"Abschnitt {a.nr}: unbekannte Rolle {a.rolle}")
        if self.art == "zeitgenau" and any(a.start is None or a.ende is None for a in self.abschnitte):
            raise ValueError("Zeitgenau braucht Zeiten in jedem Abschnitt")
        return self

    def rolle(self, kennung: str) -> Rolle:
        return next(r for r in self.rollen if r.kennung == kennung)

    def stand(self, a: Abschnitt) -> Stand:
        return a.stand(self.rolle(a.rolle), self.sprache)

    def zu_sprechen(self) -> list[Abschnitt]:
        return [a for a in self.abschnitte if self.stand(a) != "gesprochen" or a.uebersetzung_noetig(self.sprache)]

    def zu_uebersetzen(self) -> list[Abschnitt]:
        return [a for a in self.abschnitte if a.uebersetzung_noetig(self.sprache)]
