"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle, Check, ChevronDown, ChevronRight, Loader2, RotateCcw, Scale, X,
} from "lucide-react";
import { spineError } from "@/lib/spine_error";
import { KT } from "../theme";
import { money, pct } from "../format";
import {
  fundApiClient,
  RebalancePlan,
  RiskWhatIf,
  StrategyView,
} from "@/lib/fund_api";

/**
 * REBALANCE — proposing, analysing and pushing a change to the book's shape.
 *
 * Lives inside Allocate rather than on its own route: the targets you are
 * changing are on this page, and moving to a separate screen means deciding
 * without the numbers you are deciding about in front of you.
 *
 * Two halves, matching the two jobs:
 *
 *   COMPOSE  — sliders, plus the consequence. Not a form that submits weights:
 *              resizing strategies changes fund *mechanics* (how independent the
 *              bets are, how much is at risk on a bad day), and none of that is
 *              visible in a percentage field.
 *   QUEUE    — plans awaiting a human, each decorated with what has changed
 *              since it was written. The gap between deciding and doing is where
 *              analysis happens; it is also where prices move, so the queue says
 *              so rather than letting stale analysis look current.
 *
 * Approving re-prices and re-gates every order server-side. Nothing here
 * bypasses the pre-trade gate.
 */

// Formatters: ../format.ts (2026-08-20 consolidation). This file's retired
// `money` defaulted to ZERO decimals, so every call site here passes 0
// explicitly — the shared default is 2 and the rendering must not change.
const money0 = (n?: number | null) => money(n, 0);

/** Lower is better for risk; higher is better for diversification. */
function Delta({ from, to, unit = "", betterWhen }: {
  from?: number | null; to?: number | null; unit?: string; betterWhen: "higher" | "lower";
}) {
  if (from == null || to == null) return <span className={KT.muted}>—</span>;
  const d = to - from;
  if (Math.abs(d) < 0.005) return <span className={KT.muted}>no change</span>;
  return (
    <span className={(betterWhen === "higher" ? d > 0 : d < 0) ? KT.up : KT.down}>
      {d > 0 ? "+" : ""}{d.toFixed(2)}{unit}
    </span>
  );
}

function Mechanic({ label, from, to, unit, betterWhen, format, note }: {
  label: string; from?: number | null; to?: number | null; unit?: string;
  betterWhen: "higher" | "lower"; format: (n?: number | null) => string; note?: string;
}) {
  return (
    <div className="border-t border-[var(--kt-border)] px-5 py-2.5">
      <div className="flex items-baseline gap-3">
        <span className={`${KT.label} flex-1`}>{label}</span>
        <span className={`w-20 text-right font-mono tabular-nums text-sm ${KT.muted}`}>{format(from)}</span>
        <span className={KT.muted}>→</span>
        <span className="w-20 text-right font-mono tabular-nums text-sm text-[var(--kt-text-strong)]">{format(to)}</span>
        <span className="w-24 text-right font-mono tabular-nums text-[11px]">
          <Delta from={from} to={to} unit={unit} betterWhen={betterWhen} />
        </span>
      </div>
      {note && <p className={`mt-1 text-[11px] ${KT.muted}`}>{note}</p>}
    </div>
  );
}

