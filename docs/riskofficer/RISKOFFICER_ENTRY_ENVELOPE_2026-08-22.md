# Riskofficer — the graduated-deployment envelope, bounding half

**Filed by the CTO chair from run `run-riskofficer-5`, 2026-08-22. Read-only.
One half of an executive-table pair with the PM (sizing half). `## WHERE I
DIFFER` on the PM is OWED next round. Chair verification at the end.**

## DIRECTION: this is a LOOSENING, routed accordingly

The current envelope (v4, `autopolicy.py:142`) auto-approves exit-rule SELLs
only — risk-reducing by construction. An entry envelope auto-approves orders
that INCREASE exposure. That is a widening of the machine's mandate however
small the notional, so per the non-negotiable and clause 5 this design
reaches the CEO **only after the adversary has seen it blind.** The
riskofficer designs the enforceable boundary; the CEO sets the appetite
inside it.

## Part 1 — the entry envelope (a NEW class, not a relaxed `side_is_sell`)

An entry is not an exit with the sign flipped — every v4 check is safe
*because* an exit reduces risk, and none of them protects an entry. Eight
checks, all fail-closed, absence-is-never-yes:

1. **`experimental_flag_present`** — gated on a non-forgeable event only the
   deployment authorization writes, not on client free text (the propose
   endpoint is CORS-only; a rationale string is forgeable).
2. **`confidence_tier_resolved`** — confidence read from a non-client source;
   **missing/unparseable → LOWEST tier or refuse, never highest.** The single
   most abusable field: it sets the size, so if absence reads as
   high-confidence the envelope inverts.
3. **`notional_within_tier_cap`** — ≤ `MAX_EXPERIMENTAL_NOTIONAL_PCT[tier]`,
   a versioned governed constant read live, per tier.
4. **`pre_committed_exit_armed`** — auto-approve an entry ONLY if a loss-stop
   exit rule already exists, strategy-owned, **predating the ENTRY EVENT** by
   a governed margin and event-linked (a rule committed minutes before entry
   is the forged-pre-commitment shape). The entry envelope requires the exit
   envelope armed against the very position it opens.
5. **`aggregate_experimental_budget`** — SUM of experimental notional ≤
   `MAX_AGGREGATE_EXPERIMENTAL_PCT`, COUNT ≤ `MAX_CONCURRENT_EXPERIMENTAL`.
   The bounded-each-is-not-bounded-together guard; `run()` has no aggregate
   budget today (F5).
6. **`concentration_within_bound`** — experimental-book `effective_bets` stays
   above a floor after the entry. Three small experiments all long
   duration/rates are one bet at 3× notional; the machinery exists and
   already broke on this shape (`judgement.py:546,583`).
7. **`venue_is_real_and_readable`** — read the EXECUTING connector's identity,
   NEVER `order["venue"]` (which routes nothing; OrderSubmitted carries the
   real venue at `pipeline.py:229`, OrderFilled copies the requested string at
   `:318`). For an experiment whose purpose is real fills, routing to paper
   silently defeats it.
8. **Inherited from v4**: `not_halted`, the three `liveness_*` heartbeats,
   `freshness ≤10 min`.

Plus a **hard per-candidate loss stop that HALTS AND REPORTS**: if a
deployed experiment's realised loss breaches its budget, the position closes
AND the entry mandate for that candidate/tier is suspended via an EVENT (not
a log line). The exit sells the position; the loss stop stops the *program*
from re-entering the losing bet. "Deploy small to learn," not "deploy and hope."

## Which live defects MUST close before any REAL graduated deployment

- **BLOCKER 1 — unguarded resume.** `fund.py:3797-3800` calls
  `_control.resume(actor=req.actor)` with no `_guard_approval` on a CORS-only
  API. `not_halted` (check 8) reads a state anyone on the network can flip.
  An entry envelope resting on it is the unwired kill switch with the wire
  visibly cut — and it lets the machine OPEN risk, not just close it.
- **BLOCKER 2 — the integrity halt has no automatic producer** (F1:
  `riskmonitor.py:967-989` builds the data-quality alarms into a list `run()`
  never reads). For an exit this fails safe; for an entry it opens a position
  on marks the fund cannot trust, with no circuit breaker.
