"""Die fachlichen Teile der Vertonung, einmal verdrahtet: Ablage (Stimmen, Pläne), Verzeichnis, Sprechdienst, Werk,
Ton. Aufträge und Schnittstelle bekommen dieses eine Objekt statt vieler einzelner Abhängigkeiten."""

from __future__ import annotations

import asyncio
import logging
import shutil

from pathlib import Path
from uuid import UUID

from appkern.anmeldung import Konto
from appkern.app import Begleiter, Geruest
from appkern.kellerwolke import Kellerwolke, NichtGefunden
from appkern.leitstelle import hoeren
from appkern.ton import Ton

from .ablage.plaene import Plaene
from .ablage.stimmen import Stimmen, zugang
from .dienstablage import Ablage, DienstAblage
from .referenz import WortZeit
from .einstellungen import AppEinstellungen
from .modell.plan import StimmWahl
from .modell.stimme import Stimme
from .sprechen import Gewaehlt, Katalogstimme, KeineLeitstelle, Klonstimme, Sprechdienst, mit_modus
from .tempo import Sprechtempo
from .verzeichnis import Verzeichnis
from .werk.werk import Werk


class KeinRechtAufStimme(Exception):
    """Eine fremde App wollte eine private Stimme nutzen, ohne auf der Erlaubnisliste zu stehen."""


FRISTEN_TAKT_S = 3600


class Teile(Begleiter):
    def __init__(self, geruest: Geruest[AppEinstellungen]) -> None:
        self.geruest = geruest
        e = lambda: geruest.einstellungen.stand  # noqa: E731
        self.stimmen = Stimmen(lambda: geruest.kellerwolke, geruest.daten / "referenzen")
        self.plaene = Plaene(lambda: geruest.kellerwolke)
        self.verzeichnis = Verzeichnis(geruest.db)
        self.tempo = Sprechtempo(geruest.db, lambda: e().sprechtempo)
        self.dienstablage = DienstAblage(geruest.db)
        self._fristen: asyncio.Task | None = None
        self.dienst = Sprechdienst(lambda: geruest.leitstelle, lambda: (e().dienst_sprechen, e().dienst_klonen))

    async def starten(self) -> None:
        await self.verzeichnis.einrichten()
        await self.tempo.einrichten()
        await self.dienstablage.einrichten()
        self._fristen = asyncio.create_task(self._fristen_wahren())

    async def stoppen(self) -> None:
        if self._fristen:
            self._fristen.cancel()

    async def dienst_wegraeumen(self, a: Ablage) -> None:
        """Aufnahme eines Dienstauftrags samt Begleitern (Transkript, Plan, Ergebnis) in den Papierkorb der Kellerwolke,
        dazu Eintrag im Verzeichnis und Zwischenspeicher des Plans."""
        try:
            await self.zugang().loeschen(a.haupt_id)
        except NichtGefunden:
            pass                                   # schon weg (etwa von Hand)
        if a.plan_id:
            await self.verzeichnis.entfernen(a.plan_id)
            shutil.rmtree(self.speicher(a.plan_id), ignore_errors=True)
        await self.dienstablage.austragen(a.auftrag_id)

    async def _fristen_wahren(self) -> None:
        """Stündlich: was nicht bleiben soll und nicht abgeholt wurde, nach der Frist wegräumen (nie, solange der
        Auftrag noch läuft)."""
        while True:
            await asyncio.sleep(FRISTEN_TAKT_S)
            try:
                for a in await self.dienstablage.faellige():
                    if (await self.geruest.auftraege.holen(a.auftrag_id)).zustand in ("wartet", "laeuft"):
                        continue
                    await self.dienst_wegraeumen(a)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - die Kellerwolke kann kurz fehlen; in einer Stunde wieder
                logging.getLogger("vertonung").warning("Dienstablage: Wegräumen nach Frist gescheitert", exc_info=True)

    @property
    def einstellungen(self) -> AppEinstellungen:
        return self.geruest.einstellungen.stand

    @property
    def ton_jetzt(self) -> Ton:
        return Ton(self.einstellungen.ffmpeg_ordner)

    def werk(self) -> Werk:
        """Ein Werk mit dem Ton der aktuellen Einstellungen (ffmpeg kann sich ändern)."""
        return Werk(self.ton_jetzt, self.dienst, ersatzstimme=lambda: self.einstellungen.ersatzstimme,
                    sprachfremd=lambda: self.einstellungen.klonen_sprachfremd)

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
        """Für das Werk: Katalogname oder die Referenz der Klonstimme als Datei samt Referenztext. Fehlt der Text (etwa
        bei übernommenen Stimmen), wird er einmal herausgehört und in den Angaben gespeichert: das Modell klont nur mit
        einem Text, der genau zur Referenz passt, sauber."""
        if wahl.art == "katalog":
            return Katalogstimme(wahl.name or self.einstellungen.stimme_vorgabe)
        datei, text = await self.stimmen.referenz(wahl.knoten_id)
        s = await self.stimmen.lesen(wahl.knoten_id)
        sprache = s.angaben.sprache if s.angaben else "de"
        if not text.strip() and self.geruest.leitstelle is not None:
            text = await self.hoeren_text(datei, sprache)
            if text and s.angaben:
                await self.stimmen.aendern(wahl.knoten_id, s.angaben.model_copy(update={"referenztext": text[:2000]}))
        return Klonstimme(referenz=datei, referenztext=text, sprache=sprache)

    async def tempo_schluessel(self, rolle, sprache: str) -> str:
        """Unter welchem Schlüssel das Sprechtempo einer Rolle gemessen wird: die Stimme, bei einer Klonstimme im
        Abdruckmodus mit Zusatz (sie spricht dann anders schnell als mit Referenztext)."""
        if rolle.stimme.art != "klon":
            return rolle.stimme.schluessel
        s = await self.stimmen.lesen(rolle.stimme.knoten_id)
        probe = Klonstimme(referenz=Path("-"), referenztext=(s.angaben.referenztext if s.angaben else ""),
                           sprache=s.angaben.sprache if s.angaben else "de")
        modus = mit_modus(probe, rolle.klonmodus, sprache, self.einstellungen.klonen_sprachfremd).modus
        return rolle.stimme.schluessel + ("|abdruck" if modus == "abdruck" else "")

    async def hoeren_text(self, datei: Path, sprache: str) -> str:
        """Was in einer Aufnahme gesprochen wird (Hördienst über die Leitstelle)."""
        return (await self._hoeren(datei, sprache)).text

    async def hoeren_woerter(self, datei: Path, sprache: str) -> list[WortZeit]:
        """Die Wörter einer Aufnahme mit Zeiten und Sicherheit (zum Zuschneiden einer Probe)."""
        gehoert = await self._hoeren(datei, sprache)
        return [WortZeit(w.wort, w.start, w.ende) for s in gehoert.segmente for w in s.woerter]

    async def _hoeren(self, datei: Path, sprache: str):
        ls = self.geruest.leitstelle
        if ls is None:
            raise KeineLeitstelle("Zum Hören braucht die Vertonung die Leitstelle")
        return await hoeren(ls, self.einstellungen.dienst_hoeren, datei, sprache, titel="Vertonung: hören")

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
