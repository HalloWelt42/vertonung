"""Sprechen als Strom (`POST /api/v1/sprechen/strom`): Satz für Satz als NDJSON mit Lage im Eingabetext, Sprechfassung
und Ton; Fehler mitten im Strom als letzte Zeile; Abbruch des Kunden beendet die Arbeit; Stimmprüfung vor dem Strom.
Gegen eine nachgestellte Kellerwolke und Leitstelle (Prüfton) mit echtem Tondienst."""

import asyncio
import base64
import io
import json
import wave
from pathlib import Path

import httpx
import pytest

from app.main import app_bauen
from app.modell.sprechen import StromEnde, StromFehler, StromSatz
from app.saetze import saetze
from app.teile import KeinRechtAufStimme
from tests.schein import ADRESSE, ScheinLeitstelle, Weiche
from tests.test_app import kellerwolke

EINGABE = "Am 3. September  kostet es 13.439,16 €.\nDas ist z. B. viel!\n\nUm 14:30 Uhr geht es weiter."
SITZUNG = {"X-Kellerwolke-Sitzung": "t1"}


def test_saetze_kennen_ihre_lage():
    text = "  Erster Satz,\r\n  über zwei Zeilen.  Zweiter!\n\n\n Dritter im 3. Stock. Vierter am 5. Mai."
    s = saetze(text)
    assert [x.text for x in s] == ["Erster Satz, über zwei Zeilen.", "Zweiter!", "Dritter im 3. Stock.", "Vierter am 5. Mai."]
    for x in s:
        assert " ".join(text[x.von:x.bis].split()) == x.text
    assert [x.absatz_ende for x in s] == [False, True, False, True]


@pytest.fixture
async def umgebung(tmp_path: Path):
    schein = ScheinLeitstelle()
    app = app_bauen(tmp_path / "daten", transport=Weiche(schein, andere=httpx.MockTransport(kellerwolke)))
    await app.state.geruest.starten()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t", timeout=60) as c:
        await c.post("/api/v1/einrichtung", json={"kellerwolke_adresse": "http://kw.test", "kellerwolke_schluessel": "kw_app_x"})
        await c.post("/api/v1/anmeldung", json={"kennung": "probe", "passwort": "geheim"})
        r = await c.patch("/api/v1/einstellungen", headers=SITZUNG, json={"werte": {
            "leitstelle_adresse": ADRESSE, "leitstelle_schluessel": "ls_probe"}})
        assert r.status_code == 200, r.text
        yield app, c, schein
    await app.state.geruest.stoppen()


def zeilen(antwort: httpx.Response) -> list[dict]:
    assert antwort.status_code == 200, antwort.text
    assert antwort.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(z) for z in antwort.text.splitlines() if z.strip()]


async def test_strom_satz_fuer_satz(umgebung):
    _, c, schein = umgebung
    z = zeilen(await c.post("/api/v1/sprechen/strom", headers=SITZUNG, json={"text": EINGABE}))
    assert [x["art"] for x in z] == ["satz", "satz", "satz", "ende"]
    saetze_ = [StromSatz.model_validate(x) for x in z[:-1]]
    assert [s.nr for s in saetze_] == [0, 1, 2]
    for s in saetze_:
        assert s.text == EINGABE[s.von_zeichen:s.bis_zeichen]
    assert saetze_[0].text == "Am 3. September  kostet es 13.439,16 €."
    assert saetze_[0].gesprochen == "Am dritten September kostet es dreizehntausendvierhundertneununddreißig Euro sechzehn."
    assert saetze_[1].gesprochen == "Das ist zum Beispiel viel!"
    assert saetze_[2].gesprochen == "Um vierzehn Uhr dreißig geht es weiter."
    assert [t for _, t in schein.aufrufe] == [s.gesprochen for s in saetze_]   # gesprochen wird die Sprechfassung
    for s in saetze_:
        with wave.open(io.BytesIO(base64.b64decode(s.ton))) as w:
            assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (24000, 1, 2)
            assert abs(w.getnframes() / 24000 * 1000 - s.dauer_ms) <= 2
    ende = StromEnde.model_validate(z[-1])
    assert ende.saetze == 3 and ende.dauer_ms == sum(s.dauer_ms for s in saetze_)


