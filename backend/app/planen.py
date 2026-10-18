"""Pläne anlegen (sofort, ohne Auftrag): Vorlesen aus Text, Dialog aus Zeilen `Name: Satz`, zeitgenau aus den
Segmenten eines Transkripts oder aus Untertiteln. Zeitgenau werden Segmente zu Sätzen zusammengefasst: neuer Abschnitt
bei einer Pause über 1,2 s, am Satzende oder beim Sprecherwechsel; ein Stück unter 20 Zeichen hängt am Vorgänger, wenn
derselbe Sprecher spricht und die Pause höchstens 2 s ist."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .modell.plan import Abschnitt, Plan, Quelle, Rolle, StimmWahl, Ziel
from .saetze import ELLIPSE, SCHLUSSZEICHEN, saetze

__all__ = ["Segment", "aus_dialog", "aus_segmenten", "aus_text", "saetze", "segmente_aus_transkript",
           "segmente_aus_untertiteln", "zusammenfassen"]

PAUSE_SATZ_S = 0.35
PAUSE_ABSATZ_S = 0.8
PAUSE_DIALOG_S = 0.45
NEU_NACH_PAUSE_S = 1.2
KURZ_ZEICHEN = 20
KURZ_PAUSE_S = 2.0
_SATZENDE = re.compile("[.!?" + ELLIPSE + "][" + re.escape(SCHLUSSZEICHEN) + "]*$")
_DIALOG = re.compile(r"^\s*([^:\n]{1,40}?)\s*:\s*(.+)$")


@dataclass
class Segment:
    start: float
    ende: float
    text: str
    sprecher: str | None = None
    teile: list[str] = field(default_factory=list)


def _kennungen(namen: list[str]) -> dict[str, str]:
    return {n: f"r{i + 1}" for i, n in enumerate(namen)}


def aus_text(name: str, text: str, stimme: StimmWahl, *, sprache: str = "de", ziel: Ziel | None = None,
             rollenname: str = "Sprecher") -> Plan:
    abschnitte = [Abschnitt(nr=i + 1, rolle="r1", text=s.text, pause_danach_s=PAUSE_ABSATZ_S if s.absatz_ende else PAUSE_SATZ_S)
                  for i, s in enumerate(saetze(text))]
    if not abschnitte:
        raise ValueError("Kein Text zum Vorlesen")
    return Plan(art="vorlesen", name=name, sprache=sprache, rollen=[Rolle(kennung="r1", name=rollenname, stimme=stimme)],
                abschnitte=abschnitte, ziel=ziel or Ziel())


def aus_dialog(name: str, text: str, stimmen: dict[str, StimmWahl], vorgabe: StimmWahl, *, sprache: str = "de",
               ziel: Ziel | None = None) -> Plan:
    """Jede Zeile `Name: Satz` ein Abschnitt; eine Zeile ohne Namen setzt die vorige fort. Rollen in der Reihenfolge
    ihres ersten Auftritts; ohne eigene Stimme die Vorgabe."""
    zeilen: list[tuple[str, str]] = []
    for zeile in text.replace("\r\n", "\n").split("\n"):
        if not zeile.strip():
            continue
        if (m := _DIALOG.match(zeile)) is not None:
            zeilen.append((m.group(1).strip(), m.group(2).strip()))
        elif zeilen:
            zeilen[-1] = (zeilen[-1][0], f"{zeilen[-1][1]} {zeile.strip()}")
        else:
            raise ValueError("Die erste Zeile braucht einen Namen: Name: Satz")
    if not zeilen:
        raise ValueError("Kein Dialog: Zeilen in der Form Name: Satz")
    namen = list(dict.fromkeys(n for n, _ in zeilen))
    kennung = _kennungen(namen)
    rollen = [Rolle(kennung=kennung[n], name=n, stimme=stimmen.get(n, vorgabe)) for n in namen]
    abschnitte = [Abschnitt(nr=i + 1, rolle=kennung[n], text=t, pause_danach_s=PAUSE_DIALOG_S) for i, (n, t) in enumerate(zeilen)]
    return Plan(art="dialog", name=name, sprache=sprache, rollen=rollen, abschnitte=abschnitte, ziel=ziel or Ziel())


def zusammenfassen(segmente: list[Segment]) -> list[Segment]:
    gruppen: list[Segment] = []
    for s in sorted((s for s in segmente if s.text.strip()), key=lambda s: s.start):
        g = gruppen[-1] if gruppen else None
        if (g is not None and s.sprecher == g.sprecher and s.start - g.ende <= NEU_NACH_PAUSE_S
                and not _SATZENDE.search(g.text)):
            g.text = f"{g.text} {s.text.strip()}"
            g.ende = max(g.ende, s.ende)
        else:
            gruppen.append(Segment(start=s.start, ende=s.ende, text=s.text.strip(), sprecher=s.sprecher))
    aus: list[Segment] = []
    for g in gruppen:
        v = aus[-1] if aus else None
        if v is not None and len(g.text) < KURZ_ZEICHEN and g.sprecher == v.sprecher and g.start - v.ende <= KURZ_PAUSE_S:
            v.text = f"{v.text} {g.text}"
            v.ende = max(v.ende, g.ende)
        else:
            aus.append(g)
    return aus


def aus_segmenten(name: str, segmente: list[Segment], stimmen: dict[str, StimmWahl], vorgabe: StimmWahl, *,
                  quelle: Quelle | None, quelle_dauer_s: float | None, sprache: str = "de", ziel: Ziel | None = None,
                  ohne_sprecher: str = "Sprecher", ausgangssprache: str | None = None) -> Plan:
    """`ausgangssprache`: Sprache der Segmente; weicht sie von `sprache` ab, wird übersetzt (Original je Abschnitt)."""
    uebersetzen = bool(ausgangssprache) and ausgangssprache != sprache
    gruppen = zusammenfassen(segmente)
    if not gruppen:
        raise ValueError("Keine Segmente mit Text")
    namen = list(dict.fromkeys(g.sprecher or ohne_sprecher for g in gruppen))
    kennung = _kennungen(namen)
    rollen = [Rolle(kennung=kennung[n], name=n, stimme=stimmen.get(n, vorgabe)) for n in namen]
    abschnitte = [Abschnitt(nr=i + 1, rolle=kennung[g.sprecher or ohne_sprecher], text=g.text, start=round(g.start, 3),
                            ende=round(max(g.ende, g.start), 3), pause_danach_s=0, original=g.text if uebersetzen else None)
                  for i, g in enumerate(gruppen)]
    return Plan(art="zeitgenau", name=name, sprache=sprache, rollen=rollen, abschnitte=abschnitte, quelle=quelle,
                quelle_dauer_s=quelle_dauer_s, ziel=ziel or Ziel(format="wie_quelle"),
                ausgangssprache=ausgangssprache if uebersetzen else None)


def segmente_aus_transkript(transkript: dict) -> list[Segment]:
    """Segmente einer Transkriptdatei (`transkript/1`) mit den Namen ihrer Sprecher."""
    namen = {s["kennung"]: s.get("name") or s["kennung"] for s in transkript.get("sprecher") or []}
    return [Segment(start=float(s["start"]), ende=float(s["ende"]), text=s.get("text") or "",
                    sprecher=namen.get(s.get("sprecher"), s.get("sprecher")) if s.get("sprecher") else None)
            for s in transkript.get("segmente") or []]


_ZEIT = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})")


def _sekunden(text: str) -> float:
    m = _ZEIT.search(text)
    if m is None:
        raise ValueError(f"Zeit nicht lesbar: {text}")
    h, mi, s, ms = m.groups()
    return int(h or 0) * 3600 + int(mi) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def segmente_aus_untertiteln(text: str) -> list[Segment]:
    """SRT und WebVTT: je Block eine Zeitzeile `start --> ende` und Text; Auszeichnungen wie <i> fallen weg."""
    aus: list[Segment] = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()):
        zeilen = [z for z in block.split("\n") if z.strip()]
        zeit = next((i for i, z in enumerate(zeilen) if "-->" in z), None)
        if zeit is None:
            continue
        links, rechts = zeilen[zeit].split("-->", 1)
        inhalt = " ".join(re.sub(r"<[^>]+>", "", z).strip() for z in zeilen[zeit + 1:]).strip()
        if inhalt:
            aus.append(Segment(start=_sekunden(links), ende=_sekunden(rechts.split()[0]), text=inhalt))
    return aus
