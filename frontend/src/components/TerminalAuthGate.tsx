"use client";

import { useEffect, useState, type ReactNode } from "react";
import { getAccessToken, isSupabaseConfigured } from "@/lib/api";

export default function TerminalAuthGate({ children }: { children: ReactNode }) {
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

  return <>{children}</>;
}
