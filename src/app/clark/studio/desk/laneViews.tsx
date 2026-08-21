"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Skull } from "lucide-react";
import { fundApiClient, DeskView, MechanicsView, SpineEvent } from "@/lib/fund_api";
import { KT } from "../theme";
import { Metric, AbsentMetric, SectionHead } from "./components";
import {
  Cohort, Funnel, Pressure, Selector, Timeline,
} from "../components/mechanics/MechanicsViews";
import {
  DeskRun,
  SeatId,
  absent,
  artifactsForRuns,
  autopolicyAudit,
  killBoard,
  recFunnel,
} from "./seatLib";

/**
 * The track record, per lane — "whether to keep trusting this seat".
 *
 * Each seat is judged by something native to its job, because a common
 * scorecard would flatter the seats whose output is countable and punish the
 * ones whose output is a judgement. The adversary's number is kills; the pm's
 * is what the CEO did with its recommendations; the quant's is the belt.
 *
 * Where the brief asks for a metric no endpoint carries, this file renders the
 * absence and NAMES the missing field. That is not a placeholder to fill in
 * later — it is the finding: "mind-changers produced" is the adversary's best
 * measure and nothing in the fund records it.
 */

export function LaneTrackRecord({
  seat, runs, desk, events,
}: {
  seat: SeatId;
  runs: DeskRun[];
  desk: DeskView | null;
  events: SpineEvent[];
}) {
  return (
    <section className="mb-10">
      <SectionHead
        title="Track record"
        lede="The lane's own measure — what this seat is for, counted."
      />
      {seat === "mechanism" && <MechanismLane desk={desk} runs={runs} />}
      {seat === "analyst" && <AnalystLane runs={runs} />}
      {seat === "pm" && <PmLane runs={runs} />}
      {seat === "quant" && <QuantLane runs={runs} />}
      {seat === "adversary" && <AdversaryLane desk={desk} runs={runs} />}
      {seat === "validator" && <ValidatorLane runs={runs} />}
      {seat === "riskofficer" && <RiskOfficerLane events={events} />}
      {seat === "builder" && <BuilderLane runs={runs} />}
    </section>
  );
}

/* ------------------------------------------------------------ mechanism --- */

function MechanismLane({ desk, runs }: { desk: DeskView | null; runs: DeskRun[] }) {
  const proposals = (desk?.artifacts ?? []).filter((a) => a.kind === "proposal");
  const killed = proposals.filter((a) => a.status === "killed").length;
  const survives = proposals.filter((a) => a.status === "survives").length;
  const awaiting = proposals.filter((a) => a.status === "under_review").length;
  return (
    <>
      <div className={`${KT.card} flex flex-wrap gap-x-10 gap-y-4`}>
        <Metric label="proposals on the desk" value={proposals.length}
                sub="docs/proposals/*.md, read by the spine at request time" />
        <Metric label="killed" value={killed} tone="text-[var(--kt-down)]"
                sub="a demonstrated kill is a win" />
        <Metric label="survives" value={survives} />
        <Metric label="awaiting attack" value={awaiting}
                sub="unreviewed is not the same as surviving" />
        <Metric label="runs recorded" value={runs.length} />
      </div>
      <div className="mt-3">
        <AbsentMetric a={absent(
          "claim-type split (premia vs alpha)",
          "the claim type is declared inside the proposal markdown; GET /fund/desk returns only kind/status/review for an artifact. Needs desk._artifacts() to parse and expose claim_type.",
        )} />
      </div>
      <ArtifactList artifacts={proposals} />
    </>
  );
}

/* --------------------------------------------------------------- analyst -- */

