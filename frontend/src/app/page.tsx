"use client";

import { useEffect, useState } from "react";
import QuoteStrip from "@/components/QuoteStrip";
import ResearchChat from "@/components/ResearchChat";
import ResizableSplit from "@/components/ResizableSplit";
import SignalDetail from "@/components/SignalDetail";
import SignalFeed from "@/components/SignalFeed";
import TerminalHeader from "@/components/TerminalHeader";
import { getAccessToken, isSupabaseConfigured } from "@/lib/api";

export default function TerminalPage() {
  const [selectedSignalId, setSelectedSignalId] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(!isSupabaseConfigured());
  const [authFailed, setAuthFailed] = useState(false);

  useEffect(() => {
    if (!isSupabaseConfigured()) return;
    let cancelled = false;
    getAccessToken().then((token) => {
      if (cancelled) return;
      if (token) {
        setAuthReady(true);
        setAuthFailed(false);
      } else {
        setAuthFailed(true);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (authFailed) {
    return (
      <div className="flex h-full items-center justify-center font-mono text-xs text-zinc-400">
        Session expired.{" "}
        <a href="/login" className="ml-1 text-amber-500 hover:underline">
          Sign in again
        </a>
      </div>
    );
  }

  if (!authReady) {
    return (
      <div className="flex h-full items-center justify-center font-mono text-xs text-zinc-500">
        Loading session…
      </div>
    );
  }

  return (
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
                onSelectSignal={setSelectedSignalId}
              />
            }
            second={<SignalDetail idStr={selectedSignalId} />}
          />
        }
        second={<ResearchChat onCitationClick={setSelectedSignalId} />}
      />
    </div>
  );
}
