"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { fundApiClient, type DeskView } from "@/lib/fund_api";
import { KT } from "../theme";
import { RunRow } from "../desk/components";
import { RunAnalytics } from "./RunAnalytics";
import {
  absenceLabel, absenceOf, foldTally, gateSentence,
  type CandidateRow,
} from "./candidateAnalytics";

/**
 * THE BELT'S INDEX — every run the factory has judged, opening into its evidence.
 *
 * The CEO's ask, 2026-08-21: *"the quant page aka lab has no analytics making it
 * hard for me to understand agents runs ... unify the experience so I can
 * validate agents runs same way i would mine"*.
 *
 * The unification is structural rather than cosmetic. A run YOU execute in the
 * editor above renders through `LeanResults`: verdict, curve, robustness,
 * capacity, fills, in that order. A run an AGENT executed down the belt now
 * renders through `RunAnalytics` in the same order, from the same engine
 * output. Neither surface computes anything the other does not; both read the
 * record and neither recomputes a criterion.
 *
 * Absence rules on this index, all deliberate:
 *
 *   * a candidate with no stored evidence carries a badge saying WHICH absence
 *     it is (never captured / aged out / not testable / unavailable), so the
 *     reader knows before opening whether there is anything to open;
 *   * ORPHANED is shown and is neither passed nor killed — an interrupted run
 *     produced no evidence, and scoring it either way would invent one;
 *   * a spine that cannot be read says the belt's history is UNKNOWN, not empty.
 *     An empty table on a dead spine reads as "the fund has tested nothing".
 */

const stateTone = (c: CandidateRow) =>
  c.passed === true ? KT.up
    : c.state === "orphaned" ? KT.sev.warn
      : c.state === "failed" ? KT.sev.warn
        : c.passed === false ? KT.down : KT.muted;

const stateLabel = (c: CandidateRow) =>
  c.state === "orphaned" ? "orphaned"
    : c.state === "running" ? "running"
      : c.state === "failed" ? "errored"
        : c.passed === true ? "PASSED" : c.passed === false ? "killed" : "unjudged";

/**
 * WHO RAN THE BELT — the desk's own run-record envelope, unchanged.
 *
 * Rendered through `RunRow`, the SAME component the desk pages use, so a seat's
 * run reads identically wherever it is met (CEO direction 2026-08-21: "unify the
 * experience"). A second, prettier rendering of the same record is exactly how
 * two surfaces start disagreeing.
 *
 * NOT JOINED to the candidates below, and that is stated rather than hidden. A
 * run record carries `run_id`, `trace_id` and `artifact_path` — it carries no
 * candidate ids, so any line drawn between a seat's run and a belt row would be
 * inferred from an algorithm name and a timestamp. An inferred link that renders
 * like a recorded one is worse than no link: it is a claim about provenance the
 * record cannot support.
 */
function WhoRan({ runs, err }: { runs: DeskView["runs"] | null; err: string | null }) {
  if (err) {
    return (
      <p className={`mb-4 text-[11px] ${KT.sev.warn}`}>
        The bench&apos;s run records could not be read ({err}) — who ran the belt is
        unknown, not nobody.
      </p>
    );
  }
  if (runs === null) return null;
  if (runs.length === 0) {
    return (
      <p className={`mb-4 text-[11px] ${KT.muted}`}>
        No quant-seat run has been recorded. The candidates below were submitted
        by hand or by a seat that filed no run record.
      </p>
    );
  }
  return (
    <div className="mb-5">
      <p className={`${KT.label} mb-2`}>Who ran the belt</p>
      <div className="space-y-1.5">
        {runs.slice(0, 5).map((r) => <RunRow key={r.run_id} run={r} />)}
      </div>
      <p className={`mt-2 text-[10px] leading-relaxed ${KT.muted}`}>
        The bench&apos;s run records, exactly as the desk shows them. They are NOT
        joined to the candidates below — a run record carries no candidate id, so
        a line between the two would be inferred rather than recorded.
      </p>
    </div>
  );
}

