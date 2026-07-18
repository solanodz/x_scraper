import { NextRequest, NextResponse } from "next/server";
import { yahooFinanceSymbol } from "@/lib/marketSymbols";

type YahooChartResponse = {
  chart?: {
    result?: Array<{
      timestamp?: number[];
      indicators?: {
        quote?: Array<{
          open?: Array<number | null>;
          high?: Array<number | null>;
          low?: Array<number | null>;
          close?: Array<number | null>;
          volume?: Array<number | null>;
        }>;
      };
    }>;
    error?: { description?: string };
  };
};

const VALID_PERIODS = new Set([
  "1d",
  "5d",
  "1mo",
  "3mo",
  "6mo",
  "1y",
  "2y",
  "5y",
]);

const VALID_INTERVALS = new Set([
  "1m",
  "5m",
  "15m",
  "30m",
  "1h",
  "1d",
  "1wk",
]);

const PERIOD_ORDER = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"] as const;
const INTRADAY_INTERVALS = new Set(["1m", "5m", "15m", "30m", "1h"]);

function normalizeSymbol(raw: string): string {
  return raw.trim().replace(/^\$/, "").toUpperCase();
}

function normalizePeriod(raw: string | null): string {
  const period = (raw ?? "1y").trim();
  return VALID_PERIODS.has(period) ? period : "1y";
}

function normalizeInterval(raw: string | null): string {
  const interval = (raw ?? "1d").trim();
  return VALID_INTERVALS.has(interval) ? interval : "1d";
}

/** Acorta la ventana si supera límites Yahoo para el intervalo. */
function clampPeriodForInterval(period: string, interval: string): string {
  let maxPeriod: string | null = null;
  if (interval === "1m") {
    maxPeriod = "5d"; // Yahoo: 1m max ~7d
  } else if (INTRADAY_INTERVALS.has(interval)) {
    maxPeriod = "1mo"; // Yahoo: intradía <1d max ~60d
  }
  if (!maxPeriod) return period;

  const periodIdx = PERIOD_ORDER.indexOf(period as (typeof PERIOD_ORDER)[number]);
  const maxIdx = PERIOD_ORDER.indexOf(maxPeriod as (typeof PERIOD_ORDER)[number]);
  if (periodIdx < 0 || maxIdx < 0) return maxPeriod;
  return periodIdx > maxIdx ? maxPeriod : period;
}

function formatCandleDate(tsSeconds: number, interval: string): string {
  const iso = new Date(tsSeconds * 1000).toISOString();
  if (interval === "1d" || interval === "1wk") {
    return iso.slice(0, 10);
  }
  return iso;
}

export async function GET(request: NextRequest) {
  const symbol = normalizeSymbol(request.nextUrl.searchParams.get("symbol") ?? "");
  const interval = normalizeInterval(request.nextUrl.searchParams.get("interval"));
  const period = clampPeriodForInterval(
    normalizePeriod(request.nextUrl.searchParams.get("period")),
    interval,
  );

  if (!symbol) {
    return NextResponse.json(
      {
        symbol: "",
        period,
        interval,
        candles: [],
        data_points: 0,
        error: "symbol required",
      },
      { status: 400 },
    );
  }

  try {
    const yahooSymbol = yahooFinanceSymbol(symbol);
    const url =
      `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(yahooSymbol)}` +
      `?range=${period}&interval=${encodeURIComponent(interval)}&includePrePost=false`;
    const res = await fetch(url, {
      headers: { "User-Agent": "Mozilla/5.0" },
      cache: "no-store",
    });
    if (!res.ok) {
      return NextResponse.json(
        {
          symbol,
          period,
          interval,
          candles: [],
          data_points: 0,
          error: `yahoo finance ${res.status}`,
        },
        { status: 502 },
      );
    }

    const payload = (await res.json()) as YahooChartResponse;
    const result = payload.chart?.result?.[0];
    const quote = result?.indicators?.quote?.[0];
    const timestamps = result?.timestamp ?? [];

    if (!quote || timestamps.length === 0) {
      return NextResponse.json({
        symbol,
        period,
        interval,
        candles: [],
        data_points: 0,
        error: payload.chart?.error?.description ?? "sin datos históricos",
      });
    }

    const candles = timestamps
      .map((ts, index) => {
        const open = quote.open?.[index];
        const high = quote.high?.[index];
        const low = quote.low?.[index];
        const close = quote.close?.[index];
        if (
          open == null ||
          high == null ||
          low == null ||
          close == null ||
          Number.isNaN(open) ||
          Number.isNaN(high) ||
          Number.isNaN(low) ||
          Number.isNaN(close)
        ) {
          return null;
        }
        return {
          date: formatCandleDate(ts, interval),
          open: Number(open.toFixed(4)),
          high: Number(high.toFixed(4)),
          low: Number(low.toFixed(4)),
          close: Number(close.toFixed(4)),
          volume: Number(quote.volume?.[index] ?? 0),
        };
      })
      .filter((row): row is NonNullable<typeof row> => row !== null);

    return NextResponse.json({
      symbol,
      period,
      interval,
      candles,
      data_points: candles.length,
    });
  } catch (error) {
    return NextResponse.json(
      {
        symbol,
        period,
        interval,
        candles: [],
        data_points: 0,
        error: error instanceof Error ? error.message : "fetch failed",
      },
      { status: 500 },
    );
  }
}
