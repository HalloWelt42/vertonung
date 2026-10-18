// Typen der Schnittstelle der Vertonung (wie die Modelle im Backend: app/modell, app/api).

export type Bereich = "privat" | "fremd";
export type StimmBereich = Bereich | "katalog";
export type Art = "vorlesen" | "dialog" | "zeitgenau";
export type Stand = "offen" | "gesprochen" | "geaendert";
export type Weg = "frei" | "luecke" | "gestaucht" | "geschoben";
export type Format = "mp3" | "wav" | "flac" | "ogg";

export interface Herkunft {
  art: "aufnahme" | "hochgeladen" | "aufgenommen" | "uebernommen";
  knoten_id?: string | null;
  pfad?: string | null;
  start?: number | null;
  ende?: number | null;
}

export interface StimmAngaben {
  format: "stimme/1";
  name: string;
  bekannt_als: string[];
  bereich: Bereich;
  sprache: string;
  referenztext: string;
  herkunft?: Herkunft | null;
  sprecherprofil?: string | null;
  notiz: string;
}

export interface Stimme {
  id: string;
  name: string;
  bereich: StimmBereich;
  angaben: StimmAngaben | null;
  pfad: string | null;
  dauer_s: number | null;
}

export interface StimmWahl {
  art: "klon" | "katalog";
  knoten_id?: string | null;
  name?: string | null;
}

export interface Rolle {
  kennung: string;
  name: string;
  stimme: StimmWahl;
  tempo: number;
}

export interface Bericht {
  versuche: number;
  ersatz: boolean;
  stuecke: number;
  weg: Weg | null;
  stauchung: number;
  versatz_s: number;
}

export interface Abschnitt {
  nr: number;
  rolle: string;
  text: string;
  original: string | null;
  uebersetzt_aus: string | null;
  start: number | null;
  ende: number | null;
  pause_danach_s: number;
  gesprochen_als: string | null;
  dauer_s: number | null;
  bericht: Bericht | null;
}

export interface Plan {
  format: "vertonung/1";
  art: Art;
  name: string;
  quelle: { knoten_id: string; pfad: string; etag?: string | null } | null;
  quelle_dauer_s: number | null;
  sprache: string;
  ausgangssprache: string | null;
  rollen: Rolle[];
  abschnitte: Abschnitt[];
  ziel: { format: Format | "wie_quelle" };
  ergebnis: { knoten_id: string; pfad: string; dauer_s: number; erstellt_am: string; wellenform: number[] } | null;
  geaendert_am: string;
}

export interface AbschnittStand {
  nr: number;
  stand: Stand;
  hinweis: boolean;
  uebersetzen: boolean;
}

export interface PlanAntwort {
  id: string;
  stand: string;
  plan: Plan;
  staende: AbschnittStand[];
  haupt_id: string;
  haupt_pfad: string;
}

export interface Eintrag {
  id: string;
  name: string;
  art: Art;
  haupt_id: string;
  haupt_pfad: string;
  anfrage_id: string | null;
  rollen: { name: string; stimme: string }[];
  abschnitte: number;
  offen: number;
  hinweise: number;
  ergebnis_id: string | null;
  ergebnis_pfad: string | null;
  dauer_s: number | null;
  geaendert_am: string;
}

export interface Verzeichnis {
  gesamt: number;
  eintraege: Eintrag[];
  zahlen: Partial<Record<Art, number>>;
}

export interface PlanAnlegen {
  art: Art;
  name?: string;
  text?: string | null;
  quelle_id?: string | null;
  anfrage_id?: string | null;
  stimme?: StimmWahl | null;
  stimmen?: Record<string, StimmWahl>;
  sprache?: string | null;
  ausgangssprache?: string | null;
  format?: Format | null;
}

export const SPRACHEN: Record<string, string> = {
  de: "Deutsch", en: "Englisch", fr: "Französisch", es: "Spanisch", it: "Italienisch", nl: "Niederländisch", pt: "Portugiesisch",
  pl: "Polnisch", ru: "Russisch", tr: "Türkisch", ja: "Japanisch", zh: "Chinesisch",
};

export const ARTEN: Record<Art, { titel: string; symbol: string }> = {
  vorlesen: { titel: "Vorlesen", symbol: "fa-book-open-reader" },
  dialog: { titel: "Dialog", symbol: "fa-comments" },
  zeitgenau: { titel: "Zeitgenau", symbol: "fa-clock" },
};
