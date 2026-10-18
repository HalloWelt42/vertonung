"""Referenz gewinnen: nur 5 bis 7 Sekunden eines Sprechers mit Pausen an beiden Rändern, Schnitt in der Pause, Text
genau aus den Wörtern; im Ton gewinnt die Stelle mit leisen Rändern gegen eine mit Musik in den Pausen."""

import numpy as np

from app.referenz import KUERZESTENS_S, LAENGSTENS_S, WortZeit, beste, kandidaten

RATE = 16000


def satz(start: float, anzahl: int, sprecher: str = "s1", wortlaenge: float = 0.3, luecke: float = 0.05) -> list[WortZeit]:
    aus, t = [], start
    for i in range(anzahl):
        aus.append(WortZeit(f"w{start:.0f}_{i}", round(t, 3), round(t + wortlaenge, 3), sprecher, 0.9))
        t += wortlaenge + luecke
    return aus


def test_nur_ganze_stellen_eines_sprechers():
    woerter = satz(1.0, 17) + satz(8.0, 5, "s2") + satz(11.0, 30)   # 17 Wörter = 5,9 s; dann s2; dann 10,5 s am Stück
    liste = kandidaten(woerter, "s1", 30.0)
    assert liste and all(KUERZESTENS_S - 0.31 <= k.dauer_s <= LAENGSTENS_S + 0.31 for k in liste)
    erster = liste[0]
    assert erster.von < 1.0 and erster.text.startswith("w1_0")           # Schnitt in der Pause vor dem ersten Wort
    # mitten im langen Satz (ohne Pause davor) beginnt kein Kandidat
    assert not any(11.0 < k.von + 0.15 < 21.0 and k.von > 11.0 for k in liste)
    assert all("w8" not in k.text for k in liste)                         # der andere Sprecher kommt nie vor


def test_ton_entscheidet_bei_musik_in_den_pausen():
    woerter = satz(1.0, 17) + satz(10.0, 17)
    werte = np.zeros(int(20 * RATE), dtype=np.float32)
    t = np.arange(werte.size) / RATE
    for w in woerter:                                                     # "Sprache": Ton während der Wörter
        a, b = int(w.start * RATE), int(w.ende * RATE)
        werte[a:b] = 0.3 * np.sin(2 * np.pi * 220 * t[a:b])
    werte[int(0.0 * RATE):int(8.0 * RATE)] += 0.08 * np.sin(2 * np.pi * 523 * t[:int(8.0 * RATE)])   # Musik unter Satz 1
    k = beste(werte, RATE, woerter, "s1")
    assert k is not None and k.von > 9.0 and k.gruende["ruhe"] > 0.5


async def test_lange_probe_wird_in_pausen_zugeschnitten(tmp_path):
    import wave

    import pytest

    from appkern.ton import Ton

    from app.ablage.stimmen import ProbeZuKurz, probe_aufbereiten
    rate = 24000
    woerter = satz(0.5, 12) + satz(5.5, 17) + satz(12.5, 8)               # 4,2 s, dann 5,9 s am Stück, dann 2,8 s
    werte = np.zeros(int(16 * rate), dtype=np.float32)
    t = np.arange(werte.size) / rate
    for w in woerter:
        a, b = int(w.start * rate), int(w.ende * rate)
        werte[a:b] = 0.3 * np.sin(2 * np.pi * 200 * t[a:b])
    roh = tmp_path / "probe.wav"
    with wave.open(str(roh), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes((werte * 32767).astype("<i2").tobytes())

    async def gehoert(_):
        return woerter
    dauer, text = await probe_aufbereiten(Ton(), roh, tmp_path / "ref.wav", 5.0, gehoert)
    assert 5.0 <= dauer <= 7.4 and text.startswith("w6_0") and "w1_" not in text and "w12" not in text

    async def ohne_pausen(_):
        return [WortZeit("x", 0.0, 16.0)]
    with pytest.raises(ProbeZuKurz):
        await probe_aufbereiten(Ton(), roh, tmp_path / "ref2.wav", 5.0, ohne_pausen)
