"use client";

import React, { useState } from "react";
import Link from "next/link";
import { fundApiClient, DeskView } from "@/lib/fund_api";
import { KT } from "../theme";
import { ProvenanceChip } from "../components/Provenance";
import {
  DeskRun,
  TraceThread,
  fmtAt,
  fmtTokens,
  fmtUsd,
  estimateCostUsd,
  isAbsent,
  Absent,
} from "./seatLib";

/**
 * The desk's shared rendering vocabulary.
 *
 * RunRow and RecRow were written inside desk/page.tsx and are now used by nine
 * pages. Extracted rather than copied: two renderings of the same run that
 * drift apart is how a reader ends up trusting whichever one is prettier.
 */

/* --------------------------------------------------------------- chrome --- */

export function SectionHead({ title, lede }: { title: string; lede?: string }) {
  return (
    <div className="mb-3">
      <h2 className="text-lg font-medium tracking-tight">{title}</h2>
      {lede && <p className={`mt-0.5 max-w-2xl text-sm ${KT.muted}`}>{lede}</p>}
    </div>
  );
}

/** A metric that does not exist yet, rendered as a sentence naming what would
 *  supply it. The alternative — omitting it — hides the gap; the other
 *  alternative — a zero — asserts something false. */
export function AbsentMetric({ a }: { a: Absent }) {
  return (
    <div className={`${KT.inset} p-3`}>
      <p className={`${KT.label}`}>{a.what}</p>
      <p className={`mt-1 text-xs leading-relaxed ${KT.muted}`}>
        not measured — {a.needs}
      </p>
    </div>
  );
}

/** One figure with its label. `null` renders an em dash, never a zero. */
export function Metric({
  label, value, sub, tone,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  tone?: string;
}) {
  return (
    <div className="min-w-[7rem]">
      <p className={KT.label}>{label}</p>
      <p className={`mt-0.5 font-mono text-xl font-light tabular-nums ${tone ?? ""}`}>
        {value == null ? "—" : value}
      </p>
      {sub && <p className={`mt-0.5 text-[11px] leading-snug ${KT.muted}`}>{sub}</p>}
    </div>
  );
}

export function MetricOrAbsent({
  label, value, sub, tone,
}: {
  label: string;
  value: React.ReactNode | Absent;
  sub?: React.ReactNode;
  tone?: string;
}) {
  if (isAbsent(value)) return <AbsentMetric a={value} />;
  return <Metric label={label} value={value as React.ReactNode} sub={sub} tone={tone} />;
}

/* ---------------------------------------------------------------- rows ---- */

