/**
 * The halt controls' rules, tested from the operator's side.
 *
 * Two failure classes drive every case here:
 *
 *   1. a control that is OFFERED and always refused — it teaches an operator to
 *      click through errors, which is exactly what you do not want them doing
 *      on a stopped fund;
 *   2. a control that CLAIMS more than it does. An acknowledgement moves no
 *      number and re-arms no path; if the panel lets it read like a resume, the
 *      operator believes the fund is trading when it is not.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  canAcknowledge, canRebaseDrawdown, checkNewPeak, cooldownSentence, peakLine,
  raisesEffectivePeak,
  type DrawdownView,
} from "./haltControls.ts";

const DD: DrawdownView = {
  peak_nav: 2036.35, current_nav: 1884.79, drawdown_pct: 7.4427,
  limit_pct: 10.0, peak_basis: "trailing_365d",
  unrebased_peak_nav: 2036.35, rebase: null, rebase_token: "ad699edb",
};

describe("offering the acknowledge control", () => {
  it("is offered for an open halt with a token", () => {
    assert.deepEqual(
      canAcknowledge({ halted: true, halt_ack_token: "28cc3192" }), { ok: true });
  });

  it("is NOT offered on a running fund", () => {
    // The live payload carries a halt_ack_token even when halted is false —
    // reading the token as permission would put a control on a healthy fund
    // that can only ever error.
    const a = canAcknowledge({ halted: false, halt_ack_token: "28cc3192" });
    assert.equal(a.ok, false);
    assert.equal(a.ok === false && a.kind, "not-halted");
  });

  it("calls a missing token a missing CAPABILITY, not an error", () => {
    const a = canAcknowledge({ halted: true, halt_ack_token: null });
    assert.equal(a.ok, false);
    assert.ok(a.ok === false && a.why.includes("missing capability"));
    assert.ok(a.ok === false && !a.why.toLowerCase().includes("failed"));
  });

  it("is not offered twice for the same halt", () => {
    const a = canAcknowledge({ halted: true, halt_ack_token: "t",
      halt_acknowledgement: { actor: "neelesh", at: "2026-08-21T06:00:00Z" } });
    assert.equal(a.ok, false);
    assert.equal(a.ok === false && a.kind, "already");
  });
});

describe("offering the drawdown rebase", () => {
  it("does not depend on the halt state — a phantom peak caps capacity either way", () => {
    assert.deepEqual(canRebaseDrawdown(DD), { ok: true });
  });

  it("is disabled, and says why, without a token", () => {
    const a = canRebaseDrawdown({ ...DD, rebase_token: null });
    assert.equal(a.ok, false);
    assert.ok(a.ok === false && a.why.includes("missing capability"));
  });

  it("is disabled when the drawdown block is absent entirely", () => {
    assert.equal(canRebaseDrawdown(null).ok, false);
    assert.equal(canRebaseDrawdown(undefined).ok, false);
  });
});

describe("checking a proposed new peak before submitting it", () => {
  it("accepts a figure between current NAV and the current peak", () => {
    assert.deepEqual(checkNewPeak("1950", DD), { ok: true, error: null });
  });

  it("REFUSES a figure at or above the current peak — a rebase may only lower", () => {
    // The direction is the whole safety property: raising the peak would
    // manufacture drawdown capacity out of nothing.
    for (const v of ["2036.35", "2100", "999999"]) {
      const r = checkNewPeak(v, DD);
      assert.equal(r.ok, false, `${v} was accepted`);
      assert.ok(r.error?.includes("only LOWER"));
    }
  });

  it("REFUSES a figure below current NAV, with the spine's own reason", () => {
    const r = checkNewPeak("1000", DD);
    assert.equal(r.ok, false);
    assert.ok(r.error?.includes("floored at NAV"));
    assert.ok(r.error?.includes("changed nothing"));
  });

  it("treats an empty box as not-yet-typed, never as an error", () => {
    assert.deepEqual(checkNewPeak("", DD), { ok: false, error: null });
    assert.deepEqual(checkNewPeak("   ", DD), { ok: false, error: null });
  });

  it("rejects something that is not a number rather than coercing it", () => {
    // Number("") is 0 and Number(" ") is 0 — a coercing check would happily
    // submit a peak of zero.
    const r = checkNewPeak("abc", DD);
    assert.equal(r.ok, false);
    assert.ok(r.error?.includes("not a number"));
  });

  it("checks against the UNREBASED peak, exactly as the endpoint does", () => {
    // app/api/v1/fund.py compares the new peak against
    // dd["unrebased_peak_nav"]. Matching it is the point: a client rule shaped
    // differently from the server's is a UI that promises or refuses things the
    // fund does not.
    const after: DrawdownView = { ...DD, peak_nav: 1950, unrebased_peak_nav: 2036.35 };
    assert.equal(checkNewPeak("2000", after).ok, true, "the spine accepts this");
    assert.equal(checkNewPeak("1900", after).ok, true);
    assert.equal(checkNewPeak("2036.35", after).ok, false);
  });
});

describe("warning that a second rebase would RAISE the effective reference", () => {
  // A CONFIRMED defect in the spine, measured 2026-08-21 by calling
  // riskmonitor.effective_peak directly: the endpoint checks direction against
  // unrebased_peak_nav (which never moves), while the effective peak IS the
  // rebased value. So after a rebase to 1950, a second to 2000 is accepted and
  // the reference goes UP — the opposite of what riskmonitor.py's docstring
  // says is enforced. Latent: the live fund has never been rebased.
  //
  // This surface warns and does NOT refuse. Inventing a client-side refusal for
  // a server-side bug hides the bug and diverges the two rules.
  const rebased: DrawdownView = {
    ...DD, peak_nav: 1950, unrebased_peak_nav: 2036.35,
    rebase: { at: "2026-08-21T01:00:00Z", actor: "neelesh",
              reason: "the phantom high", to_nav: 1950 },
  };

  it("warns when the typed figure exceeds the CURRENT effective peak", () => {
    const w = raisesEffectivePeak("2000", rebased);
    assert.ok(w, "no warning for a rebase that raises the reference");
    assert.ok(w!.includes("$1,950.00"));
    assert.ok(w!.includes("HIGHER"));
    assert.ok(w!.includes("read WORSE"));
  });

  it("stays silent for a genuine further lowering", () => {
    assert.equal(raisesEffectivePeak("1900", rebased), null);
    assert.equal(raisesEffectivePeak("1950", rebased), null);
  });

  it("stays silent when nothing has ever been rebased", () => {
    // The live state. There is no second-rebase hazard before a first rebase,
    // and a warning here would be noise that teaches people to ignore it.
    assert.equal(raisesEffectivePeak("1900", DD), null);
    assert.equal(raisesEffectivePeak("2000", DD), null);
  });

  it("stays silent on nonsense rather than throwing", () => {
    assert.equal(raisesEffectivePeak("", rebased), null);
    assert.equal(raisesEffectivePeak("abc", rebased), null);
    assert.equal(raisesEffectivePeak("2000", null), null);
  });

  it("is a warning, not a refusal — the value still submits", () => {
    assert.equal(checkNewPeak("2000", rebased).ok, true);
  });
});

describe("the auto-resume cool-down", () => {
  it("states the CEO-accepted basis: one strike interval from the acknowledgement", () => {
    const s = cooldownSentence(30);
    assert.ok(s.includes("30 minutes"));
    assert.ok(s.includes("from the acknowledgement"));
    assert.ok(s.includes("does not start trading"));
  });

  it("reads an absent cool-down as UNKNOWN, never as immediate", () => {
    const s = cooldownSentence(null);
    assert.ok(s.includes("UNKNOWN"));
    assert.ok(s.includes("not zero"));
    assert.ok(s.includes("not immediate"));
    assert.ok(!/\b0 minutes\b/.test(s));
  });
});

describe("the peak's provenance", () => {
  it("names the basis so the reader knows what the percentage is against", () => {
    const p = peakLine(DD);
    assert.ok(p.headline.includes("$2,036.35"));
    assert.ok(p.headline.includes("trailing 365d"));
    assert.equal(p.rebased, false);
  });

  it("shows BOTH figures once the reference has moved", () => {
    // Otherwise a rebase is a quiet edit to the number risk is measured against.
    const p = peakLine({ ...DD, peak_nav: 1950,
      rebase: { at: "2026-08-21T00:00:00Z", actor: "neelesh",
                reason: "the phantom high", from_nav: 2036.35, to_nav: 1950 } });
    assert.equal(p.rebased, true);
    assert.ok(p.headline.includes("$1,950.00"));
    assert.ok(p.headline.includes("rebased down from $2,036.35"));
  });

  it("says an unreported peak is unreported rather than printing a zero", () => {
    const p = peakLine({ ...DD, peak_nav: null, unrebased_peak_nav: null });
    assert.ok(p.headline.includes("not reported"));
    assert.ok(!p.headline.includes("$0"));
  });

  it("does not claim a rebase when peak and original agree", () => {
    const p = peakLine({ ...DD, rebase: null });
    assert.ok(!p.headline.includes("rebased"));
  });
});
