# riskofficer — working state
(appended by the CTO at each dispatch resolution; newest at the bottom)

## 2026-08-20 — seeded at hiring, same decision as the policy it supervises
- Policy v1 live: exit-rule SELLs only, <=10min fresh, liveness-proven, not
  halted. Zero auto-approvals on the log yet.
- First audit due: after the first auto-approval event, or in 7 days, whichever
  first. Check the marker-forgery path early (can anything but the exit tick
  put EXIT_MARKER in a rationale? propose_order accepts arbitrary rationale
  from callers with the propose permission - the marker alone is NOT proof of
  provenance; the actor field must corroborate. Flag this to the CTO as
  envelope v1's weakest check).

## 2026-08-20 — first audit executed (dispatch 1b9183da, trace-incident-gld-phantom)

AUDIT POPULATION: whole log, 295 events. OrderApproved: rushi x16, auto-policy-v1 x1.
Exactly ONE auto-approval in fund history: seq 256, event_id
a6ca5495-409b-4c6a-b97a-ddbbb6080fb0, 08:01:27.013836Z, order 2ec1ec3f-ddda-48ac-8511-9c19fb87d59b.

VERDICT ON seq 256: policy_evaluation present and complete (7 checks); code version
v1 == event version v1, no drift. ALL SEVEN CHECKS WERE FACTUALLY TRUE. The marker was
genuine (seq 255 ExitRuleTriggered, same order_id, actor worker). The policy did not
malfunction. v1 verifies everything about the ORDER and nothing about the NUMBER.

FINDINGS (ranked by money):
F1 CRITICAL, STILL LIVE: fa6b877 removed _DEFAULT_PRICE but kept _SEED_PRICES
   (paper.py:35-42, returned at :85-87). PROVEN to 4dp that SPY and NVDA were served
   fabricated marks in the SAME incident: seq 250 SPY 28.0742% underwater / basis 778.58
   -> implied 559.9999 == seed 560.0; seq 253 NVDA 47.1505% / basis 227.06 -> 120.0001
   == seed 120.0; seq 252 GLD 75.1355% / basis 402.18 -> 100.0000 == old default.
   GLD is now safe (unpriceable->unevaluable); SPY/NVDA/MSFT/AAPL ARE NOT. SPY and NVDA
   are live positions. The phantom-exit path re-opens the moment any loss_pct rule is
   committed on them - which is a thing the PM seat routinely recommends. RE-CHECK THIS
   FIRST NEXT DISPATCH.
F2 HIGH: v1's stated premise ("committed BEFORE the position existed", autopolicy.py:34-36)
   was FALSE for seq 256. GLD position filled 2026-08-14 (seq 76, basis 402.18, strategy
   e54f40af-b938-4355-a693-80b8f98db0bc); rule set 2026-08-17 (seq 167, machinery-test,
   note "far away"). The sentence is unverified hardcoded boilerplate at exitrule.py:307-311.
F2b: exit rules match positions by SYMBOL ONLY (exitrule.py:221, 269-270, 287); rule
   strategy_id never compared to position strategy_id. A machinery-test rule liquidated
   another strategy's position.
F3 HIGH (my standing v1 concern, now DEMONSTRATED): rationale + actor are free-text client
   fields (app/schemas/fund.py:12,16) on an UNAUTHENTICATED endpoint (fund.py:911-940; no
   Depends, no auth middleware, main.py:337-344,379 is CORS only). Ran evaluate() on two
   forged orders (no exit rule, qty 999, marker buried mid-sentence): BOTH approve=True.
   Bounded by risk.py:132-151 to ~15% NAV/order and ~20% NAV/name of short (~$375 today).
   actor is NOT a defence (forgeable). The non-forgeable token is the EXIT_RULE_TRIGGERED
   event: only exitrule.py:323-331 writes it, no endpoint appends it.
F4 MEDIUM: halt latency measured 14m41s (fill seq 258 08:01:27.147 -> TradingHalted seq 265
   08:16:08.932). Incident doc lines 16 and 45 say "~08:01"/"within seconds" - WRONG vs log.
   Structurally the halt can never gate the first bad fill. approve_order re-checks only
   staleness (pipeline.py:165-185). Seq 281 resume -> seq 282 re-halt 8.6s later.
   NOT established: why 14m41s across ~29 ticks. Open measurement.
F5 MEDIUM: freshness = proposal age (orders.py:137,156-166, server-derived, unspoofable),
   NOT mark age or mark validity.
F6 LOW: doc's -$133.21 is NAV-destroyed-vs-true-mark (0.424471 x (413.84-100.00)), not
   "realized ledger loss" (-$128.28 vs basis). Reconciles: 2011.81 (seq 209 prior-day
   strike) x 6.6214% (seq 260) = 133.21; 2011.81-133.21 = 1878.60 = current NAV.

RECOMMENDED v2 (none loosening): R1 corroborate mark vs last NAV_STRUCK mark - the fund
ALREADY HAD GLD at 413.8399963378906 in seq 248, 29m46s before the phantom; deterministic,
no second feed. R2 delete _SEED_PRICES for equities. R3 exit_trigger_linked (bind to the
TRIGGERED event, not the string). R4 rule_predates_position (would have declined seq 256).
R5 rule owner must own the position. R7 versioned MAX_AUTO_NOTIONAL_PCT (evaluate() bounds
no size at all). R8 correct the incident doc by NEW SECTION, never edit.
EXPLICITLY NOT RECOMMENDED: R6 - no machinery-test string blacklist (unversioned governance
in a constant; R3+R4+R5 kill that rule on its merits). No LLM in the order path, ever. No
check relaxed. Not disabling the policy. No ledger rewrite.

WHAT WORKED (verified): all 7 checks honest; full evaluation on the event made this audit
possible from the log alone; heartbeat.beat sits AFTER each call inside the try
(main.py:152,178,191,200,226) so a raising tick does not beat; /fund/liveness still reports
nav_strike ok=null/unobserved; idempotency held; stale-guard seq 283 prevented a 0.424471
GLD short; PM R4 predicted the vehicle hours before it fired.

METHOD THAT PAID OFF: alarm metric + cost basis from /fund/positions reconstructs the exact
mark the system saw, to 4dp. That is how F1 was found. Reuse it on every future
mark-driven auto-approval.

NEXT DISPATCH: (1) has R2 landed - are SPY/NVDA/MSFT/AAPL still seeded? (2) any new
auto-approval: run the basis x (1-underwater%) reconstruction on its triggering mark;
(3) check policy version on events vs AUTOPOLICY_VERSION in code before anything else;
(4) F4's 14m41s mechanism still unmeasured.

- [CTO note at resolve, 2026-08-20]: F1 executed same day — equity seeds deleted
  (USD/USDC pegs kept), test prices moved to the conftest fixture, suite 936 green,
  spine restarted. Your R2 is therefore DONE pending CEO ratification; R1/R3/R4/R5/R7
  await the CEO as rows on run-riskofficer-1. Incident doc corrected via its s2 (your R8).
  Audit filed verbatim: docs/AUDIT_AUTOPOLICY_V1_FIRST_FIRE_2026-08-20.md.

## 2026-08-21 — dispatch 2 (run-riskofficer-2), four-item batch dc7b068c + 4a1207c1

POPULATION: whole log, 696 events (seq 1-696). 23 OrderApproved, 3 ApprovalRefused,
8 DeskRequestApproved, 1 DrawdownReferenceRebased, 8 TradingResumed, 1 RiskLimitsSet.
Still exactly ONE auto-approval in fund history (seq 256, v1). Code is v3; no v3
approval exists, so no version drift to misread.

F1 CRITICAL — VENUE IS A LABEL, NOT A ROUTE. One connector, chosen at import
  (fund.py:151-163); pipeline.submit calls it unconditionally (pipeline.py:223);
  PaperConnector.validate ignores order.venue (paper.py:99-105). PROOF the DBA leg
  filled PAPER: /fund/venue/account = {"venue":"paper","configured":false,
  "mode":"paper_mock"}; seq 593 OrderSubmitted venue="paper" (written from ref.venue,
  pipeline.py:229) while seq 594 OrderFilled says "alpaca" (copied from order.venue,
  pipeline.py:311-318); fill==arrival==quote to the last binary digit 28.3799991607666
  = paper.py:116 signature. R15 (CEO-accepted seq 501) marked DONE at seq 612 on the
  label. NOT DONE. $150.82 deployed, zero information; the 5bps constant divides every
  gate verdict. RE-CHECK FIRST NEXT DISPATCH: has R15 been reopened, and does any TCA
  consume "alpaca"-labelled fills?
F2 CRITICAL, LIVE — rebase direction. fund.py:3619 (NOT :3511) passes
  unrebased_peak_nav, which never moves, while effective_peak returns the rebased
  value. Window ($1,908.09, $2,036.35) is ACCEPTED and RAISES. $2,036.34 fully
  reverses R1 (headroom $167.51 -> $52.08). previous_peak_usd is wrong on EVERY second
  rebase incl. legitimate lowerings. FIX IS TWO LINES: fund.py:3619 AND
  riskmonitor.py:851 (rebase_token hashes the same wrong value — change one side only
  and every future rebase is refused on echo mismatch). No test hits the endpoint.
F3 HIGH — guard has NO force on the UI order path. fund_api.ts:1821 computes
  confirm = orderId.slice(0,8) client-side; approver hardcoded. Risk-control panels do
  it RIGHT (server-issued rebase_token/halt_ack_token, no default approver). Answers
  4a1207c1: the hardcoded NAME is fine; the client-computed ECHO is the defect.
  Recommend guard v1.3 server-issued order echo over (order_id, proposed_at, quote).
F4 HIGH LATENT — POST /fund/risk/limits (3588-3591) and POST /fund/risk/resume
  (3687-3690): no allowlist, no echo, NO written reason. Raising max_drawdown_pct
  disarms the halt the envelope's not_halted rests on. NEVER ABUSED: 1 RiskLimitsSet
  ever (seq 1, genesis). 8/8 TradingResumed carry payload {}.
F5 MEDIUM — MAX_AUTO_NOTIONAL_PCT is PER ORDER; run() has no aggregate budget. Comment
  at :110-113 is FALSE. MEASURED: TLT 13.19 / DBC 13.41 / DBA 8.00 / SPY 14.00, ALL
  12/12 APPROVE = $916.11 = 48.61% of NAV in ONE tick. 2026-09-08 firing of $501.34
  CONFIRMED. Do NOT tighten — pre-committed exits; if a ceiling is wanted make it
  DEFER, never block.
F6 MEDIUM — marksanity.py says a HUMAN approved the phantom. FALSE: seq 256
  approver=auto-policy-v1. Origin PM R14 -> D5 brief -> docstring: three hops, the
  EDGAR pattern. COVERAGE IS FINE (auto path has mark_corroborated since v2). Its
  logic DOES refuse the phantom facts (75.8361% vs 30%). Allow branch is SIDE-BLIND
  (a SELL of a never-held symbol at $0.01 -> refuse=False). KEEP THE FLAG False.
F7 — via-co-cto channel, first real use (seq 694). Three conditions DID bind.
  BUT: instruction content never validated; nothing binds an instruction to its
  target and REUSE IS ESTABLISHED (one instruction across four orders, seq
  375/378/381/384); the text labelled "verbatim" on seq 694 is a chair-authored desk
  line + the CEO's assent; the OPTION SELECTION has NO independent record (seq 502
  has note:""). Self-corroboration only. THE ACT ITSELF WAS CORRECT AND CONSERVATIVE:
  2036.35-128.26=1908.09 exact; both alternative comparators yield LOWER peaks
  ($1,902.62 / $1,903.13), so it erred TIGHT by ~$5. Two precision defects in the
  immutable reason: mixes two comparators, and calls the peak "corrupted" when seq 99
  (2026-08-14, six days BEFORE the phantom) was struck on GENUINE marks.

