"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { spineError } from "@/lib/spine_error";
import Link from "next/link";
import { ArrowRight, Loader2, Plus, Scale, Sliders } from "lucide-react";
import { StudioHeader } from "../components/StudioHeader";
import { CreateStrategyModal } from "../components/CreateStrategyModal";
import { RebalanceModal } from "../components/RebalanceModal";
import { AllocationModal } from "../components/AllocationModal";
import { KT } from "../theme";
import { fundApiClient, NavResponse, StrategyView } from "@/lib/fund_api";

/**
 * ALLOCATE — how much of the fund goes where, and is it where we intended.
 *
 * This replaced a 1,761-line page that had become a quant IDE (Python editor,
 * QuantConnect charts, efficient frontier, code presets) rather than an
 * allocation surface. Authoring a strategy and sizing the book are different
 * jobs; this page only does the second.
 *
 * Every figure comes from the spine. Where the spine has no answer, the cell
 * shows "—" rather than a zero that would read like a measurement.
 */

const money = (n?: number | null, dp = 2) =>
  n == null ? "—" : `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp })}`;
const pct = (n?: number | null, dp = 1) => (n == null ? "—" : `${Number(n).toFixed(dp)}%`);
const signed = (n?: number | null) =>
  n == null ? "—" : `${n >= 0 ? "+" : ""}${money(n)}`;
const tone = (n?: number | null) => (n == null ? KT.muted : n >= 0 ? KT.up : KT.down);

const STATE_TONE: Record<string, string> = {
  deployed: "border-[var(--kt-accent-border)] bg-[var(--kt-accent-bg)] text-[var(--kt-accent)]",
  backtested: "border-[var(--kt-border)] text-[var(--kt-text-dim)]",
  draft: "border-[var(--kt-border)] text-[var(--kt-text-muted)]",
  paused: "border-[var(--kt-warn)]/40 text-[var(--kt-warn)]",
};

function Badge({ state }: { state?: string }) {
  const s = state || "draft";
  return (
    <span className={`rounded border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide ${STATE_TONE[s] || STATE_TONE.draft}`}>
      {s}
    </span>
  );
}

/** Target vs actual weight, with the gap made visible rather than inferred. */
function DriftBar({ target, actual }: { target: number; actual: number }) {
  const max = Math.max(target, actual, 1);
  return (
    <div className="w-full min-w-[120px]">
      <div className={`${KT.barTrack} relative`}>
        <div className={KT.barFill} style={{ width: `${Math.min(100, (actual / max) * 100)}%` }} />
        {/* target marker — where the allocation is supposed to sit */}
        <div
          className="absolute top-[-2px] h-[10px] w-[2px] bg-[var(--kt-text-dim)]"
          style={{ left: `${Math.min(100, (target / max) * 100)}%` }}
          title={`target ${target.toFixed(1)}%`}
        />
      </div>
    </div>
  );
}

