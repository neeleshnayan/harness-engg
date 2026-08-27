# ADVERSARY — evening batch: the Leg B bound + the repaired merge gate

**Run**: `run-adversary-batchA-p2bound-mergegate`, 2026-08-27 evening
(blind; two artifacts per the batching rule).

**VERDICTS: KILL (Leg B's 0.50% level as specified — narrow; the two-leg
design, Leg A, and both mitigations CERTIFIED) · KILL (the merge gate's
coverage claim — narrow; the instrument itself certified as a clear net
improvement).**

**CTO VERIFICATION + DISPOSITIONS (chair, same hour)**:

- **Artifact B's live hazard was closed the hour the kill landed, both
  halves chair-applied as tightenings** (commit `1e279a38`):
  `app/fund/mode.py` entered `SENSITIVE_GLOBS` (verified: it now
  classifies sensitive), and `tests/test_prod_gate_body_pin.py` pins the
  gate function's BODY — no environment reads, refusal present, no bypass
  parameter — so the demonstrated dormant-bypass mutant now dies twice
  (path leg + body pin; 122 targeted tests green). The wider CLASS repair
  (the AST leg sees a refusal region in 1 of 138 app modules because it
  anchors on HTTPException; 32 own-exception control modules invisible) is
  the builder's next-batch ticket, census-with-repair required.
- **Artifact A: Leg B is HELD OFF THE CEO'S DESK as specified**, per the
  block-merge recommendation. The chair's re-specification, drafted to the
  adversary's own change-my-mind conditions, goes to Stan's 2026-08-28
  batch as **Leg B v2**: (1) REPORTED-ONLY — `marking_agreement` is a
  published number beside P2 and is NEVER rendered as met/unmet (the
  adversary: with that commitment "grounds A1 and A3 fall away"); (2) the
  statistic's NON-MARKING TERMS are named in the artifact — above all the
  accrued-fee liability at coefficient +1 (demonstrated breach: $9.96 =
  0.4975% of NAV on a perfectly-synced book; `FEE_CRYSTALLISED` has zero
  production emitters so the term is monotone) — with a RE-DERIVATION
  TRIGGER: any non-zero `FeeTermsSet` re-derives the level before anything
  relies on it; (3) THE FALSIFIER, recorded at decision time per clause 4:
  a healthy-book RTH reading (fees at zero, 0 symbols out of sync)
  exceeding 0.25% — half the level — reopens the derivation; so does the
  fee term alone crossing 0.25% of NAV.
- The RTH facts both sides now agree on: market-hours delta_pct runs
  0.001–0.011% (the chair's 60-sample window and the adversary's own
  independent probe agree); the overnight 110bps DBA dispersion is a
  one-night reading whose side (stale fund mark vs broker artifact) the
  adversary honestly could NOT establish — its own probe caught itself
  sharing the measured quantity's feed.

---

## A — Leg B: the kill, the survivors, the numbers

**THE KILL (executed on the shipped fold)**: `delta_pct` is named for
marking and carries `FeeLedger.outstanding()` at coefficient +1
(`nav.py:194-203` subtracts it from book NAV; `drift()` compares to broker
equity). Monkeypatching `outstanding` through the REAL
`NavService.compute()` + `Reconciler.drift()`:

| accrued $ | delta_pct | oos | verdict @0.50% |
|---|---|---|---|
| 0.00 | 0.0085 | 0 | MET |
| 5.00 | 0.2598 | 0 | MET |
| **9.90** | **0.5058** | 0 | **UNMET — false fire** |
| 20.00 | 1.0208 | 0 | UNMET |

Breach at **$9.96 accrued = 0.4975% of NAV**. In fee terms: 1%/yr
management breaches in 182 days of uncrystallised accrual; a 20%
performance fee breaches on a 2.49% gain. Fees are zero today only by the
`FeeTermsSet` whose note reads "Revisit before any outside capital" — the
exact regime P2 exists to exit. **A bound calibrated in the only regime
where its largest non-target term is zero, which is the regime it exists
to exit, is calibrated on nothing.** Second ground: no falsifier on the
level (clause 4). Third finding (disclosed now, undisclosed before): the
bound's MISS PROFILE in its own named domain — any single live position
may be mis-marked 376–658 bps (250 bps at the mandate cap) and read MET;
netting is free.

**CERTIFIED SURVIVORS (do not re-spend)**: both mitigations (PROD_UNLOCKED
independent at `mode.py:473`; Leg A constant-free — with one precision
correction: autopolicy RECOMPUTES the same belief rather than reading the
statistic); the UI names the code lock first and blocks on unknown
statuses; the headroom arithmetic reproduces exactly (0.3685/0.5887); the
two-leg separation and the anti-correlation finding; subscriptions do not
move book cash. The adversary's own first Attack-2 instrument was wrong
and self-discarded (the filed-NAV valuation-time trap, second sighting).

## B — the merge gate: the kill, the certification

**THE KILL (one mutant passes the whole gate)**: a dormant
`if os.environ.get(...): return` inside `_refuse_prod_unless_reachable`
scored ZERO on every classifier leg over a real git diff AND left the
module's 76 tests green — the only pin was on `resolve`'s SIGNATURE, the
shape of the bypass already removed. The class: `REFUSAL_EXCEPTIONS =
("HTTPException",)` gives the AST leg sight of **1 of 138** app modules;
32 control modules raise their own classes with no path cover;
`_CONST_ASSIGN` needs a numeric literal so a boolean control flip is not
even a note. **The repair swapped one vocabulary (predicate names) for
another (exception-class names).** The before-arm discipline held: two of
three planted mutants were killed by the SUITE and correctly not filed as
grounds.

**CERTIFIED (independent reproduction)**: the 38→60 region fix exact (60
regions / 61 names / 22 all-filtered); `ticketguard.py` classifies
sensitive; removed-side and weakened-condition legs fire; **12% flag rate
over 40 real commits** — not crying wolf; the helper-body and
JSONResponse evasions have zero live instances. Advisory noted: inside
fund.py the AST leg flags 26.9% of lines, so a random 10-line edit there
flags with ~96% probability — safe direction, but the whole-file-flag
shape the content pattern exists to avoid, for that one file.

**CHAIR-CLOSED SAME HOUR**: mode.py → SENSITIVE_GLOBS +
`test_prod_gate_body_pin.py` (both tightenings, commit 1e279a38). The
class repair is ticketed to the builder with the adversary's probes
(`advB/harness.py`, `p3_census.py`, `p4_replay.py`, `p6_suite.py`) as the
acceptance instruments: M2 must flag on some leg, and the census ships
with the repair.

---

*STATE appended, BINDS carried (validator ×2, cfo, builder ×2,
riskofficer) at the chair's resolve. Probes promoted to the shelf: the
miss-profile table (`miss.py` — run on EVERY threshold expressed as a % of
a portfolio total), the non-target-term sweep (`fee.py`), the merge-gate
mutant harness + false-urgency replay.*
