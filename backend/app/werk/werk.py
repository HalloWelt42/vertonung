"""Das Werk führt jeden Vertonungsplan aus, gleich welcher Art:

1. Sprechen je Abschnitt, der nicht schon mit gleicher Prüfsumme im Zwischenspeicher liegt: lange Sätze in Stücke
   (höchstens 180 Zeichen), jedes Stück bis dreimal versuchen und prüfen (Aussetzer, Echo), das erste gute bleibt;
   scheitert die Stimme, spricht die Ersatzstimme (vermerkt). Nie bleibt etwas stumm.
2. Fügen im Arbeitsformat (Gleitkomma, 24 kHz mono): Stücke mit Gleichleistungsblende; Vorlesen und Dialog
   hintereinander mit Pausen, zeitgenau an ihre Zeiten (Stille nutzen, stauchen, schieben).
3. Genau einmal in das Zielformat schreiben.

Abbrechen geht zwischen zwei Abschnitten; Gesprochenes bleibt im Zwischenspeicher, ein neuer Lauf spricht nur den Rest.
"""

from __future__ import annotations

import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from appkern.ton import ARBEIT, Ton, Tonformat

from ..modell.plan import Bericht, Plan, StimmWahl
from ..saetze import stuecke
from ..sprechen import Gewaehlt, Katalogstimme, Sprechdienst
from . import fuegen
from .pruefen import befund
from .zeitlage import Fenster, legen

RATE = ARBEIT.rate
VERSUCHE = 3
GRENZE_PEGEL = 0.98            # liegt die Mischung darüber, wird sie als Ganzes leiser (nie verzerrt)

Fortschritt = Callable[[float, str], Awaitable[None]]
Pruefen = Callable[[], Awaitable[None]]


@dataclass
class Gesprochen:
    werte: np.ndarray
    versuche: int
    ersatz: bool
    stuecke: int


