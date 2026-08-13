"use client";

import React, { useCallback, useEffect, useState } from "react";
import { ArrowRight, Loader2, Scale } from "lucide-react";
import { spineError } from "@/lib/spine_error";
import { KT } from "../theme";
import { fundApiClient, CandidateEvaluation } from "@/lib/fund_api";

/**
 * The two questions a backtest cannot answer, asked of every Lab run.
 *
 * A tester that reports standalone Sharpe and stops is answering "is this good
 * in isolation" — which is not a question anyone running a fund actually has.
 * The real ones are:
 *
 *   1. IS THIS ALPHA, or beta I could buy for nine basis points? A strategy that
 *      returned 40% in a year the market rose 35% found leverage, not edge.
 *   2. DOES IT IMPROVE THE FUND? A strategy with a worse standalone Sharpe but
 *      low correlation to what is already deployed can help the book more than a
 *      better one that duplicates it. This is the entire argument for running
 *      more than one strategy, and it is invisible in a standalone backtest.
 *
 * Promoting from here carries the evidence with it: the definition, the universe
 * and the backtest that earned it arrive attached to the strategy, and the
 * sizing goes into the rebalance queue for review rather than to the venue.
 */

const pct = (n?: number | null, dp = 1) => (n == null ? "—" : `${Number(n).toFixed(dp)}%`);
const money = (n?: number | null) =>
  n == null ? "—" : `$${Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

const EFFECT_COPY: Record<string, { label: string; tone: string }> = {
  diversifying: { label: "Diversifying", tone: KT.up },
  "return-seeking": { label: "Return-seeking (adds risk)", tone: "text-[var(--kt-warn)]" },
  "risk-reducing": { label: "Risk-reducing", tone: KT.muted },
  neither: { label: "Makes the book worse", tone: KT.down },
};

export function CandidateVerdict({ equityCurve, dates, symbol, template, params, onPromoted }: {
  equityCurve?: number[];
  dates?: string[];
  symbol: string;
  template: string;
  params: Record<string, number>;
  onPromoted?: (planQueued: boolean) => void;
}) {
  const [ev, setEv] = useState<CandidateEvaluation | null>(null);
  const [alloc, setAlloc] = useState(10);
  const [busy, setBusy] = useState(false);
  const [promoting, setPromoting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const evaluate = useCallback(async (allocation: number) => {
    if (!equityCurve?.length || !dates?.length) return;
    setBusy(true);
    setErr(null);
    try {
      setEv(await fundApiClient.evaluateCandidate({
        equity_curve: equityCurve, dates, allocation_pct: allocation,
      }));
    } catch (e: unknown) {
      setErr(spineError(e));
      setEv(null);      // unknown, not empty
    } finally {
      setBusy(false);
    }
  }, [equityCurve, dates]);

  useEffect(() => { setDone(null); evaluate(alloc); }, [evaluate]);   // re-run when the run changes

  const promote = async () => {
    setPromoting(true);
    setErr(null);
    try {
      const res = await fundApiClient.promoteCandidate({
        name: `${template.toUpperCase()} · ${symbol.toUpperCase()}`,
        symbols: [symbol.toUpperCase()],
        definition: { type: template, ...params },
        allocation_pct: alloc,
      });
      setDone(res.queued
        ? "Queued for review in Allocate — no order has been placed."
        : `Strategy registered, but sizing could not be queued: ${res.reason}`);
      onPromoted?.(!!res.queued);
    } catch (e: unknown) {
      setErr(spineError(e));
    } finally {
      setPromoting(false);
    }
  };

  if (!equityCurve?.length) return null;

  const f = ev?.factors;
  const fit = ev?.fit;
  const effect = fit?.effect ? EFFECT_COPY[fit.effect] : null;

  return (
    <div className={`${KT.panel} mt-4`}>
      <div className="flex items-center justify-between border-b border-[var(--kt-border)] px-5 py-3">
        <div>
          <span className={KT.label}>Is it worth owning?</span>
          <div className={`mt-1 text-[11px] ${KT.muted}`}>
            Alpha vs factor beta, and what it would do to the fund
          </div>
        </div>
        {busy && <Loader2 size={14} className={`animate-spin ${KT.muted}`} />}
      </div>

      {err && <div className={`px-5 py-3 text-sm ${KT.down}`}>{err}</div>}

      <div className="grid gap-0 lg:grid-cols-2">
        {/* --- alpha or beta --- */}
        <div className="border-b border-[var(--kt-border)] lg:border-b-0 lg:border-r">
          <div className={`px-5 pt-4 ${KT.label}`}>Alpha or beta</div>
          {!f ? (
            <div className={`px-5 py-6 text-sm ${KT.muted}`}>
              {busy ? "Measuring…" : "—"}
            </div>
          ) : !f.measurable ? (
            <div className={`px-5 py-6 text-sm ${KT.sev.warn}`}>
              Not measurable — {f.reason}.
            </div>
          ) : (
            <>
              <div className="grid grid-cols-3 gap-2 px-5 pt-2">
                <div>
                  <div className={`font-mono text-lg font-light ${
                    f.alpha_significant
                      ? ((f.alpha_annual_pct ?? 0) > 0 ? KT.up : KT.down) : KT.muted}`}>
                    {pct(f.alpha_annual_pct)}
                  </div>
                  <div className={`text-[11px] ${KT.muted}`}>
                    alpha · t {f.alpha_t_stat?.toFixed(1)}
                  </div>
                </div>
                <div>
                  <div className="font-mono text-lg font-light">
                    {((f.r_squared ?? 0) * 100).toFixed(0)}%
                  </div>
                  <div className={`text-[11px] ${KT.muted}`}>is the factors</div>
                </div>
                <div>
                  <div className="font-mono text-lg font-light">
                    {((f.idiosyncratic_share ?? 0) * 100).toFixed(0)}%
                  </div>
                  <div className={`text-[11px] ${KT.muted}`}>is its own</div>
                </div>
              </div>
              <ul className="px-5 py-3 text-sm">
                {(f.factors ?? []).slice(0, 4).map((row) => (
                  <li key={row.key} className="flex items-baseline gap-2 py-0.5">
                    <span className={`w-20 text-[11px] ${row.significant ? "" : KT.muted}`}>
                      {row.label}
                    </span>
                    <span className={`font-mono tabular-nums ${row.significant ? "" : KT.muted}`}>
                      {row.beta >= 0 ? "+" : ""}{row.beta.toFixed(2)}
                    </span>
                    <span className={`ml-auto font-mono text-[11px] ${KT.muted}`}>
                      t {row.t_stat >= 0 ? "+" : ""}{row.t_stat.toFixed(1)}
                    </span>
                  </li>
                ))}
              </ul>
              <div className={`space-y-1 px-5 pb-4 text-[11px] ${KT.muted}`}>
                {(f.verdict ?? []).slice(-1).map((l, i) => <p key={i}>{l}</p>)}
              </div>
            </>
          )}
        </div>

        {/* --- portfolio fit --- */}
        <div>
          <div className="flex items-center justify-between px-5 pt-4">
            <span className={KT.label}>Fit with the fund</span>
            <div className="flex items-center gap-2">
              <input
                type="range" min={1} max={40} step={1} value={alloc}
                onChange={(e) => setAlloc(Number(e.target.value))}
                onMouseUp={() => evaluate(alloc)}
                onTouchEnd={() => evaluate(alloc)}
                className="w-24 accent-[var(--kt-accent)]"
                aria-label="candidate allocation percent"
              />
              <span className="w-10 text-right font-mono text-[11px]">{alloc}%</span>
            </div>
          </div>
          {!fit ? (
            <div className={`px-5 py-6 text-sm ${KT.muted}`}>{busy ? "Measuring…" : "—"}</div>
          ) : !fit.measurable ? (
            <div className={`px-5 py-6 text-sm ${KT.sev.warn}`}>
              Not measurable — {fit.reason}.
            </div>
          ) : (
            <>
              <div className="px-5 pt-3">
                {effect && (
                  <div className={`text-sm font-medium ${effect.tone}`}>{effect.label}</div>
                )}
                <div className={`mt-2 space-y-1 text-sm`}>
                  <div className="flex items-baseline gap-2">
                    <span className={`w-24 ${KT.label}`}>Book vol</span>
                    <span className={`font-mono tabular-nums ${KT.muted}`}>
                      {pct(fit.before?.vol_pct)}
                    </span>
                    <span className={KT.muted}>→</span>
                    <span className={`font-mono tabular-nums ${
                      (fit.after?.vol_pct ?? 0) > (fit.before?.vol_pct ?? 0) ? KT.down : KT.up}`}>
                      {pct(fit.after?.vol_pct)}
                    </span>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className={`w-24 ${KT.label}`}>Book Sharpe</span>
                    <span className={`font-mono tabular-nums ${KT.muted}`}>
                      {fit.before?.sharpe_annual?.toFixed(2) ?? "—"}
                    </span>
                    <span className={KT.muted}>→</span>
                    <span className={`font-mono tabular-nums ${
                      (fit.after?.sharpe_annual ?? 0) >= (fit.before?.sharpe_annual ?? 0) ? KT.up : KT.down}`}>
                      {fit.after?.sharpe_annual?.toFixed(2) ?? "—"}
                    </span>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className={`w-24 ${KT.label}`}>Book ES</span>
                    <span className={`font-mono tabular-nums ${KT.muted}`}>
                      {money(fit.before?.expected_shortfall_usd)}
                    </span>
                    <span className={KT.muted}>→</span>
                    <span className={`font-mono tabular-nums ${
                      (fit.after?.expected_shortfall_usd ?? 0) > (fit.before?.expected_shortfall_usd ?? 0)
                        ? KT.down : KT.up}`}>
                      {money(fit.after?.expected_shortfall_usd)}
                    </span>
                  </div>
                </div>
              </div>

              <div className="px-5 pt-3">
                <div className={KT.label}>Correlation to what we already run</div>
                <ul className="mt-1 text-sm">
                  {(fit.per_strategy ?? []).map((p) => (
                    <li key={p.strategy_id} className="flex items-baseline gap-2 py-0.5">
                      <span className="truncate text-[11px]">{p.name}</span>
                      <span className={`ml-auto font-mono tabular-nums ${
                        p.correlation > 0.8 ? KT.down
                          : p.correlation > 0.5 ? "text-[var(--kt-warn)]" : KT.up}`}>
                        {p.correlation >= 0 ? "+" : ""}{p.correlation.toFixed(2)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className={`space-y-1 px-5 py-3 text-[11px] ${KT.muted}`}>
                {(fit.verdict ?? []).slice(1, 3).map((l, i) => <p key={i}>· {l}</p>)}
              </div>
            </>
          )}
        </div>
      </div>

      {/* --- promote --- */}
      <div className="flex flex-wrap items-center gap-3 border-t border-[var(--kt-border)] px-5 py-3">
        {/* Portfolio fit is ADVICE, not a precondition. Requiring it made this
            button permanently dead on an empty book — i.e. exactly when you are
            trying to put on the fund's first strategy. */}
        <button
          onClick={promote}
          disabled={promoting || !!done}
          className={`flex h-8 items-center ${KT.btn} disabled:opacity-40`}
        >
          {promoting ? <Loader2 size={14} className="mr-1.5 animate-spin" />
                     : <Scale size={14} className="mr-1.5" />}
          Propose at {alloc}%
        </button>
        {done ? (
          <span className={`flex items-center gap-1 text-[11px] ${KT.accent}`}>
            {done} <ArrowRight size={11} />
          </span>
        ) : (
          <span className={`text-[11px] ${KT.muted}`}>
            Registers the strategy with this backtest attached and queues the sizing
            for review in Allocate. Places no order.
          </span>
        )}
      </div>
    </div>
  );
}
