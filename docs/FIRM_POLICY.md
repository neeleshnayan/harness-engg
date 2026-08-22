# The Policy — the firm's soul

**Created 2026-08-22 on the CEO's instruction: *"we need a 5 pager max
time-wide policy; those are high level guardrails and the soul of our firm.
we dont have to fill it all up today but its whats built over time and
represents our battle scar tissues."***

## What this is, and what it is not

This is not the operating manual — that is `.claude/CLAUDE.md`, and it is
long because it is detailed. This is not the origin story — that is
`FUND_GENESIS.md`, seven stages each earned by a failure. **This is the
shortest document in the firm and the highest: the laws that hold across
time, each one earned by a scar, each one a thing we now do because we once
did the opposite and it cost us.**

**Three rules keep it the soul and not a second manual:**

1. **Five pages, hard, forever.** The cap is the point. A firm accretes rules;
   a soul does not. Adding a law here means it earns its place over what is
   already here — and if nothing gives way, it did not belong. (We are well
   under the cap today. Growth is earned, not scheduled.)
2. **Every law carries its scar.** A principle with no failure behind it is
   an opinion. The scar is dated and specific, so a future chair can weigh
   whether the world that earned the law still exists.
3. **A law leaves only the way it arrived — by a dated, human decision with
   the reason written.** Nothing here is edited quietly. A law that no longer
   serves is retired with a note, never deleted.

The operating manual can contradict itself across amendments and be fixed in
the next pass. **This cannot.** When the manual and the soul disagree, the
soul wins and the manual is the bug.

---

## The Laws

### I. Absence is never zero.

An unknown is reported unknown. A number we could not read is not a number we
read as nought. A control that cannot fire is not a control that has not
fired. A queue we could not query is not an empty queue.

**The scar.** The judgement register returned `due_for_review: []` while a
7.75% drawdown sat inside it, because a trigger nothing evaluated rendered as
not-due rather than as unchecked. The spend meter recorded what it cost to
*kill* two builder diffs and zero for *building* them, because a run that
dies is never recorded — so failure cost nothing on the books. Both are the
same law broken: the gap between *no* and *don't-know* is where the money
hides.

### II. NAV folds from the event log. The broker is a comparison, never the truth.

The book is what the events say it is. Broker equity is a number we check
*against*, and when they disagree the disagreement is the finding — never a
reason to overwrite the fold.

**The scar.** A recurring regression that read live broker equity as NAV, and
a venue reconciliation that would have entered broker holdings into the book
as fact. The ledger is sovereign because it is the only thing we can replay,
audit, and re-underwrite years later. A book you cannot reconstruct is a
rumour with a balance.

### III. Quiet loosening is the one forbidden move.

A threshold moves only by a versioned change with a written reason, in either
direction — and anything that widens an envelope, raises a bar permissively,
or removes a check goes to the adversary blind before it reaches the human.
Tightening is free; loosening is watched.

**The scar.** This is the law the whole governance apparatus exists to serve,
and the week proved why it must be mechanical: a loosening-direction challenge
reached the CEO's desk ungated because the routing rule lived in prose that
nothing evaluated, and a new component nearly entered a counter that gates a
control without anyone moving the threshold. A loosening arrives wearing the
costume of a cleanup, a schema change, a convenience. The direction is the
thing you watch, not the intent.

### IV. A rule nothing evaluates is a note. A register of notes reviews nothing.

If a guardrail is written in prose and no code checks it, it is a wish. The
firm's rules are worth exactly what the machine enforces of them.

**The scar.** Seventeen of nineteen register entries carried review triggers
no code evaluated. Constitution clause 5 — the loosening gate — was enforced
by nothing until a routing defect proved it. The wire was a design in a
document while the desk had one channel for everything. Every one of these
was a real rule that did real nothing until something evaluated it.

### V. Verify against the repo or the data before acting. A 200 is not evidence.

Nothing an agent claims is acted on until it is checked against the code or
the record. A successful HTTP call proves the call succeeded, not that it did
what it meant. The chair's own summaries are subject to this law.

