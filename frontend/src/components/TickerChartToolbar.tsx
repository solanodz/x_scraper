"use client";

import { useEffect, useState } from "react";
import {
  applyPreset,
  CHART_INTERVALS,
  CHART_PERIODS,
  CHART_PRESETS,
  clampDonchianPeriod,
  clampSmaLength,
  DONCHIAN_PERIOD_MAX,
  DONCHIAN_PERIOD_MIN,
  loadTickerChartPrefs,
  matchPresetId,
  normalizeTickerChartPrefs,
  saveTickerChartPrefs,
  SMA_LENGTH_MAX,
  SMA_LENGTH_MIN,
  type ChartPresetId,
  type TickerChartPrefs,
} from "@/lib/tickerChartPrefs";

export interface TickerChartToolbarProps {
  /** Controlled prefs. When omitted, toolbar is uncontrolled. */
  value?: TickerChartPrefs;
  defaultValue?: TickerChartPrefs;
  onChange?: (prefs: TickerChartPrefs) => void;
  /** Persist to localStorage on change (default true when uncontrolled). */
  persist?: boolean;
  className?: string;
}

function emit(
  next: TickerChartPrefs,
  persist: boolean,
  onChange?: (prefs: TickerChartPrefs) => void,
): TickerChartPrefs {
  const normalized = normalizeTickerChartPrefs(next);
  if (persist) saveTickerChartPrefs(normalized);
  onChange?.(normalized);
  return normalized;
}

