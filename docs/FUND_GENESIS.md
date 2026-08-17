# Fund Genesis — how this fund decides it is allowed to believe something

**This file is canonical.** A rendered reading of it exists as a shareable page
(published 2026-08-18). If the two ever disagree, this file wins.

---

## The thesis

**Every serious mistake this fund has made was a false belief about itself, not a
wrong guess about markets.**

A gate was loosened and documented as a tightening. Kill switches were written,
tested, and connected to nothing. A test asserted the very bug it existed to
catch. A proposed improvement measured better and was worse where it counted. None
of these were prediction errors — a fund that never placed a trade could make all
four.

So this workflow is not about being careful. Care does not scale and does not
survive a tired evening. It is about making a false belief **expensive to hold**.
Each stage below exists because something false got all the way through without
it, and each names the incident.

---

## The loop

Run in order. Each stage carries whether the fund satisfies it **today**, because
an operating manual that cannot report its own violations is an aspiration with
numbering.

### 01 · Build with a falsification — HOLDS

A mechanism ships with the observation that would prove it wrong, not just with
tests. Tests check what you thought of; a falsification condition commits you in
advance to what would change your mind.

> Ask: what would I see if this were wrong — and would I see it?

**Earned by:** a position with no falsification condition cannot be wrong, only
unlucky. This is also what produced `NOT TESTABLE` as a verdict distinct from
failure — absence of evidence had been silently scored as evidence.

### 02 · Wire it to a clock — HOLDS

A control nobody calls is a document. Before claiming a mechanism operates: find
the caller, confirm it runs unattended, and make a *missing* tick visible as an
absence rather than as silence.

> Ask: who calls this, on what schedule, and how would I know if it stopped?

**Earned by (2026-08-18):** `RiskMonitor.run()` — the only code that trips the
−10% drawdown and −4% daily-loss halts — had **zero callers**.
`SLEEVE_500_FRAMEWORK.md` said "kill switches that will act without asking". They
would not have acted. `EXIT_RULE_TRIGGERED` was emitted by no code in the
repository, so the sleeve's primary falsification condition was guaranteed true
before any order existed. Both were found by outside review, not by the system.

Mechanism: `app/fund/heartbeat.py`, `GET /fund/liveness`.

### 03 · Calibrate from both sides — GAP

Bound the instrument from below and above. Below: does pure noise pass? Above:
does something known-good pass? An instrument that passes noise is decoration; one
that rejects perfect foresight is broken. Report the **discrimination**, never one
side alone.

> Ask: what does this say about noise, and about a real edge?

**Earned by:** gate v1 passed random strategies ~50% of the time. An oracle with
perfect foreknowledge failed v2 on our own arithmetic. Gate v4 measures at a 2.9%
false-positive rate and only 22.8% power against a genuine Sharpe-1.0 strategy —
which is why `NOT TESTABLE` is the modal outcome and must never be rendered as a
rejection.

**Open gap:** `scripts/null_audit.py` still has no walk-forward leg, so the real
belt has never produced a v4 false-positive rate. A model of an instrument is not
a run of it.

Mechanisms: `scripts/null_audit.py`, `scripts/oracle_audit.py`,
`scripts/gate_power_audit.py`, `docs/GATE_CALIBRATION_2026-08-18.md`.

### 04 · Beat the incumbent against an adversary — HOLDS

A candidate improvement does not ship on being better on the headline metric. It
must survive the specific adversary the mechanism exists to defeat — constructed
on purpose, every draw a known fake.

> Ask: what is this mechanism *for*, and is my replacement better at that?

**Earned by (2026-08-18):** a pooled out-of-sample Sharpe gave **50% more power at
identical discrimination**, and the recommendation to replace the fold-majority
rule was written. Run against a one-fold wonder — all its edge in a single window,
a lucky window wearing a track record — it was **2–3× easier to fool**, swallowing
three fakes in four at the strongest level. The extra power *was* the weakness.
The incumbent was kept.

Mechanism: `scripts/gate_power_audit.py --adversary`.

### 05 · Register the value *and* the wiring — HOLDS

Every number we chose ourselves is registered with four things: its **basis**
(measured / judged / mandate / external), what would **falsify** it, a review
**trigger**, and a backstop **date**. The register *reads* live values — never
restates them — because a second copy of a number is a second place to disagree
with the code.

It registers **wiring**, not only values: a correctly-configured unreachable
control is the same class of lie as a threshold that silently moved.

