"use client";

import { useState } from "react";
import { clearAccessTokenCache, isSupabaseConfigured, refreshIngest } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import TickerWatchPopover from "@/components/TickerWatchPopover";

interface TerminalHeaderProps {
  onRefreshComplete?: () => void;
}

export default function TerminalHeader({
  onRefreshComplete,
}: TerminalHeaderProps) {
  const [refreshing, setRefreshing] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const authEnabled = isSupabaseConfigured();

  async function handleRefresh() {
    setRefreshing(true);
    setStatus(null);
    try {
      await refreshIngest();
      setStatus("Ingestion started");
      onRefreshComplete?.();
    } catch {
      setStatus("Refresh failed");
    } finally {
      setRefreshing(false);
    }
  }

  async function handleSignOut() {
    setSigningOut(true);
    clearAccessTokenCache();
    const supabase = createClient();
    await supabase.auth.signOut();
    window.location.href = "/login";
  }

  return (
    <header className="flex items-center justify-between border-b border-zinc-800 bg-zinc-950 px-4 py-2">
      <div className="flex items-center gap-3">
        <span className="text-amber-500 font-mono text-sm">▮</span>
        <h1 className="font-sans text-sm font-semibold tracking-wide text-zinc-100">
          X Scraper Terminal
        </h1>
      </div>
      <div className="flex items-center gap-3">
        {status && (
          <span className="font-mono text-xs text-emerald-500">{status}</span>
        )}
        <TickerWatchPopover />
        <button
          type="button"
          onClick={handleRefresh}
          disabled={refreshing || signingOut}
          className="rounded border border-zinc-700 bg-zinc-900 px-3 py-1 font-sans text-xs text-zinc-300 transition-colors hover:border-amber-600 hover:text-amber-400 disabled:opacity-50"
        >
          {refreshing ? "Refreshing…" : "Refresh"}
        </button>
        {authEnabled && (
          <button
            type="button"
            onClick={handleSignOut}
            disabled={signingOut}
            className="rounded border border-zinc-700 bg-zinc-900 px-3 py-1 font-sans text-xs text-zinc-400 transition-colors hover:border-zinc-600 hover:text-zinc-200 disabled:opacity-50"
          >
            {signingOut ? "Cerrando…" : "Cerrar sesión"}
          </button>
        )}
      </div>
    </header>
  );
}
