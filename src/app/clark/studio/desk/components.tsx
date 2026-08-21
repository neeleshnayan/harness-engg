"use client";

import React, { useState } from "react";
import { fundApiClient, DeskView } from "@/lib/fund_api";
import { KT } from "../theme";
import { ProvenanceChip } from "../components/Provenance";
import { VerdictStamp } from "./MemoThread";
import {
  DeskRun,
  ShelfItem,
  fmtAt,
  fmtTokens,
  fmtUsd,
  estimateCostUsd,
  isAbsent,
  verdictStamp,
  Absent,
} from "./seatLib";
import {
  SeatTelemetry, costLabel, telemetryNote, tokensLabel,
} from "./deskTelemetry";

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

/* ----------------------------------------------------- production shelf --- */

/**
 * What a desk produced, across time — memo spines on a shelf, newest first.
 *
 * The metaphor is literal: each row is the SPINE of a filed document, so the
 * eye runs down dates and titles the way it runs down a shelf. The left rule
 * carries the artifact's status (killed / survives / under review) and is the
 * only colour on the row; a run that filed nothing gets a dim rule and says so,
 * because "delivered, filed nothing" and "produced nothing" are different facts
 * about the record.
 *
 * TraceFlow used to live here. It was replaced by MemoThread (2026-08-20 brief)
 * and deleted rather than left importable — a second, prettier rendering of the
 * same trace is exactly how the audit view and the working view start to
 * disagree.
 */
