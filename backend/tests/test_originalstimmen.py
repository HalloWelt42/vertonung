"""Originalstimmen: ein bekannter Sprecher (Profil mit Stimme) wird wiederverwendet, ein neuer bekommt eine Stimme aus
seiner besten Stelle (Referenztext genau die Wörter, Profil vermerkt), wer nur kurz spricht, die feste Stimme."""

import wave
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import numpy as np

from appkern.ton import TonHier

from app.modell.plan import StimmWahl
from app.originalstimmen import RATE, zuordnen

ZEIT = StimmWahl(art="klon", knoten_id=uuid4())


def woerter(start: float, anzahl: int, praefix: str) -> list[dict]:
    return [{"wort": f"{praefix}{i}", "start": round(start + i * 0.35, 3), "ende": round(start + i * 0.35 + 0.3, 3),
             "sicherheit": 0.9} for i in range(anzahl)]


class Stimmen:
    def __init__(self, bekannt: dict[str, str]):
        self.bekannt, self.angelegt = bekannt, []

    async def alle(self, bereich):
        if bereich != "fremd":
            return []
        return [SimpleNamespace(id=i, angaben=SimpleNamespace(sprecherprofil=p, abdruck=a)) for p, (i, a) in self.bekannt.items()]

    async def anlegen(self, angaben, datei, dauer_s):
        with wave.open(str(datei)) as w:
            assert (w.getframerate(), w.getnchannels()) == (24000, 1)
            spitze = float(np.max(np.abs(np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")))) / 32768
        self.angelegt.append((angaben, dauer_s))
        self.spitzen = [*getattr(self, "spitzen", []), spitze]
        return SimpleNamespace(id=str(uuid4()))


def teile_mit(tmp_path: Path, stimmen: Stimmen, pegel: float = 0.3):
    werte = np.zeros(int(30 * RATE), dtype=np.float32)
    t = np.arange(werte.size) / RATE
    werte += pegel * np.sin(2 * np.pi * 180 * t) * ((t % 0.35) < 0.3)   # "Sprache" überall, Pausen kommen aus den Wortzeiten
    quelle = tmp_path / "video.wav"
    # Gleitkomma, damit auch eine übersteuerte Quelle (über 1,0) genau so ankommt
    roh = tmp_path / "video.f32"
    roh.write_bytes(werte.astype("<f4").tobytes())
    import subprocess
    from appkern.ton import programm
    subprocess.run([programm("ffmpeg"), "-nostdin", "-loglevel", "error", "-y", "-f", "f32le", "-ar", str(RATE), "-ac", "1",
                    "-i", str(roh), "-c:a", "pcm_f32le", str(quelle)], check=True)

    class Zugang:
        async def herunterladen(self, knoten_id, ziel):
            Path(ziel).write_bytes(quelle.read_bytes())
    return SimpleNamespace(stimmen=stimmen, zugang=lambda: Zugang(), ton=TonHier())


async def test_zuordnen(tmp_path):
    profil_a, profil_b = str(uuid4()), str(uuid4())
    transkript = {
        "sprecher": [{"kennung": "s1", "name": "Anna", "profil_id": profil_a},
                     {"kennung": "s2", "name": "Bernd", "vorschlag_id": profil_b, "vorschlag_aehnlichkeit": 0.86},
                     {"kennung": "s3", "name": "Gast"},
                     {"kennung": "s4", "name": "Carla", "abdruck": [0.9, 0.1, 0.25]}],
        "segmente": [{"sprecher": "s1", "woerter": woerter(1.0, 10, "a")},
                     {"sprecher": "s2", "woerter": woerter(6.0, 17, "b")},
                     {"sprecher": "s3", "woerter": woerter(14.0, 4, "c")}]}
    anna, carla = str(uuid4()), str(uuid4())
    stimmen = Stimmen({profil_a: (anna, None), None: (carla, [1.0, 0.0, 0.2])})
    haupt = SimpleNamespace(id=uuid4(), name="Interview.wav", pfad="Apps/Vertonung/Dienst/X/Interview.wav")
    z = {x.sprecher: x for x in await zuordnen(teile_mit(tmp_path, stimmen), transkript, haupt, "Interview", "en", ZEIT,
                                               tmp_path / "arbeit")}
    assert (z["Anna"].weg, str(z["Anna"].wahl.knoten_id)) == ("wiederverwendet", anna)
    assert z["Bernd"].weg == "gewonnen" and z["Gast"].weg == "ersatz" and z["Gast"].wahl == ZEIT
    assert (z["Carla"].weg, str(z["Carla"].wahl.knoten_id)) == ("wiedererkannt", carla)    # ohne Profil, am Abdruck
    angaben, dauer = stimmen.angelegt[0]
    assert angaben.name == "Bernd (Interview)" and angaben.sprecherprofil == profil_b and angaben.bereich == "fremd"
    assert angaben.referenztext.startswith("b0 b1") and 5.0 <= dauer <= 7.4 and angaben.herkunft.art == "aufnahme"
    assert not (tmp_path / "arbeit").exists()



async def test_uebersteuerte_stelle_wird_leiser_nie_abgeschnitten(tmp_path):
    """Eine übersteuerte Quelle (Werte über 1,0): die gewonnene Referenz wird als Ganzes leiser, nie abgeschnitten."""
    transkript = {"sprecher": [{"kennung": "s1", "name": "Laut"}],
                  "segmente": [{"sprecher": "s1", "woerter": woerter(2.0, 17, "l")}]}
    stimmen = Stimmen({})
    haupt = SimpleNamespace(id=uuid4(), name="Laut.wav", pfad="Apps/Vertonung/Dienst/X/Laut.wav")
    z = await zuordnen(teile_mit(tmp_path, stimmen, pegel=1.3), transkript, haupt, "Laut", "en", ZEIT, tmp_path / "arbeit")
    assert z[0].weg == "gewonnen" and 0.9 <= stimmen.spitzen[0] <= 0.98 + 1e-3
