"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import ResearchStepLoader from "@/components/ResearchStepLoader";
import { TickerChart } from "@/components/TickerChart";
import { TickerChartToolbar } from "@/components/TickerChartToolbar";
import TickerLogo from "@/components/TickerLogo";
import { useLiveTickerMarket } from "@/hooks/useLiveTickerMarket";
import {
  ChartPlanAnalyzeError,
  fetchChartPlan,
  fetchChartPlanVersions,
  streamChartPlanAnalyze,
} from "@/lib/api";
import {
  formatQuoteChangePercent,
  formatQuotePrice,
  formatRefreshAge,
} from "@/lib/marketRefresh";
import {
  loadTickerChartPrefs,
  matchPresetId,
  normalizeTickerChartPrefs,
  saveTickerChartPrefs,
  type TickerChartPrefs,
} from "@/lib/tickerChartPrefs";
import type {
  ChartPlanContent,
  ChartPlanIndicatorReading,
  ChartPlanSuggestedView,
  ChartPlanVersion,
  ChartPlanView,
  ResearchStep,
} from "@/lib/types";

interface ChartPlanPanelProps {
  symbol: string;
}

const SENTIMENT_COLORS: Record<string, string> = {
  positive: "#34d399",
  bullish: "#34d399",
  negative: "#f87171",
  bearish: "#f87171",
  neutral: "#a1a1aa",
  sin_etiqueta: "#71717a",
};

function viewEnabled(views: ChartPlanView[], type: string): ChartPlanView | null {
  const match = views.find((view) => view.type === type);
  if (!match?.enabled) return null;
  return match;
}

function normalizeAssessment(content: ChartPlanContent) {
  const raw = content.assessment;
  return {
    summary: raw?.summary ?? content.summary ?? "",
    conflicts: raw?.conflicts ?? [],
    data_gaps: raw?.data_gaps ?? [],
    bias_check: raw?.bias_check ?? "",
  };
}

function suggestedViewToPrefs(view: ChartPlanSuggestedView): TickerChartPrefs {
  return normalizeTickerChartPrefs({
    interval: view.interval,
    period: view.period,
    presetId: matchPresetId(view.interval, view.period),
    smaA: view.sma_a,
    smaB: view.sma_b,
    donchian: view.donchian,
    fib: view.fib,
    volume: view.volume,
  });
}

function viewsMatch(
  prefs: TickerChartPrefs,
  suggested: ChartPlanSuggestedView | undefined,
): boolean {
  if (!suggested) return true;
  return (
    prefs.interval === suggested.interval &&
    prefs.period === suggested.period &&
    prefs.smaA.enabled === suggested.sma_a.enabled &&
    prefs.smaA.length === suggested.sma_a.length &&
    prefs.smaB.enabled === suggested.sma_b.enabled &&
    prefs.smaB.length === suggested.sma_b.length &&
    prefs.donchian.enabled === suggested.donchian.enabled &&
    prefs.donchian.period === suggested.donchian.period &&
    prefs.fib === suggested.fib &&
    prefs.volume === suggested.volume
  );
}

