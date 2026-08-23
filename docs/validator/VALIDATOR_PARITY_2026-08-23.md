# Validator — the parity decision table, two instruments adopted, KG spot-audit (run-validator-parity), 2026-08-23

**Filed by the chair; operative summary — the full report with all tables
is verbatim in run `run-validator-parity`; harnesses at session scratchpad
`val23/` (reproduce commands inside). Method: a MODEL of the instrument
driving the SHIPPED plan generator/retention/gate leg (cross-checked
against `gate.evaluate()` on 107,725/107,725 evaluations), n=20,000
CRN-paired draws per cell.**

## THE FINDING THAT REFRAMES THE CEO'S THRESHOLD DECISION

**`min_walkforward_folds_retained_share` is read by NO code.** Declared in
four CRITERIA profiles (gate.py:273/297/314/353), stored into 26 verdicts
— the operative rule is a hardcoded strict majority at `gate.py:607` whose
implied bar is **75% at today's four folds** and equals the declared 0.50
at NO fold count. **Seven stored verdicts read "declared 0.5, measured
0.5, passed=False."** Moving the threshold value is a NO-OP unless :607
moves in the same versioned commit. (Validator CHALLENGE, tightening,
accepted by the chair: the Monday sheet item becomes TWO lines — wire or
delete the unread field; THEN the parity choice.)

## THE PARITY BEAT IS LIVE — as a HOLD-LENGTH beat

`int(d*365/252)` at walkforward.py:99 makes fold count non-monotone in
hold: **a 3-day hold plans five folds, a 4-day hold plans four — and that
one day halves both noise pass rate (12.67%→6.72%) and a real SR-1.0
edge's pass rate (37.21%→22.88%).** 14.3pp of leg-2 throughput decided by
an integer division nothing reports. Holds 4/9/14/19–23 land on the
four-fold side; ≥24 is not_testable.

## The decision table, distilled (live case m=4)

| rule | null FP | edge power | discrimination | note |
|---|---|---|---|---|
| majority (shipped) = share≥0.60 = share≥0.75 | 3.21% | 22.42% | 6.98 | **all three are the SAME RULE at m=4** (3-of-4) |
| share ≥ 0.50 | 7.99% | 41.35% | **5.18** | the only share value that moves today's case — and it LOOSENS discrimination |
| binomial p0=.5 α=0.10 | 0.29% | 4.21% | 14.50 | needs 4-of-4 at m=4 |
| binomial p0=.5 α=0.05 | 0.00% | 0.00% | — | **UNPASSABLE at m≤4** (min p = 0.0625) — rejects perfect foresight, the gate-v2 pattern |

**No share rule removes the oscillation at any value** (integer-vs-fraction
beat; 0.50 merely inverts the phase). **Only a binomial bounds the swing
by construction** — and it is unattainable at today's fold counts at
α=0.05, retroactively fails `cand-144387901688` (the fund's only
substantive pass, 3-of-4), and **p0=0.5 is not our null**: measured
per-fold null retention q = 0.3688 driftless / 0.4557 rising-market — a
declared α would be a label, the same defect as the unread field.
**Also: at m=4 the leg NEVER RUNS on 89.9% of noise draws and 52.8% of
genuine SR-1.0 draws — measurability, not retention, is the binding
criterion.** NO THRESHOLD RECOMMENDED — the table is the product; the
choice is the CEO's.

## Two instruments adopted into the battery

1. **Constant-observable control** (adv22/p1c.py): headline = the paired
   MARGINAL; always with an out-of-sample availability check for the
   constant (else hindsight); the mechanism test runs ONLY where
   treatment ≠ control.
2. **Trailing-window ladder** (24/36/48/72/96m) — WITH TWO RULES THE
   ADVERSARY'S SPEC LACKED, both measured: the ladder needs a DECLARED
   decision rule (all-rungs flips 2 of 2 census verdicts;
   majority-of-rungs flips 1 of 2 — the rule changes the answer), and it
   runs on the MARGINAL statistic (P1's headline passes 4/5 rungs while
   its marginal is dead; the zero-information control's own full-sample
   BE is 12.87, ABOVE the floor — the full sample alone certifies a rule
   with no information in it).

**Era-split census**: the record holds exactly 3 era-split verdicts; 2
eligible; both already killed on independent grounds — record clean,
finding prospective.

## KG spot-audit: all three honesty claims VERIFY, strengthened

105/105 kill sentences classify (0 mismatches; strengthened by
AST-walking gate.py's 21 emitter sites — 21/21 classify, the matcher
covers the producing surface); all three absence renderings correct; the
fence is exactly the constitution's six with **0 of 32 measured values
reachable through any of 17 public reader outputs**. Three repairs
ticketed: a genuine zero renders as nothing in the taxonomy block
("0" vs "never checked" indistinguishable — the fund's most recurrent
defect class, caught in the new instrument within a day); family_ledger's
"tested" counts recorded-not-judged; **KnowledgeGraph.__init__ issues DDL
on every construction — a read-only report run takes an ACCESS EXCLUSIVE
lock (wedged kg_outcome ~5 min with one ordinary concurrent
transaction).** Two procrustean merges named (walkforward_minority_folds
pools a v2/v4 rule change; holdout_no_trades latent).

## Generation levers found (the money side)

The single cheapest leg-2 lever this dispatch found: **hold-length
selection is worth 14pp of gate throughput and is invisible to every
seat** — no `hold_days` field anywhere the API serves. Store
hold_days + fold pair on every verdict and the beat becomes a lookup.
Measurement debts carried: 29 clean nulls for belt FPR (blocking S4's
D≥0.75 — everything here is a model, and this family has burned us at
2.9%-model vs 25%-belt before); oracle inversion under v4.2; the rf
series.

**Primary record (verbatim, all tables): run `run-validator-parity`;
STATE in `.claude/state/validator.md`.**
