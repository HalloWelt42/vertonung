<script lang="ts">
  // Wahl einer Stimme (fremd, privat, Katalog) für Vorlesen, eine Rolle oder sofortiges Sprechen.
  import { Auswahl } from "appkern-oberflaeche";
  import { onMount } from "svelte";
  import { alsWahl, schluessel, stimmenLaden, stimmenListe, stimmOptionen } from "../lib/stimmen.svelte";
  import type { StimmWahl } from "../lib/typen";

  let { wahl = $bindable(), klein = false, onwahl }: { wahl: StimmWahl; klein?: boolean; onwahl?: (w: StimmWahl) => void } = $props();
  const wert = $derived(schluessel(wahl));

  onMount(() => {
    if (!stimmenListe.geladen) void stimmenLaden();
  });
</script>

<Auswahl wert={wert} optionen={stimmOptionen()} {klein} titel="Stimme"
         onwahl={(s) => { wahl = alsWahl(s); onwahl?.(wahl); }} />