export default function ChartPlanPanel({ symbol }: ChartPlanPanelProps) {
  const [chartPlan, setChartPlan] = useState<ChartPlanVersion | null>(null);
  const [versions, setVersions] = useState<ChartPlanVersion[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [steps, setSteps] = useState<ResearchStep[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [disabled, setDisabled] = useState(false);
  const [needsDossier, setNeedsDossier] = useState(false);
  const [chartPrefs, setChartPrefs] = useState<TickerChartPrefs>(() =>
    loadTickerChartPrefs(),
  );
  const [softApplyAvailable, setSoftApplyAvailable] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const {
    quote,
    candles,
    candlesLoading,
    candlesError,
    quoteUpdatedAt,
    candlesUpdatedAt,
  } = useLiveTickerMarket(symbol, {
    period: chartPrefs.period,
    interval: chartPrefs.interval,
  });

  function handlePrefsChange(next: TickerChartPrefs) {
    setChartPrefs(next);
    saveTickerChartPrefs(next);
  }

  const loadChartPlan = useCallback(async (ticker: string) => {
    setLoading(true);
    setError(null);
    setDisabled(false);
    setNeedsDossier(false);
    try {
      const [latest, history] = await Promise.all([
        fetchChartPlan(ticker),
        fetchChartPlanVersions(ticker),
      ]);
      setChartPlan(latest);
      setVersions(history);
      setSelectedVersionId(latest?.id ?? history[0]?.id ?? null);
    } catch {
      setChartPlan(null);
      setVersions([]);
      setSelectedVersionId(null);
      setError("No se pudo cargar el Chart Plan");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadChartPlan(symbol);
    return () => {
      abortRef.current?.abort();
    };
  }, [symbol, loadChartPlan]);

  async function handleAnalyze() {
    if (analyzing) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setAnalyzing(true);
    setSteps([]);
    setError(null);
    setDisabled(false);
    setNeedsDossier(false);

    try {
      await streamChartPlanAnalyze(
        symbol,
        {
          onStep: (step) => {
            setSteps((prev) => {
              const idx = prev.findIndex(
                (item) => item.tool === step.tool && item.label === step.label,
              );
              if (idx >= 0) {
                const next = [...prev];
                next[idx] = step;
                return next;
              }
              return [...prev, step];
            });
          },
          onVersion: (version) => {
            setChartPlan(version);
            setSelectedVersionId(version.id);
            if (version.content?.suggested_view) {
              setSoftApplyAvailable(true);
            }
          },
        },
        controller.signal,
      );
      const history = await fetchChartPlanVersions(symbol);
      setVersions(history);
    } catch (err) {
      if (controller.signal.aborted) return;
      if (err instanceof ChartPlanAnalyzeError) {
        if (err.code === "disabled") {
          setDisabled(true);
          setError(err.message);
          return;
        }
        if (err.code === "dossier_missing") {
          setNeedsDossier(true);
          setError(err.message);
          return;
        }
      }
      setError("No se pudo analizar gráficos");
    } finally {
      setAnalyzing(false);
    }
  }

  const displayed =
    versions.find((v) => v.id === selectedVersionId) ??
    versions[0] ??
    chartPlan;

  const content = displayed?.content;
  const views = content?.views ?? [];
  const chartData = content?.chart_data;
  const assessment = content ? normalizeAssessment(content) : null;
  const sentimentEnabled = Boolean(viewEnabled(views, "sentiment_bars"));
  const timelineEnabled = Boolean(viewEnabled(views, "signals_timeline"));
  const indicatorReadings = content?.indicator_readings ?? [];
  const suggestedView = content?.suggested_view;
  const readingsStale =
    Boolean(content && suggestedView) && !viewsMatch(chartPrefs, suggestedView);

  return (
    <section className="flex h-full min-h-0 flex-col bg-zinc-950">
      <div className="flex items-center justify-between gap-2 border-b border-zinc-800 px-4 py-2">
        <div>
          <h2 className="flex flex-wrap items-center gap-2 font-sans text-sm font-semibold text-zinc-100">
            <TickerLogo symbol={symbol} logoUrl={quote?.logo} size="sm" />
            <span>
              Chart Plan ·{" "}
              <span className="font-mono text-amber-400">${symbol}</span>
            </span>
            {quote?.available && quote.price != null && (
              <span className="ml-2 font-mono text-sm text-zinc-200">
                {formatQuotePrice(quote.price)}
              </span>
            )}
            {quote?.available && quote.change_percent != null && (
              <span
                className={`ml-2 font-mono text-xs ${
                  quote.change_percent >= 0 ? "text-emerald-400" : "text-red-400"
                }`}
              >
                {formatQuoteChangePercent(quote.change_percent)}
              </span>
            )}
          </h2>
          <p className="font-mono text-[10px] text-zinc-500">
            Ticker Chart Operator-first · delay ~15m{" "}
            {quoteUpdatedAt != null && (
              <span className="text-zinc-600">
                · precio {formatRefreshAge(quoteUpdatedAt)}
                {candlesUpdatedAt != null &&
                  ` · velas ${formatRefreshAge(candlesUpdatedAt)}`}
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {versions.length > 0 && (
            <select
              value={selectedVersionId ?? ""}
              onChange={(e) => setSelectedVersionId(e.target.value)}
              disabled={loading || analyzing}
              className="max-w-[160px] rounded border border-zinc-700 bg-zinc-950 px-2 py-1 font-mono text-[10px] text-zinc-300 focus:border-amber-600 focus:outline-none disabled:opacity-50"
              aria-label="Versión del Chart Plan"
            >
              {versions.map((version, index) => (
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
            onClick={() => void handleAnalyze()}
            disabled={loading || analyzing || disabled}
            className="rounded border border-sky-800/60 bg-sky-950/30 px-3 py-1 font-mono text-[10px] text-sky-400 transition-colors hover:border-sky-600 hover:text-sky-300 disabled:opacity-50"
          >
            {analyzing ? "Analizando…" : "Analizar gráficos"}
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {loading && !displayed && (
          <p className="font-mono text-xs text-zinc-500">Cargando Chart Plan…</p>
        )}

        {error && (
          <p className="font-mono text-xs text-red-400">{error}</p>
        )}

        {disabled && (
          <p className="font-mono text-xs text-zinc-500">
            Chart Agent deshabilitado (CHART_AGENT_ENABLED=false).
          </p>
        )}

        {(analyzing || steps.length > 0) && (
          <ResearchStepLoader steps={steps} active={analyzing} />
        )}

        <section className="space-y-2 rounded border border-zinc-800/80 bg-zinc-900/40 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="font-sans text-xs font-semibold uppercase tracking-wide text-zinc-400">
              Ticker Chart
            </h3>
            {softApplyAvailable && suggestedView && (
              <button
                type="button"
                onClick={() => {
                  handlePrefsChange(suggestedViewToPrefs(suggestedView));
                  setSoftApplyAvailable(false);
                }}
                className="rounded border border-sky-800/60 bg-sky-950/30 px-2 py-0.5 font-mono text-[10px] text-sky-400 hover:border-sky-600"
              >
                Aplicar vista del Chart Plan
              </button>
            )}
          </div>
          <TickerChartToolbar
            value={chartPrefs}
            onChange={handlePrefsChange}
            persist
          />
          {candlesLoading && candles.length === 0 ? (
            <p className="py-16 text-center font-mono text-xs text-zinc-500">
              Cargando velas…
            </p>
          ) : candlesError ? (
            <p className="py-8 text-center font-mono text-xs text-red-400">
              {candlesError}
            </p>
          ) : (
            <TickerChart
              symbol={symbol}
              candles={candles}
              indicators={chartPrefs}
              height={380}
            />
          )}
          {content && indicatorReadings.length > 0 && (
            <IndicatorReadingsSection
              readings={indicatorReadings}
              stale={readingsStale}
              onApplySuggested={
                suggestedView
                  ? () => {
                      handlePrefsChange(suggestedViewToPrefs(suggestedView));
                      setSoftApplyAvailable(false);
                    }
                  : undefined
              }
            />
          )}
        </section>

        {!loading && !displayed && !analyzing && (
          <EmptyState needsDossier={needsDossier} onAnalyze={() => void handleAnalyze()} />
        )}

        {content && assessment && (
          <div className="space-y-4">
            <AssessmentSection assessment={assessment} />

            {sentimentEnabled && (
              <section className="space-y-2 rounded border border-zinc-800/80 bg-zinc-900/40 p-3">
                <h3 className="font-sans text-xs font-semibold uppercase tracking-wide text-zinc-400">
                  Sentimiento
                </h3>
                <SentimentBarsChart data={chartData?.sentiment_bars ?? []} />
              </section>
            )}

            {timelineEnabled && (
              <section className="space-y-2 rounded border border-zinc-800/80 bg-zinc-900/40 p-3">
                <h3 className="font-sans text-xs font-semibold uppercase tracking-wide text-zinc-400">
                  Timeline señales
                </h3>
                <SignalsTimelineChart data={chartData?.signals_timeline ?? []} />
              </section>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

function EmptyState({
  needsDossier,
  onAnalyze,
}: {
  needsDossier: boolean;
  onAnalyze: () => void;
}) {
  return (
    <div className="space-y-3 rounded border border-dashed border-zinc-800 px-4 py-6 text-center">
      <p className="font-mono text-xs text-zinc-500">
        {needsDossier
          ? "Generá el Dossier primero (panel izquierdo) y luego analizá gráficos."
          : "Sin Chart Plan todavía. Ejecutá el Chart Agent para generar vistas."}
      </p>
      {!needsDossier && (
        <button
          type="button"
          onClick={onAnalyze}
          className="rounded border border-sky-800/60 bg-sky-950/30 px-3 py-1 font-mono text-[10px] text-sky-400 transition-colors hover:border-sky-600 hover:text-sky-300"
        >
          Analizar gráficos
        </button>
      )}
    </div>
  );
}

function AssessmentSection({
  assessment,
}: {
  assessment: {
    summary: string;
    conflicts: string[];
    data_gaps: string[];
    bias_check: string;
  };
}) {
  return (
    <section className="space-y-2 rounded border border-zinc-800/80 bg-zinc-900/30 p-3">
      <h3 className="font-sans text-xs font-semibold uppercase tracking-wide text-zinc-400">
        Lectura objetiva
      </h3>
      <div className="space-y-2 font-mono text-[11px] text-zinc-300">
        {assessment.summary && (
          <p className="text-zinc-400">{assessment.summary}</p>
        )}
        <div>
          <p className="text-[10px] uppercase tracking-wide text-zinc-500">
            Conflictos
          </p>
          {assessment.conflicts.length > 0 ? (
            <ul className="mt-1 list-inside list-disc space-y-0.5 text-zinc-400">
              {assessment.conflicts.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 text-zinc-500">Sin conflictos declarados.</p>
          )}
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wide text-zinc-500">
            Lagunas de datos
          </p>
          {assessment.data_gaps.length > 0 ? (
            <ul className="mt-1 list-inside list-disc space-y-0.5 text-zinc-400">
              {assessment.data_gaps.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 text-zinc-500">Cobertura suficiente en ventana.</p>
          )}
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wide text-zinc-500">
            Bias check
          </p>
          <p className="mt-1 text-zinc-400">{assessment.bias_check}</p>
        </div>
      </div>
    </section>
  );
}

function IndicatorReadingsSection({
  readings,
  stale = false,
  onApplySuggested,
}: {
  readings: ChartPlanIndicatorReading[];
  stale?: boolean;
  onApplySuggested?: () => void;
}) {
  const stanceStyles: Record<string, string> = {
    alcista: "border-emerald-800/60 bg-emerald-950/20 text-emerald-300",
    bajista: "border-red-800/60 bg-red-950/20 text-red-300",
    neutral: "border-zinc-700 bg-zinc-900/50 text-zinc-300",
  };

  return (
    <section className="space-y-2 border-t border-zinc-800/80 pt-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="font-sans text-[10px] font-semibold uppercase tracking-wide text-zinc-500">
          Lectura de indicadores
        </h4>
        {stale && (
          <div className="flex items-center gap-2">
            <span className="rounded border border-amber-800/50 bg-amber-950/30 px-1.5 py-0.5 font-mono text-[9px] uppercase text-amber-400">
              Desactualizado
            </span>
            {onApplySuggested && (
              <button
                type="button"
                onClick={onApplySuggested}
                className="font-mono text-[9px] text-sky-400 hover:underline"
              >
                Aplicar vista del Plan
              </button>
            )}
          </div>
        )}
      </div>
      <div className="space-y-2">
        {readings.map((item) => {
          const stance = (item.stance || "neutral").toLowerCase();
          return (
            <article
              key={item.name}
              className={`rounded border px-3 py-2 ${
                stanceStyles[stance] ?? stanceStyles.neutral
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <p className="font-mono text-[11px] font-semibold">{item.name}</p>
                <span className="font-mono text-[9px] uppercase tracking-wide opacity-80">
                  {stance}
                </span>
              </div>
              <p className="mt-1 font-mono text-[10px] leading-relaxed opacity-90">
                {item.reading}
              </p>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function SentimentBarsChart({
  data,
}: {
  data: Array<{ label: string; count: number }>;
}) {
  if (data.length === 0) {
    return (
      <p className="font-mono text-[10px] text-zinc-500">
        Sin datos de sentimiento en la ventana.
      </p>
    );
  }

  const colored = data.map((row) => ({
    ...row,
    fill: SENTIMENT_COLORS[row.label.toLowerCase()] ?? "#60a5fa",
  }));

  return (
    <div className="h-48 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={colored} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
          <XAxis
            dataKey="label"
            tick={{ fill: "#a1a1aa", fontSize: 10 }}
            axisLine={{ stroke: "#3f3f46" }}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fill: "#a1a1aa", fontSize: 10 }}
            axisLine={{ stroke: "#3f3f46" }}
          />
          <Tooltip
            contentStyle={{
              background: "#09090b",
              border: "1px solid #3f3f46",
              fontSize: 11,
            }}
          />
          <Bar dataKey="count" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function SignalsTimelineChart({
  data,
}: {
  data: Array<{ date: string; count: number }>;
}) {
  if (data.length === 0) {
    return (
      <p className="font-mono text-[10px] text-zinc-500">
        Sin señales recientes para timeline.
      </p>
    );
  }

  const useLine = data.length >= 6;

  return (
    <div className="h-48 w-full">
      <ResponsiveContainer width="100%" height="100%">
        {useLine ? (
          <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
            <XAxis
              dataKey="date"
              tick={{ fill: "#a1a1aa", fontSize: 9 }}
              axisLine={{ stroke: "#3f3f46" }}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fill: "#a1a1aa", fontSize: 10 }}
              axisLine={{ stroke: "#3f3f46" }}
            />
            <Tooltip
              contentStyle={{
                background: "#09090b",
                border: "1px solid #3f3f46",
                fontSize: 11,
              }}
            />
            <Line
              type="monotone"
              dataKey="count"
              stroke="#38bdf8"
              strokeWidth={2}
              dot={{ r: 2, fill: "#38bdf8" }}
            />
          </LineChart>
        ) : (
          <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
            <XAxis
              dataKey="date"
              tick={{ fill: "#a1a1aa", fontSize: 9 }}
              axisLine={{ stroke: "#3f3f46" }}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fill: "#a1a1aa", fontSize: 10 }}
              axisLine={{ stroke: "#3f3f46" }}
            />
            <Tooltip
              contentStyle={{
                background: "#09090b",
                border: "1px solid #3f3f46",
                fontSize: 11,
              }}
            />
            <Bar dataKey="count" fill="#38bdf8" radius={[3, 3, 0, 0]} />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

