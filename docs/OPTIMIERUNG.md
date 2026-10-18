# Optimierung der Vertonung

Plan vom 18.10.2026 (Nutzer: "optimiere isoliert für jeden Vertonungsfall"; "am Ende muss alles mit den lokalen
Modellen lösbar sein"; "es ist ausreichend Zeit auch für mehrere Runden"). Vorrang hat TubeVault: Videos in bekannten
Sprachen werden deutsch vertont.

## Regeln

- Getestet wird nur mit Klonstimmen: der festen Zeit-Stimme oder aus Videos gewonnenen Stimmen. Nie mit den eingebauten
  Stimmen des Sprachmodells (die schlechtesten).
- Erst kurze Videos (2 bis 5 Minuten); läuft es gut, Videos mit 15 bis 20 Minuten. Keine Musikvideos, sondern Dokus,
  Filme, Anleitungen.
- Im Betrieb nur lokale Modelle über die Leitstelle. Verglichen werden Qwen3-next 80B (4 Bit), Qwen 3.6 27B (8 Bit),
  Qwen 3.6 35B-A3B (4 Bit) und Qwen 3.8 27B (4 Bit); alle liegen in LM Studio.
- Je Runde genau eine Änderung, derselbe Prüfsatz, Messgrößen vorher und nachher; das Ergebnis steht unten in der
  Tabelle der Strecke.
- Übersetzen: vollständig und sinngetreu, nur knapper formulieren, nie Inhalt weglassen (Regel des Nutzers). Ob bei
  sehr schnellen Sprechern gestrafft werden darf, entscheidet der Nutzer, wenn die Messung zeigt, dass es nötig ist.

## Prüfsatz

| Kennung | Video | Länge | Sprache | Warum |
|---|---|---|---|---|
| K1 | PostgreSQL in 100 Seconds (TubeVault n2Fluyr3lbc) | 2:36 | en | sehr schnell, Fachwörter, Zahlen, kein Untertitel |
| K2 | (folgt) eine Anleitung mit Uhrzeiten, Preisen, Einheiten | 2 bis 5 min | en | Sprechfassung |
| K3 | (folgt) ein Interview mit zwei Sprechern | 2 bis 5 min | en | Strecke 3 |
| L1 | (folgt, erst nach K1 bis K3) | 15 bis 20 min | en | Dauer, Speicher, Zeitlage über lange Strecken |
| T23 | echter TubeVault-Wunsch: Interview "Russia faces logistical winter nightmare" (Nachvertoner, Zeit-Stimme) | 15:23 | en | erster langer Lauf im Betrieb |

## Messgrößen

- Dauer: gesamt und je Minute Video, getrennt nach Transkription, Übersetzung, Sprechen
- Zeitlage: Länge des Ergebnisses gegen die Quelle, Versatz (größter, Summe), Stauchung (Mittel, größte, Anteil über
  "unauffällig")
- Aussprache: Wortfehlerquote beim Zurückhören (Mittel, größte), auffällige Abschnitte, häufige Abweichungen nach Art
  (Zahlen, Abkürzungen, Anglizismen, Eigennamen)
- Übersetzung: Anteil über der Zeichengrenze, Nachfassungen, Vollständigkeit (Stichprobe)
- Klonen: Versuche, Ersatzstimme, Befunde (Aussetzer, Echo)

## Strecke 1: feste Stimme (Zeit-Stimme), am einfachsten

1. Grundlinie: Übersetzung mit Zeichenbudget aus dem gemessenen Sprechtempo, Nachfassen zu langer Abschnitte (0.5).
2. Ausspracheprüfung messen (0.6): Quote je Abschnitt, Abweichungen nach Art auswerten.
3. Sprechfassung (Transferschicht): Zahlen, Uhrzeiten, Daten, Einheiten, Prozent, Versionen, Abkürzungen sprechbar
   machen; Anglizismen bleiben. Varianten: Regeln allein, Sprachmodell allein, Regeln und Sprachmodell; je Modell.
4. Übersetzungsmodelle vergleichen: 80B gegen 3.6 und 3.8 bei gleichem Budget (Grenzentreue, Nachfassungen, Dauer,
   Stichprobe Sinn).
5. Sprechen: bei auffälliger Aussprache neu sprechen; Stückgröße und Satzgrenzen.

| Runde | Fassung | K1 Dauer | Länge (Quelle 156,5 s) | Versatz max | Stauchung Mittel/max | Aussprache Mittel/max |
|---|---|---|---|---|---|---|
| 1 | 0.5.3 | 9:15 (3,5-fach) | 156,5 s | 0 | 1,00 / 1,02 | (noch nicht gemessen) |
| 2 | 0.6.0 | 6:42 (2,6-fach) | 156,5 s | 0 | 1,13 / 1,24 | 3,0 % / 5,3 % |

K2 (How to burn $30m on a JavaScript framework, 5:08, Zeit-Stimme, 0.7.2 mit Sprechfassung):

| Lauf | Textquelle | Dauer | Länge (Quelle 307,7 s) | Versatz max (Abschnitte) | Stauchung Mittel/max | Aussprache Mittel/max |
|---|---|---|---|---|---|---|
| K2a | Untertitel der Quelle (automatisch) | 12:10 (2,4-fach) | 307,7 s | 1,1 s (9 von 21) | 1,05 / 1,50 | 0,9 % / 9,1 % |
| K2b | eigene Transkription | 10:07 (2,0-fach), mit Transkription | 307,7 s | 0 (0 von 16) | 1,00 / 1,00 | 1,2 % / 7,5 % |

Befund K2a: Die automatischen Untertitel überlappen in der Zeit (ein Fenster beginnt, bevor das vorige endet) und haben
verfälschte Satzzeichen und Hörfehler ("Gangdom Style"); daher die vielen kleinen Verschiebungen. Die Sprechfassung
greift (2012, 30 Millionen Dollar, 65 %, 20 $).

Ergebnis K2: Die eigene Transkription ist trotz des Hörens schneller und legt sauber in die Zeit (kein Versatz, kein Stauchen), die Aussprache ist gleichauf. Automatische Untertitel der Quelle nicht verwenden; Empfehlung für TubeVault: Vorgabe der Untertitel auf "nur vom Autor" (Einstellung des Nutzers). Für Originalstimmen (Strecke 2 und 3) ist die eigene Transkription ohnehin nötig (Wortzeiten, Sprecher).

Betrieb T23 (0.7.x, über den Nachvertoner): 15:23 Video in 25,1 min vertont (1,6-fach), 45 Abschnitte, keine Ersatzstimme, an TubeVault geliefert. Ein zweiter Wunsch (#22) scheiterte, weil die Vertonung währenddessen ausgerollt wurde; seitdem wartet das Ausrollen auf laufende Aufträge (Appkern Lehre 29) und der Nachvertoner übersteht kurze Ausfälle.

Befund Runde 2: Mit gemessenem Tempo wird weniger gestrafft und etwas mehr gestaucht (über "unauffällig" 1,15 in drei von sieben Abschnitten). Die meisten Abweichungen beim Zurückhören sind nur Schreibweisen (getrennt oder zusammen); sie zählen ab 0.7 nicht mehr. Echte Fälle: englische Namen und Begriffe werden deutsch gelesen (Citus wird Zitus, Control wird Kontroll, hstore wird h store). Nächste Runde: Sprechfassung mit Regeln (0.7) und dann der Umgang mit englischen Namen.

Befund Runde 1: Die Zeit-Stimme spricht rund 17 Zeichen je Sekunde (Katalogstimme serena 11,6); gerechnet wurde noch mit der Vorgabe 11,5, die Übersetzung wurde also stärker gestrafft als nötig. Das Tempo ist jetzt gemessen. Sprechen kostet am meisten (40 bis 60 s je Abschnitt von 12 bis 39 s).

## Strecke 2: Stimme kopieren (ein Sprecher), mittel

1. Referenz gewinnen: 5 bis 7 Sekunden, Schnitt nur in Sprechpausen (Wortzeiten der Transkription), kein zweiter
   Sprecher, keine Musik, gleichmäßiger Pegel; die beste Stelle im ganzen Video; Referenztext genau aus den Wörtern
   dieses Ausschnitts; Probe sprechen und zurückhören.
2. Wiederverwenden: eine gewonnene Stimme hängt am Sprecherprofil der Transkription und wird bei späteren Videos genommen
   statt neu ausgeschnitten.
3. Wie Strecke 1 mit der gewonnenen Stimme (Referenz englisch, gesprochen deutsch).

## Strecke 3: mehrere Stimmen, am komplexesten

1. Sprechertrennung der Transkription, je Sprecher eine Stimme (wiederverwendet oder gewonnen), Rollen im Plan.
2. Überlappungen, kurze Einwürfe, Zuordnung über Sprecherprofile.