**The scar.** Six requests resolved against 8-character id prefixes appended
six orphan events, each returning 200. A candidate's headline was recorded as
fact before the adversary returned and killed the number. A brief asserted a
constant caused a rejection cohort it had no causal path to. Every one passed
a check that was not the check that mattered.

### VI. The human click on money is not waste, and ignition stays human.

Execution happens only inside a deterministic, versioned envelope the humans
govern. No agent proposes an order, clicks an approval, or starts another
agent. A posting fills an in-tray; a human fires the seat. This is what keeps
the firm's cost ceiling structural rather than hopeful.

**The scar.** The firm exists because an unwired kill switch and an
auto-approval that passed every check while destroying value taught it where
the human belongs — at the policy level, not the per-order level, and never
absent. The click is the most expensive thing the firm spends and it is not
the thing to optimise away. Reduce the *volume* that reaches the human; never
his *authority*.

### VII. Author ≠ reviewer ≠ approver. The adversary is blind.

The seat that makes a thing does not review it; the seat that reviews it does
not approve it. The adversary gets the artifact, never the author's reasoning,
because reconstructing the argument inherits the blind spot. This boundary
moves never.

**The scar.** Almost every real defect the firm has found came from a seat
that did not share the author's context — the blind review that killed a diff
on one line the author's own tests had blessed, the adversary that corrected
a headline three cycles of self-review had trusted. Independence is not
politeness; it is the only thing that catches what confidence hides.

### VIII. Make money as best we can. Do not get happy about killing ideas.

The gate exists so we do not repent when things crash — the kills serve the
money, never the reverse. A firm whose only output is kills is idle capital
wearing discipline's clothes. An honest negative is a win in service of
deployment, not instead of it.

**The scar.** The north star, stated by the CEO because a kill-shaped metric
had produced a kill-shaped firm — leg 1 of the team metric running hot while
generation sat near zero. The night the best-evidenced lead was honestly
retired by its own pre-registration, the first real candidate in five cycles
was filed the same hour. Both are the law: the discipline is for the money.

### IX. The whole team evolves together. The seats are the harness's test suite.

Seats are not consumers of the instruments; they are the load that surfaces
what is broken in them. Pausing the work to fix the tools removes the exact
pressure that reveals the flaws. The firm improves by running, and a lesson
one seat learns is carried to the seats it binds.

**The scar.** Nearly every instrument defect was found by a seat doing its
*own* job — the mechanism finding gate defects while hunting strategies, the
analyst finding a phantom price factor while measuring drift. When a chair
proposed pausing generation to concentrate on the harness, a single day of
evidence refuted it.

### X. Fix the cause, then re-baseline the contaminated field.

When a confirmed defect has polluted a measurement that future work will be
judged against, the remediation has two halves: stop the cause, and clean the
reference frame so the next experiment is not measured against old mistakes —
preserving the contaminated value beside the new one, by a measured magnitude,
under a human's name.

**The scar.** A phantom fill destroyed $128.26 and left its shadow on the
drawdown reference; fixing the fill without re-baselining would have judged
every future position against a peak that never happened. A fund that fixes
causes but never cleans its reference frame accumulates a soul made of its own
old errors — which is the one thing this document must never become.

---

## Not yet written

This is a scaffold, not a finished thing — by the CEO's own instruction, the
soul is built over time. Laws that are *lived* today but not yet earned into
these pages, and may graduate here when a scar makes them undeniable:

- **The two layers** — the work evolves, the control versions. Young (born
  2026-08-22); it earns its place here the first time the boundary is tested
  under pressure.
- **Look at the rendered thing** — the diff and the green suite miss what the
  eye catches. Four builder dispatches' worth of evidence; close to earning
  its line.
- **Decisions are provisional** — every decision here is falsifiable, and
  challenging one is a duty. Currently a section of the manual; it may be a
  law.

A law arrives here only when someone can point to the day it was written in
blood. Until then it lives in the manual, where it can still be wrong.
