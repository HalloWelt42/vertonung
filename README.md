# Vertonung

Vertonung macht aus Text Sprache. Eine App auf dem [Appkern](https://github.com/HalloWelt42/appkern): Dateien in der Kellerwolke
(Zweig `Apps/Vertonung`), KI nur über die Leitstelle, Anmeldung mit dem Kellerwolke-Konto, gestartet vom Stellwerk.
Ton rechnet sie nie selbst: messen, blenden, stauchen, legen und kodieren macht der Tondienst auf dem Mac über die
Leitstelle (Einstellung "Tondienst"); im Container gibt es kein ffmpeg. Die Tests rechnen Ton mit dem echten Tondienst im
Prozess und brauchen dafür ffmpeg auf dem Entwicklungsrechner.

## Einrichten

```bash
./einrichten.sh
```

Legt die Python-Umgebung an, holt die Pakete der Oberfläche und baut sie. Danach im Stellwerk starten (Eintrag
`stellwerk.toml`) und `http://127.0.0.1:8641` öffnen: die erste Einrichtung fragt nach der Adresse der
Kellerwolke und dem App-Schlüssel (in der Kellerwolke unter Einstellungen, Zugänge). Alles Weitere unter Einstellungen.

## Entwickeln

| Teil | Befehl |
|---|---|
| Backend | `cd backend && .venv/bin/uvicorn app.main:app --port 8641 --reload` |
| Oberfläche | `cd frontend && npm run dev` (Port 9641, leitet `/api` ans Backend) |
| Tests | `cd backend && .venv/bin/python -m pytest` |
| Symbole | `python3 tools/symbole.py` nach einer Änderung an `frontend/public/symbol.svg` |
| Fassung | `tools/version.sh minor` für eine neue Fähigkeit; jeder Commit zählt sonst selbst hoch |
| Appkern | `tools/appkern.sh` hebt Oberfläche und Backend auf denselben neuesten Commit |
| Ausrollen | `tools/ausrollen.sh` (Angaben in `deploy/ausrollen.toml`) |

Der Verbundtest (`tests/test_verbund.py`) spricht mit einer echten Kellerwolke und braucht `backend/.env.test` (nicht
im Repo) mit `KELLERWOLKE_ADRESSE`, `KELLERWOLKE_SCHLUESSEL`, `KELLERWOLKE_KENNUNG`, `KELLERWOLKE_PASSWORT`: ein eigener
Zugang nur für Tests, nicht der der Entwicklungsinstanz. Aufräumen und Zurückziehen der Aktionen kommen aus
`appkern.testen`.

## Prüfungen

Vor jedem Commit (Hook in `tools/git-hooks`, eingerichtet von `einrichten.sh`): Fassung hochzählen, nur gerade
Zeichen, Stil ohne `!important`, ohne einseitige Streifen und ohne Regeln auf Klassen der Schale. Beim Ausrollen: Tests,
gleicher Appkern in Oberfläche und Backend, Fassungen, HTTP/2, deckende Symbole. Von Hand vor dem Vorzeigen:
`docs/ABNAHME.md`.

## Aufbau

| Ort | Inhalt |
|---|---|
| `backend/app/main.py` | baut die App auf dem Gerüst |
| `backend/app/einstellungen.py` | eigene Einstellungen (dazu kommen Kellerwolke, Leitstelle, Konten) |
| `backend/app/arten.py` | Arten von Aufträgen |
| `backend/app/api/` | eigene Endpunkte; `sprechen.py` mit `/sprechen` und dem Strom `/sprechen/strom` (Vertrag in `modell/sprechen.py`) |
| `backend/app/saetze.py` | Text in Sätze (mit Lage im Eingabetext) und Stücke für den Sprechdienst |
| `backend/app/sprechfassung.py` | die eine Stelle, die Zahlen, Geld, Einheiten, Datum, Uhrzeit, Ordnungszahlen und Abkürzungen fürs Sprechen ausschreibt (Pläne, `/sprechen`, Strom, Ausspracheprüfung) |
| `frontend/src/App.svelte` | Bereiche der App in der gemeinsamen Schale |
| `frontend/src/seiten/` | Seiten der Bereiche |

Entwurf und Entscheidungen: `docs/ENTWURF.md`; Entwürfe der Oberfläche in `mockups/`.

## Lizenz

**Nicht-kommerzielle Nutzung** - Siehe [LICENSE](LICENSE)

Erlaubt: Private Nutzung, Installation, persönliche Anpassungen, Teilen mit Quellenangabe

Verboten: Kommerzielle Nutzung, Verkauf, Einbindung in kommerzielle Produkte

---

## Unterstützen

Vertonung ist ein privates Hobby-Projekt. Kein Tracking, keine Werbung, keine Kompromisse.

Wenn dir das Projekt gefällt, kannst du ihm einen Stern geben - oder direkt hier:

[![Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/HalloWelt42)

**Crypto:**

| Coin | Adresse |
|------|---------|
| BTC | `bc1qnd599khdkv3v3npmj9ufxzf6h4fzanny2acwqr` |
| DOGE | `DL7tuiYCqm3xQjMDXChdxeQxqUGMACn1ZV` |
| ETH | `0x8A28fc47bFFFA03C8f685fa0836E2dBe1CA14F27` |

Copyright (c) 2026 HalloWelt42
