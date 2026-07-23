"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import TerminalAuthGate from "@/components/TerminalAuthGate";
import TerminalHeader from "@/components/TerminalHeader";
import TickerLogo from "@/components/TickerLogo";
import {
  closeBotPosition,
  fetchTickerLogos,
  getBotConfig,
  listBotEvents,
  listBotFills,
  listBotPositions,
  patchBotConfig,
} from "@/lib/api";
import type { BotConfig, BotEvent, BotFill, BotPosition } from "@/lib/types";

const SYMBOL_OPTIONS = ["BTC", "ETH"] as const;
const INTERVAL_OPTIONS = ["15m", "30m", "1h", "4h", "1d"] as const;
/** Paper account baseline for equity curve (USD). */
const PAPER_START_USD = 10_000;

const INPUT =
  "w-full rounded border border-zinc-800 bg-zinc-950 px-2 py-1.5 font-mono text-xs text-zinc-200 outline-none focus:border-zinc-600";
const LABEL =
  "mb-1 block font-sans text-[10px] uppercase tracking-wide text-zinc-500";

type ConfigFormState = {
  symbols: string[];
  max_positions: number;
  size_usd: number;
  leverage: number;
  tp_pct: number;
  sl_pct: number;
  donchian_period: number;
  donchian_interval: string;
  cooldown_seconds: number;
};

function configToForm(cfg: BotConfig): ConfigFormState {
  return {
    symbols: [...cfg.symbols],
    max_positions: cfg.max_positions,
    size_usd: cfg.size_usd,
    leverage: cfg.leverage,
    tp_pct: cfg.tp_pct,
    sl_pct: cfg.sl_pct,
    donchian_period: cfg.donchian_period,
    donchian_interval: cfg.donchian_interval,
    cooldown_seconds: cfg.cooldown_seconds,
  };
}

function formatNum(value: number | null | undefined, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return value.toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: 0,
  });
}

