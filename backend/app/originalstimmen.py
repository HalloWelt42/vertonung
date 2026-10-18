"""Originalstimmen für eine Vertonung (Strecken 2 und 3 der Optimierung): je Sprecher des Transkripts eine Klonstimme.

Eine schon gewonnene Stimme desselben Sprechers wird wiederverwendet (Nutzer 18.10.2026: "ist die Stimme
rausgeschnitten, muss sie nicht erneut rausgeschnitten werden"). Derselbe Sprecher ist, wen die Transkription demselben
Sprecherprofil zuordnet (bestätigt oder als sicherer Vorschlag), sonst wessen Stimmabdruck dem gemerkten einer Stimme
mindestens so ähnlich ist wie die Schwelle "sicher" der Transkription (gleiches Verfahren, gleiche Skala). Sonst wird
die beste Stelle im ganzen Video ausgeschnitten (siehe referenz.py) und als fremde Stimme angelegt, mit Referenztext,
Profil und Abdruck. Wer keine brauchbare
Stelle hat, spricht mit der festen Stimme."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from appkern.kellerwolke import StandVeraltet
from appkern.ton import Tonformat

from .modell.plan import StimmWahl
from .modell.stimme import Herkunft, StimmAngaben
from .referenz import WortZeit, beste
from .werk.fuegen import begrenzen

log = logging.getLogger("vertonung")
RATE = 24000
REFERENZ = Tonformat(rate=RATE, kanaele=1, kodierung="pcm_s16le")
AEHNLICH = 0.8               # ein Vorschlag der Transkription gilt ab dieser Ähnlichkeit als derselbe Sprecher
GLEICH = 0.70                # Abdrücke ab dieser Kosinus-Ähnlichkeit: derselbe Sprecher (Schwelle "sicher" der Transkription)
BLENDE_S = 0.01              # weiche Ränder; der Schnitt liegt ohnehin in der Pause


@dataclass(frozen=True)
class Zuordnung:
    sprecher: str            # Name im Transkript (wie im Plan)
    wahl: StimmWahl
    weg: str                 # "wiederverwendet" (Profil), "wiedererkannt" (Abdruck), "gewonnen" oder "ersatz"
    grund: str = ""


def profil_des_sprechers(s: dict) -> str | None:
    if s.get("profil_id"):
        return str(s["profil_id"])
    if s.get("vorschlag_id") and (s.get("vorschlag_aehnlichkeit") or 0.0) >= AEHNLICH:
        return str(s["vorschlag_id"])
    return None


def aehnlichkeit(a: list[float], b: list[float]) -> float:
    x, y = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    if x.shape != y.shape or not x.size:
        return 0.0
    return float(x @ y / max(np.linalg.norm(x) * np.linalg.norm(y), 1e-12))


def woerter_aus(transkript: dict) -> list[WortZeit]:
    """Alle Wörter mit Zeit, Sprecherkennung und Hörsicherheit (die Segmente tragen den Sprecher)."""
    aus = []
    for seg in transkript.get("segmente") or []:
        for w in seg.get("woerter") or []:
            aus.append(WortZeit(wort=w["wort"], start=float(w["start"]), ende=float(w["ende"]), sprecher=seg.get("sprecher"),
                                sicherheit=w.get("sicherheit")))
    return sorted(aus, key=lambda w: w.start)


def ausschneiden(werte: np.ndarray, von: float, bis: float) -> np.ndarray:
    teil = begrenzen(werte[int(von * RATE): int(bis * RATE)].astype(np.float32).copy())
    n = min(int(BLENDE_S * RATE), teil.size // 2)
    if n:
        rampe = np.linspace(0.0, 1.0, n, dtype=np.float32)
        teil[:n] *= rampe
        teil[-n:] *= rampe[::-1]
    return teil


async def zuordnen(teile, transkript: dict, haupt, video: str, sprache_quelle: str, ersatz: StimmWahl, arbeit: Path) -> list[Zuordnung]:
    """Je Sprecher des Transkripts eine Stimme; der Ton der Aufnahme wird nur geholt, wenn eine Stimme zu gewinnen ist."""
    bekannte: dict[str, str] = {}
    abdruecke: list[tuple[str, list[float]]] = []
    for bereich in ("fremd", "privat"):
        for s in await teile.stimmen.alle(bereich):
            if s.angaben and s.angaben.sprecherprofil:
                bekannte.setdefault(s.angaben.sprecherprofil, s.id)
            if s.angaben and s.angaben.abdruck:
                abdruecke.append((s.id, s.angaben.abdruck))
    woerter = woerter_aus(transkript)
    werte: np.ndarray | None = None
    arbeit.mkdir(parents=True, exist_ok=True)
    aus: list[Zuordnung] = []
    try:
        for s in transkript.get("sprecher") or []:
            name = s.get("name") or s["kennung"]
            profil = profil_des_sprechers(s)
            if profil and profil in bekannte:
                aus.append(Zuordnung(name, StimmWahl(art="klon", knoten_id=bekannte[profil]), "wiederverwendet"))
                continue
            if s.get("abdruck") and abdruecke:
                beste_id, wert = max(((i, aehnlichkeit(s["abdruck"], a)) for i, a in abdruecke), key=lambda x: x[1])
                if wert >= GLEICH:
                    aus.append(Zuordnung(name, StimmWahl(art="klon", knoten_id=beste_id), "wiedererkannt",
                                         f"Ähnlichkeit {wert:.2f}"))
                    continue
            if werte is None:
                ton = arbeit / f"quelle{Path(haupt.name).suffix.lower() or '.wav'}"
                await teile.zugang().herunterladen(haupt.id, ton)
                werte = await teile.ton_jetzt.lesen(ton, RATE)
                ton.unlink(missing_ok=True)
            k = beste(werte, RATE, woerter, s["kennung"])
            if k is None:
                aus.append(Zuordnung(name, ersatz, "ersatz", "keine Stelle von 5 bis 7 Sekunden mit Pausen an beiden Rändern"))
                continue
            try:
                datei = arbeit / f"referenz-{s['kennung']}.wav"
                await teile.ton_jetzt.schreiben(ausschneiden(werte, k.von, k.bis), RATE, datei, REFERENZ)
                stimme = await _anlegen(teile, StimmAngaben(
                    name=f"{name} ({video})"[:80], bereich="fremd", sprache=sprache_quelle, referenztext=k.text,
                    herkunft=Herkunft(art="aufnahme", knoten_id=haupt.id, pfad=haupt.pfad, start=k.von, ende=k.bis),
                    sprecherprofil=profil, abdruck=s.get("abdruck"), notiz=f"Automatisch gewonnen, Wertung {k.wertung:.2f}"),
                    datei, round(k.dauer_s, 2))
            except Exception as f:  # noqa: BLE001 - ein Sprecher ohne Stimme hält die Vertonung nicht auf
                log.warning("Stimme für %s nicht gewonnen", name, exc_info=True)
                aus.append(Zuordnung(name, ersatz, "ersatz", f"Gewinnen gescheitert: {type(f).__name__}: {f}"[:200]))
                continue
            if profil:
                bekannte[profil] = stimme.id
            if s.get("abdruck"):
                abdruecke.append((stimme.id, s["abdruck"]))
            aus.append(Zuordnung(name, StimmWahl(art="klon", knoten_id=stimme.id), "gewonnen"))
    finally:
        shutil.rmtree(arbeit, ignore_errors=True)
    return aus


async def _anlegen(teile, angaben: StimmAngaben, datei: Path, dauer_s: float):
    """Anlegen; ist der Name schon vergeben (dasselbe Video noch einmal, ohne Profil), mit Zahl dahinter."""
    for n in range(1, 50):
        versuch = angaben if n == 1 else angaben.model_copy(update={"name": f"{angaben.name[:74]} ({n})"})
        try:
            return await teile.stimmen.anlegen(versuch, datei, dauer_s)
        except StandVeraltet:
            continue
    raise ValueError(f"Kein freier Name für die Stimme {angaben.name}")
