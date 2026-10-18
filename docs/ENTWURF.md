# Vertonung: Entwurf

Stand 18.10.2026, freigegeben. Grundlage: die Entscheidungen im Neubauplan (`txt2voice/docs/NEUBAU.md`, Abschnitt
"Vertonung"), die Bestandsaufnahme der alten Sprachausgabe in txt2voice (Endpunkte, Formate, Kunden) und die Lehren des
Appkerns (`Appkern/docs/LEHREN.md`).

Die Vertonung macht aus Text Sprache: vorlesen, Dialoge mit Rollen, zeitgenau nach einem Transkript neu sprechen;
später Video. Ihre Stimmen verwaltet sie selbst, privat und fremd getrennt, mit bekannten Namen. Sie ist eine App auf
dem Appkern wie die Transkription: Dateien in der Kellerwolke, KI nur über die Leitstelle (Sprechdienst, Klondienst,
Hördienst), Anmeldung mit dem Kellerwolke-Konto, läuft auf dem Pi. Alles, was die Oberfläche kann, geht auch über die
Schnittstelle; Kunden sind Rufzeichen, Fundus, Bombel, Zusage, Medienpool, das Dateimenü der Kellerwolke und später
TubeVault.

## 1. Was neu besser wird als in der alten App

| Alt | Neu |
|---|---|
| Vorlesen schickte den ganzen Text in einem Aufruf oder satzweise ohne Wiederholung; ein fehlender Satz wurde still übersprungen | Ein Werk für jede Art: Sätze teilen (höchstens 180 Zeichen je Aufruf), jedes Stück prüfen, bis dreimal wiederholen, nie stumm |
| Dialoge mit Rollen gab es nicht | Rollen mit je einer Stimme; Text in der Form `Name: Satz` |
| Zeitgenau nur in der Videovertonung, mit eigens gebautem schwarzem Ersatzvideo | Zeitgenau nach jedem Transkript oder Untertitel, ohne Video |
| Stauchen bis Faktor 2,0, Bericht nur als Summe | Erst Lücken nutzen, dann maßvoll stauchen (Komfort 1,15, höchstens 1,5), dann schieben; Bericht je Abschnitt |
| Ersatzstimme nur im Log | Ersatzstimme im Plan und in der Oberfläche vermerkt |
| Stimmen in der Datenbank, ohne privat und fremd; nach dem Hochladen "pending" und unsichtbar | Stimmen als Dateien in der Kellerwolke mit Angaben (Bereich, bekannt als, Herkunft, Referenztext); sofort nutzbar |
| Probe aus dem Video in 16 kHz gewonnen und auf 24 kHz hochgerechnet (Bandbreite blieb 8 kHz) | Probe immer aus der Originalquelle, nie aus der Hörfassung |
| Ergebnisse in `data/results` oder `data/temp`, beim Vorlesen nie MP3 | Ergebnis als Begleiter neben der Quelle, Format wählbar; genau eine Wandlung am Ende |
| Nachbessern hieß alles neu | Plan ändern; neu gesprochen wird nur, was sich geändert hat |
| Ohne Anmeldung, offen für jeden (CORS `*`) | Anmeldung oder App-Schlüssel; private Stimmen nur für erlaubte Apps |

## 2. Daten

**In der Kellerwolke** (Zweig `Apps/Vertonung`):

| Ort | Inhalt |
|---|---|
| `Stimmen/Privat/`, `Stimmen/Fremd/` | je Stimme die Referenz `<Name>.wav` (3 bis 10 s, Kanten geblendet) mit den Begleitern `<Name>.stimme.json` (Rolle `stimme`) und auf Wunsch `<Name>.quelle.<endung>` (Rolle `quelle`, die Originalaufnahme) |
| `Texte/` | freie Texte und Dialoge der App (`Brief.md`), daneben `Brief.vertonung.json` (Plan, Rolle `vertonung`) und `Brief.sprache.mp3` (Ergebnis, Rolle `sprache`) |
| neben jeder gewählten Quelle | `<Stamm>.vertonung.json` und `<Stamm>.sprache.<endung>`; gelesen und geschrieben nur mit einer Anfrage (Wahl in der App oder im Dateimenü der Kellerwolke), wie bei der Transkription |

Die festen Stimmen des Sprechdienstes (aiden, dylan, eric, ono_anna, ryan, serena, sohee, uncle_fu, vivian) bilden den
Katalog; sie haben keine Dateien.

