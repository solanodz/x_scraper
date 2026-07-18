"use client";

import type { ResearchStep } from "@/lib/types";

interface ResearchStepLoaderProps {
  steps: ResearchStep[];
  active: boolean;
}

function stepKey(step: ResearchStep, index: number): string {
  return `${step.tool}-${step.label}-${index}`;
}

export default function ResearchStepLoader({
  steps,
  active,
}: ResearchStepLoaderProps) {
  if (steps.length === 0 && !active) return null;

  const visible = steps.length > 0 ? steps : active
    ? [{ tool: "agent", label: "Iniciando research…", status: "running" as const }]
    : [];

  return (
    <div className="space-y-1.5 rounded border border-zinc-800 bg-zinc-950/80 px-3 py-2">
      <p className="font-sans text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
        Research
      </p>
      <ul className="space-y-1">
        {visible.map((step, index) => {
          const isRunning = step.status === "running";
          const showPulse = isRunning && active;

          return (
            <li
              key={stepKey(step, index)}
              className="flex items-start gap-2 font-mono text-[11px]"
            >
              <span
                className={`mt-0.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full ${
                  step.status === "done"
                    ? "bg-emerald-500"
                    : showPulse
                      ? "animate-pulse bg-amber-400"
                      : "bg-zinc-600"
                }`}
                aria-hidden
              />
              <span
                className={
                  step.status === "done"
                    ? "text-zinc-500"
                    : showPulse
                      ? "text-amber-300/90"
                      : "text-zinc-400"
                }
              >
                {step.label}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