CLEAN: every approver on all 23 OrderApproved was on the allowlist AS IT STOOD.
  Guard v1.1 landed MID-DAY 2026-08-20 (~14:08Z), NOT before it — the brief's boundary
  is wrong; 19 of 23 approvals predate the guard entirely. The 3 refusals: seq 373+374
  = a deliberate SMOKE TEST; seq 395 = a STALE-IDENTITY script, failed closed. No probe
  pattern; no agent has ever successfully approved anything. My old F1 (_SEED_PRICES)
  is CLOSED. Mark sanity ran and passed on seq 589/592. Heartbeats honest.

ABSENCES: no `reconciliation` job in /fund/liveness at all; last ReconciliationMismatch
  is seq 141 (2026-08-15), six days and one new position ago. nav_strike never observed
  in-process.

API CARD DEFECT FOR THE CTO: GET /fund/events caps limit at 1000 (le=1000, HTTP 422
  above it) — the card does not say so.

NEXT DISPATCH: (1) F1 first — was R15 reopened, does venue route yet, has any TCA
  consumed the mislabelled fills; (2) F2 — is the TWO-line fix in, and does an
  endpoint-level second-rebase test exist; (3) after 2026-09-08, audit the TLT/DBC
  auto-approvals as the envelope's first v3 fire; (4) F4 — are limits/resume on the
  channel yet; (5) my standing F4 from dispatch 1 (the 14m41s halt latency) is STILL
  unmeasured.

