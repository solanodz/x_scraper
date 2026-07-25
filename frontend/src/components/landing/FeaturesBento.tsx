"use client";

import { useEffect, useRef, useState } from "react";

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
  "¿Qué dice el Corpus de $NVDA en 48h?",
  "Signals bajistas recientes sobre $TSLA",
  "Compará sentimiento: $AAPL vs $MSFT",
  "Últimas noticias del Watch",
  "Precio de BTC y contexto en el Corpus",
];

const MOCK_CHAT_TURNS = [
  { role: "user" as const, text: "¿Qué está diciendo el Corpus de NVDA ahora?" },
  { role: "ai" as const, paragraphs: [
    { heading: null, body: "En las últimas 48h hay varios Signals sobre NVDA (noticias + X). Resumen anclado al Corpus — no es un forecast." },
    { heading: "Narrativa", body: "Aparece volumen de opciones y menciones pre-earnings en cuentas de mercado; el Detail marca Solo summary cuando el artículo no tiene body completo." },
    { heading: "Mercado", body: "Quote delayed ~15 min: precio y variación % desde Market Data. Sin predicción de target." },
  ], citations: ["@unusual_whales", "Reuters", "Signal cluster"] },
  { role: "user" as const, text: "¿Y los riesgos que menciona el Corpus?" },
  { role: "ai" as const, paragraphs: [
    { heading: "Lagunas", body: "Si un campo de fundamentals o un artículo es summary-only, el chat lo declara — no inventa PE ni flujo institucional." },
    { heading: "Contraste", body: "Podés pedir Briefing del Watch o abrir el Dossier para profundidad; el Paper Bot opera aparte en paper." },
  ], citations: ["Dossier NVDA", "Corpus 7d"] },
];

function useInView(threshold = 0.35) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) setInView(true);
      },
      { threshold },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [threshold]);

  return { ref, inView };
}

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

/** Alto fijo por slot + gap → paso del carrusel vertical. */
const QUERY_CARD_H = 52;
const QUERY_GAP = 10;
const QUERY_STEP = QUERY_CARD_H + QUERY_GAP;
const QUERY_VISIBLE = 3;
const QUERY_TRANSITION_MS = 700;

function QueryCard({
  query,
  emphasis,
}: {
  query: string;
  /** 0 = centro, 1 = adyacente, 2+ = lejos */
  emphasis: number;
}) {
  const isCenter = emphasis === 0;
  const opacity = isCenter ? 1 : emphasis === 1 ? 0.38 : 0.18;
  const scale = isCenter ? 1 : emphasis === 1 ? 0.9 : 0.84;

  return (
    <div
      className="flex w-full shrink-0 items-center justify-center"
      style={{ height: QUERY_CARD_H }}
    >
      <div
        className="flex w-full items-center gap-2.5 border border-zinc-700/60 bg-zinc-900/80 px-3.5 shadow-sm transition-[opacity,transform] duration-700 ease-out"
        style={{
          height: QUERY_CARD_H,
          opacity,
          transform: `scale(${scale})`,
        }}
      >
        <span className="flex h-6 w-6 shrink-0 items-center justify-center bg-zinc-800">
          <svg
            width="12"
            height="12"
            viewBox="0 0 16 16"
            fill="none"
            className={isCenter ? "text-zinc-200" : "text-zinc-500"}
          >
            <path
              d="M8 1v14M1 8h14"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </span>
        <span
          className={`font-mono text-[11px] leading-tight ${
            isCenter ? "text-zinc-100" : "text-zinc-500"
          }`}
        >
          {query}
        </span>
      </div>
    </div>
  );
}

