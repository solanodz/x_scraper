import type { IChartApi, IRange, Time } from "lightweight-charts";

/**
 * Bidirectional sync of visible time range (zoom/pan) across N LWC charts.
 * Uses time (not logical indices) so panes with different series warmups stay aligned.
 */
export function bindSyncedTimeScaleGroup(charts: IChartApi[]): () => void {
  const active = charts.filter(Boolean);
  if (active.length < 2) return () => {};

  let syncing = false;

  const applyToOthers = (source: IChartApi, range: IRange<Time>) => {
    syncing = true;
    try {
      for (const chart of active) {
        if (chart === source) continue;
        try {
          chart.timeScale().setVisibleRange(range);
        } catch {
          // Target may not cover the full range yet.
        }
      }
    } finally {
      syncing = false;
    }
  };

  const handlers = active.map((chart) => {
    const handler = (range: IRange<Time> | null) => {
      if (syncing || !range) return;
      applyToOthers(chart, range);
    };
    chart.timeScale().subscribeVisibleTimeRangeChange(handler);
    return { chart, handler };
  });

  // Align all to the first chart once.
  const seed = active[0].timeScale().getVisibleRange();
  if (seed) applyToOthers(active[0], seed);

  return () => {
    for (const { chart, handler } of handlers) {
      chart.timeScale().unsubscribeVisibleTimeRangeChange(handler);
    }
  };
}

/** @deprecated Prefer bindSyncedTimeScaleGroup */
export function bindSyncedTimeScales(
  primary: IChartApi,
  secondary: IChartApi,
): () => void {
  return bindSyncedTimeScaleGroup([primary, secondary]);
}