**Stimmangaben** (`<Name>.stimme.json`):

```json
{
  "format": "stimme/1",
  "name": "Kerstin",
  "bekannt_als": ["Kerstin K."],
  "bereich": "fremd",
  "sprache": "de",
  "referenztext": "Heute zeige ich euch, wie ...",
  "herkunft": {"art": "aufnahme", "knoten_id": "...", "pfad": "Apps/Transkription/Aufnahmen/Folge 12.wav", "start": 61.2, "ende": 68.4},
  "sprecherprofil": "...",
  "notiz": ""
}
```

`bekannt_als` verbindet die Stimme mit Namen, unter denen dieselbe Person woanders auftaucht; `sprecherprofil` mit dem
Profil der Transkription (gleiche Person). Private Stimmen gehören echten Menschen aus dem Umfeld: nie für Öffentliches
und nie in Bildern.

**Vertonungsplan** (`<Stamm>.vertonung.json`, Format `vertonung/1`), eine Datei je Vertonung, versioniert durch die
Kellerwolke:

```json
{
  "format": "vertonung/1",
  "art": "zeitgenau",
  "quelle": {"knoten_id": "...", "pfad": "Apps/Transkription/Aufnahmen/Runde.transkript.json", "etag": "..."},
  "sprache": "de",
  "rollen": [
    {"kennung": "r1", "name": "Anna", "stimme": {"art": "klon", "knoten_id": "..."}},
    {"kennung": "r2", "name": "Erzähler", "stimme": {"art": "katalog", "name": "serena"}}
  ],
  "abschnitte": [
    {"nr": 1, "rolle": "r1", "text": "Guten Tag ...", "start": 12.4, "ende": 18.9, "tempo": 1.0, "pause_danach_s": 0.4,
     "stand": "gesprochen", "pruefsumme": "...",
     "bericht": {"weg": "luecke", "stauchung": 1.0, "versatz_s": 0.0, "versuche": 1, "ersatz": false}}
  ],
  "ziel": {"format": "wie_quelle"},
  "ergebnis": {"knoten_id": "...", "dauer_s": 2714.0}
}
```

Die Prüfsumme je Abschnitt (Text, Stimme, Tempo) entscheidet, was neu gesprochen wird.

**In der App** (SQLite, nur Verzeichnis und Zwischenspeicher, jederzeit aus der Kellerwolke neu aufbaubar):
Verzeichnis der Pläne und der Stimmen, Ton je Abschnitt im Arbeitsformat (damit Nachbessern nur Geändertes spricht),
Aufträge und Protokoll aus dem Appkern.

## 3. Formate

| Stelle | Format | Warum |
|---|---|---|
| Referenz zum Klonen | WAV, 16 Bit, 24 kHz mono, 3 bis 10 s, Kanten 15 ms geblendet | so erwartet sie der Klondienst; gewonnen aus der Originalquelle, nur heruntergerechnet (soxr), nie hochgerechnet |
| Antwort des Sprech- und Klondienstes | WAV, 16 Bit, 24 kHz mono | die Rate des Modells |
| Arbeitsformat | WAV, 32-Bit-Gleitkomma, 24 kHz mono | Blenden, Stauchen, Pausen und Mischen ohne wiederholtes Quantisieren; die Antwort wird verlustfrei übernommen |
| Ergebnis Vorlesen und Dialog | Vorgabe MP3 mono, 24 kHz, 128 kbit/s (wählbar: WAV, FLAC, OGG) | Sprache braucht keine höhere Rate; keine künstliche Hochrechnung |
| Ergebnis zeitgenau | Abtastrate und Kanäle der Quellaufnahme, mindestens so lang wie sie | passt ohne weitere Wandlung neben das Original und unter das Video |
| Sofortantwort für Kunden | WAV, 16 Bit, 24 kHz mono | wie bisher; Rufzeichen, Fundus, Bombel, Zusage und Medienpool lesen es direkt |

Gewandelt wird genau einmal am Ende mit dem gemessenen Resampler des Appkerns (`appkern.ton`, soxr); jede Wandlung ist
getestet (Frequenz, Dauer, Format). Auf dem Pi läuft nur ffmpeg (wandeln, stauchen, mischen, kodieren).

## 4. Abläufe

**Plan anlegen** (sofort, kein Auftrag):

