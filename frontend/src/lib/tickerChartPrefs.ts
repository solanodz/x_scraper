/** Prefs globales del Ticker Chart (localStorage, browser). Ver ADR-0011. */

export const TICKER_CHART_PREFS_KEY = "xscraper.tickerChart.v5";

export type ChartPresetId = "1D" | "5D" | "1M" | "3M" | "1Y" | "5Y";

export type SmaSlotConfig = {
  enabled: boolean;
  length: number;
};

export type DonchianConfig = {
  enabled: boolean;
  period: number;
};

/** RSI en el pane de oscilador (separado del precio). */
export type OscillatorConfig = {
  enabled: boolean;
  period: number;
};

/**
 * Oracle Oscillator en el pane inferior (separado del precio).
 * Híbrido: %R + Laguerre RSI + Stoch + RSI + DeMarker.
 */
export type OracleOscillatorConfig = {
  enabled: boolean;
  /** Lookback de componentes (default 14). */
  period: number;
  /** SMA de la signal line (default 5). */
  signalPeriod: number;
};

/** Vista del Ticker Chart (también payload soft-apply del Chart Plan). */
export type ChartViewConfig = {
  interval: string;
  period: string;
  smaA: SmaSlotConfig;
  smaB: SmaSlotConfig;
  donchian: DonchianConfig;
  fib: boolean;
  volume: boolean;
  oscillator: OscillatorConfig;
  oracle: OracleOscillatorConfig;
};

export type TickerChartPrefs = ChartViewConfig & {
  presetId?: ChartPresetId | null;
};

export type ChartPreset = {
  id: ChartPresetId;
  label: string;
  interval: string;
  period: string;
};

export const CHART_PRESETS: ChartPreset[] = [
  { id: "1D", label: "1D", interval: "5m", period: "1d" },
  { id: "5D", label: "5D", interval: "15m", period: "5d" },
  { id: "1M", label: "1M", interval: "1h", period: "1mo" },
  { id: "3M", label: "3M", interval: "1d", period: "3mo" },
  { id: "1Y", label: "1Y", interval: "1d", period: "1y" },
  { id: "5Y", label: "5Y", interval: "1wk", period: "5y" },
];

export const CHART_INTERVALS = ["1m", "5m", "15m", "30m", "1h", "1d", "1wk"] as const;
export const CHART_PERIODS = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"] as const;

export const SMA_LENGTH_MIN = 5;
export const SMA_LENGTH_MAX = 200;
export const DONCHIAN_PERIOD_MIN = 5;
export const DONCHIAN_PERIOD_MAX = 200;
export const OSCILLATOR_PERIOD_MIN = 5;
export const OSCILLATOR_PERIOD_MAX = 100;
export const ORACLE_SIGNAL_PERIOD_MIN = 2;
export const ORACLE_SIGNAL_PERIOD_MAX = 50;

/** Defaults limpios: velas + pane inferior reservado; indicadores OFF. */
export const DEFAULT_CHART_VIEW: ChartViewConfig = {
  interval: "1d",
  period: "1y",
  smaA: { enabled: false, length: 20 },
  smaB: { enabled: false, length: 50 },
  donchian: { enabled: false, period: 20 },
  fib: false,
  volume: false,
  oscillator: { enabled: false, period: 14 },
  oracle: { enabled: false, period: 14, signalPeriod: 5 },
};

export function clampOscillatorPeriod(period: number): number {
  return clampLength(period, OSCILLATOR_PERIOD_MIN, OSCILLATOR_PERIOD_MAX);
}

export function clampOracleSignalPeriod(period: number): number {
  return clampLength(period, ORACLE_SIGNAL_PERIOD_MIN, ORACLE_SIGNAL_PERIOD_MAX);
}

/** Resumen corto para el chip del desplegable Indicators. */
export function indicatorsSummary(prefs: ChartViewConfig): string {
  const parts: string[] = [];
  if (prefs.smaA.enabled) parts.push(`SMA${prefs.smaA.length}`);
  if (prefs.smaB.enabled) parts.push(`SMA${prefs.smaB.length}`);
  if (prefs.donchian.enabled) parts.push(`DC${prefs.donchian.period}`);
  if (prefs.fib) parts.push("Fib");
  if (prefs.volume) parts.push("Vol");
  if (prefs.oscillator.enabled) parts.push(`RSI${prefs.oscillator.period}`);
  if (prefs.oracle.enabled) parts.push(`Oracle${prefs.oracle.period}`);
  return parts.length > 0 ? parts.join(" · ") : "None";
}

export const DEFAULT_TICKER_CHART_PREFS: TickerChartPrefs = {
  ...DEFAULT_CHART_VIEW,
  presetId: "1Y",
};

