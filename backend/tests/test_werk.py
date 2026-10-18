"""Werk mit nachgestelltem Sprechdienst (echter Ton aus ffmpeg, Länge nach Text) und der Tonarbeit, die hier rechnet
(`TonHier`, im Betrieb der Tondienst auf dem Mac): Vorlesen als MP3, nur Geändertes neu sprechen, Aussetzer wiederholen,
Ersatzstimme, zeitgenau in Format und Länge der Quelle, Zwischenspeicher im Browser spielbar."""

import asyncio
from pathlib import Path

import numpy as np
import pytest

from appkern.ton import Ton, TonHier, Tonformat, programm, wav

from app.modell.plan import StimmWahl
from app.planen import Segment, aus_dialog, aus_segmenten, aus_text
from app.sprechen import Katalogstimme
from app.werk.werk import Werk, ziel_format

SERENA = StimmWahl(art="katalog", name="serena")
STUMM = StimmWahl(art="katalog", name="stumm")


class Schein:
    """Spricht 15 Zeichen je Sekunde als Sinuston; die Stimme "stumm" liefert Stille, `aussetzer` Texte einmal leer."""

    def __init__(self, aussetzer: set[str] | None = None) -> None:
        self.aufrufe: list[tuple[str, str]] = []
        self.aussetzer = set(aussetzer or ())

    async def sprechen(self, text, stimme, sprache, tempo, ziel: Path, *, titel=""):
        name = stimme.name if isinstance(stimme, Katalogstimme) else "klon"
        self.aufrufe.append((name, text))
        dauer = max(0.3, len(text) / 15)
        laut = "0" if name == "stumm" or text in self.aussetzer else "0.5"
        self.aussetzer.discard(text)
        p = await asyncio.create_subprocess_exec(programm("ffmpeg"), "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi",
                                                 "-i", f"sine=f=330:d={dauer:.3f}:sample_rate=24000", "-af", f"volume={laut}",
                                                 "-ac", "1", "-c:a", "pcm_s16le", str(ziel))
        assert await p.wait() == 0
        return ziel


async def _stimme(w):
    return Katalogstimme(w.name)


async def _nichts(*_):
    return None


async def ausfuehren(werk, plan, tmp_path, name="ergebnis", quelle=None):
    format, endung = ziel_format(plan.art, plan.ziel.format, "128k", quelle)
    ziel = tmp_path / f"{name}{endung}"
    neu, gelegt = await werk.ausfuehren(plan, stimme=_stimme, speicher=tmp_path / "speicher", ziel=ziel, format=format,
                                        fortschritt=_nichts, pruefen=_nichts, komfort=1.15, hoechstens=1.5)
    assert gelegt.wellenform and gelegt.datei.dauer_s > 0
    return neu, ziel


async def test_vorlesen_mp3_und_nur_geaendertes(tmp_path):
    schein = Schein(aussetzer={"Zweiter Satz mit etwas mehr Text darin."})
    werk = Werk(TonHier(), schein, ersatzstimme=lambda: "aiden")
    plan = aus_text("Brief", "Erster Satz hier. Zweiter Satz mit etwas mehr Text darin. Dritter.", SERENA)
    neu, ziel = await ausfuehren(werk, plan, tmp_path)
    e = await Ton().eigenschaften(ziel)
    assert (e.rate, e.kanaele, e.kodierung) == (24000, 1, "mp3")
    erwartet = sum(a.dauer_s for a in neu.abschnitte) + 0.35 * 2
    assert e.dauer_s == pytest.approx(erwartet, abs=0.12)
    assert [a.bericht.versuche for a in neu.abschnitte] == [1, 2, 1]          # der Aussetzer wurde wiederholt
    assert all(neu.stand(a) == "gesprochen" for a in neu.abschnitte)

    speicher = sorted((tmp_path / "speicher").glob("*.wav"))
    assert len(speicher) == 3 and all(wav.dauer(d) > 0 for d in speicher)          # 16 Bit, ohne Wandlung abspielbar

    schein.aufrufe.clear()
    neu.abschnitte[2].text = "Dritter, jetzt anders."
    neu2, _ = await ausfuehren(werk, neu, tmp_path, "zweiter")
    assert schein.aufrufe == [("serena", "Dritter, jetzt anders.")]            # nur der geänderte


async def test_ersatzstimme_nie_stumm(tmp_path):
    schein = Schein()
    werk = Werk(TonHier(), schein, ersatzstimme=lambda: "aiden")
    plan = aus_dialog("Szene", "Mara: Hallo, wer ist da?\nJonas: Niemand, schlaf weiter.", {"Jonas": STUMM}, SERENA)
    neu, ziel = await ausfuehren(werk, plan, tmp_path)
    assert [a.bericht.ersatz for a in neu.abschnitte] == [False, True]
    assert ("aiden", "Niemand, schlaf weiter.") in schein.aufrufe
    werte = await Ton().lesen(ziel, 24000)
    assert float(np.max(np.abs(werte))) > 0.03                                 # Prüfton 1/8 mal 0,5, nicht still


async def test_zeitgenau_wie_quelle(tmp_path):
    schein = Schein()
    werk = Werk(TonHier(), schein, ersatzstimme=lambda: "aiden")
    seg = [Segment(1.0, 3.0, "Kurzer erster Satz.", "Anna"),
           Segment(3.2, 4.0, "Ein deutlich zu langer zweiter Satz, der nicht passt.", "Krüger"),
           Segment(8.0, 9.0, "Danach wieder Ruhe.", "Anna")]
    plan = aus_segmenten("Runde", seg, {}, SERENA, quelle=None, quelle_dauer_s=12.0)
    neu, ziel = await ausfuehren(werk, plan, tmp_path, quelle=Tonformat(rate=48000, kanaele=2, kodierung="pcm_s16le"))
    e = await Ton().eigenschaften(ziel)
    assert (e.rate, e.kanaele, e.kodierung) == (48000, 2, "pcm_s16le") and e.dauer_s == pytest.approx(12.0, abs=0.02)
    wege = [a.bericht.weg for a in neu.abschnitte]
    assert wege[0] == "frei" and wege[1] in ("gestaucht", "luecke") and neu.abschnitte[1].bericht.stauchung >= 1.0
