<script lang="ts">
  // Eine Vertonung anlegen. Vorlesen und Dialog: Text hier eingeben (er kommt nach Texte) oder aus der Kellerwolke
  // (Dateimenü "Vorlesen", dann mit Anfrage); Zeitgenau: Aufnahme mit Transkript oder Untertiteln aus der Kellerwolke
  // wählen (Dateiwahl), dann je Sprecher eine Stimme. Gesprochen wird erst im Plan (Vorschau vor Anwenden).
  import { onMount } from "svelte";
  import { anfrage as anfrageHolen, Auswahl, Dateiwahl, gehe, geraet, istMedium, navigation, waehlen,
           type WahlEintrag, type WahlSeite, type WahlZweck } from "appkern-oberflaeche";
  import * as api from "../lib/api";
  import { stimmenLaden, stimmenListe } from "../lib/stimmen.svelte";
  import { ARTEN, SPRACHEN, type Art, type Format, type StimmWahl } from "../lib/typen";
  import StimmFeld from "./StimmFeld.svelte";

  let { art, anfrage = null, ordner = null, kellerwolke = false }:
    { art: Art; anfrage?: string | null; ordner?: string | null; kellerwolke?: boolean } = $props();

  interface Vorschau { id: string; name: string; pfad: string; art: string; textquelle: string | null; sprecher: string[]; abschnitte: number; dauer_s: number | null; text: string | null; sprache: string | null }

  let name = $state("");
  let text = $state("");
  let stimme = $state<StimmWahl>({ art: "katalog", name: null });      // Stimme ab Werk, leer die Vorgabe des Sprechdienstes
  let rollen = $state<Record<string, StimmWahl>>({});
  let format = $state<Format>("mp3");
  let sprache = $state("de");
  let ausgang = $state("en");
  const SPRACHWAHL = Object.entries(SPRACHEN).map(([wert, titel]) => ({ wert, titel }));
  let vorschau = $state<Vorschau | null>(null);
  let fehler = $state("");
  let legtAn = $state(false);
  let ohneText = $state<string | null>(null);      // Aufnahme ohne Transkript: ihre Kennung
  let transkribiert = $state(false);               // an die Transkription weitergegeben, wartet auf das Transkript
  let warteTakt: ReturnType<typeof setInterval> | undefined;
  let kette = $state<WahlSeite["kette"]>([]);
  const FORMATE: { wert: Format; titel: string }[] = [
    { wert: "mp3", titel: "MP3, 24 kHz mono" }, { wert: "wav", titel: "WAV, 24 kHz mono" },
    { wert: "flac", titel: "FLAC, 24 kHz mono" }, { wert: "ogg", titel: "OGG Opus, 24 kHz mono" }];

  // Rollen eines Dialogs aus dem Text (Zeilen "Name: Satz"), in der Reihenfolge ihres ersten Auftritts
  const dialogNamen = $derived([...new Set(text.split("\n").map((z) => z.match(/^\s*([^:\n]{1,40}?)\s*:\s*\S/)?.[1]?.trim()).filter((n): n is string => !!n))]);
  const namen = $derived(art === "dialog" ? dialogNamen : vorschau?.sprecher ?? []);

  onMount(() => {
    if (!stimmenListe.geladen) void stimmenLaden();
    void api.einstellungWert<string>("stimme_vorgabe").then((v) => { if (v) stimme = { art: "katalog", name: v }; }).catch(() => {});
    void api.einstellungWert<Format>("format").then((v) => { if (v) format = v; }).catch(() => {});
    void api.einstellungWert<string>("sprache").then((v) => { if (v) sprache = v; }).catch(() => {});
    if (anfrage) void vorschauLaden();
    if (geraet.mobil) navigation.titel = ARTEN[art].titel;
    return () => clearInterval(warteTakt);
  });

  async function vorschauLaden() {
    if (!anfrage) return;
    try {
      const a = await anfrageHolen(anfrage);
      try {
        vorschau = await api.quelle(a.knoten_id, anfrage);
      } catch (f) {
        if (!(f as Error).message.includes("kein Transkript")) throw f;
        ohneText = a.knoten_id;
        return;
      }
      ohneText = null;
      clearInterval(warteTakt);
      transkribiert = false;
      name = vorschau.name.replace(/\.[^.]+$/, "");
      if (vorschau.sprache) ausgang = vorschau.sprache;
      if (vorschau.text) text = vorschau.text;
    } catch (f) {
      fehler = (f as Error).message;
    }
  }

  async function transkribierenLassen() {
    if (!ohneText) return;
    fehler = "";
    try {
      await api.transkribierenLassen(ohneText, ausgang, anfrage);
      transkribiert = true;
      warteTakt = setInterval(() => void vorschauLaden(), 10000);
    } catch (f) {
      fehler = (f as Error).message;
    }
  }

  async function anlegen() {
    legtAn = true;
    fehler = "";
    try {
      const stimmen: Record<string, StimmWahl> = {};
      for (const n of namen) stimmen[n] = rollen[n] ?? stimme;
      const p = await api.planAnlegen({
        art, name: name.trim(), stimme, stimmen, format: art === "zeitgenau" ? null : format, sprache,
        ausgangssprache: art === "zeitgenau" ? ausgang : null,
        ...(vorschau ? { quelle_id: vorschau.id, anfrage_id: anfrage } : { text }),
      });
      gehe(`vertonen/${p.id}${anfrage ? `/anfrage/${anfrage}` : ""}`);
    } catch (f) {
      fehler = (f as Error).message;
    } finally {
      legtAn = false;
    }
  }

  // Zeitgenau aus der Kellerwolke: wählbar ist Ton und Video; ohne Transkript daneben legt es die Transkription an
  const zweck: WahlZweck = {
    auftrag: "vertonen",
    quelle: (a) => String(a.eingabe.plan_id),
    ergebnis: ["vertonung"],
    einzeln: true,
    waehlbar: (e: WahlEintrag) => istMedium(e.inhaltstyp),
    ordnerAdresse: (id) => `vertonen/neu/zeitgenau/kellerwolke/${id}`,
    woerter: {
      tun: "Weiter", symbol: "fa-clock", fertig: "vertont", offen: "noch nicht vertont", gruppe: "Ton und Video",
      leer: "Hier liegt kein Ton und kein Video.", andere: "kein Ton",
      nichtWaehlbar: "Neu sprechen geht mit Ton und Video",
      hinweis: "Hier siehst du nur Namen. Lesen darf die App eine Aufnahme und ihr Transkript erst, wenn du sie wählst. Plan und neue Sprache liegen danach neben ihr.",
      hinweisKurz: "Lesen darf die App nur, was du wählst.",
      anleitung: "Eine Aufnahme anklicken, dann Weiter: je Sprecher eine Stimme wählen (fehlt das Transkript, legt es die Transkription an).",
    },
    starten: async (ids) => {
      const { anfrage: a } = await waehlen(ids[0], "neu_sprechen");
      gehe(`anfrage/${a.id}`);
      return "";
    },
  };
