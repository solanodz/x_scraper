"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ChatMarkdown, { isBriefingAssistantMessage } from "@/components/ChatMarkdown";
import ChatSessionSelect from "@/components/ChatSessionSelect";
import ResearchStepLoader from "@/components/ResearchStepLoader";
import {
  createChatSession,
  fetchChatMessages,
  fetchChatSessions,
  fetchTickerWatch,
  streamBriefing,
  streamChat,
  type StreamChatCallbacks,
} from "@/lib/api";
import type {
  ChatMessage,
  ChatMessageRecord,
  ChatSessionSummary,
  ResearchStep,
} from "@/lib/types";

const ACTIVE_SESSION_KEY = "xscraper:activeChatSession";
const BRIEFING_USER_MESSAGE = "Briefing de mi Ticker Watch";

function briefingSessionTitle(): string {
  const now = new Date();
  const dd = String(now.getDate()).padStart(2, "0");
  const mm = String(now.getMonth() + 1).padStart(2, "0");
  const yyyy = now.getFullYear();
  return `Briefing ${dd}/${mm}/${yyyy}`;
}

type AssistantStreamFn = (
  callbacks: StreamChatCallbacks,
  signal: AbortSignal,
  sessionId: string,
) => Promise<void>;

interface ResearchChatProps {
  onCitationClick: (idStr: string) => void;
}

function recordsToMessages(records: ChatMessageRecord[]): ChatMessage[] {
  return records.map((row) => ({
    role: row.role,
    content: row.content,
    citations: row.citations ?? undefined,
  }));
}

