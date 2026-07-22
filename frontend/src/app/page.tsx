"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { GradientBarHeroSection } from "@/components/ui/gradient-bar-hero-section";
import TerminalMockup from "@/components/landing/TerminalMockup";
import FeaturesBento from "@/components/landing/FeaturesBento";
import { isSupabaseConfigured } from "@/lib/supabase/env";
import { createClient } from "@/lib/supabase/client";

const STEPS = [
  {
    title: "Entrá",
    body: "Con tu cuenta de operator. No hay signup público: el acceso es por invitación.",
  },
  {
    title: "Observá",
    body: "El Feed corre en vivo y el Research Chat queda al lado. Agregá tickers al Watch.",
  },
  {
    title: "Investigá",
    body: "Abrí un Dossier por ticker o pedí un Chart Plan sobre la vista que vos controlás.",
  },
] as const;

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
    <div className="min-h-[100dvh] overflow-y-auto bg-zinc-950 text-zinc-100">
      {/* Hero con mockup de la terminal asomándose al fold */}
      <GradientBarHeroSection ctaHref={ctaHref} ctaLabel={ctaLabel}>
        <TerminalMockup />
      </GradientBarHeroSection>

      <main className="relative z-10 bg-zinc-950">
        {/* Qué es */}
        <section id="que-es" className="scroll-mt-24 py-24 sm:py-32">
          <div className="mx-auto max-w-3xl px-6 text-center sm:px-8">
            <h2 className="font-sans text-2xl font-semibold leading-snug tracking-tight text-zinc-100 sm:text-3xl">
              Todo lo que se dice del mercado, en un solo workspace
            </h2>
            <p className="mx-auto mt-6 max-w-2xl font-sans text-base leading-relaxed text-zinc-400">
              X Scraper Terminal junta lo que se dice en X y en noticias, lo
              indexa en un Corpus, y te deja investigarlo. Cada afirmación
              viene con su fuente.
            </p>
          </div>
        </section>

        {/* Features Bento */}
        <FeaturesBento />

        {/* Cómo se usa */}
        <section id="como" className="scroll-mt-24 py-24 sm:py-32">
          <div className="mx-auto max-w-3xl px-6 sm:px-8">
            <h2 className="font-sans text-xl font-semibold tracking-tight text-zinc-100 sm:text-2xl">
              Cómo se usa
            </h2>
            <div className="mt-12 space-y-0">
              {STEPS.map((step, index) => (
                <div
                  key={step.title}
                  className={`grid grid-cols-[1fr] gap-2 py-8 sm:grid-cols-[10rem_1fr] sm:gap-8 ${
                    index > 0 ? "border-t border-zinc-800/80" : ""
                  }`}
                >
                  <p className="font-sans text-base font-medium text-zinc-100">
                    {step.title}
                  </p>
                  <p className="font-sans text-sm leading-relaxed text-zinc-400 sm:text-base">
                    {step.body}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Cierre */}
        <section className="py-24 sm:py-32">
          <div className="mx-auto max-w-3xl px-6 text-center sm:px-8">
            <p className="font-sans text-2xl font-medium tracking-tight text-zinc-100 sm:text-3xl">
              Empezá por un ticker o una pregunta.
            </p>
            <div className="mt-8">
              <Link
                href={ctaHref}
                className="inline-flex rounded-full bg-zinc-100 px-8 py-3.5 font-sans text-sm font-medium text-zinc-950 transition-transform hover:scale-[1.02] hover:bg-white active:scale-[0.98] md:text-base"
              >
                {ctaLabel}
              </Link>
            </div>
            <p className="mt-6 font-mono text-xs text-zinc-600">
              Acceso por invitación · market data con ~15 min de delay
            </p>
          </div>
        </section>
      </main>

      <footer className="border-t border-zinc-900">
        <div className="mx-auto flex max-w-5xl flex-col gap-2 px-6 py-8 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <p className="font-mono text-[11px] text-zinc-700">
            ▮ x scraper terminal · personal research workspace
          </p>
          <p className="font-mono text-[11px] text-zinc-700">
            Corpus + pgvector + OpenAI
          </p>
        </div>
      </footer>
    </div>
  );
}
