"use client";

const MOCK_SIGNALS_MINI = [
  { ticker: "$NVDA", author: "@unusual_whales", text: "Call volume surging 3x ahead of earnings", badge: "x", time: "4m", bull: true },
  { ticker: "$AAPL", author: "@markgurman", text: "Apple in talks with OpenAI for iOS 20", badge: "x", time: "11m", bull: true },
  { ticker: "$TSLA", author: "Reuters", text: "Q2 deliveries miss consensus by 8%", badge: "news", time: "18m", bull: false },
  { ticker: "$GLD", author: "@goldtelegraph_", text: "Gold ATH as central banks buy reserves", badge: "x", time: "25m", bull: true },
  { ticker: "$META", author: "@alexheath", text: "Cutting 5% lowest performers, AI pivot", badge: "x", time: "32m", bull: false },
  { ticker: "$AMZN", author: "@WSJ", text: "AWS revenue beats estimates by 12%", badge: "news", time: "41m", bull: true },
  { ticker: "$MSFT", author: "@satloopy", text: "Azure AI services up 47% YoY", badge: "x", time: "48m", bull: true },
  { ticker: "$AMD", author: "@unusual_whales", text: "Put volume spiking ahead of guidance", badge: "x", time: "55m", bull: false },
  { ticker: "$GOOGL", author: "@business", text: "Gemini 3 launch boosts ad revenue outlook", badge: "news", time: "1h", bull: true },
];

const SUGGESTED_QUERIES = [
  "Forecast Q3 earnings for $NVDA",
  "Find bearish signals on $TSLA",
  "Compare sentiment: $AAPL vs $MSFT",
  "Top signals by volume today",
  "Track institutional flow in $GLD",
];

const MOCK_CHAT_TURNS = [
  { role: "user" as const, text: "What's the bull case for NVDA right now?" },
  { role: "ai" as const, paragraphs: [
    { heading: null, body: "Based on 47 Signals from the last 48 hours, the Corpus shows strong institutional conviction around NVDA heading into earnings." },
    { heading: "Options flow", body: "Unusual call volume at 3.2x the 20-day average. The largest blocks are concentrated at the $140 and $145 strikes expiring next Friday, suggesting traders are positioning for a move above current levels." },
    { heading: "Analyst sentiment", body: "Three upgrades in the last week — Goldman raised PT to $160 citing \"accelerating AI capex cycle,\" Morgan Stanley reiterated Overweight, and Bernstein initiated with a Buy noting datacenter GPU demand is \"structurally underappreciated.\"" },
  ], citations: ["Signal #2841", "Signal #2839", "Signal #2835", "Signal #2812", "Signal #2807"] },
  { role: "user" as const, text: "What are the main risks? Compare with $AMD positioning." },
  { role: "ai" as const, paragraphs: [
    { heading: "Valuation risk", body: "At 35x forward PE, NVDA is pricing in near-flawless execution. The Corpus flagged 12 bearish signals citing stretched multiples relative to historical ranges." },
    { heading: "China exposure", body: "Export restrictions remain a wildcard. 3 signals from policy-focused accounts suggest new licensing requirements could impact datacenter revenue by 8-12% in H2." },
    { heading: "AMD comparison", body: "AMD positioning is notably different — put volume spiking 2.1x ahead of guidance, with sentiment split 52/48 bull/bear. The Corpus shows a narrative divergence: NVDA is \"AI winner\" while AMD is \"show-me story.\"" },
  ], citations: ["Signal #2838", "Signal #2830", "Signal #2824", "Signal #2819"] },
];