async def test_strom_ohne_ausschreiben_und_mit_satzzeichen(umgebung):
    _, c, schein = umgebung
    z = zeilen(await c.post("/api/v1/sprechen/strom", headers=SITZUNG,
                            json={"text": "Es kostet 5 €. ...", "ausschreiben": False}))
    assert [x["art"] for x in z] == ["satz", "ende"]          # nur Satzzeichen wird nicht gesprochen
    assert z[0]["gesprochen"] == z[0]["text"] == "Es kostet 5 €."
    assert [t for _, t in schein.aufrufe] == ["Es kostet 5 €."]


async def test_fehler_mitten_im_strom(umgebung):
    _, c, schein = umgebung
    schein.scheitern_bei = "Zweiter"
    z = zeilen(await c.post("/api/v1/sprechen/strom", headers=SITZUNG,
                            json={"text": "Erster Satz. Zweiter Satz. Dritter Satz."}))
    assert [x["art"] for x in z] == ["satz", "fehler"]
    assert StromFehler.model_validate(z[-1]).meldung
    assert not any("Dritter" in t for _, t in schein.aufrufe)  # nach dem Fehler nichts mehr


async def test_stimme_wird_vor_dem_strom_geprueft(umgebung, monkeypatch):
    app, c, schein = umgebung

    async def verboten(wahl, konto):
        raise KeinRechtAufStimme("Private Stimmen sind dieser App nicht erlaubt")
    monkeypatch.setattr(app.state.teile, "stimme_pruefen", verboten)
    r = await c.post("/api/v1/sprechen/strom", headers=SITZUNG, json={"text": "Hallo."})
    assert r.status_code == 403 and schein.aufrufe == []
    assert (await c.post("/api/v1/sprechen/strom", json={"text": "Hallo."})).status_code == 401
    assert (await c.post("/api/v1/sprechen/strom", headers=SITZUNG, json={"text": "x" * 8001})).status_code == 422


async def test_sprechen_schreibt_aus(umgebung):
    _, c, schein = umgebung
    r = await c.post("/api/v1/sprechen", headers=SITZUNG, json={"text": "Nr. 5 kommt um 9 Uhr."})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"
    assert [t for _, t in schein.aufrufe] == ["Nummer fünf kommt um neun Uhr."]


async def test_abbruch_beendet_die_arbeit(umgebung):
    """Der Kunde geht nach dem ersten Satz: kein weiterer Satz geht an den Sprechdienst als der, der gerade läuft."""
    app, _, schein = umgebung
    text = " ".join(f"Satz Nummer {i} mit etwas Text." for i in range(1, 7))
    erster = asyncio.Event()
    gesendet: list[bytes] = []
    koerper = json.dumps({"text": text}).encode()
    eingang = iter([{"type": "http.request", "body": koerper, "more_body": False}])

    async def receive():
        try:
            return next(eingang)
        except StopIteration:
            await erster.wait()
            return {"type": "http.disconnect"}

    async def send(nachricht):
        if nachricht["type"] == "http.response.body" and nachricht.get("body"):
            gesendet.append(nachricht["body"])
            erster.set()

    scope = {"type": "http", "method": "POST", "path": "/api/v1/sprechen/strom", "raw_path": b"/api/v1/sprechen/strom",
             "query_string": b"", "headers": [(b"content-type", b"application/json"), (b"x-kellerwolke-sitzung", b"t1"),
                                              (b"host", b"t")],
             "scheme": "http", "server": ("t", 80), "client": ("127.0.0.1", 1), "http_version": "1.1", "root_path": ""}
    await asyncio.wait_for(app(scope, receive, send), 60)
    arten = [json.loads(z)["art"] for z in b"".join(gesendet).splitlines() if z.strip()]
    assert arten[0] == "satz" and "ende" not in arten
    await asyncio.sleep(0.5)                                   # nichts läuft im Hintergrund weiter
    assert 1 <= len(schein.aufrufe) <= 2, schein.aufrufe
    assert not list((app.state.teile.arbeit).glob("sprechen-*"))   # Arbeitsordner weg
