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
