"""Arten von Aufträgen der Vertonung.

vertonen    Einen Plan mit dem Werk ausführen: erst übersetzen, was sich im Original geändert hat (das große Sprachmodell
            über die Leitstelle, nach jedem Fenster gemerkt), dann sprechen (nur Geändertes), fügen, einmal ins Zielformat schreiben, das
            Ergebnis neben die Hauptdatei legen, den Plan mit Prüfsummen und Bericht zurückschreiben. Wurde der Plan
            während des Laufs geändert, bleiben die Änderungen; übernommen wird nur, was zu ihnen passt.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field

from appkern.anfragen import Angebot
from appkern.auftraege import Art, Kontext, Phase
from appkern.kellerwolke import Aktion, Kellerwolke, StandVeraltet
from appkern.ton import Tonformat

from .modell.plan import Ergebnis, Plan
from .sprechen import KeineLeitstelle
from .teile import Teile
from .dienst import DienstEingabe, dienst_ausfuehren
from . import aussprache
from .tempo import Probe
from .uebersetzen import knapper_fassen, plan_uebersetzen, zu_lang
from .werk.werk import ziel_format

KOPF_BYTES = 4 * 1024 * 1024      # zum Messen des Quellformats reicht meist der Anfang der Datei


class VertonenEingabe(BaseModel):
    plan_id: UUID
    anfrage_id: UUID | None = Field(None, description="Anfrage der Kellerwolke, wenn die Hauptdatei außerhalb der App liegt")
    von: str | None = None


async def quelle_messen(teile: Teile, kw: Kellerwolke, haupt_id: UUID, ordner: Path) -> tuple[Tonformat, float]:
    """Rate, Kanäle und Dauer der Aufnahme: erst aus dem Anfang der Datei, sonst aus der ganzen."""
    ton = teile.ton_jetzt
    knoten = await kw.knoten(haupt_id)
    kopf = ordner / f"quelle{Path(knoten.name).suffix.lower()}"
    with open(kopf, "wb") as datei:
        async for stueck in kw.lesen(haupt_id, start=0, ende=KOPF_BYTES - 1):
            datei.write(stueck)
    try:
        e = await ton.eigenschaften(kopf)
        if not (e.rate and e.kanaele) or (knoten.groesse or 0) > KOPF_BYTES and e.dauer_s <= 0:
            raise ValueError("Kopf reicht nicht")
    except Exception:  # noqa: BLE001 - etwa MP4 mit dem Inhaltsverzeichnis am Ende: dann die ganze Datei
        await kw.herunterladen(haupt_id, kopf)
        e = await ton.eigenschaften(kopf)
    dauer = knoten.felder.get("dauer_s") or e.dauer_s
    return Tonformat(rate=e.rate or 48000, kanaele=min(e.kanaele or 2, 8), kodierung="pcm_s16le"), float(dauer)


def frisch_gesprochen(vorher: Plan, gelaufen: Plan) -> list[Probe]:
    """Messproben des Sprechtempos aus den Abschnitten, die dieser Lauf neu gesprochen hat (Dauer bei Tempo 1)."""
    alt = {a.nr: a.gesprochen_als for a in vorher.abschnitte}
    aus = []
    for a in gelaufen.abschnitte:
        if a.dauer_s and a.gesprochen_als and a.gesprochen_als != alt.get(a.nr):
            rolle = gelaufen.rolle(a.rolle)
            aus.append(Probe(rolle.stimme.schluessel, gelaufen.sprache, len(a.text), a.dauer_s * rolle.tempo))
    return aus


def uebertragen(ziel: Plan, gelaufen: Plan) -> Plan:
    """Ergebnisse eines Laufs in einen inzwischen geänderten Plan: je Abschnitt nur, wenn Nummer und Prüfsumme passen."""
    fertig = {a.nr: a for a in gelaufen.abschnitte}
    for a in ziel.abschnitte:
        g = fertig.get(a.nr)
        if g is not None and g.gesprochen_als == a.soll(ziel.rolle(a.rolle), ziel.sprache):
            a.gesprochen_als, a.dauer_s, a.bericht = g.gesprochen_als, g.dauer_s, g.bericht
    ziel.ergebnis, ziel.quelle_dauer_s = gelaufen.ergebnis, gelaufen.quelle_dauer_s or ziel.quelle_dauer_s
    return ziel


async def plan_ausfuehren(teile: Teile, k: Kontext, plan_id: UUID, anfrage_id: UUID | None) -> dict:
    """Einen Plan ausführen (Auftrag Vertonen und Dienst): übersetzen, sprechen, fügen, ablegen, Plan zurückschreiben."""
    plaene = teile.plaene_fuer(anfrage_id)
    kw = teile.zugang(anfrage_id)
    einst = teile.einstellungen
    ordner = teile.arbeit / k.auftrag_id
    ordner.mkdir(parents=True, exist_ok=True)
    try:
        await k.fortschritt(0.0, "Vorbereiten", phase="vorbereiten")
        plan, knoten = await plaene.lesen(plan_id)
        haupt_id = knoten.haupt_id or (plan.quelle.knoten_id if plan.quelle else None)
        if haupt_id is None:
            raise ValueError("Der Plan gehört zu keiner Datei")
        ls = teile.geruest.leitstelle
        if plan.zu_uebersetzen():
            if ls is None:
                raise KeineLeitstelle("Zum Übersetzen braucht die Vertonung die Leitstelle")

            async def merken(p: Plan) -> None:
                nonlocal knoten
                p.geaendert_am = datetime.now(UTC)
                knoten = await plaene.schreiben(plan_id, p, knoten.etag or "")

            async def uebersetzt(anteil: float, text: str) -> None:
                await k.fortschritt(0.02 + 0.2 * anteil, text, phase="uebersetzen")

            je_s = {r.kennung: await teile.tempo.zeichen_je_s(r.stimme.schluessel, plan.sprache) * r.tempo for r in plan.rollen}
            neu = await plan_uebersetzen(plan, ls, zeichen_je_s=je_s, komfort=einst.komfort, hoechstens=einst.hoechstens,
                                         fortschritt=uebersetzt, pruefen=k.pruefen, merken=merken)
            await k.merken(uebersetzt=sorted(set(k.zwischenstand.get("uebersetzt", [])) | set(neu)))
        quelle: Tonformat | None = None
        if plan.art == "zeitgenau":
            quelle, dauer = await quelle_messen(teile, kw, haupt_id, ordner)
            plan.quelle_dauer_s = plan.quelle_dauer_s or dauer
        format, endung = ziel_format(plan.art, plan.ziel.format, einst.mp3_bitrate, quelle)
        ziel = ordner / f"ergebnis{endung}"

        async def sprechen(p: Plan, von: float, bis: float) -> Plan:
            async def fortschritt(anteil: float, text: str) -> None:
                await k.fortschritt(von + (bis - von) * anteil, text, phase="sprechen")

            g = await teile.werk().ausfuehren(p, stimme=teile.gewaehlt, speicher=teile.speicher(plan_id), ziel=ziel,
                                              format=format, fortschritt=fortschritt, pruefen=k.pruefen,
                                              komfort=einst.komfort, hoechstens=einst.hoechstens)
            await teile.tempo.messen(frisch_gesprochen(p, g))
            return g

        gelaufen = await sprechen(plan, 0.22, 0.86)
        # Übersetztes, das trotz stärkstem Stauchen nicht in seine Zeit passt: einmal knapper fassen, neu sprechen
        lang = zu_lang(gelaufen, set(k.zwischenstand.get("uebersetzt", [])), einst.hoechstens) if ls else []
        if lang:
            await k.fortschritt(0.86, f"Knapper fassen: {len(lang)} Abschnitte passen nicht in ihre Zeit", phase="sprechen")
            knapper = await knapper_fassen(ls, lang, gelaufen.ausgangssprache or "en", gelaufen.sprache,
                                           titel=f"Vertonung: {gelaufen.name} knapper fassen")
            for a in gelaufen.abschnitte:
                if a.nr in knapper:
                    a.text = knapper[a.nr]
            if knapper:
                gelaufen = await sprechen(gelaufen, 0.88, 0.91)
        if einst.aussprache_pruefen and ls:
            await k.fortschritt(0.91, "Aussprache prüfen", phase="sprechen")
            await aussprache.pruefen(plan, gelaufen, teile.speicher(plan_id), ordner / "aussprache", teile.ton_jetzt,
                                     teile.hoeren_text)
        await k.fortschritt(0.92, "Ablegen", phase="ablegen")
        erg = await plaene.ergebnis_ablegen(haupt_id, ziel)
        dauer_s = round(await teile.ton_jetzt.dauer(ziel), 2)
        welle = await teile.ton_jetzt.wellenform(ziel, 400)
        gelaufen.ergebnis = Ergebnis(knoten_id=erg.id, pfad=erg.pfad, dauer_s=dauer_s, erstellt_am=datetime.now(UTC),
                                     wellenform=welle)
        gelaufen.geaendert_am = datetime.now(UTC)
        for _ in range(3):
            try:
                neu_knoten = await plaene.schreiben(plan_id, gelaufen, knoten.etag or "")
                break
            except StandVeraltet:
                aktuell, knoten = await plaene.lesen(plan_id)      # inzwischen geändert: Änderungen behalten
                gelaufen = uebertragen(aktuell, gelaufen)
        else:
            raise StandVeraltet("Der Plan ändert sich laufend; das Ergebnis liegt neben der Datei")
        haupt = await kw.knoten(haupt_id)
        await teile.verzeichnis.eintragen(gelaufen, neu_knoten.id, haupt_id, haupt.pfad,
                                          await teile.stimmen_namen([r.stimme for r in gelaufen.rollen]), anfrage_id)
        return {"ergebnis": str(erg.id), "pfad": erg.pfad, "dauer_s": dauer_s, "abschnitte": len(gelaufen.abschnitte),
                "ersatz": sum(1 for a in gelaufen.abschnitte if a.bericht and a.bericht.ersatz),
                "sprache": gelaufen.sprache, "ausgangssprache": gelaufen.ausgangssprache}
    finally:
        shutil.rmtree(ordner, ignore_errors=True)



def arten(teile: Teile) -> list[Art]:
    async def vertonen(k: Kontext) -> dict:
        e: VertonenEingabe = k.eingabe
        return await plan_ausfuehren(teile, k, e.plan_id, e.anfrage_id)

    async def dienst_vertonen(k: Kontext) -> dict:
        return await dienst_ausfuehren(teile, k)

    phasen = [Phase(schluessel="vorbereiten", titel="Vorbereiten", symbol="box-open"),
              Phase(schluessel="uebersetzen", titel="Übersetzen", symbol="language"),
              Phase(schluessel="sprechen", titel="Sprechen", symbol="microphone"),
              Phase(schluessel="ablegen", titel="Ablegen", symbol="cloud-arrow-up")]
    return [
        Art("dienst_vertonen", "Vertonen für eine App", dienst_vertonen, eingabe=DienstEingabe, fortsetzbar=True,
            nach_neustart="fortsetzen", phasen=phasen),
        Art("vertonen", "Vertonen", vertonen, eingabe=VertonenEingabe, fortsetzbar=True, nach_neustart="fortsetzen",
            phasen=phasen),
    ]


# Was die App im Dateimenü der Kellerwolke anbietet (und in der eigenen Dateiwahl). Alle öffnen die Oberfläche: die
# Stimmen wählt der Mensch, bevor gesprochen wird (Vorschau vor Anwenden).
MEDIEN = ("audio/*", "video/*")
TEXTE = ("text/plain", "text/markdown")
ANGEBOTE = [
    Angebot(Aktion(kennung="oeffnen", titel="In Vertonung öffnen", symbol="fa-up-right-from-square", typen=MEDIEN + TEXTE,
                   art="oeffnen", rolle="vertonung")),
    Angebot(Aktion(kennung="vorlesen", titel="Vorlesen", titel_erneut="Neu vorlesen", symbol="fa-book-open-reader",
                   typen=TEXTE, art="oeffnen", rolle="sprache")),
    Angebot(Aktion(kennung="neu_sprechen", titel="Neu sprechen", titel_erneut="Erneut neu sprechen", symbol="fa-clock",
                   typen=MEDIEN, art="oeffnen", rolle="sprache")),
]
