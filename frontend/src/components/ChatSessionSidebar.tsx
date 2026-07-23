"use client";

import { timeAgo, truncate } from "@/lib/format";
import type { ChatSessionSummary } from "@/lib/types";

interface ChatSessionSidebarProps {
  sessions: ChatSessionSummary[];
  activeSessionId: string | null;
  onSelect: (sessionId: string) => void;
  onNewChat: () => void;
  onBriefing: () => void;
  disabled?: boolean;
  loading?: boolean;
  watchEmpty?: boolean;
  streaming?: boolean;
}

function sessionTitle(session: ChatSessionSummary): string {
  return session.title?.trim() || "Sin título";
}

export default function ChatSessionSidebar({
  sessions,
  activeSessionId,
  onSelect,
  onNewChat,
  onBriefing,
  disabled = false,
  loading = false,
  watchEmpty = false,
  streaming = false,
}: ChatSessionSidebarProps) {
  const controlsDisabled = disabled || streaming;

  return (
    <aside className="flex h-full w-72 shrink-0 flex-col border-r border-zinc-800 bg-zinc-950">
      <div className="flex items-center justify-between gap-2 border-b border-zinc-800 px-3 py-2">
        <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
          Historial
        </span>
        <button
          type="button"
          onClick={onNewChat}
          disabled={controlsDisabled}
          className="rounded border border-zinc-700 px-2 py-0.5 font-mono text-[10px] text-zinc-400 transition-colors hover:border-amber-600 hover:text-amber-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Nueva
        </button>
      </div>

      <div className="border-b border-zinc-800 px-3 py-2">
        <button
          type="button"
          onClick={onBriefing}
          disabled={streaming || watchEmpty || disabled}
          className="w-full rounded border border-amber-800/60 bg-amber-950/30 px-2 py-1.5 font-mono text-[10px] text-amber-400 transition-colors hover:border-amber-600 hover:text-amber-300 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Briefing
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading ? (
          <p className="px-3 py-4 font-mono text-[10px] text-zinc-500">
            Cargando sesiones…
          </p>
        ) : sessions.length === 0 ? (
          <p className="px-3 py-4 font-mono text-[10px] leading-relaxed text-zinc-600">
            Sin sesiones. Empezá un Research Chat con Nueva o Briefing.
          </p>
        ) : (
          <ul className="py-1">
            {sessions.map((session) => {
              const selected = session.id === activeSessionId;
              return (
                <li key={session.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(session.id)}
                    disabled={controlsDisabled}
                    className={`w-full border-l-2 px-3 py-2 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                      selected
                        ? "border-amber-500 bg-zinc-900/80"
                        : "border-transparent hover:bg-zinc-900/50"
                    }`}
                  >
                    <span
                      className={`block truncate font-mono text-[10px] ${
                        selected
                          ? "font-semibold text-amber-400"
                          : "text-zinc-300"
                      }`}
                    >
                      {truncate(sessionTitle(session), 36)}
                    </span>
                    <span className="mt-0.5 block font-mono text-[9px] text-zinc-500">
                      {timeAgo(session.updated_at)}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </aside>
  );
}
