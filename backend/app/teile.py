"""Die fachlichen Teile der Vertonung, einmal verdrahtet: Ablage (Stimmen, Pläne), Verzeichnis, Sprechdienst, Werk,
Ton. Aufträge und Schnittstelle bekommen dieses eine Objekt statt vieler einzelner Abhängigkeiten."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from appkern.anmeldung import Konto
from appkern.app import Begleiter, Geruest
from appkern.kellerwolke import Kellerwolke
from appkern.ton import Ton

from .ablage.plaene import Plaene
from .ablage.stimmen import Stimmen, zugang
from .einstellungen import AppEinstellungen
from .modell.plan import StimmWahl
from .modell.stimme import Stimme
from .sprechen import Gewaehlt, Katalogstimme, Klonstimme, Sprechdienst
from .verzeichnis import Verzeichnis
from .werk.werk import Werk


class KeinRechtAufStimme(Exception):
    """Eine fremde App wollte eine private Stimme nutzen, ohne auf der Erlaubnisliste zu stehen."""


class Teile(Begleiter):
    def __init__(self, geruest: Geruest[AppEinstellungen]) -> None:
        self.geruest = geruest
        e = lambda: geruest.einstellungen.stand  # noqa: E731
        self.stimmen = Stimmen(lambda: geruest.kellerwolke, geruest.daten / "referenzen")
        self.plaene = Plaene(lambda: geruest.kellerwolke)
        self.verzeichnis = Verzeichnis(geruest.db)
        self.dienst = Sprechdienst(lambda: geruest.leitstelle, lambda: (e().dienst_sprechen, e().dienst_klonen))

    async def starten(self) -> None:
        await self.verzeichnis.einrichten()

    async def stoppen(self) -> None:
        return None

    @property
    def einstellungen(self) -> AppEinstellungen:
        return self.geruest.einstellungen.stand

    @property
    def ton_jetzt(self) -> Ton:
        return Ton(self.einstellungen.ffmpeg_ordner)

    def werk(self) -> Werk:
        """Ein Werk mit dem Ton der aktuellen Einstellungen (ffmpeg kann sich ändern)."""
        return Werk(self.ton_jetzt, self.dienst, ersatzstimme=lambda: self.einstellungen.ersatzstimme)

    @property
    def arbeit(self) -> Path:
        return self.geruest.daten / "arbeit"

    def speicher(self, plan_id: UUID | str) -> Path:
        """Zwischenspeicher eines Plans: je Abschnitt eine Datei im Arbeitsformat."""
        return self.geruest.daten / "abschnitte" / str(plan_id)

    def zugang(self, anfrage: UUID | None = None) -> Kellerwolke:
        kw = zugang(lambda: self.geruest.kellerwolke)
        return kw.mit_anfrage(anfrage) if anfrage else kw

    def plaene_fuer(self, anfrage: UUID | None = None) -> Plaene:
        return self.plaene.fuer(self.zugang(anfrage)) if anfrage else self.plaene

    def darf_privat(self, konto: Konto | None) -> bool:
        """Menschen immer; fremde Apps nur auf der Erlaubnisliste (Medienpool nie)."""
        if konto is None or konto.mensch:
            return True
        app = (konto.app or "").strip().lower()
        return app != "medienpool" and app in {a.strip().lower() for a in self.einstellungen.private_stimmen_fuer}

    async def stimme_pruefen(self, wahl: StimmWahl, konto: Konto | None) -> Stimme | None:
        """Die Klonstimme einer Wahl (None beim Katalog); private nur, wenn der Aufrufer sie nutzen darf."""
        if wahl.art == "katalog":
            return None
        s = await self.stimmen.lesen(wahl.knoten_id)
        if s.bereich == "privat" and not self.darf_privat(konto):
            raise KeinRechtAufStimme("Private Stimmen sind dieser App nicht erlaubt")
        return s

    async def gewaehlt(self, wahl: StimmWahl) -> Gewaehlt:
        """Für das Werk: Katalogname oder die Referenz der Klonstimme als Datei samt Referenztext."""
        if wahl.art == "katalog":
            return Katalogstimme(wahl.name or self.einstellungen.stimme_vorgabe)
        datei, text = await self.stimmen.referenz(wahl.knoten_id)
        return Klonstimme(referenz=datei, referenztext=text)

    async def stimmen_namen(self, wahlen: list[StimmWahl]) -> dict[str, str]:
        namen: dict[str, str] = {}
        for w in wahlen:
            if w.art == "katalog":
                namen[w.schluessel] = w.name or ""
            else:
                try:
                    namen[w.schluessel] = (await self.stimmen.lesen(w.knoten_id)).name
                except Exception:  # noqa: BLE001 - gelöschte Stimme: der Plan bleibt lesbar
                    namen[w.schluessel] = "Stimme fehlt"
        return namen
