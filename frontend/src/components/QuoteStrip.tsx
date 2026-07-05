"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import TickerChartModal from "@/components/TickerChartModal";
import { fetchWatchlistQuotes } from "@/lib/api";
import type { Quote } from "@/lib/types";

const POLL_INTERVAL_MS = 900_000; // 15 min — Finnhub + server cache

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
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [unavailable, setUnavailable] = useState(false);
  const [loading, setLoading] = useState(true);
  const [chartSymbol, setChartSymbol] = useState<string | null>(null);

  const loadQuotes = useCallback(async () => {
    try {
      const data = await fetchWatchlistQuotes();
      setQuotes(data);
      setUnavailable(data.length === 0);
    } catch {
      setQuotes([]);
      setUnavailable(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadQuotes();
    const interval = setInterval(loadQuotes, POLL_INTERVAL_MS);
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
            <span className="shrink-0 rounded border border-zinc-700 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wide text-zinc-500">
              15m delayed
            </span>
          )}

          {loading && (
            <span className="font-mono text-[11px] text-zinc-500">
              Loading quotes…
            </span>
          )}

          {!loading && unavailable && (
            <span className="font-mono text-[11px] text-zinc-500">
              Market data unavailable
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
      className="group flex shrink-0 items-baseline gap-2 rounded px-1.5 py-0.5 font-mono text-[11px] transition-colors hover:bg-zinc-900"
      title={`Ver gráfico de ${quote.symbol}`}
    >
      <span className="font-semibold text-zinc-300 group-hover:text-amber-400">
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