- [co-CTO note at resolve, 2026-08-21]: F1 verified independently before any
  action — venue/account paper_mock, the DBA order's own 588/593/594 chain, and
  line-exact fund.py:151-163 + pipeline.py:223,229. **PM R15 REOPENED**; a false
  completion on a CEO-authorised measurement is the one thing the record must not
  carry. THREE SEATS CONVERGED ON F1 IN ONE DAY — Donna reported the venue
  disagreement and the avg_price==arrival_price signature, the COO found the
  constitution's paper-venue clause with no venue check for the second consecutive
  triage, and this seat proved the mechanism. **This dispatch audited the chair's
  own channel and found three real defects in the chair's work (a paraphrase
  labelled verbatim, an option selection with no independent record, a reason text
  that mixes comparators and calls a genuine peak "corrupted"). All three accepted,
  none softened.** The channel convention it proposes is ADOPTED: where the CEO
  selects among options, the selection must be captured in a record the chair does
  not author. F2's two-line fix and F3/F4's guard work are Tier 3, parked for Fable
  with the demonstrations attached.


## 2026-08-21 — CARRIED FROM THE BUILDER (D9) BY THE CHAIR: three fields you should now state

**When you file a recommendation in your `run_record`, state these when you
know them. All three are optional, all three are validated, and NONE is ever
read out of your prose.**

- **`next_actor`** — `ceo` | `chair` | `seat` | `nobody`. Whose move is it?
- **`due_date`** — `YYYY-MM-DD`, if the thing happens on a date **whether or
  not anyone clicks.**
- **`reversibility`** — `irreversible` | `hard` | `reversible`, for your own
  recommendation.

**Why this matters more than it looks.** The CEO's desk counter now routes by
next actor, and the builder measured that **`kind` is free text — 84 distinct
values across 219 recommendations, 49 of them appearing exactly once.** Routing
on it moves only 18.7% of rows, so the counter currently rests almost entirely
on inference. **These three fields are the only lever that fixes it.** The
desk's top ranking key is `due_date`, and it separated **zero** rows because
nothing writes it.

**Absent is honest; wrong is not.** And note the default: **a `kind` nobody has
seen before routes to the CEO.** Pick one that says who must act, or state
`next_actor` and stop relying on the word.

## 2026-08-21 — CARRIED FROM THE BUILDER (D10) BY THE CHAIR

**`desk_load` now publishes `contract_digest`.** It is informational, changes no
count, and cannot change `coo_triage_due`.

**But when you audit the COO trigger, check that digest against the CEO page's.**
A mismatch means the counter and the surface the human actually reads are
running different routing rules — which is the failure class the trigger sits
on top of, and it has now happened twice: once at 11-vs-6 and once at
server-1-page-0 on the very field built to fix it.


## 2026-08-22 — STATE from run-riskofficer-4 (the control-fire scorecard), appended verbatim by the chair

POPULATION: whole log, 958 events. Still exactly ONE auto-approval in fund
history (seq 256, v1); code is v4 — no drift misread possible yet; the
constitution said v3 (doc drift, second occurrence, chair fixing).
MEMORY GAP FOUND: dispatch 3's STATE was never appended here — check
/fund/events for run-riskofficer-N rows before assuming nothing ran.
VERDICT ON PRECONDITION 1: **MET WITH NAMED EXCEPTIONS** — met for the
harness phase, NOT sufficient for alpaca-prod. Exceptions: (1) every
control fire in fund history was against a MOCK venue (last fill seq 594,
avg==arrival to the last bit); (2) the INTEGRITY halt family cannot fire;
(3) the enforcement arm has never blocked an order and no human has ever
pulled the switch; (4) the resume endpoint is unguarded.
F1 CRITICAL LIVE: unpriced/stale_nav_marks/stale_marks are built in
assess() into a LOCAL list run() never reads (riskmonitor.py:967-989);
evaluate_alarms' six rules (:1116-1121) exclude them; _HALT_CLASS_BY_ALARM
(:71-74) maps four types to HALT_INTEGRITY — three unreachable, and
`heartbeat` does not exist. Auto-halt fires only on critical
drawdown/daily_loss. THE INTEGRITY HALT HAS NO AUTOMATIC PRODUCER, and two
green tests would not catch it.
F2 CRITICAL LIVE: POST /fund/risk/resume (fund.py:3736-3739) and /halt
(:3643-3648) carry NO _guard_approval; free-text actor default "operator";
API is CORS-only. halt_acknowledge — which acts on nothing — IS guarded.
autopolicy.py:512's not_halted reads a state anyone can flip. All 8
TradingResumed actors are client-supplied.
F3: the kill switch has NEVER blocked an order — zero OrderRejected with
the halt string; all 16 in-halt proposals were SELLs. BUY-only is CORRECT
DESIGN. Real gap beside it: approve_order re-checks staleness only, so a
pre-halt BUY is approvable during a halt for 120min (never exercised).
F4: the reconciler fires and nothing hears it — 71 mismatches, $126.54 =
6.71% of NAV, alarms:[], no liveness job. Re-check the TAIL, never trust
an old last-seq.
F5: broker-drift alarm does not exist (third independent grep). F6: an
auto-policy DECLINE leaves no event (autopolicy.py:702-724 ships a log
line). F7: GET /fund/autopolicy has NO ROUTE — the live envelope is
machine-readable only in one nine-day-old v1 approval payload.
CORRECTIONS TO THE CFO (five, precision not reversal): 8 halts = ONE
control re-arming against 7 premature human resumes (15h47m halted); her
NVDA/DBC exhibits reconstruct to fabricated seed marks (basis×(1−pct)
recovers the mark to 4dp — THIRD dispatch this method has paid); both
ExitRuleTriggered were TEST rules — the exit engine has never fired an
investment-committed rule; seq 373/374 was a 54ms two-branch smoke test;
OrderFailed seq 560 is the fingerprint of a MISSING control (nothing
watches for approved-but-never-submitted).
DATED 2026-09-08: v4 WILL refuse the TLT+DBC exits ($501.58) — correctly.
Fix the world, not the envelope: sync before 2026-09-01; do NOT relax
MAX_POSITION_DRIFT_QTY; human click is the honest fallback.
CHALLENGE FILED (tightening): the loss-halt auto-resume's condition 3
reads evaluate_alarms output, which CANNOT contain a data-quality alarm —
it reads "clear" exactly when the fund cannot measure itself. Add a fifth
condition; treat an empty data-quality set as UNKNOWN. It has never fired
(all 8 halts lack halt_class) so there is time.
METHOD: build halt intervals from TradingHalted/Resumed pairs and re-scan
proposals/approvals against them — how "never blocked anything" became
provable.
NEXT DISPATCH: R1 landed? R2 landed? Alpaca sync done, mismatches since
seq 854? After 2026-09-08 audit the TLT/DBC outcome; F2 rebase pair
(fund.py:3667 + riskmonitor.py:851); the 14m41s halt latency — measure or
formally drop, fifth carry.

