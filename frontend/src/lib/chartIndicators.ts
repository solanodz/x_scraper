import type { Time, UTCTimestamp } from "lightweight-charts";
import type { PriceCandle } from "@/lib/types";

export type IndicatorChartRow = PriceCandle & {
  i: number;
  sma20: number | null;
  sma50: number | null;
  donchianUpper: number | null;
  donchianLower: number | null;
};

export type IndicatorCalcOptions = {
  /** SMA slot A length (default 20). Written to `sma20` for backward compat. */
  smaALength?: number;
  /** SMA slot B length (default 50). Written to `sma50` for backward compat. */
  smaBLength?: number;
  /** Donchian channel period (default 20). */
  donchianPeriod?: number;
};

export type FibonacciLevel = {
  ratio: string;
  price: number;
};

/** Lightweight Charts line point. */
export type LwcTimeValuePoint = {
  time: Time;
  value: number;
};

export type LwcOhlcPoint = {
  time: Time;
  open: number;
  high: number;
  low: number;
  close: number;
};

export type LwcVolumePoint = {
  time: Time;
  value: number;
  color?: string;
};

function sma(values: number[], index: number, period: number): number | null {
  if (period < 1 || index + 1 < period) return null;
  const window = values.slice(index + 1 - period, index + 1);
  return window.reduce((sum, value) => sum + value, 0) / period;
}

function donchian(
  highs: number[],
  lows: number[],
  index: number,
  period: number,
): { upper: number | null; lower: number | null } {
  if (period < 1 || index + 1 < period) return { upper: null, lower: null };
  const highWindow = highs.slice(index + 1 - period, index + 1);
  const lowWindow = lows.slice(index + 1 - period, index + 1);
  return {
    upper: Math.max(...highWindow),
    lower: Math.min(...lowWindow),
  };
}

/** Parse candle date (ISO date or datetime) to Lightweight Charts `Time`. */
export function candleDateToLwcTime(date: string): Time {
  if (/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return date;
  }
  const ms = Date.parse(date);
  if (!Number.isNaN(ms)) {
    return Math.floor(ms / 1000) as UTCTimestamp;
  }
  const day = date.slice(0, 10);
  if (/^\d{4}-\d{2}-\d{2}$/.test(day)) {
    return day;
  }
  return date;
}

function dedupeByTime<T extends { time: Time }>(points: T[]): T[] {
  const byTime = new Map<string | number, T>();
  for (const point of points) {
    const key =
      typeof point.time === "object"
        ? `${point.time.year}-${point.time.month}-${point.time.day}`
        : point.time;
    byTime.set(key, point);
  }
  return Array.from(byTime.values());
}

export function buildFibonacciLevels(
  candles: PriceCandle[],
  lookback = 60,
): FibonacciLevel[] {
  if (candles.length < 5) return [];
  const window = candles.slice(-Math.min(lookback, candles.length));
  const swingHigh = Math.max(...window.map((c) => c.high));
  const swingLow = Math.min(...window.map((c) => c.low));
  const span = swingHigh - swingLow;
  if (span <= 0) return [];

  const ratios = ["0.382", "0.5", "0.618"];
  return ratios.map((ratio) => ({
    ratio,
    price: Number((swingHigh - span * Number(ratio)).toFixed(2)),
  }));
}

/** Fib levels when enabled; empty when off. */
export function buildFibonacciLevelData(
  candles: PriceCandle[],
  enabled = true,
  lookback = 60,
): FibonacciLevel[] {
  if (!enabled) return [];
  return buildFibonacciLevels(candles, lookback);
}

export function buildIndicatorChartRows(
  candles: PriceCandle[],
  options: IndicatorCalcOptions = {},
): IndicatorChartRow[] {
  const smaALength = options.smaALength ?? 20;
  const smaBLength = options.smaBLength ?? 50;
  const donchianPeriod = options.donchianPeriod ?? 20;

  const closes = candles.map((c) => c.close);
  const highs = candles.map((c) => c.high);
  const lows = candles.map((c) => c.low);

  return candles.map((candle, index) => {
    const channel = donchian(highs, lows, index, donchianPeriod);
    return {
      ...candle,
      i: index,
      sma20: sma(closes, index, smaALength),
      sma50: sma(closes, index, smaBLength),
      donchianUpper: channel.upper,
      donchianLower: channel.lower,
    };
  });
}

export function chartYDomain(rows: IndicatorChartRow[]): [number, number] {
  if (rows.length === 0) return [0, 1];
  let min = Infinity;
  let max = -Infinity;
  for (const row of rows) {
    min = Math.min(min, row.low, row.donchianLower ?? row.low, row.sma20 ?? row.low, row.sma50 ?? row.low);
    max = Math.max(max, row.high, row.donchianUpper ?? row.high, row.sma20 ?? row.high, row.sma50 ?? row.high);
  }
  const padding = (max - min) * 0.06 || 1;
  const yMin = min > 0 ? Math.max(min * 0.98, min - padding) : min - padding;
  return [yMin, max + padding];
}

/** OHLC series data for Lightweight Charts CandlestickSeries. */
export function toLwcCandlestickData(candles: PriceCandle[]): LwcOhlcPoint[] {
  return dedupeByTime(
    candles.map((c) => ({
      time: candleDateToLwcTime(c.date),
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    })),
  );
}

/** SMA as time/value points (skips warmup nulls). */
export function buildSmaLineData(
  candles: PriceCandle[],
  length: number,
): LwcTimeValuePoint[] {
  if (length < 1 || candles.length === 0) return [];
  const closes = candles.map((c) => c.close);
  const points: LwcTimeValuePoint[] = [];
  for (let i = 0; i < candles.length; i++) {
    const value = sma(closes, i, length);
    if (value == null) continue;
    points.push({ time: candleDateToLwcTime(candles[i].date), value });
  }
  return dedupeByTime(points);
}

/** Donchian upper/lower as time/value arrays. */
export function buildDonchianLineData(
  candles: PriceCandle[],
  period: number,
): { upper: LwcTimeValuePoint[]; lower: LwcTimeValuePoint[] } {
  if (period < 1 || candles.length === 0) {
    return { upper: [], lower: [] };
  }
  const highs = candles.map((c) => c.high);
  const lows = candles.map((c) => c.low);
  const upper: LwcTimeValuePoint[] = [];
  const lower: LwcTimeValuePoint[] = [];
  for (let i = 0; i < candles.length; i++) {
    const channel = donchian(highs, lows, i, period);
    if (channel.upper == null || channel.lower == null) continue;
    const time = candleDateToLwcTime(candles[i].date);
    upper.push({ time, value: channel.upper });
    lower.push({ time, value: channel.lower });
  }
  return { upper: dedupeByTime(upper), lower: dedupeByTime(lower) };
}

/** Volume histogram data (green/red by candle direction). */
export function buildVolumeHistogramData(candles: PriceCandle[]): LwcVolumePoint[] {
  return dedupeByTime(
    candles.map((c) => ({
      time: candleDateToLwcTime(c.date),
      value: c.volume,
      color: c.close >= c.open ? "rgba(52, 211, 153, 0.45)" : "rgba(248, 113, 113, 0.45)",
    })),
  );
}

export const INDICATOR_COLORS = {
  sma20: "#f59e0b",
  sma50: "#38bdf8",
  smaA: "#f59e0b",
  smaB: "#38bdf8",
  donchianUpper: "#a78bfa",
  donchianLower: "#a78bfa",
  fib: "#71717a",
} as const;
