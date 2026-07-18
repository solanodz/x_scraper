"use client";

import { useCallback, useState } from "react";
import QuoteStrip from "@/components/QuoteStrip";
import ResearchChat from "@/components/ResearchChat";
import ResizableSplit from "@/components/ResizableSplit";
import SignalDetail from "@/components/SignalDetail";
import SignalFeed from "@/components/SignalFeed";
import TerminalAuthGate from "@/components/TerminalAuthGate";
import TerminalHeader from "@/components/TerminalHeader";

export default function TerminalPage() {
  const [selectedSignalId, setSelectedSignalId] = useState<string | null>(null);

  const handleSelectSignal = useCallback((idStr: string) => {
    setSelectedSignalId(idStr);
  }, []);

  return (
    <TerminalAuthGate>
      <div className="flex h-full flex-col">
        <TerminalHeader />
        <QuoteStrip />
        <ResizableSplit
          minFirst={360}
          minSecond={300}
          defaultSecond={420}
          first={
            <ResizableSplit
              orientation="vertical"
              minFirst={180}
              minSecond={200}
              defaultSecond={280}
              first={
                <SignalFeed
                  selectedId={selectedSignalId}
                  onSelectSignal={handleSelectSignal}
                />
              }
              second={<SignalDetail idStr={selectedSignalId} />}
            />
          }
          second={<ResearchChat onCitationClick={handleSelectSignal} />}
        />
      </div>
    </TerminalAuthGate>
  );
}