export function BeltRuns() {
  const [rows, setRows] = useState<CandidateRow[] | null>(null);
  const [board, setBoard] = useState<Awaited<
    ReturnType<typeof fundApiClient.getCandidates>>["scoreboard"] | null>(null);
  const [runs, setRuns] = useState<DeskView["runs"] | null>(null);
  const [runsErr, setRunsErr] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Record<string, CandidateRow | "error">>({});

  const load = useCallback(async () => {
    // Settled, not awaited together: the belt's history and the bench's run
    // records fail independently, and one being unreadable must not blank the
    // other. Each renders its own absence.
    const [c, r] = await Promise.allSettled([
      fundApiClient.getCandidates(undefined, 50),
      fundApiClient.getDeskRuns("quant", 25),
    ]);
    if (c.status === "fulfilled") {
      setRows(c.value.candidates ?? []);
      setBoard(c.value.scoreboard ?? null);
      setErr(null);
    } else {
      setErr(c.reason instanceof Error ? c.reason.message : "unreachable");
    }
    if (r.status === "fulfilled") { setRuns(r.value.runs ?? []); setRunsErr(null); }
    else setRunsErr(r.reason instanceof Error ? r.reason.message : "unreachable");
  }, []);

  useEffect(() => { load(); }, [load]);

  /** The payload is fetched only when a run is opened — 80 KB of equity curve
   *  per candidate is weight without a reader until then. */
  const toggle = useCallback(async (id: string) => {
    const next = openId === id ? null : id;
    setOpenId(next);
    if (!next || next in detail) return;
    try {
      const got = await fundApiClient.getCandidate(next);
      setDetail((m) => ({ ...m, [next]: got }));
    } catch {
      setDetail((m) => ({ ...m, [next]: "error" }));
    }
  }, [openId, detail]);

  const byAlgo = useMemo(() => {
    const m = new Map<string, CandidateRow[]>();
    for (const c of rows ?? []) {
      const list = m.get(c.algorithm) ?? [];
      list.push(c);
      m.set(c.algorithm, list);
    }
    return m;
  }, [rows]);

  if (err) {
    return (
      <section className="mt-10">
        <p className={`${KT.label} mb-1`}>The belt — what was judged</p>
        <WhoRan runs={runs} err={runsErr} />
        <p className={`text-sm ${KT.sev.warn}`}>
          The belt&apos;s history could not be read ({err}) — what has been tested
          is UNKNOWN, not nothing.
        </p>
      </section>
    );
  }
  if (rows === null) {
    return (
      <section className="mt-10">
        <p className={`${KT.label} mb-1`}>The belt — what was judged</p>
        <p className={`text-xs ${KT.muted}`}>reading…</p>
      </section>
    );
  }

  return (
    <section className="mt-10">
      <p className={`${KT.label} mb-1`}>The belt — what was judged, and on what evidence</p>
      <p className={`mb-4 max-w-3xl text-xs leading-relaxed ${KT.muted}`}>
        Every candidate the factory has sent down the belt. Open one to read the
        analytics behind its verdict — the equity curve against the benchmark,
        the walk-forward folds with each fold&apos;s own reason, the cost band, and
        the gate&apos;s sentences verbatim. The same questions, in the same order, as
        a run you execute yourself above.
      </p>

      <WhoRan runs={runs} err={runsErr} />

      {board && (
        <div className="mb-4 flex flex-wrap items-baseline gap-x-6 gap-y-1 text-[11px]">
          <span><span className={KT.muted}>submitted </span>{board.submitted}</span>
          <span><span className={KT.muted}>judged </span>{board.judged}</span>
          <span className={KT.up}><span className={KT.muted}>passed </span>{board.passed}</span>
          <span><span className={KT.muted}>killed </span>{board.killed}</span>
          <span className={board.orphaned ? KT.sev.warn : ""}>
            <span className={KT.muted}>orphaned </span>{board.orphaned}
          </span>
          {board.absence_note && (
            <span className={`w-full text-[10px] ${KT.sev.warn}`}>{board.absence_note}</span>
          )}
        </div>
      )}

      {rows.length === 0 ? (
        <p className={`text-xs ${KT.muted}`}>
          The belt has judged nothing yet — a real state, and a readable one.
        </p>
      ) : (
        <div className="space-y-2">
          {Array.from(byAlgo.entries()).map(([algo, list]) => (
            <div key={algo} className={`${KT.card} p-0`}>
              <div className="flex flex-wrap items-baseline gap-x-3 border-b border-[var(--kt-border)] px-4 py-2.5">
                <span className="font-mono text-sm text-[var(--kt-accent)]">{algo}</span>
                <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
                  {list.length} candidate{list.length === 1 ? "" : "s"}
                </span>
              </div>
              <div>
                {list.map((c) => {
                  const isOpen = openId === c.candidate_id;
                  const missing = absenceOf(c);
                  const t = foldTally(c.walkforward?.folds);
                  const g = gateSentence(c);
                  return (
                    <div key={c.candidate_id} className="border-b border-[var(--kt-border)] last:border-0">
                      <button
                        type="button"
                        onClick={() => toggle(c.candidate_id)}
                        aria-expanded={isOpen}
                        className="flex w-full flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-2.5 text-left transition-colors hover:bg-[var(--kt-hover)]"
                      >
                        <span className={`w-16 font-mono text-[10px] uppercase tracking-[0.1em] ${stateTone(c)}`}>
                          {stateLabel(c)}
                        </span>
                        <span className={`font-mono text-[11px] ${KT.muted}`}>
                          {String(c.started_at ?? "—").slice(0, 16).replace("T", " ")}
                        </span>
                        <span className="font-mono text-[11px]">
                          {c.winner
                            ? Object.entries(c.winner).map(([k, v]) => `${k}=${v}`).join(" ")
                            : <span className={KT.muted}>no winner</span>}
                        </span>
                        <span className={`text-[11px] ${KT.muted}`}>
                          {t.attempted > 0
                            ? `${t.retained}/${t.measurable} folds kept`
                            : c.walkforward?.folds_measurable != null
                              ? `${c.walkforward.folds_retained ?? 0}/${c.walkforward.folds_measurable} folds kept`
                              : "no folds"}
                          {t.timedOut > 0 && (
                            <span className={KT.sev.warn}> · {t.timedOut} engine-killed</span>
                          )}
                        </span>
                        <span className={`ml-auto flex items-baseline gap-3 text-[10px] ${KT.muted}`}>
                          {missing
                            ? <span className={KT.sev.warn}>{absenceLabel(missing.reason)}</span>
                            : <span className={KT.accent}>analytics</span>}
                          <span>{isOpen ? "− close" : "+ open"}</span>
                        </span>
                        <span className={`w-full text-[11px] ${KT.muted}`}>{g.sentence}</span>
                      </button>
                      {isOpen && (
                        <div className="border-t border-[var(--kt-border)] bg-[var(--kt-bg)] px-4 py-4">
                          {detail[c.candidate_id] === undefined ? (
                            <p className={`text-xs ${KT.muted}`}>reading the evidence…</p>
                          ) : detail[c.candidate_id] === "error" ? (
                            <p className={`text-xs ${KT.sev.warn}`}>
                              The analytics could not be read from the spine. Whether
                              this run has evidence is UNKNOWN — it is not absent.
                            </p>
                          ) : (
                            <RunAnalytics candidate={detail[c.candidate_id] as CandidateRow} />
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