export function TickerChartToolbar({
  value,
  defaultValue,
  onChange,
  persist,
  className = "",
}: TickerChartToolbarProps) {
  const controlled = value !== undefined;
  const shouldPersist = persist ?? !controlled;
  const [internal, setInternal] = useState<TickerChartPrefs>(() =>
    normalizeTickerChartPrefs(defaultValue ?? loadTickerChartPrefs()),
  );

  useEffect(() => {
    if (!controlled && defaultValue === undefined) {
      setInternal(loadTickerChartPrefs());
    }
  }, [controlled, defaultValue]);

  const prefs = controlled ? normalizeTickerChartPrefs(value) : internal;

  const setPrefs = (next: TickerChartPrefs) => {
    const normalized = emit(next, shouldPersist, onChange);
    if (!controlled) setInternal(normalized);
  };

  const onPreset = (id: ChartPresetId) => {
    setPrefs(applyPreset(id, prefs));
  };

  const onAdvancedInterval = (interval: string) => {
    setPrefs(
      normalizeTickerChartPrefs({
        ...prefs,
        interval,
        presetId: matchPresetId(interval, prefs.period),
      }),
    );
  };

  const onAdvancedPeriod = (period: string) => {
    setPrefs(
      normalizeTickerChartPrefs({
        ...prefs,
        period,
        presetId: matchPresetId(prefs.interval, period),
      }),
    );
  };

  const chipClass = (active: boolean) =>
    `rounded border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide transition-colors ${
      active
        ? "border-amber-600 bg-amber-950/40 text-amber-400"
        : "border-zinc-700 bg-zinc-900 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200"
    }`;

  const selectClass =
    "rounded border border-zinc-700 bg-zinc-950 px-1.5 py-0.5 font-mono text-[10px] text-zinc-300 focus:border-amber-600 focus:outline-none";

  const inputClass =
    "w-12 rounded border border-zinc-700 bg-zinc-950 px-1 py-0.5 font-mono text-[10px] text-zinc-300 focus:border-amber-600 focus:outline-none";

  return (
    <div
      className={`flex flex-col gap-2 border-b border-zinc-800 bg-zinc-950 px-2 py-2 ${className}`}
    >
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="mr-1 font-mono text-[9px] uppercase tracking-wide text-zinc-500">
          Preset
        </span>
        {CHART_PRESETS.map((preset) => (
          <button
            key={preset.id}
            type="button"
            className={chipClass(prefs.presetId === preset.id)}
            onClick={() => onPreset(preset.id)}
            title={`${preset.interval} · ${preset.period}`}
          >
            {preset.label}
          </button>
        ))}

        <span className="mx-1 hidden h-4 w-px bg-zinc-800 sm:inline-block" />

        <span className="font-mono text-[9px] uppercase tracking-wide text-zinc-500">
          Advanced
        </span>
        <label className="flex items-center gap-1 font-mono text-[10px] text-zinc-500">
          int
          <select
            className={selectClass}
            value={prefs.interval}
            onChange={(e) => onAdvancedInterval(e.target.value)}
          >
            {!CHART_INTERVALS.includes(prefs.interval as (typeof CHART_INTERVALS)[number]) && (
              <option value={prefs.interval}>{prefs.interval}</option>
            )}
            {CHART_INTERVALS.map((interval) => (
              <option key={interval} value={interval}>
                {interval}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-1 font-mono text-[10px] text-zinc-500">
          win
          <select
            className={selectClass}
            value={prefs.period}
            onChange={(e) => onAdvancedPeriod(e.target.value)}
          >
            {!CHART_PERIODS.includes(prefs.period as (typeof CHART_PERIODS)[number]) && (
              <option value={prefs.period}>{prefs.period}</option>
            )}
            {CHART_PERIODS.map((period) => (
              <option key={period} value={period}>
                {period}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <span className="font-mono text-[9px] uppercase tracking-wide text-zinc-500">
          Indicators
        </span>

        <label className="flex items-center gap-1 font-mono text-[10px] text-zinc-400">
          <input
            type="checkbox"
            checked={prefs.smaA.enabled}
            onChange={(e) =>
              setPrefs({
                ...prefs,
                smaA: { ...prefs.smaA, enabled: e.target.checked },
              })
            }
            className="accent-amber-500"
          />
          SMA A
          <input
            type="number"
            min={SMA_LENGTH_MIN}
            max={SMA_LENGTH_MAX}
            value={prefs.smaA.length}
            disabled={!prefs.smaA.enabled}
            onChange={(e) =>
              setPrefs({
                ...prefs,
                smaA: {
                  ...prefs.smaA,
                  length: clampSmaLength(Number(e.target.value)),
                },
              })
            }
            className={inputClass}
          />
        </label>

        <label className="flex items-center gap-1 font-mono text-[10px] text-zinc-400">
          <input
            type="checkbox"
            checked={prefs.smaB.enabled}
            onChange={(e) =>
              setPrefs({
                ...prefs,
                smaB: { ...prefs.smaB, enabled: e.target.checked },
              })
            }
            className="accent-sky-400"
          />
          SMA B
          <input
            type="number"
            min={SMA_LENGTH_MIN}
            max={SMA_LENGTH_MAX}
            value={prefs.smaB.length}
            disabled={!prefs.smaB.enabled}
            onChange={(e) =>
              setPrefs({
                ...prefs,
                smaB: {
                  ...prefs.smaB,
                  length: clampSmaLength(Number(e.target.value)),
                },
              })
            }
            className={inputClass}
          />
        </label>

        <label className="flex items-center gap-1 font-mono text-[10px] text-zinc-400">
          <input
            type="checkbox"
            checked={prefs.donchian.enabled}
            onChange={(e) =>
              setPrefs({
                ...prefs,
                donchian: { ...prefs.donchian, enabled: e.target.checked },
              })
            }
            className="accent-violet-400"
          />
          Donchian
          <input
            type="number"
            min={DONCHIAN_PERIOD_MIN}
            max={DONCHIAN_PERIOD_MAX}
            value={prefs.donchian.period}
            disabled={!prefs.donchian.enabled}
            onChange={(e) =>
              setPrefs({
                ...prefs,
                donchian: {
                  ...prefs.donchian,
                  period: clampDonchianPeriod(Number(e.target.value)),
                },
              })
            }
            className={inputClass}
          />
        </label>

        <label className="flex items-center gap-1 font-mono text-[10px] text-zinc-400">
          <input
            type="checkbox"
            checked={prefs.fib}
            onChange={(e) => setPrefs({ ...prefs, fib: e.target.checked })}
            className="accent-zinc-400"
          />
          Fib
        </label>

        <label className="flex items-center gap-1 font-mono text-[10px] text-zinc-400">
          <input
            type="checkbox"
            checked={prefs.volume}
            onChange={(e) => setPrefs({ ...prefs, volume: e.target.checked })}
            className="accent-emerald-400"
          />
          Volume
        </label>
      </div>
    </div>
  );
}
