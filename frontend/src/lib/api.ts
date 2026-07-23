import { fetchEventSource } from "@microsoft/fetch-event-source";
import { createClient } from "@/lib/supabase/client";
import { isSupabaseConfigured } from "@/lib/supabase/env";
import type { FeedFilterQuery } from "./feedFilters";
import type {
  BotConfig,
  BotEvent,
  BotFill,
  BotPosition,
  ChartPlanVersion,
  ChatArtifact,
  ChatCitation,
  DossierVersion,
  PriceChartArtifact,
  PriceChartCandle,
  Quote,
  ResearchStep,
  SignalDetail,
  SignalSummary,
  TickerSuggestion,
  TickerWatchEntry,
} from "./types";

function asFiniteNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function parsePriceChartCandle(raw: unknown): PriceChartCandle | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as Record<string, unknown>;
  // Backend Market Data uses `date`; chat artifact contract prefers `t`.
  const tRaw = row.t ?? row.date;
  const t =
    typeof tRaw === "string"
      ? tRaw
      : typeof tRaw === "number"
        ? String(tRaw)
        : null;
  const open = asFiniteNumber(row.open);
  const high = asFiniteNumber(row.high);
  const low = asFiniteNumber(row.low);
  const close = asFiniteNumber(row.close);
  if (!t || open == null || high == null || low == null || close == null) {
    return null;
  }
  return { t, open, high, low, close };
}

/** Defensive parse for SSE / history artifacts. Returns null if unusable. */
export function parseChatArtifact(raw: unknown): ChatArtifact | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  if (obj.type !== "price_chart") return null;

  const symbol =
    typeof obj.symbol === "string" ? obj.symbol.trim().toUpperCase() : "";
  const period = typeof obj.period === "string" ? obj.period.trim() : "";
  if (!symbol || !period) return null;
  // Never treat ISO FX codes as equity Chart cards (e.g. mistaken USD ~$92).
  const FX_CODES = new Set([
    "USD",
    "ARS",
    "EUR",
    "GBP",
    "JPY",
    "BRL",
    "CNY",
    "MXN",
    "CLP",
    "UYU",
    "CAD",
    "AUD",
    "CHF",
    "NZD",
  ]);
  if (FX_CODES.has(symbol)) return null;

  const candlesRaw = Array.isArray(obj.candles) ? obj.candles : [];
  const candles: PriceChartCandle[] = [];
  for (const item of candlesRaw) {
    const candle = parsePriceChartCandle(item);
    if (candle) candles.push(candle);
  }
  if (candles.length === 0) return null;

  const interval =
    typeof obj.interval === "string" && obj.interval.trim()
      ? obj.interval.trim()
      : undefined;

  const artifact: PriceChartArtifact = {
    type: "price_chart",
    symbol,
    period,
    interval,
    candles,
    start_price: asFiniteNumber(obj.start_price),
    end_price: asFiniteNumber(obj.end_price),
    change_percent: asFiniteNumber(obj.change_percent),
  };
  return artifact;
}

function normalizeApiUrl(raw: string): string {
  const trimmed = raw.trim().replace(/\/+$/, "");
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  return `https://${trimmed}`;
}

const API_URL = normalizeApiUrl(
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
);

export function getApiUrl(): string {
  return API_URL;
}

export { isSupabaseConfigured };

let cachedToken: string | null | undefined;

export function clearAccessTokenCache(): void {
  cachedToken = undefined;
}

async function fetchAccessToken(): Promise<string | null> {
  try {
    const res = await fetch("/api/auth/token", { credentials: "include" });
    if (res.ok) {
      const data = (await res.json()) as { access_token?: string };
      if (data.access_token) return data.access_token;
    }
  } catch {
    // fallback abajo
  }

  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}

export async function getAccessToken(): Promise<string | null> {
  if (!isSupabaseConfigured()) return null;
  if (cachedToken !== undefined) return cachedToken;
  cachedToken = await fetchAccessToken();
  return cachedToken;
}

