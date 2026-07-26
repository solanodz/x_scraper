/**
 * Daily realized PnL helpers for Paper Bot (/bot).
 * Day keys are calendar dates in the Operator-chosen IANA timezone.
 */

export type DailyPnlPoint = {
  day: string;
  label: string;
  pnl: number;
  trades: number;
};

export type BotPnlPrefs = {
  timeZone: string;
  lookbackDays: number;
};

export const BOT_PNL_PREFS_KEY = "xscraper.bot.pnlPrefs";

export const BOT_PNL_TIMEZONES = [
  "America/Argentina/Buenos_Aires",
  "UTC",
  "America/New_York",
  "America/Los_Angeles",
  "Europe/London",
] as const;

export const BOT_PNL_LOOKBACKS = [7, 14, 30, 90] as const;

const DEFAULT_PREFS: BotPnlPrefs = {
  timeZone: "America/Argentina/Buenos_Aires",
  lookbackDays: 30,
};

export function loadBotPnlPrefs(): BotPnlPrefs {
  if (typeof window === "undefined") return { ...DEFAULT_PREFS };
  try {
    const raw = window.localStorage.getItem(BOT_PNL_PREFS_KEY);
    if (!raw) return { ...DEFAULT_PREFS };
    const parsed = JSON.parse(raw) as Partial<BotPnlPrefs>;
    const timeZone =
      typeof parsed.timeZone === "string" && parsed.timeZone
        ? parsed.timeZone
        : DEFAULT_PREFS.timeZone;
    const lookbackDays = BOT_PNL_LOOKBACKS.includes(
      parsed.lookbackDays as (typeof BOT_PNL_LOOKBACKS)[number],
    )
      ? Number(parsed.lookbackDays)
      : DEFAULT_PREFS.lookbackDays;
    return { timeZone, lookbackDays };
  } catch {
    return { ...DEFAULT_PREFS };
  }
}

export function saveBotPnlPrefs(prefs: BotPnlPrefs): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(BOT_PNL_PREFS_KEY, JSON.stringify(prefs));
}

/** Calendar day key YYYY-MM-DD in the given IANA timezone. */
export function dayKeyInTimeZone(
  iso: string | null | undefined,
  timeZone: string,
): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  try {
    return new Intl.DateTimeFormat("en-CA", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(d);
  } catch {
    return new Intl.DateTimeFormat("en-CA", {
      timeZone: "UTC",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(d);
  }
}

function todayKey(timeZone: string): string {
  return (
    dayKeyInTimeZone(new Date().toISOString(), timeZone) ??
    new Date().toISOString().slice(0, 10)
  );
}

/** Inclusive list of YYYY-MM-DD from (today - lookback + 1) … today in tz. */
export function enumerateDays(
  timeZone: string,
  lookbackDays: number,
  nowIso?: string,
): string[] {
  const end = dayKeyInTimeZone(nowIso ?? new Date().toISOString(), timeZone);
  if (!end) return [];
  const days = Math.max(1, Math.min(365, lookbackDays));
  // end is already a civil date in the Operator TZ — walk calendar days.
  const [y, m, d] = end.split("-").map(Number);
  let civilMs = Date.UTC(y, m - 1, d, 12, 0, 0);
  const out: string[] = [];
  for (let i = 0; i < days; i++) {
    const dt = new Date(civilMs - i * 86_400_000);
    const yy = dt.getUTCFullYear();
    const mm = String(dt.getUTCMonth() + 1).padStart(2, "0");
    const dd = String(dt.getUTCDate()).padStart(2, "0");
    out.push(`${yy}-${mm}-${dd}`);
  }
  return out.reverse();
}

type ClosedLike = {
  closed_at?: string | null;
  realized_pnl?: number | null;
};

/**
 * Daily realized PnL buckets for closed positions.
 * Empty days in the lookback window are filled with 0.
 */
export function buildDailyPnl(
  closed: ClosedLike[],
  prefs: BotPnlPrefs,
  nowIso?: string,
): { series: DailyPnlPoint[]; todayPnl: number; todayTrades: number } {
  const days = enumerateDays(prefs.timeZone, prefs.lookbackDays, nowIso);
  const byDay = new Map<string, { pnl: number; trades: number }>();
  for (const day of days) {
    byDay.set(day, { pnl: 0, trades: 0 });
  }

  for (const p of closed) {
    const key = dayKeyInTimeZone(p.closed_at, prefs.timeZone);
    if (!key || !byDay.has(key)) continue;
    const pnl = Number(p.realized_pnl);
    if (!Number.isFinite(pnl)) continue;
    const row = byDay.get(key)!;
    row.pnl += pnl;
    row.trades += 1;
  }

  const series: DailyPnlPoint[] = days.map((day) => {
    const row = byDay.get(day) ?? { pnl: 0, trades: 0 };
    const [, month, dom] = day.split("-");
    return {
      day,
      label: `${month}/${dom}`,
      pnl: row.pnl,
      trades: row.trades,
    };
  });

  const today = todayKey(prefs.timeZone);
  const todayRow = byDay.get(today) ?? { pnl: 0, trades: 0 };
  return {
    series,
    todayPnl: todayRow.pnl,
    todayTrades: todayRow.trades,
  };
}
