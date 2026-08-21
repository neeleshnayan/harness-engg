/**
 * When each halt control may be offered, and what it is allowed to claim.
 *
 * The controls themselves are three POSTs. Everything difficult about them is
 * decided here, apart from the pixels, because every one of these decisions is
 * a way to mislead an operator about the state of a stopped fund:
 *
 *   * a control that is present and always errors teaches an operator to click
 *     through errors. So availability is decided, not attempted;
 *   * an acknowledgement is NOT a resume. It moves no number and re-arms no
 *     path, and the copy has to say so or the button reads like a reopen;
 *   * a drawdown rebase may only ever LOWER the peak, and never below current
 *     NAV. Both bounds are the spine's to enforce and this checks them anyway,
 *     because a control that lets you type a refusal and then submits it is a
 *     control that trains people to ignore refusals;
 *   * a missing token is a MISSING CAPABILITY, not an error. A spine that
 *     predates the token cannot prove which state a click acts on, so the
 *     control is disabled with that said — the same distinction the rest of this
 *     Studio draws between "absent" and "zero".
 *
 * Shapes verified against the live payload of GET /fund/risk/monitor on
 * 2026-08-21, not assumed: `halt_ack_token` and `drawdown.rebase_token` are
 * present and non-null even when `halted` is false, `halt_acknowledgement` and
 * `halt_alarm` are null while nothing is halted, and
 * `autoresume_cooldown_minutes` is 30.0.
 */

export interface HaltAcknowledgement {
  actor?: string | null;
  at?: string | null;
  note?: string | null;
  /** The halt this acknowledgement was recorded against. */
  halt_at?: string | null;
}

export interface DrawdownView {
  peak_nav?: number | null;
  current_nav?: number | null;
  drawdown_pct?: number | null;
  limit_pct?: number | null;
  peak_basis?: string | null;
  peak_note?: string | null;
  unrebased_peak_nav?: number | null;
  rebase?: { at?: string | null; actor?: string | null; reason?: string | null;
             from_nav?: number | null; to_nav?: number | null } | null;
  rebase_token?: string | null;
}

export type Availability =
  | { ok: true }
  | { ok: false; why: string; kind: "not-halted" | "no-token" | "already" };

/**
 * Whether the ACKNOWLEDGE control should be offered.
 *
 * Any class may be acknowledged — seeing an integrity halt is worth recording —
 * but there must be a halt to see. Offering it on a running fund would let
 * someone acknowledge a darkness that is not there, and the spine would refuse,
 * which is the "always errors" pattern.
 */
export function canAcknowledge(m: {
  halted?: boolean | null;
  halt_ack_token?: string | null;
  halt_acknowledgement?: HaltAcknowledgement | null;
}): Availability {
  if (!m.halted) {
    return { ok: false, kind: "not-halted",
      why: "nothing is halted, so there is no darkness to acknowledge" };
  }
  if (!m.halt_ack_token) {
    return { ok: false, kind: "no-token",
      why: "this spine returned no halt_ack_token, so a click could not prove "
        + "which halt it acts on. A missing capability, not an error" };
  }
  if (m.halt_acknowledgement) {
    return { ok: false, kind: "already",
      why: "this halt has already been acknowledged — the record is below" };
  }
  return { ok: true };
}

/** Whether the DRAWDOWN REBASE control should be offered.
 *
 *  Independent of the halt state: the peak caps risk capacity whether or not
 *  the fund is stopped, and a phantom high is worth correcting on a running
 *  fund. Only the token gates it. */
export function canRebaseDrawdown(d: DrawdownView | null | undefined): Availability {
  if (!d?.rebase_token) {
    return { ok: false, kind: "no-token",
      why: "this spine returned no drawdown rebase token, so a click could not "
        + "prove which peak it replaces. A missing capability, not an error" };
  }
  return { ok: true };
}

export interface RebaseCheck { ok: boolean; error: string | null }

/**
 * Whether a proposed new peak is one the spine will accept.
 *
 * Both bounds are the SPINE's rules, restated here so the operator learns why
 * before submitting rather than after. Deliberately does NOT relax either: a
 * client-side check looser than the server's is how a UI starts promising
 * things the fund refuses.
 *
 *   * strictly BELOW the current peak — a rebase may only lower;
 *   * at or ABOVE current NAV — the effective peak is floored at NAV, so a
 *     lower figure would be recorded having changed nothing.
 */
