"""Schnittstelle der Vertonung unter /api/v1. Alles hinter der Anmeldung (Kellerwolke-Konto oder App-Schlüssel einer
anderen App); Inhalte für `<audio>` unter /api/v1/inhalt auch mit dem Inhalts-Cookie."""

from fastapi import FastAPI

from appkern.app import fehler_behandeln

from ..ablage.plaene import Unlesbar
from ..ablage.stimmen import KeineKellerwolke, ProbeZuKurz
from ..sprechen import KeineLeitstelle
from ..teile import KeinRechtAufStimme, Teile
from . import dienst, inhalt, plaene, sprechen, stimmen


def einbinden(app: FastAPI, teile: Teile) -> None:
    fehler_behandeln(app, {KeineKellerwolke: 503, KeineLeitstelle: 503, Unlesbar: 422, ProbeZuKurz: 422,
                           KeinRechtAufStimme: 403})
    for modul in (stimmen, plaene, sprechen, inhalt, dienst):
        app.include_router(modul.router(teile))
