"use client";

/**
 * Simulación estática fiel de la terminal real para el landing.
 * Layout horizontal: Feed | Chat, más ancho, menos alto.
 * Quote strip con carousel CSS en loop infinito.
 */

const TICKER_LOGOS: Record<string, string> = {
  AAPL: "https://cdn.simpleicons.org/apple/ffffff",
  NVDA: "https://cdn.simpleicons.org/nvidia/76B900",
  TSLA: "https://cdn.simpleicons.org/tesla/ffffff",
  META: "https://cdn.simpleicons.org/meta/0081FB",
  MSFT: "https://cdn.simpleicons.org/microsoft/ffffff",
  GOOGL: "https://cdn.simpleicons.org/google/4285F4",
};

function TickerIcon({ symbol }: { symbol: string }) {
  const url = TICKER_LOGOS[symbol];
  return (
    <span className="inline-flex h-4 w-4 shrink-0 items-center justify-center overflow-hidden rounded-full border border-zinc-700 bg-zinc-900">
      {url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt="" className="h-2.5 w-2.5 object-contain" />
      ) : (
        <span className="font-mono text-[7px] font-semibold text-zinc-400">
          {symbol.slice(0, 2)}
        </span>
      )}
    </span>
  );
}

const MOCK_QUOTES = [
  { symbol: "AAPL", price: "234.18", pct: "+1.24%", bull: true },
  { symbol: "NVDA", price: "138.42", pct: "+3.82%", bull: true },
  { symbol: "TSLA", price: "248.90", pct: "-4.11%", bull: false },
  { symbol: "MSFT", price: "468.15", pct: "+0.67%", bull: true },
  { symbol: "GLD", price: "292.34", pct: "+0.98%", bull: true },
  { symbol: "AMZN", price: "197.25", pct: "-0.32%", bull: false },
  { symbol: "META", price: "512.80", pct: "+2.14%", bull: true },
  { symbol: "GOOGL", price: "178.44", pct: "+0.41%", bull: true },
  { symbol: "SPY", price: "562.15", pct: "+0.55%", bull: true },
  { symbol: "QQQ", price: "487.30", pct: "+1.02%", bull: true },
];

const MOCK_SIGNALS = [
  {
    author: "@markgurman",
    sourceType: "x" as const,
    cashtags: ["$AAPL"],
    topic: "AI / Mobile",
    text: "Apple reportedly in talks with OpenAI for iOS 20 integration, sources say deal could reshape mobile AI...",
    time: "4m",
    likes: "2.1K",
    rts: "842",
    cluster: null,
  },
  {
    author: "@unusual_whales",
    sourceType: "x" as const,
    cashtags: ["$NVDA"],
    topic: "Options Flow",
    text: "NVDA call volume surging ahead of earnings, 3x average. $140 strike leading the flow.",
    time: "11m",
    likes: "4.8K",
    rts: "1.9K",
    cluster: "3 fuentes",
  },
  {
    author: "Reuters",
    sourceType: "news" as const,
    cashtags: ["$TSLA"],
    topic: "Earnings",
    text: "Tesla Q2 deliveries miss consensus by 8%. Shanghai factory shutdown cited as primary factor.",
    time: "18m",
    likes: null,
    rts: null,
    cluster: null,
  },
  {
    author: "@alexheath",
    sourceType: "x" as const,
    cashtags: ["$META"],
    topic: "Corporate",
    text: "Meta cutting 5% of lowest performers per Zuckerberg memo. Focus shifting to AI agents.",
    time: "32m",
    likes: "6.2K",
    rts: "3.1K",
    cluster: null,
  },
  {
    author: "@goldtelegraph_",
    sourceType: "x" as const,
    cashtags: ["$GLD"],
    topic: "Commodities",
    text: "Gold hits new ATH as central banks accelerate reserve buying. ETF inflows matching 2024 levels.",
    time: "25m",
    likes: "1.3K",
    rts: "510",
    cluster: "2 fuentes",
  },
  {
    author: "Bloomberg",
    sourceType: "news" as const,
    cashtags: ["$MSFT", "$GOOGL"],
    topic: "Cloud / AI",
    text: "Microsoft and Google ramp up AI infra spending, combined capex forecast revised upward to $68B for FY25.",
    time: "41m",
    likes: null,
    rts: null,
    cluster: null,
  },
];

