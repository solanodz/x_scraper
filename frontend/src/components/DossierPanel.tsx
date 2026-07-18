"use client";

import { useCallback, useEffect, useState } from "react";
import ChatMarkdown from "@/components/ChatMarkdown";
import TickerLogo from "@/components/TickerLogo";
import {
  fetchDossier,
  fetchDossierVersions,
  fetchTickerLogos,
  refreshDossier,
} from "@/lib/api";
import type { DossierVersion } from "@/lib/types";

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
  const [error, setError] = useState<string | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [logoUrl, setLogoUrl] = useState<string | null>(null);

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
    setRefreshing(true);
    setError(null);
    try {
      const updated = await refreshDossier(symbol);
      setDossier(updated);
      setSelectedVersionId(updated.id);
      const versions = await fetchDossierVersions(symbol);
      setDossierVersions(versions);
    } catch {
      setError("No se pudo refrescar el Dossier");
    } finally {
      setRefreshing(false);
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
              Dossier ·{" "}
              <span className="font-mono text-amber-400">${symbol}</span>
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
              className="max-w-[160px] rounded border border-zinc-700 bg-zinc-950 px-2 py-1 font-mono text-[10px] text-zinc-300 focus:border-amber-600 focus:outline-none disabled:opacity-50"
              aria-label="Versión del Dossier"
            >
              {dossierVersions.map((version, index) => (
                <option key={version.id} value={version.id}>
                  {index === 0 ? "Actual · " : ""}
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
            className="rounded border border-amber-800/60 bg-amber-950/30 px-3 py-1 font-mono text-[10px] text-amber-400 transition-colors hover:border-amber-600 hover:text-amber-300 disabled:opacity-50"
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
  error,
}: {
  symbol: string;
  dossier: DossierVersion | null;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
}) {
  if (loading && !dossier) {
    return <p className="font-mono text-xs text-zinc-500">Cargando Dossier…</p>;
  }

  if (error) {
    return <p className="font-mono text-xs text-red-400">{error}</p>;
  }

  if (!dossier) {
    return (
      <div className="space-y-2">
        <p className="font-mono text-xs text-zinc-500">
          Sin Dossier para ${symbol}. Usá Refresh para generar el análisis integral.
        </p>
        {refreshing && (
          <p className="font-mono text-xs text-amber-500">Generando…</p>
        )}
      </div>
    );
  }

  const blocks = dossier.content?.blocks ?? {};
  const sentimentStats = dossier.content?.sentiment_stats;
  const hasBlocks = DOSSIER_BLOCKS.some(({ key }) => blocks[key]?.trim());

  return (
    <div className="space-y-6 px-1">
      {!hasBlocks && (
        <p className="font-mono text-xs text-zinc-500">
          El Dossier no tiene bloques renderizables. Probá Refresh de nuevo.
        </p>
      )}
      {DOSSIER_BLOCKS.map(({ key, label }) => {
        const body = blocks[key]?.trim();
        if (!body) return null;

        return (
          <section
            key={key}
            className="space-y-2 rounded border border-zinc-800/80 bg-zinc-950/40 p-4"
          >
            <h3 className="font-sans text-xs font-semibold uppercase tracking-wide text-amber-500">
              {label}
            </h3>
            {key === "sentimiento" && sentimentStats && (
              <SentimentStatsPanel stats={sentimentStats} />
            )}
            <ChatMarkdown content={body} citations={dossier.citations} />
          </section>
        );
      })}
    </div>
  );
}

function SentimentStatsPanel({
  stats,
}: {
  stats: Record<string, unknown>;
}) {
  const hours = stats.hours;
  const totalSignals = stats.total_signals;
  const withSentiment = stats.with_sentiment;
  const withoutSentiment = stats.without_sentiment;
  const bySentiment = stats.by_sentiment;
  const bySourceType = stats.by_source_type;

  const sentimentEntries =
    bySentiment && typeof bySentiment === "object" && !Array.isArray(bySentiment)
      ? Object.entries(bySentiment as Record<string, number>)
      : [];

  const sourceEntries =
    bySourceType && typeof bySourceType === "object" && !Array.isArray(bySourceType)
      ? Object.entries(bySourceType as Record<string, number>)
      : [];

  const scalars = [
    hours != null ? { label: "ventana", value: `${hours}h` } : null,
    totalSignals != null ? { label: "signals", value: String(totalSignals) } : null,
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
    <div className="mb-2 space-y-2 rounded border border-zinc-800 bg-zinc-950 px-2 py-1.5">
      {scalars.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {scalars.map(({ label, value }) => (
            <span key={label} className="font-mono text-[10px] text-zinc-400">
              <span className="text-zinc-500">{label}:</span>{" "}
              <span className="text-emerald-400/90">{value}</span>
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
                className="rounded border border-zinc-800 bg-zinc-900 px-1.5 py-0.5 font-mono text-[10px] text-zinc-300"
              >
                <span className="text-zinc-500">{label}</span>{" "}
                <span className="text-emerald-400/90">{count}</span>
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
                className="rounded border border-zinc-800 bg-zinc-900 px-1.5 py-0.5 font-mono text-[10px] text-zinc-300"
              >
                <span className="text-zinc-500">{source}</span>{" "}
                <span className="text-emerald-400/90">{count}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
