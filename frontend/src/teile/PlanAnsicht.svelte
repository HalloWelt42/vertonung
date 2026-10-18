<script lang="ts">
  // Ein Plan: Ergebnis im Spieler, Stimmen (Vorlesen: eine, Dialog: Rollen oben, zeitgenau: Rollen in der Leiste),
  // Abschnitte mit Stand, Zeit und Bericht, jeder einzeln anhörbar und änderbar; gesprochen wird nur Geändertes.
  // Zeitgenau: Spur der Quelle und der neuen Sprache in einem Ausschnitt, Filter auf Abschnitte mit Hinweis.
  // Entwurf: mockups/vertonung.html (2, 3, 4).
  import { onMount } from "svelte";
  import { Auswahl, gehe, geraet, inKellerwolke, Leiste, leisteOeffnen, marke, navigation, Spieler, type Auftrag } from "appkern-oberflaeche";
  import * as api from "../lib/api";
  import { stimmenLaden, stimmenListe } from "../lib/stimmen.svelte";
  import { ARTEN, type Abschnitt, type Format, type Plan, type PlanAntwort } from "../lib/typen";
  import StimmFeld from "./StimmFeld.svelte";

  let { id, anfrage = null, laufend = null }: { id: string; anfrage?: string | null; laufend?: Auftrag | null } = $props();

  let antwort = $state<PlanAntwort | null>(null);
  let fehler = $state("");
  let sendet = $state(false);
  let bearbeitet = $state<number | null>(null);
  let entwurf = $state("");
  let spielt = $state<number | null>(null);
  let nurHinweise = $state(false);
  let zeit = $state(0);
  const FORMATE: { wert: Format; titel: string }[] = [
    { wert: "mp3", titel: "MP3, 24 kHz mono" }, { wert: "wav", titel: "WAV, 24 kHz mono" },
    { wert: "flac", titel: "FLAC, 24 kHz mono" }, { wert: "ogg", titel: "OGG Opus, 24 kHz mono" }];
  const TEMPI = [0.8, 0.9, 1.0, 1.1, 1.2].map((t) => ({ wert: t, titel: `${Math.round(t * 100)} %` }));

  const plan = $derived(antwort?.plan ?? null);
  const staende = $derived(Object.fromEntries((antwort?.staende ?? []).map((s) => [s.nr, s])));
  const offen = $derived((antwort?.staende ?? []).filter((s) => s.stand !== "gesprochen").length);
  const hinweise = $derived((antwort?.staende ?? []).filter((s) => s.hinweis).length);
  const sichtbar = $derived((plan?.abschnitte ?? []).filter((a) => !nurHinweise || staende[a.nr]?.hinweis));
  const farbe = (kennung: string) => `var(--s${((Number(kennung.slice(1)) - 1) % 6) + 1})`;

  async function laden() {
    fehler = "";
    try {
      antwort = await api.plan(id, anfrage);
      navigation.titel = antwort.plan.name;
    } catch (f) {
      fehler = (f as Error).message;
    }
  }

  onMount(() => {
    void laden();
    if (!stimmenListe.geladen) void stimmenLaden();
  });

  // Ein Lauf endet: neu laden (Stände, Bericht, Ergebnis)
  let warLaufend = false;
  $effect(() => {
    if (laufend) warLaufend = true;
    else if (warLaufend) {
      warLaufend = false;
      void laden();
    }
  });

  async function speichern(neu: Plan) {
    if (!antwort) return;
    fehler = "";
    try {
      antwort = await api.planAendern(id, neu, antwort.stand, anfrage);
    } catch (f) {
      fehler = (f as Error).message;
      if ((f as Error).message.includes("Inzwischen geändert")) await laden();
    }
  }

  function aendern(veraendern: (p: Plan) => void) {
    if (!plan) return;
    const neu: Plan = JSON.parse(JSON.stringify(plan));
    veraendern(neu);
    void speichern(neu);
  }

  function textBeginnen(a: Abschnitt) {
    bearbeitet = a.nr;
    entwurf = a.text;
  }

  function textFertig(a: Abschnitt) {
    const neu = entwurf.trim();
    bearbeitet = null;
    if (neu && neu !== a.text) aendern((p) => { p.abschnitte.find((x) => x.nr === a.nr)!.text = neu; });
  }

  async function sprechen() {
    sendet = true;
    fehler = "";
    try {
      await api.vertonen(id, anfrage);
    } catch (f) {
      fehler = (f as Error).message;
    } finally {
      sendet = false;
    }
  }

  function rolleName(a: Abschnitt): string {
    return plan?.rollen.find((r) => r.kennung === a.rolle)?.name ?? "";
  }

  function zeitText(a: Abschnitt): string {
    if (plan?.art === "zeitgenau" && a.start != null && a.ende != null) return `${marke(a.start)} bis ${marke(a.ende)}`;
    return a.dauer_s != null ? `${a.dauer_s.toFixed(1).replace(".", ",")} s` : "";
  }

  function hinweisPillen(a: Abschnitt): { klasse: string; text: string }[] {
    const b = a.bericht;
    if (!b) return [];
    const aus: { klasse: string; text: string }[] = [];
    if (b.weg === "luecke") aus.push({ klasse: "offen", text: "Lücke genutzt" });
    if (b.stauchung > 1.0001) aus.push({ klasse: "laeuft", text: `gestaucht ${b.stauchung.toFixed(2).replace(".", ",")}` });
    if (b.versatz_s > 0.01) aus.push({ klasse: "warn", text: `geschoben +${b.versatz_s.toFixed(1).replace(".", ",")} s` });
    if (b.ersatz) aus.push({ klasse: "warn", text: "Ersatzstimme" });
    if (b.versuche > 1 && plan?.art !== "zeitgenau") aus.push({ klasse: "offen", text: `${b.versuche}. Versuch` });
    return aus;
  }

  // Zeitgenau: ein Ausschnitt von zwei Minuten um den ersten sichtbaren Abschnitt
  const FENSTER_S = 120;
  const fensterAb = $derived(Math.max(0, Math.floor(((sichtbar[0]?.start ?? 0) - 10) / 10) * 10));
  const imFenster = $derived((plan?.abschnitte ?? []).filter((a) => (a.start ?? 0) < fensterAb + FENSTER_S && (a.ende ?? 0) > fensterAb));
  const lage = (von: number, laenge: number) => `left:${Math.max(0, ((von - fensterAb) / FENSTER_S) * 100)}%; width:${Math.max(0.4, (laenge / FENSTER_S) * 100)}%`;
  const neuBeginn = (a: Abschnitt) => (a.start ?? 0) + (a.bericht?.versatz_s ?? 0);
  const neuLaenge = (a: Abschnitt) => (a.dauer_s ?? (a.ende ?? 0) - (a.start ?? 0)) / (a.bericht?.stauchung ?? 1);
