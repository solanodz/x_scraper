import { createClient } from "@/lib/supabase/client";
import { isSupabaseConfigured } from "@/lib/supabase/env";
import type { FeedFilterQuery } from "./feedFilters";
import type { ChatCitation, Quote, SignalDetail, SignalSummary, TickerSuggestion } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
): Promise<SignalSummary[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (options?.q) params.set("q", options.q);
  if (options?.ticker) {
    params.set("ticker", options.ticker.replace(/^\$/, ""));
  }
  if (options?.source_type) params.set("source_type", options.source_type);
  if (options?.since_hours) {
    params.set("since_hours", String(options.since_hours));
  }
  const res = await fetch(`${API_URL}/signals?${params}`, {
    headers: await authHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch signals: ${res.status}`);
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

export async function streamChat(
  query: string,
  callbacks: {
    onToken: (token: string) => void;
    onCitations: (citations: ChatCitation[]) => void;
    onSession?: (sessionId: string) => void;
    onError?: (error: Error) => void;
  },
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