export function clampLength(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.min(max, Math.max(min, Math.round(value)));
}

export function clampSmaLength(length: number): number {
  return clampLength(length, SMA_LENGTH_MIN, SMA_LENGTH_MAX);
}

export function clampDonchianPeriod(period: number): number {
  return clampLength(period, DONCHIAN_PERIOD_MIN, DONCHIAN_PERIOD_MAX);
}

export function presetById(id: ChartPresetId): ChartPreset {
  return CHART_PRESETS.find((p) => p.id === id) ?? CHART_PRESETS[3];
}

export function matchPresetId(interval: string, period: string): ChartPresetId | null {
  const hit = CHART_PRESETS.find((p) => p.interval === interval && p.period === period);
  return hit?.id ?? null;
}

export function viewConfigFromPrefs(prefs: TickerChartPrefs): ChartViewConfig {
  return {
    interval: prefs.interval,
    period: prefs.period,
    smaA: { ...prefs.smaA },
    smaB: { ...prefs.smaB },
    donchian: { ...prefs.donchian },
    fib: prefs.fib,
    volume: prefs.volume,
    oscillator: { ...prefs.oscillator },
    oracle: { ...prefs.oracle },
  };
}

export function normalizeTickerChartPrefs(
  raw: Partial<TickerChartPrefs> | null | undefined,
): TickerChartPrefs {
  const base = DEFAULT_TICKER_CHART_PREFS;
  const smaALength = clampSmaLength(raw?.smaA?.length ?? base.smaA.length);
  const smaBLength = clampSmaLength(raw?.smaB?.length ?? base.smaB.length);
  const donchianPeriod = clampDonchianPeriod(raw?.donchian?.period ?? base.donchian.period);
  const oscillatorPeriod = clampOscillatorPeriod(
    raw?.oscillator?.period ?? base.oscillator.period,
  );
  const oraclePeriod = clampOscillatorPeriod(raw?.oracle?.period ?? base.oracle.period);
  const oracleSignalPeriod = clampOracleSignalPeriod(
    raw?.oracle?.signalPeriod ?? base.oracle.signalPeriod,
  );

  const interval = typeof raw?.interval === "string" && raw.interval ? raw.interval : base.interval;
  const period = typeof raw?.period === "string" && raw.period ? raw.period : base.period;

  let presetId: ChartPresetId | null | undefined = raw?.presetId;
  if (presetId === undefined) {
    presetId = matchPresetId(interval, period);
  } else if (presetId != null && !CHART_PRESETS.some((p) => p.id === presetId)) {
    presetId = matchPresetId(interval, period);
  }

  return {
    presetId: presetId ?? null,
    interval,
    period,
    smaA: {
      enabled: raw?.smaA?.enabled ?? base.smaA.enabled,
      length: smaALength,
    },
    smaB: {
      enabled: raw?.smaB?.enabled ?? base.smaB.enabled,
      length: smaBLength,
    },
    donchian: {
      enabled: raw?.donchian?.enabled ?? base.donchian.enabled,
      period: donchianPeriod,
    },
    fib: raw?.fib ?? base.fib,
    volume: raw?.volume ?? base.volume,
    oscillator: {
      enabled: raw?.oscillator?.enabled ?? base.oscillator.enabled,
      period: oscillatorPeriod,
    },
    oracle: {
      enabled: raw?.oracle?.enabled ?? base.oracle.enabled,
      period: oraclePeriod,
      signalPeriod: oracleSignalPeriod,
    },
  };
}

export function applyPreset(id: ChartPresetId, current?: Partial<TickerChartPrefs>): TickerChartPrefs {
  const preset = presetById(id);
  return normalizeTickerChartPrefs({
    ...DEFAULT_TICKER_CHART_PREFS,
    ...current,
    presetId: id,
    interval: preset.interval,
    period: preset.period,
  });
}

export function loadTickerChartPrefs(): TickerChartPrefs {
  if (typeof window === "undefined") return { ...DEFAULT_TICKER_CHART_PREFS };
  try {
    const raw = window.localStorage.getItem(TICKER_CHART_PREFS_KEY);
    if (!raw) return { ...DEFAULT_TICKER_CHART_PREFS };
    return normalizeTickerChartPrefs(JSON.parse(raw) as Partial<TickerChartPrefs>);
  } catch {
    return { ...DEFAULT_TICKER_CHART_PREFS };
  }
}

export function saveTickerChartPrefs(prefs: TickerChartPrefs): void {
  if (typeof window === "undefined") return;
  try {
    const normalized = normalizeTickerChartPrefs(prefs);
    window.localStorage.setItem(TICKER_CHART_PREFS_KEY, JSON.stringify(normalized));
  } catch {
    // Quota / private mode — ignore.
  }
}
