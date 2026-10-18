"""Verbund: Vertonung gegen die echte Kellerwolke (Entwicklungsinstanz) mit eigenem Testzugang (`backend/.env.test`,
Lehre 20) und nachgestellter Leitstelle (Prüfton). Geht nur Wege, die auch die Oberfläche geht: Stimme hochladen,
Vorlesen planen und vertonen (Ergebnis als MP3 neben dem Text), einen Satz ändern und nur ihn neu sprechen, Dialog mit
Klonstimme. Am Ende alles in den Papierkorb (Dateien vor Ordnern) und Aktionen zurückziehen."""

import asyncio
import io
from pathlib import Path

import httpx
import pytest

from appkern.testen import aktionen_zurueckziehen, aufraeumen, hat_kellerwolke, werte

from app.main import app_bauen
from tests.schein import ADRESSE, ScheinLeitstelle, Weiche, ton

W = werte(Path(__file__).resolve().parents[1] / ".env.test")
pytestmark = pytest.mark.skipif(not hat_kellerwolke(W), reason="kein eigener Testzugang eingerichtet (backend/.env.test)")


async def fertig(c: httpx.AsyncClient, h: dict, auftrag_id: str) -> dict:
    for _ in range(600):
        a = (await c.get(f"/api/v1/auftraege/{auftrag_id}", headers=h)).json()
        if a["zustand"] in ("fertig", "fehler", "abgebrochen"):
            assert a["zustand"] == "fertig", a.get("fehler")
            return a
        await asyncio.sleep(0.1)
    pytest.fail("Auftrag wurde nicht fertig")


async def test_ganzer_weg(tmp_path: Path):
    schein = ScheinLeitstelle()
    weiche = Weiche(schein)
    app = app_bauen(tmp_path / "daten", transport=weiche)
    g = app.state.geruest
    await g.starten()
    angelegt: list = []
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t", timeout=60) as c:
            r = await c.post("/api/v1/einrichtung", json={"kellerwolke_adresse": W["KELLERWOLKE_ADRESSE"],
                                                          "kellerwolke_schluessel": W["KELLERWOLKE_SCHLUESSEL"]})
            assert r.status_code == 200, r.text
            r = await c.post("/api/v1/anmeldung", json={"kennung": W["KELLERWOLKE_KENNUNG"], "passwort": W["KELLERWOLKE_PASSWORT"]})
            h = {"X-Kellerwolke-Sitzung": r.json()["token"]}
            try:
                assert (await c.post("/api/v1/adresse", headers=h, json={"adresse": "http://t"})).status_code == 200
                r = await c.patch("/api/v1/einstellungen", headers=h, json={"werte": {
                    "leitstelle_adresse": ADRESSE, "leitstelle_schluessel": "ls_probe"}})
                assert r.status_code == 200, r.text
                katalog = (await c.get("/api/v1/stimmen?bereich=katalog", headers=h)).json()
                assert [s["name"] for s in katalog] == ["serena", "aiden"]

                # Stimme aus einer hochgeladenen Probe (8 s)
                r = await c.post("/api/v1/stimmen?name=Probestimme Test&bereich=fremd&referenztext=Hallo", headers=h,
                                 content=ton(8.0, 180.0))
                assert r.status_code == 201, r.text
                stimme = r.json()
                angelegt.append(stimme["id"])
                assert stimme["bereich"] == "fremd" and 8.0 <= stimme["dauer_s"] <= 8.2
                assert stimme["id"] in [s["id"] for s in (await c.get("/api/v1/stimmen?bereich=fremd", headers=h)).json()]
                r = await c.post("/api/v1/stimmen?name=Zu kurz&bereich=fremd", headers=h, content=ton(2.0))
                assert r.status_code == 422

                # Vorlesen: Text anlegen, Plan, vertonen
                r = await c.post("/api/v1/plaene", headers=h, json={
                    "art": "vorlesen", "name": "Verbundtest Brief", "format": "mp3",
                    "text": "Erster Satz des Briefs. Zweiter Satz, etwas länger als der erste. Gruß."})
                assert r.status_code == 201, r.text
                p = r.json()
                angelegt.append(p["haupt_id"])
                assert [s["stand"] for s in p["staende"]] == ["offen"] * 3
                a = (await c.post(f"/api/v1/plaene/{p['id']}/vertonen", headers=h)).json()
                erg = (await fertig(c, h, a["id"]))["ergebnis"]
                assert erg["pfad"].endswith("Verbundtest Brief.sprache.mp3") and erg["dauer_s"] > 3
                p = (await c.get(f"/api/v1/plaene/{p['id']}", headers=h)).json()
                assert [s["stand"] for s in p["staende"]] == ["gesprochen"] * 3

                # einen Satz ändern: nur er wird neu gesprochen
                schein.aufrufe.clear()
                plan = p["plan"]
                plan["abschnitte"][2]["text"] = "Viele Grüße."
                r = await c.patch(f"/api/v1/plaene/{p['id']}", headers=h, json={"plan": plan, "stand": p["stand"]})
                assert r.status_code == 200 and [s["stand"] for s in r.json()["staende"]] == ["gesprochen", "gesprochen", "geaendert"]
                veraltet = await c.patch(f"/api/v1/plaene/{p['id']}", headers=h, json={"plan": plan, "stand": p["stand"]})
                assert veraltet.status_code == 409
                a = (await c.post(f"/api/v1/plaene/{p['id']}/vertonen", headers=h)).json()
                await fertig(c, h, a["id"])
                assert schein.aufrufe == [("serena", "Viele Grüße.")]

                # Dialog mit Klonstimme für eine Rolle
                r = await c.post("/api/v1/plaene", headers=h, json={
                    "art": "dialog", "name": "Verbundtest Szene", "text": "Mara: Hörst du das?\nJonas: Nur der Wind.",
                    "stimmen": {"Jonas": {"art": "klon", "knoten_id": stimme["id"]}}})
                assert r.status_code == 201, r.text
                d = r.json()
                angelegt.append(d["haupt_id"])
                schein.aufrufe.clear()
                a = (await c.post(f"/api/v1/plaene/{d['id']}/vertonen", headers=h)).json()
                await fertig(c, h, a["id"])
                assert schein.aufrufe == [("serena", "Hörst du das?"), ("klon", "Nur der Wind.")]
                v = (await c.get("/api/v1/plaene", headers=h)).json()
                assert {"Verbundtest Brief", "Verbundtest Szene"} <= {e["name"] for e in v["eintraege"]}
                ton_ergebnis = await c.get(f"/api/v1/inhalt/plaene/{d['id']}/ergebnis", headers=h)
                assert ton_ergebnis.status_code == 200 and ton_ergebnis.headers["content-type"].startswith("audio/mpeg")
            finally:
                await c.post("/api/v1/anmeldung/abmelden", headers=h)
    finally:
        if angelegt and g.kellerwolke is not None:
            assert await aufraeumen(g.kellerwolke, angelegt) == []
        await g.stoppen()
        await weiche.aclose()
        await aktionen_zurueckziehen(W["KELLERWOLKE_ADRESSE"], W["KELLERWOLKE_SCHLUESSEL"])
