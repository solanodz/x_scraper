import type { PriceCandle, Quote } from "@/lib/types";
import { canMergeLiveQuote } from "@/lib/marketSymbols";

/** Intervalo de refresh de quote en UI (backend cache ~15 min). */
export const MARKET_QUOTE_POLL_MS = 60_000;

/** Refresh completo de velas OHLC (fallback). */
export const MARKET_CANDLES_POLL_MS = 300_000;

export function candlesPollMsForInterval(interval: string): number {
  switch (interval) {
    case "1m":
    case "5m":
      return 60_000;
    case "15m":
    case "30m":
      return 120_000;
    case "1h":
      return 300_000;
    case "1wk":
      return 900_000;
    case "1d":
    default:
      return 300_000;
  }
}

export function formatQuotePrice(price: number): string {
  return price.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function formatQuoteChangePercent(pct: number): string {
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

function isIntradayInterval(interval: string): boolean {
  return ["1m", "5m", "15m", "30m", "1h"].includes(interval);
}

function openBucketKey(now: Date, interval: string): string {
  if (!isIntradayInterval(interval)) {
    return now.toISOString().slice(0, 10);
  }
  const ms = now.getTime();
  const minutes =
    interval === "1m"
      ? 1
      : interval === "5m"
        ? 5
        : interval === "15m"
          ? 15
          : interval === "30m"
            ? 30
            : 60;
  const bucket = Math.floor(ms / (minutes * 60_000)) * minutes * 60_000;
  return new Date(bucket).toISOString();
}

function candleMatchesOpenBucket(candleDate: string, bucketKey: string, interval: string): boolean {
  if (!isIntradayInterval(interval)) {
    return candleDate.slice(0, 10) === bucketKey.slice(0, 10);
  }
  const candleMs = Date.parse(candleDate);
  if (Number.isNaN(candleMs)) return false;
  const bucketMs = Date.parse(bucketKey);
  return Math.abs(candleMs - bucketMs) < 60_000;
}

/** Actualiza solo la vela abierta del intervalo actual con el último precio. */
export function mergeLiveQuoteIntoCandles(
  candles: PriceCandle[],
  quote: Quote | null | undefined,
  interval = "1d",
): PriceCandle[] {
  if (!candles.length || quote?.price == null || !quote.available) {
    return candles;
  }

  const price = quote.price;
  const last = candles[candles.length - 1];
  if (!canMergeLiveQuote(last.close, price)) {
    return candles;
  }

  const bucketKey = openBucketKey(new Date(), interval);

  if (candleMatchesOpenBucket(last.date, bucketKey, interval)) {
    const updated: PriceCandle = {
      ...last,
      close: price,
      high: Math.max(last.high, price),
      low: Math.min(last.low, price),
    };
    return [...candles.slice(0, -1), updated];
  }

  // Solo crear vela nueva en diario; en intradía esperar refetch
  if (!isIntradayInterval(interval)) {
    return [
      ...candles,
      {
        date: bucketKey.slice(0, 10),
        open: price,
        high: price,
        low: price,
        close: price,
        volume: last.volume,
      },
    ];
  }

  return candles;
}

export function formatRefreshAge(updatedAt: number | null): string {
  if (updatedAt == null) return "";
  const seconds = Math.max(0, Math.floor((Date.now() - updatedAt) / 1000));
  if (seconds < 60) return `hace ${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  return `hace ${minutes}m`;
}
