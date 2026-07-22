"use client";

import Link from "next/link";
import { useState } from "react";
import { Menu, X } from "lucide-react";

type GradientBarHeroSectionProps = {
  ctaHref?: string;
  ctaLabel?: string;
  children?: React.ReactNode;
};

const NAV_LINKS = [
  { href: "#que-es", label: "Qué es" },
  { href: "#superficies", label: "Superficies" },
  { href: "#como", label: "Cómo se usa" },
] as const;

const GradientBars = () => {
  const numBars = 15;

  const calculateHeight = (index: number, total: number) => {
    const position = index / (total - 1);
    const maxHeight = 100;
    const minHeight = 30;
    const center = 0.5;
    const distanceFromCenter = Math.abs(position - center);
    const heightPercentage = Math.pow(distanceFromCenter * 2, 1.2);
    return minHeight + (maxHeight - minHeight) * heightPercentage;
  };

  return (
    <div className="absolute inset-0 z-0 overflow-hidden" aria-hidden>
      <div
        className="flex h-full w-full"
        style={{
          transform: "translateZ(0)",
          backfaceVisibility: "hidden",
        }}
      >
        {Array.from({ length: numBars }).map((_, index) => {
          const height = calculateHeight(index, numBars);
          return (
            <div
              key={index}
              className="box-border"
              style={{
                flex: "1 0 calc(100% / 15)",
                maxWidth: "calc(100% / 15)",
                height: "100%",
                background:
                  "linear-gradient(to top, rgba(245, 158, 11, 0.6), rgba(245, 158, 11, 0.15) 55%, transparent)",
                transform: `scaleY(${height / 100})`,
                transformOrigin: "bottom",
              }}
            />
          );
        })}
      </div>

      <div className="absolute inset-0 bg-zinc-950/40" />

      <svg className="absolute h-0 w-0" aria-hidden>
        <filter id="hero-grain">
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.65"
            numOctaves="4"
            stitchTiles="stitch"
          />
          <feColorMatrix type="saturate" values="0" />
          <feGaussianBlur stdDeviation="0.6" />
        </filter>
      </svg>
      <div
        className="absolute inset-0"
        style={{
          filter: "url(#hero-grain)",
          opacity: 0.055,
          mixBlendMode: "soft-light",
          pointerEvents: "none",
        }}
      />
    </div>
  );
};

function Navbar({
  ctaHref,
  ctaLabel,
}: {
  ctaHref: string;
  ctaLabel: string;
}) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <nav className="relative z-50 px-6 pb-0 pt-6 md:px-12">
      <div className="mx-auto flex h-10 max-w-5xl items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <span className="font-mono text-sm text-amber-500" aria-hidden>
            ▮
          </span>
          <span className="font-sans text-sm font-semibold tracking-tight text-zinc-100">
            X Scraper Terminal
          </span>
        </Link>

        <div className="hidden items-center gap-7 md:flex">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="font-sans text-[13px] text-zinc-400 transition-colors hover:text-zinc-100"
            >
              {link.label}
            </a>
          ))}
          <Link
            href={ctaHref}
            className="rounded-full bg-zinc-100 px-4 py-1.5 font-sans text-[13px] font-medium text-zinc-950 transition-colors hover:bg-white"
          >
            {ctaLabel}
          </Link>
        </div>

        <button
          type="button"
          className="text-zinc-100 md:hidden"
          onClick={() => setIsMenuOpen((open) => !open)}
          aria-expanded={isMenuOpen}
          aria-label={isMenuOpen ? "Cerrar menú" : "Abrir menú"}
        >
          {isMenuOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>

      {isMenuOpen ? (
        <div className="mx-auto mt-3 max-w-5xl rounded-xl border border-zinc-800 bg-zinc-950/95 p-4 backdrop-blur-sm md:hidden">
          <div className="flex flex-col gap-1">
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="rounded-lg px-3 py-2.5 font-sans text-sm text-zinc-300 hover:bg-zinc-900"
                onClick={() => setIsMenuOpen(false)}
              >
                {link.label}
              </a>
            ))}
            <Link
              href={ctaHref}
              className="mt-2 rounded-full bg-zinc-100 px-4 py-2.5 text-center font-sans text-sm font-medium text-zinc-950"
              onClick={() => setIsMenuOpen(false)}
            >
              {ctaLabel}
            </Link>
          </div>
        </div>
      ) : null}
    </nav>
  );
}

export function GradientBarHeroSection({
  ctaHref = "/login",
  ctaLabel = "Entrar",
  children,
}: GradientBarHeroSectionProps) {
  return (
    <section className="relative overflow-hidden px-6 pb-16 sm:px-8 sm:pb-24 md:px-12">
      <div className="absolute inset-0 bg-zinc-950" />
      <GradientBars />
      <Navbar ctaHref={ctaHref} ctaLabel={ctaLabel} />

      <div className="relative z-10 mx-auto max-w-7xl pt-20 text-center sm:pt-28">
        <h1 className="mx-auto max-w-3xl animate-[landing-fadeIn_0.7s_ease-out_both] font-sans text-4xl font-semibold leading-[1.08] tracking-tight text-zinc-100 sm:text-5xl md:text-6xl">
          Inteligencia financiera
          <span className="block pb-1 font-normal italic leading-[1.15] text-zinc-400">
            desde el Corpus de X.
          </span>
        </h1>

        <p
          className="mx-auto mt-5 max-w-xl animate-[landing-fadeIn_0.7s_ease-out_both] font-sans text-base leading-relaxed text-zinc-400 sm:mt-6 md:text-lg"
          style={{ animationDelay: "120ms" }}
        >
          Signals en vivo, Research Chat con citas, Dossier por Ticker y Chart
          Plan. Fuentes reales, sin ruido.
        </p>

        <div
          className="mt-8 flex animate-[landing-fadeIn_0.7s_ease-out_both] flex-col items-center justify-center gap-3 sm:mt-10 sm:flex-row"
          style={{ animationDelay: "240ms" }}
        >
          <Link
            href={ctaHref}
            className="inline-flex rounded-full bg-zinc-100 px-7 py-3 font-sans text-sm font-medium text-zinc-950 transition-transform hover:scale-[1.02] hover:bg-white active:scale-[0.98]"
          >
            {ctaLabel}
          </Link>
          <a
            href="#que-es"
            className="inline-flex rounded-full border border-zinc-700 px-7 py-3 font-sans text-sm text-zinc-300 transition-colors hover:border-zinc-500 hover:text-zinc-100"
          >
            Saber más
          </a>
        </div>

        {/* Product mockup: pasa como children para que se asome al fold */}
        {children ? (
          <div
            className="mt-14 animate-[landing-fadeIn_0.8s_ease-out_both] sm:mt-20"
            style={{ animationDelay: "400ms" }}
          >
            {children}
          </div>
        ) : null}
      </div>
    </section>
  );
}

export const Component = GradientBarHeroSection;
