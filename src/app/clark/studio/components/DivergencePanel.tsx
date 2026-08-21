"use client";

import React, { useCallback, useEffect, useState } from "react";
import { KT } from "../theme";
import { pct } from "../format";
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
 *
 * ARCHIVED ROWS ARE HIDDEN BY DEFAULT (2026-08-21). Measured on the live spine
 * that day: three of the four rows this panel served were archived — Momentum,
 * Mean Reversion and Trend — and the header called all four "deployed". An
 * archived strategy's gap to its backtest is HISTORY; presenting it beside a
 * live one invites a decision about a book position that no longer exists.
 *
 * Hidden, not dropped: the toggle brings them back, the count is always stated,
 * and the spine still serves every row. A surface that silently discards rows
 * is how a reader comes to believe the fund has fewer strategies than it does.
 */

// `pct` moved to ../format.ts (2026-08-20); same body, same default of 1.

export function DivergencePanel({ refreshSignal = 0 }: { refreshSignal?: number }) {
  const [d, setD] = useState<StrategyDivergence | null>(null);
  const [err, setErr] = useState(false);
  const [showArchived, setShowArchived] = useState(false);

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

  const all = d?.rows ?? [];
  // `archived` is optional on the wire: a spine that predates the field serves
  // rows without it, and those must read as LIVE rather than be hidden. A
  // truthy test does exactly that; `!== false` would hide them.
  const archived = all.filter((r) => r.archived === true);
  const rows = showArchived ? all : all.filter((r) => r.archived !== true);
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
            {/* Counted off the rows SHOWN. Quoting the spine's n_deployed here
                would put "0/4 comparable" beside one visible row. */}
            {diverging.length === 0
              ? `${rows.filter((r) => r.comparable).length}/${rows.length} comparable · none diverging`
              : `${diverging.length} diverging`}
          </span>
        )}
      </div>

      {archived.length > 0 && (
        <div className="flex flex-wrap items-baseline gap-x-2 border-b border-[var(--kt-border)] px-5 py-2">
          <span className={`text-[11px] ${KT.muted}`}>
            {archived.length} archived {archived.length === 1 ? "strategy is" : "strategies are"}{" "}
            {showArchived ? "shown below" : "hidden"} — an archived strategy&apos;s gap
            to its backtest is history, not a live comparison.
          </span>
          <button
            type="button"
            onClick={() => setShowArchived((v) => !v)}
            className={`ml-auto font-mono text-[10px] uppercase tracking-[0.1em] ${KT.accent}`}
          >
            {showArchived ? "hide archived" : "include archived"}
          </button>
        </div>
      )}

      {rows.length === 0 ? (
        <div className={`px-5 py-5 text-sm ${KT.muted}`}>
          {archived.length > 0
            ? `No LIVE strategies to compare — all ${archived.length} on record are archived.`
            : "No deployed strategies to compare."}
        </div>
      ) : (
        <ul className="divide-y divide-[var(--kt-border)]">
          {rows.map((r) => {
            const noBacktest = !r.comparable && (r.reason ?? "").includes("no backtest");
            return (
              <li key={r.strategy_id}
                  className={`flex flex-wrap items-baseline gap-x-4 gap-y-1 px-5 py-2.5 text-[12px] ${
                    r.archived ? "opacity-60" : ""}`}>
                <span className="font-medium">{r.name ?? r.strategy_id}</span>
                {r.archived && (
                  <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.sev.warn}`}>
                    archived
                  </span>
                )}
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
