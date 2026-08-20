"use client";

import React, { useCallback, useEffect, useState } from "react";
import { KT } from "../theme";
import { TcaResponse, fundApiClient } from "@/lib/fund_api";

/**
 * What trading actually cost, against what the backtests assumed it cost.
 *
 * The backtester charges a couple of basis points a side and reports a Sharpe
 * ratio net of it. Nothing checked that against a fill until now. This panel is
 * the check, and it is deliberately blunt about the gap, because a strategy
 * that flips several times a day is exactly where a wrong cost assumption does
 * the most damage — the error compounds once per trade.
 *
 * Sample size sits next to the number rather than in a footnote. Two fills is
 * an observation, and an observation rendered like an estimate is how a number
 * ends up in a memo it cannot support.
 */

const bps = (n?: number | null, dp = 1) =>
  n == null ? "—" : `${n > 0 ? "+" : ""}${Number(n).toFixed(dp)}bp`;
const secs = (n?: number | null) =>
  n == null ? "—" : n < 60 ? `${Math.round(n)}s` : `${(n / 60).toFixed(1)}m`;

export function ExecutionQuality({ refreshSignal = 0 }: { refreshSignal?: number }) {
  const [tca, setTca] = useState<TcaResponse | null>(null);
  const [err, setErr] = useState(false);

  const load = useCallback(async () => {
    try {
      setTca(await fundApiClient.getTca(200));
      setErr(false);
    } catch {
      setErr(true);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [load, refreshSignal]);

  if (err) {
    return (
      <div className={KT.panel}>
        <div className="border-b border-[var(--kt-border)] px-5 py-3">
          <span className={KT.label}>Execution quality</span>
        </div>
        <div className={`px-5 py-6 text-sm ${KT.sev.warn}`}>
          Cost analysis unavailable — realised trading cost unknown.
        </div>
      </div>
    );
  }

  const s = tca?.summary;
  const v = s?.vs_assumption ?? null;
  // Positive excess = paying more than the backtests were told to expect.
  const over = v != null && v.excess_bps > 0;

  return (
    <div className={KT.panel}>
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-[var(--kt-border)] px-5 py-3">
        <div>
          <span className={KT.label}>Execution quality</span>
          <div className={`mt-1 text-[11px] ${KT.muted}`}>
            Realised cost per fill, measured against the decision price on the
            approval card.
          </div>
        </div>
        {v && (
          <div className="text-right">
            <div className={`font-mono text-[15px] tabular-nums ${over ? KT.down : KT.up}`}>
              {bps(v.realised_bps_per_side)}
            </div>
            <div className={`text-[10px] ${KT.muted}`}>
              vs {bps(v.assumed_bps_per_side, 0)} assumed
            </div>
          </div>
        )}
      </div>

      {!s || s.orders === 0 ? (
        <div className={`px-5 py-6 text-sm ${KT.muted}`}>
          No fills yet — nothing to measure. Cost is computed from the order
          lifecycle, so it appears as soon as the first order settles.
        </div>
      ) : !s.informative?.measurable ? (
        // Fills exist, but none on a venue that can measure cost. Rendering
        // the all-venue stats here would quote the paper venue's structural
        // zeros as a cost measurement (COO triage #2 Batch B, CEO-accepted).
        <div className={`px-5 py-6 text-sm ${KT.sev.warn}`}>
          {s.informative?.reason ??
            "No fills on a venue that can measure execution cost."}
          {" "}({s.orders} fill{s.orders === 1 ? "" : "s"} on record, none
          informative.)
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 px-5 py-3 sm:grid-cols-4">
            {/* Informative fills ONLY: the paper venue fills at its own
                quote, so every paper fill reads 0.00bps by construction and
                drags the headline toward "we trade for free". */}
            <Stat label="Informative fills"
                  value={`${s.informative.orders} of ${s.orders}`} />
            <Stat label="Median cost" value={bps(s.informative.total_bps.median)} />
            <Stat label="Worst fill" value={bps(s.informative.total_bps.worst)}
                  tone={(s.informative.total_bps.worst ?? 0) > 0 ? "down" : undefined} />
            {/* "Paid so far: $-0.77" read as an apology — a negative cost is
                money the fills GAVE us. Name the direction instead of asking
                the reader to parse a signed dollar figure. */}
            <Stat label="Net cost so far"
                  value={s.realised_cost_usd == null ? "—"
                    : s.realised_cost_usd < 0
                      ? `−$${Math.abs(s.realised_cost_usd).toFixed(2)} in our favor`
                      : `$${s.realised_cost_usd.toFixed(2)}`} />
          </div>
          <div className={`px-5 pb-2 text-[10px] ${KT.muted}`}>
            Counting {s.informative.venues_counted.join(", ") || "no venue"} ·
            excluding {s.informative.excluded_orders} paper-venue fill
            {s.informative.excluded_orders === 1 ? "" : "s"} (a paper fill's
            slippage is zero by construction, not by skill).
          </div>

          {/* The split only exists for orders placed after arrival-price
              capture. Saying so beats showing an empty pair of numbers. */}
          {s.split_available > 0 ? (
            <div className="grid grid-cols-2 gap-x-6 border-t border-[var(--kt-border)] px-5 py-3">
              <Stat label="Delay — market moved while deciding"
                    value={bps(s.delay_bps.mean)} />
              <Stat label="Execution — cost of crossing (informative venues)"
                    value={bps(s.informative.execution_bps.mean)} />
            </div>
          ) : (
            <div className={`border-t border-[var(--kt-border)] px-5 py-2 text-[11px] ${KT.muted}`}>
              Delay/execution split needs an arrival price, captured from this
              session onward. Earlier fills report a total only — an unknown
              delay cost is not a zero one.
            </div>
          )}

          <div className="border-t border-[var(--kt-border)] px-5 py-2">
            <div className={`text-[11px] ${KT.muted}`}>
              Median approval wait{" "}
              <span className="font-mono tabular-nums">
                {secs(s.approval_latency_s.median)}
              </span>
              {" · "}longest{" "}
              <span className="font-mono tabular-nums">
                {secs(s.approval_latency_s.worst)}
              </span>
              . The market moves during it, and that movement is a real cost.
            </div>
          </div>

          {v && !v.reliable && (
            <div className={`border-t border-[var(--kt-border)] px-5 py-2 text-[11px] ${KT.sev.warn}`}>
              {v.sample} fill{v.sample === 1 ? "" : "s"} — an observation, not an
              estimate. Do not re-cost a backtest on this yet.
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "down" }) {
  return (
    <div>
      <div className={`text-[10px] uppercase tracking-wide ${KT.muted}`}>{label}</div>
      <div className={`font-mono text-[13px] tabular-nums ${tone === "down" ? KT.down : ""}`}>
        {value}
      </div>
    </div>
  );
}
