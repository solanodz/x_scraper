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
}: SignalFeedFiltersProps) {
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
          className="rounded border border-zinc-700 px-2 py-1 font-mono text-[10px] text-zinc-400 hover:border-amber-600 hover:text-amber-400"
        >
          Buscar
        </button>
        {hasActive && (
          <button
            type="button"
            onClick={onClear}
            className="rounded border border-zinc-700 px-2 py-1 font-mono text-[10px] text-zinc-500 hover:text-zinc-300"
          >
            Limpiar
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2">
        <label className="flex min-w-0 flex-col gap-1">
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

        <label className="flex min-w-0 flex-col gap-1">
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
      </div>
    </div>
  );
}

export { EMPTY_FEED_FILTERS };
