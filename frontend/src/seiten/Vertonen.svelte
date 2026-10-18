<script lang="ts">
  // Vertonungen: alle Pläne mit Art, Stimmen und Stand; neu als Vorlesen, Dialog oder Zeitgenau. Unterseiten:
  // vertonen/neu/<art>[/anfrage/<id>] (anlegen), vertonen/neu/zeitgenau/kellerwolke[/<ordner>] (Aufnahme wählen),
  // vertonen/<plan>[/anfrage/<id>] (Plan). Entwurf: mockups/vertonung.html (1) und vertonung-mobil.html (2).
  import { onMount } from "svelte";
  import { beiAuftrag, gehe, geraet, hole, marke, navigation, wann, type Auftrag, type Seite } from "appkern-oberflaeche";
  import * as api from "../lib/api";
  import { ARTEN, type Art, type Eintrag, type Verzeichnis } from "../lib/typen";
  import Neu from "../teile/Neu.svelte";
  import PlanAnsicht from "../teile/PlanAnsicht.svelte";

  const SEITE = 50;
  const teile = $derived(navigation.seite === "vertonen" ? navigation.teile : []);
  const neuArt = $derived(teile[0] === "neu" ? (teile[1] as Art | undefined) ?? null : null);
  const planId = $derived(teile[0] && teile[0] !== "neu" ? teile[0] : null);
  const anfrage = $derived(teile.includes("anfrage") ? teile[teile.indexOf("anfrage") + 1] ?? null : null);

  let liste = $state<Verzeichnis | null>(null);
  let art = $state<Art | null>(null);
  let suche = $state("");
  let ab = $state(0);
  let fehler = $state("");
  let laufend = $state<Record<string, Auftrag>>({});
  let spielt = $state<string | null>(null);

  async function laden() {
    fehler = "";
    try {
      liste = await api.plaene({ art, suche, ab, anzahl: SEITE });
    } catch (f) {
      fehler = (f as Error).message;
    }
  }

  onMount(() => {
    if (!planId && !neuArt) void laden();
    void hole<Seite<Auftrag>>("/auftraege?zustand=wartet&zustand=laeuft&grenze=200").then((s) => {
      laufend = Object.fromEntries(s.eintraege.filter((a) => a.art === "vertonen").map((a) => [String(a.eingabe.plan_id), a]));
    }).catch(() => {});
    return beiAuftrag((a) => {
      if (a.art !== "vertonen") return;
      const id = String(a.eingabe.plan_id);
      if (a.zustand === "wartet" || a.zustand === "laeuft") laufend = { ...laufend, [id]: a };
      else {
        const { [id]: _weg, ...rest } = laufend;
        laufend = rest;
        void laden();
      }
    });
  });

  // Rückkehr aus einem Plan oder vom Anlegen: die Liste zeigt den neuen Stand (Lehre 11)
  let zuletzt = "";
  $effect(() => {
    const jetzt = `${planId}|${neuArt}`;
    if (jetzt !== zuletzt) {
      zuletzt = jetzt;
      if (!planId && !neuArt) void laden();
    }
  });

  let suchTakt: ReturnType<typeof setTimeout>;
  function suchen() {
    clearTimeout(suchTakt);
    suchTakt = setTimeout(() => {
      ab = 0;
      void laden();
    }, 250);
  }

  function filtern(a: Art | null) {
    art = a;
    ab = 0;
    void laden();
  }

  function stand(e: Eintrag): { klasse: string; text: string } {
    const a = laufend[e.id];
    if (a) return { klasse: "laeuft", text: a.zustand === "wartet" ? "wartet" : `${a.schritt?.split(",")[0] || "läuft"}${a.fortschritt != null ? ` ${Math.round(a.fortschritt * 100)} %` : ""}` };
    if (!e.ergebnis_id) return { klasse: "offen", text: "noch nicht gesprochen" };
    if (e.offen) return { klasse: "warn", text: `${e.offen} geändert` };
    return { klasse: "fertig", text: e.hinweise ? `fertig, ${e.hinweise} Hinweis${e.hinweise === 1 ? "" : "e"}` : "fertig" };
  }

  function meta(e: Eintrag): string {
    const stimmen = e.rollen.length > 2 ? `${e.rollen.length} Rollen` : e.rollen.map((r) => (e.art === "vorlesen" ? r.stimme : r.name)).join(", ");
    const ort = e.haupt_pfad.split("/").slice(0, -1).join("/");
    return [ARTEN[e.art].titel, stimmen, e.dauer_s ? marke(e.dauer_s) : "", ort ? `neben ${ort}` : "", wann(e.geaendert_am)].filter(Boolean).join(" · ");
  }

  const oeffnen = (e: Eintrag) => gehe(`vertonen/${e.id}${e.anfrage_id ? `/anfrage/${e.anfrage_id}` : ""}`);
</script>

