<script lang="ts">
  // Stimmen: Reiter Privat, Fremd, Katalog; rechts Probe und Angaben der gewählten (bekannt als, Bereich, Sprache,
  // Referenztext, Herkunft). Neu aus einer hochgeladenen Probe oder mit dem Rekorder aufgenommen. Private Stimmen
  // gehören Menschen aus dem Umfeld: nur für erlaubte Apps, nie für Öffentliches. Entwurf: mockups/vertonung.html (5).
  import { onMount } from "svelte";
  import { aufnahme, aufnehmen, Auswahl, geraet, Leiste, leisteOeffnen, Rekorder, Rueckfrage, type NachDerAufnahme } from "appkern-oberflaeche";
  import * as api from "../lib/api";
  import { stimmenLaden } from "../lib/stimmen.svelte";
  import type { Bereich, Stimme, StimmAngaben, StimmBereich } from "../lib/typen";

  let bereich = $state<StimmBereich>("fremd");
  let liste = $state<Stimme[]>([]);
  let suche = $state("");
  let fehler = $state("");
  let meldung = $state("");
  let gewaehltId = $state<string | null>(null);
  let angaben = $state<StimmAngaben | null>(null);
  let bekannt = $state("");
  let loeschFrage = $state(false);
  let spielt = $state<string | null>(null);
  let datei = $state<HTMLInputElement>();
  const BEREICHE: { wert: Bereich; titel: string }[] = [{ wert: "privat", titel: "Privat" }, { wert: "fremd", titel: "Fremd" }];

  const sichtbar = $derived(liste.filter((s) => !suche.trim() || s.name.toLowerCase().includes(suche.trim().toLowerCase())));
  const gewaehlt = $derived(liste.find((s) => s.id === gewaehltId) ?? (geraet.mobil ? null : sichtbar[0] ?? null));
  const geaendert = $derived(!!gewaehlt?.angaben && !!angaben && JSON.stringify(angaben) !== JSON.stringify(gewaehlt.angaben));

  async function laden() {
    fehler = "";
    try {
      liste = await api.stimmen(bereich);
    } catch (f) {
      liste = [];
      fehler = (f as Error).message;
    }
  }

  onMount(() => void laden());

  $effect(() => {
    angaben = gewaehlt?.angaben ? JSON.parse(JSON.stringify(gewaehlt.angaben)) : null;
    loeschFrage = false;
  });

  function wechseln(b: StimmBereich) {
    bereich = b;
    gewaehltId = null;
    void laden();
  }

  function waehlen(s: Stimme) {
    gewaehltId = s.id;
    leisteOeffnen();
  }

  async function speichern() {
    if (!gewaehlt || !angaben) return;
    fehler = "";
    try {
      const neu = await api.stimmeAendern(gewaehlt.id, angaben);
      meldung = neu.bereich !== bereich ? `${neu.name} liegt jetzt unter ${neu.bereich === "privat" ? "Privat" : "Fremd"}.` : "";
      await laden();
      void stimmenLaden();
    } catch (f) {
      fehler = (f as Error).message;
    }
  }

  async function loeschen() {
    if (!gewaehlt) return;
    try {
      await api.stimmeLoeschen(gewaehlt.id);
      meldung = `${gewaehlt.name} liegt im Papierkorb der Kellerwolke.`;
      gewaehltId = null;
      await laden();
      void stimmenLaden();
    } catch (f) {
      fehler = (f as Error).message;
    }
  }

  async function hochladen(e: Event) {
    const f = (e.target as HTMLInputElement).files?.[0];
    (e.target as HTMLInputElement).value = "";
    if (!f) return;
    fehler = "";
    try {
      const neu = await api.stimmeHochladen(f, f.name.replace(/\.[^.]+$/, ""), bereich === "privat" ? "privat" : "fremd",
                                            f.name.includes(".") ? f.name.slice(f.name.lastIndexOf(".")).toLowerCase() : ".wav");
      meldung = `${neu.name} angelegt (${neu.dauer_s?.toFixed(1).replace(".", ",")} s Probe).`;
      await laden();
      gewaehltId = neu.id;
      void stimmenLaden();
    } catch (f2) {
      fehler = (f2 as Error).message;
    }
  }

  // Eine aufgenommene Probe wird gleich eine Stimme (privat: meist die eigene oder die von jemandem aus dem Umfeld)
  async function ablegen(fertig: { daten: Blob; info: { name: string } }): Promise<string> {
    const endung = fertig.info.name.slice(fertig.info.name.lastIndexOf("."));
    const neu = await api.stimmeHochladen(fertig.daten, fertig.info.name.replace(/\.[^.]+$/, ""), "privat", endung);
    return neu.id;
  }

  function danachFertig(d: NachDerAufnahme) {
    aufnahme.danach = null;
    bereich = "privat";
    gewaehltId = d.id;
    void laden();
    void stimmenLaden();
  }