export default function FeaturesBento() {
  return (
    <section id="superficies" className="scroll-mt-24 py-24 sm:py-32">
      <div className="mx-auto max-w-6xl px-6 sm:px-8">
        <h2 className="font-sans text-2xl font-semibold tracking-tight text-zinc-100 sm:text-3xl">
          Todo el Corpus, desde cada ángulo
        </h2>
        <p className="mt-4 max-w-2xl font-sans text-base leading-relaxed text-zinc-400">
          Cuatro superficies conectadas al mismo Corpus. Precio, conversación,
          narrativa y análisis en un solo lugar.
        </p>

        {/* Bento Grid: 2 grandes arriba, 3 chicos abajo */}
        <div className="mt-14 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {/* ── Card 1: Chart Plan (grande, 2 cols) ── */}
          <div className="overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-950 sm:col-span-2 lg:col-span-3">
            <div className="p-6 pb-0 sm:p-8 sm:pb-0">
              <p className="font-mono text-sm text-amber-500">Chart Plan</p>
              <p className="mt-2 max-w-md font-sans text-sm leading-relaxed text-zinc-400">
                Lecturas de mercado Operator-first con datos del Corpus.
                Sugiere niveles y escenarios, vos mantenés el control.
              </p>
            </div>
            <div className="mt-4 px-3 pb-3 sm:px-5 sm:pb-5">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/chart-preview.png"
                alt="Chart Plan — velas, Oracle Oscillator, RSI divergencia"
                className="w-full rounded-lg"
                draggable={false}
              />
            </div>
          </div>

          {/* ── Card 2: Signal Feed ── */}
          <div className="relative overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-900/50 sm:col-span-1 lg:col-span-2">
            <div className="p-6 pb-4 sm:p-8 sm:pb-4">
              <p className="font-mono text-sm text-amber-500">Signal Feed</p>
              <p className="mt-2 font-sans text-sm leading-relaxed text-zinc-400">
                Signals en vivo del Corpus, filtrados y con fuente visible.
              </p>
            </div>
            <div className="px-4 sm:px-6">
              <div className="divide-y divide-zinc-800/50 rounded-t-xl border border-b-0 border-zinc-800 bg-zinc-950">
                {MOCK_SIGNALS_MINI.map((s, i) => (
                  <div key={i} className="px-3 py-2.5">
                    <div className="flex items-center gap-1.5">
                      <span className={`font-mono text-[10px] font-semibold ${s.bull ? "text-emerald-400" : "text-red-400"}`}>
                        {s.ticker}
                      </span>
                      <span className="font-mono text-[10px] text-amber-400">{s.author}</span>
                      <span className="rounded border border-zinc-700 px-1 font-mono text-[7px] uppercase text-zinc-500">{s.badge}</span>
                      <span className="ml-auto font-mono text-[8px] text-zinc-600">{s.time}</span>
                    </div>
                    <p className="mt-0.5 font-mono text-[10px] leading-relaxed text-zinc-400">{s.text}</p>
                  </div>
                ))}
              </div>
            </div>
            {/* Fade-out at the bottom edge */}
            <div className="pointer-events-none absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-zinc-900 to-transparent" />
          </div>

          {/* ── Card 3: Suggested Queries ── */}
          <div className="max-h-[420px] overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-900/50 lg:col-span-2">
            <div className="p-6 sm:p-8">
              <p className="font-mono text-sm text-amber-500">Queries sugeridas</p>
              <p className="mt-2 font-sans text-sm leading-relaxed text-zinc-400">
                Templates listos para investigar el Corpus — empezá con un click.
              </p>
            </div>
            <div className="relative px-6 pb-8 sm:px-8 sm:pb-10">
              <div className="flex flex-col items-center gap-3">
                {SUGGESTED_QUERIES.map((q, i) => {
                  const total = SUGGESTED_QUERIES.length;
                  const mid = (total - 1) / 2;
                  const dist = Math.abs(i - mid);
                  const opacity = 1 - dist * 0.3;
                  const scale = 1 - dist * 0.1;
                  return (
                    <div
                      key={i}
                      className="flex w-full items-center gap-2.5 rounded-xl border border-zinc-700/60 bg-zinc-900/80 px-3.5 py-2.5 shadow-sm"
                      style={{ opacity, transform: `scale(${scale})` }}
                    >
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-amber-500/10">
                        <svg width="12" height="12" viewBox="0 0 16 16" fill="none" className="text-amber-500">
                          <path d="M8 1v14M1 8h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                        </svg>
                      </span>
                      <span className="font-mono text-[11px] leading-tight text-zinc-200">{q}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* ── Card 4: Research Chat (grande, 3 cols) ── */}
          <div className="relative max-h-[420px] overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-900/50 sm:col-span-2 lg:col-span-3">
            <div className="p-6 sm:p-8 sm:pb-4">
              <p className="font-mono text-sm text-amber-500">Research Chat</p>
              <p className="mt-2 max-w-md font-sans text-sm leading-relaxed text-zinc-400">
                Preguntás en lenguaje natural y el agente responde citando
                Signals reales del Corpus.
              </p>
            </div>
            <div className="space-y-4 px-6 sm:px-8">
              {MOCK_CHAT_TURNS.map((turn, ti) =>
                turn.role === "user" ? (
                  <div key={ti} className="flex justify-end">
                    <div className="max-w-[75%] rounded-lg bg-zinc-800 px-3 py-2">
                      <p className="font-sans text-[11px] text-zinc-200">{turn.text}</p>
                    </div>
                  </div>
                ) : (
                  <div key={ti}>
                    {turn.paragraphs?.map((p, pi) => (
                      <p key={pi} className="mt-2 font-sans text-[11px] leading-relaxed text-zinc-300 first:mt-0">
                        {p.heading && (
                          <span className="font-semibold text-zinc-100">{p.heading}: </span>
                        )}
                        {p.body}
                      </p>
                    ))}
                    <div className="mt-2.5 flex flex-wrap gap-1">
                      {turn.citations?.map((c) => (
                        <span key={c} className="rounded bg-amber-950/30 px-1.5 py-0.5 font-mono text-[8px] text-amber-500/80">{c}</span>
                      ))}
                    </div>
                  </div>
                ),
              )}
            </div>
            {/* Fade-out gradient at the bottom */}
            <div className="pointer-events-none absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-zinc-900 to-transparent" />
          </div>
        </div>
      </div>
    </section>
  );
}