export function ProductionShelf({ items, emptyNote }: {
  items: ShelfItem[];
  emptyNote: string;
}) {
  if (!items.length) return <p className={`text-sm ${KT.muted}`}>{emptyNote}</p>;
  return (
    <ol className="space-y-1.5">
      {items.map((s) => {
        const stamp = verdictStamp(s.verdict);
        const rule =
          s.status === "killed" ? "border-l-[var(--kt-down)]"
            : s.status === "survives" ? "border-l-[var(--kt-accent)]"
              : s.status === "under_review" ? "border-l-[var(--kt-warn)]"
                : "border-l-[var(--kt-border-strong)]";
        return (
          <li key={s.runId} className={`${KT.inset} border-l-2 ${rule} px-3 py-2`}>
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className={`w-[5.5rem] shrink-0 font-mono text-[10px] tabular-nums ${KT.muted}`}>
                {s.at ? s.at.slice(0, 10) : "undated"}
              </span>
              <span className="min-w-0 flex-1 text-[13px] leading-snug">{s.title}</span>
              {s.kind && (
                <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
                  {s.kind}
                </span>
              )}
              {stamp && <VerdictStamp verdict={stamp} tone={stamp === "KILL" ? "kill" : "neutral"} />}
            </div>
            <p className={`mt-1 font-mono text-[10px] ${KT.muted}`}>
              {s.path ?? "no artifact path recorded on this run — delivered, but nothing filed"}
              {s.titleFrom === "task" && s.path && (
                <span
                  title="The desk's artifact fold does not carry this path, so the spine cannot supply the document's own title. What is shown is the run's task."
                >
                  {" · title from the run"}
                </span>
              )}
            </p>
            {/* A verdict too long to stamp prints verbatim rather than being
                compressed into a word the seat did not say. */}
            {s.verdict && !stamp && (
              <p className={`mt-1 text-[11px] leading-relaxed ${KT.body}`}>{s.verdict}</p>
            )}
          </li>
        );
      })}
    </ol>
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

/**
 * The COO triage chip: how loaded the CEO's desk is, against the registered
 * trigger.
 *
 * The CEO's standing rule (2026-08-20) is a COO triage dispatch when open items
 * pass 20. The rule existed and nothing counted, so "am I over the line?" was a
 * question only a manual tally could answer.
 *
 * Three states and they are all different facts:
 *   - absent load     → renders nothing. A spine that does not report the count
 *                       has not reported a low one.
 *   - incomplete      → the total is a FLOOR and says which part it could not
 *                       count. A desk over the line must not look under it
 *                       because a component was unreadable.
 *   - over the line   → "COO triage due". A SIGNAL for the CTO to dispatch;
 *                       this chip fires nothing and neither does the spine.
 */
export function CooTriageChip({ load }: { load?: DeskView["desk_load"] }) {
  if (!load) return null;
  const over = load.coo_triage_due;
  return (
    <span
      title={load.note}
      className={`ml-2 inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] ${
        over
          ? "border-[var(--kt-warn)] text-[var(--kt-warn)]"
          : `border-[var(--kt-border)] ${KT.muted}`
      }`}
    >
      <span className="tabular-nums">
        {load.total}
        {!load.complete && "+"}
      </span>
      <span>/ {load.threshold} open</span>
      {over && <span>· COO triage due</span>}
      {!load.complete && (
        <span title={`could not count: ${load.unreadable.join(", ")}`}>
          · partial
        </span>
      )}
    </span>
  );
}

/* ------------------------------------------------------- desk telemetry --- */

/**
 * "Is it running, how often today, at what token cost" — the CEO's three
 * figures, rendered identically on the 2D bench card and in the 3D floor's
 * desk detail.
 *
 * ONE component for both surfaces, deliberately: two renderings of the same
 * three numbers is how a reader ends up trusting whichever one is prettier, and
 * these three in particular are the ones the CEO will compare across surfaces.
 *
 * Three rules it keeps:
 *   1. An ABSENT figure renders as its sentence, never as a dash the eye reads
 *      as zero and never as a chip that is simply missing.
 *   2. A token sum missing a run's figure renders with "≥" and the caveat is in
 *      the title, which is also where the price-table provenance lives.
 *   3. RUNNING is a word, not only a dot. The dot has been on the card for a
 *      while and the CEO still had to ask whether seats were running — a marker
 *      you only notice when you were already looking is not an answer.
 */
export function SeatTelemetryChips({ t, compact = false }: {
  t: SeatTelemetry; compact?: boolean;
}) {
  const note = telemetryNote(t);
  const runs = t.runsToday;
  const toks = t.tokensToday;

  const gap: Absent | null =
    isAbsent(runs) ? runs : isAbsent(toks) ? (toks as Absent) : null;

  // Compact (the seat cards): ONE chip — "×N" runs today. The card already
  // carries the running/idle status word under the seat's name (CEO,
  // 2026-08-21: "we already have running status just below their name; I
  // just wanted something #x that shows how many runs"), and token depth
  // lives on the seat's own desk page. The absence rule survives as a
  // dashed "×?" — unmeasured must never read as zero, but it earns one
  // small chip, not a row.
  if (compact) {
    return (
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {typeof runs === "number" ? (
          <span title={note ?? `${runs} run${runs === 1 ? "" : "s"} today`}
                className={`inline-flex items-center gap-0.5 rounded-full border border-[var(--kt-border)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
            ×<span className="tabular-nums text-[var(--kt-text)]">{runs}</span>
          </span>
        ) : gap ? (
          <span
            title={`${gap.what} — not measured: ${gap.needs}.`}
            className={`inline-flex items-center rounded-full border border-dashed border-[var(--kt-border-strong)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}
          >
            ×?
          </span>
        ) : null}
      </div>
    );
  }

  return (
    <div className="mt-2 space-y-1.5">
      <div className="flex flex-wrap items-center gap-1.5">
        <span
          title={t.runningNow && t.runningTask ? t.runningTask : "No dispatch is open for this seat."}
          className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] ${
            t.runningNow
              ? "border-[var(--kt-warn)] text-[var(--kt-warn)]"
              : `border-[var(--kt-border)] ${KT.muted}`
          }`}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${
            t.runningNow ? "kt-breathe bg-[var(--kt-warn)]" : "bg-[var(--kt-border-strong)]"}`} />
          {t.runningNow ? "running now" : "not running"}
        </span>

        {typeof runs === "number" ? (
          <span title={note}
                className={`inline-flex items-center gap-1 rounded-full border border-[var(--kt-border)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
            <span className="tabular-nums text-[var(--kt-text)]">{runs}</span>
            run{runs === 1 ? "" : "s"} today
          </span>
        ) : null}

        {typeof toks === "number" ? (
          <span title={note}
                className={`inline-flex items-center gap-1 rounded-full border border-[var(--kt-border)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
            <span className="tabular-nums text-[var(--kt-text)]">{tokensLabel(t)}</span>
            tok
            {t.costUsdToday != null && (
              <span className="tabular-nums">· {costLabel(t)}</span>
            )}
          </span>
        ) : null}
      </div>

      {/* Full sentences, on the roomier surface (the floor's desk detail). */}
      {!compact && gap && (
        <p className={`text-[11px] leading-relaxed ${KT.muted}`}>
          {gap.what} — not measured: {gap.needs}.
        </p>
      )}
      {!compact && !gap && note && (
        <p className={`text-[11px] leading-relaxed ${KT.muted}`}>{note}</p>
      )}
    </div>
  );
}

export { ProvenanceChip };