const MOCK_CHAT = [
  { role: "user" as const, text: "What's driving NVDA options flow today?" },
  {
    role: "assistant" as const,
    text: "Based on the Corpus, NVDA is seeing 3x average call volume ahead of earnings. The $140 strike is leading the flow with institutional positioning strongly bullish. Key signals point to block trades and sweep activity in near-term expirations.",
    citations: ["Signal #2841", "Signal #2839", "Signal #2835"],
  },
  {
    role: "user" as const,
    text: "How does this compare to last quarter?",
  },
  {
    role: "assistant" as const,
    text: "Last quarter saw 1.8x average volume pre-earnings with the $120 strike dominant. Current flow is significantly more aggressive, both in magnitude and concentration at higher strikes.",
    citations: ["Signal #2614", "Signal #2601"],
  },
  {
    role: "user" as const,
    text: "Break down the risk/reward if I enter calls at current levels.",
  },
  {
    role: "assistant" as const,
    text: "At $138.42 with the $140 strike, you're looking at ~$1.60 out of the money. Implied vol is at 62% (vs 45% historical), so premiums are elevated. The Corpus shows 14 bullish signals in 48h against 3 bearish. Key risk: if earnings miss, IV crush alone could erase 35-40% of premium regardless of direction. Upside target from consensus is $152, which gives roughly 2.8:1 reward/risk on the $140C at current ask.",
    citations: ["Signal #2841", "Signal #2838", "Signal #2830", "Signal #2822"],
  },
];

function QuoteItem({ q }: { q: (typeof MOCK_QUOTES)[number] }) {
  return (
    <span className="flex items-center gap-1 whitespace-nowrap">
      <TickerIcon symbol={q.symbol} />
      <span className="font-mono text-[10px] text-zinc-400">{q.symbol}</span>
      <span className="font-mono text-[10px] text-zinc-200">{q.price}</span>
      <span
        className={`font-mono text-[9px] ${q.bull ? "text-emerald-400" : "text-red-400"}`}
      >
        {q.pct}
      </span>
    </span>
  );
}

