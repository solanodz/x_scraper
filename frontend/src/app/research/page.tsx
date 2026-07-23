"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import QuoteStrip from "@/components/QuoteStrip";
import ResearchChat from "@/components/ResearchChat";
import TerminalAuthGate from "@/components/TerminalAuthGate";
import TerminalHeader from "@/components/TerminalHeader";
import { terminalPath } from "@/lib/terminalNav";

export default function ResearchPage() {
  const router = useRouter();

  const handleCitationClick = useCallback(
    (idStr: string) => {
      router.push(terminalPath(idStr));
    },
    [router],
  );

  return (
    <TerminalAuthGate>
      <div className="flex h-[100dvh] flex-col overflow-hidden">
        <TerminalHeader />
        <QuoteStrip />
        <main className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <ResearchChat onCitationClick={handleCitationClick} />
        </main>
      </div>
    </TerminalAuthGate>
  );
}
