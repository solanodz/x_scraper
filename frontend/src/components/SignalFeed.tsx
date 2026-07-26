"use client";

import { fetchEventSource } from "@microsoft/fetch-event-source";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  authHeaders,
  createSignalStreamUrl,
  fetchOperatorSettings,
  fetchSignalCount,
  fetchSignals,
  fetchTickerWatch,
  getAccessToken,
  isSupabaseConfigured,
  patchOperatorSettings,
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
import { FeedRowSkeleton } from "@/components/TerminalSkeleton";

/** Primera página chica para TTFP; el resto llega al scrollear (keyset `before`). */
const FEED_PAGE_SIZE = 20;

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

function newestPublishedAt(signals: SignalSummary[]): string | null {
  if (signals.length === 0) return null;
  let best = signals[0].published_at;
  let bestMs = new Date(best).getTime();
  for (const signal of signals) {
    const ms = new Date(signal.published_at).getTime();
    if (ms > bestMs) {
      best = signal.published_at;
      bestMs = ms;
    }
  }
  return best;
}

function oldestPublishedAt(signals: SignalSummary[]): string | null {
  if (signals.length === 0) return null;
  let oldest = signals[0].published_at;
  let oldestMs = new Date(oldest).getTime();
  for (const signal of signals) {
    const ms = new Date(signal.published_at).getTime();
    if (ms < oldestMs) {
      oldest = signal.published_at;
      oldestMs = ms;
    }
  }
  return oldest;
}

