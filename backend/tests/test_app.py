"""Vertonung gegen eine nachgestellte Kellerwolke: einrichten, anmelden, Verzeichnis nur angemeldet, ohne Leitstelle
keine Stimmen des Katalogs; private Stimmen nur für Menschen und erlaubte Apps."""

import json
from pathlib import Path

import httpx
import pytest

from appkern.anmeldung import Konto

from app.main import app_bauen


def kellerwolke(request: httpx.Request) -> httpx.Response:
    pfad = request.url.path
    if pfad == "/api/v1/ablage/ich":
        return httpx.Response(200, json={"app": "Vertonung", "konto": "probe", "rechte": []})
    if pfad == "/api/v1/auth/login":
        if json.loads(request.content)["passwort"] != "geheim":
            return httpx.Response(401, json={"detail": "Anmeldung fehlgeschlagen"})
        return httpx.Response(200, json={"token": "t1", "benutzer": {"id": "1", "name": "probe", "rolle": "mitglied", "aktiv": True}})
    if pfad == "/api/v1/auth/status":
        ok = request.headers.get("x-kellerwolke-sitzung") == "t1"
        return httpx.Response(200, json={"angemeldet": ok, "benutzer": {"id": "1", "name": "probe", "rolle": "mitglied", "aktiv": True} if ok else None})
    return httpx.Response(404, json={"detail": "nicht da"})


@pytest.fixture
async def app(tmp_path: Path):
    app = app_bauen(tmp_path / "daten", transport=httpx.MockTransport(kellerwolke))
    await app.state.geruest.starten()
    yield app
    await app.state.geruest.stoppen()


async def test_einrichten_anmelden_verzeichnis(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.get("/api/v1/app")).json()["einrichtung_noetig"]
        r = await c.post("/api/v1/einrichtung", json={"kellerwolke_adresse": "http://kw.test", "kellerwolke_schluessel": "kw_app_x"})
        assert r.json()["besitzer"] == "probe"
        h = {"X-Kellerwolke-Sitzung": (await c.post("/api/v1/anmeldung", json={"kennung": "probe", "passwort": "geheim"})).json()["token"]}
        assert (await c.get("/api/v1/plaene")).status_code == 401
        v = (await c.get("/api/v1/plaene", headers=h)).json()
        assert v["gesamt"] == 0 and v["eintraege"] == [] and v["zahlen"] == {}
        r = await c.get("/api/v1/stimmen?bereich=katalog", headers=h)
        assert r.status_code == 503 and "Leitstelle" in r.json()["detail"]


async def test_private_stimmen_nur_erlaubt(app):
    teile = app.state.teile
    assert teile.darf_privat(Konto(id="1", name="chef"))                          # Menschen immer
    assert teile.darf_privat(Konto(id="1", name="chef", app="Rufzeichen"))       # auf der Liste
    assert not teile.darf_privat(Konto(id="1", name="chef", app="Medienpool"))   # nie
    assert not teile.darf_privat(Konto(id="1", name="chef", app="Fremdapp"))