</script>

{#snippet sprechKnopf()}
  {#if laufend}
    <button class="knopf primaer" disabled><i class="fa-solid fa-circle-notch fa-spin"></i>
      {laufend.zustand === "wartet" ? "wartet" : `${laufend.schritt?.split(",")[0] || "läuft"}${laufend.fortschritt != null ? ` ${Math.round(laufend.fortschritt * 100)} %` : ""}`}</button>
  {:else}
    <button class="knopf primaer" onclick={sprechen} disabled={sendet || (offen === 0 && !!plan?.ergebnis)}>
      <i class="fa-solid {sendet ? 'fa-circle-notch fa-spin' : 'fa-microphone'}"></i>
      {plan?.ergebnis ? (offen ? `Geänderte sprechen (${offen})` : "Gesprochen") : "Sprechen"}</button>
  {/if}
{/snippet}

{#snippet zeilen()}
  <div class="plan-liste">
    {#each sichtbar as a (a.nr)}
      {@const s = staende[a.nr]}
      <div class="plan-zeile" class:ohne-rolle={plan?.art === "vorlesen"} class:geaendert={s?.stand === "geaendert"} class:jetzt={spielt === a.nr}>
        <span class="nr">{a.nr}</span>
        {#if plan?.art !== "vorlesen"}<span class="sprecher"><span class="punkt" style="background:{farbe(a.rolle)}"></span>{rolleName(a)}</span>{/if}
        <div class="satz">
          {#if bearbeitet === a.nr}
            <!-- svelte-ignore a11y_autofocus -->
            <textarea class="text-eingabe niedrig" bind:value={entwurf} autofocus onblur={() => textFertig(a)}
                      onkeydown={(k) => { if (k.key === "Escape") bearbeitet = null; if (k.key === "Enter" && !k.shiftKey) { k.preventDefault(); textFertig(a); } }}></textarea>
          {:else}
            <span role="button" tabindex="0" title="Klicken zum Ändern" onclick={() => textBeginnen(a)} onkeydown={(k) => k.key === "Enter" && textBeginnen(a)}>{a.text}</span>
          {/if}
          <div class="unter"><span class="dauer">{zeitText(a)}</span>
            <span class="stand-pille {s?.stand === 'gesprochen' ? 'fertig' : s?.stand === 'geaendert' ? 'warn' : 'offen'}">{s?.stand === "gesprochen" ? "gesprochen" : s?.stand === "geaendert" ? "geändert" : "offen"}</span>
            {#each hinweisPillen(a) as h (h.text)}<span class="stand-pille {h.klasse}">{h.text}</span>{/each}
          </div>
        </div>
        <button class="rund" title={spielt === a.nr ? "Anhalten" : s?.stand === "geaendert" ? "Alte Fassung anhören" : "Anhören"}
                disabled={s?.stand === "offen"} onclick={() => (spielt = spielt === a.nr ? null : a.nr)}>
          <i class="fa-solid {spielt === a.nr ? 'fa-pause' : 'fa-play'}"></i></button>
      </div>
    {:else}
      <p class="leer">{nurHinweise ? "Kein Abschnitt mit Hinweis." : "Keine Abschnitte."}</p>
    {/each}
  </div>
{/snippet}

{#snippet leisteInhalt(p: Plan)}
  {#if p.art === "zeitgenau"}
    <div class="gruppe">
      <h3>Rollen aus dem Transkript</h3>
      <div class="liste-klein">
        {#each p.rollen as r (r.kennung)}
          <div><span class="sprecher"><span class="punkt" style="background:{farbe(r.kennung)}"></span>{r.name}</span>
            <span style="margin-left:auto"><StimmFeld wahl={r.stimme} klein onwahl={(w) => aendern((x) => { x.rollen.find((y) => y.kennung === r.kennung)!.stimme = w; })} /></span></div>
        {/each}
      </div>
    </div>
  {/if}
  <div class="gruppe">
    <h3>Bericht</h3>
    <div class="liste-klein">
      <div><i class="fa-solid fa-check" style="color:var(--gut)"></i><span>{p.abschnitte.length - offen} von {p.abschnitte.length} gesprochen</span></div>
      {#if p.art === "zeitgenau"}
        <div><i class="fa-solid fa-compress" style="color:var(--akzent)"></i><span>{p.abschnitte.filter((a) => (a.bericht?.stauchung ?? 1) > 1.0001).length} gestaucht, höchstens
          {Math.max(1, ...p.abschnitte.map((a) => a.bericht?.stauchung ?? 1)).toFixed(2).replace(".", ",")}</span></div>
        <div><i class="fa-solid fa-arrow-right" style="color:var(--warn)"></i><span>{p.abschnitte.filter((a) => (a.bericht?.versatz_s ?? 0) > 0.01).length} geschoben</span></div>
      {/if}
      <div><i class="fa-solid {p.abschnitte.some((a) => a.bericht?.ersatz) ? 'fa-triangle-exclamation' : 'fa-check'}" style="color:var({p.abschnitte.some((a) => a.bericht?.ersatz) ? '--warn' : '--gut'})"></i>
        <span>{p.abschnitte.filter((a) => a.bericht?.ersatz).length || "keine"} mit Ersatzstimme</span></div>
    </div>
  </div>
  <div class="gruppe">
    <h3>Ergebnis</h3>
    {#if p.ergebnis}
      <div class="liste-klein"><div><i class="fa-solid fa-file-audio" style="color:var(--akzent)"></i><span>{p.ergebnis.pfad.split("/").at(-1)} · {marke(p.ergebnis.dauer_s)}</span></div></div>
      {#if inKellerwolke(p.ergebnis.pfad)}<div class="knopfreihe"><a class="knopf klein" href={inKellerwolke(p.ergebnis.pfad)}><i class="fa-solid fa-cloud"></i> In der Kellerwolke zeigen</a></div>{/if}
    {:else}<p class="leer" style="text-align:left; padding:0">Noch nicht gesprochen.</p>{/if}
  </div>
  <div class="gruppe">
    <h3>Quelle</h3>
    <div class="liste-klein"><div><i class="fa-solid {ARTEN[p.art].symbol}" style="color:var(--text-3)"></i><span>{antwort?.haupt_pfad}</span></div></div>
  </div>
{/snippet}

{#if !plan}
  {#if fehler}<div class="fehlertext">{fehler}</div>{:else}<p class="leer">Lädt ...</p>{/if}
{:else if geraet.mobil}
  <div class="t-ansicht">
    {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
    <div class="knopfzeile" style="margin-bottom:10px">{@render sprechKnopf()}</div>
    {@render zeilen()}
    {#if plan.ergebnis}
      <div class="t-spieler" style="display:block; padding:6px 16px">
        <Spieler src={api.ergebnisAdresse(id, anfrage, plan.ergebnis.knoten_id + plan.geaendert_am)} dauer={plan.ergebnis.dauer_s} wellenform={plan.ergebnis.wellenform} kompakt bind:zeit />
      </div>
    {/if}
  </div>
{:else}
  <div class="geruest-innen">
    <section class="seite">
      <div class="seiten-kopf">
        <button class="knopf still" style="padding:0 6px" onclick={() => gehe("vertonen")}><i class="fa-solid fa-chevron-left"></i> Vertonen</button>
        <h1 class="titel-lang">{plan.name}</h1>
        {#if plan.art === "zeitgenau"}
          <span class="segment"><button class:aktiv={!nurHinweise} onclick={() => (nurHinweise = false)}>Alle {plan.abschnitte.length}</button>
            <button class:aktiv={nurHinweise} onclick={() => (nurHinweise = true)}>Mit Hinweis {hinweise}</button></span>
        {/if}
        <span class="knopfzeile" style="margin-left:auto">
          <button class="knopf nur-schmal" onclick={leisteOeffnen}><i class="fa-solid fa-table-columns"></i> Leiste</button>
          {@render sprechKnopf()}
        </span>
      </div>
      {#if plan.ergebnis}
        <Spieler src={api.ergebnisAdresse(id, anfrage, plan.ergebnis.knoten_id + plan.geaendert_am)} dauer={plan.ergebnis.dauer_s} wellenform={plan.ergebnis.wellenform} bind:zeit />
      {/if}
      <div class="rollfeld" style="padding-top:14px">
        {#if fehler}<div class="fehlertext" style="margin-bottom:12px">{fehler}</div>{/if}
        {#if plan.art === "vorlesen"}
          <div class="optionen">
            <span class="titel"><i class="fa-solid {ARTEN.vorlesen.symbol}"></i> Vorlesen mit</span>
            <label>Stimme <StimmFeld wahl={plan.rollen[0].stimme} onwahl={(w) => aendern((p) => { p.rollen[0].stimme = w; })} /></label>
            <label>Tempo <Auswahl wert={plan.rollen[0].tempo} optionen={TEMPI} onwahl={(t) => aendern((p) => { p.rollen[0].tempo = t; })} /></label>
            <label>Format <Auswahl wert={plan.ziel.format as Format} optionen={FORMATE} onwahl={(f) => aendern((p) => { p.ziel.format = f; })} /></label>
          </div>
        {:else if plan.art === "dialog"}
          <div class="rollen">
            {#each plan.rollen as r (r.kennung)}
              <div class="rollen-karte"><span class="sprecher"><span class="punkt" style="background:{farbe(r.kennung)}"></span>{r.name}</span>
                <StimmFeld wahl={r.stimme} onwahl={(w) => aendern((p) => { p.rollen.find((x) => x.kennung === r.kennung)!.stimme = w; })} /></div>
            {/each}
          </div>
        {:else}
          <div class="spuren">
            <div class="spuren-zeile"><span class="name">Original</span>
              <div class="spur">{#each imFenster as a (a.nr)}<span class="stueck" style={lage(a.start ?? 0, (a.ende ?? 0) - (a.start ?? 0))}></span>{/each}</div></div>
            <div class="spuren-zeile"><span class="name">Neu</span>
              <div class="spur">{#each imFenster.filter((a) => a.dauer_s != null) as a (a.nr)}
                <span class="stueck {(a.bericht?.versatz_s ?? 0) > 0.01 ? 'geschoben' : (a.bericht?.stauchung ?? 1) > 1.0001 ? 'gestaucht' : 'neu'}" style={lage(neuBeginn(a), neuLaenge(a))}></span>{/each}</div></div>
            <div class="spuren-legende"><span><i class="fa-solid fa-square" style="color:var(--akzent); opacity:.8"></i>passt ins Zeitfenster</span>
              <span><i class="fa-solid fa-square" style="color:var(--akzent)"></i>gestaucht</span><span><i class="fa-solid fa-square" style="color:var(--warn)"></i>geschoben</span>
              <span>Ausschnitt {marke(fensterAb)} bis {marke(fensterAb + FENSTER_S)} · nie gekürzt, nie abgeschnitten</span></div>
          </div>
        {/if}
        {@render zeilen()}
      </div>
    </section>
    <Leiste>
      <div class="leiste-kopf"><h2>{ARTEN[plan.art].titel}</h2></div>
      <div class="rollfeld leiste-inhalt">{@render leisteInhalt(plan)}</div>
    </Leiste>
  </div>
{/if}
{#if spielt !== null}
  <audio src={api.abschnittAdresse(id, spielt, staende[spielt]?.stand)} autoplay onended={() => (spielt = null)} onpause={() => (spielt = null)} hidden></audio>
{/if}