export default function ResearchChat({ onCitationClick }: ResearchChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [loading, setLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [watchEmpty, setWatchEmpty] = useState(true);
  const abortRef = useRef<AbortController | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const messagesRef = useRef(messages);
  const streamingRef = useRef(streaming);
  messagesRef.current = messages;
  streamingRef.current = streaming;

  const persistActiveSession = useCallback((sessionId: string | null) => {
    sessionIdRef.current = sessionId;
    setActiveSessionId(sessionId);
    if (sessionId) {
      sessionStorage.setItem(ACTIVE_SESSION_KEY, sessionId);
    } else {
      sessionStorage.removeItem(ACTIVE_SESSION_KEY);
    }
  }, []);

  const loadSessionMessages = useCallback(async (sessionId: string) => {
    const records = await fetchChatMessages(sessionId);
    setMessages(recordsToMessages(records));
  }, []);

  const refreshSessions = useCallback(async () => {
    const list = await fetchChatSessions(20);
    setSessions(list);
    return list;
  }, []);

  useEffect(() => {
    fetchTickerWatch()
      .then((entries) => setWatchEmpty(entries.length === 0))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      setLoading(true);
      setHistoryError(null);
      try {
        const list = await refreshSessions();
        const stored = sessionStorage.getItem(ACTIVE_SESSION_KEY);
        const initialId =
          stored && list.some((s) => s.id === stored)
            ? stored
            : list[0]?.id ?? null;

        if (cancelled) return;

        if (initialId) {
          persistActiveSession(initialId);
          await loadSessionMessages(initialId);
        } else {
          persistActiveSession(null);
          setMessages([]);
        }
      } catch {
        if (!cancelled) {
          setHistoryError("Historial no disponible (¿migración chat aplicada?)");
          setMessages([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    init();
    return () => {
      cancelled = true;
    };
  }, [loadSessionMessages, persistActiveSession, refreshSessions]);

  async function handleNewChat() {
    if (streaming) return;
    try {
      const session = await createChatSession();
      persistActiveSession(session.id);
      setMessages([]);
      const list = await refreshSessions();
      setSessions([session, ...list.filter((s) => s.id !== session.id)]);
    } catch {
      setHistoryError("No se pudo crear una nueva sesión");
    }
  }

  async function handleSelectSession(sessionId: string) {
    if (streaming || sessionId === activeSessionId) return;
    try {
      persistActiveSession(sessionId);
      await loadSessionMessages(sessionId);
      setHistoryError(null);
    } catch {
      setHistoryError("No se pudo cargar la sesión");
    }
  }

  const runAssistantStream = useCallback(
    async (streamFn: AssistantStreamFn, userDisplayMessage: string) => {
      if (streamingRef.current) return;

      setMessages((prev) => [
        ...prev,
        { role: "user", content: userDisplayMessage },
      ]);
      setStreaming(true);

      const assistantIndex = messagesRef.current.length + 1;
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "", steps: [] },
      ]);

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      let sessionId = sessionIdRef.current;
      if (!sessionId) {
        try {
          const session = await createChatSession();
          sessionId = session.id;
          persistActiveSession(sessionId);
          const list = await refreshSessions();
          setSessions([session, ...list.filter((s) => s.id !== session.id)]);
        } catch {
          setHistoryError("No se pudo iniciar la sesión de chat");
          setStreaming(false);
          return;
        }
      }

      try {
        await streamFn(
          {
            onSession: (nextSessionId) => {
              persistActiveSession(nextSessionId);
              refreshSessions().then(setSessions).catch(() => undefined);
            },
            onStep: (step: ResearchStep) => {
              setMessages((prev) => {
                const updated = [...prev];
                const msg = updated[assistantIndex];
                if (msg?.role !== "assistant") return prev;

                const prior = msg.steps ?? [];
                const existingIdx = prior.findIndex(
                  (s) => s.tool === step.tool && s.label === step.label,
                );
                let nextSteps: ResearchStep[];
                if (existingIdx >= 0) {
                  nextSteps = [...prior];
                  nextSteps[existingIdx] = step;
                } else {
                  nextSteps = [...prior, step];
                }

                updated[assistantIndex] = { ...msg, steps: nextSteps };
                return updated;
              });
            },
            onToken: (token) => {
              setMessages((prev) => {
                const updated = [...prev];
                const msg = updated[assistantIndex];
                if (msg?.role === "assistant") {
                  updated[assistantIndex] = {
                    ...msg,
                    content: msg.content + token,
                  };
                }
                return updated;
              });
            },
            onCitations: (citations) => {
              setMessages((prev) => {
                const updated = [...prev];
                const msg = updated[assistantIndex];
                if (msg?.role === "assistant") {
                  updated[assistantIndex] = { ...msg, citations };
                }
                return updated;
              });
            },
          },
          controller.signal,
          sessionId,
        );
      } catch {
        setMessages((prev) => {
          const updated = [...prev];
          const msg = updated[assistantIndex];
          if (msg?.role === "assistant" && !msg.content) {
            updated[assistantIndex] = {
              ...msg,
              content: "Error: failed to get response.",
            };
          }
          return updated;
        });
      } finally {
        setStreaming(false);
      }
    },
    [persistActiveSession, refreshSessions],
  );

  const runBriefing = useCallback(async () => {
    if (streamingRef.current) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setStreaming(true);

    let sessionId: string;
    try {
      const session = await createChatSession(briefingSessionTitle());
      sessionId = session.id;
      persistActiveSession(sessionId);
      const list = await refreshSessions();
      setSessions([session, ...list.filter((s) => s.id !== session.id)]);
    } catch {
      setHistoryError("No se pudo crear la sesión de Briefing");
      setStreaming(false);
      return;
    }

    setMessages([
      { role: "user", content: BRIEFING_USER_MESSAGE },
      { role: "assistant", content: "", steps: [] },
    ]);

    const assistantIndex = 1;

    try {
      await streamBriefing(
        {
          onSession: (nextSessionId) => {
            persistActiveSession(nextSessionId);
            refreshSessions().then(setSessions).catch(() => undefined);
          },
          onStep: (step: ResearchStep) => {
            setMessages((prev) => {
              const updated = [...prev];
              const msg = updated[assistantIndex];
              if (msg?.role !== "assistant") return prev;

              const prior = msg.steps ?? [];
              const existingIdx = prior.findIndex(
                (s) => s.tool === step.tool && s.label === step.label,
              );
              let nextSteps: ResearchStep[];
              if (existingIdx >= 0) {
                nextSteps = [...prior];
                nextSteps[existingIdx] = step;
              } else {
                nextSteps = [...prior, step];
              }

              updated[assistantIndex] = { ...msg, steps: nextSteps };
              return updated;
            });
          },
          onToken: (token) => {
            setMessages((prev) => {
              const updated = [...prev];
              const msg = updated[assistantIndex];
              if (msg?.role === "assistant") {
                updated[assistantIndex] = {
                  ...msg,
                  content: msg.content + token,
                };
              }
              return updated;
            });
          },
          onCitations: (citations) => {
            setMessages((prev) => {
              const updated = [...prev];
              const msg = updated[assistantIndex];
              if (msg?.role === "assistant") {
                updated[assistantIndex] = { ...msg, citations };
              }
              return updated;
            });
          },
        },
        controller.signal,
        sessionId,
      );
    } catch {
      setMessages((prev) => {
        const updated = [...prev];
        const msg = updated[assistantIndex];
        if (msg?.role === "assistant" && !msg.content) {
          updated[assistantIndex] = {
            ...msg,
            content: "Error: failed to get response.",
          };
        }
        return updated;
      });
    } finally {
      setStreaming(false);
    }
  }, [persistActiveSession, refreshSessions]);

  useEffect(() => {
    function handleBriefingEvent() {
      void runBriefing();
    }

    window.addEventListener("xscraper:briefing", handleBriefingEvent);
    return () => {
      window.removeEventListener("xscraper:briefing", handleBriefingEvent);
    };
  }, [runBriefing]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const query = input.trim();
    if (!query || streaming) return;

    setInput("");
    await runAssistantStream(
      (callbacks, signal, sessionId) =>
        streamChat(query, callbacks, signal, sessionId),
      query,
    );
  }

  function handleBriefing() {
    void runBriefing();
  }


  return (
    <section className="flex h-full min-h-0 flex-col bg-zinc-900">
      <div className="flex items-center justify-between gap-2 border-b border-zinc-800 px-3 py-1.5">
        <h2 className="font-sans text-xs font-semibold uppercase tracking-wider text-amber-500">
          Research Chat
        </h2>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleBriefing}
            disabled={streaming || watchEmpty}
            className="rounded border border-amber-800/60 bg-amber-950/30 px-2 py-0.5 font-mono text-[10px] text-amber-400 hover:border-amber-600 hover:text-amber-300 disabled:opacity-50"
          >
            Briefing
          </button>
          <button
            type="button"
            onClick={handleNewChat}
            disabled={streaming}
            className="rounded border border-zinc-700 px-2 py-0.5 font-mono text-[10px] text-zinc-400 hover:border-amber-600 hover:text-amber-400 disabled:opacity-50"
          >
            Nueva
          </button>
        </div>
      </div>

      {sessions.length > 0 && (
        <div className="flex items-center gap-2 border-b border-zinc-800/80 px-3 py-1.5">
          <ChatSessionSelect
            sessions={sessions}
            activeSessionId={activeSessionId}
            onSelect={handleSelectSession}
            disabled={streaming}
            loading={loading}
          />
        </div>
      )}

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
        {loading && (
          <p className="font-mono text-xs text-zinc-500">Cargando historial…</p>
        )}
        {historyError && (
          <p className="font-mono text-xs text-amber-600">{historyError}</p>
        )}
        {!loading && messages.length === 0 && !historyError && (
          <p className="font-mono text-xs text-zinc-500">
            Preguntá por tickers, precios, noticias o análisis cruzado — ej.
            &quot;¿cómo está NVDA y qué dicen en X?&quot;
          </p>
        )}
        {messages.map((msg, i) => (
          <div key={i}>
            {msg.role === "user" ? (
              <div className="rounded border border-zinc-700 bg-zinc-950 px-3 py-2">
                <p className="font-mono text-xs text-zinc-300">{msg.content}</p>
              </div>
            ) : (
              <div className="space-y-2">
                {msg.steps && msg.steps.length > 0 && (
                  <ResearchStepLoader
                    steps={msg.steps}
                    active={streaming && i === messages.length - 1 && !msg.content}
                  />
                )}
                {streaming && i === messages.length - 1 && !msg.content && !msg.steps?.length && (
                  <ResearchStepLoader steps={[]} active />
                )}
                {(msg.content || !(streaming && i === messages.length - 1)) && (
                  <ChatMarkdown
                    content={msg.content}
                    streaming={streaming && i === messages.length - 1}
                    citations={msg.citations}
                    onCitationClick={onCitationClick}
                    variant={
                      isBriefingAssistantMessage(messages, i)
                        ? "briefing"
                        : "default"
                    }
                  />
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      <form
        onSubmit={handleSend}
        className="flex gap-2 border-t border-zinc-800 p-3"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Preguntá por tickers, precios, noticias…"
          disabled={streaming}
          className="min-w-0 flex-1 rounded border border-zinc-700 bg-zinc-950 px-3 py-1.5 font-mono text-xs text-zinc-200 placeholder:text-zinc-600 focus:border-amber-600 focus:outline-none disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={streaming || !input.trim()}
          className="rounded border border-zinc-700 bg-zinc-800 px-3 py-1.5 font-sans text-xs text-zinc-300 transition-colors hover:border-amber-600 hover:text-amber-400 disabled:opacity-50"
        >
          {streaming ? "…" : "Send"}
        </button>
      </form>
    </section>
  );
}
