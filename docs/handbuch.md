---
zweck: "Macht aus Text Sprache für alle Apps: Stimmen aus dem Katalog und eigene Klonstimmen, Vorlesen mit Vorpuffer, Pläne für lange Texte, Ergebnis als MP3 neben der Quelle."
geraet: [pi]
abhaengigkeiten: [kellerwolke, leitstelle, klangwerk, appkern]
daten:
  - "Pi: `{{wurzel}}/daten/vertonung.sqlite` (Pläne, Aufträge, Freigaben der Stimmen, Einstellungen); `abschnitte/` (Ton je Plan bis zum Zusammensetzen) und `referenzen/` (geholte Stimmproben, Zwischenspeicher)"
  - "Kellerwolke: Stimmen mit ihren Proben und die Ergebnisse, im Zweig `Apps/Vertonung` und neben den Quellen"
sicherung:
  - "jedes Ausrollen sichert `vertonung.sqlite` vor dem Neustart nach `{{wurzel}}/sicherungen` (die letzten zehn bleiben); das Werkzeug Sicherungen holt sie täglich nach `~/Sicherungen/vertonung/pi`"
  - "Stimmen und Ergebnisse liegen in der Kellerwolke und hängen an deren Sicherung"
schluessel_orte:
  - "Pi: Einstellungen im Verzeichnis `vertonung.sqlite`: App-Schlüssel der Kellerwolke, Schlüssel der Leitstelle (in der Oberfläche unter Einstellungen, verdeckt)"
  - "Pi: `{{wurzel}}/.env`, Modus 0600, für Werte, die nicht ins Repo gehören"
  - "Pi: `{{wurzel}}/zertifikate/`, Blattzertifikat mit Schlüssel aus der Hausstelle (vom Ausrollen)"
einrichten: einrichten.sh
stand: 72d2fc1
---

# Vertonung

## Zweck

Die Vertonung spricht Text für alle Apps: aus dem Katalog des Sprechdienstes (neun feste Stimmen) oder mit eigenen
Klonstimmen aus einer Probe. Kurze Texte kommen über `/sprechen` sofort zurück, als Strom mit Vorpuffer zum
Vorlesen; lange Texte laufen als Plan in Abschnitten und landen als MP3 (mono, 24 kHz) neben ihrer Quelle in der
[[Kellerwolke]]. Zahlen, Geld, Datum und Abkürzungen schreibt sie fürs Sprechen aus. Private Stimmen bekommt eine App
nur, wenn sie auf der Erlaubnisliste steht; der Server erzwingt das.

Gerechnet wird nie auf dem Pi: Sprechen und Klonen kommen aus dem [[Klangwerk]] über die [[Leitstelle]], ebenso die
Tonarbeit (messen, blenden, legen, kodieren) über den Tondienst; im Container gibt es kein ffmpeg. Kunden sind unter
anderem [[Assistent]] (Vorlesen), [[Zusage]] (Ansagen), [[Medienpool]] und [[TubeVault]] (Nachvertoner).

Auf dem Pi läuft sie als Compose-Projekt aus `compose.pi.yml` hinter ihrem Vorschaltdienst `vorne`. Adresse:
{{adresse}}.

## Was sie braucht

- Pi nach [[Grundlage Pi]] mit Docker; Mac nach [[Grundlage Mac]] für Entwicklung, Ausrollen und Hausstelle (für die
  Tests der Entwicklung auch ffmpeg am Mac).
- [[Kellerwolke]]: Konto zum Anmelden und ein App-Schlüssel für die Vertonung.
- [[Leitstelle]]: Anwendung "Vertonung" mit den Fähigkeiten stimme, stimme_klonen, ton, hoeren und text; das Ausrollen
  prüft, dass die Leitstelle den Tondienst meldet (fehlt er, ist das eine Warnung, kein Abbruch).
- [[Klangwerk]] am Mac mit den Diensten sprechen, klonen und ton (über den [[Maschinenraum]]).

## Neu einrichten

Zwei Wege. Aus der Sicherung: die jüngste Kopie von `vertonung.sqlite` zurückspielen; dann sind Einstellungen,
Freigaben der Stimmen und offene Pläne wie vorher, Stimmen und Ergebnisse liegen in der Kellerwolke. Frisch: leere
Datenbank, erste Einrichtung mit neuem App-Schlüssel, Leitstelle unter Einstellungen; die Stimmen findet sie in der
Kellerwolke wieder.

