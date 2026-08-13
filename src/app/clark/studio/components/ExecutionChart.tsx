"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { spineError } from "@/lib/spine_error";
import { useChartColors } from "../chartColors";
import { KT } from "../theme";
import { ExecutionChartResponse, fundApiClient } from "@/lib/fund_api";

/**
 * Candles for a symbol, with our own fills marked on them.
 *
 * This is the "why did it sell there" view. The candles are the price action a
 * decision was made against; the triangles are fills that actually happened,
 * taken from the event log. Signals that never became fills are deliberately
 * absent — an intention is not a trade, and drawing both invites reading a
 * backtest as a track record.
 *
 * Fills are snapped to the trading day because the bars are daily. A fill
 * outside the fetched window is counted and reported rather than dropped, so
 * "no marks" always means "it did not trade", never "we did not look".
 *
 * Plotly loads dynamically — it is a large bundle and only the 3D risk views
 * and this chart need it.
 */
export function ExecutionChart({ symbol, strategyId, lookbackDays = 180 }: {
  symbol: string;
  strategyId?: string;
  lookbackDays?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const c = useChartColors();
  const [data, setData] = useState<ExecutionChartResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await fundApiClient.getExecutionChart(symbol, strategyId, lookbackDays));
      setErr(null);
    } catch (e: unknown) {
      setErr(spineError(e));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [symbol, strategyId, lookbackDays]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const el = ref.current;
    if (!data?.bars?.has_ohlc || !el) return;
    let cancelled = false;

    (async () => {
      const Plotly = (await import("plotly.js-dist-min")).default as any;
      if (cancelled || !el) return;

      const b = data.bars;
      const traces: any[] = [{
        type: "candlestick",
        x: b.dates,
        open: b.open, high: b.high, low: b.low, close: b.close,
        increasing: { line: { color: c.up }, fillcolor: c.up },
        decreasing: { line: { color: c.down }, fillcolor: c.down },
        name: data.symbol,
        showlegend: false,
      }];

      // Only fills that have a bar to sit on. The rest are counted in the
      // caption instead of being placed somewhere they did not happen.
      const inWin = (data.fills || []).filter((f) => f.in_window);
      const buys = inWin.filter((f) => f.side === "buy");
      const sells = inWin.filter((f) => f.side !== "buy");

      const markTrace = (rows: typeof inWin, isBuy: boolean) => ({
        type: "scatter",
        mode: "markers",
        x: rows.map((f) => f.date),
        y: rows.map((f) => f.price),
        marker: {
          symbol: isBuy ? "triangle-up" : "triangle-down",
          size: 13,
          color: isBuy ? c.up : c.down,
          line: { color: c.surface, width: 1.5 },
        },
        name: isBuy ? "buy" : "sell",
        hovertemplate:
          `<b>${isBuy ? "BUY" : "SELL"}</b> %{customdata[0]} @ $%{y:.2f}` +
          "<br>%{x}<extra></extra>",
        customdata: rows.map((f) => [f.qty]),
      });

      if (buys.length) traces.push(markTrace(buys, true));
      if (sells.length) traces.push(markTrace(sells, false));

      await Plotly.newPlot(el, traces, {
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        font: { color: c.textMuted, size: 10 },
        margin: { l: 48, r: 12, t: 8, b: 32 },
        xaxis: {
          gridcolor: c.grid, zeroline: false,
          rangeslider: { visible: false },
          // Daily bars: collapse weekends so gaps do not read as flat periods.
          rangebreaks: [{ bounds: ["sat", "mon"] }],
        },
        yaxis: { gridcolor: c.grid, zeroline: false, tickprefix: "$" },
        showlegend: buys.length > 0 && sells.length > 0,
        legend: { orientation: "h", y: 1.08, x: 0, font: { size: 10 } },
        hovermode: "closest",
      }, { displayModeBar: false, responsive: true });
    })();

    return () => { cancelled = true; try { (window as any).Plotly?.purge?.(el); } catch { } };
  }, [data, c]);

  if (loading) {
    return <div className={`px-5 py-8 text-sm ${KT.muted}`}>Loading {symbol} bars…</div>;
  }
  if (err) {
    return <div className={`px-5 py-6 text-sm ${KT.down}`}>{err} — chart unavailable.</div>;
  }
  if (!data?.bars?.has_ohlc) {
    return (
      <div className={`px-5 py-6 text-sm ${KT.muted}`}>
        {data?.source || "This source"} returned closes without open/high/low, so
        candles cannot be drawn honestly for {symbol}.
      </div>
    );
  }

  const nMarks = (data.fills || []).filter((f) => f.in_window).length;
  const outside = data.n_fills_outside_window ?? 0;

  return (
    <div>
      <div ref={ref} className="h-[340px] w-full" />
      <p className={`mt-1 px-5 text-[11px] ${KT.muted}`}>
        {data.source} · {data.adjusted
          ? `${data.adjustment} adjusted`
          : "UNADJUSTED — splits appear as price jumps"} ·{" "}
        {nMarks === 0
          ? "no fills in this window — this strategy has not traded this symbol here"
          : `${nMarks} fill${nMarks === 1 ? "" : "s"} marked`}
        {outside > 0 && ` · ${outside} outside the window, not shown`}
      </p>
    </div>
  );
}
