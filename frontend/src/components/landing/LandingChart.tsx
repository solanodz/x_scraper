"use client";

/** Fondo de velas para el landing (capa decorativa). */

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

function eased(t: number): number {
  return t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
}

function hash01(i: number, salt: number): number {
  const x = Math.sin(i * 12.9898 + salt * 78.233) * 43758.5453;
  return x - Math.floor(x);
}

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
  } else {
    high = bodyTop + short * 0.75;
    low = bodyBottom - short * 0.75;
  }

  return { high, low };
}

function buildCandleData(): Candle[] {
  const candles: Candle[] = [];
  const total = 120;
  const startPrice = 110;
  const peakPrice = 198;
  let price = startPrice;

  for (let i = 0; i < total; i++) {
    const p = i / (total - 1);
    let trendP: number;
    if (p < 0.15) {
      trendP = 0.05 * (p / 0.15);
    } else if (p < 0.35) {
      const local = (p - 0.15) / 0.2;
      trendP = 0.05 + eased(local) * 0.3;
    } else if (p < 0.5) {
      const local = (p - 0.35) / 0.15;
      trendP = 0.35 - local * 0.12;
    } else if (p < 0.75) {
      const local = (p - 0.5) / 0.25;
      trendP = 0.23 + eased(local) * 0.6;
    } else if (p < 0.88) {
      const local = (p - 0.75) / 0.13;
      trendP = 0.83 + eased(local) * 0.17;
    } else {
      trendP = 1 - ((p - 0.88) / 0.12) * 0.15;
    }

    const trendPrice = startPrice + (peakPrice - startPrice) * trendP;
    const anchorPull = (trendPrice - price) * 0.3;
    const noise =
      Math.sin(i * 2.05) * 2.0 +
      Math.cos(i * 0.7) * 1.6 +
      Math.sin(i * 4.3) * 0.8 +
      (i % 5 === 0 ? -2.5 : 0) +
      (i % 7 === 0 ? 1.8 : 0);

    const open = price;
    let close = open + anchorPull + noise;
    if (p >= 0.88 && close > open) close = open - 1.1;

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
const Y_MIN = Math.min(...CANDLE_DATA.map((c) => c.low)) - 18;
const Y_MAX = Math.max(...CANDLE_DATA.map((c) => c.high)) + 18;

function CandlestickLayer({
  data,
  yMin,
  yMax,
  barWidth = 6,
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
        const color = bull ? "#34d399" : "#f87171";
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
              opacity={0.85}
            />
            <rect
              x={cx - half}
              y={bodyTop}
              width={barWidth}
              height={bodyHeight}
              fill={color}
              opacity={0.9}
            />
          </g>
        );
      })}
    </g>
  );
}

export default function LandingChart() {
  return (
    <div className="absolute inset-0">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          data={CANDLE_DATA}
          margin={{ top: 8, right: 4, bottom: 8, left: 4 }}
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
            barWidth={4}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