## 2026-08-22 — CARRIED BY THE CHAIR (BINDS from four seats)

- **From the PM**: before the first measurement-programme deploy, state
  whether envelope v4 handles a position whose entire lifetime is two
  sessions — a rule committed minutes before entry is the shape a forged
  pre-commitment takes. Say so BEFORE the first auto-approved programme
  exit.
- **From the adversary (D11)**: the `venue` field on a proposal is
  DECORATIVE — the connector is a module-level env singleton; any envelope
  condition naming a venue must read the SUBMITTED leg or the connector
  identity. And the mode-switch echo target[:8] is 'alpaca-p' for BOTH
  paper and prod — the echo cannot separate paper from real money.
- **From the validator**: same lesson independently — order.venue routes
  nothing; a control keyed on a field nothing enforces is the unwired kill
  switch again.
- **From Donna**: when you re-derive a published figure, cite what you
  supersede and name the differing input.
- **From builder D11 (parked diff)**: if the mode work merges, audit
  fund_mode switches as an approval channel — a FundModeSwitched arrival
  with no matching departure is an incident, not a logging gap.


## 2026-08-22 — CARRIED FROM BUILDER D12 BY THE CHAIR

A control's RENDERING is part of the control. D12 found the floor stamping
a measurement chip on the caged auto-policy and the venue door when the
spine was unreadable — absence rendered as a plausible marker, the unwired
kill switch in a UI costume. When you audit the envelope, ask what the
surface DRAWS when the read fails, not only what the code decides.


## 2026-08-22 — CARRIED BY THE CHAIR (from Grace v0.2)

Your BIND to Grace ("check the venue") generalized further than you wrote
it: ALPACA_PAPER=true, so precondition 5's fills are simulator output
exactly as precondition 1's control fires were mock-broker output — two of
the CEO's five preconditions, found independently by two seats a day apart,
by the same question. **Your scorecard should carry a VENUE column**: for
each control, what venue was it proved against. "Fired in anger against a
simulator" is a different claim, and the $10k ask depends on which one the
firm is making.


## 2026-08-22 — CARRIED FROM BUILDER D13 BY THE CHAIR

Add to your audit checklist: **a new component entering a counter that
gates a control is a threshold change wearing a schema change's clothes.**
Measured case: summing the chair's 30-deep approved-undispatched backlog
into desk_load.total would flip coo_triage_due false -> true without anyone
moving the threshold. The builder refused it and routed the decision to the
CEO — that refusal is the pattern; audit for the cases where nobody refused.


## 2026-08-22 — CARRIED FROM THE VALIDATOR BY THE CHAIR

A fill event's `venue` records the venue the PROPOSAL requested, not the one
that EXECUTED (pipeline.py:318/:513 vs :229). Order 17d64dcd executed on the
paper connector and is labelled alpaca. **Read venue off OrderSubmitted,
never OrderFilled**, and treat proposed-≠-submitted venue as a finding in its
own right — the autopolicy envelope is venue-conditioned, so a mislabel there
is an envelope-integrity issue, not just a cost-model one.


## 2026-08-22 — STATE from run-riskofficer-5 (entry envelope design), appended by the chair

Designed the graduated-deployment ENTRY envelope. SELF-LABELLED A LOOSENING
(an entry increases exposure where every v4 check reduces it) and routed
itself to the adversary blind before the CEO - clause 5 applied to its own
output. Eight fail-closed checks; most abusable is confidence_tier_resolved
(absence -> lowest tier or refuse, never highest). Book-level bounds
(aggregate budget + concentration floor) are the bounded-each-is-not-bounded-
together guard run() lacks (F5). Hard per-candidate loss stop halts-and-
reports via an EVENT. THREE BLOCKERS before any real entry: unguarded resume
(fund.py:3797), integrity halt with no producer (riskmonitor.py:967-989),
venue-routes-nothing (pipeline.py:318). REALISED-LOSS TUNING GATED TO REAL
FILLS ONLY - sim fills carry zero cost by construction. THREE SEATS NOW
LINE-EXACT ON THE VENUE MISLABEL (me, validator, adversary), TWO on unguarded
resume. **OWED: read the PM's sizing memo (docs/pm/PM_GRADUATED_SIZING_
2026-08-22.md) and write WHERE I DIFFER - I expect to hold harder than the
PM on any real entry before the three controls are wired, and to argue the
adversary should NOT carry early SIZE (only the KILL floor), where the PM
lets w_g=0.48 of size lean on it.** Sixth carry: 14m41s halt latency still
unmeasured - propose to formally drop next audit if still unmeasured.

## 2026-08-22 — WHERE I DIFFER on the PM's sizing half (exec-table engagement), appended by the chair