function formatUsd(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}$${formatNum(Math.abs(value), 2)}`;
}

function formatTs(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function unrealizedUsd(p: BotPosition): number | null {
  const entry = p.entry_price;
  const mark = p.mark_price;
  const qty = p.qty;
  if (
    entry == null ||
    mark == null ||
    qty == null ||
    !Number.isFinite(entry) ||
    !Number.isFinite(mark) ||
    !Number.isFinite(qty)
  ) {
    return null;
  }
  const delta = mark - entry;
  return p.side === "short" ? -delta * qty : delta * qty;
}

function unrealizedPct(p: BotPosition): number | null {
  const entry = p.entry_price;
  const mark = p.mark_price;
  if (entry == null || mark == null || !Number.isFinite(entry) || entry === 0) {
    return null;
  }
  if (!Number.isFinite(mark)) return null;
  const raw = ((mark - entry) / entry) * 100;
  return p.side === "short" ? -raw : raw;
}

function signedClass(value: number | null | undefined): string {
  if (value == null || value === 0 || !Number.isFinite(value)) {
    return "text-zinc-400";
  }
  return value > 0 ? "text-emerald-500" : "text-red-500";
}

function sideClass(side: string): string {
  return side === "long" ? "text-emerald-500" : "text-red-500";
}

function clampInt(
  raw: string,
  min: number,
  max: number,
  fallback: number,
): number {
  const n = Number.parseInt(raw, 10);
  if (!Number.isFinite(n)) return fallback;
  return Math.min(max, Math.max(min, n));
}

type EquityPoint = { t: string; label: string; equity: number; pnl: number };

function buildStats(open: BotPosition[], closed: BotPosition[]) {
  const realized = closed.reduce(
    (sum, p) => sum + (Number.isFinite(p.realized_pnl) ? Number(p.realized_pnl) : 0),
    0,
  );
  const unrealized = open.reduce((sum, p) => {
    const u = unrealizedUsd(p);
    return sum + (u ?? 0);
  }, 0);

  const wins = closed.filter((p) => (p.realized_pnl ?? 0) > 0);
  const losses = closed.filter((p) => (p.realized_pnl ?? 0) < 0);
  const avgWin =
    wins.length > 0
      ? wins.reduce((s, p) => s + Number(p.realized_pnl), 0) / wins.length
      : null;
  const avgLoss =
    losses.length > 0
      ? losses.reduce((s, p) => s + Number(p.realized_pnl), 0) / losses.length
      : null;
  const winRate =
    closed.length > 0 ? (wins.length / closed.length) * 100 : null;

  const sorted = [...closed].sort((a, b) => {
    const ta = a.closed_at ? new Date(a.closed_at).getTime() : 0;
    const tb = b.closed_at ? new Date(b.closed_at).getTime() : 0;
    return ta - tb;
  });

  const curve: EquityPoint[] = [
    {
      t: "start",
      label: "Start",
      equity: PAPER_START_USD,
      pnl: 0,
    },
  ];
  let cum = 0;
  for (const p of sorted) {
    cum += Number(p.realized_pnl) || 0;
    curve.push({
      t: p.closed_at || p.id,
      label: formatTs(p.closed_at),
      equity: PAPER_START_USD + cum,
      pnl: cum,
    });
  }
  if (open.length > 0 || curve.length === 1) {
    curve.push({
      t: "now",
      label: "Now",
      equity: PAPER_START_USD + realized + unrealized,
      pnl: realized + unrealized,
    });
  }

  return {
    realized,
    unrealized,
    total: realized + unrealized,
    equity: PAPER_START_USD + realized + unrealized,
    trades: closed.length,
    openCount: open.length,
    winRate,
    avgWin,
    avgLoss,
    curve,
  };
}

function BotPageContent() {
  const [config, setConfig] = useState<BotConfig | null>(null);
  const [form, setForm] = useState<ConfigFormState | null>(null);
  const [positions, setPositions] = useState<BotPosition[]>([]);
  const [closedPositions, setClosedPositions] = useState<BotPosition[]>([]);
  const [fills, setFills] = useState<BotFill[]>([]);
  const [events, setEvents] = useState<BotEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [arming, setArming] = useState(false);
  const [closingId, setClosingId] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [logos, setLogos] = useState<Record<string, string | null>>({});
  const [configOpen, setConfigOpen] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void fetchTickerLogos([...SYMBOL_OPTIONS])
      .then((map) => {
        if (!cancelled) setLogos(map);
      })
      .catch(() => {
        if (!cancelled) setLogos({});
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [cfg, openPositions, closed, recentFills, recentEvents] =
        await Promise.all([
          getBotConfig(),
          listBotPositions("open"),
          listBotPositions("closed"),
          listBotFills(),
          listBotEvents(),
        ]);
      setConfig(cfg);
      setForm(configToForm(cfg));
      setPositions(openPositions);
      setClosedPositions(closed);
      setFills(recentFills);
      setEvents(recentEvents);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setConfig(null);
      setForm(null);
      setPositions([]);
      setClosedPositions([]);
      setFills([]);
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const stats = useMemo(
    () => buildStats(positions, closedPositions),
    [positions, closedPositions],
  );

  async function handleToggleArmed() {
    if (!config) return;
    setArming(true);
    setActionMsg(null);
    try {
      const next = await patchBotConfig({ armed: !config.armed });
      setConfig(next);
      setForm(configToForm(next));
      setActionMsg(next.armed ? "Armed" : "Paused");
    } catch (err) {
      setActionMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setArming(false);
    }
  }

  async function handleSaveConfig(e: FormEvent) {
    e.preventDefault();
    if (!form) return;
    setSaving(true);
    setActionMsg(null);
    try {
      const next = await patchBotConfig({
        symbols: form.symbols,
        max_positions: form.max_positions,
        size_usd: form.size_usd,
        leverage: form.leverage,
        tp_pct: form.tp_pct,
        sl_pct: form.sl_pct,
        donchian_period: form.donchian_period,
        donchian_interval: form.donchian_interval,
        cooldown_seconds: form.cooldown_seconds,
      });
      setConfig(next);
      setForm(configToForm(next));
      setActionMsg("Saved");
    } catch (err) {
      setActionMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleClosePosition(id: string) {
    setClosingId(id);
    setActionMsg(null);
    try {
      await closeBotPosition(id);
      setActionMsg("Closed");
      await loadAll();
    } catch (err) {
      setActionMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setClosingId(null);
    }
  }

  function toggleSymbol(symbol: string) {
    if (!form) return;
    const has = form.symbols.includes(symbol);
    const next = has
      ? form.symbols.filter((s) => s !== symbol)
      : [...form.symbols, symbol];
    setForm({ ...form, symbols: next.length > 0 ? next : form.symbols });
  }

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-zinc-950">
      <TerminalHeader onRefreshComplete={() => void loadAll()} />
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {/* Main */}
        <main className="min-h-0 min-w-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-6xl space-y-6 px-4 py-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="font-sans text-sm font-semibold text-zinc-100">
                    Paper Bot
                  </h1>
                  <span className="font-mono text-[10px] text-zinc-500">
                    paper · HL off · start ${formatNum(PAPER_START_USD, 0)}
                    
                  </span>
                </div>
                <p className="mt-1 font-sans text-xs text-zinc-500">
                  Donchian BTC/ETH. Simulated — not investment advice.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {actionMsg && (
                  <span className="font-mono text-[11px] text-zinc-500">
                    {actionMsg}
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => setConfigOpen((v) => !v)}
                  className="rounded border border-zinc-800 px-2.5 py-1.5 font-sans text-xs text-zinc-400 hover:border-zinc-600 hover:text-zinc-200 lg:hidden"
                >
                  {configOpen ? "Hide config" : "Config"}
                </button>
                <button
                  type="button"
                  onClick={() => void loadAll()}
                  disabled={loading}
                  className="rounded border border-zinc-800 px-2.5 py-1.5 font-sans text-xs text-zinc-400 hover:border-zinc-600 hover:text-zinc-200 disabled:opacity-50"
                >
                  Reload
                </button>
                <button
                  type="button"
                  onClick={() => void handleToggleArmed()}
                  disabled={!config || arming || loading}
                  className="rounded border border-zinc-700 bg-zinc-900 px-3 py-1.5 font-sans text-xs font-medium text-zinc-200 hover:border-zinc-500 disabled:opacity-50"
                >
                  {arming ? "…" : config?.armed ? "Armed" : "Paused"}
                </button>
                <button
                  type="button"
                  onClick={() => setConfigOpen((v) => !v)}
                  className="hidden rounded border border-zinc-800 px-2.5 py-1.5 font-sans text-xs text-zinc-400 hover:border-zinc-600 hover:text-zinc-200 lg:inline-flex"
                >
                  {configOpen ? "Hide config" : "Show config"}
                </button>
              </div>
            </div>

            {loading && (
              <p className="font-mono text-xs text-zinc-600">Loading…</p>
            )}
            {error && (
              <p className="font-mono text-xs text-red-500">{error}</p>
            )}

            {!loading && !error && form && config && (
              <>
                {/* Compact metrics + chart — secondary */}
                <div className="space-y-2 border-b border-zinc-800/80 pb-4">
                  <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 font-mono text-[11px] text-zinc-500">
                    <span>
                      Equity{" "}
                      <span className="text-zinc-300">
                        ${formatNum(stats.equity, 2)}
                      </span>
                    </span>
                    <span>
                      PnL{" "}
                      <span className={signedClass(stats.total)}>
                        {formatUsd(stats.total)}
                      </span>
                    </span>
                    <span>
                      Real{" "}
                      <span className={signedClass(stats.realized)}>
                        {formatUsd(stats.realized)}
                      </span>
                    </span>
                    <span>
                      Unreal{" "}
                      <span className={signedClass(stats.unrealized)}>
                        {formatUsd(stats.unrealized)}
                      </span>
                    </span>
                    <span>
                      Trades{" "}
                      <span className="text-zinc-400">
                        {stats.trades}c / {stats.openCount}o
                      </span>
                    </span>
                    <span>
                      Win{" "}
                      <span
                        className={
                          stats.winRate == null
                            ? "text-zinc-500"
                            : stats.winRate >= 50
                              ? "text-emerald-500"
                              : "text-red-500"
                        }
                      >
                        {stats.winRate == null
                          ? "—"
                          : `${formatNum(stats.winRate, 0)}%`}
                      </span>
                    </span>
                    <span>
                      AvgW{" "}
                      <span className={signedClass(stats.avgWin)}>
                        {formatUsd(stats.avgWin)}
                      </span>
                    </span>
                    <span>
                      AvgL{" "}
                      <span className={signedClass(stats.avgLoss)}>
                        {formatUsd(stats.avgLoss)}
                      </span>
                    </span>
                  </div>
                  <div className="h-28 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart
                        data={stats.curve}
                        margin={{ top: 4, right: 4, left: 0, bottom: 0 }}
                      >
                        <defs>
                          <linearGradient
                            id="equityFill"
                            x1="0"
                            y1="0"
                            x2="0"
                            y2="1"
                          >
                            <stop
                              offset="0%"
                              stopColor={
                                stats.total >= 0 ? "#10b981" : "#ef4444"
                              }
                              stopOpacity={0.25}
                            />
                            <stop
                              offset="100%"
                              stopColor={
                                stats.total >= 0 ? "#10b981" : "#ef4444"
                              }
                              stopOpacity={0}
                            />
                          </linearGradient>
                        </defs>
                        <XAxis dataKey="label" hide />
                        <YAxis hide domain={["auto", "auto"]} />
                        <Tooltip
                          contentStyle={{
                            background: "#09090b",
                            border: "1px solid #27272a",
                            borderRadius: 6,
                            fontSize: 10,
                            fontFamily: "ui-monospace, monospace",
                          }}
                          labelStyle={{ color: "#a1a1aa" }}
                          formatter={(value) => [
                            `$${formatNum(Number(value), 2)}`,
                            "Equity",
                          ]}
                        />
                        <Area
                          type="monotone"
                          dataKey="equity"
                          stroke={stats.total >= 0 ? "#10b981" : "#ef4444"}
                          fill="url(#equityFill)"
                          strokeWidth={1.5}
                          isAnimationActive={false}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Primary: open positions */}
                <section>
                  <h2 className="mb-3 font-sans text-sm font-semibold text-zinc-100">
                    Open positions
                    <span className="ml-2 font-mono text-xs font-normal text-zinc-500">
                      {positions.length}
                    </span>
                  </h2>
                  <div className="overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-900/30">
                    <table className="w-full min-w-[640px] border-collapse text-left">
                      <thead>
                        <tr className="border-b border-zinc-800 font-mono text-[10px] uppercase tracking-wide text-zinc-500">
                          <th className="px-3 py-2 font-medium">Symbol</th>
                          <th className="px-3 py-2 font-medium">Side</th>
                          <th className="px-3 py-2 font-medium">Size</th>
                          <th className="px-3 py-2 font-medium">Entry</th>
                          <th className="px-3 py-2 font-medium">Mark</th>
                          <th className="px-3 py-2 font-medium">PnL</th>
                          <th className="px-3 py-2 font-medium">TP / SL</th>
                          <th className="px-3 py-2 font-medium" />
                        </tr>
                      </thead>
                      <tbody>
                        {positions.length === 0 ? (
                          <tr>
                            <td
                              colSpan={8}
                              className="px-3 py-5 text-center font-mono text-xs text-zinc-600"
                            >
                              No open positions
                            </td>
                          </tr>
                        ) : (
                          positions.map((p) => {
                            const pct = unrealizedPct(p);
                            const usd = unrealizedUsd(p);
                            return (
                              <tr
                                key={p.id}
                                className="border-b border-zinc-800/60 font-mono text-[11px] text-zinc-300 last:border-b-0"
                              >
                                <td className="px-3 py-2.5">
                                  <span className="inline-flex items-center gap-1.5 text-zinc-100">
                                    <TickerLogo
                                      symbol={p.symbol}
                                      logoUrl={logos[p.symbol]}
                                      size="xs"
                                    />
                                    {p.symbol}
                                  </span>
                                </td>
                                <td
                                  className={`px-3 py-2.5 uppercase ${sideClass(p.side)}`}
                                >
                                  {p.side}
                                </td>
                                <td className="px-3 py-2.5">
                                  ${formatNum(p.size_usd)} ·{" "}
                                  {formatNum(p.leverage, 1)}x
                                </td>
                                <td className="px-3 py-2.5">
                                  {formatNum(p.entry_price, 4)}
                                </td>
                                <td className="px-3 py-2.5">
                                  {formatNum(p.mark_price, 4)}
                                </td>
                                <td
                                  className={`px-3 py-2.5 ${signedClass(usd)}`}
                                >
                                  {formatUsd(usd)}
                                  {pct != null
                                    ? ` (${pct > 0 ? "+" : ""}${formatNum(pct, 2)}%)`
                                    : ""}
                                </td>
                                <td className="px-3 py-2.5 text-zinc-500">
                                  <span className="text-emerald-500">
                                    {formatNum(p.tp_price, 2)}
                                  </span>
                                  {" / "}
                                  <span className="text-red-500">
                                    {formatNum(p.sl_price, 2)}
                                  </span>
                                </td>
                                <td className="px-3 py-2.5 text-right">
                                  <button
                                    type="button"
                                    onClick={() =>
                                      void handleClosePosition(p.id)
                                    }
                                    disabled={closingId === p.id}
                                    className="rounded border border-zinc-800 px-2 py-0.5 text-[10px] text-zinc-400 hover:border-zinc-600 hover:text-zinc-200 disabled:opacity-50"
                                  >
                                    {closingId === p.id ? "…" : "Close"}
                                  </button>
                                </td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                    </table>
                  </div>
                </section>

                <div className="grid gap-4 lg:grid-cols-2">
                  <section>
                    <h2 className="mb-3 font-sans text-sm font-semibold text-zinc-100">
                      Fills
                    </h2>
                    <div className="overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-900/30">
                      <table className="w-full min-w-[360px] border-collapse text-left">
                        <thead>
                          <tr className="border-b border-zinc-800/80 font-mono text-[10px] uppercase tracking-wide text-zinc-500">
                            <th className="px-3 py-2 font-medium">Time</th>
                            <th className="px-3 py-2 font-medium">Symbol</th>
                            <th className="px-3 py-2 font-medium">Side</th>
                            <th className="px-3 py-2 font-medium">Price</th>
                            <th className="px-3 py-2 font-medium">Qty</th>
                          </tr>
                        </thead>
                        <tbody>
                          {fills.length === 0 ? (
                            <tr>
                              <td
                                colSpan={5}
                                className="px-3 py-5 text-center font-mono text-xs text-zinc-600"
                              >
                                None yet
                              </td>
                            </tr>
                          ) : (
                            fills.slice(0, 20).map((f) => (
                              <tr
                                key={f.id}
                                className="border-b border-zinc-800/60 font-mono text-[11px] text-zinc-300 last:border-b-0"
                              >
                                <td className="whitespace-nowrap px-3 py-2 text-zinc-500">
                                  {formatTs(f.created_at)}
                                </td>
                                <td className="px-3 py-2 text-zinc-100">
                                  {f.symbol}
                                </td>
                                <td
                                  className={`px-3 py-2 uppercase ${sideClass(f.side)}`}
                                >
                                  {f.side}
                                </td>
                                <td className="px-3 py-2">
                                  {formatNum(f.price, 4)}
                                </td>
                                <td className="px-3 py-2">
                                  {formatNum(f.qty, 6)}
                                </td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                  </section>

                  <section>
                    <h2 className="mb-3 font-sans text-sm font-semibold text-zinc-100">
                      Events
                    </h2>
                    <div className="overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-900/30">
                      <table className="w-full min-w-[360px] border-collapse text-left">
                        <thead>
                          <tr className="border-b border-zinc-800/80 font-mono text-[10px] uppercase tracking-wide text-zinc-500">
                            <th className="px-3 py-2 font-medium">Time</th>
                            <th className="px-3 py-2 font-medium">Kind</th>
                            <th className="px-3 py-2 font-medium">Symbol</th>
                            <th className="px-3 py-2 font-medium">Detail</th>
                          </tr>
                        </thead>
                        <tbody>
                          {events.length === 0 ? (
                            <tr>
                              <td
                                colSpan={4}
                                className="px-3 py-5 text-center font-mono text-xs text-zinc-600"
                              >
                                None yet
                              </td>
                            </tr>
                          ) : (
                            events.slice(0, 20).map((ev) => (
                              <tr
                                key={ev.id}
                                className="border-b border-zinc-800/60 font-mono text-[11px] text-zinc-300 last:border-b-0"
                              >
                                <td className="whitespace-nowrap px-3 py-2 text-zinc-500">
                                  {formatTs(ev.created_at)}
                                </td>
                                <td className="px-3 py-2">{ev.kind}</td>
                                <td className="px-3 py-2">
                                  {ev.symbol ?? "—"}
                                </td>
                                <td className="max-w-[180px] truncate px-3 py-2 text-zinc-500">
                                  {ev.payload
                                    ? JSON.stringify(ev.payload)
                                    : "—"}
                                </td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                  </section>
                </div>
              </>
            )}
          </div>
        </main>

        {/* Config sidebar */}
        {configOpen && form && config && !error && (
          <aside className="flex w-full shrink-0 flex-col border-t border-zinc-800 bg-zinc-950 sm:border-t-0 sm:border-l lg:w-80">
            <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
              <h2 className="font-sans text-xs font-semibold uppercase tracking-wide text-zinc-400">
                Config
              </h2>
              <button
                type="button"
                onClick={() => setConfigOpen(false)}
                className="font-mono text-xs text-zinc-500 hover:text-zinc-300"
              >
                Close
              </button>
            </div>
            <form
              onSubmit={(e) => void handleSaveConfig(e)}
              className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4"
            >
              <div className="flex flex-wrap gap-2">
                {SYMBOL_OPTIONS.map((sym) => {
                  const active = form.symbols.includes(sym);
                  return (
                    <button
                      key={sym}
                      type="button"
                      onClick={() => toggleSymbol(sym)}
                      className={`inline-flex items-center gap-1.5 rounded border px-2.5 py-1 font-mono text-xs ${
                        active
                          ? "border-zinc-500 text-zinc-100"
                          : "border-zinc-800 text-zinc-600 opacity-60"
                      }`}
                    >
                      <TickerLogo
                        symbol={sym}
                        logoUrl={logos[sym]}
                        size="xs"
                      />
                      {sym}
                    </button>
                  );
                })}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <label>
                  <span className={LABEL}>Max positions</span>
                  <input
                    type="number"
                    min={1}
                    max={10}
                    className={INPUT}
                    value={form.max_positions}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        max_positions: clampInt(e.target.value, 1, 10, 1),
                      })
                    }
                  />
                </label>
                <label>
                  <span className={LABEL}>Size USD</span>
                  <input
                    type="number"
                    min={1}
                    step="any"
                    className={INPUT}
                    value={form.size_usd}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        size_usd: Number(e.target.value) || 0,
                      })
                    }
                  />
                </label>
                <label>
                  <span className={LABEL}>Leverage</span>
                  <input
                    type="number"
                    min={1}
                    step="any"
                    className={INPUT}
                    value={form.leverage}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        leverage: Number(e.target.value) || 1,
                      })
                    }
                  />
                </label>
                <label>
                  <span className={LABEL}>Interval</span>
                  <select
                    className={INPUT}
                    value={form.donchian_interval}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        donchian_interval: e.target.value,
                      })
                    }
                  >
                    {!INTERVAL_OPTIONS.includes(
                      form.donchian_interval as (typeof INTERVAL_OPTIONS)[number],
                    ) && (
                      <option value={form.donchian_interval}>
                        {form.donchian_interval}
                      </option>
                    )}
                    {INTERVAL_OPTIONS.map((iv) => (
                      <option key={iv} value={iv}>
                        {iv}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span className={LABEL}>
                    TP % <span className="text-emerald-500">●</span>
                  </span>
                  <input
                    type="number"
                    min={0}
                    step="any"
                    className={INPUT}
                    value={form.tp_pct}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        tp_pct: Number(e.target.value) || 0,
                      })
                    }
                  />
                </label>
                <label>
                  <span className={LABEL}>
                    SL % <span className="text-red-500">●</span>
                  </span>
                  <input
                    type="number"
                    min={0}
                    step="any"
                    className={INPUT}
                    value={form.sl_pct}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        sl_pct: Number(e.target.value) || 0,
                      })
                    }
                  />
                </label>
                <label>
                  <span className={LABEL}>Donchian period</span>
                  <input
                    type="number"
                    min={1}
                    className={INPUT}
                    value={form.donchian_period}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        donchian_period: clampInt(e.target.value, 1, 500, 20),
                      })
                    }
                  />
                </label>
                <label>
                  <span className={LABEL}>Cooldown (sec)</span>
                  <input
                    type="number"
                    min={0}
                    className={INPUT}
                    value={form.cooldown_seconds}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        cooldown_seconds: clampInt(e.target.value, 0, 86400, 0),
                      })
                    }
                  />
                </label>
              </div>

              <button
                type="submit"
                disabled={saving || form.symbols.length === 0}
                className="w-full rounded border border-zinc-700 px-3 py-2 font-sans text-xs text-zinc-200 hover:border-zinc-500 disabled:opacity-50"
              >
                {saving ? "Saving…" : "Save config"}
              </button>
            </form>
          </aside>
        )}
      </div>
    </div>
  );
}


export default function BotPage() {
  return (
    <TerminalAuthGate>
      <BotPageContent />
    </TerminalAuthGate>
  );
}
