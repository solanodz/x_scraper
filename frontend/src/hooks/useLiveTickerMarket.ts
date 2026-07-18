"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchPriceCandles, fetchQuotes } from "@/lib/api";
import {
  MARKET_QUOTE_POLL_MS,
  candlesPollMsForInterval,
  mergeLiveQuoteIntoCandles,
} from "@/lib/marketRefresh";
import type { PriceCandle, Quote } from "@/lib/types";

interface UseLiveTickerMarketOptions {
  period?: string;
  interval?: string;
}

interface UseLiveTickerMarketResult {
  quote: Quote | null;
  candles: PriceCandle[];
  candlesLoading: boolean;
  candlesError: string | null;
  quoteUpdatedAt: number | null;
  candlesUpdatedAt: number | null;
  refreshNow: () => Promise<void>;
}

export function useLiveTickerMarket(
  symbol: string,
  options: UseLiveTickerMarketOptions = {},
): UseLiveTickerMarketResult {
  const period = options.period ?? "1y";
  const interval = options.interval ?? "1d";

  const [quote, setQuote] = useState<Quote | null>(null);
  const [baseCandles, setBaseCandles] = useState<PriceCandle[]>([]);
  const [candlesLoading, setCandlesLoading] = useState(true);
  const [candlesError, setCandlesError] = useState<string | null>(null);
  const [quoteUpdatedAt, setQuoteUpdatedAt] = useState<number | null>(null);
  const [candlesUpdatedAt, setCandlesUpdatedAt] = useState<number | null>(null);
  const [, setAgeTick] = useState(0);
  const symbolRef = useRef(symbol);
  const periodRef = useRef(period);
  const intervalRef = useRef(interval);

  const loadQuote = useCallback(async (ticker: string, silent = true) => {
    try {
      const quotes = await fetchQuotes([ticker]);
      const next = quotes[0] ?? null;
      if (symbolRef.current !== ticker) return;
      setQuote(next);
      setQuoteUpdatedAt(Date.now());
      return next;
    } catch {
      if (!silent && symbolRef.current === ticker) {
        setQuote(null);
      }
      return null;
    }
  }, []);

  const loadCandles = useCallback(async (ticker: string, silent = false) => {
    const p = periodRef.current;
    const i = intervalRef.current;
    if (!silent) {
      setCandlesLoading(true);
      setCandlesError(null);
    }
    try {
      const payload = await fetchPriceCandles(ticker, p, i);
      if (symbolRef.current !== ticker) return;
      if (periodRef.current !== p || intervalRef.current !== i) return;
      if (payload.error) {
        setBaseCandles([]);
        setCandlesError(payload.error);
        return;
      }
      setBaseCandles(payload.candles ?? []);
      setCandlesUpdatedAt(Date.now());
      setCandlesError(null);
    } catch (err) {
      if (symbolRef.current !== ticker) return;
      setBaseCandles([]);
      const message =
        err instanceof Error ? err.message : "No se pudieron cargar las velas de precio";
      setCandlesError(message);
    } finally {
      if (!silent && symbolRef.current === ticker) {
        setCandlesLoading(false);
      }
    }
  }, []);

  const refreshNow = useCallback(async () => {
    const ticker = symbolRef.current;
    await Promise.all([loadQuote(ticker, true), loadCandles(ticker, true)]);
  }, [loadCandles, loadQuote]);

  useEffect(() => {
    symbolRef.current = symbol;
    periodRef.current = period;
    intervalRef.current = interval;
    setQuote(null);
    setBaseCandles([]);
    setCandlesLoading(true);
    setCandlesError(null);
    setQuoteUpdatedAt(null);
    setCandlesUpdatedAt(null);

    void (async () => {
      await Promise.all([loadQuote(symbol, true), loadCandles(symbol, false)]);
    })();

    const quoteTimer = window.setInterval(() => {
      void loadQuote(symbol, true);
    }, MARKET_QUOTE_POLL_MS);

    const candlesTimer = window.setInterval(() => {
      void loadCandles(symbol, true);
    }, candlesPollMsForInterval(interval));

    return () => {
      window.clearInterval(quoteTimer);
      window.clearInterval(candlesTimer);
    };
  }, [symbol, period, interval, loadCandles, loadQuote]);

  useEffect(() => {
    const ageTimer = window.setInterval(() => {
      setAgeTick((value) => value + 1);
    }, 10_000);
    return () => window.clearInterval(ageTimer);
  }, []);

  const candles = useMemo(
    () => mergeLiveQuoteIntoCandles(baseCandles, quote, interval),
    [baseCandles, quote, interval],
  );

  return {
    quote,
    candles,
    candlesLoading,
    candlesError,
    quoteUpdatedAt,
    candlesUpdatedAt,
    refreshNow,
  };
}
