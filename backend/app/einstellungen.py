"""Einstellungen der Vertonung. Kellerwolke, Leitstelle und weitere Konten bringt das Gerüst mit; hier kommen die der
Vertonung dazu. Die Seite Einstellungen der Oberfläche entsteht daraus von selbst."""

from typing import Literal

from pydantic import Field

from appkern.app import Grundeinstellungen

SPRECHEN = {"gruppe": "Sprechen"}
ZEITGENAU = {"gruppe": "Zeitgenau"}
ERGEBNIS = {"gruppe": "Ergebnis"}
STIMMEN = {"gruppe": "Stimmen"}
VERBUND = {"gruppe": "Verbund"}
TECHNIK = {"gruppe": "Technik"}

SPRACHEN = {"de": "Deutsch", "en": "Englisch", "fr": "Französisch", "es": "Spanisch", "it": "Italienisch"}
Sprache = Literal["de", "en", "fr", "es", "it"]
Format = Literal["mp3", "wav", "flac", "ogg"]
FORMATE = {"mp3": "MP3 mono 24 kHz", "wav": "WAV mono 24 kHz", "flac": "FLAC mono 24 kHz", "ogg": "OGG Opus mono 24 kHz"}


class AppEinstellungen(Grundeinstellungen):
    sprache: Sprache = Field("de", title="Sprache", json_schema_extra={**SPRECHEN, "beschriftungen": SPRACHEN},
                             description="In welcher Sprache gesprochen wird; Vorgabe für neue Vertonungen.")
    stimme_vorgabe: str = Field("serena", title="Stimme ab Werk", json_schema_extra=SPRECHEN,
                                description="Feste Stimme des Sprechdienstes für neue Vertonungen und Rollen ohne eigene Stimme.")
    ersatzstimme: str = Field("serena", title="Ersatzstimme", json_schema_extra=SPRECHEN,
                              description="Spricht ein Stück, wenn die gewählte Stimme dreimal scheitert; im Bericht vermerkt. "
                                          "Nie bleibt etwas stumm.")
    dienst_sprechen: str = Field("klangwerk-sprechen", title="Dienst für feste Stimmen", json_schema_extra=SPRECHEN,
                                 description="Spricht mit den festen Stimmen des Katalogs.")
    dienst_klonen: str = Field("klangwerk-klonen", title="Dienst für Klonstimmen", json_schema_extra=SPRECHEN,
                               description="Spricht mit einer Stimme nach ihrer Referenzprobe.")
    dienst_hoeren: str = Field("klangwerk-hoeren", title="Dienst zum Hören", json_schema_extra=SPRECHEN,
                               description="Hört den Referenztext einer Stimme heraus, wenn keiner angegeben ist, und "
                                           "prüft die Aussprache.")
    aussprache_pruefen: bool = Field(True, title="Aussprache prüfen", json_schema_extra=SPRECHEN,
                                     description="Jeder neu gesprochene Abschnitt wird zurückgehört und Wort für Wort mit "
                                                 "dem Text verglichen; Abweichungen stehen im Bericht. Kostet etwas Zeit.")

    komfort: float = Field(1.15, ge=1.0, le=1.5, title="Stauchen unauffällig bis",
                           json_schema_extra={**ZEITGENAU, "schritt": 0.05, "einheit": "fach"},
                           description="Bis zu diesem Faktor klingt schnelleres Sprechen noch natürlich; mehr wird im Bericht "
                                       "als Hinweis vermerkt.")
    hoechstens: float = Field(1.5, ge=1.0, le=2.0, title="Stauchen höchstens",
                              json_schema_extra={**ZEITGENAU, "schritt": 0.05, "einheit": "fach"},
                              description="Schneller wird nie gesprochen; was dann noch fehlt, wird nach hinten geschoben. "
                                          "Gekürzt oder abgeschnitten wird nie.")

    sprechtempo: float = Field(11.5, ge=5.0, le=25.0, title="Sprechtempo ab Werk",
                               json_schema_extra={**ZEITGENAU, "schritt": 0.5, "einheit": "Zeichen je Sekunde"},
                               description="Damit rechnet die Übersetzung, wie viel Text in die Zeit eines Abschnitts "
                                           "passt, bis eine Stimme genug gesprochen hat; danach gilt ihr gemessenes Tempo.")

    format: Format = Field("mp3", title="Format beim Vorlesen", json_schema_extra={**ERGEBNIS, "beschriftungen": FORMATE},
                           description="Für Vorlesen und Dialoge. Zeitgenau entsteht immer eine WAV in Rate und Kanälen der "
                                       "Quellaufnahme.")
    mp3_bitrate: Literal["96k", "128k", "160k"] = Field("128k", title="Bitrate MP3", json_schema_extra=ERGEBNIS,
                                                        description="Für Sprache in Mono genügen 128 kbit/s.")

    private_stimmen_fuer: list[str] = Field(["rufzeichen", "fundus", "bombel", "zusage", "nachvertoner"], title="Private Stimmen für",
                                            json_schema_extra=STIMMEN,
                                            description="Kennungen der Apps (Zugänge der Kellerwolke), die private Stimmen "
                                                        "nutzen dürfen. Alle anderen bekommen nur fremde und Katalogstimmen; "
                                                        "Medienpool nie.")
    probe_min_s: float = Field(6.0, ge=3.0, le=15.0, title="Probe mindestens", json_schema_extra={**STIMMEN, "einheit": "s"},
                               description="Kürzere Stellen ergeben keine Klonstimme.")

    transkription_app: str = Field("Transkription", title="Transkription", json_schema_extra=VERBUND,
                                   description="Name der Transkription unter den Zugängen der Kellerwolke. Liegt neben einer "
                                               "Aufnahme kein Transkript, gibt die Vertonung das Transkribieren dorthin weiter.")

    zwischenspeicher_gb: int = Field(5, ge=1, le=100, title="Speicher für gesprochene Abschnitte",
                                     json_schema_extra={**TECHNIK, "einheit": "GB"},
                                     description="Gesprochene Abschnitte bleiben, damit Nachbessern nur Geändertes spricht. "
                                                 "Wird es mehr, gehen die am längsten nicht genutzten zuerst.")
    ffmpeg_ordner: str = Field("", title="Ordner von ffmpeg", json_schema_extra=TECHNIK,
                               description="ffmpeg wandelt, staucht und kodiert. Ohne Eintrag wird es im Suchpfad gesucht.")