export async function authHeaders(): Promise<Record<string, string>> {
  const token = await getAccessToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

export async function fetchSignals(
  limit = 50,
  options?: FeedFilterQuery,
  offset = 0,
): Promise<SignalSummary[]> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  appendFeedFilterParams(params, options);
  const res = await fetch(`${API_URL}/signals?${params}`, {
    headers: await authHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch signals: ${res.status}`);
  }
  return res.json();
}

function appendFeedFilterParams(
  params: URLSearchParams,
  options?: FeedFilterQuery,
): void {
  if (options?.q) params.set("q", options.q);
  if (options?.ticker) {
    params.set("ticker", options.ticker.replace(/^\$/, ""));
  }
  if (options?.source_type) params.set("source_type", options.source_type);
  if (options?.since_hours) {
    params.set("since_hours", String(options.since_hours));
  }
}

export async function fetchSignalCount(
  options?: FeedFilterQuery,
): Promise<number> {
  const params = new URLSearchParams();
  appendFeedFilterParams(params, options);
  const query = params.toString();
  const res = await fetch(
    `${API_URL}/signals/count${query ? `?${query}` : ""}`,
    { headers: await authHeaders() },
  );
  if (!res.ok) {
    throw new Error(`Failed to fetch signal count: ${res.status}`);
  }
  const data = (await res.json()) as { total: number };
  return data.total;
}

export async function fetchTickerWatch(): Promise<TickerWatchEntry[]> {
  const res = await fetch(`${API_URL}/watch`, {
    headers: await authHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch ticker watch: ${res.status}`);
  }
  return res.json();
}

export async function addTickerWatch(
  symbol: string,
): Promise<TickerWatchEntry> {
  const cleaned = symbol.replace(/^\$/, "").trim();
  const res = await fetch(`${API_URL}/watch`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(await authHeaders()),
    },
    body: JSON.stringify({ symbol: cleaned }),
  });
  if (!res.ok) {
    throw new Error(`Failed to add ticker watch: ${res.status}`);
  }
  return res.json();
}

export async function removeTickerWatch(symbol: string): Promise<void> {
  const normalized = symbol.replace(/^\$/, "").trim().toUpperCase();
  const res = await fetch(
    `${API_URL}/watch/${encodeURIComponent(normalized)}`,
    {
      method: "DELETE",
      headers: await authHeaders(),
    },
  );
  if (!res.ok) {
    throw new Error(`Failed to remove ticker watch: ${res.status}`);
  }
}

export async function updateTickerWatchThesis(
  symbol: string,
  note: string | null,
): Promise<TickerWatchEntry> {
  const normalized = symbol.replace(/^\$/, "").trim().toUpperCase();
  const trimmed = note?.trim() ?? "";
  const payload = { note: trimmed.length > 0 ? trimmed : null };
  const res = await fetch(
    `${API_URL}/watch/${encodeURIComponent(normalized)}`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...(await authHeaders()),
      },
      body: JSON.stringify(payload),
    },
  );
  if (!res.ok) {
    throw new Error(`Failed to update ticker thesis: ${res.status}`);
  }
  return res.json();
}

export async function fetchTickerSuggestions(
  prefix = "",
  limit = 50,
): Promise<TickerSuggestion[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (prefix) params.set("q", prefix);
  const res = await fetch(`${API_URL}/quotes/tickers?${params}`, {
    headers: await authHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch ticker suggestions: ${res.status}`);
  }
  return res.json();
}

export async function fetchSignal(idStr: string): Promise<SignalDetail> {
  const res = await fetch(`${API_URL}/signals/${idStr}`, {
    headers: await authHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch signal: ${res.status}`);
  }
  return res.json();
}

export async function refreshIngest(): Promise<void> {
  const res = await fetch(`${API_URL}/ingest/refresh`, {
    method: "POST",
    headers: await authHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to refresh ingest: ${res.status}`);
  }
}

export function createSignalStreamUrl(): string {
  return `${API_URL}/signals/stream`;
}

export async function fetchWatchlistQuotes(): Promise<Quote[]> {
  const res = await fetch(`${API_URL}/quotes/watchlist`, {
    headers: await authHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch watchlist quotes: ${res.status}`);
  }
  return res.json();
}