</script>

{#snippet detail(s: Stimme)}
  <div class="gruppe">
    <h3>Probe</h3>
    {#if s.bereich !== "katalog"}
      <div class="knopfreihe"><button class="knopf" onclick={() => (spielt = spielt === s.id ? null : s.id)}>
        <i class="fa-solid {spielt === s.id ? 'fa-pause' : 'fa-play'}"></i> {spielt === s.id ? "Anhalten" : "Anhören"}{s.dauer_s ? ` (${s.dauer_s.toFixed(1).replace(".", ",")} s)` : ""}</button></div>
    {:else}<p class="leer" style="text-align:left; padding:0">Feste Stimme des Sprechdienstes, ohne eigene Probe.</p>{/if}
  </div>
  {#if angaben}
    <div class="gruppe">
      <h3>Angaben</h3>
      <dl class="stimme-angabe">
        <dt>Name</dt><dd><label class="eingabe klein-eingabe"><input bind:value={angaben.name} aria-label="Name" /></label></dd>
        <dt>Bereich</dt><dd><Auswahl bind:wert={angaben.bereich} optionen={BEREICHE} klein /></dd>
        <dt>Sprache</dt><dd><label class="eingabe klein-eingabe"><input bind:value={angaben.sprache} aria-label="Sprache" /></label></dd>
        <dt>Bekannt als</dt><dd>
          <span class="chips">{#each angaben.bekannt_als as b, i (b)}<span class="chip">{b}
            <button title="Entfernen" onclick={() => angaben && (angaben.bekannt_als = angaben.bekannt_als.filter((_, j) => j !== i))}><i class="fa-solid fa-xmark"></i></button></span>{/each}</span>
          <label class="eingabe klein-eingabe" style="margin-top:6px"><input bind:value={bekannt} placeholder="weiterer Name, Enter"
            onkeydown={(k) => { if (k.key === "Enter" && bekannt.trim() && angaben) { angaben.bekannt_als = [...angaben.bekannt_als, bekannt.trim()]; bekannt = ""; } }} /></label></dd>
        {#if angaben.herkunft?.pfad}<dt>Herkunft</dt><dd>{angaben.herkunft.pfad}</dd>{/if}
      </dl>
      <p class="beschriftung" style="margin:12px 0 4px">Referenztext (was in der Probe gesagt wird)</p>
      <textarea class="text-eingabe niedrig" bind:value={angaben.referenztext} aria-label="Referenztext"></textarea>
      <div class="knopfreihe">
        <button class="knopf primaer klein" disabled={!geaendert} onclick={speichern}><i class="fa-solid fa-floppy-disk"></i> Speichern</button>
        <button class="knopf klein still" onclick={() => (loeschFrage = true)}><i class="fa-solid fa-trash-can"></i> In den Papierkorb</button>
      </div>
      {#if loeschFrage}
        <Rueckfrage frage="{s.name} in den Papierkorb?" hinweis="Probe, Angaben und Originalaufnahme gehen zusammen; zurückholen geht in der Kellerwolke."
                    knopf="In den Papierkorb" onabbrechen={() => (loeschFrage = false)} onja={loeschen} />
      {/if}
    </div>
  {/if}
{/snippet}

{#snippet zeile(s: Stimme)}
  <div class="zeile" class:gewaehlt={!geraet.mobil && gewaehlt?.id === s.id} role="button" tabindex="0"
       onclick={() => waehlen(s)} onkeydown={(k) => k.key === "Enter" && waehlen(s)}>
    <span class="art"><i class="fa-solid fa-user"></i></span>
    <div style="min-width:0"><div class="name">{s.name}</div>
      <div class="meta">{[s.angaben?.sprache === "de" ? "Deutsch" : s.angaben?.sprache, s.dauer_s ? `${s.dauer_s.toFixed(1).replace(".", ",")} s` : "",
        s.angaben?.herkunft?.art === "uebernommen" ? "übernommen aus der alten App" : s.angaben?.herkunft?.art === "hochgeladen" ? "hochgeladen" : "",
        s.angaben?.bekannt_als.length ? `bekannt als ${s.angaben.bekannt_als.join(", ")}` : "", s.bereich === "katalog" ? "feste Stimme" : ""].filter(Boolean).join(" · ")}</div></div>
    <span></span>
    {#if s.bereich !== "katalog"}
      <button class="rund" title={spielt === s.id ? "Anhalten" : "Probe anhören"} onclick={(k) => { k.stopPropagation(); spielt = spielt === s.id ? null : s.id; }}>
        <i class="fa-solid {spielt === s.id ? 'fa-pause' : 'fa-play'}"></i></button>
    {:else}<span></span>{/if}
  </div>
{/snippet}

{#snippet kopfKnoepfe()}
  <button class="knopf" title="Eine Probe mit dem Mikrofon aufnehmen" onclick={() => void aufnehmen()} disabled={aufnahme.laeuft || !!aufnahme.danach}>
    <i class="fa-solid fa-circle-dot" style="color:var(--gefahr)"></i> Aufnehmen</button>
  <button class="knopf primaer" onclick={() => datei?.click()}><i class="fa-solid fa-upload"></i> Hochladen</button>
  <input type="file" accept="audio/*" hidden bind:this={datei} onchange={hochladen} />
{/snippet}

{#snippet segment()}
  <span class="segment">
    {#each [["privat", "Privat"], ["fremd", "Fremd"], ["katalog", "Katalog"]] as [b, t] (b)}
      <button class:aktiv={bereich === b} onclick={() => wechseln(b as StimmBereich)}>{t}{bereich === b ? ` ${liste.length}` : ""}</button>
    {/each}
  </span>
{/snippet}

{#if aufnahme.laeuft || aufnahme.danach}
  <div class="seiten-kopf"><h1>Probe aufnehmen</h1></div>
  <div class="rollfeld rek-flaeche">
    <Rekorder ort="Stimmen, Privat" {ablegen} onfertig={(m) => (meldung = m)}>
      {#snippet danach(d)}
        <p class="leer" style="text-align:left">Die Probe ist als Stimme unter Privat angelegt. Name, Bereich und Referenztext lassen sich dort ändern.</p>
        <div class="knopfzeile"><button class="knopf primaer" onclick={() => danachFertig(d)}><i class="fa-solid fa-user"></i> Zur Stimme</button></div>
      {/snippet}
    </Rekorder>
  </div>
{:else if geraet.mobil}
  {@render segment()}
  {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
  {#if meldung}<p class="leer" style="padding:6px 4px">{meldung}</p>{/if}
  {#if gewaehlt}
    <div class="leiste-inhalt">{@render detail(gewaehlt)}</div>
    <button class="knopf" style="width:100%; margin-top:10px" onclick={() => (gewaehltId = null)}><i class="fa-solid fa-chevron-left"></i> Alle Stimmen</button>
  {:else}
    <div class="t-liste" style="margin-top:12px">
      {#each sichtbar as s (s.id)}
        <button class="t-zeile" onclick={() => waehlen(s)}><i class="fa-solid fa-user"></i>
          <span class="t-text"><span class="t-name">{s.name}</span><span class="t-meta">{s.dauer_s ? `${s.dauer_s.toFixed(1).replace(".", ",")} s` : "feste Stimme"}</span></span>
          {#if s.bereich !== "katalog"}<i class="fa-solid {spielt === s.id ? 'fa-pause' : 'fa-play'}" style="color:var(--akzent)"></i>{/if}</button>
      {:else}<div class="leer">Hier gibt es noch keine Stimme.</div>{/each}
    </div>
    <div class="knopfzeile" style="margin-top:14px">{@render kopfKnoepfe()}</div>
  {/if}
{:else}
  <div class="geruest-innen">
    <section class="seite">
      <div class="seiten-kopf">
        <h1>Stimmen</h1>
        {@render segment()}
        <label class="suche" style="min-width:180px"><i class="fa-solid fa-magnifying-glass"></i>
          <input class="eingabe-roh" placeholder="Name suchen" bind:value={suche} /></label>
        <span class="knopfzeile" style="margin-left:auto">{#if bereich !== "katalog"}{@render kopfKnoepfe()}{/if}
          <button class="knopf nur-schmal" onclick={leisteOeffnen}><i class="fa-solid fa-table-columns"></i> Leiste</button></span>
      </div>
      <div class="rollfeld">
        {#if bereich === "privat"}
          <div class="hinweis-band"><i class="fa-solid fa-shield-halved"></i><span>Private Stimmen gehören Menschen aus deinem Umfeld: nutzbar nur für die Apps, die du in den Einstellungen erlaubst, nie für Öffentliches.</span></div>
        {/if}
        {#if fehler}<div class="fehlertext" style="margin-bottom:12px">{fehler}</div>{/if}
        {#if meldung}<p class="leer" style="padding:6px 4px 14px; text-align:left">{meldung}</p>{/if}
        {#each sichtbar as s (s.id)}{@render zeile(s)}{:else}<p class="leer">{suche ? "Niemand gefunden." : "Hier gibt es noch keine Stimme."}</p>{/each}
      </div>
    </section>
    <Leiste>
      {#if gewaehlt}
        <div class="leiste-kopf"><h2>{gewaehlt.name}</h2></div>
        <div class="rollfeld leiste-inhalt">{@render detail(gewaehlt)}</div>
      {:else}<div class="leiste-kopf"><h2>Keine Stimme gewählt</h2></div>{/if}
    </Leiste>
  </div>
{/if}
{#if spielt}<audio src={api.probeAdresse(spielt)} autoplay onended={() => (spielt = null)} onpause={() => (spielt = null)} hidden></audio>{/if}
