"use client";

import { useEffect, useRef, useState } from "react";
import { fetchTickerSuggestions } from "@/lib/api";
import {
  activeTickerPrefix,
  replaceActiveTicker,
} from "@/lib/feedFilters";
import type { TickerSuggestion } from "@/lib/types";

interface FeedSearchInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  className?: string;
}

const inputClass =
  "min-w-0 flex-1 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 font-mono text-[10px] text-zinc-300 placeholder:text-zinc-600 focus:border-amber-600 focus:outline-none";

export default function FeedSearchInput({
  value,
  onChange,
  onSubmit,
  className = "",
}: FeedSearchInputProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [suggestions, setSuggestions] = useState<TickerSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [highlight, setHighlight] = useState(0);

  const tickerPrefix = activeTickerPrefix(value);

  useEffect(() => {
    if (tickerPrefix === null) {
      setOpen(false);
      setSuggestions([]);
      return;
    }

    setOpen(true);
    setHighlight(0);
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setLoading(true);
      try {
        const data = await fetchTickerSuggestions(tickerPrefix, 50);
        if (!controller.signal.aborted) {
          setSuggestions(data);
        }
      } catch {
        if (!controller.signal.aborted) setSuggestions([]);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, tickerPrefix.length === 0 ? 0 : 180);

    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [tickerPrefix]);

  useEffect(() => {
    if (!open) return;

    function handlePointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, [open]);

  function selectSuggestion(symbol: string) {
    onChange(replaceActiveTicker(value, symbol));
    setOpen(false);
    inputRef.current?.focus();
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || suggestions.length === 0) {
      if (event.key === "Enter") onSubmit();
      return;
    }

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
      setOpen(false);
      return;
    }

    if (event.key === "Enter") {
      event.preventDefault();
      const picked = suggestions[highlight];
      if (picked) selectSuggestion(picked.symbol);
      else onSubmit();
      return;
    }

    if (event.key === "Tab" && suggestions[highlight]) {
      event.preventDefault();
      selectSuggestion(suggestions[highlight].symbol);
    }
  }

  return (
    <div ref={rootRef} className={`relative min-w-0 flex-1 ${className}`}>
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        onFocus={() => {
          if (activeTickerPrefix(value) !== null) setOpen(true);
        }}
        placeholder="Palabras clave o $ticker (ej. $NVDA, Fed earnings…)"
        className={`${inputClass} w-full`}
        autoComplete="off"
        spellCheck={false}
        aria-expanded={open}
        aria-autocomplete="list"
        role="combobox"
      />

      {open && (
        <ul
          role="listbox"
          className="absolute left-0 right-0 top-[calc(100%+4px)] z-40 max-h-56 overflow-y-auto rounded border border-zinc-700 bg-zinc-950 py-1 shadow-lg shadow-black/40"
        >
          {loading && suggestions.length === 0 && (
            <li className="px-2 py-1.5 font-mono text-[10px] text-zinc-500">
              Buscando tickers…
            </li>
          )}

          {!loading && suggestions.length === 0 && (
            <li className="px-2 py-1.5 font-mono text-[10px] text-zinc-500">
              Sin tickers para este prefijo — seguí escribiendo
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
                      selected ? "font-semibold text-amber-400" : "text-zinc-200"
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
  );
}
