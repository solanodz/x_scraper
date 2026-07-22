"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { isSupabaseConfigured } from "@/lib/supabase/env";
import { createClient } from "@/lib/supabase/client";

export default function LandingPage() {
  const [sessionLabel, setSessionLabel] = useState<string | null>(null);

  useEffect(() => {
    if (!isSupabaseConfigured()) return;
    let cancelled = false;
    const supabase = createClient();
    supabase.auth.getSession().then(({ data }) => {
      if (cancelled) return;
      const email = data.session?.user?.email;
      if (email) setSessionLabel(email.split("@")[0] ?? "ops");
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const ctaHref = sessionLabel ? "/terminal" : "/login";
  const ctaLabel = sessionLabel ? `Continuar · @${sessionLabel}` : "Entrar";

  return (
    <div className="flex min-h-[100dvh] flex-col items-center justify-center bg-zinc-950 px-6 text-zinc-100">
      <p className="font-mono text-sm text-amber-500">▮ x scraper terminal</p>
      <h1 className="mt-4 max-w-xl text-center font-sans text-3xl font-semibold tracking-tight sm:text-4xl">
        Inteligencia financiera sobre el Corpus de X
      </h1>
      <p className="mt-4 max-w-lg text-center font-sans text-base text-zinc-400">
        Signal Feed, Research Chat, Dossier y Chart Plan en un solo workspace.
      </p>
      <Link
        href={ctaHref}
        className="mt-8 inline-flex rounded-full bg-zinc-100 px-8 py-3.5 font-sans text-sm font-medium text-zinc-950 transition-transform hover:scale-[1.02] hover:bg-white active:scale-[0.98]"
      >
        {ctaLabel}
      </Link>
    </div>
  );
}
