/**
 * Stale-while-revalidate cache for Quote Strip.
 * First paint can reuse last good watchlist while a fresh fetch runs.
 */

import type { Quote } from "@/lib/types";

const CACHE_KEY = "xscraper.quotes.watchlist.v1";
const MAX_AGE_MS = 15 * 60 * 1000; // align with backend quote TTL

type CachedWatchlist = {
  quotes: Quote[];
  savedAt: number;
};

export function readCachedWatchlistQuotes(): Quote[] | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CachedWatchlist;
    if (!Array.isArray(parsed.quotes) || typeof parsed.savedAt !== "number") {
      return null;
    }
    if (Date.now() - parsed.savedAt > MAX_AGE_MS) return null;
    return parsed.quotes;
  } catch {
    return null;
  }
}

export function writeCachedWatchlistQuotes(quotes: Quote[]): void {
  if (typeof window === "undefined") return;
  try {
    const payload: CachedWatchlist = { quotes, savedAt: Date.now() };
    window.sessionStorage.setItem(CACHE_KEY, JSON.stringify(payload));
  } catch {
    // quota / private mode
  }
}