</script>

{#snippet rollenWahl()}
  {#if namen.length}
    <div class="rollen">
      {#each namen as n, i (n)}
        <div class="rollen-karte"><span class="sprecher"><span class="punkt" style="background:var(--s{(i % 6) + 1})"></span>{n}</span>
          <StimmFeld wahl={rollen[n] ?? stimme} onwahl={(w) => (rollen = { ...rollen, [n]: w })} /></div>
      {/each}
    </div>
  {/if}
{/snippet}

{#if art === "zeitgenau" && kellerwolke}
  {#if !geraet.mobil}
    <div class="seiten-kopf">
      <button class="knopf still" style="padding:0 6px" onclick={() => gehe("vertonen")}><i class="fa-solid fa-chevron-left"></i> Vertonen</button>
      <h1>Zeitgenau: Aufnahme wählen</h1>
      {#if kette.length > 1}
        <span class="chips">{#each kette as k, i (k.id ?? "wurzel")}
          <button class="chip" onclick={() => gehe(k.id ? `vertonen/neu/zeitgenau/kellerwolke/${k.id}` : "vertonen/neu/zeitgenau/kellerwolke")}>{i === 0 ? "Meine Dateien" : k.name}</button>{/each}</span>
      {/if}
    </div>
  {/if}
  <div class="rollfeld"><Dateiwahl {zweck} {ordner} bind:kette /></div>
{:else}
  {#if !geraet.mobil}
    <div class="seiten-kopf">
      <button class="knopf still" style="padding:0 6px" onclick={() => gehe("vertonen")}><i class="fa-solid fa-chevron-left"></i> Vertonen</button>
      <h1>{ARTEN[art].titel}{vorschau ? `: ${vorschau.name}` : ""}</h1>
      <span class="knopfzeile" style="margin-left:auto">
        <button class="knopf primaer" onclick={anlegen} disabled={legtAn || (!vorschau && !text.trim())}>
          <i class="fa-solid {legtAn ? 'fa-circle-notch fa-spin' : 'fa-list-check'}"></i> Plan anlegen</button>
      </span>
    </div>
  {/if}
  <div class="rollfeld" style="max-width:1020px">
    {#if fehler}<div class="fehlertext" style="margin-bottom:12px">{fehler}</div>{/if}
    {#if ohneText}
      <div class="hinweis-band"><i class="fa-solid {transkribiert ? 'fa-circle-notch fa-spin' : 'fa-closed-captioning'}"></i>
        <span>{transkribiert ? "Die Transkription arbeitet; sobald das Transkript neben der Aufnahme liegt, geht es hier weiter." :
          `Neben dieser Aufnahme liegt noch kein Transkript und keine Untertitel. Die Transkription kann es anlegen (Aufnahme auf ${SPRACHEN[ausgang]}, unten änderbar).`}</span>
        {#if !transkribiert}<span class="knopfzeile"><button class="knopf primaer" onclick={transkribierenLassen}><i class="fa-solid fa-closed-captioning"></i> Transkribieren lassen</button></span>{/if}
      </div>
    {/if}
    {#if vorschau && art === "zeitgenau"}
      <div class="hinweis-band"><i class="fa-solid fa-file-audio"></i><span><b>{vorschau.name}</b> · {vorschau.textquelle ?? "Transkript"} ·
        {vorschau.abschnitte} Abschnitte · {vorschau.sprecher.length} Sprecher · das Ergebnis kommt als WAV in Rate und Kanälen der Aufnahme daneben</span></div>
    {/if}
    <div class="optionen">
      <span class="titel"><i class="fa-solid {ARTEN[art].symbol}"></i> {art === "vorlesen" ? "Vorlesen mit" : "Stimme ab Werk"}</span>
      <label>Name <span class="eingabe" style="width:240px; height:38px"><input class="eingabe-roh" bind:value={name} placeholder="Name der Vertonung" /></span></label>
      <label>Stimme <StimmFeld bind:wahl={stimme} /></label>
      {#if art !== "zeitgenau"}<label>Format <Auswahl bind:wert={format} optionen={FORMATE} /></label>{/if}
      {#if art === "zeitgenau"}
        <label>Aufnahme auf <Auswahl bind:wert={ausgang} optionen={SPRACHWAHL} /></label>
        <label>Sprechen auf <Auswahl bind:wert={sprache} optionen={SPRACHWAHL} /></label>
      {/if}
    </div>
    {#if art === "zeitgenau" && ausgang !== sprache}
      <p class="leer" style="text-align:left; padding:0 2px 12px">Vor dem Sprechen wird aus dem {SPRACHEN[ausgang]}en ins {SPRACHEN[sprache]}e
        übersetzt: vollständig, knapp genug für die Zeitfenster, nie gekürzt. Das Original bleibt je Abschnitt im Plan.</p>
    {/if}
    {#if art !== "vorlesen"}{@render rollenWahl()}{/if}
    {#if art !== "zeitgenau"}
      <textarea class="text-eingabe" bind:value={text} readonly={!!vorschau} aria-label="Text"
                placeholder={art === "dialog" ? "Mara: Hörst du das?\nJonas: Nur der Wind." : "Text zum Vorlesen"}></textarea>
      <p class="leer" style="text-align:left; padding:8px 2px">{art === "dialog"
        ? "Je Zeile Name: Satz. Eine Zeile ohne Namen setzt die vorige fort; jeder Name wird eine Rolle."
        : vorschau ? "Der Text kommt aus der gewählten Datei; der Plan teilt ihn in Sätze." : "Der Text wird als Datei unter Texte abgelegt; der Plan teilt ihn in Sätze, jeder ist einzeln anhörbar und änderbar."}</p>
    {/if}
    {#if geraet.mobil}
      <button class="knopf primaer" style="width:100%; height:48px; margin-top:12px" onclick={anlegen} disabled={legtAn || (!vorschau && !text.trim())}>
        <i class="fa-solid {legtAn ? 'fa-circle-notch fa-spin' : 'fa-list-check'}"></i> Plan anlegen</button>
    {/if}
  </div>
{/if}
