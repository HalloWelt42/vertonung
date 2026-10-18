"""Nachgestellte Leitstelle mit Sprech- und Klondienst (Prüfton, 15 Zeichen je Sekunde, WAV 16 Bit 24 kHz mono) und
eine Weiche, die nur sie abfängt; alles andere (die echte Kellerwolke) geht durch."""

from __future__ import annotations

import io
import json
import re
import wave

import httpx
import numpy as np

HOST = "ls.test"
ADRESSE = f"http://{HOST}"


def ton(dauer_s: float, frequenz: float = 220.0) -> bytes:
    t = np.arange(int(24000 * dauer_s)) / 24000
    werte = (0.3 * np.sin(2 * np.pi * frequenz * t) * 32767).astype("<i2")
    puffer = io.BytesIO()
    with wave.open(puffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(werte.tobytes())
    return puffer.getvalue()


class ScheinLeitstelle:
    def __init__(self) -> None:
        self.aufrufe: list[tuple[str, str]] = []      # (Stimme oder "klon", Text)
        self.dateien: dict[str, bytes] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        m = re.match(r"^/v1/dienste/([^/]+)/(.*)$", request.url.path)
        if m is None:
            return httpx.Response(404, json={"detail": "nicht da"})
        rest = m.group(2)
        if rest == "tts/voices":
            return httpx.Response(200, json={"speakers": ["serena", "aiden"], "languages": ["german", "english"]})
        if rest in ("tts", "tts/clone"):
            if rest == "tts":
                daten = json.loads(request.content)
                text, stimme = daten["text"], daten["voice"]
            else:
                inhalt = request.content.decode("latin-1")
                text = re.search(r'name="text"\r\n\r\n(.*?)\r\n--', inhalt, re.S).group(1).encode("latin-1").decode("utf-8")
                stimme = "klon"
            self.aufrufe.append((stimme, text))
            name = f"t{len(self.dateien)}.wav"
            self.dateien[name] = ton(max(0.4, len(text) / 15))
            return httpx.Response(200, json={"filename": name, "sample_rate": 24000})
        if rest.startswith("tts/audio/") and rest.rsplit("/", 1)[1] in self.dateien:
            return httpx.Response(200, content=self.dateien[rest.rsplit("/", 1)[1]], headers={"content-type": "audio/wav"})
        return httpx.Response(404, json={"detail": "nicht da"})


class Weiche(httpx.AsyncBaseTransport):
    def __init__(self, schein: ScheinLeitstelle) -> None:
        self.schein = httpx.MockTransport(schein)
        self.echt = httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        ziel = self.schein if request.url.host == HOST else self.echt
        return await ziel.handle_async_request(request)

    async def aclose(self) -> None:
        await self.echt.aclose()
