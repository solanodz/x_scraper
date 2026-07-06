"use client";

import { fetchEventSource } from "@microsoft/fetch-event-source";
import { useCallback, useEffect, useState } from "react";
import {
  authHeaders,
  createSignalStreamUrl,
  fetchSignalCount,
  fetchSignals,
  getAccessToken,
  isSupabaseConfigured,
} from "@/lib/api";
import {
  activeFilterLabels,
  draftToQuery,
  EMPTY_FEED_FILTERS,
  hasActiveFilters,
  matchesFeedFilters,
  type FeedFilterDraft,
  type FeedFilterQuery,
} from "@/lib/feedFilters";
import { formatEngagement, timeAgo, truncate } from "@/lib/format";
import {
  clusterSourcesLabel,
  displayAuthor,
  isXSignal,
  sourceBadgeLabel,
} from "@/lib/signalSource";
import type { SignalSummary } from "@/lib/types";
import SignalFeedFilters from "@/components/SignalFeedFilters";

const FEED_PAGE_SIZE = 200;

interface SignalFeedProps {
  selectedId: string | null;
  onSelectSignal: (idStr: string) => void;
}

function byPublishedDesc(a: SignalSummary, b: SignalSummary): number {
  return (
    new Date(b.published_at).getTime() - new Date(a.published_at).getTime()
  );
}

function mergeSignal(
  list: SignalSummary[],
  incoming: SignalSummary,
): SignalSummary[] {
  if (list.some((s) => s.id_str === incoming.id_str)) return list;

  let next = [...list];

  if (incoming.cluster_id) {
    const existingIdx = next.findIndex(
      (s) => s.cluster_id === incoming.cluster_id,
    );
    if (existingIdx >= 0) {
      const existing = next[existingIdx];
      if (
        new Date(incoming.published_at).getTime() <=
        new Date(existing.published_at).getTime()
      ) {
        return next;
      }
      next = next.filter((_, i) => i !== existingIdx);
    }
  }

  return [...next, incoming].sort(byPublishedDesc);
}

function mergeSignalLists(
  existing: SignalSummary[],
  incoming: SignalSummary[],
): SignalSummary[] {
  let next = existing;
  for (const signal of incoming) {
    next = mergeSignal(next, signal);
  }
  return next;
}

function displayHeadline(signal: SignalSummary): string {
  return signal.title?.trim() || signal.raw_content;
}

