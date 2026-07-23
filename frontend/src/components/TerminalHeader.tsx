"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { clearAccessTokenCache, isSupabaseConfigured, refreshIngest } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import TickerWatchPopover from "@/components/TickerWatchPopover";

const NAV_ITEMS = [
  {
    href: "/terminal",
    label: "Terminal",
    match: (path: string) => path === "/terminal" || path.startsWith("/terminal/"),
  },
  {
    href: "/research",
    label: "Research",
    match: (path: string) => path === "/research" || path.startsWith("/research/"),
  },
  {
    href: "/dossier",
    label: "Dossier",
    match: (path: string) => path.startsWith("/dossier"),
  },
  {
    href: "/bot",
    label: "Bot",
    match: (path: string) => path === "/bot" || path.startsWith("/bot/"),
  },
] as const;

interface TerminalHeaderProps {
  onRefreshComplete?: () => void;
}

export default function TerminalHeader({ onRefreshComplete }: TerminalHeaderProps) {
  const pathname = usePathname();
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
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-3">
          <span className="font-mono text-sm text-amber-500">▮</span>
          <h1 className="font-sans text-sm font-semibold tracking-wide text-zinc-100">
            X Scraper Terminal
          </h1>
        </div>
        <nav className="flex items-center gap-1" aria-label="Principal">
          {NAV_ITEMS.map(({ href, label, match }) => {
            const active = match(pathname);
            return (
              <Link
                key={href}
                href={href}
                className={`rounded px-2.5 py-1 font-sans text-xs transition-colors ${
                  active
                    ? "bg-amber-950/40 font-semibold text-amber-400"
                    : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
                }`}
              >
                {label}
              </Link>
            );
          })}
        </nav>
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
