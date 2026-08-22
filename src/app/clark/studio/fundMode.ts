/**
 * How the fund's MODE is presented — the decisions, separated from the pixels.
 *
 * The failure this surface exists to prevent is a human reading a test number
 * as a real one. That makes every judgement in this file load-bearing, and
 * KryptonPay has no DOM test runner, so the judgements live here as pure
 * functions with tests rather than inside a component where nothing can reach
 * them.
 *
 * THE RULE THAT SHAPES ALL OF IT: absence is never a mode. A spine that has
 * not declared its mode, and a spine we cannot reach, are two different
 * unknowns and neither of them is "test" or "alpaca-paper". Both render as an
 * explicit unknown, and an unknown is treated as LOUDLY as a real-money mode —
 * because not knowing whether the numbers on screen are real is not a calmer
 * state than knowing they are.
 */

import type { FundModeName, FundModeReport } from "@/lib/fund_api";

/** How much of the surface this state is allowed to take over. */
export type ModeVolume = "quiet" | "loud" | "alarming";

export interface ModePresentation {
  /** Machine-readable, for `data-fund-mode` on the Studio root. */
  key: FundModeName | "unknown" | "unreachable" | "unrecognised";
  /** Short, upper-case, the thing scanned in half a second. */
  badge: string;
  /** One sentence: what this mode means for the numbers on screen. */
  headline: string;
  /** The consequence, in the operator's terms. */
  detail: string;
  volume: ModeVolume;
  /** True when a fill can move the CEO's actual money. */
  realMoney: boolean;
  /** True when the surface should be visibly framed, not just labelled. */
  frameSurface: boolean;
}

const UNREACHABLE: ModePresentation = {
  key: "unreachable",
  badge: "MODE UNKNOWN",
  headline: "Cannot reach the spine, so cannot say which mode this is",
  // Deliberately not reassuring. The honest reading of an unreachable spine is
  // that every number on this page is of unknown provenance.
  detail:
    "Nothing on screen can be trusted as the fund's own numbers until the " +
    "spine answers — this is not a quiet state",
  volume: "alarming",
  realMoney: false,
  frameSurface: true,
};

/**
 * The spine named a mode this build has never heard of.
 *
 * Adversary review of builder D11, 2026-08-22 — the one repair on the
 * KryptonPay half. `presentMode` was a switch over a three-member union with
 * no `default:`, so a fourth mode returned `undefined` and `ModeBar`
 * dereferenced it unguarded: a blank screen at exactly the moment the fund had
 * grown a mode the UI could not name.
 *
 * ALARMING, not quiet, and that is the same judgement the rest of this file
 * makes about every unknown. A UI newer or older than its spine, disagreeing
 * about which fund this is, is the precise state where a human reads a test
 * number as a real one — and a mode nobody recognises could be a real-money
 * one. The safe assumption and the honest assumption are the same assumption.
 */
const UNRECOGNISED = (name: string): ModePresentation => ({
  key: "unrecognised",
  badge: "MODE UNRECOGNISED",
  headline: `The spine reports a mode this app does not know: "${name}"`,
  detail:
    "This build is older or newer than the spine. It cannot say whether " +
    "these numbers are real, and a mode it cannot name could be a " +
    "real-money one — update the app before approving anything",
  volume: "alarming",
  // NOT false as a fact — false as a refusal to claim. The `realMoney: true`
  // treatment is reserved for a mode we KNOW moves money; the frame and the
  // alarming volume already give this state the loudest presentation there is.
  realMoney: false,
  frameSurface: true,
});

const UNDECLARED: ModePresentation = {
  key: "unknown",
  badge: "MODE UNDECLARED",
  headline: "The spine is running without a declared mode",
  detail:
    "It should have refused to start. Treat every number here as unverified " +
    "and check the spine's configuration before approving anything",
  volume: "alarming",
  realMoney: false,
  frameSurface: true,
};

/**
 * The presentation for a report.
 *
 * `null` means the request failed. A report whose `active` is null means the
 * spine answered and told us it has no mode — a different fact, and a worse
 * one, because the spine is supposed to refuse to start in that state.
 */
export function presentMode(report: FundModeReport | null): ModePresentation {
  if (!report) return UNREACHABLE;
  const active = report.active;
  if (!active) return UNDECLARED;

  switch (active.mode) {
    case "test":
      return {
        key: "test",
        badge: "TEST MODE",
        headline: "Not the fund — simulated fills at real prices",
        // Says what IS trustworthy as well as what is not. "Nothing here is
        // real" would be false: the prices are real, and the record is
        // persistent, and a warning that overstates gets ignored.
        detail:
          "Orders fill against a simulator; the prices are real and the " +
          `record is kept in ${active.store.pg_database}. These are not the ` +
          "fund's NAV, positions or P&L",
        volume: "loud",
        realMoney: false,
        frameSurface: true,
      };
    case "alpaca-paper":
      return {
        key: "alpaca-paper",
        badge: "ALPACA PAPER",
        headline: "The fund's live book — real broker, paper money",
        detail:
          "Orders go to the Alpaca paper account and every control runs " +
          `against this book (${active.store.pg_database})`,
        // QUIET, and that is a decision. This is the fund's normal state, and
        // a banner that shouts during normal operation is a banner nobody
        // reads on the day it matters.
        volume: "quiet",
        realMoney: false,
        frameSurface: false,
      };
    case "alpaca-prod":
      return {
        key: "alpaca-prod",
        badge: "REAL MONEY",
        headline: "Live trading with real money",
        detail:
          "Every fill moves actual capital. Nothing on this screen is a " +
          "rehearsal",
        volume: "alarming",
        realMoney: true,
        frameSurface: true,
      };
    // NOT unreachable, whatever the type says. `active.mode` arrives over the
    // wire from a spine that may be a different version, so the union is a
    // claim about this build and not about the world.
    default:
      return UNRECOGNISED(String(active.mode));
  }
}

