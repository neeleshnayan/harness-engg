"use client";

import React from "react";
import { KT } from "../theme";
import { moneyCompact, pct } from "../format";
import { EquityChart } from "./EquityChart";
import {
  NOT_CAPTURED, PRUNED, NOT_TESTABLE,
  absenceLabel, absenceOf, breakevenSentence, costBand,
  foldTally, foldVerdict, gateSentence, honoured, windowLine,
  type CandidateRow, type FoldRow,
} from "./candidateAnalytics";

/**
 * THE ANALYTICS BEHIND A BELT RUN.
 *
 * The CEO's ask, three times on 2026-08-21: *"the quant page aka lab has no
 * analytics making it hard for me to understand agents runs ... importantly be
 * able to see the analytics behind the runs!"* — and, the same day, *"i can see
 * monthend_rebalance_flow but cant see the analytics behind"*.
 *
 * The order of this panel is the order of the questions a person actually asks
 * when validating someone else's run, and it is deliberately the same order
 * `LeanResults` uses for a run you executed yourself — that sameness IS the
 * unification the ask names:
 *
 *   1. what did the gate say, in its own words;
 *   2. what happened — the curve, against simply owning the thing;
 *   3. did it hold up in windows it was not chosen on — the folds;
 *   4. how wrong could we be about costs before it stops paying;
 *   5. what it actually did — the fills.
 *
 * THE ABSENCE RULE BINDS HARDEST HERE and it is the reason this file is longer
 * than it looks like it should be. Every one of the five sections can be
 * missing for a DIFFERENT reason, and a blank panel would say none of them.
 * A candidate judged before 2026-08-21 has no evidence at all and says so; a
 * fold the engine killed says the engine killed it; a one-point grid says a
 * band was never measured rather than showing a flat line. Nothing here ever
 * renders an absent figure as zero.
 */

/* ------------------------------------------------------------------ atoms */

function Note({ children, tone = "muted" }: {
  children: React.ReactNode; tone?: "muted" | "warn" | "down";
}) {
  const cls = tone === "warn" ? KT.sev.warn : tone === "down" ? KT.down : KT.muted;
  return <p className={`text-[11px] leading-relaxed ${cls}`}>{children}</p>;
}

/** A named absence, never an empty box. Carries the spine's own sentence. */
function Absent({ label, note, sub }: {
  label: string; note: string; sub?: string | null;
}) {
  return (
    <div className={`${KT.inset} px-4 py-3`}>
      <div className="flex items-baseline gap-2">
        <span className={KT.label}>{label}</span>
      </div>
      <p className={`mt-1.5 max-w-3xl text-[11px] leading-relaxed ${KT.muted}`}>{note}</p>
      {sub && <p className={`mt-1 text-[10px] ${KT.muted}`}>{sub}</p>}
    </div>
  );
}

function Section({ title, hint, children }: {
  title: string; hint?: string; children: React.ReactNode;
}) {
  return (
    <div className={KT.panel}>
      <div className="border-b border-[var(--kt-border)] px-5 py-3">
        <span className={KT.label}>{title}</span>
        {hint && <div className={`mt-1 text-[11px] ${KT.muted}`}>{hint}</div>}
      </div>
      <div className="px-5 py-4">{children}</div>
    </div>
  );
}

/* --------------------------------------------------------------- sections */

/** The gate's sentence, verbatim, and every failure it listed.
 *
 *  Never paraphrased and never scored. The gate returns sentences precisely so
 *  a verdict cannot be negotiated ("0.61 is nearly 0.65"); a UI that summarised
 *  them into a number would hand that back. */
function GateVerdict({ c }: { c: CandidateRow }) {
  const g = gateSentence(c);
  const tone = g.passed === true ? KT.up : g.passed === false ? KT.down : KT.sev.warn;
  return (
    <Section
      title="What the gate said"
      hint="the bar, declared before the result was known — its words, not ours"
    >
      <p className={`text-sm ${tone}`}>{g.sentence}</p>
      {g.failures.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {g.failures.map((f, i) => (
            <li key={i} className={`text-[11px] leading-relaxed ${KT.body}`}>
              <span className={KT.muted}>—</span> {f}
            </li>
          ))}
        </ul>
      )}
      <p className={`mt-3 text-[10px] ${KT.muted}`}>
        {g.version
          ? `judged by gate ${g.version} · a candidate cleared under one version has not been cleared under another`
          : "the gate version was not stored with this verdict — which bar it cleared is unknown, not assumed"}
      </p>
    </Section>
  );
}

