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

/** Classic Wilder RSI as time/value points. */
export function buildRsiLineData(
  candles: PriceCandle[],
  period: number,
): LwcTimeValuePoint[] {
  if (period < 2 || candles.length <= period) return [];
  const closes = candles.map((c) => c.close);
  const points: LwcTimeValuePoint[] = [];

  let avgGain = 0;
  let avgLoss = 0;
  for (let i = 1; i <= period; i++) {
    const delta = closes[i] - closes[i - 1];
    if (delta >= 0) avgGain += delta;
    else avgLoss -= delta;
  }
  avgGain /= period;
  avgLoss /= period;

  const firstRs = avgLoss === 0 ? 100 : avgGain / avgLoss;
  const firstRsi = avgLoss === 0 ? 100 : 100 - 100 / (1 + firstRs);
  points.push({
    time: candleDateToLwcTime(candles[period].date),
    value: firstRsi,
  });

  for (let i = period + 1; i < closes.length; i++) {
    const delta = closes[i] - closes[i - 1];
    const gain = delta > 0 ? delta : 0;
    const loss = delta < 0 ? -delta : 0;
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    const rsi = avgLoss === 0 ? 100 : 100 - 100 / (1 + rs);
    points.push({
      time: candleDateToLwcTime(candles[i].date),
      value: rsi,
    });
  }

  return dedupeByTime(points);
}

/** Flat midline for empty/reserved oscillator pane (keeps scale 0–100). */
export function buildOscillatorPlaceholderData(
  candles: PriceCandle[],
  value = 50,
): LwcTimeValuePoint[] {
  return dedupeByTime(
    candles.map((c) => ({
      time: candleDateToLwcTime(c.date),
      value,
    })),
  );
}

function clamp01to100(value: number): number {
  if (!Number.isFinite(value)) return 50;
  return Math.min(100, Math.max(0, value));
}

/** Wilder RSI series aligned to candle index (null during warmup). */
function rsiValues(closes: number[], period: number): Array<number | null> {
  const out: Array<number | null> = closes.map(() => null);
  if (period < 2 || closes.length <= period) return out;

  let avgGain = 0;
  let avgLoss = 0;
  for (let i = 1; i <= period; i++) {
    const delta = closes[i] - closes[i - 1];
    if (delta >= 0) avgGain += delta;
    else avgLoss -= delta;
  }
  avgGain /= period;
  avgLoss /= period;
  out[period] =
    avgLoss === 0 ? 100 : clamp01to100(100 - 100 / (1 + avgGain / avgLoss));

  for (let i = period + 1; i < closes.length; i++) {
    const delta = closes[i] - closes[i - 1];
    const gain = delta > 0 ? delta : 0;
    const loss = delta < 0 ? -delta : 0;
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    out[i] =
      avgLoss === 0 ? 100 : clamp01to100(100 - 100 / (1 + avgGain / avgLoss));
  }
  return out;
}

/** Williams %R remapped from [-100, 0] → [0, 100] (higher = more bullish). */
function williamsRNormValues(
  highs: number[],
  lows: number[],
  closes: number[],
  period: number,
): Array<number | null> {
  const out: Array<number | null> = closes.map(() => null);
  if (period < 1) return out;
  for (let i = period - 1; i < closes.length; i++) {
    const hh = Math.max(...highs.slice(i + 1 - period, i + 1));
    const ll = Math.min(...lows.slice(i + 1 - period, i + 1));
    const range = hh - ll;
    if (range <= 0) {
      out[i] = 50;
      continue;
    }
    const raw = ((hh - closes[i]) / range) * -100; // [-100, 0]
    out[i] = clamp01to100(raw + 100);
  }
  return out;
}

/** Stochastic %K (0–100). */
function stochasticKValues(
  highs: number[],
  lows: number[],
  closes: number[],
  period: number,
): Array<number | null> {
  const out: Array<number | null> = closes.map(() => null);
  if (period < 1) return out;
  for (let i = period - 1; i < closes.length; i++) {
    const hh = Math.max(...highs.slice(i + 1 - period, i + 1));
    const ll = Math.min(...lows.slice(i + 1 - period, i + 1));
    const range = hh - ll;
    out[i] = range <= 0 ? 50 : clamp01to100(((closes[i] - ll) / range) * 100);
  }
  return out;
}

