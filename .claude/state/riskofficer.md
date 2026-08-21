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
