# Grace - Token Ledger #1, 2026-08-22/23

**THE FINDING: the prod gate (GET /fund/mode -> prod_gate) is broken in
BOTH directions** - P1 (controls_fired) reads MET on pre-D11v2 mock-broker
fires (its evaluator has no venue/time fence while its sibling forty lines
away fences deliberately; 3 of 4 controls last fired 2026-08-20), and
THREE rows have NO evaluator and render "unchecked" forever - 0 of 82
desk requests would fix it. **Grace's law for the architecture: a false
green is strictly worse than an absent check - the dispatch queue IS the
attention allocator** (P1 reading met is why the $0-risk drill set sat
unranked). **THE DATES COLLAPSED INTO ONE**: prod_gate.reachable IS both
first-real-dollar and the $10k ask - **new date Fri 2026-08-28** (14 days
in), first real VENUE fill Mon 08-24. Grace self-falsified her own
Grace-3 claim ("P5 impossible on paper" - tca.py:131 defines informative
as venue != paper). **METER: 08-22 spent 47.1% of the firm's lifetime
tokens and was the best-value day ever** (~0% parked vs 59.7% prior;
builder findings/M 1.2 -> 4.4). Largest waste: ~163k on a defect an
incident comment had documented - **an incident comment is not a
control.** Chair latency UNMEASURABLE ("my unit is TIME and the firm has
no clock" - ticketed). Binding constraint: SPECIFICATION - the CEO's
one-word "in anger" ruling is worth ~14 days.

**Primary record: run `run-cfo-5`; STATE in `.claude/state/cfo.md`. The
G5-2 evaluability pack is with the adversary (a26debb9, loosening, her
own kill condition attached); the scoreboard pack is ticketed
(a0e640de).**
