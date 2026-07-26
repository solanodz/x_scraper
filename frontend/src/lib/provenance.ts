import type { Provenance } from "@/lib/types";

const KIND_LABELS: Record<string, string> = {
  market_data: "Market Data",
  fundamentals: "Fundamentals",
  fx: "FX",
  corpus_stats: "Corpus stats",
  chart_plan: "Chart Plan",
};

const SOURCE_LABELS: Record<string, string> = {
  finnhub: "Finnhub",
  yfinance: "yfinance",
  alpha_vantage: "Alpha Vantage",
  "dolarapi.com": "dolarapi",
  dolarapi: "dolarapi",
  "frankfurter.app": "Frankfurter",
  frankfurter: "Frankfurter",
  none: "N/A",
  unknown: "desconocido",
};

export function normalizeProvenance(raw: unknown): Provenance | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  const kind = typeof obj.kind === "string" ? obj.kind.trim() : "";
  const source = typeof obj.source === "string" ? obj.source.trim() : "";
  if (!kind || !source) return null;
  const out: Provenance = { kind, source };
  if (typeof obj.as_of === "string" && obj.as_of.trim()) {
    out.as_of = obj.as_of.trim();
  }
  if (typeof obj.delay_label === "string" && obj.delay_label.trim()) {
    out.delay_label = obj.delay_label.trim();
  }
  if (typeof obj.note === "string" && obj.note.trim()) {
    out.note = obj.note.trim();
  }
  return out;
}

function formatClock(asOf?: string | null): string | null {
  if (!asOf) return null;
  try {
    const d = new Date(asOf);
    if (Number.isNaN(d.getTime())) return null;
    return d.toLocaleTimeString("es-AR", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return null;
  }
}

/** Etiqueta corta: `Market Data · Finnhub · delay ~15m · 14:02`. */
export function formatProvenanceLabel(
  provenance: Provenance | null | undefined,
): string {
  if (!provenance) return "";
  const kind = KIND_LABELS[provenance.kind] ?? provenance.kind;
  const source = SOURCE_LABELS[provenance.source] ?? provenance.source;
  const parts = [kind, source];
  if (provenance.delay_label) parts.push(`delay ${provenance.delay_label}`);
  const clock = formatClock(provenance.as_of);
  if (clock) parts.push(clock);
  if (provenance.note) parts.push(provenance.note);
  return parts.join(" · ");
}