function AnalystLane({ runs }: { runs: DeskRun[] }) {
  const [corpus, setCorpus] = useState<{ observations: number; tickers: number;
                                         filings_read: number; last_extracted_at?: string | null } | null>(null);
  const [corpusErr, setCorpusErr] = useState(false);

  useEffect(() => {
    let alive = true;
    fundApiClient.getObservationsCoverage()
      .then((r) => { if (alive) setCorpus(r.coverage); })
      .catch(() => { if (alive) setCorpusErr(true); });
    return () => { alive = false; };
  }, []);

  const delivered = runs.filter((r) => r.artifact_path).length;
  return (
    <>
      <div className={`${KT.card} flex flex-wrap gap-x-10 gap-y-4`}>
        <Metric label="memos delivered" value={delivered}
                sub="runs that named an artifact path" />
        <Metric label="runs recorded" value={runs.length} />
        <Metric
          label="corpus observations"
          value={corpusErr ? "—" : corpus?.observations ?? "…"}
          sub={corpusErr
            ? "corpus unreadable — not an empty corpus"
            : corpus
              ? `${corpus.tickers} tickers · ${corpus.filings_read} filings read`
              : "reading GET /fund/research/observations"}
        />
      </div>
      {corpus?.last_extracted_at && (
        <p className={`mt-2 text-[11px] ${KT.muted}`}>
          Last extraction {corpus.last_extracted_at.slice(0, 16).replace("T", " ")}Z.
          The corpus is the analyst's raw material; it is read live here rather
          than quoted, because a number written into a page goes stale silently.
        </p>
      )}
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        <AbsentMetric a={absent(
          "verdict outcomes on theses",
          "a thesis memo's outcome lives in the adversary's review doc, not in a field. GET /fund/desk exposes review verdicts only for docs/proposals/** and gate designs — theses in docs/research/** are outside the artifact fold.",
        )} />
        <AbsentMetric a={absent(
          "runner-ups parked",
          "nothing records the names a survey considered and set aside; it would need a field on the run or a parked-candidates table.",
        )} />
      </div>
      <VerdictList runs={runs} />
    </>
  );
}

/* -------------------------------------------------------------------- pm -- */

