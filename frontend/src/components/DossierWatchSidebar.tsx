"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import TickerLogo from "@/components/TickerLogo";
import { fetchTickerLogos, fetchTickerWatch } from "@/lib/api";
import { dossierPath } from "@/lib/dossierNav";
import type { TickerWatchEntry } from "@/lib/types";

const COLLAPSED_KEY = "xscraper.dossierWatch.collapsed";

function PanelToggleIcon({ collapsed }: { collapsed: boolean }) {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      {collapsed ? (
        <path d="M6 3.5 11 8l-5 4.5" />
      ) : (
        <path d="M10 3.5 5 8l5 4.5" />
      )}
    </svg>
  );
}

export default function DossierWatchSidebar() {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const activeSymbol = searchParams.get("symbol")?.toUpperCase() ?? null;
  const [entries, setEntries] = useState<TickerWatchEntry[]>([]);
  const [logos, setLogos] = useState<Record<string, string | null>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem(COLLAPSED_KEY) === "1");
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchTickerWatch()
      .then(async (data) => {
        if (cancelled) return;
        setEntries(data);
        if (data.length === 0) return;
        try {
          const logoMap = await fetchTickerLogos(data.map((e) => e.symbol));
          if (!cancelled) setLogos(logoMap);
        } catch {
          if (!cancelled) setLogos({});
        }
      })
      .catch(() => {
        if (!cancelled) setError("No se pudo cargar el Watch");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(COLLAPSED_KEY, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  }

  return (
    <aside
      className={`flex h-full min-h-0 shrink-0 flex-col border-r border-zinc-800 bg-zinc-950 transition-[width] duration-200 ease-out ${
        collapsed ? "w-12" : "w-52"
      }`}
    >
      <div
        className={`flex items-center border-b border-zinc-800 ${
          collapsed ? "justify-center px-1 py-2" : "justify-between gap-1 px-3 py-2"
        }`}
      >
        {!collapsed && (
          <p className="font-mono text-[10px] uppercase tracking-wide text-amber-500">
            Ticker Watch
          </p>
        )}
        <button
          type="button"
          onClick={toggleCollapsed}
          className="inline-flex items-center justify-center rounded border border-zinc-700 p-1 text-zinc-400 transition-colors hover:border-amber-700 hover:text-amber-400"
          aria-label={collapsed ? "Expandir Ticker Watch" : "Colapsar Ticker Watch"}
          title={collapsed ? "Expandir" : "Colapsar"}
        >
          <PanelToggleIcon collapsed={collapsed} />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading && (
          <p
            className={`py-2 font-mono text-[10px] text-zinc-500 ${
              collapsed ? "px-1 text-center" : "px-3"
            }`}
          >
            …
          </p>
        )}
        {error && !collapsed && (
          <p className="px-3 py-2 font-mono text-[10px] text-red-400">{error}</p>
        )}
        {!loading && !error && entries.length === 0 && !collapsed && (
          <p className="px-3 py-2 font-mono text-[10px] text-zinc-500">
            Sin tickers. Agregá símbolos desde Watch en el header.
          </p>
        )}
        {entries.map((entry) => {
          const href = dossierPath(entry.symbol);
          const isActive =
            pathname === "/dossier" && activeSymbol === entry.symbol;
          const hasThesis = Boolean(entry.note?.trim());

          return (
            <Link
              key={entry.id}
              href={href}
              title={`$${entry.symbol}`}
              aria-label={`$${entry.symbol}`}
              className={`relative flex items-center border-b border-zinc-800/60 font-mono text-[11px] transition-colors ${
                collapsed
                  ? "justify-center px-1 py-2.5"
                  : "gap-2 px-3 py-2"
              } ${
                isActive
                  ? "bg-amber-950/30 text-amber-300"
                  : "text-zinc-300 hover:bg-zinc-900 hover:text-amber-400"
              }`}
            >
              <TickerLogo
                symbol={entry.symbol}
                logoUrl={logos[entry.symbol]}
                size={collapsed ? "md" : "sm"}
              />
              {!collapsed && (
                <>
                  <span className="font-semibold text-amber-400">
                    ${entry.symbol}
                  </span>
                  {hasThesis && (
                    <span
                      className="h-1.5 w-1.5 rounded-full bg-amber-500"
                      aria-label="Thesis guardada"
                    />
                  )}
                </>
              )}
              {collapsed && hasThesis && (
                <span
                  className="absolute right-1 top-1 h-1 w-1 rounded-full bg-amber-500"
                  aria-label="Thesis guardada"
                />
              )}
            </Link>
          );
        })}
      </div>
    </aside>
  );
}