export default function SignalFeed({
  selectedId,
  onSelectSignal,
}: SignalFeedProps) {
  const [signals, setSignals] = useState<SignalSummary[]>([]);
  const [totalAvailable, setTotalAvailable] = useState<number | null>(null);
  const [loadedOffset, setLoadedOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [filterDraft, setFilterDraft] =
    useState<FeedFilterDraft>(EMPTY_FEED_FILTERS);
  const [activeFilters, setActiveFilters] = useState<FeedFilterQuery>({});

  const loadSignals = useCallback(async (filters: FeedFilterQuery) => {
    try {
      const [data, total] = await Promise.all([
        fetchSignals(FEED_PAGE_SIZE, filters, 0),
        fetchSignalCount(filters),
      ]);
      setSignals(data);
      setLoadedOffset(data.length);
      setTotalAvailable(total);
      setError(null);
    } catch {
      setError("Failed to load signals");
      setTotalAvailable(null);
      setLoadedOffset(0);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, []);

  const loadMoreSignals = useCallback(async () => {
    if (loadingMore || totalAvailable == null || loadedOffset >= totalAvailable) {
      return;
    }
    setLoadingMore(true);
    try {
      const data = await fetchSignals(
        FEED_PAGE_SIZE,
        activeFilters,
        loadedOffset,
      );
      if (data.length > 0) {
        setSignals((prev) => mergeSignalLists(prev, data));
        setLoadedOffset((prev) => prev + data.length);
      }
    } catch {
      setError("Failed to load signals");
    } finally {
      setLoadingMore(false);
    }
  }, [activeFilters, loadedOffset, loadingMore, totalAvailable]);

  const loadAllSignals = useCallback(async () => {
    if (loadingMore || totalAvailable == null || loadedOffset >= totalAvailable) {
      return;
    }
    setLoadingMore(true);
    try {
      let offset = loadedOffset;
      const batches: SignalSummary[][] = [];
      while (offset < totalAvailable) {
        const data = await fetchSignals(FEED_PAGE_SIZE, activeFilters, offset);
        if (data.length === 0) break;
        batches.push(data);
        offset += data.length;
      }
      if (batches.length > 0) {
        setSignals((prev) => {
          let merged = prev;
          for (const batch of batches) {
            merged = mergeSignalLists(merged, batch);
          }
          return merged;
        });
        setLoadedOffset(offset);
      }
    } catch {
      setError("Failed to load signals");
    } finally {
      setLoadingMore(false);
    }
  }, [activeFilters, loadedOffset, loadingMore, totalAvailable]);

  useEffect(() => {
    loadSignals(activeFilters);
  }, [loadSignals, activeFilters]);

  useEffect(() => {
    const ctrl = new AbortController();
    let cancelled = false;

    async function connectStream() {
      if (isSupabaseConfigured()) {
        const token = await getAccessToken();
        if (!token) {
          setConnected(false);
          return;
        }
      }

      const headers = await authHeaders();

      await fetchEventSource(createSignalStreamUrl(), {
        headers,
        signal: ctrl.signal,
        onopen: async (res) => {
          if (cancelled) return;
          setConnected(res.ok);
        },
        onmessage: (ev) => {
          if (cancelled || ev.event !== "signal" || !ev.data) return;
          try {
            const signal = JSON.parse(ev.data) as SignalSummary;
            if (!matchesFeedFilters(signal, activeFilters)) return;
            setSignals((prev) => mergeSignal(prev, signal));
          } catch {
            // ignore malformed events
          }
        },
        onerror: () => {
          if (!cancelled) setConnected(false);
          throw new Error("SSE connection error");
        },
      });
    }

    connectStream().catch(() => {
      if (!cancelled) setConnected(false);
    });

    return () => {
      cancelled = true;
      ctrl.abort();
    };
  }, [activeFilters]);

  function applyFilters(override?: FeedFilterDraft) {
    const next = override ?? filterDraft;
    if (override) setFilterDraft(next);
    setActiveFilters(draftToQuery(next));
    setLoadedOffset(0);
    setLoading(true);
  }

  function clearFilters() {
    setFilterDraft(EMPTY_FEED_FILTERS);
    setActiveFilters({});
    setLoadedOffset(0);
    setLoading(true);
  }

  const filterLabels = activeFilterLabels(activeFilters);
  const hasMoreFromApi =
    totalAvailable != null && loadedOffset < totalAvailable;

  return (
    <section className="flex h-full min-h-0 flex-col bg-zinc-900">
      <div className="flex items-center justify-between border-b border-zinc-800 px-3 py-1.5">
        <div className="flex min-w-0 items-baseline gap-2">
          <h2 className="font-sans text-xs font-semibold uppercase tracking-wider text-amber-500">
            Signal Feed
          </h2>
          {!loading && totalAvailable != null && !error && (
            <span className="truncate font-mono text-[10px] text-zinc-500">
              {signals.length.toLocaleString("es-AR")} de{" "}
              {totalAvailable.toLocaleString("es-AR")} en pantalla
            </span>
          )}
        </div>
        <span
          className={`shrink-0 font-mono text-[10px] ${connected ? "text-emerald-500" : "text-zinc-600"}`}
        >
          {connected ? "● LIVE" : "○ OFFLINE"}
        </span>
      </div>

      <SignalFeedFilters
        draft={filterDraft}
        onDraftChange={setFilterDraft}
        onApply={applyFilters}
        onClear={clearFilters}
        hasActive={hasActiveFilters(activeFilters)}
      />

      {filterLabels.length > 0 && (
        <div className="flex flex-wrap gap-1.5 border-b border-zinc-800/60 px-3 py-1.5">
          {filterLabels.map((label) => (
            <span
              key={label}
              className="rounded border border-emerald-900/50 bg-emerald-950/20 px-1.5 py-0.5 font-mono text-[9px] text-emerald-400"
            >
              {label}
            </span>
          ))}
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading && (
          <p className="px-3 py-4 font-mono text-xs text-zinc-500">Loading…</p>
        )}
        {error && (
          <p className="px-3 py-4 font-mono text-xs text-red-400">{error}</p>
        )}
        {!loading && !error && signals.length === 0 && (
          <p className="px-3 py-4 font-mono text-xs text-zinc-500">
            {hasActiveFilters(activeFilters)
              ? "Sin resultados para estos filtros."
              : "No signals yet. Run Refresh to ingest."}
          </p>
        )}
        {signals.map((signal) => (
          <button
            key={signal.id_str}
            type="button"
            onClick={() => onSelectSignal(signal.id_str)}
            className={`w-full border-b border-zinc-800/60 px-3 py-2 text-left transition-colors hover:bg-zinc-800/50 ${
              selectedId === signal.id_str ? "bg-zinc-800/80" : ""
            }`}
          >
            <div className="flex items-baseline justify-between gap-2">
              <div className="flex min-w-0 items-center gap-1.5">
                <span className="font-mono text-xs font-semibold text-amber-400">
                  {displayAuthor(signal.username, signal.source_type)}
                </span>
                <span className="shrink-0 rounded border border-zinc-700 px-1 font-mono text-[9px] uppercase text-zinc-500">
                  {sourceBadgeLabel(signal.source_type)}
                </span>
                {clusterSourcesLabel(signal.cluster_sources) && (
                  <span className="shrink-0 rounded border border-amber-900/50 bg-amber-950/30 px-1 font-mono text-[9px] text-amber-500">
                    {clusterSourcesLabel(signal.cluster_sources)}
                  </span>
                )}
              </div>
              <span className="shrink-0 font-mono text-[10px] text-zinc-500">
                {timeAgo(signal.published_at)}
              </span>
            </div>
            <p className="mt-0.5 font-mono text-xs leading-relaxed text-zinc-300">
              {truncate(displayHeadline(signal))}
            </p>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              {signal.cashtags.map((tag) => (
                <span
                  key={tag}
                  className="font-mono text-[10px] text-emerald-500"
                >
                  {tag}
                </span>
              ))}
              {signal.topic?.trim() && (
                <span className="font-mono text-[10px] text-zinc-500">
                  {signal.topic.trim()}
                </span>
              )}
              <span className="ml-auto font-mono text-[10px] text-zinc-600">
                {isXSignal(signal.source_type) ? (
                  <>
                    ♥ {formatEngagement(signal.engagement.like_count)} · ↻{" "}
                    {formatEngagement(signal.engagement.retweet_count)}
                  </>
                ) : (
                  <span className="text-zinc-500">noticia</span>
                )}
              </span>
            </div>
          </button>
        ))}
        {!loading && !error && hasMoreFromApi && (
          <div className="flex flex-col gap-2 border-t border-zinc-800/60 px-3 py-3">
            <button
              type="button"
              onClick={() => void loadMoreSignals()}
              disabled={loadingMore}
              className="rounded border border-zinc-700 bg-zinc-900 px-3 py-2 font-mono text-[11px] text-zinc-300 transition-colors hover:border-amber-700 hover:text-amber-400 disabled:opacity-50"
            >
              {loadingMore
                ? "Cargando…"
                : `Cargar más (${Math.min(
                    FEED_PAGE_SIZE,
                    totalAvailable! - loadedOffset,
                  )} de ${(totalAvailable! - loadedOffset).toLocaleString("es-AR")} restantes)`}
            </button>
            {totalAvailable! - loadedOffset > FEED_PAGE_SIZE && (
              <button
                type="button"
                onClick={() => void loadAllSignals()}
                disabled={loadingMore}
                className="font-mono text-[10px] text-zinc-500 underline-offset-2 hover:text-amber-500 hover:underline disabled:opacity-50"
              >
                Cargar todas ({totalAvailable!.toLocaleString("es-AR")})
              </button>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
