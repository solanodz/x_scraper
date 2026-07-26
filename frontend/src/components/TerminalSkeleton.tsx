"use client";

import type { CSSProperties } from "react";

/** Skeletons mono/terminal (zinc pulse). Sin cards redondeadas. */

function Bone({
  className = "",
  style,
}: {
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <div
      className={`animate-pulse bg-zinc-800/80 ${className}`}
      style={style}
      aria-hidden
    />
  );
}

export function FeedRowSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="space-y-0" role="status" aria-label="Cargando Signal Feed">
      {Array.from({ length: rows }, (_, i) => (
        <div
          key={i}
          className="border-b border-zinc-800/80 px-3 py-2.5"
        >
          <div className="mb-1.5 flex items-center gap-2">
            <Bone className="h-2.5 w-14" />
            <Bone className="h-2 w-10" />
            <Bone className="ml-auto h-2 w-8" />
          </div>
          <Bone className="mb-1 h-2.5 w-[92%]" />
          <Bone
            className="h-2.5"
            style={{ width: `${55 + ((i * 17) % 35)}%` }}
          />
        </div>
      ))}
    </div>
  );
}

export function ChartPaneSkeleton({
  className = "h-64",
}: {
  className?: string;
}) {
  return (
    <div
      className={`flex flex-col justify-end border border-zinc-800 bg-zinc-950/60 p-3 ${className}`}
      role="status"
      aria-label="Cargando gráfico"
    >
      <div className="flex h-full items-end gap-1">
        {Array.from({ length: 24 }, (_, i) => (
          <Bone
            key={i}
            className="min-w-0 flex-1"
            style={{ height: `${28 + ((i * 37) % 60)}%` }}
          />
        ))}
      </div>
      <div className="mt-3 flex gap-2">
        <Bone className="h-2 w-16" />
        <Bone className="h-2 w-10" />
      </div>
    </div>
  );
}

export function DossierBlockSkeleton({ blocks = 3 }: { blocks?: number }) {
  return (
    <div className="space-y-4" role="status" aria-label="Cargando Dossier">
      {Array.from({ length: blocks }, (_, i) => (
        <div
          key={i}
          className="space-y-2 border border-zinc-800/80 bg-zinc-950/40 p-4"
        >
          <Bone className="h-2.5 w-28" />
          <Bone className="h-2 w-full" />
          <Bone className="h-2 w-[88%]" />
          <Bone className="h-2 w-[70%]" />
        </div>
      ))}
    </div>
  );
}

export function SessionListSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-0 py-1" role="status" aria-label="Cargando sesiones">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="border-l-2 border-transparent px-3 py-2">
          <Bone className="mb-1 h-2.5 w-[70%]" />
          <Bone className="h-2 w-12" />
        </div>
      ))}
    </div>
  );
}

export function ChatHistorySkeleton() {
  return (
    <div
      className="mx-auto w-full max-w-3xl space-y-3 px-4 py-6"
      role="status"
      aria-label="Cargando mensajes"
    >
      <div className="ml-auto max-w-[55%] space-y-1.5 bg-zinc-800/60 px-4 py-3">
        <Bone className="h-2.5 w-full bg-zinc-700/80" />
        <Bone className="h-2.5 w-[66%] bg-zinc-700/80" />
      </div>
      <div className="mr-auto max-w-[75%] space-y-2 border border-zinc-800/80 px-4 py-3">
        <Bone className="h-2 w-16" />
        <Bone className="h-2.5 w-full" />
        <Bone className="h-2.5 w-[90%]" />
        <Bone className="h-2.5 w-[60%]" />
      </div>
      <div className="ml-auto max-w-[40%] space-y-1.5 bg-zinc-800/60 px-4 py-3">
        <Bone className="h-2.5 w-full bg-zinc-700/80" />
      </div>
    </div>
  );
}

export function QuoteStripSkeleton() {
  return (
    <div
      className="flex items-center gap-6 overflow-hidden"
      role="status"
      aria-label="Cargando cotizaciones"
    >
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className="flex shrink-0 items-center gap-2">
          <Bone className="h-3 w-3" />
          <Bone className="h-2.5 w-10" />
          <Bone className="h-2.5 w-14" />
          <Bone className="h-2.5 w-10" />
        </div>
      ))}
    </div>
  );
}

export function DetailSkeleton() {
  return (
    <div className="space-y-3 p-4" role="status" aria-label="Cargando detalle">
      <div className="flex items-center gap-2">
        <Bone className="h-3 w-20" />
        <Bone className="h-2 w-12" />
      </div>
      <Bone className="h-2.5 w-full" />
      <Bone className="h-2.5 w-[95%]" />
      <Bone className="h-2.5 w-[80%]" />
      <Bone className="mt-4 h-24 w-full" />
    </div>
  );
}
