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
    if pfad == "/api/v1/ablage/apps":
        assert request.headers["authorization"] == "Bearer kw_app_x"
        return httpx.Response(200, json=[{"app": a, "aktiv": True} for a in ["Vorlesen", "Medienpool", "Rufzeichen"]])
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


async def test_private_stimmen_nur_erlaubt(app, monkeypatch):
    teile = app.state.teile
    zeit, freund = "7ce9880d-9f61-4220-ae2b-648076764afd", "06138119-9a96-4da9-b79c-d877cb900928"
    medienpool = Konto(id="1", name="chef", app="Medienpool")
    monkeypatch.setattr(teile.einstellungen, "private_stimmen_fuer", [*teile.einstellungen.private_stimmen_fuer, f"medienpool:{zeit}"])
    assert teile.darf_privat(Konto(id="1", name="chef"), freund)                  # Menschen immer
    assert teile.darf_privat(Konto(id="1", name="chef", app="Rufzeichen"), freund)  # als Ganzes auf der Liste
    assert teile.darf_privat(medienpool, zeit.upper())                            # nur die einzeln eingetragene
    assert not teile.darf_privat(medienpool, freund)                              # Freundesstimmen nie
    assert teile.private_freigabe(medienpool) == frozenset({zeit})
    assert not teile.darf_privat(Konto(id="1", name="chef", app="Fremdapp"), zeit)
    assert not teile.private_freigabe(Konto(id="1", name="chef", app="Fremdapp"))
    # Ein pauschaler Eintrag gibt dem Medienpool trotzdem nicht alle
    monkeypatch.setattr(teile.einstellungen, "private_stimmen_fuer", [*teile.einstellungen.private_stimmen_fuer, "medienpool"])
    assert not teile.darf_privat(medienpool, freund) and teile.darf_privat(medienpool, zeit)


def test_medienpool_nie_alle():
    from pydantic import ValidationError

    from app.einstellungen import AppEinstellungen

    with pytest.raises(ValidationError):
        AppEinstellungen(private_stimmen_fuer=["fundus", "Medienpool"])
    assert AppEinstellungen(private_stimmen_fuer=["medienpool:abc"]).private_stimmen_fuer == ["medienpool:abc"]
    assert AppEinstellungen().stimme_vorgabe == "" and AppEinstellungen().ersatzstimme == ""   # keine feste Stimme


async def test_auswahl_statt_freitext(app, monkeypatch):
    """Stimme ab Werk und Ersatzstimme aus dem Katalog des Sprechdienstes, die Freigabe privater Stimmen als Paare aus
    den Apps der Kellerwolke und den privaten Stimmen mit Namen."""
    from app.modell.stimme import Stimme

    teile = app.state.teile
    zeit = "7CE9880D-9F61-4220-AE2B-648076764AFD"

    async def privat(bereich):
        assert bereich == "privat"
        return [Stimme(id=zeit, name="Zeit Stimme", bereich="privat")]

    async def katalog():
        return ["serena", "aiden"]

    monkeypatch.setattr(teile.stimmen, "alle", privat)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        await c.post("/api/v1/einrichtung", json={"kellerwolke_adresse": "http://kw.test", "kellerwolke_schluessel": "kw_app_x"})
        h = {"X-Kellerwolke-Sitzung": (await c.post("/api/v1/anmeldung", json={"kennung": "probe", "passwort": "geheim"})).json()["token"]}
        felder = {f["name"]: f for f in (await c.get("/api/v1/einstellungen", headers=h)).json()}
        assert all(felder[n]["angebot"] for n in ("stimme_vorgabe", "ersatzstimme", "private_stimmen_fuer"))
        assert felder["private_stimmen_fuer"]["paar"]["erstes"] == "App" and felder["stimme_vorgabe"]["wert"] == ""

        a = (await c.get("/api/v1/einstellungen/angebot/stimme_vorgabe", headers=h)).json()
        assert [o["wert"] for o in a["optionen"]] == [""] and "Leitstelle" in a["stand"] and not a["eigener_wert"]
        monkeypatch.setattr(teile.dienst, "katalog", katalog)
        a = (await c.get("/api/v1/einstellungen/angebot/ersatzstimme", headers=h)).json()
        assert [(o["wert"], o["titel"]) for o in a["optionen"]] == [("", "Vorgabe des Sprechdienstes"), ("serena", "serena"),
                                                                    ("aiden", "aiden")]

        a = (await c.get("/api/v1/einstellungen/angebot/private_stimmen_fuer", headers=h)).json()
        assert [(o["wert"], o["titel"]) for o in a["optionen"]] == [("medienpool", "Medienpool"), ("rufzeichen", "Rufzeichen"),
                                                                    ("vorlesen", "Vorlesen")]
        assert "nur einzelne" in a["optionen"][0]["hinweis"] and a["stand"] == ""
        assert a["zweite"] == [{"wert": zeit.lower(), "titel": "Zeit Stimme", "hinweis": "private Stimme"}]
        a = (await c.get("/api/v1/einstellungen/angebot/transkription_app", headers=h)).json()
        assert [o["wert"] for o in a["optionen"]] == ["Medienpool", "Rufzeichen", "Vorlesen"] and not a["eigener_wert"]

        # Freigabe der Zeit-Stimme für Vorlesen: gespeichert wie bisher als app:<Kennung>, und sie gilt sofort
        neu = [*teile.einstellungen.private_stimmen_fuer, f"vorlesen:{zeit.lower()}"]
        r = await c.patch("/api/v1/einstellungen", headers=h, json={"werte": {"private_stimmen_fuer": neu}})
        assert r.status_code == 200, r.text
        assert teile.darf_privat(Konto(id="1", name="probe", app="Vorlesen"), zeit)
        r = await c.patch("/api/v1/einstellungen", headers=h, json={"werte": {"private_stimmen_fuer": [*neu, "medienpool"]}})
        assert r.status_code == 422 and "Medienpool" in r.text


async def test_ohne_stimme_spricht_die_vorgabe_des_sprechdienstes(tmp_path):
    from app.modell.plan import StimmWahl
    from app.sprechen import Katalogstimme, Sprechdienst

    gesendet: list[dict] = []

    class Dienst:
        def gebunden(self):
            class Bindung:
                async def __aenter__(self): return self
                async def __aexit__(self, *_): return None
            return Bindung()

        async def json(self, methode, pfad, *, titel="", json=None, **_):
            gesendet.append(json)
            return {"filename": "a.wav"}

        async def herunterladen(self, pfad, ziel, *, titel=""):
            return ziel

    class Leitstelle:
        def dienst(self, name):
            return Dienst()

    sprechen = Sprechdienst(lambda: Leitstelle(), lambda: ("sprechen", "klonen"))
    await sprechen.sprechen("Hallo.", Katalogstimme(""), "de", 1.0, tmp_path / "a.wav")
    await sprechen.sprechen("Hallo.", Katalogstimme("aiden"), "de", 1.0, tmp_path / "b.wav")
    assert "voice" not in gesendet[0] and gesendet[1]["voice"] == "aiden"
    assert StimmWahl.fest("  ").name is None and StimmWahl.fest("").schluessel == "katalog:"
    assert StimmWahl.fest("aiden").schluessel == "katalog:aiden"
