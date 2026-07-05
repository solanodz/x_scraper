"use client";

import { useEffect, useRef, useState } from "react";
import { timeAgo, truncate } from "@/lib/format";
import type { ChatSessionSummary } from "@/lib/types";

interface ChatSessionSelectProps {
  sessions: ChatSessionSummary[];
  activeSessionId: string | null;
  onSelect: (sessionId: string) => void;
  disabled?: boolean;
  loading?: boolean;
}

function sessionTitle(session: ChatSessionSummary): string {
  return session.title?.trim() || "Sin título";
}

export default function ChatSessionSelect({
  sessions,
  activeSessionId,
  onSelect,
  disabled = false,
  loading = false,
}: ChatSessionSelectProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const active = sessions.find((s) => s.id === activeSessionId);

  useEffect(() => {
    if (!open) return;

    function handlePointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  const isDisabled = disabled || loading || sessions.length === 0;

  return (
    <div ref={rootRef} className="relative min-w-0 flex-1">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        disabled={isDisabled}
        aria-expanded={open}
        aria-haspopup="listbox"
        className="flex w-full items-center justify-between gap-2 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-left transition-colors hover:border-zinc-600 focus:border-amber-600 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
      >
        <span className="min-w-0 flex-1">
          {loading ? (
            <span className="font-mono text-[10px] text-zinc-500">
              Cargando sesiones…
            </span>
          ) : active ? (
            <>
              <span className="block truncate font-mono text-[10px] text-zinc-200">
                {truncate(sessionTitle(active), 52)}
              </span>
              <span className="block font-mono text-[9px] text-zinc-500">
                {timeAgo(active.updated_at)}
              </span>
            </>
          ) : (
            <span className="font-mono text-[10px] text-zinc-500">
              Sin sesión activa
            </span>
          )}
        </span>
        <span
          className={`shrink-0 font-mono text-[10px] text-zinc-500 transition-transform ${open ? "rotate-180 text-amber-500" : ""}`}
          aria-hidden
        >
          ▾
        </span>
      </button>

      {open && !isDisabled && (
        <ul
          role="listbox"
          className="absolute left-0 right-0 top-[calc(100%+4px)] z-20 max-h-44 overflow-y-auto rounded border border-zinc-700 bg-zinc-950 py-1 shadow-lg shadow-black/40"
        >
          {sessions.map((session) => {
            const selected = session.id === activeSessionId;
            return (
              <li key={session.id} role="option" aria-selected={selected}>
                <button
                  type="button"
                  onClick={() => {
                    onSelect(session.id);
                    setOpen(false);
                  }}
                  className={`w-full border-b border-zinc-800/60 px-2 py-1.5 text-left transition-colors last:border-b-0 hover:bg-zinc-800/50 ${
                    selected ? "bg-zinc-800/80" : ""
                  }`}
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <span
                      className={`min-w-0 truncate font-mono text-[10px] ${
                        selected ? "font-semibold text-amber-400" : "text-zinc-300"
                      }`}
                    >
                      {truncate(sessionTitle(session), 48)}
                    </span>
                    {selected && (
                      <span className="shrink-0 font-mono text-[9px] uppercase text-amber-600">
                        activa
                      </span>
                    )}
                  </div>
                  <span className="font-mono text-[9px] text-zinc-500">
                    {timeAgo(session.updated_at)}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
