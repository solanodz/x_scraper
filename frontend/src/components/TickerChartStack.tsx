"use client";

import { useCallback, useEffect, useState } from "react";
import type { IChartApi } from "lightweight-charts";
import { TickerChart, type TickerChartIndicators } from "@/components/TickerChart";
import { TickerOscillatorPane } from "@/components/TickerOscillatorPane";
import { bindSyncedTimeScaleGroup } from "@/lib/chartTimeSync";
import type { PriceCandle } from "@/lib/types";

interface TickerChartStackProps {
  symbol: string;
  candles: PriceCandle[];
  indicators: TickerChartIndicators;
  /** Height of the price chart only. */
  priceHeight?: number;
  /** Height of each oscillator pane (Oracle / RSI). */
  oscillatorHeight?: number;
  className?: string;
  /** When true, price chart fills remaining space (omit priceHeight). */
  fillPrice?: boolean;
}

/**
 * Precio (arriba) + Oracle / RSI debajo, con zoom/pan sincronizado entre todos.
 */
export function TickerChartStack({
  symbol,
  candles,
  indicators,
  priceHeight = 320,
  oscillatorHeight = 128,
  className = "",
  fillPrice = false,
}: TickerChartStackProps) {
  const [priceApi, setPriceApi] = useState<IChartApi | null>(null);
  const [oscApis, setOscApis] = useState<IChartApi[]>([]);

  const onPriceReady = useCallback((api: IChartApi | null) => {
    setPriceApi(api);
  }, []);

  const onOscApisReady = useCallback((apis: IChartApi[]) => {
    setOscApis(apis);
  }, []);

  useEffect(() => {
    const group = [priceApi, ...oscApis].filter(
      (api): api is IChartApi => api != null,
    );
    if (group.length < 2) return;
    return bindSyncedTimeScaleGroup(group);
  }, [priceApi, oscApis]);

  return (
    <div
      className={`flex min-h-0 flex-col gap-1.5 ${className}`}
      data-component="ticker-chart-stack"
    >
      <div className={fillPrice ? "min-h-0 flex-1" : undefined}>
        <TickerChart
          symbol={symbol}
          candles={candles}
          indicators={indicators}
          height={fillPrice ? undefined : priceHeight}
          className={fillPrice ? "h-full" : undefined}
          onApiReady={onPriceReady}
        />
      </div>
      <TickerOscillatorPane
        symbol={symbol}
        candles={candles}
        oscillator={indicators.oscillator}
        oracle={indicators.oracle}
        height={oscillatorHeight}
        className="shrink-0"
        onApisReady={onOscApisReady}
      />
    </div>
  );
}