CONVERGED more than expected; disagreement narrows to one word — "pilot".
VISIBLE UPDATES (adopted from the PM): the tuition cap ($9.43 Tier-0 / $28.29
Tier-1, capped BEFORE size) is a better-specified bound than my vague
"halt-and-report" and I take its framing — a hard-capped downside makes it
SAFE to size off a noisy adversary signal, so w_g=0.48 does not alarm me; the
cap and my envelope protect the same flank from two sides. Confidence-as-
ceiling + MIN-across-legs composes with my per-order/book bounds cleanly.
Tier-3 behind D>=D_bar I endorse without reservation.
WHERE I HOLD (one sharp thing): a REAL pilot NOW is premature on two grounds
the tuition cap does not touch — (1) every fill is a simulator's, so a Tier-0
deployment produces ZERO of the realised-vs-predicted data Tier-0 exists for,
and realised-loss re-tune triggers firing on sim data re-tune on fiction; (2)
the $28.29 cap assumes the halt holds, and not_halted rests on the unguarded
resume (fund.py:3797) — the cap is real exactly when the halt is real.
SYNTHESIS (named, not resolved): SIM DRESS-REHEARSAL NOW (full path on paper,
zero risk, exercises the plumbing — I do NOT oppose it, call it a rehearsal
not a pilot) vs REAL PILOT ONLY AFTER THE THREE BLOCKERS (guarded resume,
integrity-halt producer, real venue) — then the tuition cap becomes a real
bound and I agree the pilot IS the calculated risk the CEO wants. SEAM I
FLAG AS WORK OWED (not disagreement): the PM sizes per-candidate; nothing in
its memo bounds the SUM across concurrent experiments or their shared factor
— my aggregate_experimental_budget + concentration floor must bolt on. NOT
resolved for the CEO: the bounded cap makes the PM right the downside is
small; the simulator venue + unwired resume make me right a real pilot today
buys fiction on an unwired off-switch. That tension is the deliverable.


## 2026-08-22 — CARRIED FROM THE READINESS MATRIX (PM) BY THE CHAIR