function PmLane({ runs }: { runs: DeskRun[] }) {
  const f = recFunnel(runs);
  const bars: { label: string; n: number; tone?: string }[] = [
    { label: "made", n: f.made },
    { label: "open", n: f.open },
    { label: "accepted", n: f.accepted },
    { label: "rejected", n: f.rejected, tone: "text-[var(--kt-down)]" },
    { label: "staged", n: f.staged },
    { label: "done", n: f.done },
    // Read and closed without a decision (CEO, 2026-08-21) — a real outcome,
    // and one the funnel would otherwise lose.
    { label: "noted", n: f.noted },
  ];
  // Only drawn when it is non-zero: an "unrecognised" bar at 0 is noise, and a
  // missing one when it is not 0 is a funnel that does not add up.
  if (f.other > 0) bars.push({ label: "unrecognised", n: f.other,
                               tone: "text-[var(--kt-warn)]" });
  const max = Math.max(1, f.made);
  return (
    <>
      <div className={`${KT.card}`}>
        <p className={`${KT.label} mb-3`}>Decision funnel</p>
        <div className="space-y-1.5">
          {bars.map((b) => (
            <div key={b.label} className="flex items-center gap-3">
              <span className={`w-20 shrink-0 font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
                {b.label}
              </span>
              <span className={`w-8 shrink-0 text-right font-mono text-xs tabular-nums ${b.tone ?? ""}`}>
                {b.n}
              </span>
              <div className="h-4 min-w-0 flex-1 overflow-hidden rounded bg-[var(--kt-inset)]">
                <div className="h-full rounded bg-[var(--kt-accent)]/30 transition-[width] duration-1000 ease-out"
                     style={{ width: `${(b.n / max) * 100}%` }} />
              </div>
            </div>
          ))}
        </div>
        <p className={`mt-3 text-xs leading-relaxed ${KT.muted}`}>
          Folded from every recommendation on this seat&apos;s runs
          (<span className="font-mono">run.recommendations[].status</span>), not from the
          open-recommendations list — that list carries only open, accepted and
          staged, so a funnel built on it would show a fund that has never
          rejected anything.
        </p>
      </div>
      <div className="mt-3">
        <AbsentMetric a={absent(
          "what an accepted recommendation became",
          "the link from an accepted rec to the order it was staged as exists only in the order's rationale marker ([pm · rec N]); GET /fund/desk does not join them. Needs the rec row to carry the order_id the CTO staged.",
        )} />
      </div>
    </>
  );
}

/* ----------------------------------------------------------------- quant -- */

function QuantLane({ runs }: { runs: DeskRun[] }) {
  const [m, setM] = useState<MechanicsView | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    fundApiClient.getMechanics()
      .then((r) => { if (alive) { setM(r); setErr(null); } })
      .catch((e) => { if (alive) setErr(e instanceof Error ? e.message : "unreachable"); });
    return () => { alive = false; };
  }, []);

  const nonCal = (m?.cohort?.candidates ?? []).filter((c) => !c.is_calibration);
  const variants = nonCal.reduce((a, c) => a + (c.variants || 0), 0);

  return (
    <>
      <div className={`${KT.card} flex flex-wrap gap-x-10 gap-y-4`}>
        <Metric label="candidates submitted" value={m ? nonCal.length : "—"}
                sub="excludes calibration instruments — they measure the gate" />
        <Metric label="variants swept" value={m ? variants : "—"}
                sub="product of each candidate's grid" />
        <Metric label="gate version" value={m?.gate_version ?? "—"} />
        <Metric label="runs recorded" value={runs.length} />
      </div>
      {err && (
        <p className={`mt-2 text-xs ${KT.sev.warn}`}>
          Mechanics unreadable ({err}) — the belt&apos;s figures below are absent,
          not zero.
        </p>
      )}
      <div className="mt-3">
        <AbsentMetric a={absent(
          "container runs consumed per candidate",
          "GET /fund/mechanics exposes grid size (variants), not engine invocations. A container-run counter would have to come from the LEAN runner's own job rows.",
        )} />
      </div>
      <VerdictList runs={runs} />
      {m && (
        <div className="mt-8">
          {/* The belt's own charts live here now: this is the lane that submits
              candidates, so the funnel and the causes of death sit beside the
              seat that acts on them. */}
          <Funnel m={m} />
          <Pressure m={m} />
          <Selector m={m} />
          <Cohort m={m} />
          <Timeline m={m} />
        </div>
      )}
    </>
  );
}

/* ------------------------------------------------------------- adversary -- */

function AdversaryLane({ desk, runs }: { desk: DeskView | null; runs: DeskRun[] }) {
  const b = killBoard(runs, desk?.artifacts ?? []);
  return (
    <>
      <div className={`${KT.card} flex flex-wrap gap-x-10 gap-y-4`}>
        <Metric label="KILL" value={b.kill} tone="text-[var(--kt-down)]"
                sub="a kill is a win at this firm" />
        <Metric label="SURVIVES" value={b.survives} />
        <Metric label="CANNOT TELL" value={b.cannotTell}
                sub="its own verdict, never folded into either side" />
        <Metric label="artifacts reviewed" value={b.reviewed.length} />
        <Metric label="unreviewed on the desk" value={b.unreviewed.length}
                sub="unreviewed is not surviving" />
      </div>
      <p className={`mt-2 text-[11px] leading-relaxed ${KT.muted}`}>
        Counted from this seat&apos;s run verdicts plus every review on file in the
        artifact chain (<span className="font-mono">artifact.review.verdict</span>).
        A verdict is read from its opening word, so a review that merely mentions
        the word &ldquo;kill&rdquo; is not counted as one.
      </p>
      <div className="mt-3">
        <AbsentMetric a={absent(
          "mind-changers — verdicts that changed a design",
          "no field links a review to the design revision it forced. It would need the review doc, or the run, to name the artifact version it changed.",
        )} />
      </div>
      <ArtifactList artifacts={b.reviewed} />
    </>
  );
}

/* ------------------------------------------------------------- validator -- */

function ValidatorLane({ runs }: { runs: DeskRun[] }) {
  const filed = runs.filter((r) => r.artifact_path).length;
  return (
    <>
      <div className={`${KT.card} flex flex-wrap gap-x-10 gap-y-4`}>
        <Metric label="measurements filed" value={filed}
                sub="runs that named an artifact path" />
        <Metric label="runs recorded" value={runs.length} />
        <Metric label="recommendations made" value={recFunnel(runs).made} />
        <Metric label="accepted + done" value={recFunnel(runs).accepted + recFunnel(runs).done}
                sub="the CEO acted on these" />
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        <AbsentMetric a={absent(
          "method, sample size and confidence per measurement",
          "these live in the prose of each finding doc; no field carries them. Exposing them would need the audit register to store a structured row per measurement.",
        )} />
        <AbsentMetric a={absent(
          "defects confirmed in our own instruments",
          "the firm's own metric, and nothing counts it: a confirmed defect is currently a sentence in a doc. Needs a defect register (finding -> instrument -> confirmed/refuted).",
        )} />
      </div>
      <VerdictList runs={runs} />
    </>
  );
}

/* ----------------------------------------------------------- riskofficer -- */

function RiskOfficerLane({ events }: { events: SpineEvent[] }) {
  const a = autopolicyAudit(events);
  return (
    <>
      <div className={`${KT.card} flex flex-wrap gap-x-10 gap-y-4`}>
        <Metric label="auto-approvals" value={a.auto.length}
                sub="approvals whose approver names the policy" />
        <Metric label="approvals in window" value={a.approvals}
                sub="every OrderApproved event read" />
        <Metric label="exit rules fired" value={a.exitsFired}
                sub="the only orders v1's envelope can cover" />
        <Metric label="halt / resume events" value={a.halts} />
      </div>
      <p className={`mt-2 text-[11px] leading-relaxed ${KT.muted}`}>
        An auto-approval is identified by{" "}
        <span className="font-mono">payload.approver</span> beginning
        &ldquo;auto-policy&rdquo; — the string app/fund/autopolicy.py writes when it
        approves through the ordinary pipeline. Zero here means zero such events
        in the window read, which is a measurement, not an assumption.
      </p>
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        <AbsentMetric a={absent(
          "the live envelope and its version",
          "AUTOPOLICY_VERSION and the check list exist only inside app/fund/autopolicy.py and in each approval's payload; no GET endpoint exposes the policy itself. Needs GET /fund/autopolicy (read-only).",
        )} />
        <AbsentMetric a={absent(
          "envelope-change recommendations, by version",
          "recommendations carry a seat and a status but no envelope version, so a recommendation to widen v1 cannot be told from one about v2.",
        )} />
      </div>
      <p className={`mt-4 text-sm ${KT.muted}`}>
        The evidence base for this seat is the risk engine&apos;s six measured
        modules —{" "}
        <Link href="/clark/studio/risk" className={KT.accent}>
          open /risk
        </Link>
        . Linked, never duplicated: two renderings of the same limit is how two
        pages start disagreeing about whether it is breached.
      </p>
    </>
  );
}

/* --------------------------------------------------------------- builder -- */

function BuilderLane({ runs }: { runs: DeskRun[] }) {
  return (
    <>
      <div className={`${KT.card} flex flex-wrap gap-x-10 gap-y-4`}>
        <Metric label="briefs completed" value={runs.length}
                sub="runs recorded for this seat" />
        <Metric label="with an artifact" value={runs.filter((r) => r.artifact_path).length} />
        <Metric label="recommendations made" value={recFunnel(runs).made} />
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        <AbsentMetric a={absent(
          "diffs merged vs rejected",
          "the merge decision happens in git, and nothing writes it back to the desk. It would need the CTO's resolve to record the merge commit (or the rejection) on the run.",
        )} />
        <AbsentMetric a={absent(
          "tests-passed record",
          "test results are reported in the run's prose; no field carries pass/fail counts. A structured field on the run would make this countable.",
        )} />
      </div>
      <VerdictList runs={runs} />
    </>
  );
}

/* ---------------------------------------------------------------- shared -- */

function VerdictList({ runs }: { runs: DeskRun[] }) {
  const withVerdict = runs.filter((r) => r.verdict);
  if (!withVerdict.length) return null;
  return (
    <div className="mt-4">
      <p className={`${KT.label} mb-2`}>Verdicts, verbatim</p>
      <div className="space-y-1">
        {withVerdict.map((r) => (
          <div key={r.run_id} className={`${KT.inset} flex flex-wrap items-baseline gap-x-3 p-2.5 text-xs`}>
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--kt-text-dim)]">
              {r.resolved_at ? r.resolved_at.slice(0, 10) : "undated"}
            </span>
            <span className="min-w-0 flex-1">{r.verdict}</span>
            {r.artifact_path && (
              <span className={`font-mono text-[10px] ${KT.muted}`}>{r.artifact_path}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function ArtifactList({ artifacts }: { artifacts: DeskView["artifacts"] }) {
  if (!artifacts.length) return null;
  return (
    <div className="mt-4">
      <p className={`${KT.label} mb-2`}>Artifacts</p>
      <div className="space-y-1.5">
        {artifacts.map((a) => (
          <div key={a.path}
               className={`${KT.card} border-l-2 p-3 ${
                 a.status === "killed" ? "border-l-[var(--kt-down)]"
                   : a.status === "survives" ? "border-l-[var(--kt-accent)]"
                     : "border-l-[var(--kt-warn)]"}`}>
            <div className="flex flex-wrap items-center gap-2">
              {a.status === "killed" && <Skull size={11} className="text-[var(--kt-down)]" />}
              <span className="text-sm font-medium">{a.title}</span>
              <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
                {a.status.replace("_", " ")}
              </span>
            </div>
            <p className={`mt-1 font-mono text-[10px] ${KT.muted}`}>{a.path}</p>
            {a.review && (
              <p className={`mt-1 text-xs ${KT.muted}`}>
                <span className="text-[var(--kt-down)]">{a.review.verdict}</span> —{" "}
                {a.review.review_title}{" "}
                <span className="font-mono text-[10px]">({a.review.review_path})</span>
              </p>
            )}
            {a.note && <p className={`mt-1 text-xs italic ${KT.muted}`}>{a.note}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}

export { artifactsForRuns };
