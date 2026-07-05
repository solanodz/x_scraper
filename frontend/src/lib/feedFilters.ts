import { isXSignal } from "@/lib/signalSource";
import type { SignalSummary } from "@/lib/types";

export type FeedSourceFilter = "" | "x" | "news";

export interface FeedFilterDraft {
  q: string;
  sourceType: FeedSourceFilter;
  sinceHours: number;
}

export interface FeedFilterQuery {
  q?: string;
  ticker?: string;
  source_type?: string;
  since_hours?: number;
}

export const EMPTY_FEED_FILTERS: FeedFilterDraft = {
  q: "",
  sourceType: "",
  sinceHours: 0,
};

export const FEED_TIME_OPTIONS: { value: number; label: string }[] = [
  { value: 0, label: "Todo el período" },
  { value: 24, label: "Últimas 24 h" },
  { value: 168, label: "Últimos 7 días" },
  { value: 720, label: "Últimos 30 días" },
];

export const FEED_SOURCE_OPTIONS: { value: FeedSourceFilter; label: string }[] = [
  { value: "", label: "Todas las fuentes" },
  { value: "news", label: "Noticias" },
  { value: "x", label: "X / tweets" },
];

function normalizeTicker(value: string): string {
  return value.trim().replace(/^\$/, "").toUpperCase();
}

function keywordTerms(query: string): string[] {
  return query
    .trim()
    .split(/\s+/)
    .map((part) => part.trim())
    .filter(Boolean);
}

/** Barra unificada: $NVDA / NVDA → ticker; $NVDA earnings → ticker + keywords. */
export function parseSearchInput(
  raw: string,
): Pick<FeedFilterQuery, "q" | "ticker"> {
  const trimmed = raw.trim();
  if (!trimmed) return {};

  const tickerWithKeywords = trimmed.match(/^\$([A-Za-z]{1,10})(?:\s+(.+))?$/);
  if (tickerWithKeywords) {
    const result: FeedFilterQuery = {
      ticker: tickerWithKeywords[1].toUpperCase(),
    };
    const keywords = tickerWithKeywords[2]?.trim();
    if (keywords) result.q = keywords;
    return result;
  }

  if (/^[A-Za-z]{1,5}$/.test(trimmed)) {
    return { ticker: normalizeTicker(trimmed) };
  }

  return { q: trimmed };
}

/** Prefijo activo tras $ al final del input (null si no hay modo ticker). */
export function activeTickerPrefix(value: string): string | null {
  const match = value.match(/\$([A-Za-z]*)$/);
  if (!match) return null;
  return match[1].toUpperCase();
}

export function replaceActiveTicker(value: string, symbol: string): string {
  if (!value.match(/\$[A-Za-z]*$/)) return `$${symbol}`;
  return value.replace(/\$[A-Za-z]*$/, `$${symbol}`);
}

function searchableText(signal: SignalSummary): string {
  return [
    signal.title,
    signal.summary,
    signal.body,
    signal.raw_content,
    signal.topic,
    signal.username,
    ...signal.cashtags,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function matchesSourceType(
  signal: SignalSummary,
  sourceType: FeedSourceFilter,
): boolean {
  if (!sourceType) return true;
  const resolved = signal.source_type || "x";
  if (sourceType === "x") return isXSignal(resolved);
  if (sourceType === "news") return !isXSignal(resolved);
  return resolved === sourceType;
}

function matchesSinceHours(signal: SignalSummary, sinceHours: number): boolean {
  if (!sinceHours) return true;
  const published = new Date(signal.published_at).getTime();
  if (Number.isNaN(published)) return true;
  return published >= Date.now() - sinceHours * 60 * 60 * 1000;
}

export function draftToQuery(draft: FeedFilterDraft): FeedFilterQuery {
  const query: FeedFilterQuery = { ...parseSearchInput(draft.q) };
  if (draft.sourceType) query.source_type = draft.sourceType;
  if (draft.sinceHours > 0) query.since_hours = draft.sinceHours;
  return query;
}

export function hasActiveFilters(query: FeedFilterQuery): boolean {
  return Object.keys(query).length > 0;
}

export function activeFilterLabels(query: FeedFilterQuery): string[] {
  const labels: string[] = [];
  if (query.ticker) labels.push(`Ticker: $${query.ticker}`);
  if (query.q) labels.push(`Búsqueda: ${query.q}`);
  if (query.source_type) {
    const option = FEED_SOURCE_OPTIONS.find((o) => o.value === query.source_type);
    labels.push(`Fuente: ${option?.label ?? query.source_type}`);
  }
  if (query.since_hours) {
    const option = FEED_TIME_OPTIONS.find((o) => o.value === query.since_hours);
    labels.push(option?.label ?? `${query.since_hours}h`);
  }
  return labels;
}

export function matchesFeedFilters(
  signal: SignalSummary,
  query: FeedFilterQuery,
): boolean {
  if (!hasActiveFilters(query)) return true;

  for (const term of keywordTerms(query.q ?? "")) {
    if (!searchableText(signal).includes(term.toLowerCase())) {
      return false;
    }
  }

  if (query.ticker) {
    const normalized = normalizeTicker(query.ticker);
    const hasTicker = signal.cashtags.some(
      (tag) => tag.replace(/^\$/, "").toUpperCase() === normalized,
    );
    if (!hasTicker) return false;
  }

  if (query.source_type) {
    if (
      !matchesSourceType(signal, query.source_type as FeedSourceFilter)
    ) {
      return false;
    }
  }

  if (query.since_hours) {
    if (!matchesSinceHours(signal, query.since_hours)) return false;
  }

  return true;
}
