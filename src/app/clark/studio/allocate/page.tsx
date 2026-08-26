"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { spineError } from "@/lib/spine_error";
import Link from "next/link";
import { ArrowRight, Loader2, Plus, Scale, Sliders } from "lucide-react";
import { StudioHeader } from "../components/StudioHeader";
import { AllocationModal } from "../components/AllocationModal";
import { DivergencePanel } from "../components/DivergencePanel";
import { RebalancePanel } from "../components/RebalancePanel";
import { NavPanel } from "../components/NavPanel";
import { ExecutionAnalytics } from "../components/ExecutionAnalytics";
import { KT } from "../theme";
import { money, pct, signedMoney } from "../format";
import { archivedStillHolding, cashPctOfNav, engineOf, foldBook, isHolding } from "./bookFold";
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
 *
 * Two defects fixed here on 2026-08-20, both found by RUNNING the page rather
 * than reading it:
 *
 *   C1 — the false zero. The headline totals were folded over
 *        `state === "deployed"` only, so three PAUSED strategies holding 43.1%
 *        of NAV rendered as "0.0% of NAV actually at work". State is a label
 *        now, never a filter; the arithmetic lives in ./bookFold.ts with tests.
 *
 *   C3 — the healthy empty book. `Promise.all` meant one dead endpoint
 *        rejected both, `strategies` stayed `[]` and `nav` stayed null, and the
 *        page rendered a calm, fully-populated 0.0% / $0 fund. It is
 *        `Promise.allSettled` now, each source's failure is stated
 *        separately, and an unread number renders "—", never 0.
 */

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

/**
 * ENGINE PROVENANCE — the smallest thing that makes an algorithmic strategy
 * findable among hand-managed sleeves (CEO, 2026-08-26: "I would like to see
 * the Lean engine's strategy in allocate … to get a quick sense and imo most
 * of our early work will be algorithmic").
 *
 * It is a LINK, not just a label. The badge alone would tell the reader that
 * something is different and leave them to find where; the engine page is
 * where the datasource, the rule and the signal history actually live, and it
 * is one click from here.
 *
 * Renders NOTHING for a hand-managed strategy — no "manual" badge. Most rows
 * are manual, and a badge on every row is a badge on none.
 */
function EngineBadge({ strategy }: { strategy: StrategyView }) {
  const engine = engineOf(strategy);
  if (!engine) return null;
  return (
    <Link
      href="/clark/studio/engine"
      title={`Run by the ${engine} engine — open the engine page for its datasource, rule and signal history`}
      className="rounded border border-[var(--kt-accent-border)] bg-[var(--kt-accent-bg)] px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-[var(--kt-accent)] hover:underline"
    >
      {engine} engine
    </Link>
  );
}

/** Target vs actual weight, with the gap made visible rather than inferred.
 *
 *  Both inputs are nullable: an unreported weight draws NO bar and no marker
 *  rather than a bar pinned at zero, which would read as a measured flat
 *  position. A drawn zero-length bar is a claim; blank is the absence. */
function DriftBar({ target, actual }: { target?: number | null; actual?: number | null }) {
  if (target == null && actual == null) {
    return (
      <div className={`w-full min-w-[120px] text-[10px] ${KT.muted}`}>
        no weights reported
      </div>
    );
  }
  const max = Math.max(target ?? 0, actual ?? 0, 1);
  return (
    <div className="w-full min-w-[120px]">
      <div className={`${KT.barTrack} relative`}>
        {actual != null && (
          <div className={KT.barFill} style={{ width: `${Math.min(100, (actual / max) * 100)}%` }} />
        )}
        {/* target marker — where the allocation is supposed to sit */}
        {target != null && (
          <div
            className="absolute top-[-2px] h-[10px] w-[2px] bg-[var(--kt-text-dim)]"
            style={{ left: `${Math.min(100, (target / max) * 100)}%` }}
            title={`target ${target.toFixed(1)}%`}
          />
        )}
      </div>
    </div>
  );
}