function QueryCarousel({ active }: { active: boolean }) {
  const reduced = usePrefersReducedMotion();
  const total = SUGGESTED_QUERIES.length;
  const [index, setIndex] = useState(0);
  const [smooth, setSmooth] = useState(true);

  // Lista duplicada para loop infinito sin salto visible.
  const track = [...SUGGESTED_QUERIES, ...SUGGESTED_QUERIES];

  useEffect(() => {
    if (!active || reduced) return;
    const id = window.setInterval(() => {
      setSmooth(true);
      setIndex((prev) => prev + 1);
    }, 3000);
    return () => window.clearInterval(id);
  }, [active, reduced]);

  // Al terminar el primer ciclo, reset sin transición.
  useEffect(() => {
    if (index < total) return;
    const id = window.setTimeout(() => {
      setSmooth(false);
      setIndex(0);
    }, QUERY_TRANSITION_MS);
    return () => window.clearTimeout(id);
  }, [index, total]);

  // Re-habilitar transición en el siguiente frame tras el snap.
  useEffect(() => {
    if (smooth || index !== 0) return;
    const id = window.requestAnimationFrame(() => setSmooth(true));
    return () => window.cancelAnimationFrame(id);
  }, [smooth, index]);

  const viewportH =
    QUERY_VISIBLE * QUERY_CARD_H + (QUERY_VISIBLE - 1) * QUERY_GAP;
  // Con 3 visibles, la del medio es index + 1 en el track.
  const focusIndex = index + 1;

  if (reduced) {
    return (
      <div className="flex min-h-0 flex-1 flex-col justify-center gap-2.5 px-6 pb-8 sm:px-8 sm:pb-10">
        {SUGGESTED_QUERIES.map((query) => (
          <QueryCard key={query} query={query} emphasis={0} />
        ))}
      </div>
    );
  }

  return (
    <div className="relative flex min-h-0 flex-1 items-center px-6 pb-8 sm:px-8 sm:pb-10">
      <div
        className="relative w-full overflow-hidden"
        style={{ height: viewportH }}
        aria-live="polite"
      >
        <div
          className="flex flex-col"
          style={{
            gap: QUERY_GAP,
            transform: `translateY(-${index * QUERY_STEP}px)`,
            transition: smooth
              ? `transform ${QUERY_TRANSITION_MS}ms cubic-bezier(0.22, 1, 0.36, 1)`
              : "none",
          }}
        >
          {track.map((query, i) => (
            <QueryCard
              key={`${query}-${i}`}
              query={query}
              emphasis={Math.abs(i - focusIndex)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function ResearchChatDemo({ active }: { active: boolean }) {
  const reduced = usePrefersReducedMotion();
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const [visibleCount, setVisibleCount] = useState(
    reduced ? MOCK_CHAT_TURNS.length : 0,
  );

  useEffect(() => {
    if (!active) return;
    if (reduced) {
      setVisibleCount(MOCK_CHAT_TURNS.length);
      return;
    }

    let cancelled = false;
    let step = 0;
    let timeout: number | undefined;

    const schedule = (fn: () => void, ms: number) => {
      timeout = window.setTimeout(() => {
        if (!cancelled) fn();
      }, ms);
    };

    const tick = () => {
      step += 1;
      if (step <= MOCK_CHAT_TURNS.length) {
        setVisibleCount(step);
        const delay = MOCK_CHAT_TURNS[step - 1]?.role === "ai" ? 2200 : 1100;
        schedule(tick, delay);
      } else {
        schedule(() => {
          step = 0;
          setVisibleCount(0);
          schedule(tick, 400);
        }, 2800);
      }
    };

    setVisibleCount(0);
    schedule(tick, 500);
    return () => {
      cancelled = true;
      if (timeout !== undefined) window.clearTimeout(timeout);
    };
  }, [active, reduced]);

  useEffect(() => {
    const node = scrollerRef.current;
    if (!node || visibleCount === 0) return;
    node.scrollTo({ top: node.scrollHeight, behavior: reduced ? "auto" : "smooth" });
  }, [visibleCount, reduced]);

  return (
    <div
      ref={scrollerRef}
      className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-6 pb-6 sm:px-8 sm:pb-8"
    >
      <div className="space-y-4">
        {MOCK_CHAT_TURNS.slice(0, visibleCount).map((turn, ti) =>
          turn.role === "user" ? (
            <div key={`${ti}-${visibleCount}`} className="landing-chat-bubble flex justify-end">
              <div className="max-w-[75%] bg-zinc-800 px-3 py-2">
                <p className="font-sans text-[11px] text-zinc-200">{turn.text}</p>
              </div>
            </div>
          ) : (
            <div key={`${ti}-${visibleCount}`} className="landing-chat-bubble">
              {turn.paragraphs?.map((p, pi) => (
                <p
                  key={pi}
                  className="mt-2 font-sans text-[11px] leading-relaxed text-zinc-300 first:mt-0"
                >
                  {p.heading && (
                    <span className="font-semibold text-zinc-100">{p.heading}: </span>
                  )}
                  {p.body}
                </p>
              ))}
              <div className="mt-2.5 flex flex-wrap gap-1">
                {turn.citations?.map((c) => (
                  <span
                    key={c}
                    className="border border-zinc-800 bg-zinc-900 px-1.5 py-0.5 font-mono text-[8px] text-zinc-400"
                  >
                    {c}
                  </span>
                ))}
              </div>
            </div>
          ),
        )}
        {active && !reduced && visibleCount === 0 && (
          <p className="font-mono text-[10px] text-zinc-600">Escribiendo…</p>
        )}
      </div>
    </div>
  );
}

function SignalFeedMini() {
  return (
    <div className="flex min-h-0 flex-1 flex-col px-4 sm:px-6">
      <div className="min-h-0 flex-1 overflow-hidden border border-b-0 border-zinc-800 bg-zinc-950">
        <div className="divide-y divide-zinc-800/50">
          {MOCK_SIGNALS_MINI.map((s) => (
            <div key={`${s.ticker}-${s.time}`} className="px-3 py-2.5">
              <div className="flex items-center gap-1.5">
                <span
                  className={`font-mono text-[10px] font-semibold ${
                    s.bull ? "text-emerald-400" : "text-red-400"
                  }`}
                >
                  {s.ticker}
                </span>
                <span className="font-mono text-[10px] text-zinc-400">
                  {s.author}
                </span>
                <span className="border border-zinc-700 px-1 font-mono text-[7px] uppercase text-zinc-500">
                  {s.badge}
                </span>
                <span className="ml-auto font-mono text-[8px] text-zinc-600">
                  {s.time}
                </span>
              </div>
              <p className="mt-0.5 font-mono text-[10px] leading-relaxed text-zinc-400">
                {s.text}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/** PRNG determinístico (mismo output en SSR/cliente). */
function mulberry32(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Candles [open, high, low, close] 0–100 — random walk con shocks irregulares. */
function buildMockCandles(count = 78, seed = 0xc4a7): Array<[number, number, number, number]> {
  const rand = mulberry32(seed);
  const out: Array<[number, number, number, number]> = [];
  let price = 45 + rand() * 16;

  for (let i = 0; i < count; i++) {
    // Drift + shocks ocasionales (no ritmo fijo) — amplitud alta para cuerpos largos.
    const shock = rand() < 0.14 ? (rand() - 0.5) * 42 : 0;
    const drift = (rand() - 0.48) * 16 + shock;
    const open = price;
    let close = open + drift;
    close = Math.min(94, Math.max(6, close));

    // Mechas cortas la mayoría del tiempo; largas solo a veces.
    const wickUp =
      rand() < 0.18 ? 1 + rand() * 6 : rand() < 0.55 ? rand() * 1.8 : 0.2 + rand() * 0.8;
    const wickDown =
      rand() < 0.18 ? 1 + rand() * 6 : rand() < 0.55 ? rand() * 1.8 : 0.2 + rand() * 0.8;
    const high = Math.min(98, Math.max(open, close) + wickUp);
    const low = Math.max(2, Math.min(open, close) - wickDown);

    // Cuerpos muy chicos a veces (doji-ish).
    if (rand() < 0.06) {
      close = open + (rand() - 0.5) * 2;
    }

    out.push([open, high, low, close]);
    price = close;
  }
  return out;
}

const MOCK_CANDLES = buildMockCandles();

function MockCandles({ className }: { className?: string }) {
  const w = 420;
  const h = 160;
  const pad = 1;
  const n = MOCK_CANDLES.length;
  const slot = (w - pad * 2) / n;
  const bodyW = Math.max(1.2, slot * 0.62);

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className={className}
      preserveAspectRatio="none"
      aria-hidden
    >
      {[25, 50, 75].map((y) => (
        <line
          key={y}
          x1={0}
          y1={(y / 100) * h}
          x2={w}
          y2={(y / 100) * h}
          stroke="#27272a"
          strokeWidth={1}
        />
      ))}
      {MOCK_CANDLES.map(([o, hi, lo, c], i) => {
        const x = pad + i * slot + slot / 2;
        const bull = c >= o;
        const color = bull ? "#34d399" : "#f87171";
        const y = (v: number) => h - (v / 100) * (h - 8) - 4;
        return (
          <g key={i}>
            <line
              x1={x}
              y1={y(hi)}
              x2={x}
              y2={y(lo)}
              stroke={color}
              strokeWidth={1}
            />
            <rect
              x={x - bodyW / 2}
              y={y(Math.max(o, c))}
              width={bodyW}
              height={Math.max(1.5, Math.abs(y(o) - y(c)))}
              fill={color}
            />
          </g>
        );
      })}
      {/* Nivel sugerido */}
      <line
        x1={0}
        y1={yLevel(58, h)}
        x2={w}
        y2={yLevel(58, h)}
        stroke="#71717a"
        strokeWidth={1}
        strokeDasharray="4 3"
      />
    </svg>
  );
}

function yLevel(v: number, h: number) {
  return h - (v / 100) * (h - 8) - 4;
}

/** Serie 0–100 estilo Oracle + SMA signal (seed fijo). */
function buildOracleSeries(count = 64, seed = 0x0a5c) {
  const rand = mulberry32(seed);
  const values: number[] = [];
  let v = 42 + rand() * 16;
  for (let i = 0; i < count; i++) {
    v = Math.min(92, Math.max(8, v + (rand() - 0.48) * 9 + (rand() < 0.1 ? (rand() - 0.5) * 18 : 0)));
    values.push(v);
  }
  const signal = values.map((_, i) => {
    const from = Math.max(0, i - 4);
    const slice = values.slice(from, i + 1);
    return slice.reduce((a, b) => a + b, 0) / slice.length;
  });
  return { values, signal };
}

const MOCK_ORACLE = buildOracleSeries();

function oscY(v: number, h: number) {
  return h - (v / 100) * h;
}

function seriesPolyline(
  values: number[],
  w: number,
  h: number,
  clamp?: (v: number) => number,
) {
  return values
    .map((v, i) => {
      const x = (i / Math.max(1, values.length - 1)) * w;
      const y = oscY(clamp ? clamp(v) : v, h);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function baselineFillPath(
  values: number[],
  w: number,
  h: number,
  side: "above" | "below",
) {
  const mid = 50;
  const midY = oscY(mid, h);
  const clamp =
    side === "above"
      ? (v: number) => Math.max(v, mid)
      : (v: number) => Math.min(v, mid);
  const line = values
    .map((v, i) => {
      const x = (i / Math.max(1, values.length - 1)) * w;
      return `L ${x.toFixed(1)} ${oscY(clamp(v), h).toFixed(1)}`;
    })
    .join(" ");
  const xLast = w;
  return `M 0 ${midY} ${line} L ${xLast.toFixed(1)} ${midY} Z`;
}

/** Oracle Oscillator del Dossier: baseline fill + signal dashed + bandas 75/25. */
function MockOracleOscillator() {
  const w = 420;
  const h = 56;
  const { values, signal } = MOCK_ORACLE;
  const midY = oscY(50, h);

  return (
    <div>
      <p className="mb-0.5 px-0.5 font-mono text-[8px] uppercase tracking-wide text-zinc-500">
        Oracle Oscillator
      </p>
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="h-14 w-full sm:h-16"
        preserveAspectRatio="none"
        aria-hidden
      >
        <defs>
          <linearGradient id="oracleTopFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgb(34,197,94)" stopOpacity="0.55" />
            <stop offset="100%" stopColor="rgb(250,204,14)" stopOpacity="0.18" />
          </linearGradient>
          <linearGradient id="oracleBotFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgb(250,204,14)" stopOpacity="0.18" />
            <stop offset="100%" stopColor="rgb(239,68,68)" stopOpacity="0.55" />
          </linearGradient>
        </defs>
        {/* Bandas 75 / 25 */}
        <line
          x1={0}
          y1={oscY(75, h)}
          x2={w}
          y2={oscY(75, h)}
          stroke="#22c55e"
          strokeWidth={0.8}
          opacity={0.7}
        />
        <line
          x1={0}
          y1={oscY(25, h)}
          x2={w}
          y2={oscY(25, h)}
          stroke="#ef4444"
          strokeWidth={0.8}
          opacity={0.7}
        />
        <line
          x1={0}
          y1={midY}
          x2={w}
          y2={midY}
          stroke="#3f3f46"
          strokeWidth={0.6}
        />
        <path d={baselineFillPath(values, w, h, "above")} fill="url(#oracleTopFill)" />
        <path d={baselineFillPath(values, w, h, "below")} fill="url(#oracleBotFill)" />
        <polyline
          points={seriesPolyline(values, w, h)}
          fill="none"
          stroke="#e4e4e7"
          strokeWidth={1.4}
        />
        <polyline
          points={seriesPolyline(signal, w, h)}
          fill="none"
          stroke="#facc15"
          strokeWidth={1}
          strokeDasharray="4 3"
        />
      </svg>
    </div>
  );
}

function buildRsiSeries(count = 64, seed = 0xb51) {
  const rand = mulberry32(seed);
  const values: number[] = [];
  let v = 55;
  for (let i = 0; i < count; i++) {
    v = Math.min(88, Math.max(18, v + (rand() - 0.5) * 8));
    values.push(v);
  }
  // Tramo bajista para marca Bear (divergencia).
  values[50] = 72;
  values[58] = 58;
  return values;
}

const MOCK_RSI = buildRsiSeries();

/** RSI pane chico con marca Bear (como divergencia del Dossier). */
function MockRsiPane() {
  const w = 420;
  const h = 40;
  const values = MOCK_RSI;
  const bearX = (58 / 63) * w;
  const bearY = oscY(58, h);

  return (
    <div className="border-t border-zinc-800/80 pt-1">
      <p className="mb-0.5 px-0.5 font-mono text-[8px] uppercase tracking-wide text-zinc-500">
        Indicador de divergencia RSI
      </p>
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="h-10 w-full sm:h-11"
        preserveAspectRatio="none"
        aria-hidden
      >
        <line
          x1={0}
          y1={oscY(70, h)}
          x2={w}
          y2={oscY(70, h)}
          stroke="rgba(113,113,122,0.45)"
          strokeWidth={0.8}
          strokeDasharray="2 2"
        />
        <line
          x1={0}
          y1={oscY(30, h)}
          x2={w}
          y2={oscY(30, h)}
          stroke="rgba(113,113,122,0.45)"
          strokeWidth={0.8}
          strokeDasharray="2 2"
        />
        <polyline
          points={seriesPolyline(values, w, h)}
          fill="none"
          stroke="#38bdf8"
          strokeWidth={1.4}
        />
        {/* Divergencia bear */}
        <line
          x1={(50 / 63) * w}
          y1={oscY(72, h)}
          x2={bearX}
          y2={bearY}
          stroke="#ef4444"
          strokeWidth={1.5}
        />
        <rect
          x={bearX - 2}
          y={bearY - 8}
          width={4}
          height={4}
          fill="#ef4444"
        />
        <text
          x={bearX + 5}
          y={bearY - 4}
          fill="#ef4444"
          fontSize="7"
          fontFamily="ui-monospace, monospace"
        >
          Bear
        </text>
      </svg>
    </div>
  );
}

function ChartPlanMock() {
  return (
    <div className="border border-zinc-800 bg-zinc-950">
      {/* Barra ticker */}
      <div className="flex flex-wrap items-center gap-2 border-b border-zinc-800 px-3 py-2">
        <span className="font-mono text-[11px] font-semibold text-zinc-100">
          Chart Plan · <span className="text-zinc-300">$NVDA</span>
        </span>
        <span className="font-mono text-[11px] text-zinc-200">138.42</span>
        <span className="font-mono text-[10px] text-emerald-400">+3.82%</span>
        <span className="ml-auto font-mono text-[9px] text-zinc-600">
          delay ~15m
        </span>
      </div>

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-1.5 border-b border-zinc-800 px-3 py-1.5">
        {["4H", "EMA", "Oracle", "RSI"].map((chip) => (
          <span
            key={chip}
            className="border border-zinc-700 bg-zinc-900 px-1.5 py-0.5 font-mono text-[9px] text-zinc-400"
          >
            {chip}
          </span>
        ))}
        <span className="ml-auto border border-zinc-700 bg-zinc-900/80 px-2 py-0.5 font-mono text-[9px] text-zinc-300">
          Aplicar vista
        </span>
      </div>

      {/* Chart */}
      <div className="relative px-2 pt-2">
        <MockCandles className="h-[180px] w-full sm:h-[210px]" />
        <span className="absolute right-3 top-3 font-mono text-[8px] text-zinc-600">
          nivel 58
        </span>
      </div>
      <div className="space-y-1 border-t border-zinc-800/80 px-2 pb-2 pt-1">
        <MockOracleOscillator />
        <MockRsiPane />
      </div>
    </div>
  );
}

export default function FeaturesBento() {
  const { ref: queriesRef, inView: queriesInView } = useInView(0.3);
  const { ref: chatRef, inView: chatInView } = useInView(0.3);

  return (
    <section id="superficies" className="scroll-mt-24 py-24 sm:py-32">
      <div className="mx-auto max-w-6xl px-6 sm:px-8">
        <h2 className="font-sans text-2xl font-semibold tracking-tight text-zinc-100 sm:text-3xl">
          Todo el Corpus, desde cada ángulo
        </h2>
        <p className="mt-4 max-w-2xl font-sans text-base leading-relaxed text-zinc-400">
          Superficies conectadas al mismo Corpus: Feed, Research con Citations,
          Dossier / Chart Plan, más Briefing del Watch y Paper Bot. Analítico —
          sin recomendaciones de compra/venta.
        </p>

        <div className="mt-14 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {/* Chart Plan — mock UI (define alto de la fila) */}
          <div className="overflow-hidden border border-zinc-800 bg-zinc-950 sm:col-span-2 lg:col-span-3">
            <div className="p-6 pb-0 sm:p-8 sm:pb-0">
              <p className="font-mono text-sm text-zinc-300">Chart Plan</p>
              <p className="mt-2 max-w-md font-sans text-sm leading-relaxed text-zinc-400">
                Lecturas de mercado Operator-first con datos del Corpus.
                Sugiere niveles y escenarios, vos mantenés el control.
              </p>
            </div>
            <div className="mt-4 px-3 pb-3 sm:px-5 sm:pb-5">
              <ChartPlanMock />
            </div>
          </div>

          {/* Signal Feed — estático, mismo alto que Chart Plan */}
          <div className="flex min-h-0 flex-col overflow-hidden border border-zinc-800 bg-zinc-900/50 sm:col-span-1 lg:col-span-2">
            <div className="shrink-0 p-6 pb-4 sm:p-8 sm:pb-4">
              <p className="font-mono text-sm text-zinc-300">Signal Feed</p>
              <p className="mt-2 font-sans text-sm leading-relaxed text-zinc-400">
                Signals en vivo del Corpus, filtrados y con fuente visible.
              </p>
            </div>
            <SignalFeedMini />
          </div>

          {/* Queries — carousel, altura fija + cards centradas */}
          <div
            ref={queriesRef}
            className="flex h-[420px] flex-col overflow-hidden border border-zinc-800 bg-zinc-900/50 lg:col-span-2"
          >
            <div className="shrink-0 p-6 pb-4 sm:p-8 sm:pb-4">
              <p className="font-mono text-sm text-zinc-300">Queries sugeridas</p>
              <p className="mt-2 font-sans text-sm leading-relaxed text-zinc-400">
                Preguntas típicas al Corpus (precios, Signals, contraste) — sin
                templates de forecast inventado.
              </p>
            </div>
            <QueryCarousel active={queriesInView} />
          </div>

          {/* Research Chat — sequential messages, altura fija */}
          <div
            ref={chatRef}
            className="flex h-[420px] flex-col overflow-hidden border border-zinc-800 bg-zinc-900/50 sm:col-span-2 lg:col-span-3"
          >
            <div className="shrink-0 p-6 pb-4 sm:p-8 sm:pb-4">
              <p className="font-mono text-sm text-zinc-300">Research Chat</p>
              <p className="mt-2 max-w-md font-sans text-sm leading-relaxed text-zinc-400">
                Preguntás en lenguaje natural y el agente responde citando
                Signals reales del Corpus.
              </p>
            </div>
            <ResearchChatDemo active={chatInView} />
          </div>
        </div>
      </div>
    </section>
  );
}
