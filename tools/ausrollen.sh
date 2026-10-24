#!/usr/bin/env bash
# Ausrollen auf den Pi (vom Mac aus) nach deploy/ausrollen.toml. Ablauf und Prüfungen stehen für alle Apps gleich im
# Appkern (appkern.werkzeuge.ausrollen): nur gepushte Stände, Tests grün, Appkern gleich in Oberfläche und Backend,
# mit Ton das ffmpeg des Pi, Zertifikat, Datenbank sichern, bauen, Vorschaltdienst neu starten, Fassungen, HTTP/2 und
# Symbole.
set -euo pipefail
# >>> handbuch: vorher Seite, Einrichtungsskript, Probelauf und Bau des Handbuchs (eingesetzt von "handbuch einbinden")
handbuch_befehl="$(command -v handbuch || true)"
[ -n "$handbuch_befehl" ] || handbuch_befehl="$HOME/.local/bin/handbuch"
if [ ! -x "$handbuch_befehl" ]; then
  echo "Abbruch: das Werkzeug handbuch fehlt (Handbuch, Grundlage Mac)" >&2
  exit 1
fi
"$handbuch_befehl" freigabe "$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)" || {
  echo "Abbruch: das Handbuch ist nicht in Ordnung, nichts ausgerollt" >&2
  exit 1
}
# <<< handbuch
cd "$(dirname "${BASH_SOURCE[0]}")/.."
# Rechner, Ordner, Adresse, Namen und Leitstelle aus der privaten Wahrheit (handbuch ziel)
ergaenzung="$(mktemp)"
trap 'rm -f "$ergaenzung"' EXIT
"$handbuch_befehl" ziel "$(pwd)" --toml > "$ergaenzung" || { echo "Abbruch: kein Ziel in der privaten Wahrheit (handbuch ziel)" >&2; exit 1; }
backend/.venv/bin/python -m appkern.werkzeuge ausrollen --ergaenzung "$ergaenzung" "$@"