/** The verification run: the curve, the benchmark, and the headline figures. */
function Verification({ c }: { c: CandidateRow }) {
  const v = c.analytics?.verification;
  if (!v || v.present !== true) {
    return (
      <Section title="What happened" hint="the winner, re-run in full">
        <Absent
          label="no verification run"
          note={v?.note
            ?? "the run that carries costs, benchmark and capacity is not in the record"}
        />
      </Section>
    );
  }
  const r = v.result ?? {};
  const curve = r.equity_curve ?? [];
  const bench = r.benchmark_curve ?? [];
  const dates = r.equity_dates ?? [];
  const strat = r.total_return_pct;
  const bmk = r.benchmark_return_pct;
  const cap = r.capacity?.capacity_usd;

  return (
    <Section
      title="What happened"
      hint="the grid's winner, re-run IN FULL — the sweep's own rows carry no costs, benchmark or capacity"
    >
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Figure label="Total return" value={pct(strat)}
                sub={bmk != null ? `buy & hold ${pct(bmk)}` : "no benchmark recorded"}
                tone={strat == null ? "" : strat >= 0 ? KT.up : KT.down} />
        <Figure label="Sharpe" value={r.sharpe == null ? "—" : r.sharpe.toFixed(2)}
                sub="LEAN statistic" />
        <Figure label="Max drawdown" value={pct(r.max_drawdown_pct)} sub="peak to trough"
                tone={r.max_drawdown_pct == null ? "" : KT.down} />
        <Figure label="Capacity"
                value={cap == null ? "not estimated" : moneyCompact(cap)}
                sub={cap == null
                  ? (r.capacity?.reason ?? "unmeasured is not adequate")
                  : "how much money it could hold"} />
      </div>

      {strat != null && bmk != null && strat <= bmk && (
        <p className={`mt-3 text-[11px] ${KT.down}`}>
          Trails simply owning the underlying by {(bmk - strat).toFixed(2)}% — an
          expensive way to hold it.
        </p>
      )}

      <div className="mt-4">
        {curve.length >= 2 ? (
          <EquityChart equity={curve}
                       benchmark={bench.length >= 2 ? bench : undefined}
                       dates={dates.length ? dates : null} />
        ) : (
          <Absent
            label="no equity curve"
            note="the engine recorded fewer than two points, so there is nothing to
                  plot. That is a fact about this run, not a zero."
          />
        )}
      </div>
      <p className={`mt-2 text-[10px] ${KT.muted}`}>
        job {v.job_id ?? "—"}
        {v.wall_seconds != null ? ` · ${v.wall_seconds}s wall` : ""}
        {v.parameters ? ` · ${Object.entries(v.parameters)
          .map(([k, val]) => `${k}=${val}`).join(" ")}` : ""}
      </p>
    </Section>
  );
}

function Figure({ label, value, sub, tone = "" }: {
  label: string; value: string; sub?: string; tone?: string;
}) {
  return (
    <div>
      <div className={KT.label}>{label}</div>
      <div className={`mt-1 font-mono tabular-nums text-xl font-light ${tone}`}>{value}</div>
      {sub && <div className={`mt-1 text-[10px] ${KT.muted}`}>{sub}</div>}
    </div>
  );
}

/**
 * The folds — one holdout is one draw.
 *
 * The rows the quant seat had to reconstruct "from sweeps by grid-key luck"
 * (run-quant-entry11, accepted 2026-08-21). Three things this table does that a
 * naive one would not:
 *
 *   * an unmeasurable fold shows its REASON, never a dash and never a 0%;
 *   * a fold the ENGINE killed is marked as ours, because it demands "re-run it
 *     with more time" and not a conclusion about the rule;
 *   * `dates_honoured` renders in three states — an unchecked fold is not a
 *     validated one.
 */