export default function AllocatePage() {
  // `null` = the strategy list has not been read. Distinct from `[]`, which is
  // the fund genuinely running nothing (C3: those two rendered identically).
  const [strategies, setStrategies] = useState<StrategyView[] | null>(null);
  const [nav, setNav] = useState<NavResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [stratErr, setStratErr] = useState<string | null>(null);
  const [navErr, setNavErr] = useState<string | null>(null);

  const [allocTarget, setAllocTarget] = useState<StrategyView | null>(null);
  // Which strategy's fills and round-trips are expanded below the table.
  const [drillInto, setDrillInto] = useState<StrategyView | null>(null);

  // C3: allSettled, not all. Two independent questions ("what does the fund
  // own?" and "what is it worth?") were sharing one failure: a dead NAV
  // endpoint blanked the strategy table too, and the page then rendered a
  // complete, healthy, empty book. Each source now fails on its own and says
  // which one failed.
  const load = useCallback(async () => {
    const [s, n] = await Promise.allSettled([
      fundApiClient.getStrategies(),
      fundApiClient.getNav(),
    ]);
    if (s.status === "fulfilled") {
      setStrategies(s.value.strategies || []);
      setStratErr(null);
    } else {
      setStrategies(null);          // unknown, never an empty book
      setStratErr(spineError(s.reason));
    }
    if (n.status === "fulfilled") {
      setNav(n.value);
      setNavErr(null);
    } else {
      setNav(null);
      setNavErr(spineError(n.reason));
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  // Nulls survive all the way to the render. `?? 0` here was the whole of C3:
  // it turned "the spine did not answer" into "the fund holds nothing".
  const navUsd = nav?.live?.total_nav_usd ?? null;
  const cashUsd = nav?.live?.breakdown?.cash ?? null;

  const fold = useMemo(() => foldBook(strategies ?? []), [strategies]);
  const orphanedHoldings = useMemo(
    () => archivedStillHolding(strategies ?? []),
    [strategies],
  );

  const { book, bench } = fold;
  /* How many rows `foldBook` dropped as archived. Stated on the bench panel so
     "nothing on the bench" cannot be read as "the fund has no idle strategies"
     when it actually means "every idle one is dead". */
  const archivedCount = (strategies ?? []).filter((s) => s.archived).length;
  const targetTotal = fold.target.value;
  const actualTotal = fold.actual.value;
  /* The whole book including archived holders — the hero's number whenever an
     archived strategy still holds exposure (CDO D2). Null stays null: an
     unmeasurable total renders as a dash, never as a reassuring zero. */
  const atWorkTrue = fold.actualIncludingArchived.value;
  const archivedPct = fold.archivedActual.value;
  const cashPct = cashPctOfNav(cashUsd, navUsd);
  const worstDrift = fold.worstDrift;
  const driftOverLimit = worstDrift != null && worstDrift > 5;
  // Every strategy whose dollars are live while its state says it is not
  // trading. Zero is the ordinary case; non-zero is the C1 condition and gets
  // said out loud rather than folded into a total.
  const pausedHolders = fold.holdingWhileNotDeployed;

  return (
    <div className={KT.page}>
      <StudioHeader
        subtitle="Strategies, weights and composition"
        actions={
          <>
            <Link href="/clark/studio/compose" className={`flex h-8 items-center ${KT.btnGhost}`}>
              <Sliders size={14} className="mr-1.5" /> Composer
            </Link>
            <a href="#rebalance" className={`flex h-8 items-center ${KT.btnGhost}`}>
              <Scale size={14} className="mr-1.5" /> Rebalance
            </a>
            <Link href="/clark/studio/lab" className={`flex h-8 items-center ${KT.btn}`}>
              <Plus size={14} className="mr-1.5" /> New strategy
            </Link>
          </>
        }
      />

      <div className="mx-auto max-w-[1600px] px-6 py-6">
        {/* C3: each source names itself. "Could not read the fund" and "could
            not price the fund" send the reader to different places. */}
        {(stratErr || navErr) && (
          <div className={`mb-4 p-3 text-sm ${KT.inset} ${KT.down}`}>
            <div className="font-medium">
              {stratErr && navErr
                ? "Cannot read the book or its value"
                : stratErr
                  ? "Cannot read the strategy list"
                  : "Cannot read NAV"}
            </div>
            <div className={`mt-0.5 ${KT.muted}`}>{stratErr || navErr}</div>
            <div className="mt-1 text-[11px]">
              This is not an empty book. What the fund holds is unknown from here —
              every figure below that depends on the missing source shows “—”.
            </div>
          </div>
        )}

        {/* The C1 sentence. A pause stops a strategy TRADING; it does not sell
            its positions, and for three weeks this page said otherwise. */}
        {pausedHolders.length > 0 && (
          <div className={`mb-4 p-3 text-sm ${KT.inset} border-l-2 border-l-[var(--kt-warn)]`}>
            <span className={KT.sev.warn}>
              {pausedHolders.length} {pausedHolders.length === 1 ? "strategy is" : "strategies are"} paused
              but still holding
            </span>{" "}
            — {pct(fold.actual.value)} of NAV sits in positions no strategy is managing.
            Pausing halts new orders; it does not close anything. These are counted in
            every total on this page and listed in the book below.
          </div>
        )}

        {orphanedHoldings.length > 0 && (
          <div className={`mb-4 p-3 text-sm ${KT.inset} ${KT.down}`}>
            {orphanedHoldings.length} ARCHIVED{" "}
            {orphanedHoldings.length === 1 ? "strategy still reports" : "strategies still report"}{" "}
            exposure. Archiving is supposed to mean the position is gone — this is a
            contradiction in the spine, not a rounding artefact, and the totals below
            EXCLUDE it.
          </div>
        )}

        {/* Is the book where we intended it to be?
            Strictly about INTENT vs REALITY. NAV in dollars, P&L and cash all
            live in NavPanel directly below, and showing them here as well meant
            the same three numbers appeared twice on one screen — which trains
            the eye to skip the strip rather than read it. */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div className={KT.card}>
            <div className={KT.label}>Allocated (target)</div>
            <div className={`mt-1 ${KT.numberLg}`}>{pct(targetTotal)}</div>
            <div className={`mt-1 text-[11px] ${KT.muted}`}>
              {strategies === null
                ? "strategy list unreadable"
                : `across ${fold.all.length} live ${fold.all.length === 1 ? "strategy" : "strategies"}`}
            </div>
          </div>
          <div className={KT.card}>
            {/* Renamed from "Deployed (actual)": the figure was never about the
                deployed state, and the label was half of why the false zero
                read as plausible. */}
            <div className={KT.label}>At work (actual)</div>
            {/* CDO D2: while an ARCHIVED strategy still held exposure, this
                rendered 0.0% — directly above a banner saying archived
                strategies still hold positions. The hero now reports the whole
                book, archived rows included, because dollars at work do not
                stop being at work when a flag is set on the row that carries
                them. Where even that total is unmeasurable it renders as an
                absent dash carrying the banner's sentence, never as 0.0%. */}
            <div className={`mt-1 ${KT.numberLg}${
              orphanedHoldings.length > 0 ? " text-[var(--kt-warn)]" : ""}`}>
              {pct(orphanedHoldings.length > 0 ? atWorkTrue : actualTotal)}
            </div>
            <div className={`mt-1 text-[11px] ${KT.muted}`}>
              {strategies === null
                ? "unknown — the strategy list did not load"
                : orphanedHoldings.length > 0
                  ? (atWorkTrue == null
                      ? `not measurable — ${orphanedHoldings.length} archived ${
                          orphanedHoldings.length === 1 ? "strategy holds" : "strategies hold"
                        } exposure and no row reported a percentage`
                      : `of NAV in positions — INCLUDES ${orphanedHoldings.length} archived ${
                          orphanedHoldings.length === 1
                            ? "strategy that still holds"
                            : "strategies that still hold"
                        }${
                          archivedPct == null
                            ? ""
                            : Math.abs(archivedPct - atWorkTrue) < 0.005
                              ? " — all of it"
                              : ` (${pct(archivedPct)} of it)`
                        }`)
                  : pausedHolders.length > 0
                    ? `of NAV in positions · ${pausedHolders.length} paused, still held`
                    : "of NAV actually at work, whatever the state says"}
            </div>
          </div>
          <div className={KT.card}>
            <div className={KT.label}>Worst drift</div>
            <div className={`mt-1 ${KT.numberLg} ${driftOverLimit ? KT.down : ""}`}>
              {pct(worstDrift)}
            </div>
            <div className={`mt-1 text-[11px] ${KT.muted}`}>
              {worstDrift == null
                ? "no strategy reported both a target and an actual"
                : driftOverLimit
                  ? "a strategy is off its target"
                  : "every strategy near target"}
            </div>
          </div>
          <div className={KT.card}>
            <div className={KT.label}>Unallocated</div>
            <div className={`mt-1 ${KT.numberLg}`}>
              {targetTotal == null ? "—" : pct(100 - targetTotal)}
            </div>
            <div className={`mt-1 text-[11px] ${KT.muted}`}>
              target left to assign · {pct(cashPct)} sitting in cash
            </div>
          </div>
        </div>

        <NavPanel nav={nav} strategies={strategies ?? []} />

        {/* The book: everything DEPLOYED or HOLDING. Membership follows the
            positions, not the state string — see bookFold.ts (defect C1). */}
        <div className={`mt-6 ${KT.panel}`}>
          <div className="flex items-center justify-between border-b border-[var(--kt-border)] px-5 py-3">
            <span className={KT.label}>The book · deployed or holding</span>
            {driftOverLimit && (
              <a href="#rebalance" className={`text-[11px] ${KT.accent} underline underline-offset-2`}>
                drift over 5% — rebalance
              </a>
            )}
          </div>

          {loading ? (
            <div className={`flex items-center gap-2 px-5 py-10 text-sm ${KT.muted}`}>
              <Loader2 size={14} className="animate-spin" /> Loading…
            </div>
          ) : strategies === null ? (
            // C3: the dead-spine case. Previously indistinguishable from the
            // cheerful "nothing deployed yet" below.
            <div className={`px-5 py-10 text-sm ${KT.sev.warn}`}>
              The strategy list could not be read, so what the fund holds is unknown —
              not nothing. Positions may be open. Check the venue directly before acting
              on this screen.
            </div>
          ) : book.length === 0 ? (
            <div className={`px-5 py-10 text-sm ${KT.muted}`}>
              Nothing deployed and nothing held. Strategies are born in the <Link href="/clark/studio/lab" className={KT.accent}>Lab</Link> — backtest an idea,
              check whether it is alpha or beta you already own, then propose it at a weight.
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
                    <th className="px-5 py-2 text-right font-normal">Cost Basis</th>
                    <th className="px-5 py-2 text-right font-normal">Unrealized</th>
                    <th className="px-5 py-2 text-right font-normal">Realized</th>
                    <th className="px-5 py-2 text-right font-normal">Sharpe</th>
                    <th className="px-5 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {book.map((s) => {
                    // An absent weight stays absent. `?? 0` here would have
                    // drawn a strategy at zero target and zero actual as if
                    // that had been measured — the row-level twin of C1.
                    const target = s.allocation_pct;
                    const actual = s.actual_pct;
                    const drift =
                      target != null && actual != null ? actual - target : null;
                    const unmanaged = s.state !== "deployed" && isHolding(s);
                    return (
                      <tr key={s.strategy_id} className="border-b border-[var(--kt-border)] last:border-0">
                        <td className="px-5 py-3">
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{s.name}</span>
                            <Badge state={s.state} />
                            <EngineBadge strategy={s} />
                            {/* The state badge alone reads as bookkeeping. This
                                says what the state MEANS for money at risk. */}
                            {unmanaged && (
                              <span className={`text-[10px] uppercase tracking-wide ${KT.sev.warn}`}>
                                holding · not managed
                              </span>
                            )}
                          </div>
                          <div className={`mt-0.5 text-[11px] ${KT.muted}`}>
                            {s.assets?.length ? s.assets.join(" · ") : "no assets scoped"}
                          </div>
                        </td>
                        <td className="px-5 py-3">
                          <DriftBar target={target} actual={actual} />
                        </td>
                        <td className={`px-5 py-3 text-right ${KT.number}`}>{pct(target)}</td>
                        <td className={`px-5 py-3 text-right ${KT.number}`}>{pct(actual)}</td>
                        <td className={`px-5 py-3 text-right font-mono tabular-nums ${drift != null && Math.abs(drift) > 5 ? KT.down : KT.muted}`}>
                          {drift == null ? "—" : `${drift >= 0 ? "+" : ""}${drift.toFixed(1)}%`}
                        </td>
                        <td className={`px-5 py-3 text-right ${KT.number}`}>{money(s.exposure_usd)}</td>
                        <td className={`px-5 py-3 text-right ${KT.number}`}>{money(s.cost_basis_usd)}</td>
                        <td className={`px-5 py-3 text-right font-mono tabular-nums ${tone(s.unrealized_pnl_usd)}`}>
                          {signedMoney(s.unrealized_pnl_usd)}
                        </td>
                        <td className={`px-5 py-3 text-right font-mono tabular-nums ${tone(s.realized_pnl_usd)}`}>
                          {signedMoney(s.realized_pnl_usd)}
                        </td>
                        <td className={`px-5 py-3 text-right ${KT.number}`}>
                          {s.backtest?.sharpe != null ? s.backtest.sharpe.toFixed(2) : "—"}
                        </td>
                        <td className="px-5 py-3 text-right">
                          <div className="flex items-center justify-end gap-3">
                            <button
                              onClick={() => setDrillInto(drillInto?.strategy_id === s.strategy_id ? null : s)}
                              className={`text-[11px] ${KT.accent} underline underline-offset-2`}>
                              {drillInto?.strategy_id === s.strategy_id ? "hide trades" : "trades"}
                            </button>
                            <button onClick={() => setAllocTarget(s)} className={`text-[11px] ${KT.accent} underline underline-offset-2`}>
                              resize
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {drillInto && (
          <ExecutionAnalytics
            key={drillInto.strategy_id}
            strategyId={drillInto.strategy_id}
            title={`${drillInto.name} — execution history`}
          />
        )}

        {/* The promise each live strategy was allocated capital ON, against
            what it is delivering — the question this page's weights should be
            re-answered by. Shared with Monitor: same panel, same honesty about
            youth ("1.7 of 14 live days"). */}
        <div className="mt-6">
          <DivergencePanel />
        </div>

        <div id="rebalance" className="scroll-mt-24">
          {/* The book, not the deployed subset: a rebalance that cannot see the
              paused holdings would propose weights against 57% of the fund and
              call it 100%. */}
          <RebalancePanel strategies={book} navUsd={navUsd} onCommitted={load} />
        </div>

        {/* Not yet carrying capital.
            ARCHIVED rows are already out — `foldBook` derives the bench from
            non-archived strategies only — but the COUNT is stated below rather
            than left implicit, because "nothing on the bench" and "everything
            on the bench is archived" are different facts and the panel used to
            render the second as the first. */}
        <div className={`mt-6 ${KT.panel}`}>
          <div className={`border-b border-[var(--kt-border)] px-5 py-3 ${KT.label}`}>
            Bench · not carrying capital
          </div>
          {strategies === null ? (
            <div className={`px-5 py-8 text-sm ${KT.sev.warn}`}>
              Unreadable — the bench is unknown, not empty.
            </div>
          ) : bench.length === 0 ? (
            <div className={`px-5 py-8 text-sm ${KT.muted}`}>
              Nothing on the bench.
              {archivedCount > 0 && (
                <> {archivedCount} archived {archivedCount === 1 ? "strategy is" : "strategies are"}{" "}
                  excluded — archived is the fund&apos;s own &ldquo;this no longer
                  exists&rdquo;, and a dead strategy is not a benched one.</>
              )}
            </div>
          ) : (
            <ul className="divide-y divide-[var(--kt-border)]">
              {bench.map((s) => (
                <li key={s.strategy_id} className="flex items-center gap-3 px-5 py-3">
                  <span className="font-medium">{s.name}</span>
                  <Badge state={s.state} />
                  <EngineBadge strategy={s} />
                  <span className={`text-[11px] ${KT.muted}`}>
                    {/* Each figure absent on its OWN terms. This read
                        `(total_return ?? 0) * 100` and printed "return 0.0%"
                        for a backtest that had a Sharpe and no return — an
                        unmeasured figure rendered as a measured flat result,
                        on the number an allocation decision is taken against. */}
                    {s.backtest?.sharpe == null && s.backtest?.total_return == null
                      ? "no backtest yet"
                      : <>
                          Sharpe {s.backtest?.sharpe != null
                            ? s.backtest.sharpe.toFixed(2)
                            : <span className={KT.sev.warn}>not recorded</span>}
                          {" · return "}
                          {s.backtest?.total_return != null
                            ? `${(s.backtest.total_return * 100).toFixed(1)}%`
                            : <span className={KT.sev.warn}>not recorded</span>}
                        </>}
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

      <AllocationModal
        strategy={allocTarget}
        onClose={() => setAllocTarget(null)}
        onSuccess={() => load()}
      />
    </div>
  );
}
