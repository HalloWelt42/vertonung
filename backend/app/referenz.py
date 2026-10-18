"""Referenz für eine Klonstimme aus einer Aufnahme gewinnen (Nutzer 18.10.2026): 5 bis 7 Sekunden eines Sprechers,
geschnitten nur in Sprechpausen (ein harter Schnitt im Wort knackt und verdirbt das Klonen), durchgehend gesprochen, kein
anderer Sprecher dazwischen; gesucht wird die beste Stelle im ganzen Video. Der Referenztext sind genau die Wörter des
Ausschnitts, so wie das Modell es verlangt.

Zwei Stufen: aus den Wortzeiten des Transkripts die Kandidaten samt einer ersten Wertung (Länge nahe sechs Sekunden,
Pausen an den Rändern, Hörsicherheit, natürliches Tempo); für die besten dann der Ton selbst (gleichmäßiger Pegel, leise
Ränder ohne Musik oder Rauschen, keine Übersteuerung)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

KUERZESTENS_S, LAENGSTENS_S, ZIEL_S = 5.0, 7.0, 6.0
PAUSE_RAND_S = 0.25          # so viel Stille muss vor dem ersten und nach dem letzten Wort liegen
PAUSE_INNEN_S = 0.7          # längere Pausen im Ausschnitt: dann spricht er nicht durchgehend
SCHNITT_RAND_S = 0.15        # so viel Stille wird vorn und hinten mitgenommen (der Schnitt liegt in der Pause)
TEMPO_WOERTER_S = (1.8, 4.2)  # natürliches Sprechtempo in Wörtern je Sekunde
FENSTER_S = 0.05             # Rahmen für Pegelmessungen


@dataclass(frozen=True)
class WortZeit:
    wort: str
    start: float
    ende: float
    sprecher: str | None = None
    sicherheit: float | None = None


@dataclass(frozen=True)
class Kandidat:
    von: float               # Schnitt vorn (in der Pause vor dem ersten Wort)
    bis: float               # Schnitt hinten (in der Pause nach dem letzten Wort)
    text: str                # genau die Wörter des Ausschnitts
    wertung: float           # 0 bis 1, höher ist besser
    gruende: dict[str, float] = field(default_factory=dict)

    @property
    def dauer_s(self) -> float:
        return self.bis - self.von


def _anteil(wert: float, gut: float) -> float:
    return max(0.0, min(wert / gut, 1.0))


def kandidaten(woerter: list[WortZeit], sprecher: str | None, aufnahme_s: float) -> list[Kandidat]:
    """Alle Ausschnitte von 5 bis 7 Sekunden eines Sprechers mit Pausen an beiden Rändern, beste zuerst. `sprecher` None:
    jeder (Aufnahmen mit nur einer Stimme)."""
    w = sorted(woerter, key=lambda x: x.start)
    aus: list[Kandidat] = []
    for i, erstes in enumerate(w):
        if sprecher is not None and erstes.sprecher != sprecher:
            continue
        davor = erstes.start - (w[i - 1].ende if i else 0.0)
        if davor < PAUSE_RAND_S:
            continue
        for j in range(i, len(w)):
            letztes = w[j]
            if j > i and (letztes.sprecher != erstes.sprecher or letztes.start - w[j - 1].ende > PAUSE_INNEN_S):
                break
            dauer = letztes.ende - erstes.start
            if dauer > LAENGSTENS_S:
                break
            danach = (w[j + 1].start if j + 1 < len(w) else aufnahme_s) - letztes.ende
            if dauer < KUERZESTENS_S or danach < PAUSE_RAND_S:
                continue
            teil = w[i:j + 1]
            sicher = [x.sicherheit for x in teil if x.sicherheit is not None]
            tempo = len(teil) / max(dauer, 1e-3)
            gruende = {
                "laenge": 1.0 - min(abs(dauer - ZIEL_S) / (LAENGSTENS_S - ZIEL_S), 1.0),
                "pausen": _anteil(min(davor, danach), 0.6),
                "sicherheit": (sum(sicher) / len(sicher)) if sicher else 0.8,
                "tempo": 1.0 if TEMPO_WOERTER_S[0] <= tempo <= TEMPO_WOERTER_S[1] else 0.4,
            }
            wertung = 0.3 * gruende["laenge"] + 0.3 * gruende["pausen"] + 0.25 * gruende["sicherheit"] + 0.15 * gruende["tempo"]
            von = max(0.0, erstes.start - min(SCHNITT_RAND_S, davor / 2))
            bis = min(aufnahme_s, letztes.ende + min(SCHNITT_RAND_S, danach / 2))
            aus.append(Kandidat(von=round(von, 3), bis=round(bis, 3), text=" ".join(x.wort for x in teil).strip(),
                                wertung=round(wertung, 4), gruende=gruende))
    return sorted(aus, key=lambda k: k.wertung, reverse=True)


def _pegel(werte: np.ndarray, rate: int) -> np.ndarray:
    n = max(1, int(FENSTER_S * rate))
    rahmen = werte[: len(werte) // n * n].reshape(-1, n)
    return np.sqrt(np.mean(rahmen.astype(np.float64) ** 2, axis=1) + 1e-12)


def ton_wertung(werte: np.ndarray, rate: int, k: Kandidat, woerter: list[WortZeit]) -> dict[str, float]:
    """Wertung aus dem Ton eines Kandidaten (`werte`: die ganze Aufnahme mono): gleichmäßiger Pegel im Gesprochenen,
    leise Ränder gegen das Gesprochene (Abstand in dB), keine Übersteuerung."""
    teil = werte[int(k.von * rate): int(k.bis * rate)]
    if teil.size < rate:
        return {"gleichmaessig": 0.0, "ruhe": 0.0, "sauber": 0.0}
    erstes = next(w for w in woerter if w.start >= k.von - 1e-3)
    letztes = [w for w in woerter if w.ende <= k.bis + 1e-3][-1]
    rand = np.concatenate([teil[: max(1, int((erstes.start - k.von) * rate))], teil[int((letztes.ende - k.von) * rate):]])
    sprache = _pegel(teil[int((erstes.start - k.von) * rate): int((letztes.ende - k.von) * rate)], rate)
    laut = sprache[sprache >= np.percentile(sprache, 30)] if sprache.size > 3 else sprache
    gleich = 1.0 - min(float(np.std(20 * np.log10(laut))) / 12.0, 1.0) if laut.size else 0.0
    abstand_db = 20 * np.log10(float(np.median(laut)) / float(np.mean(_pegel(rand, rate)) if rand.size else 1e-6)) if laut.size else 0.0
    return {"gleichmaessig": round(gleich, 3), "ruhe": round(_anteil(abstand_db, 30.0), 3),
            "sauber": 0.0 if float(np.max(np.abs(teil))) >= 0.99 else 1.0}


def beste(werte: np.ndarray, rate: int, woerter: list[WortZeit], sprecher: str | None, *, pruefen: int = 12) -> Kandidat | None:
    """Der beste Ausschnitt: die `pruefen` besten nach den Wortzeiten, dann nach dem Ton gewertet."""
    aufnahme_s = werte.size / rate
    liste = kandidaten(woerter, sprecher, aufnahme_s)[:pruefen]
    if not liste:
        return None
    gewertet = []
    for k in liste:
        t = ton_wertung(werte, rate, k, woerter)
        gesamt = 0.5 * k.wertung + 0.2 * t["gleichmaessig"] + 0.2 * t["ruhe"] + 0.1 * t["sauber"]
        gewertet.append(Kandidat(k.von, k.bis, k.text, round(gesamt, 4), {**k.gruende, **t}))
    return max(gewertet, key=lambda k: k.wertung)
