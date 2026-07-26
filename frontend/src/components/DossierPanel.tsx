"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ChatMarkdown from "@/components/ChatMarkdown";
import ProvenanceChip from "@/components/ProvenanceChip";
import ResearchStepLoader from "@/components/ResearchStepLoader";
import { DossierBlockSkeleton } from "@/components/TerminalSkeleton";
import TickerLogo from "@/components/TickerLogo";
import {
  fetchDossier,
  fetchDossierVersions,
  fetchTickerLogos,
  streamDossierRefresh,
} from "@/lib/api";
import type {
  DossierFundamentalsSnapshot,
  DossierVersion,
  ResearchStep,
} from "@/lib/types";

const DOSSIER_BLOCKS = [
  { key: "panorama_mercado", label: "Panorama de mercado" },
  { key: "narrativa_7d", label: "Narrativa (7 días)" },
  { key: "narrativa_7_30d", label: "Narrativa (7–30 días)" },
  { key: "sentimiento", label: "Sentimiento" },
  { key: "contexto_macro", label: "Contexto macro/sector" },
  { key: "fundamentals", label: "Fundamentals" },
  { key: "lectura_integrada", label: "Lectura integrada" },
] as const;

interface DossierPanelProps {
  symbol: string;
}

export default function DossierPanel({ symbol }: DossierPanelProps) {
  const [dossier, setDossier] = useState<DossierVersion | null>(null);
  const [dossierVersions, setDossierVersions] = useState<DossierVersion[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshSteps, setRefreshSteps] = useState<ResearchStep[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(
    null,
  );
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const refreshAbortRef = useRef<AbortController | null>(null);

  const loadDossier = useCallback(async (ticker: string) => {
    setLoading(true);
    setError(null);
    try {
      const [latest, versions] = await Promise.all([
        fetchDossier(ticker),
        fetchDossierVersions(ticker),
      ]);
      setDossier(latest);
      setDossierVersions(versions);
      setSelectedVersionId(latest?.id ?? versions[0]?.id ?? null);
    } catch {
      setDossier(null);
      setDossierVersions([]);
      setSelectedVersionId(null);
      setError("No se pudo cargar el Dossier");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDossier(symbol);
  }, [symbol, loadDossier]);

  useEffect(() => {
    let cancelled = false;
    setLogoUrl(null);
    void fetchTickerLogos([symbol])
      .then((map) => {
        if (!cancelled) setLogoUrl(map[symbol] ?? null);
      })
      .catch(() => {
        if (!cancelled) setLogoUrl(null);
      });
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  async function handleRefresh() {
    if (refreshing) return;
    refreshAbortRef.current?.abort();
    const ctrl = new AbortController();
    refreshAbortRef.current = ctrl;
    setRefreshing(true);
    setRefreshSteps([]);
    setError(null);
    try {
      await streamDossierRefresh(
        symbol,
        {
          onStep: (step) => {
            setRefreshSteps((prev) => {
              const next = [...prev];
              const idx = next.findIndex((s) => s.tool === step.tool);
              if (idx >= 0) next[idx] = step;
              else next.push(step);
              return next;
            });
          },
          onVersion: (updated) => {
            setDossier(updated);
            setSelectedVersionId(updated.id);
          },
          onError: (message) => setError(message),
        },
        ctrl.signal,
      );
      const versions = await fetchDossierVersions(symbol);
      setDossierVersions(versions);
    } catch {
      setError("No se pudo refrescar el Dossier");
    } finally {
      setRefreshing(false);
      setRefreshSteps([]);
      if (refreshAbortRef.current === ctrl) refreshAbortRef.current = null;
    }
  }

  const displayedDossier =
    dossierVersions.find((v) => v.id === selectedVersionId) ??
    dossierVersions[0] ??
    dossier;

  return (
    <section className="flex h-full min-h-0 flex-col bg-zinc-900">
      <div className="flex items-center justify-between gap-2 border-b border-zinc-800 px-4 py-2">
        <div>
          <h2 className="flex items-center gap-2 font-sans text-sm font-semibold text-zinc-100">
            <TickerLogo symbol={symbol} logoUrl={logoUrl} size="sm" />
            <span>
              Dossier ·{""}
              <span className="font-mono text-zinc-300">${symbol}</span>
            </span>
          </h2>
          <p className="font-mono text-[10px] text-zinc-500">
            Análisis integral del Ticker Watch
          </p>
        </div>
        <div className="flex items-center gap-2">
          {dossierVersions.length > 0 && (
            <select
              value={selectedVersionId ?? ""}
              onChange={(e) => setSelectedVersionId(e.target.value)}
              disabled={loading || refreshing}
              className="max-w-[160px] border border-zinc-700 bg-zinc-950 px-2 py-1 font-mono text-[10px] text-zinc-300 focus:border-zinc-500 focus:outline-none disabled:opacity-50"
              aria-label="Versión del Dossier"
            >
              {dossierVersions.map((version, index) => (
                <option key={version.id} value={version.id}>
                  {index === 0 ? "Actual ·" : ""}
                  {new Date(version.created_at).toLocaleString("es-AR", {
                    day: "2-digit",
                    month: "2-digit",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </option>
              ))}
            </select>
          )}
          <button
            type="button"
            onClick={() => void handleRefresh()}
            disabled={loading || refreshing}
            className="border border-zinc-600 bg-zinc-900 px-3 py-1 font-mono text-[10px] text-zinc-300 transition-colors hover:border-zinc-500 hover:text-zinc-200 disabled:opacity-50"
          >
            {refreshing ? "Generando…" : "Refresh"}
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        <DossierContent
          symbol={symbol}
          dossier={displayedDossier}
          loading={loading}
          refreshing={refreshing}
          refreshSteps={refreshSteps}
          error={error}
        />
      </div>
    </section>
  );
}

function DossierContent({
  symbol,
  dossier,
  loading,
  refreshing,
  refreshSteps,
  error,
}: {
  symbol: string;
  dossier: DossierVersion | null;
  loading: boolean;
  refreshing: boolean;
  refreshSteps: ResearchStep[];
  error: string | null;
}) {
  if (loading && !dossier) {
    return <DossierBlockSkeleton blocks={4} />;
  }

  if (error && !dossier) {
    return <p className="font-mono text-xs text-red-400">{error}</p>;
  }

  if (!dossier) {
    return (
      <div className="space-y-2">
        <p className="font-mono text-xs text-zinc-500">
          Sin Dossier para ${symbol}. Usá Refresh para generar el análisis
          integral.
        </p>
        {refreshing && (
          <ResearchStepLoader steps={refreshSteps} active />
        )}
      </div>
    );
  }

  const blocks = dossier.content?.blocks ?? {};
  const sentimentStats = dossier.content?.sentiment_stats;
  const fundamentals = dossier.content?.fundamentals ?? null;
  const hasBlocks = DOSSIER_BLOCKS.some(({ key }) => blocks[key]?.trim());

  return (
    <div className="space-y-6 px-1">
      {refreshing && <ResearchStepLoader steps={refreshSteps} active />}
      {error && (
        <p className="font-mono text-xs text-red-400">{error}</p>
      )}
      {!hasBlocks && (
        <p className="font-mono text-xs text-zinc-500">
          El Dossier no tiene bloques renderizables. Probá Refresh de nuevo.
        </p>
      )}
      {DOSSIER_BLOCKS.map(({ key, label }) => {
        const body = blocks[key]?.trim();
        if (!body && !(key === "fundamentals" && fundamentals)) return null;

        return (
          <section
            key={key}
            className="space-y-2 border border-zinc-800/80 bg-zinc-950/40 p-4"
          >
            <h3 className="font-sans text-xs font-semibold uppercase tracking-wide text-zinc-400">
              {label}
            </h3>
            {key === "sentimiento" && sentimentStats && (
              <SentimentStatsPanel stats={sentimentStats} />
            )}
            {key === "fundamentals" && fundamentals ? (
              <FundamentalsSnapshotPanel snapshot={fundamentals} />
            ) : (
              body && (
                <ChatMarkdown content={body} citations={dossier.citations} />
              )
            )}
          </section>
        );
      })}
    </div>
  );
}

function formatMcap(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "no disponible";
  if (value >= 1_000_000_000_000)
    return `$${(value / 1_000_000_000_000).toFixed(2)}T`;
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  return `$${value.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

function formatNum(value: number | null | undefined, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "no disponible";
  return value.toFixed(digits);
}

function FundamentalsSnapshotPanel({
  snapshot,
}: {
  snapshot: DossierFundamentalsSnapshot;
}) {
  const rows = [
    {
      label: "precio",
      value:
        snapshot.price == null
          ? "no disponible"
          : `$${snapshot.price.toLocaleString("en-US", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}`,
    },
    { label: "market cap", value: formatMcap(snapshot.market_cap) },
    { label: "P/E", value: formatNum(snapshot.pe) },
    { label: "EPS", value: formatNum(snapshot.eps) },
    { label: "sector", value: snapshot.sector?.trim() || "no disponible" },
    {
      label: "industry",
      value: snapshot.industry?.trim() || "no disponible",
    },
  ];

  const provenance =
    snapshot.provenance ??
    (snapshot.source
      ? {
          kind: "fundamentals" as const,
          source: snapshot.source,
          as_of: snapshot.as_of,
          note:
            snapshot.asset_kind === "crypto"
              ? "ratios equity no aplican"
              : undefined,
        }
      : null);

  return (
    <div className="mb-2 space-y-2 border border-zinc-800 bg-zinc-950 px-2 py-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <ProvenanceChip provenance={provenance} />
        {snapshot.asset_kind === "crypto" && (
          <span className="font-mono text-[9px] uppercase tracking-wide text-zinc-600">
            crypto
          </span>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        {rows.map(({ label, value }) => (
          <span key={label} className="font-mono text-[10px] text-zinc-400">
            <span className="text-zinc-500">{label}:</span>
            {""}
            <span
              className={
                value === "no disponible" ? "text-zinc-600" : "text-zinc-200"
              }
            >
              {value}
            </span>
          </span>
        ))}
      </div>
      {snapshot.asset_kind === "crypto" && (
        <p className="font-mono text-[10px] text-zinc-600">
          PE/EPS/market cap equity no aplican; solo precio de Market Data.
        </p>
      )}
    </div>
  );
}

function SentimentStatsPanel({ stats }: { stats: Record<string, unknown> }) {
  const hours = stats.hours;
  const totalSignals = stats.total_signals;
  const withSentiment = stats.with_sentiment;
  const withoutSentiment = stats.without_sentiment;
  const bySentiment = stats.by_sentiment;
  const bySourceType = stats.by_source_type;

  const sentimentEntries =
    bySentiment &&
    typeof bySentiment === "object" &&
    !Array.isArray(bySentiment)
      ? Object.entries(bySentiment as Record<string, number>)
      : [];

  const sourceEntries =
    bySourceType &&
    typeof bySourceType === "object" &&
    !Array.isArray(bySourceType)
      ? Object.entries(bySourceType as Record<string, number>)
      : [];

  const scalars = [
    hours != null ? { label: "ventana", value: `${hours}h` } : null,
    totalSignals != null
      ? { label: "signals", value: String(totalSignals) }
      : null,
    withSentiment != null
      ? { label: "con sentimiento", value: String(withSentiment) }
      : null,
    withoutSentiment != null
      ? { label: "sin etiqueta", value: String(withoutSentiment) }
      : null,
  ].filter((item): item is { label: string; value: string } => item !== null);

  if (
    scalars.length === 0 &&
    sentimentEntries.length === 0 &&
    sourceEntries.length === 0
  ) {
    return null;
  }

  return (
    <div className="mb-2 space-y-2 border border-zinc-800 bg-zinc-950 px-2 py-1.5">
      {scalars.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {scalars.map(({ label, value }) => (
            <span key={label} className="font-mono text-[10px] text-zinc-400">
              <span className="text-zinc-500">{label}:</span>
              {""}
              <span className="text-zinc-200">{value}</span>
            </span>
          ))}
        </div>
      )}

      {sentimentEntries.length > 0 && (
        <div className="space-y-1">
          <p className="font-mono text-[9px] uppercase tracking-wide text-zinc-500">
            Por sentimiento
          </p>
          <div className="flex flex-wrap gap-1.5">
            {sentimentEntries.map(([label, count]) => (
              <span
                key={label}
                className="border border-zinc-800 bg-zinc-900 px-1.5 py-0.5 font-mono text-[10px] text-zinc-300"
              >
                <span className="text-zinc-500">{label}</span>
                {""}
                <span className="text-zinc-200">{count}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {sourceEntries.length > 0 && (
        <div className="space-y-1">
          <p className="font-mono text-[9px] uppercase tracking-wide text-zinc-500">
            Por fuente
          </p>
          <div className="flex flex-wrap gap-1.5">
            {sourceEntries.map(([source, count]) => (
              <span
                key={source}
                className="border border-zinc-800 bg-zinc-900 px-1.5 py-0.5 font-mono text-[10px] text-zinc-300"
              >
                <span className="text-zinc-500">{source}</span>
                {""}
                <span className="text-zinc-200">{count}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
