"""Originalstimmen für eine Vertonung (Strecken 2 und 3 der Optimierung): je Sprecher des Transkripts eine Klonstimme.

Eine schon gewonnene Stimme desselben Sprechers wird wiederverwendet (Nutzer 18.10.2026: "ist die Stimme
rausgeschnitten, muss sie nicht erneut rausgeschnitten werden"). Derselbe Sprecher ist, wen die Transkription demselben
Sprecherprofil zuordnet (bestätigt oder als sicherer Vorschlag), sonst wessen Stimmabdruck dem gemerkten einer Stimme
mindestens so ähnlich ist wie die Schwelle "sicher" der Transkription (gleiches Verfahren, gleiche Skala). Sonst wird
die beste Stelle im ganzen Video ausgeschnitten (siehe referenz.py) und als fremde Stimme angelegt, mit Referenztext,
Profil und Abdruck. Wer keine brauchbare
Stelle hat, spricht mit der festen Stimme. Gerechnet wird im Tondienst: einmal der Pegelverlauf der Aufnahme (für die
Wahl der Stelle), dann alle Ausschnitte in einem Aufruf."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from appkern.kellerwolke import StandVeraltet
from appkern.ton import Aufbereiten, Ausgabe, Messen, Tonarbeit, Tonformat

from .modell.plan import StimmWahl
from .modell.stimme import Herkunft, StimmAngaben
from .referenz import FENSTER_S, Kandidat, WortZeit, beste

log = logging.getLogger("vertonung")
RATE = 24000
REFERENZ = Tonformat(rate=RATE, kanaele=1, kodierung="pcm_s16le")
AEHNLICH = 0.8               # ein Vorschlag der Transkription gilt ab dieser Ähnlichkeit als derselbe Sprecher
GLEICH = 0.70                # Abdrücke ab dieser Kosinus-Ähnlichkeit: derselbe Sprecher (Schwelle "sicher" der Transkription)
BLENDE_MS = 10               # weiche Ränder; der Schnitt liegt ohnehin in der Pause
SPITZE = 0.98                # eine übersteuerte Stelle wird leiser, nie abgeschnitten


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


async def zuordnen(teile, transkript: dict, haupt, video: str, sprache_quelle: str, ersatz: StimmWahl, arbeit: Path,
                   ton: Tonarbeit | None = None) -> list[Zuordnung]:
    """Je Sprecher des Transkripts eine Stimme; der Ton der Aufnahme wird nur geholt, wenn eine Stimme zu gewinnen ist.
    `ton`: die Tonarbeit des Auftrags (geduldig), sonst die der App."""
    ton = ton or teile.ton
    bekannte: dict[str, str] = {}
    abdruecke: list[tuple[str, list[float]]] = []
    for bereich in ("fremd", "privat"):
        for s in await teile.stimmen.alle(bereich):
            if s.angaben and s.angaben.sprecherprofil:
                bekannte.setdefault(s.angaben.sprecherprofil, s.id)
            if s.angaben and s.angaben.abdruck:
                abdruecke.append((s.id, s.angaben.abdruck))
    woerter = woerter_aus(transkript)
    arbeit.mkdir(parents=True, exist_ok=True)
    quelle: Path | None = None
    pegel = None
    aus: dict[str, Zuordnung] = {}
    zu_gewinnen: list[tuple[dict, str, str | None, Kandidat]] = []
    sprecher = transkript.get("sprecher") or []
    try:
        for s in sprecher:
            name = s.get("name") or s["kennung"]
            profil = profil_des_sprechers(s)
            if profil and profil in bekannte:
                aus[name] = Zuordnung(name, StimmWahl(art="klon", knoten_id=bekannte[profil]), "wiederverwendet")
                continue
            if s.get("abdruck") and abdruecke:
                beste_id, wert = max(((i, aehnlichkeit(s["abdruck"], a)) for i, a in abdruecke), key=lambda x: x[1])
                if wert >= GLEICH:
                    aus[name] = Zuordnung(name, StimmWahl(art="klon", knoten_id=beste_id), "wiedererkannt", f"Ähnlichkeit {wert:.2f}")
                    continue
            if pegel is None:
                quelle = arbeit / f"quelle{Path(haupt.name).suffix.lower() or '.wav'}"
                await teile.zugang().herunterladen(haupt.id, quelle)
                pegel = (await ton.aufbereiten(quelle, Aufbereiten(messen=Messen(pegel_ms=int(FENSTER_S * 1000))), [],
                                               titel=f"{video}, Pegel der Sprecher")).messwerte.pegel
            k = beste(pegel, woerter, s["kennung"])
            if k is None:
                aus[name] = Zuordnung(name, ersatz, "ersatz", "keine Stelle von 5 bis 7 Sekunden mit Pausen an beiden Rändern")
                continue
            zu_gewinnen.append((s, name, profil, k))
        if zu_gewinnen:
            await _gewinnen(teile, ton, zu_gewinnen, quelle, haupt, video, sprache_quelle, ersatz, arbeit, aus, bekannte, abdruecke)
    finally:
        shutil.rmtree(arbeit, ignore_errors=True)
    return [aus[s.get("name") or s["kennung"]] for s in sprecher]


async def _gewinnen(teile, ton: Tonarbeit, zu_gewinnen, quelle: Path, haupt, video: str, sprache_quelle: str, ersatz: StimmWahl,
                    arbeit: Path, aus: dict[str, Zuordnung], bekannte: dict[str, str],
                    abdruecke: list[tuple[str, list[float]]]) -> None:
    """Alle Ausschnitte in einem Aufruf des Tondienstes, dann je Sprecher eine fremde Stimme anlegen."""
    dateien = [arbeit / f"referenz-{s['kennung']}.wav" for s, *_ in zu_gewinnen]
    try:
        erg = await ton.aufbereiten(quelle, Aufbereiten(ausgaben=[
            Ausgabe(format=REFERENZ, beginn_s=k.von, ende_s=k.bis, spitze=SPITZE, blende_ms=BLENDE_MS) for *_, k in zu_gewinnen]),
            dateien, titel=f"{video}, Stimmen ausschneiden")
    except Exception as f:  # noqa: BLE001 - ohne Ausschnitt spricht die Ersatzstimme; die Vertonung geht weiter
        log.warning("Ausschnitte für %s nicht gewonnen", video, exc_info=True)
        for _, name, _, _ in zu_gewinnen:
            aus[name] = Zuordnung(name, ersatz, "ersatz", f"Ausschneiden gescheitert: {type(f).__name__}: {f}"[:200])
        return
    for (s, name, profil, k), datei, d in zip(zu_gewinnen, dateien, erg.ausgaben, strict=True):
        try:
            stimme = await _anlegen(teile, StimmAngaben(
                name=f"{name} ({video})"[:80], bereich="fremd", sprache=sprache_quelle, referenztext=k.text,
                herkunft=Herkunft(art="aufnahme", knoten_id=haupt.id, pfad=haupt.pfad, start=k.von, ende=k.bis),
                sprecherprofil=profil, abdruck=s.get("abdruck"), notiz=f"Automatisch gewonnen, Wertung {k.wertung:.2f}"),
                datei, round(d.dauer_s, 2))
        except Exception as f:  # noqa: BLE001 - ein Sprecher ohne Stimme hält die Vertonung nicht auf
            log.warning("Stimme für %s nicht gewonnen", name, exc_info=True)
            aus[name] = Zuordnung(name, ersatz, "ersatz", f"Gewinnen gescheitert: {type(f).__name__}: {f}"[:200])
            continue
        if profil:
            bekannte[profil] = stimme.id
        if s.get("abdruck"):
            abdruecke.append((stimme.id, s["abdruck"]))
        aus[name] = Zuordnung(name, StimmWahl(art="klon", knoten_id=stimme.id), "gewonnen")


async def _anlegen(teile, angaben: StimmAngaben, datei: Path, dauer_s: float):
    """Anlegen; ist der Name schon vergeben (dasselbe Video noch einmal, ohne Profil), mit Zahl dahinter."""
    for n in range(1, 50):
        versuch = angaben if n == 1 else angaben.model_copy(update={"name": f"{angaben.name[:74]} ({n})"})
        try:
            return await teile.stimmen.anlegen(versuch, datei, dauer_s)
        except StandVeraltet:
            continue
    raise ValueError(f"Kein freier Name für die Stimme {angaben.name}")
