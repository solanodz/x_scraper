"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  addTickerWatch,
  fetchTickerSuggestions,
  fetchTickerWatch,
  removeTickerWatch,
  updateTickerWatchThesis,
} from "@/lib/api";
import type { TickerSuggestion, TickerWatchEntry } from "@/lib/types";

export default function TickerWatchPopover() {
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [entries, setEntries] = useState<TickerWatchEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [suggestions, setSuggestions] = useState<TickerSuggestion[]>([]);
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);
  const [expandedSymbol, setExpandedSymbol] = useState<string | null>(null);
  const [thesisDraft, setThesisDraft] = useState("");
  const [savingThesis, setSavingThesis] = useState<string | null>(null);

  const prefix = input.replace(/^\$/, "").trim().toUpperCase();

  const loadWatchlist = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchTickerWatch();
      setEntries(data);
    } catch {
      setError("Failed to load watchlist");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) loadWatchlist();
  }, [open, loadWatchlist]);

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

  useEffect(() => {
    if (!open || !input.trim()) {
      setSuggestionsOpen(false);
      setSuggestions([]);
      return;
    }

    setSuggestionsOpen(true);
    setHighlight(0);
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setSuggestionsLoading(true);
      try {
        const data = await fetchTickerSuggestions(prefix, 50);
        if (!controller.signal.aborted) setSuggestions(data);
      } catch {
        if (!controller.signal.aborted) setSuggestions([]);
      } finally {
        if (!controller.signal.aborted) setSuggestionsLoading(false);
      }
    }, prefix.length === 0 ? 0 : 180);

    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [prefix, open, input]);

  async function handleAdd(symbol: string) {
    const cleaned = symbol.replace(/^\$/, "").trim();
    if (!cleaned || adding) return;
    setAdding(true);
    setError(null);
    try {
      await addTickerWatch(cleaned);
      setInput("");
      setSuggestionsOpen(false);
      await loadWatchlist();
    } catch {
      setError("Failed to add ticker");
    } finally {
      setAdding(false);
    }
  }

  async function handleRemove(symbol: string) {
    if (removing) return;
    setRemoving(symbol);
    setError(null);
    try {
      await removeTickerWatch(symbol);
      if (expandedSymbol === symbol) {
        setExpandedSymbol(null);
        setThesisDraft("");
      }
      await loadWatchlist();
    } catch {
      setError("Failed to remove ticker");
    } finally {
      setRemoving(null);
    }
  }

  function toggleThesisEditor(entry: TickerWatchEntry) {
    if (expandedSymbol === entry.symbol) {
      setExpandedSymbol(null);
      setThesisDraft("");
      return;
    }
    setExpandedSymbol(entry.symbol);
    setThesisDraft(entry.note ?? "");
  }

  async function saveThesis(symbol: string) {
    if (savingThesis) return;
    const entry = entries.find((row) => row.symbol === symbol);
    const current = entry?.note ?? "";
    const next = thesisDraft.trim();
    if (next === current.trim()) {
      setExpandedSymbol(null);
      setThesisDraft("");
      return;
    }

    setSavingThesis(symbol);
    setError(null);
    try {
      const updated = await updateTickerWatchThesis(
        symbol,
        next.length > 0 ? next : null,
      );
      setEntries((prev) =>
        prev.map((row) => (row.symbol === symbol ? updated : row)),
      );
      setExpandedSymbol(null);
      setThesisDraft("");
    } catch {
      setError("Failed to save thesis");
    } finally {
      setSavingThesis(null);
    }
  }

  function selectSuggestion(symbol: string) {
    void handleAdd(symbol);
    inputRef.current?.focus();
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (suggestionsOpen && suggestions.length > 0) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setHighlight((prev) => (prev + 1) % suggestions.length);
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        setHighlight(
          (prev) => (prev - 1 + suggestions.length) % suggestions.length,
        );
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        setSuggestionsOpen(false);
        return;
      }
      if (event.key === "Enter") {
        event.preventDefault();
        const picked = suggestions[highlight];
        if (picked) selectSuggestion(picked.symbol);
        else if (prefix) void handleAdd(prefix);
        return;
      }
      if (event.key === "Tab" && suggestions[highlight]) {
        event.preventDefault();
        selectSuggestion(suggestions[highlight].symbol);
        return;
      }
    } else if (event.key === "Enter" && prefix) {
      event.preventDefault();
      void handleAdd(prefix);
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
        aria-haspopup="dialog"
        className={`rounded border px-3 py-1 font-sans text-xs transition-colors ${
          open
            ? "border-amber-600 bg-zinc-900 text-amber-400"
            : "border-zinc-700 bg-zinc-900 text-zinc-300 hover:border-amber-600 hover:text-amber-400"
        }`}
      >
        Watch
      </button>

      {open && (
        <div className="absolute right-0 top-[calc(100%+4px)] z-40 w-72 rounded border border-zinc-700 bg-zinc-900 shadow-lg shadow-black/40">
          <div className="border-b border-zinc-800 px-3 py-2">
            <span className="font-mono text-[10px] uppercase tracking-wide text-amber-500">
              Ticker Watch
            </span>
          </div>

          <div className="max-h-48 overflow-y-auto">
            {loading && entries.length === 0 && (
              <p className="px-3 py-2 font-mono text-[10px] text-zinc-500">
                Loading…
              </p>
            )}

            {!loading && entries.length === 0 && (
              <p className="px-3 py-2 font-mono text-[10px] text-zinc-500">
                No tickers watched
              </p>
            )}

            {entries.map((entry) => {
              const isExpanded = expandedSymbol === entry.symbol;
              const hasThesis = Boolean(entry.note?.trim());
              return (
                <div
                  key={entry.id}
                  className="border-b border-zinc-800/60 last:border-b-0"
                >
                  <div className="flex items-center justify-between gap-2 px-3 py-1.5">
                    <button
                      type="button"
                      onClick={() => toggleThesisEditor(entry)}
                      className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
                    >
                      <span className="font-mono text-[10px] font-semibold text-amber-400">
                        ${entry.symbol}
                      </span>
                      {hasThesis && (
                        <span
                          className="h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500"
                          aria-label="Thesis saved"
                        />
                      )}
                    </button>
                    <div className="flex shrink-0 items-center gap-1">
                      <button
                        type="button"
                        onClick={() => toggleThesisEditor(entry)}
                        aria-label={`Edit thesis for ${entry.symbol}`}
                        className="font-mono text-[10px] text-zinc-500 transition-colors hover:text-amber-400"
                      >
                        ✎
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleRemove(entry.symbol)}
                        disabled={removing === entry.symbol}
                        aria-label={`Remove ${entry.symbol}`}
                        className="font-mono text-xs text-zinc-500 transition-colors hover:text-red-400 disabled:opacity-50"
                      >
                        ×
                      </button>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="space-y-1 border-t border-zinc-800/60 px-3 py-2">
                      <label className="font-mono text-[9px] uppercase tracking-wide text-zinc-500">
                        Mi tesis
                      </label>
                      <textarea
                        value={thesisDraft}
                        onChange={(e) => setThesisDraft(e.target.value)}
                        onBlur={() => void saveThesis(entry.symbol)}
                        maxLength={280}
                        rows={3}
                        placeholder="¿Por qué sigo este ticker? ¿Qué riesgo me preocupa?"
                        disabled={savingThesis === entry.symbol}
                        className="w-full resize-none rounded border border-zinc-700 bg-zinc-950 px-2 py-1 font-mono text-[10px] text-zinc-300 placeholder:text-zinc-600 focus:border-amber-600 focus:outline-none disabled:opacity-50"
                      />
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-[9px] text-zinc-600">
                          {thesisDraft.length}/280
                        </span>
                        <button
                          type="button"
                          onClick={() => void saveThesis(entry.symbol)}
                          disabled={savingThesis === entry.symbol}
                          className="rounded border border-amber-800/60 px-1.5 py-0.5 font-mono text-[10px] text-amber-400 transition-colors hover:border-amber-600 hover:text-amber-300 disabled:opacity-50"
                        >
                          ✓
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {error && (
            <p className="border-t border-zinc-800 px-3 py-1.5 font-mono text-[10px] text-red-400">
              {error}
            </p>
          )}

          {entries.length > 0 && (
            <div className="border-t border-zinc-800 px-2 py-1.5">
              <button
                type="button"
                onClick={() => {
                  setOpen(false);
                  window.dispatchEvent(new CustomEvent("xscraper:briefing"));
                }}
                className="w-full rounded border border-amber-800/60 bg-amber-950/30 px-2 py-1 font-mono text-xs text-amber-400 transition-colors hover:border-amber-600 hover:text-amber-300"
              >
                Briefing
              </button>
            </div>
          )}

          <div className="relative border-t border-zinc-800 p-2">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => {
                if (input.trim()) setSuggestionsOpen(true);
              }}
              placeholder="Add $ticker…"
              disabled={adding}
              autoComplete="off"
              spellCheck={false}
              aria-expanded={suggestionsOpen}
              aria-autocomplete="list"
              role="combobox"
              className="w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1 font-mono text-[10px] text-zinc-300 placeholder:text-zinc-600 focus:border-amber-600 focus:outline-none disabled:opacity-50"
            />

            {suggestionsOpen && (
              <ul
                role="listbox"
                className="absolute bottom-[calc(100%+4px)] left-2 right-2 max-h-40 overflow-y-auto rounded border border-zinc-700 bg-zinc-950 py-1 shadow-lg shadow-black/40"
              >
                {suggestionsLoading && suggestions.length === 0 && (
                  <li className="px-2 py-1.5 font-mono text-[10px] text-zinc-500">
                    Searching…
                  </li>
                )}

                {!suggestionsLoading && suggestions.length === 0 && (
                  <li className="px-2 py-1.5 font-mono text-[10px] text-zinc-500">
                    No matches — press Enter to add
                  </li>
                )}

                {suggestions.map((item, index) => {
                  const selected = index === highlight;
                  return (
                    <li
                      key={`${item.symbol}-${item.source}`}
                      role="option"
                      aria-selected={selected}
                    >
                      <button
                        type="button"
                        onMouseEnter={() => setHighlight(index)}
                        onClick={() => selectSuggestion(item.symbol)}
                        className={`flex w-full items-center justify-between gap-2 border-b border-zinc-800/60 px-2 py-1.5 text-left transition-colors last:border-b-0 hover:bg-zinc-800/50 ${
                          selected ? "bg-zinc-800/80" : ""
                        }`}
                      >
                        <span
                          className={`font-mono text-[10px] ${
                            selected
                              ? "font-semibold text-amber-400"
                              : "text-zinc-200"
                          }`}
                        >
                          ${item.symbol}
                        </span>
                        <span className="min-w-0 truncate font-mono text-[9px] text-zinc-500">
                          {item.description || item.source}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
