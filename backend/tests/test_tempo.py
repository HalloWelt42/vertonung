"""Sprechtempo: bis genug gesprochen ist, gilt die Vorgabe; danach die Messung je Stimme und Sprache, ältere Messungen
verblassen. Gemessen wird nur, was ein Lauf neu gesprochen hat, und zwar bei Tempo 1."""

from appkern.datenbank import Datenbank

from app.arten import frisch_gesprochen
from app.modell.plan import StimmWahl
from app.planen import Segment, aus_segmenten
from app.tempo import GEDAECHTNIS_S, Probe, Sprechtempo


async def test_messung_ersetzt_die_vorgabe_und_verblasst(tmp_path):
    db = Datenbank(tmp_path / "t.sqlite")
    await db.oeffnen()
    try:
        t = Sprechtempo(db, lambda: 11.5)
        await t.einrichten()
        assert await t.zeichen_je_s("katalog:serena", "de") == 11.5
        await t.messen([Probe("katalog:serena", "de", 100, 10.0)])
        assert await t.zeichen_je_s("katalog:serena", "de") == 11.5          # 10 s reichen noch nicht
        await t.messen([Probe("katalog:serena", "de", 200, 20.0), Probe("katalog:serena", "en", 300, 20.0)])
        assert await t.zeichen_je_s("katalog:serena", "de") == 10.0
        assert await t.zeichen_je_s("katalog:serena", "en") == 15.0          # je Sprache getrennt
        await t.messen([Probe("katalog:serena", "de", int(GEDAECHTNIS_S * 14), GEDAECHTNIS_S)])
        # das Neue zählt fast ganz, das Alte (10 je Sekunde) verblasst
        assert 13.8 < await t.zeichen_je_s("katalog:serena", "de") < 14.0
    finally:
        await db.schliessen()


def test_nur_frisch_gesprochenes_bei_tempo_eins():
    seg = [Segment(0.0, 2.0, "Hallo zusammen.", "A"), Segment(2.5, 5.0, "Willkommen.", "B")]
    vorher = aus_segmenten("Probe", seg, {}, StimmWahl(art="katalog", name="serena"), quelle=None, quelle_dauer_s=6.0,
                           sprache="de")
    vorher.rolle(vorher.abschnitte[1].rolle).tempo = 1.2
    vorher.abschnitte[0].gesprochen_als = "alt"
    gelaufen = vorher.model_copy(deep=True)
    for a in gelaufen.abschnitte:
        a.gesprochen_als, a.dauer_s = f"neu{a.nr}", 1.0
    gelaufen.abschnitte[0].gesprochen_als = "alt"                               # aus dem Zwischenspeicher
    assert frisch_gesprochen(vorher, gelaufen) == [Probe("katalog:serena", "de", len("Willkommen."), 1.2)]
