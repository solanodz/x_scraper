"use client";

import type { ResearchStep } from "@/lib/types";

interface ResearchStepLoaderProps {
  steps: ResearchStep[];
  active: boolean;
}

function currentLabel(steps: ResearchStep[]): string {
  if (steps.length === 0) return "Iniciando research…";
  const running = [...steps].reverse().find((s) => s.status === "running");
  if (running) return running.label;
  return steps[steps.length - 1]?.label ?? "Iniciando research…";
}

export default function ResearchStepLoader({
  steps,
  active,
}: ResearchStepLoaderProps) {
  // Transient status only — never linger in chat history after the answer lands.
  if (!active) return null;

  return (
    <p
      className="font-mono text-[11px] text-zinc-500"
      aria-live="polite"
      aria-busy="true"
    >
      <span className="inline-block animate-pulse">{currentLabel(steps)}</span>
    </p>
  );
}
