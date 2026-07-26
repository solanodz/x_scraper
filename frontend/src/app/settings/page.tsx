"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import TerminalAuthGate from "@/components/TerminalAuthGate";
import TerminalHeader from "@/components/TerminalHeader";
import {
  fetchOperatorSettings,
  patchOperatorSettings,
} from "@/lib/api";
import {
  BOT_PNL_LOOKBACKS,
  BOT_PNL_TIMEZONES,
  loadBotPnlPrefs,
  saveBotPnlPrefs,
  type BotPnlPrefs,
} from "@/lib/botDailyPnl";

const INPUT =
  "w-full border border-zinc-800 bg-zinc-950 px-2 py-1.5 font-mono text-xs text-zinc-200 outline-none focus:border-zinc-600";
const LABEL =
  "mb-1 block font-sans text-[10px] uppercase tracking-wide text-zinc-500";

function SettingsContent() {
  const [botPnl, setBotPnl] = useState<BotPnlPrefs>(() => loadBotPnlPrefs());
  const [watchOnly, setWatchOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchOperatorSettings()
      .then((res) => {
        if (cancelled) return;
        const pnl = res.settings.bot_pnl;
        const next: BotPnlPrefs = {
          timeZone: pnl.timeZone,
          lookbackDays: pnl.lookbackDays,
        };
        setBotPnl(next);
        saveBotPnlPrefs(next);
        setWatchOnly(Boolean(res.settings.feed_filters?.watchOnly));
        setError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setStatus(null);
    setError(null);
    try {
      const res = await patchOperatorSettings({
        bot_pnl: {
          timeZone: botPnl.timeZone,
          lookbackDays: botPnl.lookbackDays,
        },
        feed_filters: { watchOnly },
      });
      const next: BotPnlPrefs = {
        timeZone: res.settings.bot_pnl.timeZone,
        lookbackDays: res.settings.bot_pnl.lookbackDays,
      };
      setBotPnl(next);
      saveBotPnlPrefs(next);
      setWatchOnly(Boolean(res.settings.feed_filters?.watchOnly));
      setStatus("Guardado");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-zinc-950">
      <TerminalHeader />
      <main className="mx-auto w-full max-w-lg flex-1 overflow-y-auto px-4 py-8">
        <div className="mb-6 flex items-baseline justify-between gap-3">
          <div>
            <h2 className="font-sans text-sm font-semibold text-zinc-100">
              Settings
            </h2>
            <p className="mt-1 font-sans text-xs text-zinc-500">
              Preferencias del Operator. Se sincronizan con tu cuenta.
            </p>
          </div>
          <Link
            href="/terminal"
            className="font-sans text-xs text-zinc-500 hover:text-zinc-300"
          >
            ← Terminal
          </Link>
        </div>

        {loading ? (
          <p className="font-mono text-xs text-zinc-500">Cargando…</p>
        ) : (
          <form onSubmit={handleSave} className="space-y-6">
            <section className="border border-zinc-800 p-4">
              <h3 className="mb-3 font-sans text-xs font-semibold uppercase tracking-wide text-zinc-400">
                Paper Bot — Daily PnL
              </h3>
              <div className="space-y-3">
                <div>
                  <label htmlFor="tz" className={LABEL}>
                    Timezone
                  </label>
                  <select
                    id="tz"
                    className={INPUT}
                    value={botPnl.timeZone}
                    onChange={(e) =>
                      setBotPnl((p) => ({ ...p, timeZone: e.target.value }))
                    }
                  >
                    {BOT_PNL_TIMEZONES.map((tz) => (
                      <option key={tz} value={tz}>
                        {tz}
                      </option>
                    ))}
                    {!BOT_PNL_TIMEZONES.includes(
                      botPnl.timeZone as (typeof BOT_PNL_TIMEZONES)[number],
                    ) && (
                      <option value={botPnl.timeZone}>{botPnl.timeZone}</option>
                    )}
                  </select>
                </div>
                <div>
                  <label htmlFor="lookback" className={LABEL}>
                    Lookback
                  </label>
                  <select
                    id="lookback"
                    className={INPUT}
                    value={botPnl.lookbackDays}
                    onChange={(e) =>
                      setBotPnl((p) => ({
                        ...p,
                        lookbackDays: Number(e.target.value) || 30,
                      }))
                    }
                  >
                    {BOT_PNL_LOOKBACKS.map((d) => (
                      <option key={d} value={d}>
                        {d} días
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </section>

            <section className="border border-zinc-800 p-4">
              <h3 className="mb-3 font-sans text-xs font-semibold uppercase tracking-wide text-zinc-400">
                Signal Feed
              </h3>
              <label className="flex cursor-pointer items-center gap-3">
                <input
                  type="checkbox"
                  checked={watchOnly}
                  onChange={(e) => setWatchOnly(e.target.checked)}
                  className="h-3.5 w-3.5 border-zinc-600 bg-zinc-950 text-zinc-100"
                />
                <span className="font-sans text-xs text-zinc-300">
                  Mis tickers por defecto (watchOnly)
                </span>
              </label>
              <p className="mt-2 font-sans text-[11px] text-zinc-600">
                Al abrir el Terminal, el filtro Mis tickers arranca en este
                estado. También podés cambiarlo en el Feed.
              </p>
            </section>

            <section className="border border-zinc-800 p-4">
              <h3 className="mb-2 font-sans text-xs font-semibold uppercase tracking-wide text-zinc-400">
                Ticker Chart
              </h3>
              <p className="font-sans text-[11px] leading-relaxed text-zinc-600">
                Intervalo, periodo e indicadores se sincronizan al cambiarlos en
                el chart (soft sync con el servidor; cache local en este
                browser).
              </p>
            </section>

            <div className="flex items-center gap-3">
              <button
                type="submit"
                disabled={saving}
                className="border border-zinc-600 bg-zinc-100 px-4 py-1.5 font-sans text-xs font-medium text-zinc-950 transition-colors hover:bg-white disabled:opacity-50"
              >
                {saving ? "Guardando…" : "Guardar"}
              </button>
              {status && (
                <span className="font-mono text-xs text-zinc-400">{status}</span>
              )}
              {error && (
                <span className="font-mono text-xs text-red-400">{error}</span>
              )}
            </div>
          </form>
        )}
      </main>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <TerminalAuthGate>
      <SettingsContent />
    </TerminalAuthGate>
  );
}
