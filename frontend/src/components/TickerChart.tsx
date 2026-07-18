"use client";

import { useEffect, useRef } from "react";
import {
  CandlestickSeries,
  ColorType,
  createChart,
  HistogramSeries,
  LineSeries,
  LineStyle,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
} from "lightweight-charts";
import {
  buildDonchianLineData,
  buildFibonacciLevelData,
  buildSmaLineData,
  buildVolumeHistogramData,
  INDICATOR_COLORS,
  toLwcCandlestickData,
} from "@/lib/chartIndicators";
import type { ChartViewConfig } from "@/lib/tickerChartPrefs";
import type { PriceCandle } from "@/lib/types";

export type TickerChartIndicators = Pick<
  ChartViewConfig,
  "smaA" | "smaB" | "donchian" | "fib" | "volume"
>;

export interface TickerChartProps {
  symbol: string;
  candles: PriceCandle[];
  indicators: TickerChartIndicators;
  height?: number;
  className?: string;
}

const BG = "#09090b"; // zinc-950
const GRID = "#27272a"; // zinc-800
const TEXT = "#a1a1aa"; // zinc-400
const BORDER = "#3f3f46"; // zinc-700

export function TickerChart({
  symbol,
  candles,
  indicators,
  height = 360,
  className = "",
}: TickerChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || candles.length === 0) return;

    const chart: IChartApi = createChart(el, {
      width: el.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: BG },
        textColor: TEXT,
        attributionLogo: false,
        panes: {
          separatorColor: GRID,
          separatorHoverColor: "#3f3f46",
          enableResize: true,
        },
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
      },
      timeScale: {
        borderColor: BORDER,
        timeVisible: true,
        secondsVisible: false,
      },
    });

    const candleSeries = chart.addSeries(
      CandlestickSeries,
      {
        upColor: "#34d399",
        downColor: "#f87171",
        borderUpColor: "#34d399",
        borderDownColor: "#f87171",
        wickUpColor: "#34d399",
        wickDownColor: "#f87171",
      },
      0,
    );
    candleSeries.setData(toLwcCandlestickData(candles));

    const overlaySeries: ISeriesApi<"Line">[] = [];
    const priceLines: IPriceLine[] = [];

    if (indicators.smaA.enabled) {
      const smaA = chart.addSeries(
        LineSeries,
        {
          color: INDICATOR_COLORS.smaA,
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: true,
          title: `SMA ${indicators.smaA.length}`,
        },
        0,
      );
      smaA.setData(buildSmaLineData(candles, indicators.smaA.length));
      overlaySeries.push(smaA);
    }

    if (indicators.smaB.enabled) {
      const smaB = chart.addSeries(
        LineSeries,
        {
          color: INDICATOR_COLORS.smaB,
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: true,
          title: `SMA ${indicators.smaB.length}`,
        },
        0,
      );
      smaB.setData(buildSmaLineData(candles, indicators.smaB.length));
      overlaySeries.push(smaB);
    }

    if (indicators.donchian.enabled) {
      const channel = buildDonchianLineData(candles, indicators.donchian.period);
      const upper = chart.addSeries(
        LineSeries,
        {
          color: INDICATOR_COLORS.donchianUpper,
          lineWidth: 1,
          lineStyle: LineStyle.Dotted,
          priceLineVisible: false,
          lastValueVisible: false,
          title: "DC Upper",
        },
        0,
      );
      upper.setData(channel.upper);
      overlaySeries.push(upper);

      const lower = chart.addSeries(
        LineSeries,
        {
          color: INDICATOR_COLORS.donchianLower,
          lineWidth: 1,
          lineStyle: LineStyle.Dotted,
          priceLineVisible: false,
          lastValueVisible: false,
          title: "DC Lower",
        },
        0,
      );
      lower.setData(channel.lower);
      overlaySeries.push(lower);
    }

    if (indicators.fib) {
      const levels = buildFibonacciLevelData(candles, true);
      for (const level of levels) {
        priceLines.push(
          candleSeries.createPriceLine({
            price: level.price,
            color: INDICATOR_COLORS.fib,
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: `Fib ${level.ratio}`,
          }),
        );
      }
    }

    if (indicators.volume) {
      chart.addPane(true);
      const volumeSeries = chart.addSeries(
        HistogramSeries,
        {
          priceFormat: { type: "volume" },
          priceLineVisible: false,
          lastValueVisible: false,
        },
        1,
      );
      volumeSeries.setData(buildVolumeHistogramData(candles));
      const panes = chart.panes();
      if (panes[0]) panes[0].setStretchFactor(3);
      if (panes[1]) panes[1].setStretchFactor(1);
    }

    chart.timeScale().fitContent();

    const ro =
      typeof ResizeObserver !== "undefined"
        ? new ResizeObserver((entries) => {
            const width = entries[0]?.contentRect.width;
            if (width && width > 0) {
              chart.applyOptions({ width, height });
            }
          })
        : null;
    ro?.observe(el);

    return () => {
      ro?.disconnect();
      for (const line of priceLines) {
        try {
          candleSeries.removePriceLine(line);
        } catch {
          // chart may already be disposed
        }
      }
      for (const series of overlaySeries) {
        try {
          chart.removeSeries(series);
        } catch {
          // ignore
        }
      }
      chart.remove();
    };
  }, [symbol, candles, indicators, height]);

  if (candles.length === 0) {
    return (
      <div
        className={`flex items-center justify-center rounded border border-zinc-800 bg-zinc-950 font-mono text-xs text-zinc-500 ${className}`}
        style={{ height }}
      >
        {`Sin velas para $${symbol}`}
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`w-full overflow-hidden rounded border border-zinc-800 bg-zinc-950 ${className}`}
      style={{ height }}
      data-symbol={symbol}
    />
  );
}