export function RecRow({ r, onDecide }: {
  r: DeskView["open_recommendations"][number];
  onDecide: () => Promise<void> | void;
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const decide = async (status: "accepted" | "rejected") => {
    setBusy(true);
    setErr(null);
    try {
      await fundApiClient.decideRecommendation(r.run_id, r.rec_id, { status, actor: "ceo" });
      await onDecide();
    } catch (e) {
      // A decision that failed must not look like a decision that landed.
      setErr(e instanceof Error ? e.message : "the spine did not record it");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className={`${KT.card} flex flex-wrap items-center gap-3 p-3`}>
      <ProvenanceChip kind="agent" seat={r.seat} recId={r.rec_id} />
      <span className="min-w-0 flex-1 text-sm leading-snug">{r.text}</span>
      {r.status === "open" ? (
        <span className="flex shrink-0 gap-2">
          <button type="button" disabled={busy} onClick={() => decide("accepted")}
            className={`${KT.btn} px-2 py-1 text-xs disabled:opacity-40`}>
            Accept
          </button>
          <button type="button" disabled={busy} onClick={() => decide("rejected")}
            className="rounded-lg border border-[var(--kt-border)] px-2 py-1 text-xs text-[var(--kt-text-dim)] hover:border-[var(--kt-down)] hover:text-[var(--kt-down)] disabled:opacity-40">
            Reject
          </button>
        </span>
      ) : (
        <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${r.status === "staged" ? "text-[var(--kt-warn)]" : KT.muted}`}>
          {r.status}
        </span>
      )}
      {err && (
        <p className="w-full text-[11px] text-[var(--kt-down)]">
          Not recorded: {err} — the recommendation is still open.
        </p>
      )}
    </div>
  );
}

export function RunRow({ run, showSeat = true }: { run: DeskRun; showSeat?: boolean }) {
  const [open, setOpen] = useState(false);
  const bullets = (run.reasoning || "")
    .split("\n")
    .map((l) => l.replace(/^[-*•]\s*/, "").trim())
    .filter(Boolean);
  const cost = estimateCostUsd(run.model, run.tokens);
  return (
    <div className={`${KT.card} p-3 text-xs`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full flex-wrap items-baseline gap-x-3 gap-y-1 text-left"
      >
        {showSeat && <span className="font-mono text-[var(--kt-accent)]">{run.seat}</span>}
        <span className="min-w-0 flex-1 truncate">{run.task}</span>
        {run.verdict && (
          <span className={`font-mono text-[10px] uppercase ${run.verdict === "KILL" || run.verdict === "KILLED" ? "text-[var(--kt-down)]" : KT.muted}`}>
            {run.verdict}
          </span>
        )}
        {run.tokens != null && (
          <span className={`font-mono text-[10px] tabular-nums ${KT.muted}`}>
            {fmtTokens(run.tokens)} tok
          </span>
        )}
        <span className={`font-mono text-[10px] ${KT.muted}`}>
          {bullets.length ? (open ? "− why" : "+ why") : ""}
        </span>
      </button>
      {open && bullets.length > 0 && (
        <ul className="mt-2 space-y-1 border-t border-[var(--kt-border)] pt-2">
          {bullets.map((b, i) => (
            <li key={i} className="flex gap-2 leading-relaxed">
              <span className="text-[var(--kt-accent)]">·</span>
              <span>{b}</span>
            </li>
          ))}
        </ul>
      )}
      {open && (
        <p className={`mt-1.5 font-mono text-[10px] leading-relaxed ${KT.muted}`}>
          {run.artifact_path && <>full record: {run.artifact_path} · </>}
          Postgres run {run.run_id}
          {run.trace_id && <> · trace {run.trace_id.slice(0, 8)}</>}
          {run.model && <> · model {run.model}</>}
          {run.resolved_at && <> · resolved {fmtAt(run.resolved_at)}</>}
          {cost != null && <> · ≈{fmtUsd(cost)} est.</>}
        </p>
      )}
      {open && !bullets.length && (
        <p className={`mt-1.5 text-[11px] italic ${KT.muted}`}>
          No reasoning bullets were recorded at resolve — the run is stored whole,
          but its distilled why is absent rather than empty.
        </p>
      )}
    </div>
  );
}

/* --------------------------------------------------------------- traces --- */

const NODE_GLYPH: Record<string, string> = {
  request: "ask",
  dispatch: "dispatch",
  run: "run",
  decision: "decision",
};

/**
 * One chatter thread as a directed flow: ask → dispatch → run(verdict) →
 * decision. Nodes carry actor and timestamp; the edges ARE the trace id.
 *
 * This is the CEO's "chatter flow, recreatable" and the audit view in one
 * drawing — which is the point: an audit that is a different picture from the
 * working view gets read once.
 */
export function TraceFlow({ t, dense = false }: { t: TraceThread; dense?: boolean }) {
  return (
    <div className={`${KT.card} p-3`}>
      <div className="mb-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className={`font-mono text-[10px] ${KT.muted}`}>
          trace {t.traceId.slice(0, 8)}
        </span>
        {t.synthetic && (
          <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--kt-warn)]"
                title="No trace_id was recorded on this item; it is shown as its own chain rather than merged into someone else's.">
            untraced
          </span>
        )}
        {t.seats.map((s) => (
          <Link key={s} href={`/clark/studio/desk/${s}`}
                className={`font-mono text-[10px] ${KT.accent} hover:underline`}>
            {s}
          </Link>
        ))}
        <span className={`ml-auto font-mono text-[10px] tabular-nums ${KT.muted}`}>
          {fmtAt(t.first)} → {fmtAt(t.last)}
        </span>
      </div>
      <ol className="flex flex-wrap items-stretch gap-1.5">
        {t.nodes.map((n, i) => (
          <React.Fragment key={i}>
            {i > 0 && (
              <li aria-hidden className={`self-center font-mono text-xs ${KT.muted}`}>→</li>
            )}
            <li className={`${KT.inset} min-w-[8rem] max-w-[18rem] flex-1 p-2`}>
              <p className={`font-mono text-[9px] uppercase tracking-[0.12em] ${
                n.kind === "run" ? KT.accent : KT.muted}`}>
                {NODE_GLYPH[n.kind]}
                {n.seat ? ` · ${n.seat}` : ""}
              </p>
              <p className={`mt-1 leading-snug ${dense ? "line-clamp-2 text-[11px]" : "text-xs"}`}>
                {n.label}
              </p>
              {n.verdict && (
                <p className="mt-1 font-mono text-[10px] uppercase text-[var(--kt-text-dim)]">
                  {n.verdict}
                </p>
              )}
              {n.status && (
                <p className={`mt-1 font-mono text-[10px] uppercase ${KT.muted}`}>{n.status}</p>
              )}
              <p className={`mt-1 font-mono text-[9px] tabular-nums ${KT.muted}`}>
                {n.actor ? `${n.actor} · ` : ""}{fmtAt(n.at)}
              </p>
            </li>
          </React.Fragment>
        ))}
      </ol>
    </div>
  );
}

/* --------------------------------------------------------------- shared --- */

/** The honest line about how far back a folded view can see. The events
 *  endpoint caps at 1000 rows, so a day older than the window is NOT a quiet
 *  day — it is a day this page cannot see. */
export function WindowNote({ events, capped }: { events: number; capped: boolean }) {
  return (
    <p className={`mt-2 text-[11px] italic leading-relaxed ${KT.muted}`}>
      Folded from the {events} most recent spine events
      {capped && " — the endpoint caps at 1000, so days older than the oldest event shown are outside this view, not quiet"}
      , plus the flight recorder's runs.
    </p>
  );
}

export { ProvenanceChip };
