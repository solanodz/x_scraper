"use client";

import { useEffect, useMemo, useRef } from "react";
import { tradingViewSymbol } from "@/lib/tradingview";
import type { ChartPlanTradingViewStudy } from "@/lib/types";

interface TradingViewAdvancedChartProps {
  symbol: string;
  interval: string;
  studies?: ChartPlanTradingViewStudy[];
  compact?: boolean;
  className?: string;
}

function normalizeStudies(
  studies: ChartPlanTradingViewStudy[] | undefined,
): Array<{ id: string; inputs?: Record<string, number | string> }> {
  if (!studies?.length) return [];
  return studies
    .filter((study) => study.id?.trim())
    .slice(0, 6)
    .map((study) => {
      const entry: { id: string; inputs?: Record<string, number | string> } = {
        id: study.id.trim(),
      };
      if (study.inputs && Object.keys(study.inputs).length > 0) {
        entry.inputs = study.inputs;
      }
      return entry;
    });
}

export default function TradingViewAdvancedChart({
  symbol,
  interval,
  studies,
  compact = true,
  className = "h-[360px] w-full rounded border border-zinc-800",
}: TradingViewAdvancedChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const studiesKey = useMemo(
    () => JSON.stringify(normalizeStudies(studies)),
    [studies],
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    container.innerHTML = "";

    const widgetHost = document.createElement("div");
    widgetHost.className = "tradingview-widget-container h-full w-full";
    widgetHost.style.height = "100%";
    widgetHost.style.width = "100%";

    const widgetSurface = document.createElement("div");
    widgetSurface.className = "tradingview-widget-container__widget h-full w-full";
    widgetSurface.style.height = "100%";
    widgetSurface.style.width = "100%";
    widgetHost.appendChild(widgetSurface);
    container.appendChild(widgetHost);

    const normalizedStudies = normalizeStudies(studies);
    const config: Record<string, unknown> = {
      autosize: true,
      symbol: tradingViewSymbol(symbol),
      interval,
      timezone: "America/New_York",
      theme: "dark",
      backgroundColor: "#09090b",
      style: "1",
      locale: "en",
      hide_top_toolbar: compact,
      hide_side_toolbar: compact,
      allow_symbol_change: false,
      save_image: false,
      withdateranges: !compact,
      hideideas: true,
      support_host: "https://www.tradingview.com",
    };
    if (normalizedStudies.length > 0) {
      config.studies = normalizedStudies;
    }

    const script = document.createElement("script");
    script.src =
      "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.type = "text/javascript";
    script.async = true;
    script.innerHTML = JSON.stringify(config);
    widgetHost.appendChild(script);

    return () => {
      container.innerHTML = "";
    };
  }, [symbol, interval, compact, studiesKey]);

  return <div ref={containerRef} className={className} />;
}
