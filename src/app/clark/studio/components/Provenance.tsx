"use client";

import React from "react";
import { KT } from "../theme";
import { SeatFace } from "../desk/SeatFace";

/**
 * Who is suggesting this action?
 *
 * Found live by the CEO, reading Monitor's "What the strategies want" panel:
 * there was no way to tell whether an agent was recommending the trade or
 * whether deterministic code had evaluated a rule. Those two carry completely
 * different weights — one is a model's judgement, the other is arithmetic the
 * fund committed to in advance — and a surface that renders them identically
 * invites the reader to treat them identically.
 *
 * So every surface that SUGGESTS AN ACTION carries one of these chips. Three
 * kinds, and the third is the honest one:
 *
 *   deterministic — code evaluated a committed rule (a strategy signal, the
 *                   auto-approval envelope). No model was consulted.
 *   agent         — a seat's judgement, with the seat and rec id, exactly as
 *                   the desk's recommendation rows already do.
 *   unattributed  — nothing in the payload says where it came from. Stated,
 *                   not guessed: an order whose rationale carries no marker is
 *                   NOT thereby deterministic.
 *
 * Colour carries no meaning here beyond the Studio's one existing rule —
 * violet is the machine (KT.agent), everything else is neutral border and type.
 * Hierarchy comes from type and space, per theme.ts.
 */

export type ProvenanceKind = "deterministic" | "agent" | "unattributed";

export function ProvenanceChip({
  kind,
  source,
  seat,
  recId,
  title,
}: {
  kind: ProvenanceKind;
  /** For deterministic chips: what did the computing, in the reader's words —
   *  "strategy signal (no agent)", "auto-policy v1". */
  source?: string;
  seat?: string;
  recId?: number | string;
  title?: string;
}) {
  const base =
    "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] whitespace-nowrap";

  if (kind === "agent") {
    return (
      <span
        title={title ?? "A seat's judgement — an agent recommended this"}
        className={`${base} border-[var(--kt-agent-border)] bg-[var(--kt-agent-bg)] text-[var(--kt-agent)]`}
      >
        {/* The seat's face, the same drawing it has on the floor and on every
            memo — a recommendation is a colleague asking, and the chip should
            say which colleague before it says anything else. Decorative: the
            name is right beside it. */}
        <SeatFace actor={seat} size={14} decorative />
        agent — {seat ?? "unnamed seat"}
        {recId != null && <> · rec {recId}</>}
      </span>
    );
  }

  if (kind === "unattributed") {
    return (
      <span
        title={title ?? "Nothing in the payload names the source. Unattributed is not the same as deterministic."}
        className={`${base} border-[var(--kt-border)] ${KT.muted}`}
      >
        unattributed — no source recorded
      </span>
    );
  }

  return (
    <span
      title={title ?? "Computed by deterministic code from a committed rule. No model was consulted."}
      className={`${base} border-[var(--kt-border)] text-[var(--kt-text-dim)]`}
    >
      deterministic{source ? ` — ${source}` : ""}
    </span>
  );
}

/** The marker the desk stamps into an order rationale when a recommendation is
 *  staged: "[pm · rec 6]". Matching it is how an approval card can say which
 *  agent's judgement is being clicked on. */
const REC_MARKER = /\[([a-z_]+)\s*(?:·|\||-)\s*rec\s*(\d+)\]/i;

/**
 * Read an order's provenance out of its rationale, honestly.
 *
 * Returns `agent` only when the marker is actually present; returns
 * `deterministic` only when the rationale carries the exit tick's own marker
 * (`PRE-COMMITTED EXIT FIRED`, the string app/fund/autopolicy.py matches on).
 * Everything else is `unattributed` — including an empty rationale. Defaulting
 * an unknown source to "deterministic" would launder a model's suggestion into
 * arithmetic, which is the failure this chip exists to prevent.
 */
export function provenanceOfRationale(rationale?: string | null): {
  kind: ProvenanceKind;
  seat?: string;
  recId?: string;
  source?: string;
} {
  const text = rationale || "";
  const m = REC_MARKER.exec(text);
  if (m) return { kind: "agent", seat: m[1].toLowerCase(), recId: m[2] };
  if (text.includes("PRE-COMMITTED EXIT FIRED")) {
    return { kind: "deterministic", source: "pre-committed exit rule" };
  }
  return { kind: "unattributed" };
}