export default function SignalFeed({
  selectedId,
  onSelectSignal,
}: SignalFeedProps) {
  const [signals, setSignals] = useState<SignalSummary[]>([]);
  const [totalAvailable, setTotalAvailable] = useState<number | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [filterDraft, setFilterDraft] =
    useState<FeedFilterDraft>(EMPTY_FEED_FILTERS);
  const [activeFilters, setActiveFilters] = useState<FeedFilterQuery>({});
  const [watchSymbols, setWatchSymbols] = useState<string[]>([]);
  const [watchLoaded, setWatchLoaded] = useState(false);
  const [streamSince, setStreamSince] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const loadingMoreRef = useRef(false);
  const hasMoreRef = useRef(false);
  const oldestCursorRef = useRef<string | null>(null);
  const signalsRef = useRef<SignalSummary[]>([]);

  const watchEmptyActive =
    Boolean(activeFilters.tickers) &&
    (activeFilters.tickers?.length ?? 0) === 0;

  const loadSignals = useCallback(async (filters: FeedFilterQuery) => {
    if (filters.tickers !== undefined && filters.tickers.length === 0) {
      setSignals([]);
      signalsRef.current = [];
      setTotalAvailable(0);
      setHasMore(false);
      hasMoreRef.current = false;
      oldestCursorRef.current = null;
      setStreamSince(null);
      setError(null);
      setLoading(false);
      setLoadingMore(false);
      return;
    }
    setStreamSince(null);
    setTotalAvailable(null);
    try {
      // Primer paint: solo la lista (count va en background — era el otro cuello).
      const data = await fetchSignals(FEED_PAGE_SIZE, filters, 0, {
        includeClusterSources: false,
      });
      setSignals(data);
      signalsRef.current = data;
      oldestCursorRef.current = oldestPublishedAt(data);
      const more = data.length >= FEED_PAGE_SIZE;
      setHasMore(more);
      hasMoreRef.current = more;
      setError(null);
      setStreamSince(newestPublishedAt(data) ?? new Date().toISOString());
      setLoading(false);

      void fetchSignalCount(filters)
        .then((total) => {
          setTotalAvailable(total);
          const stillMore = data.length < total;
          setHasMore(stillMore);
          hasMoreRef.current = stillMore;
        })
        .catch(() => {
          /* el hasMore por tamaño de página alcanza */
        });
    } catch {
      setError("Failed to load signals");
      setTotalAvailable(null);
      setHasMore(false);
      hasMoreRef.current = false;
      oldestCursorRef.current = null;
      setStreamSince(null);
      setLoading(false);
    } finally {
      setLoadingMore(false);
    }
  }, []);

  const loadMoreSignals = useCallback(async () => {
    if (
      loadingMoreRef.current ||
      !hasMoreRef.current ||
      watchEmptyActive ||
      !oldestCursorRef.current
    ) {
      return;
    }
    loadingMoreRef.current = true;
    setLoadingMore(true);
    try {
      const data = await fetchSignals(FEED_PAGE_SIZE, activeFilters, 0, {
        before: oldestCursorRef.current,
        includeClusterSources: false,
      });
      if (data.length === 0) {
        setHasMore(false);
        hasMoreRef.current = false;
        return;
      }
      const merged = mergeSignalLists(signalsRef.current, data);
      signalsRef.current = merged;
      setSignals(merged);
      oldestCursorRef.current = oldestPublishedAt(merged);
      const more = data.length >= FEED_PAGE_SIZE;
      setHasMore(more);
      hasMoreRef.current = more;
      if (totalAvailable != null && merged.length >= totalAvailable) {
        setHasMore(false);
        hasMoreRef.current = false;
      }
    } catch {
      setError("Failed to load signals");
    } finally {
      loadingMoreRef.current = false;
      setLoadingMore(false);
    }
  }, [activeFilters, totalAvailable, watchEmptyActive]);

  useEffect(() => {
    let cancelled = false;
    fetchTickerWatch()
      .then((entries) => {
        if (cancelled) return;
        setWatchSymbols(entries.map((e) => e.symbol));
        setWatchLoaded(true);
      })
      .catch(() => {
        if (cancelled) return;
        setWatchSymbols([]);
        setWatchLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void fetchOperatorSettings()
      .then((res) => {
        if (cancelled) return;
        const watchOnly = Boolean(res.settings.feed_filters?.watchOnly);
        setFilterDraft((prev) => {
          if (prev.watchOnly === watchOnly) return prev;
          return { ...prev, watchOnly };
        });
      })
      .catch(() => {
        /* defaults */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    loadSignals(activeFilters);
  }, [loadSignals, activeFilters]);

  useEffect(() => {
    const root = scrollRef.current;
    const sentinel = sentinelRef.current;
    if (!root || !sentinel || loading || watchEmptyActive) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          void loadMoreSignals();
        }
      },
      { root, rootMargin: "320px 0px", threshold: 0 },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [loadMoreSignals, loading, watchEmptyActive, signals.length, streamSince]);

  useEffect(() => {
    if (!streamSince || watchEmptyActive) {
      setConnected(false);
      return;
    }

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

      await fetchEventSource(createSignalStreamUrl(streamSince), {
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
            setSignals((prev) => {
              const next = mergeSignal(prev, signal);
              signalsRef.current = next;
              return next;
            });
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
  }, [activeFilters, streamSince, watchEmptyActive]);

  function applyFilters(override?: FeedFilterDraft) {
    const next = override ?? filterDraft;
    const prevWatchOnly = filterDraft.watchOnly;
    if (override) setFilterDraft(next);
    setActiveFilters(draftToQuery(next, watchSymbols));
    setStreamSince(null);
    setLoading(true);
    if (next.watchOnly !== prevWatchOnly) {
      void patchOperatorSettings({
        feed_filters: { watchOnly: next.watchOnly },
      }).catch(() => {
        /* ignore */
      });
    }
  }

  function clearFilters() {
    const wasWatchOnly = filterDraft.watchOnly;
    setFilterDraft(EMPTY_FEED_FILTERS);
    setActiveFilters({});
    setStreamSince(null);
    setLoading(true);
    if (wasWatchOnly) {
      void patchOperatorSettings({
        feed_filters: { watchOnly: false },
      }).catch(() => {
        /* ignore */
      });
    }
  }

  useEffect(() => {
    if (!watchLoaded || !filterDraft.watchOnly) return;
    setActiveFilters(draftToQuery(filterDraft, watchSymbols));
    setStreamSince(null);
    setLoading(true);
  }, [watchSymbols, watchLoaded, filterDraft.watchOnly]); // eslint-disable-line react-hooks/exhaustive-deps -- Watch + hydrate

  const filterLabels = activeFilterLabels(activeFilters);

  return (
    <section className="flex h-full min-h-0 flex-col bg-zinc-900">
      <div className="flex items-center justify-between border-b border-zinc-800 px-3 py-1.5">
        <div className="flex min-w-0 items-baseline gap-2">
          <h2 className="font-sans text-xs font-semibold uppercase tracking-wider text-zinc-400">
            Signal Feed
          </h2>
          {!loading && !error && (
            <span className="truncate font-mono text-[10px] text-zinc-500">
              {signals.length.toLocaleString("es-AR")}
              {totalAvailable != null
                ? ` de ${totalAvailable.toLocaleString("es-AR")}`
                : ""}{" "}
              en pantalla
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
        watchCount={watchLoaded ? watchSymbols.length : null}
      />

      {filterLabels.length > 0 && (
        <div className="flex flex-wrap gap-1.5 border-b border-zinc-800/60 px-3 py-1.5">
          {filterLabels.map((label) => (
            <span
              key={label}
              className="border border-zinc-700 bg-zinc-900 px-1.5 py-0.5 font-mono text-[9px] text-zinc-400"
            >
              {label}
            </span>
          ))}
        </div>
      )}

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
        {loading && !watchEmptyActive && <FeedRowSkeleton rows={8} />}
        {error && (
          <p className="px-3 py-4 font-mono text-xs text-red-400">{error}</p>
        )}
        {!loading && !error && watchEmptyActive && (
          <div className="space-y-2 px-3 py-6">
            <p className="font-mono text-xs text-zinc-300">
              Tu Ticker Watch está vacío.
            </p>
            <p className="font-mono text-[11px] leading-relaxed text-zinc-500">
              Agregá símbolos desde Watch en el header para filtrar el Signal
              Feed a tus tickers. Mientras tanto no se muestra el feed general
              para no mezclarlo con &quot;Mis tickers&quot;.
            </p>
          </div>
        )}
        {!loading && !error && !watchEmptyActive && signals.length === 0 && (
          <p className="px-3 py-4 font-mono text-xs text-zinc-500">
            {hasActiveFilters(activeFilters)
              ? "Sin resultados para estos filtros."
              : "No signals yet. Run Refresh to ingest."}
          </p>
        )}
        {!loading &&
          !error &&
          !watchEmptyActive &&
          signals.map((signal) => (
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
                  <span className="font-mono text-xs font-semibold text-zinc-300">
                    {displayAuthor(signal.username, signal.source_type)}
                  </span>
                  <span className="shrink-0 border border-zinc-700 px-1 font-mono text-[9px] uppercase text-zinc-500">
                    {sourceBadgeLabel(signal.source_type)}
                  </span>
                  {clusterSourcesLabel(signal.cluster_sources) && (
                    <span className="shrink-0 border border-zinc-700 bg-zinc-900 px-1 font-mono text-[9px] text-zinc-400">
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
        {!loading && !error && !watchEmptyActive && hasMore && (
          <div
            ref={sentinelRef}
            className="flex items-center justify-center px-3 py-3"
            aria-hidden
          >
            {loadingMore ? (
              <span className="font-mono text-[10px] text-zinc-500">
                Cargando más…
              </span>
            ) : (
              <span className="font-mono text-[10px] text-zinc-600">
                Scroll para cargar más
              </span>
            )}
          </div>
        )}
        {!loading &&
          !error &&
          !watchEmptyActive &&
          !hasMore &&
          signals.length > 0 && (
            <p className="px-3 py-3 text-center font-mono text-[10px] text-zinc-600">
              Fin del feed
            </p>
          )}
      </div>
    </section>
  );
}