export function FoldTable({ folds, verdict }: {
  folds: FoldRow[] | null | undefined; verdict?: string | null;
}) {
  const rows = folds ?? [];
  const t = foldTally(rows);
  if (rows.length === 0) {
    return (
      <Absent
        label="no fold rows"
        note="the walk-forward summary exists but the per-fold rows are not in this
              record. The counts above are the whole of what was stored."
      />
    );
  }
  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
              <th className="py-1 pr-3 font-normal">#</th>
              <th className="py-1 pr-3 font-normal">test window requested</th>
              <th className="py-1 pr-3 font-normal">covered</th>
              <th className="py-1 pr-3 font-normal">train %</th>
              <th className="py-1 pr-3 font-normal">test %</th>
              <th className="py-1 pr-3 font-normal">fills</th>
              <th className="py-1 pr-3 font-normal">kept</th>
              <th className="py-1 font-normal">dates</th>
            </tr>
          </thead>
          <tbody className="tabular-nums">
            {rows.map((f, i) => {
              const v = foldVerdict(f);
              const w = windowLine(f);
              const h = honoured(f);
              const toneCls = v.tone === "kept" ? KT.up
                : v.tone === "lost" ? KT.down
                : v.tone === "ours" ? KT.sev.warn : KT.muted;
              return (
                <React.Fragment key={f.fold ?? i}>
                  <tr className="border-t border-[var(--kt-border)]">
                    <td className="py-1.5 pr-3">{f.fold ?? i + 1}</td>
                    <td className={`py-1.5 pr-3 font-mono text-[11px] ${KT.muted}`}>{w.requested}</td>
                    <td className="py-1.5 pr-3 font-mono text-[11px]">{w.covered}</td>
                    <td className="py-1.5 pr-3">{pct(f.train_return_pct, 2)}</td>
                    <td className="py-1.5 pr-3">{pct(f.test_return_pct, 2)}</td>
                    <td className="py-1.5 pr-3">
                      {/* An absent fill count is not zero fills: a killed
                          container never reported one, and a run that placed
                          none reported 0. */}
                      {f.test_orders == null ? "—" : f.test_orders}
                    </td>
                    <td className={`py-1.5 pr-3 ${toneCls}`}>{v.label}</td>
                    <td className="py-1.5 text-[11px]">
                      {h === "honoured" ? <span className={KT.muted}>honoured</span>
                        : h === "dishonoured"
                          ? <span className={KT.down}>SAME DATES TWICE</span>
                          : <span className={KT.sev.warn}>unchecked</span>}
                    </td>
                  </tr>
                  {v.reason && (
                    <tr>
                      <td />
                      <td colSpan={7} className={`pb-2 text-[11px] leading-relaxed ${
                        v.ours ? KT.sev.warn : KT.muted}`}>
                        {v.ours ? "OUR CLOCK, not the strategy — " : ""}{v.reason}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className={`mt-3 text-[11px] leading-relaxed ${KT.body}`}>
        {t.measurable} of {t.attempted} folds produced a figure; {t.retained} kept
        at least {(0.5 * 100).toFixed(0)}% of the training edge.
        {t.timedOut > 0 && (
          <span className={KT.sev.warn}>
            {" "}{t.timedOut} fold{t.timedOut === 1 ? "" : "s"} ended because the
            ENGINE ran out of wall clock — {t.timedOut === 1 ? "it was" : "they were"}
            {" "}never examined, and that is our failure rather than the strategy&apos;s.
          </span>
        )}
      </p>
      {verdict && <Note>{verdict}</Note>}
    </>
  );
}

function Folds({ c }: { c: CandidateRow }) {
  const wf = c.analytics?.walkforward;
  const rows = wf?.folds ?? c.walkforward?.folds ?? null;
  const hint = "a strategy must keep its edge in a strict majority of INDEPENDENT " +
    "windows — the property a lucky draw cannot supply";

  if (wf && wf.present !== true) {
    return (
      <Section title="Did it hold up out of sample?" hint={hint}>
        <Absent
          label={wf.reason === NOT_TESTABLE ? "not testable on our history" : "walk-forward unavailable"}
          note={wf.note ?? "no reason was recorded, which is itself a gap"}
          sub={wf.hold_days != null
            ? `holding period ${wf.hold_days} days (${wf.hold_days_source ?? "source unknown"})`
            : null}
        />
        {wf.reason === NOT_TESTABLE && (
          <Note>
            NOT TESTABLE is not a verdict about the strategy. It says the fund
            cannot yet examine a rule this slow, and the answer is a faster rule
            or more history — never a different threshold.
          </Note>
        )}
      </Section>
    );
  }
  return (
    <Section title="Did it hold up out of sample?" hint={hint}>
      <FoldTable folds={rows} verdict={wf?.verdict ?? null} />
    </Section>
  );
}

/** The cost band — how wrong we could be about costs before the edge stops paying. */
function Costs({ c }: { c: CandidateRow }) {
  const s = c.analytics?.sweep;
  const hint = "not “what does trading cost” — nobody knows to a basis " +
    "point — but “how wrong could we be before this stops working”";
  if (!s || s.present !== true) {
    return (
      <Section title="How robust is it to costs?" hint={hint}>
        <Absent label="no cost sweep recorded"
                note={s?.note ?? "no sweep is in this record"} />
      </Section>
    );
  }
  const band = costBand(s.points);
  const be = s.summary?.breakeven_cost ?? null;
  return (
    <Section title="How robust is it to costs?" hint={hint}>
      {band.length === 0 ? (
        <Absent
          label="no cost parameter was swept"
          note="this grid varied something other than slippage, so the band that
                would say where the edge dies was never produced. Not swept is not
                robust."
        />
      ) : (
        <div className="space-y-1">
          {band.map((r, i) => (
            <div key={i} className="flex items-baseline gap-3 text-[11px]">
              <span className={`w-24 font-mono ${KT.muted}`}>
                {r.bps == null ? r.value : `${r.bps}bps`}
              </span>
              {r.returnPct == null ? (
                <span className={KT.sev.warn}>
                  no return — {r.error ?? `point ${r.state ?? "unknown"}`}
                </span>
              ) : (
                <span className={`font-mono tabular-nums ${
                  r.returnPct >= 0 ? KT.up : KT.down}`}>
                  {r.returnPct >= 0 ? "+" : ""}{r.returnPct}%
                </span>
              )}
            </div>
          ))}
        </div>
      )}
      <p className={`mt-3 text-[11px] leading-relaxed ${KT.body}`}>
        {breakevenSentence(be, band.length)}
      </p>
    </Section>
  );
}

/** What it actually did. */
function Fills({ c }: { c: CandidateRow }) {
  const r = c.analytics?.verification?.result;
  const orders = r?.orders ?? [];
  if (!r) return null;
  return (
    <Section title="What it actually did"
             hint={`${orders.length} fill${orders.length === 1 ? "" : "s"} from the verification run`}>
      {orders.length === 0 ? (
        <Absent
          label="no fills"
          note="the algorithm never entered a position over this window. That is a
                result — and it means no out-of-sample number here says anything
                about an edge."
        />
      ) : (
        <>
          {r.orders_truncated && <Note tone="warn">{r.orders_truncated_note}</Note>}
          <div className="max-h-[280px] overflow-auto">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-[var(--kt-surface)]">
                <tr className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
                  <th className="py-1 pr-3 font-normal">#</th>
                  <th className="py-1 pr-3 font-normal">side</th>
                  <th className="py-1 pr-3 font-normal">symbol</th>
                  <th className="py-1 pr-3 font-normal">filled</th>
                  <th className="py-1 pr-3 text-right font-normal">qty</th>
                  <th className="py-1 pr-3 text-right font-normal">price</th>
                  <th className="py-1 text-right font-normal">value</th>
                </tr>
              </thead>
              <tbody className="tabular-nums">
                {orders.map((o, i) => (
                  <tr key={i} className="border-t border-[var(--kt-border)]">
                    <td className={`py-1 pr-3 ${KT.muted}`}>{i + 1}</td>
                    <td className={`py-1 pr-3 uppercase ${o.side === "sell" ? KT.down : KT.up}`}>
                      {o.side ?? "—"}
                    </td>
                    <td className="py-1 pr-3">{o.symbol ?? "—"}</td>
                    <td className={`py-1 pr-3 ${KT.muted}`}>
                      {o.time ? String(o.time).slice(0, 10) : "—"}
                    </td>
                    <td className="py-1 pr-3 text-right">{o.qty ?? "—"}</td>
                    <td className="py-1 pr-3 text-right">{o.price ?? "—"}</td>
                    <td className="py-1 text-right">{o.value ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Section>
  );
}

/* ----------------------------------------------------------------- panel */

export function RunAnalytics({ candidate }: { candidate: CandidateRow }) {
  const c = candidate;
  const missing = absenceOf(c);

  return (
    <div className="space-y-4">
      <GateVerdict c={c} />

      {missing ? (
        <Section
          title="The analytics behind this run"
          hint="the evidence the verdict above was computed from"
        >
          <Absent
            label={absenceLabel(missing.reason)}
            note={missing.note}
            sub={missing.prunedAt
              ? `aged out ${String(missing.prunedAt).slice(0, 10)}`
              : null}
          />
          {missing.reason === NOT_CAPTURED && (
            <Note>
              The verdict above is not in doubt — it was computed from evidence
              that existed and was then discarded. Re-running this candidate on
              today&apos;s belt stores all of it.
            </Note>
          )}
          {missing.reason === PRUNED && (
            <Note>
              Aged out is not never-measured. The retention policy removed the
              payload; the verdict, its failures and the fold counts above are
              untouched.
            </Note>
          )}
        </Section>
      ) : (
        <>
          <Verification c={c} />
          <Folds c={c} />
          <Costs c={c} />
          <Fills c={c} />
        </>
      )}

      <p className={`text-[10px] leading-relaxed ${KT.muted}`}>
        Everything above is the engine&apos;s own output and the gate&apos;s own
        sentences, read from the record — nothing is recomputed here. An absent
        figure renders as absent: no number on this page has been defaulted to
        zero.
      </p>
    </div>
  );
}