export async function fetchQuotes(symbols: string[]): Promise<Quote[]> {
  if (symbols.length === 0) return [];
  const normalized = symbols.map((s) => s.replace(/^\$/, "").toUpperCase());
  const params = new URLSearchParams({ symbols: normalized.join(",") });
  const res = await fetch(`${API_URL}/quotes?${params}`, {
    headers: await authHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch quotes: ${res.status}`);
  }
  return res.json();
}

export async function fetchTickerLogos(
  symbols: string[],
): Promise<Record<string, string | null>> {
  if (symbols.length === 0) return {};
  const normalized = [
    ...new Set(symbols.map((s) => s.replace(/^\$/, "").toUpperCase())),
  ];
  const params = new URLSearchParams({ symbols: normalized.join(",") });
  const res = await fetch(`${API_URL}/quotes/logos?${params}`, {
    headers: await authHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch ticker logos: ${res.status}`);
  }
  const rows = (await res.json()) as import("./types").TickerLogoEntry[];
  const map: Record<string, string | null> = {};
  for (const row of rows) {
    map[row.symbol] = row.logo;
  }
  return map;
}

export async function fetchPriceCandles(
  symbol: string,
  period = "1y",
  interval = "1d",
): Promise<import("./types").PriceCandlesResponse> {
  const normalized = symbol.replace(/^\$/, "").toUpperCase();
  const params = new URLSearchParams({
    symbol: normalized,
    period,
    interval,
  });

  const backendRes = await fetch(`${API_URL}/quotes/candles?${params}`, {
    headers: await authHeaders(),
    cache: "no-store",
  });

  if (backendRes.ok) {
    return backendRes.json();
  }

  // Fallback: API local sin redeploy o sin el endpoint nuevo
  if (backendRes.status === 404 || backendRes.status === 401) {
    const localRes = await fetch(`/api/candles?${params}`, { cache: "no-store" });
    if (localRes.ok) {
      return localRes.json();
    }
  }

  let detail = `HTTP ${backendRes.status}`;
  try {
    const body = (await backendRes.json()) as { detail?: string };
    if (body.detail) detail = body.detail;
  } catch {
    // ignore
  }
  throw new Error(`Failed to fetch candles: ${detail}`);
}

export async function fetchChatSessions(
  limit = 20,
): Promise<import("./types").ChatSessionSummary[]> {
  const res = await fetch(`${API_URL}/chat/sessions?limit=${limit}`, {
    headers: await authHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch chat sessions: ${res.status}`);
  }
  return res.json();
}

export async function createChatSession(
  title?: string,
): Promise<import("./types").ChatSessionSummary> {
  const res = await fetch(`${API_URL}/chat/sessions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(await authHeaders()),
    },
    body: JSON.stringify(title ? { title } : {}),
  });
  if (!res.ok) {
    throw new Error(`Failed to create chat session: ${res.status}`);
  }
  return res.json();
}