{#snippet knopf(e: Eintrag)}
  {#if laufend[e.id]}<span></span>
  {:else if e.ergebnis_id && e.offen}
    <button class="knopf still" onclick={(k) => { k.stopPropagation(); oeffnen(e); }}><i class="fa-solid fa-microphone"></i> Geänderte sprechen</button>
  {:else if e.ergebnis_id}
    <button class="knopf still" onclick={(k) => { k.stopPropagation(); spielt = spielt === e.id ? null : e.id; }}>
      <i class="fa-solid {spielt === e.id ? 'fa-pause' : 'fa-play'}"></i> {spielt === e.id ? "Anhalten" : "Anhören"}</button>
  {:else}<span></span>{/if}
{/snippet}

{#if neuArt}
  <Neu art={neuArt} {anfrage} ordner={teile[2] === "kellerwolke" ? teile[3] ?? null : null} kellerwolke={teile[2] === "kellerwolke"} />
{:else if planId}
  <PlanAnsicht id={planId} {anfrage} laufend={laufend[planId] ?? null} />
{:else if geraet.mobil}
  {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
  {@const offen = (liste?.eintraege ?? []).filter((e) => laufend[e.id])}
  {#if offen.length}
    <div class="t-gruppe">Läuft</div>
    <div class="t-liste">
      {#each offen as e (e.id)}
        <button class="t-zeile" onclick={() => oeffnen(e)}><i class="fa-solid {ARTEN[e.art].symbol}"></i>
          <span class="t-text"><span class="t-name">{e.name}</span><span class="t-meta">{ARTEN[e.art].titel} · {stand(e).text}</span></span>
          <span class="stand-pille laeuft"><i class="fa-solid fa-circle-notch fa-spin"></i></span></button>
      {/each}
    </div>
  {/if}
  <div class="t-gruppe">Vertonungen</div>
  <div class="t-liste">
    {#each (liste?.eintraege ?? []).filter((e) => !laufend[e.id]) as e (e.id)}
      <button class="t-zeile" onclick={() => (e.ergebnis_id && !e.offen ? (spielt = spielt === e.id ? null : e.id) : oeffnen(e))}>
        <i class="fa-solid {ARTEN[e.art].symbol}"></i>
        <span class="t-text"><span class="t-name">{e.name}</span><span class="t-meta">{meta(e)}</span></span>
        {#if e.offen && e.ergebnis_id}<span class="stand-pille warn">geändert</span>
        {:else if e.ergebnis_id}<i class="fa-solid {spielt === e.id ? 'fa-pause' : 'fa-play'}" style="color:var(--akzent)"></i>
        {:else}<i class="fa-solid fa-chevron-right" style="color:var(--text-3)"></i>{/if}
      </button>
    {:else}
      <div class="leer">{liste ? "Noch keine Vertonung. Unter Vorlesen geht es los." : "Lädt ..."}</div>
    {/each}
  </div>
{:else}
    <div class="seiten-kopf">
      <h1>Vertonen</h1>
      <span class="segment">
        <button class:aktiv={art === null} onclick={() => filtern(null)}>Alle {liste ? Object.values(liste.zahlen).reduce((a, b) => a + (b ?? 0), 0) : ""}</button>
        {#each Object.entries(ARTEN) as [a, info] (a)}
          <button class:aktiv={art === a} onclick={() => filtern(a as Art)}>{info.titel} {liste?.zahlen[a as Art] ?? 0}</button>
        {/each}
      </span>
      <label class="suche" style="min-width:200px"><i class="fa-solid fa-magnifying-glass"></i>
        <input class="eingabe-roh" placeholder="Name suchen" bind:value={suche} oninput={suchen} /></label>
      <span class="knopfzeile" style="margin-left:auto">
        <button class="knopf primaer" onclick={() => gehe("vertonen/neu/vorlesen")}><i class="fa-solid {ARTEN.vorlesen.symbol}"></i> Vorlesen</button>
        <button class="knopf" onclick={() => gehe("vertonen/neu/dialog")}><i class="fa-solid {ARTEN.dialog.symbol}"></i> Dialog</button>
        <button class="knopf" onclick={() => gehe("vertonen/neu/zeitgenau/kellerwolke")}><i class="fa-solid {ARTEN.zeitgenau.symbol}"></i> Zeitgenau</button>
      </span>
    </div>
    <div class="rollfeld">
      {#if fehler}<div class="fehlertext" style="margin-bottom:12px">{fehler}</div>{/if}
      {#each liste?.eintraege ?? [] as e (e.id)}
        {@const s = stand(e)}
        <div class="zeile" role="button" tabindex="0" onclick={() => oeffnen(e)} onkeydown={(k) => k.key === "Enter" && oeffnen(e)}>
          <span class="art"><i class="fa-solid {ARTEN[e.art].symbol}"></i></span>
          <div style="min-width:0"><div class="name">{e.name}</div><div class="meta">{meta(e)}</div></div>
          <span class="stand-pille {s.klasse}">{#if s.klasse === "laeuft"}<i class="fa-solid fa-circle-notch fa-spin"></i> {/if}{s.text}</span>
          {@render knopf(e)}
        </div>
      {:else}
        <p class="leer">{liste ? (suche ? "Nichts gefunden." : "Noch keine Vertonung. Vorlesen, Dialog oder Zeitgenau beginnen.") : "Lädt ..."}</p>
      {/each}
      {#if liste && liste.gesamt > SEITE}
        <div class="seitenzeile"><span>{ab + 1} bis {Math.min(ab + SEITE, liste.gesamt)} von {liste.gesamt}</span>
          <button class="knopf" disabled={ab === 0} onclick={() => { ab = Math.max(0, ab - SEITE); void laden(); }}><i class="fa-solid fa-chevron-left"></i> Zurück</button>
          <button class="knopf" disabled={ab + SEITE >= liste.gesamt} onclick={() => { ab += SEITE; void laden(); }}>Weiter <i class="fa-solid fa-chevron-right"></i></button>
        </div>
      {/if}
    </div>
{/if}
{#if spielt}<audio src={api.ergebnisAdresse(spielt, liste?.eintraege.find((e) => e.id === spielt)?.anfrage_id)} autoplay onended={() => (spielt = null)} onpause={() => (spielt = null)} hidden></audio>{/if}
