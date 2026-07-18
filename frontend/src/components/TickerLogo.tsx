"use client";

import { useEffect, useState } from "react";

interface TickerLogoProps {
  symbol: string;
  logoUrl?: string | null;
  size?: "xs" | "sm" | "md";
  className?: string;
}

const SIZE_CLASS: Record<NonNullable<TickerLogoProps["size"]>, string> = {
  xs: "h-4 w-4 text-[8px]",
  sm: "h-5 w-5 text-[9px]",
  md: "h-7 w-7 text-[10px]",
};

function initials(symbol: string): string {
  const clean = symbol.replace(/^\$/, "").toUpperCase();
  return clean.slice(0, 2);
}

export default function TickerLogo({
  symbol,
  logoUrl,
  size = "sm",
  className = "",
}: TickerLogoProps) {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [symbol, logoUrl]);

  const showImage = Boolean(logoUrl) && !failed;

  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full border border-zinc-700 bg-zinc-900 ${SIZE_CLASS[size]} ${className}`}
      aria-hidden
    >
      {showImage ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={logoUrl!}
          alt=""
          className="h-full w-full object-cover"
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
        />
      ) : (
        <span className="font-mono font-semibold leading-none text-zinc-400">
          {initials(symbol)}
        </span>
      )}
    </span>
  );
}
