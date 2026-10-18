"""Das Werk führt jeden Vertonungsplan aus, gleich welcher Art. Es rechnet selbst keinen Ton (der Pi liefert nur Daten):
messen, blenden, stauchen, legen und kodieren macht die Tonarbeit im Tondienst auf dem Mac; das Werk entscheidet.

1. Sprechen je Abschnitt, der nicht schon mit gleicher Prüfsumme im Zwischenspeicher liegt: lange Sätze in Stücke
   (höchstens 180 Zeichen), jedes Stück bis dreimal versuchen und prüfen (Aussetzer, Echo, gemessen an seiner lauten
   Spanne), das erste gute bleibt; scheitert die Stimme, spricht die Ersatzstimme (vermerkt). Nie bleibt etwas stumm.
   Die Stücke werden ohne Stille an den Rändern mit Gleichleistungsblende zum Abschnitt (WAV 16 Bit, 24 kHz mono).
2. Legen: Vorlesen und Dialog hintereinander mit Pausen, zeitgenau an ihre Zeiten (Stille nutzen, stauchen,
   schieben); die Zeiten rechnet das Werk, gelegt wird im Tondienst.
3. Genau einmal in das Zielformat schreiben, begrenzt auf GRENZE_PEGEL (die Mischung wird als Ganzes leiser, nie
   verzerrt), mit Wellenform.

Abbrechen geht zwischen zwei Abschnitten; Gesprochenes bleibt im Zwischenspeicher, ein neuer Lauf spricht nur den Rest.
"""

from __future__ import annotations

import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from appkern.ton import (
    ARBEIT, Aufbereiten, Blenden, Gelegt, Lage, LautWahl, Legen, Messen, Stueck, Tonarbeit, Tonformat, wav,
)

from ..modell.plan import Bericht, Plan, StimmWahl
from ..saetze import stuecke
from ..sprechen import Gewaehlt, Katalogstimme, Sprechdienst, mit_modus
from .pruefen import befund
from .zeitlage import Fenster, legen

RATE = ARBEIT.rate
VERSUCHE = 3
GRENZE_PEGEL = 0.98            # liegt die Mischung darüber, wird sie als Ganzes leiser (nie verzerrt)
BLENDE_MS = 30                 # Gleichleistungsblende zwischen den Stücken eines Abschnitts
RAND_MS = 5                    # glatte Ränder jedes gelegten Abschnitts
STILLE = LautWahl(rate=RATE, schwelle_db=-45.0, rand_ms=40)      # Stille an den Rändern eines Stücks fällt weg
ABSCHNITT = Tonformat(rate=RATE, kanaele=1, kodierung="pcm_s16le")   # Zwischenspeicher: im Browser direkt spielbar
SPEICHERFASSUNG = "s16"        # steht im Namen jeder Datei des Zwischenspeichers (ältere Fassungen gelten nicht)
WELLENFORM = 400

Fortschritt = Callable[[float, str], Awaitable[None]]
Pruefen = Callable[[], Awaitable[None]]


@dataclass(frozen=True)
class Gutes:
    datei: Path
    von_s: float
    bis_s: float


@dataclass
class Gesprochen:
    datei: Path
    dauer_s: float
    versuche: int
    ersatz: bool
    stuecke: int