| Art | Aus | Abschnitte |
|---|---|---|
| Vorlesen | Text oder Datei (Text, Markdown) | Sätze; eine Stimme |
| Dialog | Text mit Zeilen `Name: Satz` | je Zeile ein Abschnitt; je Name eine Rolle mit Stimme |
| Zeitgenau | Transkript der Transkription oder Untertitel (SRT, WebVTT) | Segmente zu Sätzen zusammengefasst (neuer Satz bei Pause über 1,2 s, Satzende oder Sprecherwechsel; unter 20 Zeichen am Vorgänger, wenn derselbe Sprecher spricht); je Sprecher eine Rolle |

**Aufträge:**

| Art | Phasen | Fortsetzbar |
|---|---|---|
| `vertonen` | Vorbereiten (Plan, Stimmen, Referenzen holen); Sprechen je Abschnitt (an Teilsatz- und Wortgrenzen teilen, über die Leitstelle sprechen oder klonen, prüfen: leer oder kürzer als Zeichen/25 s heißt Aussetzer, länger als Zeichen/1,8 s heißt Echo; bis dreimal, das längste gute Ergebnis bleibt; sonst die Ersatzstimme, vermerkt); Fügen (Gleichleistungsblende 30 ms; zeitgenau erst Lücken, dann stauchen, dann schieben, nie Text kürzen, nie abschneiden); Wandeln (einmal); Ablegen (Ergebnis und Plan mit Bericht als Begleiter) | ja, je Abschnitt; nach Neustart weiter; Geändertes nur neu |
| `stimme_gewinnen` | Quelle holen; Transkript und Sprecher aus der Transkription (ein vorhandenes Transkript wird genutzt); Kandidaten von 6 bis 8 s eines einzigen Sprechers ohne Überlappung, Pegel geprüft (zu leise, übersteuert); bis vier Kandidaten zum Anhören | nein |

Wartet die Leitstelle (Modell lädt, Speicher knapp), steht das als Schritt im Auftrag; abbrechen geht zwischen zwei
Abschnitten.

## 5. Schnittstelle (`/api/v1`, alles hinter Anmeldung oder App-Schlüssel)

| Aufruf | Zweck |
|---|---|
| `GET /stimmen?bereich=privat\|fremd\|katalog&suche=` | Stimmen mit Angaben; private nur für erlaubte Aufrufer |
| `GET /stimmen/{id}`, `PATCH /stimmen/{id}`, `DELETE /stimmen/{id}` | Angaben lesen und ändern (Bereich wechselt den Ordner); löschen in den Papierkorb der Kellerwolke |
| `POST /stimmen?name=&bereich=` | Referenz hochladen (Körper ist der Ton); ohne Referenztext hört die Transkription ihn heraus |
| `GET /inhalt/stimmen/{id}/probe` | Referenz zum Anhören |
| `POST /stimmen/gewinnen`, `POST /stimmen/gewinnen/{auftrag}/uebernehmen` | Kandidaten aus einer Aufnahme suchen; einen als Stimme anlegen |
| `POST /sprechen` | `{text, stimme, sprache, tempo}` liefert sofort den Ton (WAV, 24 kHz mono) mit Dauer im Kopf; mit `?strom=1` satzweise, damit Vorlesen beim ersten Satz beginnt. Für kurze Texte der Kunden; längere gehen über einen Plan |
| `GET /plaene?suche=&art=`, `POST /plaene` | Verzeichnis; Plan anlegen aus Text, Dialog, Transkript oder Untertiteln |
| `GET /plaene/{id}`, `PATCH /plaene/{id}` | Plan lesen und ändern; nur mit dem zuletzt gelesenen Stand (sonst 409) |
| `POST /plaene/{id}/vertonen` | Auftrag; spricht nur Abschnitte, deren Prüfsumme sich geändert hat |
| `GET /inhalt/plaene/{id}/abschnitte/{nr}`, `GET /inhalt/plaene/{id}/ergebnis` | einzelner Abschnitt und Ergebnis zum Anhören |

Aktionen im Dateimenü der Kellerwolke: **Vorlesen** (Text, Markdown), **Neu sprechen** (Transkript, SRT, WebVTT),
**Stimme gewinnen** (Ton, Video). Fremde Apps melden sich mit ihrem App-Schlüssel der Kellerwolke an. Die alten Kunden
stellen in Stufe T4 auf diese Schnittstelle um; die alten Pfade (`/api/synthesize`, `/api/voices`) bildet die
Vertonung nicht nach.

## 6. Oberfläche (Entwürfe in `mockups/`)

