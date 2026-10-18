// Stimmen für Auswahlfelder, einmal geladen und geteilt: Katalog (feste Stimmen des Sprechdienstes), fremde und private
// Klonstimmen. Eine Wahl hat einen Schlüssel ("katalog:serena", "klon:<kennung>") wie im Backend.
import * as api from "./api";
import type { Stimme, StimmWahl } from "./typen";

export const stimmenListe = $state({ katalog: [] as Stimme[], fremd: [] as Stimme[], privat: [] as Stimme[], geladen: false, fehler: "" });

export async function stimmenLaden(): Promise<void> {
  const [k, f, p] = await Promise.allSettled([api.stimmen("katalog"), api.stimmen("fremd"), api.stimmen("privat")]);
  stimmenListe.katalog = k.status === "fulfilled" ? k.value : [];
  stimmenListe.fremd = f.status === "fulfilled" ? f.value : [];
  stimmenListe.privat = p.status === "fulfilled" ? p.value : [];
  stimmenListe.fehler = k.status === "rejected" ? (k.reason as Error).message : "";
  stimmenListe.geladen = true;
}

export function schluessel(w: StimmWahl | null | undefined): string {
  if (!w) return "";
  return w.art === "klon" ? `klon:${w.knoten_id}` : `katalog:${w.name}`;
}

export function alsWahl(s: string): StimmWahl {
  const [art, rest] = [s.slice(0, s.indexOf(":")), s.slice(s.indexOf(":") + 1)];
  return art === "klon" ? { art: "klon", knoten_id: rest } : { art: "katalog", name: rest };
}

export function stimmOptionen(): { wert: string; titel: string; hinweis?: string }[] {
  return [
    ...stimmenListe.fremd.map((s) => ({ wert: `klon:${s.id}`, titel: `${s.name} · fremd` })),
    ...stimmenListe.privat.map((s) => ({ wert: `klon:${s.id}`, titel: `${s.name} · privat` })),
    ...stimmenListe.katalog.map((s) => ({ wert: `katalog:${s.name}`, titel: `${s.name} · Katalog` })),
  ];
}

export function stimmName(w: StimmWahl | null | undefined): string {
  const s = schluessel(w);
  return stimmOptionen().find((o) => o.wert === s)?.titel ?? (w?.art === "katalog" ? `${w.name} · Katalog` : "Klonstimme");
}