class Werk:
    def __init__(self, ton: Tonarbeit, dienst: Sprechdienst, *, ersatzstimme: Callable[[], str],
                 sprachfremd: Callable[[], str] = lambda: "icl") -> None:
        self.ton = ton
        self.dienst = dienst
        self._ersatz = ersatzstimme
        self._sprachfremd = sprachfremd

    async def _stueck(self, text: str, stimme: Gewaehlt, sprache: str, tempo: float, arbeit: Path, nr: int,
                      titel: str) -> tuple[Gutes | None, int]:
        for versuch in range(1, VERSUCHE + 1):
            roh = arbeit / f"stueck-{nr}-{versuch}.wav"
            await self.dienst.sprechen(text, stimme, sprache, tempo, roh, titel=titel)
            laut = (await self.ton.aufbereiten(roh, Aufbereiten(messen=Messen(laut=STILLE)), [],
                                               titel=f"{titel}, prüfen")).messwerte.laut
            if laut is not None and befund(text, laut.dauer_s, laut.spitze) == "gut":
                return Gutes(roh, laut.von_s, laut.bis_s), versuch
        return None, VERSUCHE

    async def abschnitt_sprechen(self, text: str, stimme: Gewaehlt, sprache: str, tempo: float, ziel: Path, *,
                                 titel: str = "") -> Gesprochen:
        """Spricht `text` nach `ziel` (Format ABSCHNITT)."""
        gute: list[Gutes] = []
        versuche, ersatz = 0, False
        with tempfile.TemporaryDirectory(prefix="vertonung-") as ordner:
            arbeit = Path(ordner)
            for nr, teil in enumerate(stuecke(text)):
                g, n = await self._stueck(teil, stimme, sprache, tempo, arbeit, nr, titel)
                versuche = max(versuche, n)
                if g is None:
                    ersatz = True
                    g, _ = await self._stueck(teil, Katalogstimme(self._ersatz()), sprache, tempo, arbeit, nr, titel)
                if g is None:
                    raise RuntimeError(f"Auch die Ersatzstimme bleibt stumm: {teil[:60]}")
                gute.append(g)
            d = await self.ton.blenden([g.datei for g in gute],
                                       Blenden(rate=RATE, blende_ms=BLENDE_MS, format=ABSCHNITT,
                                               stuecke=[Stueck(datei=i, von_s=g.von_s, bis_s=g.bis_s) for i, g in enumerate(gute)]),
                                       ziel, titel=f"{titel}, blenden")
        return Gesprochen(datei=ziel, dauer_s=d.dauer_s, versuche=versuche, ersatz=ersatz, stuecke=len(gute))

    async def ausfuehren(self, plan: Plan, *, stimme: Callable[[StimmWahl], Awaitable[Gewaehlt]], speicher: Path,
                         ziel: Path, format: Tonformat, fortschritt: Fortschritt, pruefen: Pruefen,
                         komfort: float, hoechstens: float) -> tuple[Plan, Gelegt]:
        """Führt `plan` aus und schreibt das Ergebnis nach `ziel`; der zurückgegebene Plan trägt Prüfsummen, Dauern und
        Berichte, dazu kommt, was das Legen gemessen hat (Dauer, Wellenform). `speicher` ist der Zwischenspeicher dieses
        Plans (je Abschnitt eine Datei)."""
        speicher.mkdir(parents=True, exist_ok=True)
        plan = plan.model_copy(deep=True)
        gewaehlt: dict[str, Gewaehlt] = {}
        dateien: dict[int, Path] = {}
        gesamt = len(plan.abschnitte)
        for i, a in enumerate(plan.abschnitte):
            await pruefen()
            rolle = plan.rolle(a.rolle)
            soll = a.soll(rolle, plan.sprache)
            datei = abschnitt_datei(speicher, a.nr, soll)
            if a.gesprochen_als == soll and datei.is_file():
                dauer = wav.dauer(datei)
            else:
                await fortschritt(i / gesamt, f"Abschnitt {a.nr} von {gesamt}")
                if rolle.stimme.schluessel not in gewaehlt:
                    gewaehlt[rolle.stimme.schluessel] = await stimme(rolle.stimme)
                wie = mit_modus(gewaehlt[rolle.stimme.schluessel], rolle.klonmodus, plan.sprache, self._sprachfremd())
                g = await self.abschnitt_sprechen(a.gesprochen(plan.sprache), wie, plan.sprache, rolle.tempo, datei,
                                                  titel=f"{plan.name}, Abschnitt {a.nr}")
                for alt in speicher.glob(f"{a.nr:05d}-*.wav"):
                    if alt != datei:
                        alt.unlink(missing_ok=True)
                dauer = g.dauer_s
                a.gesprochen_als, a.bericht = soll, Bericht(versuche=g.versuche, ersatz=g.ersatz, stuecke=g.stuecke)
            dateien[a.nr] = datei
            a.dauer_s = round(dauer, 3)
        await fortschritt(1.0, "Fügen")
        auftrag = Legen(rate=RATE, lagen=self._lagen(plan, komfort, hoechstens), rand_ms=RAND_MS,
                        mindestens_s=(plan.quelle_dauer_s or 0.0) if plan.art == "zeitgenau" else 0.0,
                        spitze=GRENZE_PEGEL, format=format, endung=ziel.suffix.lower() or ".wav", wellenform=WELLENFORM)
        gelegt = await self.ton.legen([dateien[a.nr] for a in plan.abschnitte], auftrag, ziel, titel=f"{plan.name}, fügen")
        return plan, gelegt

    def _lagen(self, plan: Plan, komfort: float, hoechstens: float) -> list[Lage]:
        """Wohin jeder Abschnitt kommt (Nummer der Datei wie die Abschnitte). Vorlesen und Dialog: hintereinander, nach
        jedem seine Pause; zeitgenau nach der Zeitlage, die auch in den Bericht geht."""
        if plan.art != "zeitgenau":
            lagen, beginn = [], 0.0
            for i, a in enumerate(plan.abschnitte):
                lagen.append(Lage(datei=i, beginn_s=round(beginn, 4)))
                beginn += (a.dauer_s or 0.0) + a.pause_danach_s
            return lagen
        fenster = [Fenster(a.start or 0.0, a.ende or 0.0, a.dauer_s or 0.0) for a in plan.abschnitte]
        lagen = []
        for i, (a, lage) in enumerate(zip(plan.abschnitte, legen(fenster, quelle_ende=plan.quelle_dauer_s, komfort=komfort,
                                                                hoechstens=hoechstens))):
            lagen.append(Lage(datei=i, beginn_s=lage.beginn, stauchung=lage.stauchung if lage.stauchung > 1.0001 else 1.0))
            a.bericht = (a.bericht or Bericht()).model_copy(update={"weg": lage.weg, "stauchung": lage.stauchung,
                                                                    "versatz_s": lage.versatz_s})
        return lagen


def abschnitt_datei(speicher: Path, nr: int, soll: str) -> Path:
    """Gesprochener Abschnitt im Zwischenspeicher eines Plans, je Prüfsumme eine Datei."""
    return speicher / f"{nr:05d}-{soll}.{SPEICHERFASSUNG}.wav"


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
