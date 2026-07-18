"use client";

import { useMemo } from "react";
import {
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  usePlotArea,
} from "recharts";
import {
  buildFibonacciLevels,
  buildIndicatorChartRows,
  chartYDomain,
  INDICATOR_COLORS,
  type FibonacciLevel,
  type IndicatorChartRow,
} from "@/lib/chartIndicators";
import type { PriceCandle } from "@/lib/types";

interface TickerIndicatorChartProps {
  symbol: string;
  candles: PriceCandle[];
  loading?: boolean;
  error?: string | null;
  className?: string;
}

function formatDateLabel(date: string): string {
  const parsed = new Date(`${date}T12:00:00`);
  if (Number.isNaN(parsed.getTime())) return date.slice(5);
  return parsed.toLocaleDateString("es-AR", { day: "2-digit", month: "short" });
}

function CandlestickLayer({
  data,
  yMin,
  yMax,
  barWidth = 5,
}: {
  data: IndicatorChartRow[];
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
        const bodyHeight = Math.max(Math.abs(yClose - yOpen), 1.5);
        const half = barWidth / 2;

        return (
          <g key={`${candle.date}-${candle.i}`}>
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

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: IndicatorChartRow }>;
}) {
  if (!active || !payload?.[0]?.payload) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded border border-zinc-700 bg-zinc-950/95 px-2 py-1.5 font-mono text-[10px] text-zinc-300 shadow-lg">
      <p className="text-zinc-500">{formatDateLabel(row.date)}</p>
      <p>
        O {row.open.toFixed(2)} · H {row.high.toFixed(2)} · L {row.low.toFixed(2)} · C{" "}
        {row.close.toFixed(2)}
      </p>
      {row.sma20 != null && (
        <p style={{ color: INDICATOR_COLORS.sma20 }}>SMA 20: {row.sma20.toFixed(2)}</p>
      )}
      {row.sma50 != null && (
        <p style={{ color: INDICATOR_COLORS.sma50 }}>SMA 50: {row.sma50.toFixed(2)}</p>
      )}
      {row.donchianUpper != null && row.donchianLower != null && (
        <p style={{ color: INDICATOR_COLORS.donchianUpper }}>
          Donchian 20: {row.donchianLower.toFixed(2)} – {row.donchianUpper.toFixed(2)}
        </p>
      )}
    </div>
  );
}

function FibLegend({ levels }: { levels: FibonacciLevel[] }) {
  if (levels.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2 font-mono text-[9px] text-zinc-500">
      {levels.map((level) => (
        <span key={level.ratio}>
          Fib {level.ratio}:{" "}
          <span className="text-zinc-400">{level.price.toFixed(2)}</span>
        </span>
      ))}
    </div>
  );
}

export default function TickerIndicatorChart({
  symbol,
  candles,
  loading = false,
  error = null,
  className = "h-[380px] w-full",
}: TickerIndicatorChartProps) {
  const rows = useMemo(() => buildIndicatorChartRows(candles), [candles]);
  const fibLevels = useMemo(() => buildFibonacciLevels(candles), [candles]);
  const [yMin, yMax] = useMemo(() => chartYDomain(rows), [rows]);

  if (loading) {
    return (
      <div
        className={`flex items-center justify-center rounded border border-zinc-800 bg-zinc-950/60 ${className}`}
      >
        <p className="font-mono text-xs text-zinc-500">Cargando velas…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div
        className={`flex items-center justify-center rounded border border-zinc-800 bg-zinc-950/60 px-4 ${className}`}
      >
        <p className="text-center font-mono text-xs text-red-400">{error}</p>
      </div>
    );
  }

  if (rows.length < 5) {
    return (
      <div
        className={`flex items-center justify-center rounded border border-zinc-800 bg-zinc-950/60 px-4 ${className}`}
      >
        <p className="text-center font-mono text-xs text-zinc-500">
          Sin datos históricos suficientes para {symbol}.
        </p>
      </div>
    );
  }

  const tickIndexes = [
    0,
    Math.floor((rows.length - 1) * 0.33),
    Math.floor((rows.length - 1) * 0.66),
    rows.length - 1,
  ];

  return (
    <div className="space-y-2">
      <div className={`rounded border border-zinc-800 bg-zinc-950/60 ${className}`}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={rows}
            margin={{ top: 12, right: 12, bottom: 8, left: 4 }}
          >
            <XAxis
              dataKey="i"
              type="number"
              domain={[-0.5, rows.length - 0.5]}
              ticks={tickIndexes}
              tickFormatter={(value) => {
                const row = rows[Number(value)];
                return row ? formatDateLabel(row.date) : "";
              }}
              tick={{ fill: "#71717a", fontSize: 10 }}
              axisLine={{ stroke: "#3f3f46" }}
              tickLine={false}
            />
            <YAxis
              domain={[yMin, yMax]}
              tick={{ fill: "#71717a", fontSize: 10 }}
              axisLine={{ stroke: "#3f3f46" }}
              tickLine={false}
              width={48}
              tickFormatter={(value) => Number(value).toFixed(0)}
            />
            <Tooltip content={<ChartTooltip />} />
            {fibLevels.map((level) => (
              <ReferenceLine
                key={level.ratio}
                y={level.price}
                stroke={INDICATOR_COLORS.fib}
                strokeDasharray="4 4"
                strokeOpacity={0.55}
              />
            ))}
            <Line
              type="monotone"
              dataKey="donchianUpper"
              stroke={INDICATOR_COLORS.donchianUpper}
              strokeWidth={1}
              strokeDasharray="3 3"
              dot={false}
              isAnimationActive={false}
              connectNulls={false}
            />
            <Line
              type="monotone"
              dataKey="donchianLower"
              stroke={INDICATOR_COLORS.donchianLower}
              strokeWidth={1}
              strokeDasharray="3 3"
              dot={false}
              isAnimationActive={false}
              connectNulls={false}
            />
            <Line
              type="monotone"
              dataKey="sma50"
              stroke={INDICATOR_COLORS.sma50}
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
              connectNulls={false}
            />
            <Line
              type="monotone"
              dataKey="sma20"
              stroke={INDICATOR_COLORS.sma20}
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
              connectNulls={false}
            />
            <CandlestickLayer data={rows} yMin={yMin} yMax={yMax} barWidth={5} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-3 font-mono text-[9px] uppercase tracking-wide">
          <span style={{ color: INDICATOR_COLORS.sma20 }}>SMA 20</span>
          <span style={{ color: INDICATOR_COLORS.sma50 }}>SMA 50</span>
          <span style={{ color: INDICATOR_COLORS.donchianUpper }}>Donchian 20</span>
          <span style={{ color: INDICATOR_COLORS.fib }}>Fib 38.2 / 50 / 61.8</span>
        </div>
        <FibLegend levels={fibLevels} />
      </div>
    </div>
  );
}