export default function AllocatePage() {
  const [strategies, setStrategies] = useState<StrategyView[]>([]);
  const [nav, setNav] = useState<NavResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [rebalanceOpen, setRebalanceOpen] = useState(false);
  const [allocTarget, setAllocTarget] = useState<StrategyView | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, n] = await Promise.all([
        fundApiClient.getStrategies(),
        fundApiClient.getNav(),
      ]);
      setStrategies(s.strategies || []);
      setNav(n);
      setErr(null);
    } catch (e: any) {
      setErr(spineError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const navUsd = nav?.live?.total_nav_usd ?? 0;
  const cashUsd = nav?.live?.breakdown?.cash ?? 0;

  const live = useMemo(
    () => strategies.filter((s) => !s.archived && s.state === "deployed"),
    [strategies],
  );
  const bench = useMemo(
    () => strategies.filter((s) => !s.archived && s.state !== "deployed"),
    [strategies],
  );

  const targetTotal = live.reduce((a, s) => a + (s.allocation_pct ?? 0), 0);
  const actualTotal = live.reduce((a, s) => a + (s.actual_pct ?? 0), 0);
  const cashPct = navUsd > 0 ? (cashUsd / navUsd) * 100 : 0;
  const worstDrift = live.reduce((w, s) => {
    const d = Math.abs((s.actual_pct ?? 0) - (s.allocation_pct ?? 0));
    return d > w ? d : w;
  }, 0);

  return (
    <div className={KT.page}>
      <StudioHeader
        subtitle="Strategies, weights and composition"
        actions={
          <>
            <Link href="/clark/studio/compose" className={`flex h-8 items-center ${KT.btnGhost}`}>
              <Sliders size={14} className="mr-1.5" /> Composer
            </Link>
            <button className={`flex h-8 items-center ${KT.btnGhost}`} onClick={() => setRebalanceOpen(true)}>
              <Scale size={14} className="mr-1.5" /> Rebalance
            </button>
            <button className={`flex h-8 items-center ${KT.btn}`} onClick={() => setCreateOpen(true)}>
              <Plus size={14} className="mr-1.5" /> New strategy
            </button>
          </>
        }
      />

      <div className="mx-auto max-w-[1600px] px-6 py-6">
        {err && (
          <div className={`mb-4 p-3 text-sm ${KT.inset} ${KT.down}`}>
            {err}
          </div>
        )}

        {/* Is the book where we intended it to be? */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div className={KT.card}>
            <div className={KT.label}>Fund NAV</div>
            <div className={`mt-1 ${KT.numberLg}`}>{money(navUsd)}</div>
          </div>
          <div className={KT.card}>
            <div className={KT.label}>Allocated (target)</div>
            <div className={`mt-1 ${KT.numberLg}`}>{pct(targetTotal)}</div>
            <div className={`mt-1 text-[11px] ${KT.muted}`}>{live.length} deployed</div>
          </div>
          <div className={KT.card}>
            <div className={KT.label}>Deployed (actual)</div>
            <div className={`mt-1 ${KT.numberLg}`}>{pct(actualTotal)}</div>
            <div className={`mt-1 text-[11px] ${worstDrift > 5 ? KT.down : KT.muted}`}>
              worst drift {pct(worstDrift)}
            </div>
          </div>
          <div className={KT.card}>
            <div className={KT.label}>Cash</div>
            <div className={`mt-1 ${KT.numberLg}`}>{money(cashUsd)}</div>
            <div className={`mt-1 text-[11px] ${KT.muted}`}>{pct(cashPct)} of NAV</div>
          </div>
        </div>

        {/* Live book */}
        <div className={`mt-6 ${KT.panel}`}>
          <div className="flex items-center justify-between border-b border-[var(--kt-border)] px-5 py-3">
            <span className={KT.label}>Live allocations</span>
            {worstDrift > 5 && (
              <button onClick={() => setRebalanceOpen(true)} className={`text-[11px] ${KT.accent} underline underline-offset-2`}>
                drift over 5% — rebalance
              </button>
            )}
          </div>

          {loading ? (
            <div className={`flex items-center gap-2 px-5 py-10 text-sm ${KT.muted}`}>
              <Loader2 size={14} className="animate-spin" /> Loading…
            </div>
          ) : live.length === 0 ? (
            <div className={`px-5 py-10 text-sm ${KT.muted}`}>
              Nothing deployed. Create a strategy, back it, then deploy it to put capital to work.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className={`border-b border-[var(--kt-border)] ${KT.label}`}>
                    <th className="px-5 py-2 text-left font-normal">Strategy</th>
                    <th className="px-5 py-2 text-left font-normal">Target vs actual</th>
                    <th className="px-5 py-2 text-right font-normal">Target</th>
                    <th className="px-5 py-2 text-right font-normal">Actual</th>
                    <th className="px-5 py-2 text-right font-normal">Drift</th>
                    <th className="px-5 py-2 text-right font-normal">Gross Exposure</th>
                    <th className="px-5 py-2 text-right font-normal">Unrealized</th>
                    <th className="px-5 py-2 text-right font-normal">Realized</th>
                    <th className="px-5 py-2 text-right font-normal">Sharpe</th>
                    <th className="px-5 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {live.map((s) => {
                    const target = s.allocation_pct ?? 0;
                    const actual = s.actual_pct ?? 0;
                    const drift = actual - target;
                    return (
                      <tr key={s.strategy_id} className="border-b border-[var(--kt-border)] last:border-0">
                        <td className="px-5 py-3">
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{s.name}</span>
                            <Badge state={s.state} />
                          </div>
                          <div className={`mt-0.5 text-[11px] ${KT.muted}`}>
                            {s.assets?.length ? s.assets.join(" · ") : "no assets scoped"}
                          </div>
                        </td>
                        <td className="px-5 py-3"><DriftBar target={target} actual={actual} /></td>
                        <td className={`px-5 py-3 text-right ${KT.number}`}>{pct(target)}</td>
                        <td className={`px-5 py-3 text-right ${KT.number}`}>{pct(actual)}</td>
                        <td className={`px-5 py-3 text-right font-mono tabular-nums ${Math.abs(drift) > 5 ? KT.down : KT.muted}`}>
                          {drift >= 0 ? "+" : ""}{drift.toFixed(1)}%
                        </td>
                        <td className={`px-5 py-3 text-right ${KT.number}`}>{money(s.exposure_usd)}</td>
                        <td className={`px-5 py-3 text-right font-mono tabular-nums ${tone(s.unrealized_pnl_usd)}`}>
                          {signed(s.unrealized_pnl_usd)}
                        </td>
                        <td className={`px-5 py-3 text-right font-mono tabular-nums ${tone(s.realized_pnl_usd)}`}>
                          {signed(s.realized_pnl_usd)}
                        </td>
                        <td className={`px-5 py-3 text-right ${KT.number}`}>
                          {s.backtest?.sharpe != null ? s.backtest.sharpe.toFixed(2) : "—"}
                        </td>
                        <td className="px-5 py-3 text-right">
                          <button onClick={() => setAllocTarget(s)} className={`text-[11px] ${KT.accent} underline underline-offset-2`}>
                            resize
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Not yet carrying capital */}
        <div className={`mt-6 ${KT.panel}`}>
          <div className={`border-b border-[var(--kt-border)] px-5 py-3 ${KT.label}`}>
            Bench · not carrying capital
          </div>
          {bench.length === 0 ? (
            <div className={`px-5 py-8 text-sm ${KT.muted}`}>Nothing on the bench.</div>
          ) : (
            <ul className="divide-y divide-[var(--kt-border)]">
              {bench.map((s) => (
                <li key={s.strategy_id} className="flex items-center gap-3 px-5 py-3">
                  <span className="font-medium">{s.name}</span>
                  <Badge state={s.state} />
                  <span className={`text-[11px] ${KT.muted}`}>
                    {s.backtest?.sharpe != null
                      ? `Sharpe ${s.backtest.sharpe.toFixed(2)} · return ${((s.backtest.total_return ?? 0) * 100).toFixed(1)}%`
                      : "no backtest yet"}
                  </span>
                  <button onClick={() => setAllocTarget(s)} className={`ml-auto flex items-center gap-1 text-[11px] ${KT.accent}`}>
                    allocate <ArrowRight size={11} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <CreateStrategyModal
        isOpen={createOpen}
        onClose={() => setCreateOpen(false)}
        onSuccess={() => load()}
        strategies={strategies}
      />
      <RebalanceModal
        open={rebalanceOpen}
        onOpenChange={setRebalanceOpen}
        strategies={strategies}
        totalNavUsd={navUsd}
        onSuccess={() => load()}
      />
      <AllocationModal
        strategy={allocTarget}
        onClose={() => setAllocTarget(null)}
        onSuccess={() => load()}
      />
    </div>
  );
}