- **BLOCKER 3 — venue routes nothing / mislabel** (check 7). Until the
  executing venue is knowable, no venue check is trustworthy and a real-fill
  experiment silently produces sim data.
- **NOT a close-first but a hard tuning limit — every fill is a simulator's.**
  ALPACA_PAPER=true; last fill avg==arrival to the last bit. This blocks
  *calibrating* the realised-loss half of the envelope, not building it.

## Part 2 — the re-tuning mechanism

Each bound becomes a registered decision in `judgement.py` (which reads the
LIVE constant, so the register cannot drift from code), with `falsified_by`
and `review_trigger`. Triggers: realised > predicted loss on a REAL
deployment → tighten; cost model becomes reliable → caps re-derived from
measured cost (can loosen → adversary first); a control fires in anger →
evidence the bound is placed right or too loose; concentration alarm on the
experimental book → add/tighten a factor cap. **Meta-calibration guard:** a
bound moves only after a minimum sample of independent REAL deployments, and
at most ONE tier-step per re-tune — a rate limit so the envelope cannot be
walked wide in a single loosening. Tighten-free / loosen-adversary is the
standing asymmetry.

## Entry 20, bounded structurally (not a verdict on the order)

Deliberately did not look up its specifics — recommendations are about the
envelope, never an order. If it reaches deployment it is bounded like any
candidate: confidence sets its tier; notional capped at the tier constant;
counts against aggregate/concurrent budgets and the concentration floor;
auto-approves only with a pre-entry event-linked loss stop; routes to a real
readable venue. **If its desired size exceeds its tier cap, the envelope
declines the excess and it waits for a CEO click.** The envelope makes the
CEO's appetite enforceable; it does not bend to the candidate.

## NUANCES AND UNKNOWNS

1. **Sim fills bound what is tunable.** TUNABLE on sim: the mechanical bounds
   (freshness, notional arithmetic, aggregate arithmetic, exit-linkage, that
   the loss stop fires). NOT TUNABLE: anything keyed on realised loss/cost —
   frozen at conservative initial values until real fills exist. A re-tune
   trigger firing on sim data is measuring the simulator and would loosen the
   envelope on fiction; gate it to real-venue fills only.
2. **Bounded-each ≠ bounded-together, and the unknown is the shared FACTOR** —
   duration, rates, issuer, vol regime. The concentration floor catches
   statistical clustering; a factor the fund does not model it cannot bound.
   Name the factors before the third experiment.
3. **A bound is only as real as its enforcing control** — the three blockers.
   None is engineerable-around; each must be wired before the bound above it
   means anything.
4. **Meta-calibration cadence has no measured answer** — zero real deployments
   exist, so it registers with `basis: judged`, not defended as measured.
5. **The two-session-lifetime case** (PM's BIND): a same-tick
   commit-then-enter is the forgery vector; the exit's SET event must predate
   the ENTRY event by a governed margin — margin UNKNOWN, flagged.

## Recommendations (for the CEO's batch, after the adversary pass)

- Adopt the 8-check entry envelope + hard loss stop as the v-next spec —
  **routed adversary-blind before the CEO, because it is a widening.**
- **Wire three controls before ANY real graduated entry**: guard
  `/fund/risk/resume`, give the integrity halt a producer, make venue knowable
  from connector identity. (hard)
- Register four governance entries (envelope version, per-tier caps,
  aggregate+concurrent budget, per-candidate loss stop).
- Gate every realised-loss/cost re-tune trigger to REAL fills only.

---

# CHAIR VERIFICATION

Re-verified live this dispatch by the seat and spot-checked by the chair:
`fund.py:3797-3800` resume is unguarded (converges with the riskofficer's own
run-4 finding and the validator's); venue singleton at `pipeline.py:58/223`,
OrderSubmitted vs OrderFilled venue at `:229`/`:318` (converges with the
adversary and validator — now **three seats line-exact on the same
mislabel**). The design is a proposal; it deploys nothing and moves no
threshold. **It correctly self-labels a LOOSENING and routes itself to the
adversary blind first** — the seat applying clause 5 to its own output is the
governance working. The executive-table engagement is incomplete: `WHERE I
DIFFER` between this and the PM's sizing half is owed and is being run now.
