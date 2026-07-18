"use client";

import { useEffect, useState } from "react";
import { TickerChart } from "@/components/TickerChart";
import { TickerChartToolbar } from "@/components/TickerChartToolbar";
import TickerLogo from "@/components/TickerLogo";
import { useLiveTickerMarket } from "@/hooks/useLiveTickerMarket";
import {
  formatQuoteChangePercent,
  formatQuotePrice,
} from "@/lib/marketRefresh";
import {
  loadTickerChartPrefs,
  saveTickerChartPrefs,
  type TickerChartPrefs,
} from "@/lib/tickerChartPrefs";

interface TickerChartModalProps {
  symbol: string;
  onClose: () => void;
}

export default function TickerChartModal({
  symbol,
  onClose,
}: TickerChartModalProps) {
  const [chartPrefs, setChartPrefs] = useState<TickerChartPrefs>(() =>
    loadTickerChartPrefs(),
  );

  const { quote, candles, candlesLoading, candlesError } = useLiveTickerMarket(
    symbol,
    { period: chartPrefs.period, interval: chartPrefs.interval },
  );

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="flex h-[min(88vh,820px)] w-full max-w-5xl flex-col overflow-hidden rounded-lg border border-zinc-700 bg-zinc-950 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`${symbol} chart`}
      >
        <header className="flex shrink-0 items-center justify-between border-b border-zinc-800 px-4 py-2">
          <div className="flex items-center gap-2">
            <TickerLogo symbol={symbol} logoUrl={quote?.logo} size="md" />
            <span className="font-mono text-sm font-semibold text-amber-400">
              ${symbol}
            </span>
            {quote?.available && quote.price != null && (
              <span className="font-mono text-sm text-zinc-200">
                {formatQuotePrice(quote.price)}
              </span>
            )}
            {quote?.available && quote.change_percent != null && (
              <span
                className={`font-mono text-xs ${
                  quote.change_percent >= 0 ? "text-emerald-400" : "text-red-400"
                }`}
              >
                {formatQuoteChangePercent(quote.change_percent)}
              </span>
            )}
            <span className="font-mono text-[10px] text-zinc-500">
              Ticker Chart · ~15m delayed
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-zinc-700 px-2 py-0.5 font-mono text-xs text-zinc-400 transition-colors hover:border-zinc-500 hover:text-zinc-200"
          >
            Esc
          </button>
        </header>

        <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
          <TickerChartToolbar
            value={chartPrefs}
            onChange={(next) => {
              setChartPrefs(next);
              saveTickerChartPrefs(next);
            }}
            persist
          />
          {candlesLoading && candles.length === 0 ? (
            <p className="py-20 text-center font-mono text-xs text-zinc-500">
              Cargando velas…
            </p>
          ) : candlesError ? (
            <p className="py-12 text-center font-mono text-xs text-red-400">
              {candlesError}
            </p>
          ) : (
            <TickerChart
              symbol={symbol}
              candles={candles}
              indicators={chartPrefs}
              height={520}
            />
          )}
        </div>
      </div>
    </div>
  );
}