/**
 * Can this mode be selected from the UI, and if not, why?
 *
 * Returns a REASON rather than just a boolean, because a disabled control with
 * no explanation is how a precondition list becomes invisible.
 */
export function selectability(
  report: FundModeReport | null,
  target: FundModeName,
): { selectable: boolean; reason: string; isCurrent: boolean } {
  if (!report) {
    return { selectable: false, reason: "the spine is unreachable",
             isCurrent: false };
  }
  if (report.active?.mode === target) {
    // NOT A PROBLEM, and the caller needs to know that. Found by looking at
    // the rendered dialog: every unavailable row wore the warning colour, so
    // "already in this mode" — the normal, correct state of exactly one row on
    // every reading — shouted as loudly as "locked in code, 5 of 5
    // preconditions not met". A palette where the ordinary case is amber is a
    // palette where nobody reads the amber.
    return { selectable: false, reason: "already in this mode",
             isCurrent: true };
  }
  if (target === "alpaca-prod") {
    const gate = report.prod_gate;
    if (!gate.code_lock.open) {
      return {
        selectable: false,
        isCurrent: false,
        reason:
          `locked in code (${gate.code_lock.constant} is false) and ` +
          `${gate.n_blocking} of ${gate.n_preconditions} preconditions are ` +
          "not met",
      };
    }
    if (gate.n_blocking > 0) {
      return {
        selectable: false,
        isCurrent: false,
        reason: `${gate.n_blocking} of ${gate.n_preconditions} preconditions are not met`,
      };
    }
  }
  const spec = report.modes.find((m) => m.mode === target);
  if (spec && !spec.wired) {
    return { selectable: false, reason: "this mode has never been wired",
             isCurrent: false };
  }
  return { selectable: true, reason: "", isCurrent: false };
}

/**
 * The echo the switch endpoint demands: the first 8 characters of the target
 * mode. Kept here rather than inlined so the UI and the tests agree about it,
 * and so a change to the guard breaks one place.
 */
export function confirmEcho(target: FundModeName): string {
  return target.slice(0, 8);
}

/** Wording for a precondition row. `unchecked` must never read as passing. */
export function preconditionTone(
  status: "met" | "unmet" | "unchecked",
): { symbol: string; word: string; blocking: boolean } {
  switch (status) {
    case "met":
      return { symbol: "✓", word: "met", blocking: false };
    case "unmet":
      return { symbol: "✗", word: "not met", blocking: true };
    case "unchecked":
      // The distinction the fund's own decision register got wrong: 17 of 19
      // triggers were free text nothing evaluated while the endpoint reported
      // `triggers_unchecked: []`. Unchecked BLOCKS and says why.
      return { symbol: "?", word: "unchecked — nothing evaluates this", blocking: true };
    // The same hazard as presentMode's missing default, in the same file, on a
    // status string that also arrives over the wire. An unknown status BLOCKS:
    // the one thing a precondition row must never do is read as passing
    // because this build has not heard of its status yet.
    default:
      return {
        symbol: "?",
        word: `unrecognised status "${String(status)}" — treated as blocking`,
        blocking: true,
      };
  }
}

/**
 * The two authorities disagreeing about which mode this spine is in.
 *
 * Adversary review of builder D11, finding K7. `scripts/run.sh` exports
 * FUND_MODE unconditionally and the switch endpoint writes only the mode file,
 * so any switch away from the launch script's mode arms a ModeConflict on the
 * next restart. The spine refuses at boot — correct — but the refusal lands
 * hours after the click and the UI rendered neither declaration.
 *
 * Reads the spine's own computed `declared.conflict` when it is there, and
 * falls back to comparing the two declarations itself when it is not, so a UI
 * newer than its spine still tells the truth rather than falling silent. The
 * fallback is the half this file can be sure of; the spine's version carries
 * the remedy text.
 */
export interface DeclarationConflict {
  env: string;
  file: string;
  effect: string;
  remedy: string;
}

export function declarationConflict(
  report: FundModeReport | null,
): DeclarationConflict | null {
  if (!report) return null;
  const declared = report.declared;
  if (!declared) return null;
  if (declared.conflict) return declared.conflict;
  const env = (declared.env || "").trim();
  const file = (declared.file?.mode || "").trim();
  if (!env || !file || env === file) return null;
  return {
    env,
    file,
    effect:
      "the next spine start will refuse with ModeConflict — it will not pick " +
      "a winner between two authorities",
    remedy: `start with FUND_MODE=${file}, or switch the mode back to ${env}`,
  };
}
