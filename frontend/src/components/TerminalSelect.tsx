"use client";

import { useEffect, useRef, useState } from "react";

export interface TerminalSelectOption<T extends string | number> {
  value: T;
  label: string;
}

interface TerminalSelectProps<T extends string | number> {
  value: T;
  options: TerminalSelectOption<T>[];
  onChange: (value: T) => void;
  disabled?: boolean;
  className?: string;
}

export default function TerminalSelect<T extends string | number>({
  value,
  options,
  onChange,
  disabled = false,
  className = "",
}: TerminalSelectProps<T>) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const active = options.find((option) => option.value === value);

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

  return (
    <div ref={rootRef} className={`relative min-w-0 ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        disabled={disabled}
        aria-expanded={open}
        aria-haspopup="listbox"
        className="flex w-full items-center justify-between gap-2 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-left transition-colors hover:border-zinc-600 focus:border-amber-600 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
      >
        <span className="min-w-0 truncate font-mono text-[10px] text-zinc-300">
          {active?.label ?? "—"}
        </span>
        <span
          className={`shrink-0 font-mono text-[10px] text-zinc-500 transition-transform ${open ? "rotate-180 text-amber-500" : ""}`}
          aria-hidden
        >
          ▾
        </span>
      </button>

      {open && !disabled && (
        <ul
          role="listbox"
          className="absolute left-0 right-0 top-[calc(100%+4px)] z-30 max-h-40 overflow-y-auto rounded border border-zinc-700 bg-zinc-950 py-1 shadow-lg shadow-black/40"
        >
          {options.map((option) => {
            const selected = option.value === value;
            return (
              <li
                key={String(option.value)}
                role="option"
                aria-selected={selected}
              >
                <button
                  type="button"
                  onClick={() => {
                    onChange(option.value);
                    setOpen(false);
                  }}
                  className={`flex w-full items-center justify-between gap-2 border-b border-zinc-800/60 px-2 py-1.5 text-left transition-colors last:border-b-0 hover:bg-zinc-800/50 ${
                    selected ? "bg-zinc-800/80" : ""
                  }`}
                >
                  <span
                    className={`min-w-0 truncate font-mono text-[10px] ${
                      selected
                        ? "font-semibold text-amber-400"
                        : "text-zinc-300"
                    }`}
                  >
                    {option.label}
                  </span>
                  {selected && (
                    <span className="shrink-0 font-mono text-[9px] uppercase text-amber-600">
                      ✓
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
