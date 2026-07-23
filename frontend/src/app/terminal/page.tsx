"use client";

import { Suspense, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import QuoteStrip from "@/components/QuoteStrip";
import ResizableSplit from "@/components/ResizableSplit";
import SignalDetail from "@/components/SignalDetail";
import SignalFeed from "@/components/SignalFeed";
import TerminalAuthGate from "@/components/TerminalAuthGate";
import TerminalHeader from "@/components/TerminalHeader";
import { terminalPath } from "@/lib/terminalNav";

function TerminalPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const selectedSignalId = searchParams.get("signal");

  const handleSelectSignal = useCallback(
    (idStr: string) => {
      router.push(terminalPath(idStr));
    },
    [router],
  );

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden">
      <TerminalHeader />
      <QuoteStrip />
      <ResizableSplit
        minFirst={320}
        minSecond={320}
        defaultSecond={480}
        first={
          <SignalFeed
            selectedId={selectedSignalId}
            onSelectSignal={handleSelectSignal}
          />
        }
        second={<SignalDetail idStr={selectedSignalId} />}
      />
    </div>
  );
}

export default function TerminalPage() {
  return (
    <TerminalAuthGate>
      <Suspense
        fallback={
          <div className="flex h-[100dvh] items-center justify-center bg-zinc-950 font-mono text-xs text-zinc-500">
            Loading…
          </div>
        }
      >
        <TerminalPageContent />
      </Suspense>
    </TerminalAuthGate>
  );
}
