"use client";

import TerminalSelect from "@/components/TerminalSelect";
import FeedSearchInput from "@/components/FeedSearchInput";
import {
  EMPTY_FEED_FILTERS,
  FEED_SOURCE_OPTIONS,
  FEED_TIME_OPTIONS,
  type FeedFilterDraft,
} from "@/lib/feedFilters";

interface SignalFeedFiltersProps {
  draft: FeedFilterDraft;
  onDraftChange: (draft: FeedFilterDraft) => void;
  onApply: (draft?: FeedFilterDraft) => void;
  onClear: () => void;
  hasActive: boolean;
  watchCount: number | null;
}

function updateDraft(
  draft: FeedFilterDraft,
  patch: Partial<FeedFilterDraft>,
): FeedFilterDraft {
  return { ...draft, ...patch };
}

export default function SignalFeedFilters({
  draft,
  onDraftChange,
  onApply,
  onClear,
  hasActive,
  watchCount,
}: SignalFeedFiltersProps) {
  const watchLabel =
    watchCount == null
      ? "Mis tickers"
      : watchCount === 0
        ? "Mis tickers (0)"
        : `Mis tickers (${watchCount})`;

  return (
    <div className="space-y-1.5 border-b border-zinc-800/80 px-3 py-1.5">
      <div className="flex items-center gap-2">
        <FeedSearchInput
          value={draft.q}
          onChange={(q) => onDraftChange(updateDraft(draft, { q }))}
          onSubmit={() => onApply()}
        />
        <button
          type="button"
          onClick={() => onApply()}
          className="border border-zinc-700 px-2 py-1 font-mono text-[10px] text-zinc-400 hover:border-zinc-500 hover:text-zinc-300"
        >
          Buscar
        </button>
        {hasActive && (
          <button
            type="button"
            onClick={onClear}
            className="border border-zinc-700 px-2 py-1 font-mono text-[10px] text-zinc-500 hover:text-zinc-300"
          >
            Limpiar
          </button>
        )}
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <label className="flex min-w-0 flex-1 basis-[40%] flex-col gap-1">
          <span className="font-mono text-[9px] uppercase tracking-wide text-zinc-500">
            Fuente
          </span>
          <TerminalSelect
            value={draft.sourceType}
            options={FEED_SOURCE_OPTIONS}
            onChange={(sourceType) => {
              const next = updateDraft(draft, { sourceType });
              onDraftChange(next);
              onApply(next);
            }}
          />
        </label>

        <label className="flex min-w-0 flex-1 basis-[40%] flex-col gap-1">
          <span className="font-mono text-[9px] uppercase tracking-wide text-zinc-500">
            Período
          </span>
          <TerminalSelect
            value={draft.sinceHours}
            options={FEED_TIME_OPTIONS}
            onChange={(sinceHours) => {
              const next = updateDraft(draft, { sinceHours });
              onDraftChange(next);
              onApply(next);
            }}
          />
        </label>

        <button
          type="button"
          role="switch"
          aria-checked={draft.watchOnly}
          title="Filtrar Signal Feed por el Ticker Watch"
          onClick={() => {
            const next = updateDraft(draft, { watchOnly: !draft.watchOnly });
            onDraftChange(next);
            onApply(next);
          }}
          className={`shrink-0 border px-2 py-1 font-mono text-[10px] transition-colors ${
            draft.watchOnly
              ? "border-zinc-400 bg-zinc-800 text-zinc-100"
              : "border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-300"
          }`}
        >
          {watchLabel}
        </button>
      </div>
    </div>
  );
}

export { EMPTY_FEED_FILTERS };