/** DeMarker (0–100). */
function demarkerValues(
  highs: number[],
  lows: number[],
  period: number,
): Array<number | null> {
  const n = highs.length;
  const out: Array<number | null> = Array.from({ length: n }, () => null);
  if (period < 1 || n < period + 1) return out;

  const deMax: number[] = [0];
  const deMin: number[] = [0];
  for (let i = 1; i < n; i++) {
    deMax.push(highs[i] > highs[i - 1] ? highs[i] - highs[i - 1] : 0);
    deMin.push(lows[i] < lows[i - 1] ? lows[i - 1] - lows[i] : 0);
  }

  for (let i = period; i < n; i++) {
    let sumMax = 0;
    let sumMin = 0;
    for (let j = i - period + 1; j <= i; j++) {
      sumMax += deMax[j];
      sumMin += deMin[j];
    }
    const denom = sumMax + sumMin;
    out[i] = denom <= 0 ? 50 : clamp01to100((sumMax / denom) * 100);
  }
  return out;
}

/**
 * John Ehlers Laguerre RSI (0–100).
 * gamma ∈ [0,1]; 0.5 is the classic default (smooth vs reactive).
 */
function laguerreRsiValues(closes: number[], gamma: number): number[] {
  const g = Math.min(1, Math.max(0, gamma));
  const alpha = 1 - g;
  const out: number[] = [];
  let l0 = 0;
  let l1 = 0;
  let l2 = 0;
  let l3 = 0;

  for (let i = 0; i < closes.length; i++) {
    const price = closes[i];
    const prev0 = l0;
    const prev1 = l1;
    const prev2 = l2;
    const prev3 = l3;

    if (i === 0) {
      l0 = price;
      l1 = price;
      l2 = price;
      l3 = price;
    } else {
      l0 = alpha * price + g * prev0;
      l1 = -g * l0 + prev0 + g * prev1;
      l2 = -g * l1 + prev1 + g * prev2;
      l3 = -g * l2 + prev2 + g * prev3;
    }

    let cu = 0;
    let cd = 0;
    const pairs: Array<[number, number]> = [
      [l0, l1],
      [l1, l2],
      [l2, l3],
    ];
    for (const [upper, lower] of pairs) {
      if (upper >= lower) cu += upper - lower;
      else cd += lower - upper;
    }
    out.push(cu + cd > 0 ? clamp01to100((100 * cu) / (cu + cd)) : 50);
  }
  return out;
}

export type OracleOscillatorOptions = {
  /** Lookback for %R / Stoch / DeMarker / RSI components (default 14). */
  period?: number;
  /** Laguerre damping factor (default 0.5). */
  gamma?: number;
  /** SMA length of the yellow signal line (default 5). */
  signalPeriod?: number;
};

export type OracleOscillatorSeries = {
  oracle: LwcTimeValuePoint[];
  signal: LwcTimeValuePoint[];
};

/**
 * Oracle Oscillator (open recreation of the published hybrid weights):
 * 30% Williams %R + 30% Laguerre RSI + 20% Stochastic + 10% RSI + 10% DeMarker.
 * Bounded 0–100; overbought/oversold typically 75 / 25.
 *
 * Not the closed-source MQL5 binary — same public architecture for Operator use.
 */
export function buildOracleOscillatorData(
  candles: PriceCandle[],
  options: OracleOscillatorOptions = {},
): OracleOscillatorSeries {
  const period = options.period ?? 14;
  const gamma = options.gamma ?? 0.5;
  const signalPeriod = options.signalPeriod ?? 5;

  if (candles.length < period + 2) {
    return { oracle: [], signal: [] };
  }

  const closes = candles.map((c) => c.close);
  const highs = candles.map((c) => c.high);
  const lows = candles.map((c) => c.low);

  const wr = williamsRNormValues(highs, lows, closes, period);
  const stoch = stochasticKValues(highs, lows, closes, period);
  const dem = demarkerValues(highs, lows, period);
  const rsi = rsiValues(closes, period);
  const lrsi = laguerreRsiValues(closes, gamma);

  const oracleRaw: Array<number | null> = closes.map(() => null);
  for (let i = 0; i < closes.length; i++) {
    const a = wr[i];
    const b = lrsi[i];
    const c = stoch[i];
    const d = rsi[i];
    const e = dem[i];
    if (a == null || c == null || d == null || e == null) continue;
    oracleRaw[i] = clamp01to100(0.3 * a + 0.3 * b + 0.2 * c + 0.1 * d + 0.1 * e);
  }

  const oracle: LwcTimeValuePoint[] = [];
  for (let i = 0; i < candles.length; i++) {
    const value = oracleRaw[i];
    if (value == null) continue;
    oracle.push({ time: candleDateToLwcTime(candles[i].date), value });
  }

  const signal: LwcTimeValuePoint[] = [];
  if (signalPeriod >= 1) {
    for (let i = 0; i < oracleRaw.length; i++) {
      if (i + 1 < signalPeriod) continue;
      let sum = 0;
      let count = 0;
      let ok = true;
      for (let j = i + 1 - signalPeriod; j <= i; j++) {
        const v = oracleRaw[j];
        if (v == null) {
          ok = false;
          break;
        }
        sum += v;
        count += 1;
      }
      if (!ok || count === 0) continue;
      signal.push({
        time: candleDateToLwcTime(candles[i].date),
        value: sum / count,
      });
    }
  }

  return {
    oracle: dedupeByTime(oracle),
    signal: dedupeByTime(signal),
  };
}