export function checkNewPeak(raw: string, d: DrawdownView | null | undefined): RebaseCheck {
  const s = raw.trim();
  if (!s) return { ok: false, error: null };   // not yet typed: no error, no submit
  const n = Number(s);
  if (!Number.isFinite(n)) {
    return { ok: false, error: `“${s}” is not a number` };
  }
  const nav = d?.current_nav;
  // The UNREBASED peak, matching `app/api/v1/fund.py`'s
  // `dd.get("unrebased_peak_nav", dd.get("peak_nav"))` exactly. A client check
  // shaped differently from the server's — looser OR stricter — is a UI that
  // starts promising or refusing things the fund does not. Where the two rules
  // diverge in EFFECT, that is said as an advisory (see `raisesEffectivePeak`),
  // never as a refusal this side invented.
  const peak = d?.unrebased_peak_nav ?? d?.peak_nav;
  if (peak != null && n >= peak) {
    return { ok: false,
      error: `a rebase may only LOWER the reference — ${fmtUsd(n)} is not below `
        + `the current peak of ${fmtUsd(peak)}` };
  }
  if (nav != null && n < nav) {
    return { ok: false,
      error: `${fmtUsd(n)} is below current NAV of ${fmtUsd(nav)}. The effective `
        + `peak is floored at NAV, so this would be recorded having changed `
        + `nothing — the spine refuses it` };
  }
  return { ok: true, error: null };
}

/**
 * Would this rebase RAISE the reference the drawdown is actually measured from?
 *
 * MEASURED against the spine's own code on 2026-08-21, not inferred. The
 * endpoint checks direction against `unrebased_peak_nav`, which does not move
 * when a rebase is applied, while `effective_peak()` returns the rebased value.
 * So after a rebase to $1,950 a SECOND rebase to $2,000 passes the check
 * (2000 < 2036.35) and the effective peak goes 1950 -> 2000 — the opposite of
 * the direction `riskmonitor.py`'s own docstring says is enforced. Verified by
 * calling `effective_peak` directly; latent, since the live fund has never been
 * rebased (`peak_note`: "the drawdown reference has never been rebased").
 *
 * ADVISORY ONLY. This surface does not get to invent a refusal the spine does
 * not make — the fix belongs in the risk engine, by a human, versioned. What it
 * can honestly do is tell the operator what the click will actually do.
 */
export function raisesEffectivePeak(raw: string, d: DrawdownView | null | undefined
                                    ): string | null {
  const n = Number((raw || "").trim());
  if (!Number.isFinite(n) || !d?.rebase) return null;
  const effective = d.peak_nav;
  if (effective == null || n <= effective) return null;
  return `Careful: the reference is already rebased to ${fmtUsd(effective)}, and `
    + `${fmtUsd(n)} is HIGHER. The spine checks direction against the original `
    + `peak, so it will accept this — and the drawdown will then be measured `
    + `from a larger number, i.e. it will read WORSE. A rebase is meant only to `
    + `lower the reference.`;
}

function fmtUsd(n: number): string {
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2,
                                           maximumFractionDigits: 2 })}`;
}

/**
 * What the auto-resume cool-down means, in words, for a value that may be absent.
 *
 * Absent is not zero and it is emphatically not "resumes immediately": a spine
 * that does not report the cool-down is one whose auto-resume behaviour this
 * panel cannot describe.
 */
export function cooldownSentence(minutes: number | null | undefined): string {
  if (minutes == null) {
    return "This spine does not report an auto-resume cool-down, so how long a "
      + "loss halt must stay shut after acknowledgement is UNKNOWN here — not "
      + "zero, and not immediate.";
  }
  return `A loss halt stays shut for at least ${minutes} minutes after it is `
    + `acknowledged — one strike interval, measured from the acknowledgement, so `
    + `the fund observes at least one fresh mark before any path reopens. `
    + `Acknowledging does not start trading; it satisfies one of four conditions.`;
}

/**
 * The peak's provenance, said plainly.
 *
 * `peak_basis` and `peak_note` come from the spine. When the peak has been
 * rebased the ORIGINAL is still reported (`unrebased_peak_nav`), and showing
 * both is the point — a reader must be able to see that the reference moved and
 * by how much, or the rebase is a quiet edit to the number risk is measured
 * against.
 */
export function peakLine(d: DrawdownView | null | undefined): {
  headline: string; rebased: boolean; original: number | null;
} {
  if (!d) return { headline: "The drawdown reference is unreadable.",
                   rebased: false, original: null };
  const peak = d.peak_nav;
  const orig = d.unrebased_peak_nav ?? null;
  const rebased = !!d.rebase;
  const head = peak == null
    ? "The drawdown peak is not reported — the drawdown percentage above cannot "
      + "be checked against it."
    : `Measured from a peak of ${fmtUsd(peak)}`
      + (d.peak_basis ? ` (${d.peak_basis.replace(/_/g, " ")})` : "")
      + (rebased && orig != null && orig !== peak
        ? `, rebased down from ${fmtUsd(orig)}`
        : "");
  return { headline: head, rebased, original: orig };
}
