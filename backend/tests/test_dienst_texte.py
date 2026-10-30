"""Texte eines Dienstauftrags: das Transkript, das die Vertonung transkribieren ließ, gibt es, sobald es neben der
Aufnahme liegt (während der Auftrag läuft und auch nachdem er scheiterte), damit der Sender es sofort weitergeben kann;
der Text der neuen Tonspur erst, wenn der Auftrag fertig ist. Hat der Sender den Text selbst mitgeschickt, kommt kein
Transkript zurück."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from appkern.auftraege import Auftrag

from app.dienst import texte
from app.dienstablage import Ablage

TRANSKRIPT = {"format": "transkript/1", "sprache": "en", "sprecher": [{"kennung": "s1", "name": "Host"}],
              "segmente": [{"start": 0.0, "ende": 1.5, "sprecher": "s1", "text": " Good evening. "},
                           {"start": 2.0, "ende": 2.5, "sprecher": "s1", "text": "  "}]}


class Zugang:
    def __init__(self, mit_transkript: bool) -> None:
        self.mit_transkript = mit_transkript

    async def begleiter(self, knoten_id):
        return [SimpleNamespace(id="t1", rolle="transkript")] if self.mit_transkript else []

    async def lesen_ganz(self, knoten_id) -> bytes:
        return json.dumps(TRANSKRIPT).encode("utf-8")


class Plaene:
    async def lesen(self, plan_id):
        raise AssertionError("Der Plan wird erst gelesen, wenn der Auftrag fertig ist")


def teile(mit_transkript: bool = True):
    zugang = Zugang(mit_transkript)
    return SimpleNamespace(zugang=lambda: zugang, plaene=Plaene())


def ablage(weitergegeben: bool) -> Ablage:
    return Ablage(auftrag_id="a1", haupt_id=uuid4(), app="Nachvertoner", behalten=False, plan_id=uuid4(),
                  frist_bis=datetime.now(UTC), transkription_anfrage="anfrage-1" if weitergegeben else None)


def auftrag(zustand: str) -> Auftrag:
    return Auftrag(id="a1", art="dienst_vertonen", titel="Probe", zustand=zustand, eingabe={"ausgangssprache": None},
                   erstellt_am=datetime.now(UTC))


async def test_transkript_schon_waehrend_des_laufs_und_nach_fehler():
    for zustand in ("laeuft", "fehler", "abgebrochen"):
        t = await texte(teile(), ablage(weitergegeben=True), auftrag(zustand))
        assert t.transkript is not None and t.transkript.sprache == "en", zustand
        assert [(s.text, s.sprecher) for s in t.transkript.segmente] == [("Good evening.", "Host")]
        assert t.uebersetzung is None                        # Zeiten der neuen Tonspur stehen erst am Ende fest


async def test_noch_kein_transkript_heisst_leer():
    t = await texte(teile(mit_transkript=False), ablage(weitergegeben=True), auftrag("laeuft"))
    assert t.transkript is None and t.uebersetzung is None


async def test_mitgeschickter_text_kommt_nicht_zurueck():
    t = await texte(teile(), ablage(weitergegeben=False), auftrag("laeuft"))
    assert t.transkript is None