export type OscillatorPivot = {
  index: number;
  time: ReturnType<typeof candleDateToLwcTime>;
  value: number;
  price: number;
};

export type RsiDivergence = {
  type: "bull" | "bear";
  start: OscillatorPivot;
  end: OscillatorPivot;
};

function findSwingPivots(
  candles: PriceCandle[],
  values: Array<number | null>,
  kind: "high" | "low",
  left = 5,
  right = 5,
): OscillatorPivot[] {
  const pivots: OscillatorPivot[] = [];
  for (let i = left; i < candles.length - right; i++) {
    const value = values[i];
    if (value == null) continue;
    let isPivot = true;
    for (let j = i - left; j <= i + right; j++) {
      if (j === i) continue;
      const other = values[j];
      if (other == null) continue;
      if (kind === "high" && other > value) {
        isPivot = false;
        break;
      }
      if (kind === "low" && other < value) {
        isPivot = false;
        break;
      }
    }
    if (!isPivot) continue;
    pivots.push({
      index: i,
      time: candleDateToLwcTime(candles[i].date),
      value,
      price: kind === "high" ? candles[i].high : candles[i].low,
    });
  }
  return pivots;
}

/**
 * Divergencias regulares precio ↔ RSI.
 * Bull: precio lower-low + RSI higher-low.
 * Bear: precio higher-high + RSI lower-high.
 */
export function detectRsiDivergences(
  candles: PriceCandle[],
  period: number,
  options?: { left?: number; right?: number; maxSignals?: number },
): RsiDivergence[] {
  const left = options?.left ?? 5;
  const right = options?.right ?? 5;
  const maxSignals = options?.maxSignals ?? 4;

  const closes = candles.map((c) => c.close);
  const rsi = rsiValues(closes, period);
  const highs = findSwingPivots(candles, rsi, "high", left, right);
  const lows = findSwingPivots(candles, rsi, "low", left, right);

  const bulls: RsiDivergence[] = [];
  for (let i = 0; i < lows.length - 1; i++) {
    for (let j = i + 1; j < lows.length; j++) {
      const a = lows[i];
      const b = lows[j];
      // Prefer nearby pivot pairs (skip if too many bars apart).
      if (b.index - a.index > 80) break;
      if (b.price < a.price && b.value > a.value) {
        bulls.push({ type: "bull", start: a, end: b });
      }
    }
  }

  const bears: RsiDivergence[] = [];
  for (let i = 0; i < highs.length - 1; i++) {
    for (let j = i + 1; j < highs.length; j++) {
      const a = highs[i];
      const b = highs[j];
      if (b.index - a.index > 80) break;
      if (b.price > a.price && b.value < a.value) {
        bears.push({ type: "bear", start: a, end: b });
      }
    }
  }

  // Keep the most recent signals only (less clutter).
  const recentBulls = bulls.slice(-Math.ceil(maxSignals / 2));
  const recentBears = bears.slice(-Math.ceil(maxSignals / 2));
  return [...recentBulls, ...recentBears].sort(
    (a, b) => a.end.index - b.end.index,
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
  rsi: "#38bdf8",
  rsiBull: "#22c55e",
  rsiBear: "#ef4444",
  oracle: "#e4e4e7",
  oracleSignal: "#facc15",
  oracleTopLine: "#22c55e",
  oracleBottomLine: "#ef4444",
  oscillatorReserved: "rgba(113, 113, 122, 0.35)",
} as const;
