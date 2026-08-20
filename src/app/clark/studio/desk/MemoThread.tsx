"use client";

import React, { useState } from "react";
import Link from "next/link";
import { KT } from "../theme";
import { memoSubject } from "../memo";
import { SeatFace } from "./SeatFace";
import { TraceNode, TraceThread, fmtAt, isSeat, verdictStamp } from "./seatLib";

/**
 * A trace, rendered as a MEMO THREAD.
 *
 * This replaces TraceFlow, and it is a RE-SKIN, not a re-derivation: the input
 * is the same `seatLib.traceThreads` output the audit view and the wire already
 * use, node for node. That constraint is the point — an audit picture that is a
 * different picture from the working view gets read once, and the two then
 * disagree without anyone noticing. Everything below is layout.
 *
 * Why memos: the CEO's ask was for the chatter to read like an office, "a clean
 * well designed memo" rather than a flow chart. So each hop is a letterhead
 * card — FROM a face TO a face, a date, a one-line subject — and the hops hang
 * off one quiet vertical thread, which is the trace id made visible.
 *
 * The two honesty rules the skin keeps:
 *
 *   - The addressee is READ, never invented. A delivery is addressed to whoever
 *     dispatched it, taken from the dispatch node in this same thread; when the
 *     thread has no dispatch node the card says the recipient is not recorded
 *     rather than naming the office.
 *   - A verdict is stamped only when it is genuinely one word (see
 *     `verdictStamp`). Sentence verdicts print verbatim under the subject —
 *     a stamp reading "KILL" over a verdict that said "fix incomplete" would be
 *     a cleaner finding than the seat delivered.
 */

const KIND_LABEL: Record<TraceNode["kind"], string> = {
  request: "ask",
  dispatch: "dispatch",
  run: "delivery",
  decision: "decision",
};

/** Who the memo is from and to, per hop. Presentation only — every value here
 *  comes off a node already in the thread. */
function addressees(n: TraceNode, thread: TraceThread): { from: string | null; to: string | null } {
  switch (n.kind) {
    case "request":
    case "dispatch":
      // The actor asked/dispatched; the seat is the addressee.
      return { from: n.actor, to: n.seat ?? null };
    case "run": {
      // Addressed back to whoever dispatched it. Not recorded on the run
      // itself, so it is read from this thread's dispatch hop — and left null
      // when there is none, rather than addressed to "the office".
      const dispatch = thread.nodes.find((x) => x.kind === "dispatch");
      const ask = thread.nodes.find((x) => x.kind === "request");
      return { from: n.seat ?? null, to: dispatch?.actor ?? ask?.actor ?? null };
    }
    case "decision":
      // The human decided; the seat that made the recommendation is told.
      return { from: n.actor, to: n.seat ?? null };
  }
}

function Party({ who, label }: { who: string | null; label: string }) {
  const body = (
    <span className="inline-flex items-center gap-1.5">
      <SeatFace actor={who} size={18} decorative />
      <span className="font-mono text-[11px]">{who ?? "not recorded"}</span>
    </span>
  );
  return (
    <span className="inline-flex items-baseline gap-1.5">
      <span className={`font-mono text-[9px] uppercase tracking-[0.14em] ${KT.muted}`}>
        {label}
      </span>
      {who && isSeat(who) ? (
        <Link href={`/clark/studio/desk/${who}`} className="hover:underline">{body}</Link>
      ) : (
        <span title={who ? undefined : "No actor was recorded for this hop."}>{body}</span>
      )}
    </span>
  );
}

/**
 * A verdict as a physical stamp — deliberately the least restrained thing on
 * the page. A kill is a WIN at this firm, and a day of killing that reads as a
 * day of nothing pushes the firm toward shipping instead of falsifying.
 */
export function VerdictStamp({ verdict, tone = "kill" }: {
  verdict: string;
  tone?: "kill" | "neutral";
}) {
  const colour = tone === "kill"
    ? "border-[var(--kt-down)] text-[var(--kt-down)]"
    : "border-[var(--kt-border-strong)] text-[var(--kt-text-dim)]";
  return (
    <span
      className={`inline-block -rotate-[5deg] rounded-[3px] border-2 px-2 py-[1px] font-mono text-[10px] font-semibold uppercase tracking-[0.22em] opacity-90 ${colour}`}
    >
      {verdict}
    </span>
  );
}

function Stamp({ n }: { n: TraceNode }) {
  const stamp = verdictStamp(n.verdict);
  if (stamp) return <VerdictStamp verdict={stamp} tone={stamp === "KILL" ? "kill" : "neutral"} />;
  if (n.status === "rejected") return <VerdictStamp verdict="rejected" tone="kill" />;
  if (n.status) return <VerdictStamp verdict={n.status} tone="neutral" />;
  return null;
}

