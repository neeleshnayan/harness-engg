/**
 * THE PATTERN-DAY-TRADER RULE — one reading, for every surface that shows it.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHY THIS FILE EXISTS. The PDT rule was RETIRED on 2026-08-27 (the rule itself
 * ended 2026-06-04; `GET /fund/compliance` now returns `pdt.retired: true`,
 * `applies: false`, and a `retired_note`). Three Studio surfaces rendered it —
 * `SystemStatus`, `MonitorVerdict`, `ClarkConsole` — each with its own copy of
 * the branch, and the three did NOT behave the same way when the rule went
 * away:
 *
 *   · `MonitorVerdict` fell silent. Correct by luck: its branch was
 *     `if (applies)`, and a retired rule simply stopped rendering.
 *   · `ClarkConsole` fell silent on the FACTS and kept a standing prompt
 *     offering the CEO *"What can I still do today without burning a day
 *     trade?"* — a question about a rule that no longer exists.
 *   · `SystemStatus` was ACTIVELY WRONG. Its `else` branch printed
 *     *"Day-trade budget · above $25k — the rule does not restrict this
 *     account"*. The account holds **$2,008.99**. The rule did not restrict it
 *     because the rule was retired, not because the fund is rich, and a
 *     status panel stating a false reason for a green row is worse than one
 *     saying nothing: it teaches the reader a fact about the account that is
 *     not true.
 *
 * THAT LAST ONE IS THE DEFECT CLASS THIS FIRM KEEPS MEASURING — a fix applied
 * to one member of a family and not its siblings. So the reading is computed
 * ONCE, here, and the three surfaces render what they are handed.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * THE ABSENCE RULE THAT MATTERS HERE: a retired rule and an unreadable one are
 * OPPOSITE facts. "The rule does not restrict this account" is a claim; "we
 * could not ask the broker" is not. `state` keeps four cases apart and never
 * collapses two of them into a green row.
 *
 * AND THE REASON IS NEVER INVENTED. When the payload says the rule does not
 * apply and does NOT say it is retired, this reports the exemption WITHOUT a
 * cause unless the equity actually clears the threshold — because that is the
 * exact sentence that shipped false.
 */

import type { ComplianceStatus } from "@/lib/fund_api";

export type PdtState = "unreadable" | "retired" | "exempt" | "applies";

export interface PdtRead {
  state: PdtState;
  /** The severity a status row should carry. */
  level: "ok" | "warn" | "bad" | "unknown";
  /** The one line a status row shows. Never empty. */
  detail: string;
  /**
   * Is this a LIVE CONSTRAINT — something that can stop a trade today?
   *
   * The whole point of the field: a surface asks this instead of asking
   * `applies`, so a retired rule can never be rendered as a cliff, and a rule
   * that comes BACK does not need three surfaces edited again.
   */
  live: boolean;
  /** Day trades left. `null` whenever the number is not a live constraint. */
  remaining: number | null;
}

/** The row label, in one place, so three surfaces cannot drift on it. */
export const PDT_LABEL = "Day-trade budget";

export function readPdt(compliance: ComplianceStatus | null | undefined): PdtRead {
  const pdt = compliance?.pdt;
  if (!compliance || !pdt) {
    return {
      state: "unreadable",
      level: "unknown",
      detail: "day-trade budget unreadable — UNKNOWN, not unrestricted",
      live: false,
      remaining: null,
    };
  }

  // RETIRED IS CHECKED FIRST AND ON ITS OWN FIELD. A retired rule also reports
  // `applies: false`, so an `applies`-first reading would classify it as an
  // exemption and then have to guess at a cause — which is precisely how the
  // false "$25k" sentence got onto the status panel.
  if (pdt.retired === true) {
    return {
      state: "retired",
      level: "ok",
      detail:
        pdt.retired_note ??
        "retired — the pattern-day-trader rule ended 2026-06-04; the counts on " +
          "this record are history, not a constraint",
      live: false,
      remaining: null,
    };
  }

  if (!pdt.applies) {
    const equity = compliance.account?.equity;
    const threshold = pdt.equity_threshold;
    // ONLY SAY "ABOVE $25k" IF THE ACCOUNT IS ABOVE $25k. Read from the
    // payload's own two numbers, both of which may be absent; an unreadable
    // equity gives an exemption with NO cause rather than the flattering one.
    const clears =
      equity != null && threshold != null && Number.isFinite(equity) && equity >= threshold;
    return {
      state: "exempt",
      level: "ok",
      detail: clears
        ? `above $${Math.round(threshold).toLocaleString()} — the rule does not restrict this account`
        : "the rule does not apply, and the payload does not say why",
      live: false,
      remaining: null,
    };
  }

  const left = pdt.remaining;
  return {
    state: "applies",
    // An UNREADABLE remaining count is not a comfortable zero and not a
    // comfortable four: it is unknown, and a cliff whose distance is unknown
    // is a warning.
    level: left == null ? "warn" : left <= 0 ? "bad" : left === 1 ? "warn" : "ok",
    detail:
      `${pdt.used}/${pdt.max_day_trades} used · ` +
      `${left == null ? "remaining UNKNOWN" : `${left} left`} before a 90-day` +
      ` restriction · via ${pdt.source}${pdt.diverges ? " (counts disagree)" : ""}`,
    live: true,
    remaining: left,
  };
}
