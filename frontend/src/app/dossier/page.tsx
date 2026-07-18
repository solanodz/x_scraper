"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import ChartPlanPanel from "@/components/ChartPlanPanel";
import DossierPanel from "@/components/DossierPanel";
import DossierWatchSidebar from "@/components/DossierWatchSidebar";
import QuoteStrip from "@/components/QuoteStrip";
import ResizableSplit from "@/components/ResizableSplit";
import TerminalAuthGate from "@/components/TerminalAuthGate";
import TerminalHeader from "@/components/TerminalHeader";
import { fetchTickerWatch } from "@/lib/api";
import { dossierPath } from "@/lib/dossierNav";

function DossierPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const symbol = searchParams.get("symbol")?.trim().toUpperCase() ?? null;

  useEffect(() => {
    if (symbol) return;
    let cancelled = false;
    fetchTickerWatch()
      .then((entries) => {
        if (cancelled || entries.length === 0) return;
        router.replace(dossierPath(entries[0].symbol));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [symbol, router]);

  return (
    <div className="flex h-full flex-col">
      <TerminalHeader />
      <QuoteStrip />
      <div className="flex min-h-0 flex-1">
        <DossierWatchSidebar />
        <main className="flex h-full min-h-0 min-w-0 flex-1">
          {symbol ? (
            <ResizableSplit
              className="h-full w-full"
              minFirst={320}
              minSecond={320}
              defaultSecond={480}
              first={<DossierPanel key={`dossier-${symbol}`} symbol={symbol} />}
              second={<ChartPlanPanel key={`chart-${symbol}`} symbol={symbol} />}
            />
          ) : (
            <div className="flex h-full items-center justify-center p-6">
              <p className="max-w-sm text-center font-mono text-xs text-zinc-500">
                Elegí un ticker del Watch o agregá símbolos desde el header para
                ver su Dossier.
              </p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default function DossierPage() {
  return (
    <TerminalAuthGate>
      <Suspense
        fallback={
          <div className="flex h-full items-center justify-center font-mono text-xs text-zinc-500">
            Loading…
          </div>
        }
      >
        <DossierPageContent />
      </Suspense>
    </TerminalAuthGate>
  );
}
