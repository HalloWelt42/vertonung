<script lang="ts">
  // Die Bereiche der Vertonung in der gemeinsamen Schale (Kopf, Navigation, Aufträge, Protokoll, Einstellungen).
  // Aus der Kellerwolke geöffnet: "Vorlesen" an einem Text, "Neu sprechen" an einer Aufnahme mit Transkript (beides
  // erst anlegen, dann sprechen), "In Vertonung öffnen" führt zum Plan neben der Datei.
  import { Schale, type Anfrage, type Bereich } from "appkern-oberflaeche";
  import * as api from "./lib/api";
  import Stimmen from "./seiten/Stimmen.svelte";
  import Vertonen from "./seiten/Vertonen.svelte";

  const bereiche: Bereich[] = [
    { schluessel: "vertonen", titel: "Vertonen", symbol: "fa-wave-square", seite: Vertonen, reiter: true },
    { schluessel: "stimmen", titel: "Stimmen", symbol: "fa-user-group", seite: Stimmen, reiter: true },
  ];

  async function oeffnen(a: Anfrage): Promise<string> {
    if (a.aktion === "vorlesen") return `vertonen/neu/vorlesen/anfrage/${a.id}`;
    if (a.aktion === "neu_sprechen") return `vertonen/neu/zeitgenau/anfrage/${a.id}`;
    const plan = await api.planZurDatei(a.knoten_id, a.id);
    return plan ? `vertonen/${plan}/anfrage/${a.id}` : `vertonen/neu/vorlesen/anfrage/${a.id}`;
  }
</script>

<Schale {bereiche} fassung={__APP_FASSUNG__} {oeffnen} />
