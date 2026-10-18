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
| K3 | National Geographic, Fort Lauderdale: Erzähler, Beamte, Fluggast | 3:35 | en | Strecke 3 |
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

Runde 4 (Modellvergleich, K2, 16 Abschnitte, gleiche Anweisung und Budgets; Werkzeug app/messung/vergleich.py):

| Übersetzer | Dauer warm | Länge gegen Grenze | vollständig nach 3.6 35B / 3.8 27B / 3.6 27B |
|---|---|---|---|
| Qwen3-next 80B | 105 bis 170 s | 0,58 bis 0,62 | 94 % / 56 bis 81 % / 100 % |
| Qwen 3.8 27B | 316 s | 0,79 bis 0,81 | 100 % / 100 % (eigenes) / 100 % |
| Qwen 3.6 27B (8 Bit) | (476 s mit Laden) | 0,78 | 100 % / 100 % / - |
| Qwen 3.6 35B-A3B | 79 s | 0,58 bis 0,80 | 94 % (eigenes) / 69 bis 100 % / 94 % |

Befund: Das 80B kürzt Inhalt weg (Telegrammstil, "a cool parlor trick" wird "einen Trick"), und als eigener Gutachter
übersieht es das; Gutachter streuen stark, ein Urteil braucht mehrere. Neue Modelle in LM Studio liefern die Antwort
mit festem Schema im Denkfeld (Appkern 0.28 liest es). Ursache beim 80B ist auch die Anweisung ("möglichst nahe am
Ziel"); sie stellt jetzt Vollständigkeit vor Kürze (0.10.4), Messung folgt.

Runde 5 (19.10.2026, Anweisung 0.10.4 "Vollständigkeit vor Kürze", K2, gleiche Budgets; Qwen 3.8 und 3.6 lokal, weil
dasselbe Modell lokal da ist; Zeiten der lokalen Modelle mit Laden, 80B aus der Nacht davor):

| Übersetzer | Dauer | über Grenze | knapper | Länge gegen Grenze | vollständig nach 80B / 3.6 35B / 3.8 27B |
|---|---|---|---|---|---|
| Qwen3-next 80B | 233 s | 0/16 | 0 | 0,82 | - / 88 % / 94 % |
| Qwen 3.8 27B | 374 s | 0/16 | 1 | 0,81 | 100 % / 94 % / 100 % (eigenes) |
| Qwen 3.6 35B-A3B | 308 s | 0/16 | 1 | 0,82 | 94 % / 81 % (eigenes) / 94 % |

Befund: Die neue Anweisung wirkt. Das 80B nutzt das Budget jetzt wie die anderen (0,82 statt 0,58 bis 0,62) und
kürzt keinen Inhalt mehr weg; die Gutachter finden je höchstens zwei Kleinigkeiten (Ton, "minions"). Qwen 3.6 35B
lässt echte Sprachfehler stehen ("eventually scheiterte", "Wirtschaftlichkeit die Erstellung") und findet sie als
eigener Gutachter selbst. Qwen 3.8 ist etwas vollständiger, aber rund 1,6-mal langsamer. Das 80B bleibt der Übersetzer;
ein Wechsel lohnt nach dieser Messung nicht. Gutachter streuen weiter: 3.6 urteilt streng und zum Teil kleinlich
(Einzahl und Mehrzahl), 3.8 schreibt Begründungen in die Felder.

## Strecke 2: Stimme kopieren (ein Sprecher), mittel

1. Referenz gewinnen: 5 bis 7 Sekunden, Schnitt nur in Sprechpausen (Wortzeiten der Transkription), kein zweiter
   Sprecher, keine Musik, gleichmäßiger Pegel; die beste Stelle im ganzen Video; Referenztext genau aus den Wörtern
   dieses Ausschnitts; Probe sprechen und zurückhören.
2. Wiederverwenden: eine gewonnene Stimme hängt am Sprecherprofil der Transkription und wird bei späteren Videos genommen
   statt neu ausgeschnitten.
3. Wie Strecke 1 mit der gewonnenen Stimme (Referenz englisch, gesprochen deutsch).

| Lauf | Fassung | Stimme | Dauer | Länge | Stauchung Mittel/max | Aussprache Mittel/max |
|---|---|---|---|---|---|---|
| K1 A | 0.8.5 | gewonnen (6,1 s, Wertung 0,66), mit Referenztext (ICL) | 16:02 (6,2-fach, KI-Transkripte parallel) | 156,5 s | 1,03 / 1,07 | 14,4 % / 28,1 % |
| K1 B | 0.9.0 | dieselbe, nur Stimmabdruck | 10:25 (4,0-fach) | 156,5 s | 1,19 / 1,31 | 7,1 % / 15,8 % |
| K2 | 0.9.1 | wiedererkannt am Stimmabdruck (die aus K1), Abdruckmodus | 16:02 (3,1-fach) | 307,7 s | 1,01 / 1,09 | 6,8 % / 23,1 % |

Befund Strecke 2: Gewinnen klappt (6,1 s, Schnitt in Pausen, Referenztext genau die Wörter, Abdruck gemerkt). Eine
englische Referenz bringt mit Referenztext ihren Akzent ins Deutsche ("oco system", "opferage"); nur mit dem
Stimmabdruck halbieren sich die Aussprachefehler. Vorgabe "Klonen in fremder Sprache" daher Stimmabdruck (0.9.1); ob
B dem Original ähnlich genug klingt, entscheidet das Ohr des Nutzers (Hörproben A und B). Das Sprechtempo wird ab 0.9.1
je Modus gemessen. KI-Transkripte laufen nur noch, wenn die Vertonung frei ist (Nachvertoner 2.77.4), weil Hören und
Klonen sich die Rechner teilen.

## Strecke 3: mehrere Stimmen, am komplexesten

1. Sprechertrennung der Transkription, je Sprecher eine Stimme (wiederverwendet oder gewonnen), Rollen im Plan.
2. Überlappungen, kurze Einwürfe, Zuordnung über Sprecherprofile.

Runde 1 (K3: "Passenger with suspicious packages questioned in Fort Lauderdale", National Geographic, 3:35, Erzähler,
Beamte, Fluggast): Die Transkription lieferte trotz Sprechertrennung nur einen Sprecher. Ursache: Das Hörmodell liefert
Segmente von rund 14 s, in denen die Sprecher wechseln; jedes Segment ging ganz an den überwiegenden Sprecher, und
ähnliche Mittel wurden zusammengelegt. Abhilfe (Transkription 0.12): Segmente an den Sprecherwechseln der Trennung
teilen (Wortzeiten) und die Abdrücke der geteilten Segmente neu bestimmen. Nebenbefunde: Transkripte ohne Satzzeichen
ergaben einen einzigen Abschnitt (Vertonung fasst jetzt höchstens 25 s zusammen); übersteuerte Quellen brachen das
Gewinnen ab (Referenz wird jetzt leiser); die Ausspracheprüfung wartete je Abschnitt auf das eine Hör-Fach der
Leitstelle (sie hört jetzt das fertige Ergebnis in Stücken bis 5 Minuten).

Runde 2 (18.10.2026, Transkription 0.12): wieder nur ein Sprecher (K3b: 7:22, Aussprache 4,6 %). Ursache gemessen: die
Transkription wandelte auf dem Pi; dessen Ton wich um -45 dB vom Mac ab, und davon kippte die Gruppierung der
Sprechertrennung (zweiter Sprecher 7 statt 31 s, 66 statt 50 Wechsel). Abhilfe: alle Tonarbeit im Tondienst auf dem
Mac (Nutzer: "pi ist nur datenlieferant"; Appkern 0.29, Transkription 0.13, Vertonung 0.12).

Runde 3 (K3c, 18.10.2026, alles über den Tondienst):

| Messgröße | Wert |
|---|---|
| Sprecher | 2 (Trennung auf Mac-gewandeltem Ton: zweiter Sprecher 33,7 s); 28 statt 16 Abschnitte |
| Stimmen | Sprecher 1 gewonnen (beste Stelle im Video), Sprecher 2 am Abdruck wiedererkannt |
| Länge | 215,06 s bei 215,1 s Quelle; Versatz höchstens 0,1 s; Stauchung im Mittel 1,17, höchstens 1,50 |
| Aussprache | im Mittel 18,3 % (viele Abschnitte mit 1 bis 4 Wörtern: ein falsch gehörtes Wort zählt 25 % und mehr) |
| Dauer | 29:30, davon 17 Minuten ein durchgegangener Klon (das Modell erzeugte bis zur Vorgabe von 4096 Token, etwa 340 s Ton, verworfen als Echo); Klangwerk 0.3.1 begrenzt die Länge nach dem Text |

Empfindlichkeit der Trennung (K3, derselbe Ton in kleinen Abwandlungen, Sprechzeit der beiden Sprecher in Sekunden):

| Abwandlung | Wechsel | Sprecher |
|---|---|---|
| Tondienst (16 kHz) | 56 | 137,1 / 33,7 |
| Mac, ffmpeg ohne soxr | 50 | 140,3 / 30,9 |
| Original (m4a) | 50 | 140,3 / 30,9 |
| 0,5 dB lauter / leiser | 56 | 137,6 / 33,1 und 137,1 / 33,6 |
| Rauschen -60 dB | 53 | 138,8 / 31,8 |
| 20 ms später beginnen | 40 | 164,1 / 7,2 |
| auf dem Pi gewandelt | 66 | 147,0 / 7,1 |

Pegel und Rauschen ändern nichts; eine Verschiebung um 20 ms (andere Fensterlage der Trennung) oder ein anderer
Resampler kippt die Gruppierung. Nächster Schritt: die Schwelle der Gruppierung der Trennung und eine Prüfung über
zwei Fensterlagen messen (erst messen, dann entscheiden).

Messung der Gruppierung (18.10.2026, pyannote 3.1 offline mit denselben Abwandlungen; Werkzeuge im Arbeitsordner:
trennschwellen.py, trennturns.py, trennvergleich.py, trennmatrix.py):

- **Schwelle** (0,55 bis 0,80): keine ist stabil; der zweite Sprecher hat je nach Schwelle und Abwandlung 31 oder 7 s,
  ohne Ordnung. Die versetzte Abwandlung scheitert bei jeder Schwelle.
- **Ursache**: der zweite Sprecher zerfällt in zwei Teilgruppen (etwa 17 und 16 s), beide unter der kleinsten
  Gruppengröße von 12; ob sie zusammenfinden oder im ersten Sprecher aufgehen, entscheidet ein kleiner Unterschied im
  Ton. Mit Gruppengröße 8 bleiben die Teilgruppen erhalten (in den Wörtern 94 % richtig, aber drei Sprecher; die
  kleine Gruppe mit 3,5 s klingt laut Stimmabdruck weder wie der eine noch wie der andere, Ähnlichkeit 0,07 und 0,01);
  mit 4 und 6 zerfällt es weiter, das Zusammenlegen per Stimmabdruck (0,60) fügt die Stücke nicht.
- **Gruppierung nur per Stimmabdruck** (Trennung nur als Grenzen): schlechter, meist ein Sprecher (70 bis 86 %).
- **Bekannte Sprecherzahl** (`num_speakers` 2, ohne Zusammenlegen, wie die Transkription es bei Anzahl tut):

| Abwandlung | Anzahl unbekannt (heute) | Anzahl 2 |
|---|---|---|
| Mac | 100 % | 100 % |
| Tondienst | 98 % | 98 % |
| Rauschen -60 dB | 98 % | 98 % |
| 20 ms versetzt | 86 % (ein Sprecher) | 96 % |
| auf dem Pi gewandelt | 86 % (ein Sprecher) | 87 % |

Befund: Über die Gruppierung allein ist die Trennung nicht stabil zu bekommen; die bekannte Sprecherzahl macht sie es
(Pi-Wandlung entfällt seit dem Tondienst). Die Transkription nimmt eine Anzahl schon an (Feld "Anzahl"), die Vertonung
reicht bei Originalstimmen keine weiter. Offen zur Entscheidung: Sprecherzahl beim Vormerken angeben (TubeVault,
Vertonung) oder die Trennung zweimal mit versetzter Fensterlage rechnen und das Ergebnis mit dem größeren Anteil des
kleineren Sprechers nehmen (doppelte Trennzeit, an mehr als einer Aufnahme zu prüfen).

Offen: die Trennung bleibt empfindlich (kleine Abweichungen im Ton kippen die Gruppierung); Messgröße Aussprache nach
Wörtern gewichten statt je Abschnitt; kurze Einwürfe (unter 1,5 s) eher mit dem Nachbarabschnitt desselben Sprechers
zusammenfassen oder bei hoher Stauchung schieben.
