"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import ProvenanceChip from "@/components/ProvenanceChip";
import { QuoteStripSkeleton } from "@/components/TerminalSkeleton";
import TickerChartModal from "@/components/TickerChartModal";
import TickerLogo from "@/components/TickerLogo";
import { fetchWatchlistQuotes } from "@/lib/api";
import { MARKET_QUOTE_POLL_MS } from "@/lib/marketRefresh";
import {
  readCachedWatchlistQuotes,
  writeCachedWatchlistQuotes,
} from "@/lib/quoteCache";
import type { Quote } from "@/lib/types";

const POLL_INTERVAL_MS = MARKET_QUOTE_POLL_MS;

function formatPrice(price: number): string {
  return price.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatChangePercent(pct: number): string {
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

export default function QuoteStrip() {
  const [quotes, setQuotes] = useState<Quote[]>(
    () => readCachedWatchlistQuotes() ?? [],
  );
  const [unavailable, setUnavailable] = useState(false);
  const [loading, setLoading] = useState(
    () => (readCachedWatchlistQuotes() ?? []).length === 0,
  );
  const [chartSymbol, setChartSymbol] = useState<string | null>(null);

  const loadQuotes = useCallback(async () => {
    try {
      const data = await fetchWatchlistQuotes();
      setQuotes(data);
      setUnavailable(data.length === 0);
      if (data.length > 0) writeCachedWatchlistQuotes(data);
    } catch {
      // Keep stale cache on network blip; only mark unavailable if empty.
      setQuotes((prev) => {
        if (prev.length === 0) {
          queueMicrotask(() => setUnavailable(true));
        }
        return prev;
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadQuotes();
    const interval = setInterval(() => void loadQuotes(), POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [loadQuotes]);

  const carouselDuration = useMemo(
    () => Math.max(48, quotes.length * 2.8),
    [quotes.length],
  );

  const carouselItems = useMemo(
    () => (quotes.length > 0 ? [...quotes, ...quotes] : []),
    [quotes],
  );

  return (
    <>
      <div className="border-b border-zinc-800 bg-zinc-950">
        <div className="flex items-center gap-3 px-4 py-1.5">
          {!loading && !unavailable && quotes.length > 0 && (
            <ProvenanceChip
              provenance={
                quotes.find((q) => q.provenance)?.provenance ?? {
                  kind: "market_data",
                  source:
                    quotes.find((q) => q.source)?.source || "unknown",
                  delay_label: "~15m",
                }
              }
              className="shrink-0"
            />
          )}

          {loading && <QuoteStripSkeleton />}

          {!loading && unavailable && (
            <span className="font-mono text-[11px] text-zinc-500">
              Cotizaciones no disponibles — Market Data offline o sin símbolos
            </span>
          )}

          {!loading && !unavailable && quotes.length > 0 && (
            <div className="quote-carousel-mask min-w-0 flex-1">
              <div
                className="quote-carousel-track flex w-max items-center gap-6"
                style={{
                  animationDuration: `${carouselDuration}s`,
                }}
              >
                {carouselItems.map((quote, index) => (
                  <QuoteItem
                    key={`${quote.symbol}-${index}`}
                    quote={quote}
                    onSelect={setChartSymbol}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {chartSymbol && (
        <TickerChartModal
          symbol={chartSymbol}
          onClose={() => setChartSymbol(null)}
        />
      )}
    </>
  );
}

function QuoteItem({
  quote,
  onSelect,
}: {
  quote: Quote;
  onSelect: (symbol: string) => void;
}) {
  const hasPrice = quote.available !== false && quote.price != null;
  const positive = (quote.change_percent ?? 0) >= 0;
  const colorClass = positive ? "text-emerald-400" : "text-red-400";

  return (
    <button
      type="button"
      onClick={() => onSelect(quote.symbol)}
      className="group flex shrink-0 items-center gap-2 px-1.5 py-0.5 font-mono text-[11px] transition-colors hover:bg-zinc-900"
      title={`Ver gráfico de ${quote.symbol}`}
    >
      <TickerLogo symbol={quote.symbol} logoUrl={quote.logo} size="xs" />
      <span className="font-semibold text-zinc-300 group-hover:text-zinc-300">
        {quote.symbol}
      </span>
      {hasPrice ? (
        <>
          <span className="text-zinc-100">${formatPrice(quote.price!)}</span>
          <span className={colorClass}>
            {formatChangePercent(quote.change_percent ?? 0)}
          </span>
        </>
      ) : (
        <span className="text-zinc-600">—</span>
      )}
    </button>
  );
}
