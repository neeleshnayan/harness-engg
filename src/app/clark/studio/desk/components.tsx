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
import { ChipTotal, chipShowsTotal } from "./deskAwaiting";
import { NOBODY, isRecordRow, recordRowNote } from "./recordRow";
import { nextMoveLine } from "./cardAnatomy";

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

/* `MetricOrAbsent` was DELETED here (D31, cleanup ticket dce47670): a
   component with no caller in this repo, prod or test, since it was written.
   `AbsentMetric` and `Metric` are both live and are what callers reach for
   directly; the union wrapper only ever moved the branch one level up. */

/* ---------------------------------------------------------------- rows ---- */

/**
 * One recommendation, decidable in place.
 *
 * THE CONTROL EXISTS ON A DIFFERENT TEST FROM THE COUNT (D42, and the CEO's
 * *"like WTF"*). `status === "open"` used to decide both, and it is the wrong
 * question for the second: a row filed FOR THE RECORD is open forever, because
 * there is nothing in it to decide. This row is where he saw an
 * already-executed chair action carrying Accept and Reject — it is the only
 * component in the repo that offered a decision on `status` alone.
 */
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
      {/* QUESTION 4 OF THE RATIFIED CARD — WHOSE MOVE IS IT (D42).
          This flat list showed a row's STATUS and nothing about its owner, so
          32 of the 54 rows under "awaiting a decision" were the chair's and a
          reader could not tell. The arrow chip is `DeskMatrix`'s existing
          idiom rather than a second invention, the reason rides the tooltip,
          and the CEO's own rows show nothing: "→ ceo" on the CEO's queue is a
          badge on every row, which is how a badge stops meaning anything. A
          record row is skipped too — its sentence below already says it. */}
      {(() => {
        const move = nextMoveLine(r);
        if (!move || move.actor === "ceo" || move.actor === NOBODY) return null;
        return (
          <span className={`shrink-0 font-mono text-[10px] ${KT.muted}`}
                title={move.why ?? "the spine stated no reason"}>
            → {move.actor}
          </span>
        );
      })()}
      {r.status === "open" && isRecordRow(r) ? (
        /* No control, and a sentence where the buttons were. A record row
           whose controls simply vanished would read as a rendering failure.
           STATUS IS CHECKED FIRST, and it is not redundant: a row that was
           ACCEPTED and then routed to nobody is decided, not filed-for-record,
           and must keep saying "accepted". Found by writing the mutant, not by
           the suite — `splitRecordRows` and `rowLamp` both put the lifecycle
           ahead of the routing and this line did not. */
        <span className={`shrink-0 text-[11px] ${KT.muted}`}
              title={recordRowNote(r)}>
          filed for the record
        </span>
      ) : r.status === "open" ? (
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
        {/* THE SPEND-DEMOTION RULE (docs/design/RUN_PAGE_2026-08-24.md; CEO,
            verbatim: *"this puts the spend on my focus lens; I am more
            interested in the work being done. this can be a small mention per
            ticket not the focus."*). The token count used to sit HERE, on the
            card's face, beside the verdict — the second-most prominent thing
            on a row about a piece of work. It moved to the metadata footer
            below, which already carries the model, the trace and the cost
            estimate; nothing is deleted and the figure is one click away on
            every row that had it. */}
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
          {/* The spend, in the one place the spec allows it: the small muted
              metadata line, beside the model and the trace. NOTHING IS LOST —
              the figure that was on the face is here, verbatim, and an absent
              one still says so rather than reading as zero. */}
          {run.tokens != null
            ? <> · {fmtTokens(run.tokens)} tok</>
            : <> · tokens not recorded</>}
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
 *
 * `total` — WHETHER THIS CHIP MAY PRINT THE COUNT, and it is a named case
 * rather than a boolean because the two situations are genuinely different.
 * On the CTO console the chip is the ONLY figure on screen and must carry it.
 * On the CEO's desk the served figure is already the headline on the line
 * above, and the chip printing its own made the desk render "96 awaiting your
 * decision" over "97 / 50 AWAITING YOU" — two numbers for one question, which
 * is the defect `deskAwaiting` exists to end. Everything else the chip says —
 * the trigger, the elsewhere split, the unknowns, the partial flag — is
 * information the headline does NOT carry and stays either way.
 */
export function CooTriageChip(
  { load, total = "show" }: {
    load?: DeskView["desk_load"];
    /** `already-on-screen`: the surface renders the served figure itself. */
    total?: ChipTotal;
  },
) {
  if (!load) return null;
  const over = load.coo_triage_due;
  // The predicate lives in deskAwaiting, tested: inverted here it survived a
  // mutation pass, because no runner in this repo can render this component.
  const showTotal = chipShowsTotal(total);
  // Work that is real and is somebody else's. Rendered BESIDE the CEO's figure
  // and never folded into it: the counter stopped counting chair work on
  // 2026-08-22 because it was never the CEO's, and a surface that then dropped
  // it from the screen would have solved a counting problem by hiding work.
  const elsewhere = load.open_elsewhere ?? 0;
  // An absent split is absent, not zero — a spine predating the change reports
  // no `by_actor`, and inventing a "0 unknown" for it would be a fabricated
  // reassurance.
  const unknown = load.by_actor?.unknown;
  return (
    <span
      title={load.note}
      className={`ml-2 inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] ${
        over
          ? "border-[var(--kt-warn)] text-[var(--kt-warn)]"
          : `border-[var(--kt-border)] ${KT.muted}`
      }`}
    >
      {showTotal ? (
        <>
          <span className="tabular-nums">
            {load.total}
            {!load.complete && "+"}
          </span>
          <span>/ {load.threshold} awaiting you</span>
        </>
      ) : (
        // The count is on screen already. What is NOT is the line it is being
        // measured against, so the chip keeps the threshold and drops the
        // rival figure.
        <span>triage trigger {load.threshold}</span>
      )}
      {!!unknown && (
        <span
          title="rows whose next actor could not be determined. They COUNT toward your figure — an unmeasurable is not a zero."
        >
          · {unknown} unknown
        </span>
      )}
      {elsewhere > 0 && (
        <span
          className={KT.muted}
          title={`${elsewhere} OPEN recommendation(s) are owned by the chair or another seat. Real work, not yours to decide — shown so it is not invisible. Anything you have already decided is counted separately, as "decided, awaiting execution".`}
        >
          · +{elsewhere} elsewhere
        </span>
      )}
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
        {/* THREE states, because the chip used to have two and the missing one
            told a lie: a seat whose dispatch had RETURNED rendered as "not
            running" with the title "No dispatch is open for this seat", while
            a dispatch was open and owed the chair a review. The dot does not
            breathe on the third state — a pulse says someone is working, and
            a returned dispatch means the opposite. */}
        <span
          title={
            t.awaitingReview
              ? `Returned${t.returnedRunId ? ` as ${t.returnedRunId}` : ""} — the chair has not reviewed it yet. A dispatch closes on a resolution, never on a run coming back.${t.runningTask ? `\n\n${t.runningTask}` : ""}`
              : t.runningNow && t.runningTask
                ? t.runningTask
                : "No dispatch is open for this seat."
          }
          className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] ${
            t.runningNow
              ? "border-[var(--kt-warn)] text-[var(--kt-warn)]"
              : t.awaitingReview
                ? "border-[var(--kt-border-strong)] text-[var(--kt-text)]"
                : `border-[var(--kt-border)] ${KT.muted}`
          }`}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${
            t.runningNow
              ? "kt-breathe bg-[var(--kt-warn)]"
              : t.awaitingReview
                ? "bg-[var(--kt-text)]"
                : "bg-[var(--kt-border-strong)]"}`} />
          {t.runningNow
            ? "running now"
            : t.awaitingReview
              ? "awaiting review"
              : "not running"}
        </span>

        {typeof runs === "number" ? (
          <span title={note}
                className={`inline-flex items-center gap-1 rounded-full border border-[var(--kt-border)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
            <span className="tabular-nums text-[var(--kt-text)]">{runs}</span>
            run{runs === 1 ? "" : "s"} today
          </span>
        ) : null}

        {/* THE TOKEN CHIP WAS HERE. It moved down to the quiet line (D42, the
            SPEND-DEMOTION RULE — docs/design/RUN_PAGE_2026-08-24.md amends the
            seat card's ledger zone: "the three-tile row is struck; a seat card
            carries one quiet line"). A bordered chip at the same weight as
            "running now" and "3 runs today" put the seat's spend among the
            answers to "what is this seat DOING", which is the focus-lens
            complaint in one component. */}
      </div>

      {/* THE QUIET LINE. Runs are the work and stay a chip; tokens and cost
          are a sentence underneath, at metadata scale. Absent stays absent —
          a seat with no token figure says so below rather than rendering a
          chip that is simply missing. */}
      {typeof toks === "number" && (
        <p className={`font-mono text-[10px] tabular-nums ${KT.muted}`}
           title={note}>
          {tokensLabel(t)} tok
          {t.costUsdToday != null ? ` · ${costLabel(t)}` : ""}
        </p>
      )}

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
