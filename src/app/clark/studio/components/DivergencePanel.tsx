"use client";

import React, { useCallback, useEffect, useState } from "react";
import { KT } from "../theme";
import { StrategyDivergence, fundApiClient } from "@/lib/fund_api";

/**
 * Live vs backtest, per deployed strategy — the promise each strategy was
 * deployed on, held against what it has actually done.
 *
 * The honest state for a young fund is "too early to say", and this panel says
 * it in those words instead of hiding the row: a strategy under the 14-day
 * floor shows its age against the floor, because "1.7 of 14 days" tells the
 * operator exactly when the comparison will start meaning something. The
 * engine refuses to annualise before then — a two-day return annualised is a
 * verdict manufactured from noise.
 *
 * A strategy with no backtest on record is the loudest row here. Deployed on
 * what?
 */

const pct = (n?: number | null, dp = 1) => (n == null ? "—" : `${Number(n).toFixed(dp)}%`);

export function DivergencePanel({ refreshSignal = 0 }: { refreshSignal?: number }) {
  const [d, setD] = useState<StrategyDivergence | null>(null);
  const [err, setErr] = useState(false);

  const load = useCallback(async () => {
    try {
      setD(await fundApiClient.getStrategyDivergence());
      setErr(false);
    } catch {
      setErr(true);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 300000); // slow clock — this moves daily, not by the minute
    return () => clearInterval(t);
  }, [load, refreshSignal]);

  if (err) {
    return (
      <div className={KT.panel}>
        <div className="border-b border-[var(--kt-border)] px-5 py-3">
          <span className={KT.label}>Live vs backtest</span>
        </div>
        <div className={`px-5 py-5 text-sm ${KT.sev.warn}`}>
          Divergence unreadable — whether live matches the backtests is unknown.
        </div>
      </div>
    );
  }

  const rows = d?.rows ?? [];
  const diverging = rows.filter((r) => r.diverging);

  return (
    <div className={KT.panel}>
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-[var(--kt-border)] px-5 py-3">
        <div>
          <span className={KT.label}>Live vs backtest</span>
          <div className={`mt-1 text-[11px] ${KT.muted}`}>
            The return each strategy was deployed on, against the return it is
            actually producing.
          </div>
        </div>
        {d && (
          <span className={`font-mono text-[11px] tabular-nums ${diverging.length ? KT.down : KT.muted}`}>
            {diverging.length === 0
              ? `${d.n_comparable}/${d.n_deployed} comparable · none diverging`
              : `${diverging.length} diverging`}
          </span>
        )}
      </div>

      {rows.length === 0 ? (
        <div className={`px-5 py-5 text-sm ${KT.muted}`}>
          No deployed strategies to compare.
        </div>
      ) : (
        <ul className="divide-y divide-[var(--kt-border)]">
          {rows.map((r) => {
            const noBacktest = !r.comparable && (r.reason ?? "").includes("no backtest");
            return (
              <li key={r.strategy_id}
                  className="flex flex-wrap items-baseline gap-x-4 gap-y-1 px-5 py-2.5 text-[12px]">
                <span className="font-medium">{r.name ?? r.strategy_id}</span>
                {r.comparable ? (
                  <span className={`font-mono tabular-nums ${r.diverging ? KT.down : KT.muted}`}>
                    live {pct(r.live_annual_return_pct)} vs backtest {pct(r.backtest_annual_return_pct)}
                    {r.gap_pp != null && <> · gap {r.gap_pp.toFixed(1)}pp</>}
                    {r.diverging && " — outside the band"}
                  </span>
                ) : noBacktest ? (
                  <span className={KT.sev.warn}>{r.reason}</span>
                ) : (
                  <span className={KT.muted}>
                    too early to say
                    {r.live_days != null && (
                      <> — <span className="font-mono tabular-nums">{r.live_days.toFixed(1)}</span> of 14 live days</>
                    )}
                  </span>
                )}
                {r.live_pnl_usd != null && (
                  <span className={`ml-auto font-mono text-[11px] tabular-nums ${
                    r.live_pnl_usd >= 0 ? KT.up : KT.down}`}>
                    {r.live_pnl_usd >= 0 ? "+" : "−"}${Math.abs(r.live_pnl_usd).toFixed(2)} live
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