export async function fetchChatMessages(
  sessionId: string,
): Promise<import("./types").ChatMessageRecord[]> {
  const res = await fetch(`${API_URL}/chat/sessions/${sessionId}/messages`, {
    headers: await authHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch chat messages: ${res.status}`);
  }
  return res.json();
}

export type StreamChatCallbacks = {
  onToken: (token: string) => void;
  onCitations: (citations: ChatCitation[]) => void;
  onStep?: (step: ResearchStep) => void;
  onSession?: (sessionId: string) => void;
  onArtifact?: (artifact: ChatArtifact) => void;
  onError?: (error: Error) => void;
};

async function readSseStream(
  res: Response,
  callbacks: StreamChatCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const reader = res.body?.getReader();
  if (!reader) {
    throw new Error("No response body");
  }

  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (line.startsWith(":")) {
          continue;
        }
        if (line.startsWith("event: ")) {
          currentEvent = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          const raw = line.slice(6);
          if (currentEvent === "citations") {
            callbacks.onCitations(JSON.parse(raw) as ChatCitation[]);
            currentEvent = "";
          } else if (currentEvent === "session") {
            const payload = JSON.parse(raw) as { session_id?: string };
            if (payload.session_id) {
              callbacks.onSession?.(payload.session_id);
            }
            currentEvent = "";
          } else if (currentEvent === "step") {
            callbacks.onStep?.(JSON.parse(raw) as ResearchStep);
            currentEvent = "";
          } else if (currentEvent === "artifact") {
            try {
              const artifact = parseChatArtifact(JSON.parse(raw));
              if (artifact) callbacks.onArtifact?.(artifact);
            } catch {
              // Malformed artifact payloads must not break the stream.
            }
            currentEvent = "";
          } else {
            const token = JSON.parse(raw) as string;
            callbacks.onToken(token);
          }
        } else if (line === "") {
          currentEvent = "";
        }
      }
    }
  } catch (err) {
    if (signal?.aborted) return;
    const error = err instanceof Error ? err : new Error(String(err));
    callbacks.onError?.(error);
    throw error;
  }
}

export async function streamChat(
  query: string,
  callbacks: StreamChatCallbacks,
  signal?: AbortSignal,
  sessionId?: string | null,
): Promise<void> {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(await authHeaders()),
    },
    body: JSON.stringify({
      query,
      session_id: sessionId ?? undefined,
    }),
    signal,
  });

  if (!res.ok) {
    throw new Error(`Chat request failed: ${res.status}`);
  }

  await readSseStream(res, callbacks, signal);
}

export async function streamBriefing(
  callbacks: StreamChatCallbacks,
  signal?: AbortSignal,
  sessionId?: string | null,
): Promise<void> {
  const res = await fetch(`${API_URL}/chat/briefing`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(await authHeaders()),
    },
    body: JSON.stringify({
      session_id: sessionId ?? undefined,
    }),
    signal,
  });

  if (!res.ok) {
    throw new Error(`Briefing request failed: ${res.status}`);
  }

  await readSseStream(res, callbacks, signal);
}

function normalizeDossierSymbol(symbol: string): string {
  return symbol.replace(/^\$/, "").trim().toUpperCase();
}

export async function fetchDossier(symbol: string): Promise<DossierVersion | null> {
  const normalized = normalizeDossierSymbol(symbol);
  const res = await fetch(`${API_URL}/dossier/${encodeURIComponent(normalized)}`, {
    headers: await authHeaders(),
  });
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(`Failed to fetch dossier: ${res.status}`);
  }
  return res.json();
}

export async function fetchDossierVersions(
  symbol: string,
): Promise<DossierVersion[]> {
  const normalized = normalizeDossierSymbol(symbol);
  const res = await fetch(
    `${API_URL}/dossier/${encodeURIComponent(normalized)}/versions`,
    { headers: await authHeaders() },
  );
  if (!res.ok) {
    throw new Error(`Failed to fetch dossier versions: ${res.status}`);
  }
  return res.json();
}

export async function refreshDossier(symbol: string): Promise<DossierVersion> {
  const normalized = normalizeDossierSymbol(symbol);
  const res = await fetch(
    `${API_URL}/dossier/${encodeURIComponent(normalized)}/refresh`,
    {
      method: "POST",
      headers: await authHeaders(),
    },
  );
  if (!res.ok) {
    throw new Error(`Failed to refresh dossier: ${res.status}`);
  }
  const body = (await res.json()) as { version: DossierVersion };
  return body.version;
}

export async function fetchChartPlan(
  symbol: string,
): Promise<ChartPlanVersion | null> {
  const normalized = normalizeDossierSymbol(symbol);
  const res = await fetch(
    `${API_URL}/chart-plan/${encodeURIComponent(normalized)}`,
    { headers: await authHeaders() },
  );
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(`Failed to fetch chart plan: ${res.status}`);
  }
  return res.json();
}

export async function fetchChartPlanVersions(
  symbol: string,
): Promise<ChartPlanVersion[]> {
  const normalized = normalizeDossierSymbol(symbol);
  const res = await fetch(
    `${API_URL}/chart-plan/${encodeURIComponent(normalized)}/versions`,
    { headers: await authHeaders() },
  );
  if (!res.ok) {
    throw new Error(`Failed to fetch chart plan versions: ${res.status}`);
  }
  return res.json();
}

export type StreamChartPlanCallbacks = {
  onStep?: (step: ResearchStep) => void;
  onVersion?: (version: ChartPlanVersion) => void;
  onError?: (error: Error) => void;
};

export class ChartPlanAnalyzeError extends Error {
  constructor(
    message: string,
    readonly code: "disabled" | "dossier_missing" | "failed",
  ) {
    super(message);
    this.name = "ChartPlanAnalyzeError";
  }
}

export type ChartPlanAnalyzeBody = {
  chart_image_base64?: string | null;
  chart_image_media_type?: string;
  chart_view?: Record<string, unknown> | null;
};

export async function getBotConfig(): Promise<BotConfig> {
  const res = await fetch(`${API_URL}/bot/config`, {
    headers: await authHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch bot config: ${res.status}`);
  }
  return res.json();
}