### 1. Repo und Entwicklungsumgebung am Mac

```
git clone {{repo}} {{ordner}}
cd {{ordner}} && ./einrichten.sh
```

Python-Umgebung, Oberfläche, Appkern auf einen Commit, Git-Haken; das Ausrollen prüft mit dieser Umgebung.

Probe: `test -f frontend/dist/index.html && backend/.venv/bin/python -c "import appkern"` endet ohne Fehler.

### 2. Ordner auf dem Pi

Auf dem Pi `mkdir -p {{wurzel}}/daten` (sonst legt Docker ihn für root an). Aus der Sicherung die jüngste Kopie als
`{{wurzel}}/daten/vertonung.sqlite` ablegen (Besitzer `pi`).

Probe: `stat -c %U {{wurzel}}/daten` meldet `pi`.

### 3. Ausrollen

Am Mac `tools/ausrollen.sh`: Tests, Appkern-Stand, Tondienst bei der Leitstelle, Zertifikat, Bau, Start und Prüfung von
Fassung, HTTP/2 und Symbolen. Vorher läuft `handbuch freigabe` (Prüfung der Seite, Probelauf, Handbuch).

Probe: `curl -s --cacert "$(mkcert -CAROOT)/rootCA.pem" {{adresse}}/api/v1/app` meldet `"fassung": "{{fassung}}"`.

### 4. Erste Einrichtung

Aus der Sicherung entfällt sie. Frisch: in der [[Kellerwolke]] einen App-Schlüssel für die Vertonung anlegen,
{{adresse}} öffnen und mit dem Einrichtungscode aus `{{wurzel}}/daten/einrichtungscode` (auf dem Pi) die Adresse der
Kellerwolke und den Schlüssel eintragen; danach mit dem eigenen Kellerwolke-Konto anmelden.

Probe: `/api/v1/app` meldet `"einrichtung_noetig": false` und den Besitzer.

### 5. Leitstelle, Tondienst und Stimmen

Aus der Sicherung stehen sie im Verzeichnis. Frisch: in der [[Leitstelle]] die Anwendung "Vertonung" anlegen, ihren
Schlüssel unter Einstellungen, Verbindungen eintragen, "Tondienst" wählen und "Adresse dieser App" auf {{adresse}}
setzen. Unter Stimmen prüfen, welche Apps private Stimmen bekommen (Erlaubnisliste).

Probe: unter Einstellungen, Verbindungen sind Kellerwolke und Leitstelle grün, und ein kurzer Text spricht hörbar mit
einer Katalogstimme.

## Sicherung und Rückspielen

Jedes Ausrollen legt vor dem Neustart eine stimmige Kopie von `vertonung.sqlite` nach
`{{wurzel}}/sicherungen/vertonung-<Zeit>.sqlite`; die letzten zehn bleiben. Das Werkzeug Sicherungen am Mac holt sie
täglich nach `~/Sicherungen/vertonung/pi` (Stand in `~/Sicherungen/LIESMICH.md`). Zwischen zwei Ausrollen entsteht
keine Sicherung. `abschnitte/` und `referenzen/` sind Zwischenstände und brauchen keine Sicherung; Stimmen und
Ergebnisse hängen an der Sicherung der Kellerwolke.

Zurückspielen: auf dem Pi im Ordner {{wurzel}} `docker compose -f compose.pi.yml stop vertonung`, die Kopie als
`daten/vertonung.sqlite` ablegen (alte `-wal` und `-shm` daneben entfernen), `docker compose -f compose.pi.yml start
vertonung`. Probe wie in Schritt 3.

## Wenn etwas klemmt

- Sprechen scheitert: die Leitstelle meldet keinen Sprechdienst (Klangwerk sprechen nicht gestartet, oder der Mac
  schläft); Aufträge warten über den Appkern und versuchen es erneut.
- Tonarbeit scheitert: kein Tondienst bei der Leitstelle (Klangwerk ton); das Ausrollen warnt schon davor.
- Eine App bekommt eine private Stimme nicht: sie steht nicht auf der Erlaubnisliste unter Stimmen; das ist Absicht.
- Das Ausrollen wartet lange: es wartet auf eine Lücke ohne laufenden Auftrag (bis vier Stunden); `--sofort` rollt
  trotzdem aus.
