"use client";

import { useEffect, useState } from "react";
import { TickerChartStack } from "@/components/TickerChartStack";
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
import type { PriceCandle } from "@/lib/types";
import type { TickerChartIndicators } from "@/components/TickerChart";

interface TickerChartModalProps {
  symbol: string;
  onClose: () => void;
  /** Prefs controladas (p. ej. sync con Chart Plan). */
  prefs?: TickerChartPrefs;
  onPrefsChange?: (prefs: TickerChartPrefs) => void;
}

export default function TickerChartModal({
  symbol,
  onClose,
  prefs: controlledPrefs,
  onPrefsChange,
}: TickerChartModalProps) {
  const [internalPrefs, setInternalPrefs] = useState<TickerChartPrefs>(() =>
    loadTickerChartPrefs(),
  );
  const chartPrefs = controlledPrefs ?? internalPrefs;

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

  function handlePrefsChange(next: TickerChartPrefs) {
    if (onPrefsChange) {
      onPrefsChange(next);
    } else {
      setInternalPrefs(next);
      saveTickerChartPrefs(next);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-3 backdrop-blur-sm sm:p-6"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="flex h-[min(92vh,960px)] w-full max-w-7xl flex-col overflow-hidden rounded-lg border border-zinc-700 bg-zinc-950 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`${symbol} chart expandido`}
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

        <div className="flex min-h-0 flex-1 flex-col">
          <TickerChartToolbar
            value={chartPrefs}
            onChange={handlePrefsChange}
            persist={!onPrefsChange}
          />
          <div className="min-h-0 flex-1 p-3">
            {candlesLoading && candles.length === 0 ? (
              <p className="flex h-full items-center justify-center font-mono text-xs text-zinc-500">
                Cargando velas…
              </p>
            ) : candlesError ? (
              <p className="flex h-full items-center justify-center font-mono text-xs text-red-400">
                {candlesError}
              </p>
            ) : (
              <ExpandedChart
                symbol={symbol}
                candles={candles}
                indicators={chartPrefs}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function ExpandedChart({
  symbol,
  candles,
  indicators,
}: {
  symbol: string;
  candles: PriceCandle[];
  indicators: TickerChartIndicators;
}) {
  return (
    <TickerChartStack
      symbol={symbol}
      candles={candles}
      indicators={indicators}
      fillPrice
      oscillatorHeight={140}
      className="h-full min-h-[420px]"
    />
  );
}