export async function patchBotConfig(
  partial: Partial<BotConfig>,
): Promise<BotConfig> {
  const res = await fetch(`${API_URL}/bot/config`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...(await authHeaders()),
    },
    body: JSON.stringify(partial),
  });
  if (!res.ok) {
    throw new Error(`Failed to update bot config: ${res.status}`);
  }
  return res.json();
}

export async function listBotPositions(
  status?: "open" | "closed",
): Promise<BotPosition[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  const query = params.toString();
  const res = await fetch(
    `${API_URL}/bot/positions${query ? `?${query}` : ""}`,
    { headers: await authHeaders() },
  );
  if (!res.ok) {
    throw new Error(`Failed to fetch bot positions: ${res.status}`);
  }
  return res.json();
}

export async function closeBotPosition(id: string): Promise<BotPosition> {
  const res = await fetch(`${API_URL}/bot/positions/${encodeURIComponent(id)}/close`, {
    method: "POST",
    headers: await authHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to close bot position: ${res.status}`);
  }
  return res.json();
}

export async function listBotFills(): Promise<BotFill[]> {
  const res = await fetch(`${API_URL}/bot/fills`, {
    headers: await authHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch bot fills: ${res.status}`);
  }
  return res.json();
}

export async function listBotEvents(): Promise<BotEvent[]> {
  const res = await fetch(`${API_URL}/bot/events`, {
    headers: await authHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch bot events: ${res.status}`);
  }
  return res.json();
}

export async function streamChartPlanAnalyze(
  symbol: string,
  callbacks: StreamChartPlanCallbacks,
  signal?: AbortSignal,
  body?: ChartPlanAnalyzeBody,
): Promise<void> {
  const normalized = normalizeDossierSymbol(symbol);
  const headers = await authHeaders();
  const payload: ChartPlanAnalyzeBody = {
    chart_image_base64: body?.chart_image_base64 ?? null,
    chart_image_media_type: body?.chart_image_media_type ?? "image/png",
    chart_view: body?.chart_view ?? null,
  };

  try {
    await fetchEventSource(
      `${API_URL}/chart-plan/${encodeURIComponent(normalized)}/analyze`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...headers,
        },
        body: JSON.stringify(payload),
        signal,
        async onopen(res) {
          if (res.status === 503) {
            throw new ChartPlanAnalyzeError(
              "Chart Agent deshabilitado en el servidor",
              "disabled",
            );
          }
          if (res.status === 404) {
            throw new ChartPlanAnalyzeError(
              "Generá el Dossier primero",
              "dossier_missing",
            );
          }
          if (!res.ok) {
            throw new ChartPlanAnalyzeError(
              `Chart plan analyze failed: ${res.status}`,
              "failed",
            );
          }
        },
        onmessage(ev) {
          if (ev.event === "step" && ev.data) {
            callbacks.onStep?.(JSON.parse(ev.data) as ResearchStep);
            return;
          }
          if (
            (ev.event === "chart_plan" || ev.event === "version") &&
            ev.data
          ) {
            callbacks.onVersion?.(JSON.parse(ev.data) as ChartPlanVersion);
            return;
          }
          if (ev.event === "error" && ev.data) {
            const payload = JSON.parse(ev.data) as { detail?: string };
            throw new ChartPlanAnalyzeError(
              payload.detail ?? "Chart plan analyze error",
              "failed",
            );
          }
        },
        onerror(err) {
          if (signal?.aborted) return;
          const error =
            err instanceof Error ? err : new Error(String(err ?? "SSE error"));
          callbacks.onError?.(error);
          throw error;
        },
      },
    );
  } catch (err) {
    if (signal?.aborted) return;
    const error = err instanceof Error ? err : new Error(String(err));
    callbacks.onError?.(error);
    throw error;
  }
}
