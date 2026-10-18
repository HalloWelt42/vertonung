"""Weitergabe an die Transkription: Sprache, bei Originalstimmen Sprechertrennung und die bekannte Sprecherzahl."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.dienst import DienstEingabe, weitergabe_optionen


def test_optionen_der_weitergabe():
    e = DienstEingabe(haupt_id=uuid4(), name="x", ausgangssprache="en")
    assert weitergabe_optionen(e) == {"sprache": "en"}
    e = DienstEingabe(haupt_id=uuid4(), name="x", stimmen="original")
    assert weitergabe_optionen(e) == {"sprache": "auto", "sprecher": "trennung"}
    e = DienstEingabe(haupt_id=uuid4(), name="x", stimmen="original", sprecher_anzahl=2)
    assert weitergabe_optionen(e) == {"sprache": "auto", "sprecher": "trennung", "anzahl": 2}
    assert "anzahl" not in weitergabe_optionen(DienstEingabe(haupt_id=uuid4(), name="x", sprecher_anzahl=2)), "nur bei Originalstimmen"
    with pytest.raises(ValidationError):
        DienstEingabe(haupt_id=uuid4(), name="x", sprecher_anzahl=0)
