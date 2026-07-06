/** Utilidades para renderizado visual del Briefing (secciones + sentimiento). */

export interface BriefingSection {
  title: string;
  body: string;
}

export function splitBriefingSections(content: string): BriefingSection[] {
  const trimmed = content.trim();
  if (!trimmed) return [];

  const chunks = trimmed.split(/^## /m);
  const sections: BriefingSection[] = [];

  for (const chunk of chunks) {
    if (!chunk.trim()) continue;
    const newline = chunk.indexOf("\n");
    if (newline === -1) {
      sections.push({ title: chunk.trim(), body: "" });
      continue;
    }
    sections.push({
      title: chunk.slice(0, newline).trim(),
      body: chunk.slice(newline + 1).trim(),
    });
  }

  return sections;
}

export function normalizeSectionTitle(title: string): string {
  return title.trim().toLowerCase();
}

export function isPrioritySection(title: string): boolean {
  return normalizeSectionTitle(title) === "prioridad alta";
}

const PRIORITY_FIELD_LABELS = new Set([
  "hecho",
  "implicación",
  "qué mirar",
  "riesgo principal",
]);

/** ### bajo Prioridad alta que nombra un Ticker (no Hecho / Implicación / etc.). */
export function isPriorityTickerLabel(label: string): boolean {
  const norm = label.trim().toLowerCase();
  if (PRIORITY_FIELD_LABELS.has(norm)) return false;
  const trimmed = label.trim();
  return /^[A-Z][A-Z0-9.\-^]{0,12}$/.test(trimmed);
}

export function isDeltaSection(title: string): boolean {
  return normalizeSectionTitle(title) === "desde el último briefing";
}

/** Títulos de sección — chip con fondo para legibilidad. */
export function briefingSectionTitleClass(title: string): string {
  const chip =
    "inline-block rounded-sm px-2.5 py-1 font-sans text-xs uppercase tracking-wide";
  if (isPrioritySection(title)) {
    return `${chip} mt-0 mb-3 bg-zinc-600/50 font-bold text-zinc-100`;
  }
  if (isDeltaSection(title)) {
    return `${chip} mb-2 mt-0 bg-zinc-700/60 font-semibold text-zinc-200`;
  }
  return `${chip} mb-2 mt-4 bg-zinc-800 font-semibold text-zinc-200 first:mt-0`;
}

/** Subtítulos ### (Hecho, Implicación, tickers, etc.). */
export function briefingSubheadingClass(
  label: string,
  inDeltaSection: boolean,
  inPrioritySection = false,
): string {
  const chip =
    "inline-block rounded-sm px-2 py-0.5 font-mono text-xs font-semibold";
  if (inDeltaSection) {
    const deltaTone = deltaSubheadingSentiment(label);
    if (deltaTone === "positive") {
      return `${chip} mb-1 mt-2 bg-emerald-950/50 ${sentimentTextClass.positive}`;
    }
    if (deltaTone === "negative") {
      return `${chip} mb-1 mt-2 bg-red-950/50 ${sentimentTextClass.negative}`;
    }
  }
  if (inPrioritySection && isPriorityTickerLabel(label)) {
    return `${chip} mb-2 mt-4 bg-slate-700 font-bold tracking-wide text-slate-100 first:mt-0`;
  }
  return `${chip} mb-1 mt-2.5 bg-zinc-800 text-zinc-200`;
}

/** Wrapper con resaltado sutil (delta) o panel (Prioridad alta). */
export function briefingSectionWrapperClass(title: string): string | null {
  const norm = normalizeSectionTitle(title);
  if (norm === "desde el último briefing") {
    return "mb-3 rounded-r-sm border-l-2 border-zinc-600/60 bg-zinc-900/40 py-2 pl-3 pr-1";
  }
  if (norm === "prioridad alta") {
    return "mb-3 rounded-sm border border-zinc-700 bg-zinc-700/25 py-3 px-3";
  }
  return null;
}

export type SentimentMarker = "positive" | "negative" | null;

const POS_PREFIX = "[+]";
const NEG_PREFIX = "[-]";

export function sentimentFromText(text: string): SentimentMarker {
  const t = text.trimStart();
  if (t.startsWith(POS_PREFIX)) return "positive";
  if (t.startsWith(NEG_PREFIX)) return "negative";
  return null;
}

export function stripSentimentMarker(text: string): string {
  return text
    .trimStart()
    .replace(/^\[\+\]\s?/, "")
    .replace(/^\[-\]\s?/, "")
    .trimStart();
}

export function alignmentSentiment(text: string): SentimentMarker {
  const lower = text.toLowerCase();
  if (lower.includes("alineación:") && lower.includes("refuerza")) {
    return "positive";
  }
  if (lower.includes("alineación:") && lower.includes("tensiona")) {
    return "negative";
  }
  return null;
}

/** Solo subsecciones del delta con tono semántico en el label. */
export function deltaSubheadingSentiment(label: string): SentimentMarker {
  const lower = label.toLowerCase();
  if (lower === "nuevo") return "positive";
  if (lower.includes("cambió el tono")) return "negative";
  return null;
}

export const sentimentTextClass: Record<
  NonNullable<SentimentMarker>,
  string
> = {
  positive: "text-emerald-300",
  negative: "text-red-500",
};

export const sentimentBlockClass: Record<
  NonNullable<SentimentMarker>,
  string
> = {
  positive:
    "border-l-2 border-emerald-500/80 bg-emerald-950/30 pl-2.5 py-1 rounded-r-sm",
  negative:
    "border-l-2 border-red-600 bg-red-950/50 pl-2.5 py-1 rounded-r-sm",
};

export function sentimentParagraphClass(text: string): string {
  const marker = sentimentFromText(text) ?? alignmentSentiment(text);
  const base = "mb-2 leading-relaxed last:mb-0 ";
  if (marker === "positive") {
    return `${base}${sentimentBlockClass.positive} ${sentimentTextClass.positive}`;
  }
  if (marker === "negative") {
    return `${base}${sentimentBlockClass.negative} ${sentimentTextClass.negative}`;
  }
  return `${base}text-zinc-200`;
}