> Ask: did I choose this number, and does anything check that it still means what
> I wrote?

**Earned by (2026-08-18):** within minutes of existing, the register caught three
risk defaults **looser than the mandate in force** — drawdown 0.15 against 0.10 —
so a restore from a snapshot predating the limits event would have widened the
kill switch by half with nobody deciding to. It then flagged the v3→v4 gate change
on its own, unprompted.

Mechanisms: `app/fund/judgement.py`, `GET /fund/judgement`, digest section
`our_own_knobs`.

### 06 · Get reviewed by someone blind to your reasoning — HOLDS

Two standing consultant lenses — one macro / diversification / drawdown, one
microstructure / execution / capacity — review independently, without seeing the
builder's reasoning. Then **every claim is verified in the repo before it is acted
on**, including the flattering ones.

> Ask: who checked this who could not see how I got here?

**Earned by (2026-08-18):** both lenses independently found the unwired controls.
Our own suite had stayed green straight through the gate regression, because two
tests had been written to *assert* the loosening — a test can only catch what it
was not written to bless.

These are analytical lenses derived from publicly known investment philosophies.
They are never presented as the views of the real individuals.

### 07 · Change it in the open — GAP

A threshold moves only by a versioned change with a written reason, **in either
direction**. Tightenings attract scrutiny naturally. Loosenings pass as
housekeeping, and quiet loosening is the single forbidden move. Every prior
version is kept **complete**, so an old verdict can be re-read against the bar it
actually cleared — partial copies silently inherit current defaults.

> Ask: is this a loosening, and does the written reason say so?

**Earned by (2026-08-18):** gate v3 dropped the fold requirement to 2 and left the
retained share compared with `<`, so 1-of-2 folds passed as a "majority". Its
discrimination was **1.21** — barely distinguishable from a coin — and it shipped
with a commit message about rigour.

**Open gap:** `docs/SLEEVE_500_FRAMEWORK.md` §3, §4 and §6a still carry claims now
known false. They are to be struck through with the date rather than quietly
edited, so the record shows what we believed and when.

---

## The absence doctrine

One rule under all seven, and the source of most of the bugs above: **missing
information has to look missing.** Every collapse in this table was found in live
code.

| This | is never | Because |
|---|---|---|
| No trades | 0% retention | A test leg that never traded says nothing either way — usually warm-up starvation |
| Unmeasurable | Failed | `NOT TESTABLE` means the fund cannot examine this yet; the answer is more history, not a lower bar |
| Unreadable | Unchanged | A register falling back to a remembered value asserts knowledge it does not have |
| Silence | Calm | No alarm is evidence of calm only if something was looking |
| Not yet observed | Fine *or* broken | Another process may hold the lease; both other answers are claims the process cannot support |
| Never measured | Robust | Two gate criteria once passed by never having been tested against |
| Unreviewed | Dismissed | 376 observations carried one review, made by the person testing the review button |
| Limit not breached | Limit works | A control that has never fired is a control nobody has verified |

---

## Who decides what

| Role | Owns |
|---|---|
| **Operator** | Risk appetite, security selection, every approval click. Mandate numbers are registered to be *watched*, never tuned. |
| **Builder** | Everything upstream of the click: mechanisms, calibration, thresholds, and the written reason for each. |
| **Two lenses** | Independent adversarial critique, blind to the builder's reasoning. Advisory, and every claim verified before action. |

### Two invariants, not preferences

1. **The machine proposes; the human clicks.** No automated path executes. The
   moment an agent path completes a trade, every claim this system makes about
   itself stops being true.
2. **The builder does not select securities.** Analysis of measured properties —
   shortlists, correlations, sizing arithmetic — yes. The instrument choice and
   the click stay with the operator.

---

## What counts as a good week

- **Truthful verdicts per week.** A gate pass is an outcome, never a target.
- **An honest negative result is a win.** Three deployed strategies failing their
  own gate is the harness working.
- **A rejected improvement is a win.** Stage 04 killed a change that measured
  better on the headline metric.
- **A false belief found is worth more than a feature shipped.** Everything on
  this page came from four of them.

---

## Using this on a new piece of work

Short form, for the top of a working session:

1. What would prove this wrong, and would I see it?
2. Who calls it, and how do I know if it stopped?
3. What does it say about noise, and about a real edge?
4. Is my replacement better at the thing the mechanism is *for*?
5. Which numbers here did I choose, and what falsifies them?
6. Who can check this without seeing my reasoning?
7. Is this a loosening, and does the reason say so?