Bereiche in der Schale: **Vertonen**, **Stimmen**; dazu aus dem Appkern Aufträge, Protokoll, Einstellungen. Die
Entwürfe laden die echte Gestaltung aus dem eingebundenen Appkern (`mockups/kopf.css`); ansehen mit einem statischen
Server aus dem Repo-Wurzelordner, dann `/mockups/vertonung.html` und `/mockups/vertonung-mobil.html` (Knopf unten
rechts: hell oder dunkel). In allen Entwürfen stehen nur Katalog-Namen von Stimmen.

`mockups/vertonung.html`, am Rechner:

1. **Vertonen**: die Vertonungen mit Art, Quelle, Stimmen und Stand; neu als Vorlesen, Dialog oder Zeitgenau (Quelle
   aus dem Zweig der App oder aus der ganzen Kellerwolke über die Dateiwahl).
2. **Vorlesen**: Text einfügen oder Datei wählen, Stimme, Tempo, Format; der Plan zeigt die Sätze, jeder einzeln
   anhörbar; Ergebnis im Spieler.
3. **Dialog**: Rollen oben (Name, Stimme, Probe), darunter die Abschnitte als Zwiegespräch; eine Stimme tauschen
   markiert die Abschnitte der Rolle als geändert, "Geänderte sprechen" spricht nur diese.
4. **Zeitgenau**: Spur der Quelle und Spur der neuen Sprache übereinander; je Abschnitt der Bericht (Lücke genutzt,
   gestaucht 1,12, geschoben 0,4 s, Ersatzstimme); Abschnitte mit Hinweis oben in der Liste.
5. **Stimmen**: Reiter Privat, Fremd, Katalog; Liste mit Probe; rechts die Angaben (bekannt als, Sprache, Herkunft mit
   Sprung in die Quelle, Referenztext, Sprecherprofil der Transkription).
6. **Stimme gewinnen**: Aufnahme gewählt, Kandidaten mit Wellenform, Sprecher und Bewertung; anhören, einen
   übernehmen, Bereich wählen.

`mockups/vertonung-mobil.html`, eigene Telefonansicht (Reiter Vorlesen, Vertonungen, Stimmen, Mehr):

1. **Vorlesen**: Text einfügen, Stimme, los; spielt ab dem ersten Satz.
2. **Vertonungen**: Liste mit Stand; Tippen öffnet die Vertonung, ein eigener Knopf spielt das Ergebnis.
3. **Stimmen**: Liste nach Bereich, Probe anhören; eine Probe aufnehmen mit dem Rekorder des Appkerns.

## 7. Übernahme der Stimmen

Die Stimmen der alten App liegen seit dem Umzug (17.10.2026) in `Apps/Stimmenausgabe/Stimmen`. Ein Werkzeug mit
Vorschau ordnet sie nach `Stimmen/Privat` und `Stimmen/Fremd` (Vorschlag aus der Herkunft: aus Videos fremd, eigene
Aufnahmen privat; der Nutzer bestätigt je Stimme), schreibt die Angaben und verschiebt, ohne Doppel anzulegen
(Prüfsumme gegen den ganzen Zweig).

## 8. Entscheidungen des Nutzers (18.10.2026)

1. Entwürfe am Rechner und am Telefon: so übernehmen.
2. Private Stimmen nur für Apps auf einer Erlaubnisliste in den Einstellungen; Vorgabe Rufzeichen, Fundus, Bombel,
   Zusage und (18.10.2026) der Nachvertoner von TubeVault; Medienpool nie. Der Server erzwingt es.
3. Ergebnis beim Vorlesen und bei Dialogen: MP3 mono, 24 kHz, 128 kbit/s; WAV, FLAC und OGG wählbar.
4. Repository: öffentlich, wie Transkription und Appkern.
5. Dienst für andere Apps (18.10.2026): der Sender bestimmt, ob Aufnahme, Plan und Ergebnis in der Kellerwolke bleiben
   (`behalten`); TubeVault behält nicht. Der Nachvertoner läuft auf dem Pi.
6. Klonen in Originalstimmen (18.10.2026): Referenz 5 bis 7 Sekunden, geschnitten nur in Sprechpausen, Referenztext
   genau für diesen Ausschnitt; die Stelle wird im ganzen Video gesucht. Eine gewonnene Stimme hängt am erkannten
   Sprecher und wird bei späteren Videos wiederverwendet statt neu ausgeschnitten.
