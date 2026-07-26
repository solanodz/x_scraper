"use client";

import type { Provenance } from "@/lib/types";
import { formatProvenanceLabel } from "@/lib/provenance";

interface ProvenanceChipProps {
  provenance: Provenance | null | undefined;
  className?: string;
}

/** Chip neutro (zinc) para hechos no-Signal. No reemplaza Citations. */
export default function ProvenanceChip({
  provenance,
  className = "",
}: ProvenanceChipProps) {
  const label = formatProvenanceLabel(provenance);
  if (!label) return null;
  return (
    <span
      className={`inline-flex max-w-full border border-zinc-700 bg-zinc-950 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wide text-zinc-500 ${className}`}
      title={label}
    >
      <span className="truncate">{label}</span>
    </span>
  );
}

interface ProvenanceListProps {
  items: Provenance[] | null | undefined;
  className?: string;
}

export function ProvenanceList({ items, className = "" }: ProvenanceListProps) {
  if (!items || items.length === 0) return null;
  return (
    <div className={`flex flex-wrap gap-1.5 ${className}`}>
      {items.map((prov, i) => (
        <ProvenanceChip
          key={`${prov.kind}-${prov.source}-${i}`}
          provenance={prov}
        />
      ))}
    </div>
  );
}
