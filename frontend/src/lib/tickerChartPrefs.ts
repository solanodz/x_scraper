/** Prefs globales del Ticker Chart (localStorage, browser). Ver ADR-0011. */

export const TICKER_CHART_PREFS_KEY = "xscraper.tickerChart.v2";

export type ChartPresetId = "1D" | "5D" | "1M" | "3M" | "1Y" | "5Y";

export type SmaSlotConfig = {
  enabled: boolean;
  length: number;
};

export type DonchianConfig = {
  enabled: boolean;
  period: number;
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

export const DEFAULT_CHART_VIEW: ChartViewConfig = {
  interval: "1d",
  period: "1y",
  smaA: { enabled: true, length: 20 },
  smaB: { enabled: true, length: 50 },
  donchian: { enabled: true, period: 20 },
  fib: true,
  volume: true,
};

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
  };
}

export function normalizeTickerChartPrefs(
  raw: Partial<TickerChartPrefs> | null | undefined,
): TickerChartPrefs {
  const base = DEFAULT_TICKER_CHART_PREFS;
  const smaALength = clampSmaLength(raw?.smaA?.length ?? base.smaA.length);
  const smaBLength = clampSmaLength(raw?.smaB?.length ?? base.smaB.length);
  const donchianPeriod = clampDonchianPeriod(raw?.donchian?.period ?? base.donchian.period);

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
