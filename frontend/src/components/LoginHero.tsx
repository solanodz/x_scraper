"use client";

/** Panel decorativo minimalista (login hero). */

import {
  ComposedChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
  usePlotArea,
} from "recharts";

type Candle = {
  i: number;
  open: number;
  high: number;
  low: number;
  close: number;
};

/** Progreso suave 0→1 (ease-in-out). */
function eased(t: number): number {
  return t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
}

/** Pseudo-aleatorio determinista 0→1 (estable en SSR). */
function hash01(i: number, salt: number): number {
  const x = Math.sin(i * 12.9898 + salt * 78.233) * 43758.5453;
  return x - Math.floor(x);
}

/** Mechas variadas: algunas pegadas al high/low, otras con líneas visibles. */
function assignWicks(
  open: number,
  close: number,
  i: number,
): { high: number; low: number } {
  const bodyTop = Math.max(open, close);
  const bodyBottom = Math.min(open, close);

  const roll = hash01(i, 1);
  const short = 0.12 + hash01(i, 2) * 0.35;
  const medium = 0.5 + hash01(i, 3) * 1.2;
  const long = 0.85 + hash01(i, 7) * 1.6;

  let high: number;
  let low: number;

  if (roll < 0.22) {
    high = bodyTop + short;
    low = bodyBottom - medium;
  } else if (roll < 0.44) {
    high = bodyTop + medium;
    low = bodyBottom - short;
  } else if (roll < 0.7) {
    high = bodyTop + medium * 0.65;
    low = bodyBottom - medium * 0.65;
  } else if (roll < 0.88) {
    const upperLong = hash01(i, 4) < 0.5;
    high = bodyTop + (upperLong ? long : short);
    low = bodyBottom - (upperLong ? short : long);
  } else if (roll < 0.95) {
    high = bodyTop + short * 0.75;
    low = bodyBottom - short * 0.75;
  } else {
    high = bodyTop;
    low = bodyBottom;
  }

  return { high, low };
}

/** Forma GLD-like: plano → subida gradual ruidosa → corrección leve. */
function buildCandleData(): Candle[] {
  const candles: Candle[] = [];
  const total = 104;
  const startPrice = 96;
  const peakPrice = 208;
  let price = startPrice;

  for (let i = 0; i < total; i++) {
    const p = i / (total - 1);
    let trendP: number;

    if (p < 0.26) {
      trendP = 0.12 * (p / 0.26);
    } else if (p < 0.94) {
      const local = (p - 0.26) / (0.94 - 0.26);
      trendP = 0.12 + eased(local) * 0.88;
    } else {
      trendP = 1 - ((p - 0.94) / (1 - 0.94)) * 0.1;
    }

    const trendPrice = startPrice + (peakPrice - startPrice) * trendP;
    const anchorPull = (trendPrice - price) * 0.38;

    let noise: number;

    if (p < 0.26) {
      noise =
        Math.sin(i * 2.6) * 2.2 +
        Math.cos(i * 1.15) * 1.6 +
        (i % 5 === 0 ? -1.8 : 0);
    } else if (p < 0.94) {
      noise =
        Math.sin(i * 2.1) * 1.5 +
        Math.cos(i * 0.85) * 1 +
        (i % 7 === 0 ? -2.6 : 0) +
        (i % 5 === 2 ? -1.5 : 0) +
        (i % 4 === 1 ? -0.9 : 0);
    } else {
      noise = -2.2 - (i % 2) * 1;
    }

    const open = price;
    let close = open + anchorPull + noise;
    if (p >= 0.94 && close > open) close = open - 1.2;

    const { high, low } = assignWicks(open, close, i);

    candles.push({
      i,
      open: Math.round(open * 10) / 10,
      high: Math.round(high * 10) / 10,
      low: Math.round(low * 10) / 10,
      close: Math.round(close * 10) / 10,
    });
    price = close;
  }

  return candles;
}

const CANDLE_DATA = buildCandleData();
const Y_MIN = Math.min(...CANDLE_DATA.map((c) => c.low)) - 22;
const Y_MAX = Math.max(...CANDLE_DATA.map((c) => c.high)) + 22;

function CandlestickLayer({
  data,
  yMin,
  yMax,
  barWidth = 8,
}: {
  data: Candle[];
  yMin: number;
  yMax: number;
  barWidth?: number;
}) {
  const plot = usePlotArea();
  if (!plot || data.length < 2) return null;

  const span = yMax - yMin;
  const xAt = (index: number) =>
    plot.x + (index / (data.length - 1)) * plot.width;
  const yAt = (value: number) =>
    plot.y + plot.height * (1 - (value - yMin) / span);

  return (
    <g>
      {data.map((candle) => {
        const cx = xAt(candle.i);
        const yHigh = yAt(candle.high);
        const yLow = yAt(candle.low);
        const yOpen = yAt(candle.open);
        const yClose = yAt(candle.close);

        const bull = candle.close >= candle.open;
        const color = bull ? "#26a69a" : "#ef5350";
        const bodyTop = Math.min(yOpen, yClose);
        const bodyHeight = Math.max(Math.abs(yClose - yOpen), 2);
        const half = barWidth / 2;

        return (
          <g key={candle.i}>
            <line
              x1={cx}
              y1={yHigh}
              x2={cx}
              y2={yLow}
              stroke={color}
              strokeWidth={1}
            />
            <rect
              x={cx - half}
              y={bodyTop}
              width={barWidth}
              height={bodyHeight}
              fill={color}
            />
          </g>
        );
      })}
    </g>
  );
}

export default function LoginHero() {
  return (
    <div className="relative flex h-full min-h-screen flex-col border-l border-zinc-800 bg-zinc-900">
      <div className="pointer-events-none absolute inset-0 opacity-95">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={CANDLE_DATA}
            margin={{ top: 56, right: 20, bottom: 56, left: 20 }}
          >
            <XAxis
              dataKey="i"
              type="number"
              domain={[-0.5, CANDLE_DATA.length - 0.5]}
              hide
            />
            <YAxis domain={[Y_MIN, Y_MAX]} hide />
            <CandlestickLayer
              data={CANDLE_DATA}
              yMin={Y_MIN}
              yMax={Y_MAX}
              barWidth={6}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="relative z-10 flex flex-1 flex-col justify-between px-10 py-14 lg:px-16 lg:py-16">
        <div>
          <h2 className="max-w-2xl font-sans text-3xl font-semibold leading-none tracking-tight text-zinc-100 lg:text-5xl">
            Inteligencia financiera desde el Corpus de X
          </h2>
          <p className="mt-5 max-w-md font-mono text-xs leading-relaxed text-zinc-500 lg:text-sm">
            Monitoreá Signals relevantes del feed, seguí el mercado y consultá
            con un agente RAG que cita fuentes reales del Corpus.
          </p>
        </div>

        <p className="font-mono text-[10px] text-zinc-600">
          Market data ~15m delayed
        </p>
      </div>
    </div>
  );
}