class Werk:
    def __init__(self, ton: Ton, dienst: Sprechdienst, *, ersatzstimme: Callable[[], str]) -> None:
        self.ton = ton
        self.dienst = dienst
        self._ersatz = ersatzstimme

    async def _stueck(self, text: str, stimme: Gewaehlt, sprache: str, tempo: float, arbeit: Path,
                      titel: str) -> tuple[np.ndarray | None, int]:
        bestes: np.ndarray | None = None
        for versuch in range(1, VERSUCHE + 1):
            roh = arbeit / f"stueck-{versuch}.wav"
            await self.dienst.sprechen(text, stimme, sprache, tempo, roh, titel=titel)
            werte = fuegen.stille_kuerzen(await self.ton.lesen(roh, RATE), RATE)
            spitze = float(np.max(np.abs(werte))) if werte.size else 0.0
            if befund(text, werte.size / RATE, spitze) == "gut":
                bestes = werte
                break
        return bestes, versuch

    async def abschnitt_sprechen(self, text: str, stimme: Gewaehlt, sprache: str, tempo: float, *, titel: str = "") -> Gesprochen:
        teile: list[np.ndarray] = []
        versuche, ersatz = 0, False
        with tempfile.TemporaryDirectory(prefix="vertonung-") as ordner:
            arbeit = Path(ordner)
            stuecke_ = stuecke(text)
            for teil in stuecke_:
                werte, n = await self._stueck(teil, stimme, sprache, tempo, arbeit, titel)
                versuche = max(versuche, n)
                if werte is None:
                    ersatz = True
                    werte, _ = await self._stueck(teil, Katalogstimme(self._ersatz()), sprache, tempo, arbeit, titel)
                if werte is None:
                    raise RuntimeError(f"Auch die Ersatzstimme bleibt stumm: {teil[:60]}")
                teile.append(werte)
        return Gesprochen(werte=fuegen.blenden(teile, RATE), versuche=versuche, ersatz=ersatz, stuecke=len(teile))

    async def ausfuehren(self, plan: Plan, *, stimme: Callable[[StimmWahl], Awaitable[Gewaehlt]], speicher: Path,
                         ziel: Path, format: Tonformat, fortschritt: Fortschritt, pruefen: Pruefen,
                         komfort: float, hoechstens: float) -> Plan:
        """Führt `plan` aus und schreibt das Ergebnis nach `ziel`; der zurückgegebene Plan trägt Prüfsummen, Dauern und
        Berichte. `speicher` ist der Zwischenspeicher dieses Plans (je Abschnitt eine Datei im Arbeitsformat)."""
        speicher.mkdir(parents=True, exist_ok=True)
        plan = plan.model_copy(deep=True)
        gewaehlt: dict[str, Gewaehlt] = {}
        werte: dict[int, np.ndarray] = {}
        gesamt = len(plan.abschnitte)
        for i, a in enumerate(plan.abschnitte):
            await pruefen()
            rolle = plan.rolle(a.rolle)
            soll = a.soll(rolle, plan.sprache)
            datei = abschnitt_datei(speicher, a.nr, soll)
            if a.gesprochen_als == soll and datei.is_file():
                werte[a.nr] = await self.ton.lesen(datei, RATE)
            else:
                await fortschritt(i / gesamt, f"Abschnitt {a.nr} von {gesamt}")
                if rolle.stimme.schluessel not in gewaehlt:
                    gewaehlt[rolle.stimme.schluessel] = await stimme(rolle.stimme)
                g = await self.abschnitt_sprechen(a.gesprochen(plan.sprache), gewaehlt[rolle.stimme.schluessel], plan.sprache, rolle.tempo,
                                                  titel=f"{plan.name}, Abschnitt {a.nr}")
                await self.ton.schreiben(g.werte, RATE, datei, ARBEIT)
                for alt in speicher.glob(f"{a.nr:05d}-*.wav"):
                    if alt != datei:
                        alt.unlink(missing_ok=True)
                werte[a.nr] = g.werte
                a.gesprochen_als, a.bericht = soll, Bericht(versuche=g.versuche, ersatz=g.ersatz, stuecke=g.stuecke)
            a.dauer_s = round(werte[a.nr].size / RATE, 3)
        await fortschritt(1.0, "Fügen")
        gesamt_werte = await self._fuegen(plan, werte, komfort, hoechstens)
        spitze = float(np.max(np.abs(gesamt_werte))) if gesamt_werte.size else 0.0
        if spitze > GRENZE_PEGEL:
            gesamt_werte = gesamt_werte * (GRENZE_PEGEL / spitze)
        await self.ton.schreiben(gesamt_werte, RATE, ziel, format)
        return plan

    async def _fuegen(self, plan: Plan, werte: dict[int, np.ndarray], komfort: float, hoechstens: float) -> np.ndarray:
        if plan.art != "zeitgenau":
            return fuegen.folge([(werte[a.nr], a.pause_danach_s) for a in plan.abschnitte], RATE)
        fenster = [Fenster(a.start or 0.0, a.ende or 0.0, werte[a.nr].size / RATE) for a in plan.abschnitte]
        lagen = legen(fenster, quelle_ende=plan.quelle_dauer_s, komfort=komfort, hoechstens=hoechstens)
        stuecke_: list[tuple[np.ndarray, float]] = []
        for a, lage in zip(plan.abschnitte, lagen):
            w = werte[a.nr]
            if lage.stauchung > 1.0001:
                w = await self.ton.stauchen(w, RATE, lage.stauchung)
            stuecke_.append((w, lage.beginn))
            bericht = a.bericht or Bericht()
            a.bericht = bericht.model_copy(update={"weg": lage.weg, "stauchung": lage.stauchung, "versatz_s": lage.versatz_s})
        return fuegen.legen(stuecke_, RATE, mindestens_s=plan.quelle_dauer_s or 0.0)


def abschnitt_datei(speicher: Path, nr: int, soll: str) -> Path:
    """Gesprochener Abschnitt im Zwischenspeicher eines Plans (Arbeitsformat), je Prüfsumme eine Datei."""
    return speicher / f"{nr:05d}-{soll}.wav"


def ziel_format(art: str, format: str, mp3_bitrate: str, quelle: Tonformat | None) -> tuple[Tonformat, str]:
    """(Format, Endung) des Ergebnisses: zeitgenau in Rate und Kanälen der Quelle (WAV, oder AAC als M4A für lange
    Videos), sonst wie eingestellt, mono 24 kHz."""
    if art == "zeitgenau" or format in ("wie_quelle", "m4a"):
        q = quelle or Tonformat(rate=RATE, kanaele=1, kodierung="pcm_s16le")
        if format == "m4a":
            return Tonformat(rate=q.rate, kanaele=q.kanaele, kodierung="aac", bitrate="192k"), ".m4a"
        return Tonformat(rate=q.rate, kanaele=q.kanaele, kodierung="pcm_s16le"), ".wav"
    return {
        "mp3": (Tonformat(rate=RATE, kanaele=1, kodierung="libmp3lame", bitrate=mp3_bitrate), ".mp3"),
        "wav": (Tonformat(rate=RATE, kanaele=1, kodierung="pcm_s16le"), ".wav"),
        "flac": (Tonformat(rate=RATE, kanaele=1, kodierung="flac"), ".flac"),
        "ogg": (Tonformat(rate=RATE, kanaele=1, kodierung="libopus", bitrate="48k"), ".ogg"),
    }[format]
