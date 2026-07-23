"use client";

import { useRouter } from "next/navigation";
import { dossierPath } from "@/lib/dossierNav";
import { formatQuoteChangePercent } from "@/lib/marketRefresh";
import type { PriceChartArtifact } from "@/lib/types";

const WIDTH = 280;
const HEIGHT = 56;
const PAD_X = 2;
const PAD_Y = 4;

function sparklinePoints(closes: number[]): string | null {
  if (closes.length < 2) return null;
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const span = max - min || 1;
  const innerW = WIDTH - PAD_X * 2;
  const innerH = HEIGHT - PAD_Y * 2;

  return closes
    .map((close, i) => {
      const x = PAD_X + (i / (closes.length - 1)) * innerW;
      const y = PAD_Y + (1 - (close - min) / span) * innerH;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

function resolveChangePercent(artifact: PriceChartArtifact): number | null {
  if (
    typeof artifact.change_percent === "number" &&
    Number.isFinite(artifact.change_percent)
  ) {
    return artifact.change_percent;
  }
  const closes = artifact.candles.map((c) => c.close);
  if (closes.length < 2) return null;
  const start =
    typeof artifact.start_price === "number" &&
    Number.isFinite(artifact.start_price)
      ? artifact.start_price
      : closes[0];
  const end =
    typeof artifact.end_price === "number" && Number.isFinite(artifact.end_price)
      ? artifact.end_price
      : closes[closes.length - 1];
  if (!Number.isFinite(start) || start === 0) return null;
  return ((end - start) / start) * 100;
}

interface PriceChartCardProps {
  artifact: PriceChartArtifact;
}

const FX_CURRENCY_CODES = new Set([
  "USD",
  "ARS",
  "EUR",
  "GBP",
  "JPY",
  "BRL",
  "CNY",
  "MXN",
  "CLP",
  "UYU",
  "CAD",
  "AUD",
  "CHF",
  "NZD",
]);

export default function PriceChartCard({ artifact }: PriceChartCardProps) {
  const router = useRouter();
  const closes = artifact.candles.map((c) => c.close);
  const points = sparklinePoints(closes);
  const changePct = resolveChangePercent(artifact);
  const positive = (changePct ?? 0) >= 0;
  const stroke = positive ? "#34d399" : "#f87171";
  const endPrice =
    typeof artifact.end_price === "number" && Number.isFinite(artifact.end_price)
      ? artifact.end_price
      : closes[closes.length - 1];
  const symbol = artifact.symbol.trim().toUpperCase();
  // Divisas no tienen Dossier/Chart Plan — no navegar a /dossier?ticker=USD.
  const isFxCode = FX_CURRENCY_CODES.has(symbol);
  const openDossier = () => {
    if (isFxCode) return;
    router.push(dossierPath(artifact.symbol));
  };

  return (
    <button
      type="button"
      onClick={openDossier}
      disabled={isFxCode}
      className="group w-full max-w-sm rounded-lg border border-zinc-800 bg-zinc-950/80 px-3 py-2.5 text-left transition-colors hover:border-zinc-600 hover:bg-zinc-900/90 disabled:cursor-default disabled:hover:border-zinc-800 disabled:hover:bg-zinc-950/80"
      aria-label={
        isFxCode
          ? `Cotización FX ${artifact.symbol} (sin Dossier)`
          : `Abrir dossier de ${artifact.symbol}`
      }
    >
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <div className="flex min-w-0 items-baseline gap-2">
          <span className="font-mono text-sm font-semibold text-zinc-100">
            {artifact.symbol}
          </span>
          <span className="truncate font-mono text-[10px] uppercase tracking-wide text-zinc-500">
            {artifact.period}
            {artifact.interval ? ` · ${artifact.interval}` : ""}
          </span>
        </div>
        <div className="shrink-0 text-right font-mono text-[11px]">
          {Number.isFinite(endPrice) && (
            <span className="mr-2 text-zinc-300">${endPrice.toFixed(2)}</span>
          )}
          {changePct != null && (
            <span className={positive ? "text-emerald-400" : "text-red-400"}>
              {formatQuoteChangePercent(changePct)}
            </span>
          )}
        </div>
      </div>

      {points ? (
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="h-14 w-full"
          preserveAspectRatio="none"
          aria-hidden
        >
          <polyline
            fill="none"
            stroke={stroke}
            strokeWidth="1.5"
            strokeLinejoin="round"
            strokeLinecap="round"
            points={points}
            vectorEffect="non-scaling-stroke"
          />
        </svg>
      ) : (
        <div className="flex h-14 items-center font-mono text-[10px] text-zinc-600">
          Sin serie para graficar
        </div>
      )}

      <p className="mt-1 font-mono text-[10px] text-zinc-600 group-hover:text-zinc-500">
        Ver en dossier →
      </p>
    </button>
  );
}