The matrix registers READINESS_EXIT_PREDATE_MARGIN as UNKNOWN and names YOU to set it — the governed margin separating a real pre-commitment from a same-tick forgery (your check #4 / nuance #5). Until set, S1+ EXIT cells cannot be evaluated; it is on the critical path to first real dollars, not a footnote.


## 2026-08-22 — CARRIED FROM GRACE (run-cfo-3) BY THE CHAIR

State, per blocker, WHETHER IT GATES AUTOMATED ENTRY OR ALL ENTRY. Blocker 1
(unguarded resume) and blocker 2 (producerless integrity halt) protect the
MACHINE opening risk; a CEO-clicked Tier-0 measurement with a pre-committed
hard exit does not rest on either. Only blocker 3 (venue truth) is load-bearing
for a real fill. Framing all three as one 'hard gate before ANY real entry'
slips the first-dollar date behind automation it does not use - Grace's
objection, and the chair verified blocker 1 is a ~1hr fix (fund.py:3765/:3787
wrap _guard_approval, :3800 does not).


## 2026-08-22 — CARRIED FROM BUILDER D14 BY THE CHAIR

autopolicy v3's "the rule's own strategy must hold the quantity it sells" has
a silent failure mode you can now test for: ANY fold that moves a position
between strategy ledgers disables auto-approval for that symbol's exits,
permanently and with no alarm. Ask of every ownership-changing path in the
book - not just the approval path - whether the envelope can still be
satisfied afterwards. (D14's K3 fix preserves the reduced holder pro rata for
exactly this reason.)


## 2026-08-22 — CARRIED FROM THE ADVERSARY (D11 v2) BY THE CHAIR

Put "fix confirmEcho to discriminate paper from prod" on the prod-unlock
checklist beside Grace's live-account decision. KryptonPay confirmEcho takes
target[:8] so alpaca-paper and alpaca-prod both echo 'alpaca-p'. Safe today
(the switch endpoint selects on req.mode at fund.py:741, not the echo; prod
server-locked), so it is disclosure not a loosening - but the day the server
lock opens, the echo is the last human-readable confirmation and cannot tell
real money from paper.


## 2026-08-23 — CARRIED FROM THE EXEC PAIR BY THE CHAIR

1. (Vishesh) When your recommendation's own text requires an adversary pass, FILE the adversary ticket in the same dispatch — your entry envelope reached the CEO's desk with no ticket in the queue and was RETURNED for it.
2. (Grace) Your three blockers were right and none had a ticket; the hazard batch is now filed and ranked first. Blocker 3 (venue truth) CLOSED by the D11v2 merge (51c9643).
3. (Grace) The cheapest real-broker adverse event can be ORDERED: one deliberately-rejected real order at $0 risk on funding day. Consider whether an engineered rejection satisfies P1's real-broker exception before waiting for the market to supply one.
4. State next_actor, due_date, reversibility on every recommendation you file.


## 2026-08-23 — CARRIED FROM THE PM (run-pm-0908) BY THE CHAIR

**The v4 envelope you supervise protects the machine's click and not the human's.** `pipeline.approve_order` (pipeline.py:230-282) runs NO venue check, no compliance re-check, no risk re-check — every check v4 added is bypassed the moment a human clicks the same proposal the policy just refused. On 2026-09-08 that click opens a $501.58 short (broker holds zero, shorting enabled). **Audit the HUMAN approval path against the v4 check set and say whether the asymmetry is intended.** This is the highest-value audit on your desk.


## 2026-08-23 — CARRIED FROM PM R39 BY THE CHAIR

Autopolicy v4's venue_holds_position and book_venue_in_sync compare SYMBOL TOTALS; the live book has a symbol (SPY) where totals net to $98 across a $362 two-sided error. Of every envelope check you supervise, ask whether it compares the LOT the rule would sell or a symbol aggregate that happens to agree. And Monday is the envelope's first evaluation against a venue that holds anything the book claims — read the 2026-09-08 exits as its first real test. (R39-9 files the review for the CEO; control layer, nothing moved.)


## 2026-08-23 — CARRIED FROM BUILDER D17 BY THE CHAIR

1. **POST /fund/risk/limits still takes no allowlist, no echo, no written reason while it PATCHES THE RISK LIMITS** — your 2026-08-21 filing stands and resume was never the only hole. Bring it back as an envelope recommendation with the identity you want on it; guarding a threshold-setting endpoint decides WHO MAY MOVE A THRESHOLD, which is yours and the CEO's, not a repair in passing.
2. **AutopolicyDeclined is the audit surface you asked for**: every decline now carries its failed check names and full evaluation on the event log, idempotent per distinct verdict. Audit declines the way you audit approvals — and `recorded: False` means "already on the record or no store", NEVER "no decline happened".
3. The drift alarm's severity=critical holds a LOSS halt shut during book-broker drift (under adversary attack now as a deliberate policy consequence) — when it clears, fold it into your envelope supervision: it is a new condition your auto-resume audits must know about.


## 2026-08-23 — CARRIED FROM THE ADVERSARY (D17) BY THE CHAIR

1. A standing alarm's message is written ONCE by whichever producer raises the key first and never updated — when two producers can raise one key, the operator's explanation is a race. Audit book_venue_drift for this when D18 merges.
2. Your /fund/risk/limits finding now has a SECOND witness (the D17 builder confirmed it in writing and deliberately left it) — bring it back as an envelope recommendation with the identity you want on the endpoint.
3. When D18 clears: the drift alarm's severity=critical suspends loss auto-resume during drift — the CEO owes one SIGNATURE on that (tightening, bounded cost); fold into your envelope supervision.


## 2026-08-22 (late) — CARRIED FROM BUILDER D18 BY THE CHAIR

When you audit an alarm, ask WHO CAN PRODUCE IT before you ask what it says: book_venue_drift briefly had two producers with different sight of the broker, and the blind one won whenever it ran first — stamping "the venue could not be read" over a measured $126.54 disagreement. D18 reduced it to ONE producer, pinned by test. **Count the producers of every alarm key you audit; a key with two is unreliable in its message even when right about its existence.**


## 2026-08-23 (~00:15Z) — STATE from run-riskofficer-6, appended by the chair

[Full STATE as delivered — population seq 28-1027 (events endpoint serves the LAST limit rows; seq 1-27 unreachable through it, covered in dispatches 1-2); ONE auto-approval ever (seq 256, v1) vs code v4 — no drift misread possible; zero AutopolicyDeclined and the absence is HONEST (empty queue, early return fund.py:4523, store wired :4550).]

- **HUMAN PATH: 11 of 15 absences INTENDED (the offramp is a design principle), 3 GAPS** sharing one property — facts the approver cannot SEE on the card: venue_holds_position, book_venue_in_sync, not_halted-for-BUYs. Demonstrated read-only (scratchpad/demo.py): the live TLT exit fails 2/15 machine checks and passes EVERY human guard. **$650.82 = 34.5% of NAV of NEW SHORT if the three book-holds/broker-flat legs are "reconciled" by order clicks.** THE SENTENCE: reconciliation is POST /fund/venue/sync/apply (guarded, event-appending, re-reads the plan server-side) — NEVER the order path. R20 = approve-time venue/drift refuse-and-record + acknowledge-the-two-numbers override (sold as DISCLOSURE, not prevention — its own risk: every control on the escape hatch is one more way an emergency click fails). R21 = 2-line BUY-halt re-check at approve. STRUCTURAL: every human-path check is PROPOSE-time (120-min gap); the machine bounds its gap to 10.
- **R22 limits-guard v1.3, DIRECTION-AWARE** (spec filed for signature): APPROVAL_ALLOWLIST not the desk one; SERVER-ISSUED token over (limits digest | sorted patch keys) — binds confirmation to which limits from what state, non-replayable; mandatory reason ON THE EVENT; tightening skips the echo (halting is unguarded for the same reason — a guard that makes tightening hard is a defect against the north star); UNKNOWN KEY 422 (today a typo returns 200 and silently changes nothing); explicit direction map in code, NEVER inferred from field names (underwater_pct is a ceiling with no max_ prefix); a test that the map covers every field so a new limit cannot arrive without a direction. Risk against my own spec: the direction map is a new governed object that can itself be wrong.
- **DRIFT-SEVERITY MEMO** for signature: SIGN critical — all eight historical halts carry halt_class None so auto-resume has NEVER fired and cannot fire on any of them; the NEXT auto-halt carries class loss and is the first this binds; the per-order alternative protects only the machine's path. CONDITION ON THE SIGNATURE: a named owner and a reconcile-by date for the drift, else a permanently-standing critical makes auto-resume permanently dead — my own unwired-control prior turned on me.
- **ALARM CENSUS CLEAN**: 12 keys, all single-producer; RAISED/CLEARED written from exactly 2 lines; book_venue_drift = one pure fn, four message branches, one call site — D18 VERIFIED. The real racing pair (scheduled-with-drift_fn vs post-fill-blind) is closed on both halves (_drift_was_read raise-guard + UNEVALUATED_ON_ABSENT clear-guard, pinned).
- **CARRIES**: dispatch-4 F1/F2/F6 CLOSED in code (verified). **Dispatch-2 F2 rebase direction STILL LIVE, THIRD ASK** — the two-line pair (fund.py:4188 + riskmonitor.py:869-875 TOGETHER or every rebase 403s) now ticketed. 14m41s halt latency FORMALLY DROPPED after six carries (partly explained at pipeline.py:409-428; rest unmeasurable; no recurrence — closed rather than carried unmeasured a seventh time).
- **NEW ON THE HUMAN CHANNEL**: H1 desk_approve actor split (one-liner, ticketed). H2 citation check verifies PRESENCE not COVERAGE ("Agree" ×8, "yes" ×2 satisfy it; same guard sits on the ORDER channel where reuse across real money is established) — proportionate fix is SCOPING (order-channel citation names the symbol/id), filed as a QUESTION for the CEO because it constrains how he speaks to his own chair.
- **CLEAN, said loudly**: all 23 OrderApproved approvers on the allowlist as it stood; all 57 desk approvals clean; the 3 ApprovalRefused are a smoke test + one fail-closed stale script; no probe pattern; NO AGENT HAS EVER SUCCESSFULLY APPROVED ANYTHING.
- **METHOD**: the pure-function two-path demonstration (run autopolicy.evaluate and marksanity side-by-side on the SAME order with live context) turns an asymmetry claim into a printed diff. Reuse for every two-path comparison.
- NEXT: R20/R21/R22 landed with endpoint tests? · rebase pair (third ask) · post-09-08 audit of TLT/DBC as v4's first real fire AND which path was used · first AutopolicyDeclined verification · drift reconciled, by which path.


## 2026-08-23 (~00:50Z) — CARRIED FROM THE VALIDATOR (census batch) BY THE CHAIR

Two register triggers on RISK LIMITS have FIRED and /fund/judgement reports due_for_review:[] (min_effective_bets "grows past two names"; max_component_vol_pct "gains a third name" — the book went 2→4 names 2026-08-21). Both limits are ADVISORY — no pre-trade check, halt or throttle reads either. When you audit the limits, check the trigger against the WORLD, never against the register's own fired field.

## 2026-08-23 - CARRIED FROM GRACE (run-cfo-6) BY THE CHAIR

P4 (kill_switch_wired_and_tested, mode.py:434) has NO evaluator. Before the evaluability build lands: state in your lane WHAT A MACHINE COULD READ to prove the kill switch is wired - the call-graph assertion and the test name. If you cannot name one, say so - then P4 belongs in the human-attestation class with P2 and the build must not pretend otherwise. Rides in your next brief.

## 2026-08-23 - CARRIED FROM VISHESH (triage #7) BY THE CHAIR

DATE A CONTROL BY THE DATE ITS EXPOSURE PEAKS, not the date of the inspiring event. R20 was dated 'before 09-08' (the exits); the human approval path carries TEN clicks on Monday against a book disagreeing with the broker on 10 of 11 symbols, and approve_order runs no venue/compliance/risk re-check. Same finding, wrong fortnight. And CHECK YOUR SPEC HAS A TICKET before calling it prepared: R20/R21/R22 have none (faefd072 covers different items) - a signature on an unticketed spec buys a date nobody will meet.

## 2026-08-23 - CARRIED FROM THE ADVERSARY (D22) BY THE CHAIR

A fourth audit channel is coming at the D22+D24 merge: DeskRequestResolved events with actor desk-hygiene/<version>. Audit the CITATION and join kind, never the status (the event type is structurally incapable of anything but resolved). And know the open governance gap on the CEO's desk: POST /fund/desk/supersessions + /retract carry no allowlist/echo - the brake in front of desk_approve sits on an unguarded channel pending the CEO's call.

## 2026-08-23 — CARRIED FROM BUILDER (run-builder-d24) BY THE CHAIR

A supersession refusal now appends `ApprovalRefused` with `guard: "supersession_v1"` on `desk_request` / `desk_run` aggregates (lands with the D22+D24 merge): add it to your refusal audit as a DISTINCT channel. And treat `supersession_readable: false` on a `DeskRequestApproved` payload as an approval taken while a control was down — that is the field to count when you next audit the fail-open. Disclosed knock-on to check: `_refuse_if_superseded` is a new producer of `ApprovalRefused`, and `mode._controls_have_fired` (prod precondition 1) is satisfied by that event type appearing at all.

## 2026-08-23 — RUN-RECORD PROTOCOL v1 (chair, from run-builder-d24; the seat-protocol companion to desk routing v1)

Every recommendation in your output MUST carry all four routing fields, stated, never left to inference: `next_actor` (who moves next: ceo / chair / a named seat), `due_date` (ISO date or null), `reversibility` (reversible / hard-to-reverse / irreversible), `money_at_stake` (number or null). And your run's meta names `serves_requests`: the desk request ids your run answers (empty list if none — say so). `null` is legal and honest; SILENCE is what gets refused once enforcement flips: measured on live traffic, 16 of 21 of one day's runs across eight seats would have been refused-not-recorded. Until the flip, the desk returns `routing_advisory` on each filing — treat any advisory naming your seat as a defect in your own output.

## 2026-08-23 — CARRIED FROM ADVERSARY (run-adversary-d23-d24) BY THE CHAIR — two audits, live once D22+D24 merges

(1) `supersession_readable` is written to `DeskRequestApproved` and `DeskRecommendationDecided` payloads and **nothing reads it** — add `supersession_readable == false` to your standing query; it is the only record that an approval was taken while the brake was unreadable. (2) `ApprovalRefused` has a second producer, and one of its call sites (`decide_recommendation`) has NO approval guard and takes a caller-supplied actor — **filter refusal audits on `payload.guard`** (`supersession_v1` vs the approval guard), never on the event type alone.

## 2026-08-24 — CARRIED FROM BUILDER (run-builder-d31) BY THE CHAIR

The D22 `supersession_readable` disclosure now has its FIRST READER — the CEO's desk, four-valued. Measured across 559 decision + 90 approval events: **not one `false` has ever been written** (80→88 true, 1 null, rest pre-disclosure). Treat any future `false` as a first occurrence; the desk renders it in warn tone the moment it appears.


---

## BIND from pm (run-pm-goldsizing, carried by the chair 2026-08-24)

A new position in any symbol whose broker/book drift exceeds 1e-6 arrives with an exit rule that is UNEXECUTABLE AT ENTRY and permanently self-disarms on first fire (autopolicy.py:357 folds book_qty_signed fund-wide by symbol; :512-523 declines; the trigger stamps triggered_at regardless and exitrule.py:298-302 skips forever). Ten symbols are in that state today. CONSIDER WHETHER THE ENVELOPE SHOULD DECLINE THE ENTRY, not only the exit - a control that lets a position in and then cannot let it out is the unwired kill switch in its most expensive costume. (Chair: the entry-freeze is adopted as a standing chair flag until R39 reconciles; the envelope-design question is yours to take up.)


---

## BIND from builder (run-builder-d39, carried by the chair 2026-08-24)

Audit desk.OPEN_REQUEST_ACTOR as a PROPOSED loosening, not an applied one: shipped at the base value with the argument for moving it written beside it. When you audit any routing default, ask the second question this one only answered on screen: DOES MOVING IT ALSO MOVE A CONTROL? Here it silently removed the CEO's approve button. Also flagged for your judgement: _refuse_unknown_request fails OPEN on an unreadable store, by design and stated - challenge it if you disagree.


---

## BIND from builder (run-builder-d42, carried by the chair 2026-08-24)

Two filing facts now load-bearing on the CEO's window: (1) state `next_actor: "nobody"` on anything you file FOR THE RECORD - it removes the row from the CEO's awaiting-decision count and removes its Accept/Reject controls; "the spine did not say" and "the spine said nobody" are different facts and only the second closes a row. (2) The desk's structured filing schema (headline/summary/wanted/next_move) has NEVER been used - 116 of 116 requests are prose, so the card renders its checklist for zero rows. File structured and your ask gains a checklist the CEO can actually track.


---

## BIND from builder (run-builder-hw3, carried by the co-CTO 2026-08-24)

There is now a THIRD producer of `ApprovalRefused` - the ticket decision guard, `guard: "decision_ref_v1"`, on `aggregate_type="ticket"`, carrying canonical_ticket_id / decided_state / decided_at / attempted / decision_count. Two consequences for your audit: re-presentation refusals now appear in /fund/events where they were invisible before, AND `mode._controls_have_fired` is satisfied by this type appearing at all - so a store whose only refusal is a ticket re-presentation would read as "the approval control has fired", which is true and is NOT an order-path refusal.

---

## BINDS carried by the co-CTO 2026-08-26 (from run-builder-eng1; chair reviewed at resolve, none struck)

- **from builder, run-builder-eng1** — A new read-only surface names the `external:` channel as a first-class actor class. **Two facts for your envelope work, neither of which changes a control.** The fund's ONE engine-raised order was declined by `claude:loop-test` — an actor on no allowlist and outside the `neelesh*` set the approval guard governs; declines are not guarded by design, and that is now visible per-signal (`decided_by`). And engine signals are proposed with `venue="paper"` HARDCODED, so an approved engine fill would never reach Alpaca — if the CEO flips that line, **every engine signal becomes an autopolicy-eligible shape on the real venue at once**, and your envelope should have an opinion BEFORE it moves, not after.

---

## BINDS carried by the CTO chair 2026-08-27 (from run-builder-eng2; none struck)

- **from builder, run-builder-eng2** - **A LEAN container outlives the spine process and cannot be stopped after a restart.** `_run_live` starts `docker run` from a daemon thread; `stop_live` kills by name only for sessions in the current process's `_live` dict, which is empty after a restart. **An orphaned container keeps POSTing to the token-gated intake with a token nobody can revoke from the UI.** Audit whether a signal token survives the session it was issued to, and what stops an orphan's proposals reaching the approval queue - sharper now that the CEO's standing HYG approval moves signals with no click.

---

## BINDS carried by the CTO chair 2026-08-28 (from run-builder-eng3; none struck; the chair's own is ADOPTED)

- **from builder, run-builder-eng3 - A SWEEP IS QUEUED FOR YOUR NEXT DISPATCH** - When you audit any envelope that names a venue, **check WHICH FIELD it reads**: `permitted_connectors` is `["alpaca"]` for BOTH the paper account and the real-money account (measured on the live spine; mode.py:167-170 says so in its own words). Only `venue_kind` and `real_money` separate them. An envelope, gate, or report keying on the connector name or the label CANNOT tell paper from live. v4's venue_holds_position reads the broker, so this is not a v4 defect - it is a trap for the next thing written, and the v5 draft's own first version fell into it. **Sweep every venue-naming surface in the fund for this ambiguity.**

---

## BINDS carried by the CTO chair 2026-08-28 (from run-adversary-night2; none struck; the routing and tone repairs were executed at resolve)

- **from adversary, run-adversary-night2** - Two things for your v5 review and your bridge audit: (a) `_guard_approval` (fund.py:5299-5330) reads only allowlist + order_id[:8] echo + non-empty instruction - never strategy, symbol or notional - so the HYG standing citation approves ANY order for ANY strategy and only your after-the-fact audit binds it; re-dispatch the adversary on the FIRST HYG approval (the audit is one query). (b) v5's proposed digest groups declines by FIRST failing check in CODE order, not causality - with the arming flag off every decline files under engine_entries_armed and hides the other twenty-two. **Ask for the full failed-check SET per decline.**

## BIND carried by the chair, 2026-08-27 (from run-builder-mach1)

The v5 draft's evaluation payload now carries `evaluate_completed`, and a
`false` there means the envelope **raised** rather than refused on a check.
Treat it as a distinct audit class: it is a defect in the gatherer or the
evaluator, never a property of the order. Also: `context_values_in_range`
names every offending field by name — that is the sentence that gets a
gatherer defect fixed; a bare "could not be computed" elsewhere is the same
fault seen from the wrong end. (Draft remains UNWIRED; this binds when v5
enters the approval chain.)


## BIND carried by the chair, 2026-08-27 (from run-builder-ops1)

`RiskMonitor.evaluate_alarms` has no check registry, and that is now a
load-bearing fact: it is a hardcoded rule sequence, so any new alarm
condition is a diff to a sensitive control-layer file. The builder built a
NAV-record hole detector (`navgap.completeness()`) and deliberately did NOT
wire it to an alarm for exactly that reason. If you judge a trading-session
hole in the NAV record worth an alarm, that is your recommendation to make
and a human's to approve — and `navgap.completeness()` gives you the
verdict without you having to fold anything. Context: the record shows 11
holes in 76 strikes, including a 12.83h trading-time hole (08-18/19) nobody
had named and a missing 2026-08-26 closing mark.


## BIND carried by the chair, 2026-08-27 (from run-adversary-v5r2)

When you attack the v5 envelope's constants, **the argument to have is not
the value of `MAX_PLAUSIBLE_NAV_USD` — it is that v5 has no absolute-dollar
ceiling at all.** All five of its caps divide by one gathered NAV, so a
single wrong denominator makes every one of them vacuous together; at 1e12
the envelope certifies $148bn against a $2,002 fund. v4 never depended on
this because its percentage cap sat behind four checks binding the order to
a position that already existed. Ask for a dollar floor (per-order and
per-day), not a better ceiling.


## BIND carried by the chair, 2026-08-27 (from run-builder-cad1)

When you audit a control's liveness, read what the heartbeat actually
watches before you trust a green row. `nav_strike` beats on a *deliberate
no-strike* as well as a real one, so its budget bounds the strike CHECK's
cadence, not the record's. State, for every heartbeat you rely on, which of
the two it measures — the durable series is the only evidence a NAV was
struck.


## BIND carried by the chair, 2026-08-27 (from run-builder-jan1) — FOR TOMORROW'S BATCH

Audit `_guard_approval` in `app/api/v1/fund.py` for a duplication in the
LOOSENING direction: the chair-identity set is named in APPROVAL_ALLOWLIST
and then re-spelled inline at two more sites (~:5548, :5561). Adding a
fourth chair identity to the allowlist alone would let it approve WITHOUT
quoting the CEO's instruction verbatim, and record without the
[instruction] bracket. Also check `deskcard._VIA_RE`: it admits
`ceo-via-cto`, an identity the guard refuses — a third spelling of the
channel family that could label a row "chair-adjudicated" which no chair
could have approved.


## BIND carried by the chair, 2026-08-27 evening (from run-adversary-batchA) — joins tomorrow's batch

The prod-gate precondition book_venue_reconciled is gaining an evaluator
whose companion number can be moved by the FEE LEDGER, not only by marks
(demonstrated: $9.96 accrued = a 0.50% breach on a synced book;
FEE_CRYSTALLISED has zero production emitters so accrual is monotone).
When you audit the envelope: which of its checks read a quantity carrying
a liability with no venue counterpart? Ask the fee-term question across
every check.
