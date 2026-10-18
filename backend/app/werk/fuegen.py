"""Fügen im Arbeitsformat (Gleitkomma, eine Rate): Stücke eines Satzes mit Gleichleistungsblende verbinden, Ränder
glätten und Stille kürzen, Abschnitte hintereinander mit Pausen oder an ihre Zeiten legen."""

from __future__ import annotations

import numpy as np

BLENDE_MS = 30
RAND_MS = 5
STILLE_DB = -45.0
STILLE_RAND_MS = 40


def blenden(teile: list[np.ndarray], rate: int, blende_ms: int = BLENDE_MS) -> np.ndarray:
    """Hintereinander mit Gleichleistungsblende (cos und sin): die Lautheit bleibt über die Naht gleich."""
    teile = [np.asarray(t, dtype=np.float32) for t in teile if np.asarray(t).size]
    if not teile:
        return np.zeros(0, dtype=np.float32)
    aus = teile[0]
    for t in teile[1:]:
        n = min(int(rate * blende_ms / 1000), aus.size, t.size)
        if n == 0:
            aus = np.concatenate([aus, t])
            continue
        x = np.linspace(0.0, np.pi / 2, n, dtype=np.float32)
        naht = aus[-n:] * np.cos(x) + t[:n] * np.sin(x)
        aus = np.concatenate([aus[:-n], naht, t[n:]])
    return aus.astype(np.float32)


def stille_kuerzen(werte: np.ndarray, rate: int, schwelle_db: float = STILLE_DB, rand_ms: int = STILLE_RAND_MS) -> np.ndarray:
    """Stille am Anfang und Ende weg (bis auf einen kleinen Rand), damit Pausen und Zeitlage vom Plan kommen."""
    if werte.size == 0:
        return werte
    schwelle = 10 ** (schwelle_db / 20)
    laut = np.flatnonzero(np.abs(werte) > schwelle)
    if laut.size == 0:
        return werte[:0]
    rand = int(rate * rand_ms / 1000)
    return werte[max(0, laut[0] - rand):min(werte.size, laut[-1] + rand + 1)]


def raender(werte: np.ndarray, rate: int, rand_ms: int = RAND_MS) -> np.ndarray:
    """Kurz ein- und ausblenden, damit kein Knacks entsteht."""
    werte = np.array(werte, dtype=np.float32)
    n = min(int(rate * rand_ms / 1000), werte.size // 2)
    if n:
        rampe = np.linspace(0.0, 1.0, n, dtype=np.float32)
        werte[:n] *= rampe
        werte[-n:] *= rampe[::-1]
    return werte


def folge(abschnitte: list[tuple[np.ndarray, float]], rate: int) -> np.ndarray:
    """Vorlesen und Dialog: Abschnitte hintereinander, nach jedem seine Pause (Sekunden)."""
    teile: list[np.ndarray] = []
    for werte, pause_s in abschnitte:
        teile.append(raender(werte, rate))
        teile.append(np.zeros(int(round(rate * pause_s)), dtype=np.float32))
    if teile:
        teile.pop()                                # nach dem letzten keine Pause
    return np.concatenate(teile).astype(np.float32) if teile else np.zeros(0, dtype=np.float32)


def legen(stuecke: list[tuple[np.ndarray, float]], rate: int, mindestens_s: float = 0.0) -> np.ndarray:
    """Zeitgenau: jedes Stück an seinen Beginn (Sekunden); mindestens `mindestens_s` lang (so lang wie die Quelle)."""
    ende = max([b + w.size / rate for w, b in stuecke] + [mindestens_s])
    aus = np.zeros(int(np.ceil(ende * rate)), dtype=np.float32)
    for werte, beginn in stuecke:
        a = int(round(beginn * rate))
        w = raender(werte, rate)
        aus[a:a + w.size] += w[:max(0, aus.size - a)]
    return aus


def begrenzen(werte: np.ndarray, spitze: float = 0.98) -> np.ndarray:
    """Liegt die Spitze darüber (etwa eine übersteuerte Quelle nach dem Umrechnen), wird das Ganze leiser; nie
    abgeschnitten, nie verzerrt."""
    hoch = float(np.max(np.abs(werte))) if werte.size else 0.0
    return werte * (spitze / hoch) if hoch > spitze else werte
