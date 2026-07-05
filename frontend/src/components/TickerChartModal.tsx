"use client";

import { useEffect } from "react";
import { tradingViewSymbol } from "@/lib/tradingview";

interface TickerChartModalProps {
  symbol: string;
  onClose: () => void;
}

export default function TickerChartModal({
  symbol,
  onClose,
}: TickerChartModalProps) {
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

  const tvSymbol = encodeURIComponent(tradingViewSymbol(symbol));
  const chartSrc =
    `https://s.tradingview.com/widgetembed/?` +
    `symbol=${tvSymbol}&interval=D&hidesidetoolbar=0&hidetoptoolbar=0` +
    `&symboledit=1&saveimage=0&toolbarbg=09090b&theme=dark&style=1` +
    `&timezone=America%2FNew_York&withdateranges=1&hideideas=1&locale=en`;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="flex h-[min(82vh,720px)] w-full max-w-5xl flex-col overflow-hidden rounded-lg border border-zinc-700 bg-zinc-950 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`${symbol} chart`}
      >
        <header className="flex shrink-0 items-center justify-between border-b border-zinc-800 px-4 py-2">
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-sm font-semibold text-amber-400">
              {symbol}
            </span>
            <span className="font-mono text-[10px] text-zinc-500">
              TradingView · 15m delayed quotes
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
        <iframe
          title={`${symbol} chart`}
          src={chartSrc}
          className="min-h-0 flex-1 border-0"
        />
      </div>
    </div>
  );
}
