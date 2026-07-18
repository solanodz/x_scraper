"use client";

import { useEffect, useRef } from "react";
import {
  BaselineSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import {
  buildOracleOscillatorData,
  buildRsiLineData,
  detectRsiDivergences,
  INDICATOR_COLORS,
} from "@/lib/chartIndicators";
import type {
  OracleOscillatorConfig,
  OscillatorConfig,
} from "@/lib/tickerChartPrefs";
import type { PriceCandle } from "@/lib/types";

const BG = "#09090b";
const GRID = "#27272a";
const TEXT = "#a1a1aa";
const BORDER = "#3f3f46";

interface TickerOscillatorPaneProps {
  symbol: string;
  candles: PriceCandle[];
  oscillator: OscillatorConfig;
  oracle: OracleOscillatorConfig;
  /** Height per active oscillator chart. */
  height?: number;
  className?: string;
  /** Called with all active oscillator chart APIs (for multi-pane time sync). */
  onApisReady?: (apis: IChartApi[]) => void;
}

function baseChartOptions(height: number) {
  return {
    height,
    layout: {
      background: { type: ColorType.Solid as const, color: BG },
      textColor: TEXT,
      attributionLogo: false,
    },
    grid: {
      vertLines: { color: GRID },
      horzLines: { color: GRID },
    },
    crosshair: {
      vertLine: { color: "#52525b", labelBackgroundColor: "#27272a" },
      horzLine: { color: "#52525b", labelBackgroundColor: "#27272a" },
    },
    rightPriceScale: {
      borderColor: BORDER,
      scaleMargins: { top: 0.08, bottom: 0.08 },
    },
    timeScale: {
      borderColor: BORDER,
      timeVisible: true,
      secondsVisible: false,
      visible: false,
    },
    handleScroll: true,
    handleScale: true,
  };
}

function mountOracleChart(
  el: HTMLDivElement,
  candles: PriceCandle[],
  oracle: OracleOscillatorConfig,
  height: number,
): IChartApi {
  const chart = createChart(el, {
    width: Math.max(1, el.clientWidth),
    ...baseChartOptions(height),
  });

  const { oracle: oraclePoints, signal } = buildOracleOscillatorData(candles, {
    period: oracle.period,
    signalPeriod: oracle.signalPeriod,
  });

  const baseline = chart.addSeries(BaselineSeries, {
    baseValue: { type: "price", price: 50 },
    relativeGradient: true,
    topFillColor1: "rgba(34, 197, 94, 0.55)",
    topFillColor2: "rgba(250, 204, 14, 0.18)",
    topLineColor: INDICATOR_COLORS.oracleTopLine,
    bottomFillColor1: "rgba(250, 204, 14, 0.18)",
    bottomFillColor2: "rgba(239, 68, 68, 0.55)",
    bottomLineColor: INDICATOR_COLORS.oracleBottomLine,
    lineWidth: 2,
    lineVisible: true,
    lastValueVisible: false,
    priceLineVisible: false,
    crosshairMarkerVisible: false,
    title: "Oracle",
    autoscaleInfoProvider: () => ({
      priceRange: { minValue: 0, maxValue: 100 },
    }),
  });
  baseline.setData(oraclePoints);

  baseline.createPriceLine({
    price: 75,
    color: INDICATOR_COLORS.oracleTopLine,
    lineWidth: 1,
    lineStyle: LineStyle.Solid,
    axisLabelVisible: false,
    title: "",
  });
  baseline.createPriceLine({
    price: 25,
    color: INDICATOR_COLORS.oracleBottomLine,
    lineWidth: 1,
    lineStyle: LineStyle.Solid,
    axisLabelVisible: false,
    title: "",
  });

  if (signal.length > 0) {
    const signalLine = chart.addSeries(LineSeries, {
      color: INDICATOR_COLORS.oracleSignal,
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
      title: "Signal",
      autoscaleInfoProvider: () => ({
        priceRange: { minValue: 0, maxValue: 100 },
      }),
    });
    signalLine.setData(signal);
  }

  return chart;
}

function mountRsiChart(
  el: HTMLDivElement,
  candles: PriceCandle[],
  oscillator: OscillatorConfig,
  height: number,
): IChartApi {
  const chart = createChart(el, {
    width: Math.max(1, el.clientWidth),
    ...baseChartOptions(height),
  });

  const rsi = chart.addSeries(LineSeries, {
    color: INDICATOR_COLORS.rsi,
    lineWidth: 2,
    priceLineVisible: false,
    lastValueVisible: false,
    title: `RSI ${oscillator.period}`,
    autoscaleInfoProvider: () => ({
      priceRange: { minValue: 0, maxValue: 100 },
    }),
  });
  rsi.setData(buildRsiLineData(candles, oscillator.period));

  rsi.createPriceLine({
    price: 70,
    color: "rgba(113, 113, 122, 0.45)",
    lineWidth: 1,
    lineStyle: LineStyle.Dotted,
    axisLabelVisible: false,
    title: "",
  });
  rsi.createPriceLine({
    price: 30,
    color: "rgba(113, 113, 122, 0.45)",
    lineWidth: 1,
    lineStyle: LineStyle.Dotted,
    axisLabelVisible: false,
    title: "",
  });

  const divergences = detectRsiDivergences(candles, oscillator.period, {
    maxSignals: 6,
  });
  const divergenceSeries: ISeriesApi<"Line">[] = [];
  const markers: SeriesMarker<Time>[] = [];

  for (const div of divergences) {
    const color =
      div.type === "bull" ? INDICATOR_COLORS.rsiBull : INDICATOR_COLORS.rsiBear;
    const line = chart.addSeries(LineSeries, {
      color,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
      autoscaleInfoProvider: () => ({
        priceRange: { minValue: 0, maxValue: 100 },
      }),
    });
    line.setData([
      { time: div.start.time, value: div.start.value },
      { time: div.end.time, value: div.end.value },
    ]);
    divergenceSeries.push(line);

    markers.push({
      time: div.end.time,
      position: div.type === "bull" ? "belowBar" : "aboveBar",
      color,
      shape: "square",
      text: div.type === "bull" ? "Bull" : "Bear",
      size: 1.2,
    });
  }

  markers.sort((a, b) => {
    const ta = typeof a.time === "number" ? a.time : String(a.time);
    const tb = typeof b.time === "number" ? b.time : String(b.time);
    return ta < tb ? -1 : ta > tb ? 1 : 0;
  });
  createSeriesMarkers(rsi, markers);

  // Keep refs alive until chart.remove(); series are owned by chart.
  void divergenceSeries;

  return chart;
}

/**
 * Pane(s) de oscilador debajo del precio.
 * Oracle (baseline fill) y RSI con señales Bull/Bear por divergencia — charts separados, sync externo.
 */
export function TickerOscillatorPane({
  symbol,
  candles,
  oscillator,
  oracle,
  height = 120,
  className = "",
  onApisReady,
}: TickerOscillatorPaneProps) {
  const oracleRef = useRef<HTMLDivElement | null>(null);
  const rsiRef = useRef<HTMLDivElement | null>(null);
  const onApisReadyRef = useRef(onApisReady);
  onApisReadyRef.current = onApisReady;

  const showOracle = oracle.enabled && candles.length > 0;
  const showRsi = oscillator.enabled && candles.length > 0;
  const active = showOracle || showRsi;

  useEffect(() => {
    if (!active) {
      onApisReadyRef.current?.([]);
      return;
    }

    const charts: IChartApi[] = [];
    const cleanups: Array<() => void> = [];

    if (showOracle && oracleRef.current) {
      const chart = mountOracleChart(
        oracleRef.current,
        candles,
        oracle,
        height,
      );
      charts.push(chart);
      const el = oracleRef.current;
      const ro =
        typeof ResizeObserver !== "undefined"
          ? new ResizeObserver((entries) => {
              const width = entries[0]?.contentRect.width;
              if (width && width > 0) {
                chart.applyOptions({ width: Math.floor(width), height });
              }
            })
          : null;
      ro?.observe(el);
      cleanups.push(() => {
        ro?.disconnect();
        chart.remove();
      });
    }

    if (showRsi && rsiRef.current) {
      const chart = mountRsiChart(rsiRef.current, candles, oscillator, height);
      charts.push(chart);
      const el = rsiRef.current;
      const ro =
        typeof ResizeObserver !== "undefined"
          ? new ResizeObserver((entries) => {
              const width = entries[0]?.contentRect.width;
              if (width && width > 0) {
                chart.applyOptions({ width: Math.floor(width), height });
              }
            })
          : null;
      ro?.observe(el);
      cleanups.push(() => {
        ro?.disconnect();
        chart.remove();
      });
    }

    onApisReadyRef.current?.(charts);

    return () => {
      onApisReadyRef.current?.([]);
      for (const cleanup of cleanups) cleanup();
    };
  }, [symbol, candles, oscillator, oracle, height, active, showOracle, showRsi]);

  if (!active) {
    return (
      <div
        className={`relative w-full overflow-hidden rounded border border-zinc-800 bg-zinc-950 ${className}`}
        style={{ height }}
        data-symbol={symbol}
        data-pane="oscillator"
      >
        <div className="flex h-full flex-col items-start justify-center gap-1 px-3">
          <span className="font-mono text-[9px] uppercase tracking-wide text-zinc-600">
            Oscillator · reserved
          </span>
          <span className="font-mono text-[10px] text-zinc-700">
            Activá Oracle o RSI en Ind — pane separado del precio
          </span>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`flex w-full flex-col gap-1.5 ${className}`}
      data-symbol={symbol}
      data-pane="oscillator-stack"
    >
      {showOracle && (
        <div
          className="relative overflow-hidden rounded border border-zinc-800 bg-zinc-950"
          style={{ height }}
        >
          <span className="pointer-events-none absolute left-2 top-1.5 z-10 font-mono text-[9px] uppercase tracking-wide text-zinc-500">
            Oracle Oscillator
          </span>
          <div ref={oracleRef} className="h-full w-full" />
        </div>
      )}
      {showRsi && (
        <div
          className="relative overflow-hidden rounded border border-zinc-800 bg-zinc-950"
          style={{ height }}
        >
          <span className="pointer-events-none absolute left-2 top-1.5 z-10 font-mono text-[9px] uppercase tracking-wide text-zinc-500">
            Indicador de divergencia RSI
          </span>
          <div ref={rsiRef} className="h-full w-full" />
        </div>
      )}
    </div>
  );
}