function OrderList({ orders, title }: { orders: RebalancePlan["orders"]; title?: string }) {
  if (!orders?.length) return null;
  return (
    <div>
      {title && <div className={`px-5 pt-3 ${KT.label}`}>{title}</div>}
      <ul className="px-5 py-2">
        {orders.map((o, i) => (
          <li key={`${o.symbol}-${i}`} className="flex flex-wrap items-baseline gap-x-3 py-1 text-sm">
            <span className={`w-10 font-medium uppercase ${o.side === "buy" ? KT.up : KT.down}`}>
              {o.side}
            </span>
            <span className="w-14 font-semibold">{o.symbol}</span>
            <span className={`font-mono tabular-nums ${KT.muted}`}>{o.qty}</span>
            <span className={`font-mono tabular-nums text-[11px] ${KT.muted}`}>
              @ ${o.est_price}
            </span>
            <span className="ml-auto font-mono tabular-nums">{money0(o.notional_usd)}</span>
            {o.breaches?.length ? (
              <span className={`w-full text-[11px] ${KT.down}`}>{o.breaches.join("; ")}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** One queued plan: the evidence, what has changed since, and the two actions. */
function PlanCard({ plan, onDone }: { plan: RebalancePlan; onDone: () => void }) {
  const [open, setOpen] = useState(true);
  const [busy, setBusy] = useState<null | "approve" | "decline">(null);
  const [err, setErr] = useState<string | null>(null);
  const m = plan.mechanics;

  const act = async (what: "approve" | "decline") => {
    setBusy(what);
    setErr(null);
    try {
      if (what === "approve") await fundApiClient.approveRebalance(plan.plan_id!, "rushi");
      else await fundApiClient.declineRebalance(plan.plan_id!, "rushi");
      onDone();
    } catch (e: unknown) {
      setErr(spineError(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className={`${KT.inset} overflow-hidden`}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-5 py-3 text-left"
      >
        {open ? <ChevronDown size={14} className={KT.muted} /> : <ChevronRight size={14} className={KT.muted} />}
        <span className="text-sm font-medium">
          {plan.orders.length} order{plan.orders.length === 1 ? "" : "s"} ·{" "}
          {money0(plan.turnover_usd)} turnover
        </span>
        <span className={`text-[11px] ${KT.muted}`}>
          by {plan.proposed_by}
          {plan.age_minutes != null &&
            ` · ${plan.age_minutes < 60
              ? `${plan.age_minutes.toFixed(0)}m ago`
              : `${(plan.age_minutes / 60).toFixed(1)}h ago`}`}
        </span>
        {(plan.warnings?.length ?? 0) > 0 && (
          <span className={`ml-auto flex items-center gap-1 text-[11px] ${KT.sev.warn}`}>
            <AlertTriangle size={12} /> {plan.warnings!.length}
          </span>
        )}
      </button>

      {open && (
        <div className="border-t border-[var(--kt-border)]">
          {/* What changed while this sat in the queue — the reason a queue needs
              decorating at read time rather than trusting the snapshot. */}
          {(plan.warnings?.length ?? 0) > 0 && (
            <div className="space-y-1 px-5 py-3">
              {plan.warnings!.map((w, i) => (
                <p key={i} className={`flex gap-2 text-[11px] ${KT.sev.warn}`}>
                  <AlertTriangle size={12} className="mt-0.5 shrink-0" /> {w}
                </p>
              ))}
            </div>
          )}

          {plan.note && (
            <p className={`px-5 pb-2 text-sm ${KT.body}`}>&ldquo;{plan.note}&rdquo;</p>
          )}

          <OrderList orders={plan.orders} title="Orders" />

          {m?.before && m?.after && (
            <div className="mt-1">
              <div className={`px-5 pt-2 ${KT.label}`}>Fund mechanics at proposal</div>
              <Mechanic label="Effective bets" from={m.before.effective_bets} to={m.after.effective_bets}
                        betterWhen="higher" format={(n) => (n == null ? "—" : n.toFixed(2))} />
              <Mechanic label="Book volatility" from={m.before.portfolio_vol_pct} to={m.after.portfolio_vol_pct}
                        unit="pp" betterWhen="lower" format={(n) => pct(n)} />
              <Mechanic label="Expected shortfall" from={m.before.expected_shortfall_usd}
                        to={m.after.expected_shortfall_usd} betterWhen="lower" format={(n) => money0(n)} />
              <Mechanic label="Gross exposure" from={m.before.gross_exposure_pct_of_nav}
                        to={m.after.gross_exposure_pct_of_nav} unit="pp" betterWhen="lower" format={(n) => pct(n)} />
            </div>
          )}
          {m && m.measurable === false && (
            <p className={`px-5 py-2 text-[11px] ${KT.sev.warn}`}>
              Risk mechanics were not measurable when this was proposed — {m.reason}.
            </p>
          )}

          <div className={`border-t border-[var(--kt-border)] px-5 py-2 text-[11px] ${KT.muted}`}>
            Cash after {pct(plan.cash_after_pct)} ({money0(plan.cash_after_usd)}). Approving
            re-prices and re-gates every order — sizes may differ from those shown.
          </div>

          {err && <div className={`px-5 py-2 text-[11px] ${KT.down}`}>{err}</div>}

          <div className="flex gap-2 border-t border-[var(--kt-border)] px-5 py-3">
            <button onClick={() => act("approve")} disabled={busy !== null}
                    className={`flex h-8 items-center ${KT.btn} disabled:opacity-50`}>
              {busy === "approve" ? <Loader2 size={14} className="mr-1.5 animate-spin" />
                                  : <Check size={14} className="mr-1.5" />}
              Approve &amp; push
            </button>
            <button onClick={() => act("decline")} disabled={busy !== null}
                    className={`flex h-8 items-center ${KT.btnGhost} disabled:opacity-50`}>
              <X size={14} className="mr-1.5" /> Decline
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export function RebalancePanel({ strategies, navUsd, onCommitted }: {
  strategies: StrategyView[];
  /** null = NAV could not be read. The dollar previews below render "—" for it
   *  rather than sizing a proposed trade against a NAV of zero (defect C3). */
  navUsd: number | null;
  onCommitted: () => void;
}) {
  const [composing, setComposing] = useState(false);
  const [targets, setTargets] = useState<Record<string, number>>({});
  const [initial, setInitial] = useState<Record<string, number>>({});
  const [whatIf, setWhatIf] = useState<RiskWhatIf | null>(null);
  const [preview, setPreview] = useState<RebalancePlan | null>(null);
  const [pending, setPending] = useState<RebalancePlan[] | null>(null);
  const [computing, setComputing] = useState(false);
  const [proposing, setProposing] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadQueue = useCallback(async () => {
    try {
      setPending((await fundApiClient.getPendingRebalances()).pending || []);
    } catch {
      setPending(null);        // unknown, not empty
    }
  }, []);

  useEffect(() => { loadQueue(); }, [loadQueue]);

  useEffect(() => {
    const t: Record<string, number> = {};
    strategies.forEach((s) => { t[s.strategy_id] = s.allocation_pct ?? 0; });
    setTargets(t);
    setInitial(t);
  }, [strategies]);

  // Debounced: each recompute reads a year of market history per holding.
  useEffect(() => {
    if (!composing || !Object.keys(targets).length) return;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      setComputing(true);
      try {
        const [w, p] = await Promise.all([
          fundApiClient.riskWhatIf(targets),
          fundApiClient.previewRebalance(targets).catch(() => null),
        ]);
        setWhatIf(w);
        setPreview(p);
        setErr(null);
      } catch (e: unknown) {
        setErr(spineError(e));
        setWhatIf(null);
      } finally {
        setComputing(false);
      }
    }, 450);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [targets, composing]);

  const totalTarget = useMemo(
    () => Object.values(targets).reduce((a, b) => a + (b || 0), 0), [targets]);
  const impliedCash = 100 - totalTarget;
  const dirty = useMemo(
    () => Object.keys(targets).some((k) => Math.abs((targets[k] ?? 0) - (initial[k] ?? 0)) > 0.05),
    [targets, initial]);

  const propose = async () => {
    setProposing(true);
    setErr(null);
    try {
      await fundApiClient.proposeRebalance(targets, "rushi", note || undefined);
      setComposing(false);
      setNote("");
      await loadQueue();
    } catch (e: unknown) {
      setErr(spineError(e));
    } finally {
      setProposing(false);
    }
  };

  const before = whatIf?.before;
  const after = whatIf?.after;
  const queue = pending ?? [];

  return (
    <div className={`mt-6 ${KT.panel}`}>
      <div className="flex items-center justify-between border-b border-[var(--kt-border)] px-5 py-3">
        <div>
          <span className={KT.label}>Rebalance</span>
          <div className={`mt-1 text-[11px] ${KT.muted}`}>
            {pending === null
              ? "queue unavailable — cannot confirm whether plans are waiting"
              : queue.length > 0
                ? `${queue.length} plan${queue.length === 1 ? "" : "s"} awaiting review`
                : "no plans awaiting review"}
          </div>
        </div>
        {!composing ? (
          <button onClick={() => setComposing(true)} disabled={strategies.length === 0}
                  className={`flex h-8 items-center ${KT.btnGhost} disabled:opacity-40`}>
            <Scale size={14} className="mr-1.5" /> Compose a plan
          </button>
        ) : (
          <div className="flex gap-2">
            <button onClick={() => { setTargets(initial); setWhatIf(null); setPreview(null); }}
                    disabled={!dirty} className={`flex h-8 items-center ${KT.btnGhost} disabled:opacity-40`}>
              <RotateCcw size={14} className="mr-1.5" /> Reset
            </button>
            <button onClick={() => { setComposing(false); setTargets(initial); }}
                    className={`flex h-8 items-center ${KT.btnGhost}`}>
              Cancel
            </button>
          </div>
        )}
      </div>

      {err && <div className={`px-5 py-3 text-sm ${KT.down}`}>{err}</div>}

      {/* ---- compose ---- */}
      {composing && (
        <div className="grid gap-6 border-b border-[var(--kt-border)] px-5 py-4 lg:grid-cols-2">
          <div className="space-y-5">
            {strategies.map((s) => {
              const t = targets[s.strategy_id] ?? 0;
              const changed = Math.abs(t - (initial[s.strategy_id] ?? 0)) > 0.05;
              return (
                <div key={s.strategy_id}>
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="text-sm font-medium">{s.name}</span>
                    <span className={`font-mono tabular-nums text-sm ${changed ? KT.accent : KT.muted}`}>
                      {t.toFixed(1)}%
                    </span>
                  </div>
                  <input type="range" min={0} max={100} step={0.5} value={t}
                         onChange={(e) => setTargets((p) => ({ ...p, [s.strategy_id]: Number(e.target.value) }))}
                         className="mt-2 w-full accent-[var(--kt-accent)]"
                         aria-label={`${s.name} target percent`} />
                  <div className={`mt-1 flex justify-between text-[11px] ${KT.muted}`}>
                    <span>was {pct(initial[s.strategy_id])} · {pct(s.actual_pct)} actual</span>
                    <span className="font-mono">
                      {money0(navUsd == null ? null : (navUsd * t) / 100)}
                    </span>
                  </div>
                </div>
              );
            })}

            <div className={`${KT.inset} p-3`}>
              <div className="flex items-baseline justify-between text-sm">
                <span className={KT.label}>Allocated</span>
                <span className={`font-mono tabular-nums ${totalTarget > 100 ? KT.down : ""}`}>
                  {pct(totalTarget)}
                </span>
              </div>
              <div className="mt-1 flex items-baseline justify-between text-sm">
                <span className={KT.label}>Implied cash</span>
                <span className={`font-mono tabular-nums ${impliedCash < 5 ? KT.down : KT.muted}`}>
                  {pct(impliedCash)} ·{" "}
                  {money0(navUsd == null ? null : (navUsd * impliedCash) / 100)}
                </span>
              </div>
              {totalTarget > 100 && (
                <p className={`mt-2 text-[11px] ${KT.down}`}>
                  Over 100% of NAV — this book has no leverage, so it cannot be filled.
                </p>
              )}
              {impliedCash < 5 && impliedCash >= 0 && (
                <p className={`mt-2 text-[11px] ${KT.sev.warn}`}>
                  Below the 5% cash floor — the pre-trade gate will reject the buys that
                  take cash under it, so this would only partly fill.
                </p>
              )}
            </div>

            {(preview?.limit_warnings?.length ?? 0) > 0 && (
              <div className="space-y-1">
                {preview!.limit_warnings!.map((w, i) => (
                  <p key={i} className={`flex gap-2 text-[11px] ${KT.sev.warn}`}>
                    <AlertTriangle size={12} className="mt-0.5 shrink-0" /> {w}
                  </p>
                ))}
              </div>
            )}

            <div>
              <input value={note} onChange={(e) => setNote(e.target.value)}
                     placeholder="Why this change? (optional, kept in the audit trail)"
                     className={`${KT.input} w-full`} />
              {/* Enablement follows the ORDERS, not whether a slider moved.
                  Gating on "did you change a target" made this dead in the one
                  case that matters most: targets already set at 25/25/25 against
                  a book that is 0% invested, i.e. the fund's opening trade. What
                  matters is drift from ACTUAL, which is exactly what the preview
                  computes. */}
              <button onClick={propose}
                      disabled={proposing || !preview?.orders?.length || totalTarget > 100}
                      className={`mt-2 flex h-9 w-full items-center justify-center ${KT.btn} disabled:opacity-40`}>
                {proposing ? <Loader2 size={14} className="mr-1.5 animate-spin" /> : null}
                {preview?.orders?.length
                  ? `Queue ${preview.orders.length} order${preview.orders.length === 1 ? "" : "s"} for review`
                  : computing ? "Measuring…"
                  : "Book already matches these targets — nothing to trade"}
              </button>
            </div>
          </div>

          {/* consequence */}
          <div className={KT.inset}>
            <div className="flex items-center justify-between px-5 py-3">
              <span className={KT.label}>Fund mechanics</span>
              {computing && <Loader2 size={14} className={`animate-spin ${KT.muted}`} />}
            </div>
            {!whatIf ? (
              <div className={`px-5 pb-6 text-sm ${KT.muted}`}>
                {computing ? "Measuring…" : "Move a target to see the effect."}
              </div>
            ) : !whatIf.measurable ? (
              <div className={`px-5 pb-6 text-sm ${KT.sev.warn}`}>
                Not measurable — {whatIf.reason}. This is not an all-clear.
              </div>
            ) : (
              <>
                <Mechanic label="Effective bets" from={before?.effective_bets} to={after?.effective_bets}
                          betterWhen="higher" format={(n) => (n == null ? "—" : n.toFixed(2))}
                          note="Independent positions after correlation. Unchanged by cash — holding more of it does not make the rest less alike." />
                <Mechanic label="Book volatility" from={before?.portfolio_vol_pct} to={after?.portfolio_vol_pct}
                          unit="pp" betterWhen="lower" format={(n) => pct(n)} />
                <Mechanic label="If correlations → 1" from={before?.stressed_vol_pct} to={after?.stressed_vol_pct}
                          unit="pp" betterWhen="lower" format={(n) => pct(n)}
                          note="The crisis case, where diversification stops working." />
                <Mechanic label="Expected shortfall 97.5%" from={before?.expected_shortfall_usd}
                          to={after?.expected_shortfall_usd} betterWhen="lower" format={(n) => money0(n)}
                          note="Average loss on the worst 2.5% of days, from this book's own returns." />
                <Mechanic label="Gross exposure" from={before?.gross_exposure_pct_of_nav}
                          to={after?.gross_exposure_pct_of_nav} unit="pp" betterWhen="lower" format={(n) => pct(n)} />
                {preview?.orders?.length ? <OrderList orders={preview.orders} title="Orders this implies" /> : null}
                <p className={`border-t border-[var(--kt-border)] px-5 py-2 text-[11px] ${KT.muted}`}>
                  {whatIf.assumption}
                </p>
              </>
            )}
          </div>
        </div>
      )}

      {/* ---- queue ---- */}
      {pending === null ? (
        <div className={`px-5 py-6 text-sm ${KT.sev.warn}`}>
          Rebalance queue unreachable — cannot confirm whether plans are waiting.
        </div>
      ) : queue.length === 0 ? (
        !composing && (
          <div className={`px-5 py-6 text-sm ${KT.muted}`}>
            Nothing queued. Compose a plan to propose a change to the book&apos;s shape;
            it waits here for review before any order is placed.
          </div>
        )
      ) : (
        <div className="space-y-3 px-5 py-4">
          {queue.map((p) => (
            <PlanCard key={p.plan_id} plan={p}
                      onDone={() => { loadQueue(); onCommitted(); }} />
          ))}
        </div>
      )}
    </div>
  );
}
