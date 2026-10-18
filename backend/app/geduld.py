"""Geduld je Auftrag: alles, was ein Auftrag über die Leitstelle ruft (Tondienst, Sprechen und Klonen, Hören, Übersetzen),
wird wiederholt, solange sie sagt, dass es gerade nicht geht (Neustart von Leitstelle oder Maschinenraum, Dienst lädt);
der Auftrag zeigt, worauf er wartet, und lässt sich dabei abbrechen (`appkern.leitstelle.geduldig`). Eine kurze Pause
der Umgebung bricht so keine Vertonung mehr ab (Lehre 31 des Appkerns)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from appkern.auftraege import Kontext
from appkern.leitstelle import Leitstelle, geduldig
from appkern.ton import GeduldigeTonarbeit, Tonarbeit

from .sprechen import Gewaehlt, Sprechdienst


@dataclass(frozen=True)
class Geduld:
    melden: Callable[[str], Awaitable[None]] | None = None
    pruefen: Callable[[], Awaitable[None]] | None = None

    @classmethod
    def fuer(cls, k: Kontext) -> "Geduld":
        async def melden(text: str) -> None:
            await k.fortschritt(None, text)
        return cls(melden=melden, pruefen=k.pruefen)

    async def __call__(self, aufruf, was: str):
        return await geduldig(aufruf, was=was, melden=self.melden, pruefen=self.pruefen)

    def ton(self, ton: Tonarbeit) -> Tonarbeit:
        return GeduldigeTonarbeit(ton, melden=self.melden, pruefen=self.pruefen)


class GeduldigesSprechen:
    """Sprechen und Klonen wie `Sprechdienst`, aber geduldig."""

    def __init__(self, dienst: Sprechdienst, geduld: Geduld) -> None:
        self.dienst, self.geduld = dienst, geduld

    async def sprechen(self, text: str, stimme: Gewaehlt, sprache: str, tempo: float, ziel: Path, *, titel: str = "") -> Path:
        return await self.geduld(lambda: self.dienst.sprechen(text, stimme, sprache, tempo, ziel, titel=titel), "Sprechen")


class GeduldigeLeitstelle:
    """Sprachmodell (chat) wie die Leitstelle, aber geduldig; für das Übersetzen."""

    def __init__(self, ls: Leitstelle, geduld: Geduld) -> None:
        self.ls, self.geduld = ls, geduld

    async def chat(self, nachrichten, **weiter):
        return await self.geduld(lambda: self.ls.chat(nachrichten, **weiter), "Sprachmodell")