export default function TerminalMockup() {
  return (
    <div
      className="overflow-hidden rounded-t-2xl border border-b-0 border-zinc-800 bg-zinc-900 text-left shadow-[0_-8px_60px_rgba(0,0,0,0.7)]"
      style={{
        maskImage: "linear-gradient(to bottom, black 78%, transparent 94%)",
        WebkitMaskImage: "linear-gradient(to bottom, black 78%, transparent 94%)",
      }}
    >
      {/* ── Header ── */}
      <div className="flex items-center justify-between border-b border-zinc-800 bg-zinc-950 px-4 py-2">
        <div className="flex items-center gap-3">
          <span className="font-mono text-sm text-amber-500">▮</span>
          <span className="font-sans text-[11px] font-semibold text-zinc-100 sm:text-xs">
            X Scraper Terminal
          </span>
          <div className="flex items-center gap-1">
            <span className="rounded bg-amber-950/40 px-2 py-0.5 font-sans text-[9px] font-semibold text-amber-400 sm:text-[10px]">
              Terminal
            </span>
            <span className="rounded px-2 py-0.5 font-sans text-[9px] text-zinc-500 sm:text-[10px]">
              Dossier
            </span>
          </div>
        </div>
        <div className="hidden items-center gap-2 sm:flex">
          <span className="rounded border border-zinc-700 bg-zinc-900 px-2.5 py-0.5 font-sans text-[10px] text-zinc-400">
            Refresh
          </span>
          <span className="rounded border border-zinc-700 bg-zinc-900 px-2.5 py-0.5 font-sans text-[10px] text-zinc-500">
            Cerrar sesión
          </span>
        </div>
      </div>

      {/* ── Quote Strip Carousel ── */}
      <div className="flex items-center gap-1 overflow-hidden border-b border-zinc-800/60 bg-zinc-950/80 px-4 py-1.5">
        <span className="shrink-0 rounded border border-zinc-700 px-1 py-0.5 font-mono text-[8px] uppercase tracking-wide text-zinc-600">
          15m delayed
        </span>
        <div className="quote-carousel-mask ml-2 flex-1">
          <div
            className="quote-carousel-track flex gap-5"
            style={{ animationDuration: "30s" }}
          >
            {/* Duplicado para loop continuo */}
            {[...MOCK_QUOTES, ...MOCK_QUOTES].map((q, i) => (
              <QuoteItem key={`${q.symbol}-${i}`} q={q} />
            ))}
          </div>
        </div>
      </div>

      {/* ── Main: Feed | Chat side by side ── */}
      <div className="grid min-h-[28rem] grid-cols-1 sm:grid-cols-[1.2fr_1fr]">
        {/* Feed */}
        <div className="border-r border-zinc-800/60 pb-20">
          <div className="flex items-center justify-between border-b border-zinc-800 px-3 py-1.5">
            <div className="flex items-baseline gap-2">
              <span className="font-sans text-[10px] font-semibold uppercase tracking-wider text-amber-500">
                Signal Feed
              </span>
              <span className="font-mono text-[9px] text-zinc-600">
                1.247 de 3.891
              </span>
            </div>
            <span className="font-mono text-[9px] text-emerald-500">
              ● LIVE
            </span>
          </div>
          <div className="divide-y divide-zinc-800/40">
            {MOCK_SIGNALS.map((signal, i) => (
              <div
                key={i}
                className={`px-3 py-2 ${i === 1 ? "bg-zinc-800/30" : ""}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-1.5">
                    <span className="font-mono text-[11px] font-semibold text-amber-400">
                      {signal.author}
                    </span>
                    <span className="shrink-0 rounded border border-zinc-700 px-1 font-mono text-[8px] uppercase text-zinc-500">
                      {signal.sourceType === "x" ? "x" : "news"}
                    </span>
                    {signal.cluster && (
                      <span className="shrink-0 rounded border border-amber-900/50 bg-amber-950/30 px-1 font-mono text-[8px] text-amber-500">
                        {signal.cluster}
                      </span>
                    )}
                  </div>
                  <span className="shrink-0 font-mono text-[9px] text-zinc-600">
                    {signal.time}
                  </span>
                </div>
                <p className="mt-0.5 text-left font-mono text-[10px] leading-relaxed text-zinc-300 sm:text-[11px]">
                    {signal.text}
                  </p>
                <div className="mt-1 flex items-center gap-2">
                  {signal.cashtags.map((tag) => (
                    <span
                      key={tag}
                      className="font-mono text-[9px] text-emerald-500"
                    >
                      {tag}
                    </span>
                  ))}
                  <span className="font-mono text-[9px] text-zinc-600">
                    {signal.topic}
                  </span>
                  {signal.likes ? (
                    <span className="ml-auto font-mono text-[9px] text-zinc-600">
                      ♥ {signal.likes} · ↻ {signal.rts}
                    </span>
                  ) : (
                    <span className="ml-auto font-mono text-[9px] text-zinc-500">
                      noticia
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Chat */}
        <div className="hidden sm:flex sm:flex-col">
          <div className="border-b border-zinc-800 px-3 py-1.5">
            <span className="font-sans text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
              Research Chat
            </span>
          </div>
          <div className="flex flex-1 flex-col p-3">
            <div className="space-y-3">
              {MOCK_CHAT.map((msg, i) =>
                msg.role === "user" ? (
                  <div key={i} className="flex justify-end">
                    <div className="max-w-[85%] rounded-lg bg-zinc-800 px-3 py-2">
                      <p className="font-sans text-[11px] text-zinc-200">
                        {msg.text}
                      </p>
                    </div>
                  </div>
                ) : (
                  <div key={i} className="max-w-[95%] text-left">
                    <p className="font-sans text-[11px] leading-relaxed text-zinc-300 text-left">
                      {msg.text}
                    </p>
                    {"citations" in msg && msg.citations && (
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {msg.citations.map((c) => (
                          <span
                            key={c}
                            className="rounded bg-amber-950/30 px-1.5 py-0.5 font-mono text-[8px] text-amber-500/80"
                          >
                            {c}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ),
              )}
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}