/* ------------------------------------------------------------ the thread -- */

/** How many memos a thread shows before it folds its middle away. Chosen from
 *  the live log: the longest thread today is 17 hops (the pm's first review and
 *  every decision that followed), and a 17-card wall is a scroll, not a file. */
const SHOW_HEAD = 1;
const SHOW_TAIL = 5;

export function MemoThread({ t, dense = false }: { t: TraceThread; dense?: boolean }) {
  const [full, setFull] = useState(false);
  const n = t.nodes.length;
  const folds = !full && n > SHOW_HEAD + SHOW_TAIL + 1;
  // The ask and the outcome are what a file is read for; the middle is folded,
  // never dropped — the count of what is hidden is on the control itself, so
  // the reader can see that something is being withheld.
  const shown = folds
    ? [...t.nodes.slice(0, SHOW_HEAD), ...t.nodes.slice(n - SHOW_TAIL)]
    : t.nodes;
  const hidden = n - shown.length;

  return (
    <div className={`${KT.card} p-4`}>
      {/* the file cover */}
      <div className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-[var(--kt-border)] pb-2">
        <span className={`font-mono text-[10px] uppercase tracking-[0.14em] ${KT.muted}`}>
          thread {t.traceId.slice(0, 8)}
        </span>
        {t.synthetic && (
          <span
            className="font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--kt-warn)]"
            title="No trace_id was recorded on this item; it is shown as its own thread rather than merged into someone else's."
          >
            untraced
          </span>
        )}
        <span className={`font-mono text-[10px] ${KT.muted}`}>
          {n} memo{n === 1 ? "" : "s"}
        </span>
        <span className={`ml-auto font-mono text-[10px] tabular-nums ${KT.muted}`}>
          {fmtAt(t.first)} → {fmtAt(t.last)}
        </span>
      </div>

      {/* the thread line: one continuous rule down the left, memos hanging off it */}
      <ol className="relative ml-2 border-l border-[var(--kt-border)] pl-4">
        {shown.map((node, i) => (
          <React.Fragment key={`${node.kind}-${node.at}-${i}`}>
            <MemoCard n={node} thread={t} dense={dense} last={i === shown.length - 1} />
            {folds && i === SHOW_HEAD - 1 && (
              <li className="mb-2">
                <button
                  type="button"
                  onClick={() => setFull(true)}
                  className={`text-[11px] ${KT.muted} underline-offset-2 hover:text-[var(--kt-text)] hover:underline`}
                >
                  {hidden} memo{hidden === 1 ? "" : "s"} folded away — open the file
                </button>
              </li>
            )}
          </React.Fragment>
        ))}
      </ol>
      {full && n > SHOW_HEAD + SHOW_TAIL + 1 && (
        <button
          type="button"
          onClick={() => setFull(false)}
          className={`mt-2 text-[11px] ${KT.muted} underline-offset-2 hover:text-[var(--kt-text)] hover:underline`}
        >
          close the file
        </button>
      )}
    </div>
  );
}

function MemoCard({ n, thread, dense, last }: {
  n: TraceNode; thread: TraceThread; dense: boolean; last: boolean;
}) {
  const { from, to } = addressees(n, thread);
  const subject = memoSubject(n.label, dense ? 96 : 160);
  const stampable = verdictStamp(n.verdict);
  return (
    <li className={last ? "" : "mb-2"}>
      {/* the tie to the thread line */}
      <span
        aria-hidden
        className="absolute -ml-[21px] mt-[13px] block h-[5px] w-[5px] rounded-full bg-[var(--kt-border-strong)]"
      />
      <article className={`${KT.inset} px-3 py-2.5`}>
        <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <Party who={from} label="from" />
          <Party who={to} label="to" />
          <span className={`ml-auto font-mono text-[9px] uppercase tracking-[0.14em] ${KT.muted}`}>
            {KIND_LABEL[n.kind]}
          </span>
          <span className={`font-mono text-[10px] tabular-nums ${KT.muted}`}>
            {fmtAt(n.at)}
          </span>
        </header>
        <p className={`mt-2 leading-snug ${dense ? "text-[12px]" : "text-[13px]"}`}>
          {subject || <span className={KT.muted}>no subject recorded</span>}
        </p>
        {(stampable || n.status) && (
          <div className="mt-2">
            <Stamp n={n} />
          </div>
        )}
        {/* A verdict too long to stamp prints verbatim — the seat's words, not
            a summary of them. */}
        {n.verdict && !stampable && (
          <p className={`mt-2 text-[11px] leading-relaxed ${KT.body}`}>
            <span className={`${KT.label} mr-1.5`}>verdict</span>
            {n.verdict}
          </p>
        )}
      </article>
    </li>
  );
}
