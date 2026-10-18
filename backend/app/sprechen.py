"""Die Sprechdienste des Klangwerks, erreicht über die Leitstelle: feste Stimmen (`POST /tts`, Katalog über
`GET /tts/voices`) und Klonstimmen (`POST /tts/clone` mit Referenzprobe). Beide liefern WAV, 16 Bit, 24 kHz mono, die
man beim selben Dienst abholt (`GET /tts/audio/<datei>`). Hier wird nur übersetzt; Prüfen und Fügen macht das Werk."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from appkern.leitstelle import Leitstelle

SPRACHNAMEN = {"de": "german", "en": "english", "fr": "french", "es": "spanish", "it": "italian"}


class KeineLeitstelle(Exception):
    """Die App ist noch nicht mit einer Leitstelle verbunden."""


@dataclass(frozen=True)
class Katalogstimme:
    name: str


@dataclass(frozen=True)
class Klonstimme:
    referenz: Path            # Referenzprobe als Datei (aus der Kellerwolke geholt)
    referenztext: str


Gewaehlt = Katalogstimme | Klonstimme


class Sprechdienst:
    def __init__(self, leitstelle: Callable[[], Leitstelle | None], namen: Callable[[], tuple[str, str]]) -> None:
        """`namen` liefert die Kennungen der Dienste für feste Stimmen und für Klonstimmen (aus den Einstellungen)."""
        self._ls = leitstelle
        self._namen = namen

    def _leitstelle(self) -> Leitstelle:
        ls = self._ls()
        if ls is None:
            raise KeineLeitstelle("Keine Leitstelle eingerichtet")
        return ls

    async def katalog(self) -> list[str]:
        antwort = await self._leitstelle().dienst(self._namen()[0]).json("GET", "/tts/voices", titel="Stimmen des Katalogs")
        return [str(s) for s in antwort.get("speakers") or []]

    async def sprechen(self, text: str, stimme: Gewaehlt, sprache: str, tempo: float, ziel: Path, *, titel: str = "") -> Path:
        sprache_name = SPRACHNAMEN.get(sprache, "german")
        if isinstance(stimme, Katalogstimme):
            dienst = self._leitstelle().dienst(self._namen()[0])
            antwort = await dienst.json("POST", "/tts", titel=titel,
                                        json={"text": text, "voice": stimme.name, "language": sprache_name, "speed": tempo})
        else:
            dienst = self._leitstelle().dienst(self._namen()[1])
            with open(stimme.referenz, "rb") as referenz:
                antwort = await dienst.json("POST", "/tts/clone", titel=titel,
                                            data={"text": text, "ref_text": stimme.referenztext, "language": sprache_name,
                                                  "speed": str(tempo)},
                                            files={"ref_audio": (stimme.referenz.name, referenz, "audio/wav")})
        return await dienst.herunterladen(f"/tts/audio/{antwort['filename']}", ziel, titel=titel)
