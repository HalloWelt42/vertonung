// Aufrufe der Schnittstelle der Vertonung (über `hole` der Schale: Anmeldung, Fehler, Verbindungsstand).
import { abfrage, hochladen, hole, json, type Auftrag } from "appkern-oberflaeche";
import type { Bereich, Plan, PlanAnlegen, PlanAntwort, Stimme, StimmAngaben, StimmBereich, Verzeichnis } from "./typen";

// Eine Datei aus der Kellerwolke (über eine Anfrage geöffnet): jeder Aufruf nennt die Anfrage.
export type AnfrageId = string | null | undefined;
const mit = (pfad: string, anfrage: AnfrageId) => `${pfad}${abfrage({ anfrage })}`;

// --- Stimmen ----------------------------------------------------------------------------------------------------

export const stimmen = (bereich: StimmBereich, suche = "") => hole<Stimme[]>(`/stimmen${abfrage({ bereich, suche })}`);
export const stimme = (id: string) => hole<Stimme>(`/stimmen/${id}`);
export const stimmeAendern = (id: string, angaben: StimmAngaben) =>
  hole<Stimme>(`/stimmen/${id}`, { method: "PATCH", ...json(angaben) });
export const stimmeLoeschen = (id: string) => hole<void>(`/stimmen/${id}`, { method: "DELETE" });
export const stimmeHochladen = (daten: Blob, name: string, bereich: Bereich, endung: string, referenztext = "") =>
  hochladen<Stimme>(`/api/v1/stimmen${abfrage({ name, bereich, endung, referenztext })}`, daten, name);
export const probeAdresse = (id: string) => `/api/v1/inhalt/stimmen/${id}/probe`;

// --- Pläne ------------------------------------------------------------------------------------------------------

export const plaene = (o: { art?: string | null; suche?: string; ab?: number; anzahl?: number }) =>
  hole<Verzeichnis>(`/plaene${abfrage(o)}`);
export const planAnlegen = (a: PlanAnlegen) => hole<PlanAntwort>("/plaene", { method: "POST", ...json(a) });
export const plan = (id: string, anfrage?: AnfrageId) => hole<PlanAntwort>(mit(`/plaene/${id}`, anfrage));
export const planAendern = (id: string, p: Plan, stand: string, anfrage?: AnfrageId) =>
  hole<PlanAntwort>(mit(`/plaene/${id}`, anfrage), { method: "PATCH", ...json({ plan: p, stand }) });
export const vertonen = (id: string, anfrage?: AnfrageId) =>
  hole<Auftrag>(mit(`/plaene/${id}/vertonen`, anfrage), { method: "POST" });
export const planLoeschen = (id: string, anfrage?: AnfrageId) =>
  hole<void>(mit(`/plaene/${id}`, anfrage), { method: "DELETE" });
export const abschnittAdresse = (id: string, nr: number, stand?: string | null) =>
  `/api/v1/inhalt/plaene/${id}/abschnitte/${nr}${abfrage({ v: stand })}`;
export const ergebnisAdresse = (id: string, anfrage?: AnfrageId, stand?: string | null) =>
  `/api/v1/inhalt/plaene/${id}/ergebnis${abfrage({ anfrage, v: stand })}`;

// --- Quelle und Einstellungen -----------------------------------------------------------------------------------

export const quelle = (knotenId: string, anfrage?: AnfrageId) =>
  hole<{ id: string; name: string; pfad: string; art: string; textquelle: string | null; sprecher: string[]; abschnitte: number;
         dauer_s: number | null; text: string | null; sprache: string | null }>(mit(`/quelle/${knotenId}`, anfrage));
export async function einstellungWert<T>(name: string): Promise<T | null> {
  const e = await hole<{ werte: Record<string, unknown> }>("/einstellungen");
  return (e.werte[name] as T) ?? null;
}
// Kein Transkript neben einer Aufnahme: das Transkribieren an die Transkription weitergeben
export const transkribierenLassen = (knotenId: string, anfrage?: AnfrageId) =>
  hole<{ anfrage: string }>(mit(`/quelle/${knotenId}/transkribieren`, anfrage), { method: "POST" });
// Der Plan neben einer Datei (Begleiter der Rolle vertonung), sonst null
export const planZurDatei = async (knotenId: string, anfrage?: AnfrageId) =>
  (await hole<{ id: string | null }>(mit(`/quelle/${knotenId}/plan`, anfrage))).id;
