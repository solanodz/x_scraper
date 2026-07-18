"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  applyPreset,
  CHART_INTERVALS,
  CHART_PERIODS,
  CHART_PRESETS,
  clampDonchianPeriod,
  clampOracleSignalPeriod,
  clampOscillatorPeriod,
  clampSmaLength,
  DONCHIAN_PERIOD_MAX,
  DONCHIAN_PERIOD_MIN,
  indicatorsSummary,
  loadTickerChartPrefs,
  matchPresetId,
  normalizeTickerChartPrefs,
  ORACLE_SIGNAL_PERIOD_MAX,
  ORACLE_SIGNAL_PERIOD_MIN,
  OSCILLATOR_PERIOD_MAX,
  OSCILLATOR_PERIOD_MIN,
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
  /** Optional expand control (e.g. open large chart dialog). */
  onExpand?: () => void;
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
  onExpand,
  className = "",
}: TickerChartToolbarProps) {
  const controlled = value !== undefined;
  const shouldPersist = persist ?? !controlled;
  const [internal, setInternal] = useState<TickerChartPrefs>(() =>
    normalizeTickerChartPrefs(defaultValue ?? loadTickerChartPrefs()),
  );
  const [indicatorsOpen, setIndicatorsOpen] = useState(false);
  const indicatorsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!controlled && defaultValue === undefined) {
      setInternal(loadTickerChartPrefs());
    }
  }, [controlled, defaultValue]);

  useEffect(() => {
    if (!indicatorsOpen) return;

    function handlePointerDown(event: MouseEvent) {
      if (!indicatorsRef.current?.contains(event.target as Node)) {
        setIndicatorsOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setIndicatorsOpen(false);
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [indicatorsOpen]);

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
    "w-14 rounded border border-zinc-700 bg-zinc-950 px-1.5 py-0.5 font-mono text-[10px] text-zinc-300 focus:border-amber-600 focus:outline-none disabled:opacity-40";

  const summary = indicatorsSummary(prefs);
  const hasIndicators = summary !== "None";

  return (
    <div
      className={`flex flex-wrap items-center gap-1.5 border-b border-zinc-800 bg-zinc-950 px-2 py-2 ${className}`}
    >
      <span className="mr-0.5 font-mono text-[9px] uppercase tracking-wide text-zinc-500">
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
          {!CHART_INTERVALS.includes(
            prefs.interval as (typeof CHART_INTERVALS)[number],
          ) && <option value={prefs.interval}>{prefs.interval}</option>}
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
          {!CHART_PERIODS.includes(
            prefs.period as (typeof CHART_PERIODS)[number],
          ) && <option value={prefs.period}>{prefs.period}</option>}
          {CHART_PERIODS.map((period) => (
            <option key={period} value={period}>
              {period}
            </option>
          ))}
        </select>
      </label>

      <span className="mx-1 hidden h-4 w-px bg-zinc-800 sm:inline-block" />

      <div className="relative" ref={indicatorsRef}>
        <button
          type="button"
          onClick={() => setIndicatorsOpen((open) => !open)}
          className={`flex max-w-[220px] items-center gap-1.5 rounded border px-2 py-0.5 font-mono text-[10px] transition-colors ${
            hasIndicators
              ? "border-amber-700/70 bg-amber-950/30 text-amber-400"
              : "border-zinc-700 bg-zinc-900 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200"
          }`}
          aria-expanded={indicatorsOpen}
          aria-haspopup="dialog"
        >
          <span className="uppercase tracking-wide text-zinc-500">Ind</span>
          <span className="truncate">{summary}</span>
          <span className="text-zinc-600" aria-hidden>
            ▾
          </span>
        </button>

        {indicatorsOpen && (
          <div
            className="absolute left-0 top-full z-30 mt-1 w-72 rounded border border-zinc-700 bg-zinc-950 p-2 shadow-xl"
            role="dialog"
            aria-label="Indicadores del Ticker Chart"
          >
            <p className="mb-2 font-mono text-[9px] uppercase tracking-wide text-zinc-500">
              Indicators
            </p>
            <div className="space-y-2">
              <IndicatorRow
                label="SMA A"
                accent="accent-amber-500"
                enabled={prefs.smaA.enabled}
                onToggle={(enabled) =>
                  setPrefs({
                    ...prefs,
                    smaA: { ...prefs.smaA, enabled },
                  })
                }
              >
                <label className="flex items-center gap-1 font-mono text-[10px] text-zinc-500">
                  len
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
              </IndicatorRow>

              <IndicatorRow
                label="SMA B"
                accent="accent-sky-400"
                enabled={prefs.smaB.enabled}
                onToggle={(enabled) =>
                  setPrefs({
                    ...prefs,
                    smaB: { ...prefs.smaB, enabled },
                  })
                }
              >
                <label className="flex items-center gap-1 font-mono text-[10px] text-zinc-500">
                  len
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
              </IndicatorRow>

              <IndicatorRow
                label="Donchian"
                accent="accent-violet-400"
                enabled={prefs.donchian.enabled}
                onToggle={(enabled) =>
                  setPrefs({
                    ...prefs,
                    donchian: { ...prefs.donchian, enabled },
                  })
                }
              >
                <label className="flex items-center gap-1 font-mono text-[10px] text-zinc-500">
                  per
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
              </IndicatorRow>

              <IndicatorRow
                label="Fibonacci"
                accent="accent-zinc-400"
                enabled={prefs.fib}
                onToggle={(enabled) => setPrefs({ ...prefs, fib: enabled })}
              />

              <IndicatorRow
                label="Volume"
                accent="accent-emerald-400"
                enabled={prefs.volume}
                onToggle={(enabled) => setPrefs({ ...prefs, volume: enabled })}
              />

              <IndicatorRow
                label="RSI"
                accent="accent-amber-400"
                enabled={prefs.oscillator.enabled}
                onToggle={(enabled) =>
                  setPrefs({
                    ...prefs,
                    oscillator: { ...prefs.oscillator, enabled },
                  })
                }
              >
                <label className="flex items-center gap-1 font-mono text-[10px] text-zinc-500">
                  per
                  <input
                    type="number"
                    min={OSCILLATOR_PERIOD_MIN}
                    max={OSCILLATOR_PERIOD_MAX}
                    value={prefs.oscillator.period}
                    disabled={!prefs.oscillator.enabled}
                    onChange={(e) =>
                      setPrefs({
                        ...prefs,
                        oscillator: {
                          ...prefs.oscillator,
                          period: clampOscillatorPeriod(Number(e.target.value)),
                        },
                      })
                    }
                    className={inputClass}
                  />
                </label>
              </IndicatorRow>

              <IndicatorRow
                label="Oracle"
                accent="accent-sky-400"
                enabled={prefs.oracle.enabled}
                onToggle={(enabled) =>
                  setPrefs({
                    ...prefs,
                    oracle: { ...prefs.oracle, enabled },
                  })
                }
              >
                <div className="flex items-center gap-1.5">
                  <label className="flex items-center gap-1 font-mono text-[10px] text-zinc-500">
                    per
                    <input
                      type="number"
                      min={OSCILLATOR_PERIOD_MIN}
                      max={OSCILLATOR_PERIOD_MAX}
                      value={prefs.oracle.period}
                      disabled={!prefs.oracle.enabled}
                      onChange={(e) =>
                        setPrefs({
                          ...prefs,
                          oracle: {
                            ...prefs.oracle,
                            period: clampOscillatorPeriod(Number(e.target.value)),
                          },
                        })
                      }
                      className={inputClass}
                    />
                  </label>
                  <label className="flex items-center gap-1 font-mono text-[10px] text-zinc-500">
                    sig
                    <input
                      type="number"
                      min={ORACLE_SIGNAL_PERIOD_MIN}
                      max={ORACLE_SIGNAL_PERIOD_MAX}
                      value={prefs.oracle.signalPeriod}
                      disabled={!prefs.oracle.enabled}
                      onChange={(e) =>
                        setPrefs({
                          ...prefs,
                          oracle: {
                            ...prefs.oracle,
                            signalPeriod: clampOracleSignalPeriod(
                              Number(e.target.value),
                            ),
                          },
                        })
                      }
                      className={inputClass}
                    />
                  </label>
                </div>
              </IndicatorRow>
            </div>
          </div>
        )}
      </div>

      {onExpand && (
        <>
          <span className="mx-1 hidden h-4 w-px bg-zinc-800 sm:inline-block" />
          <button
            type="button"
            onClick={onExpand}
            className="rounded border border-zinc-700 bg-zinc-900 px-2 py-0.5 font-mono text-[10px] text-zinc-400 transition-colors hover:border-amber-700 hover:text-amber-400"
            title="Ampliar gráfico"
            aria-label="Ampliar gráfico"
          >
            Expand
          </button>
        </>
      )}
    </div>
  );
}

function IndicatorRow({
  label,
  accent,
  enabled,
  onToggle,
  children,
}: {
  label: string;
  accent: string;
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
  children?: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-2 rounded border border-zinc-800/80 px-2 py-1.5">
      <label className="flex min-w-0 items-center gap-1.5 font-mono text-[10px] text-zinc-300">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => onToggle(e.target.checked)}
          className={accent}
        />
        {label}
      </label>
      {children}
    </div>
  );
}
