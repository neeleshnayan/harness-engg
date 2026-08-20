# INCIDENT — the fund's first auto-approval fired on a fabricated price

**2026-08-20, 08:01:25–08:01:27 UTC. Filed by the CTO the same morning.
Status: root cause fixed and pinned by regression tests (commit referenced
below); riskofficer audit dispatched; trading halt left in place for the CEO's
manual resume, by design.**

## What happened, second by second (all from the event log)

| t (UTC) | event | detail |
|---|---|---|
| 08:01:25 | `RiskAlarmRaised` | the risk monitor read GLD's mark as $100.00 |
| 08:01:26 | `OrderProposed` (actor worker) | SELL 0.424471 GLD, rationale `PRE-COMMITTED EXIT FIRED. down -75.14%, past the 25.00% loss exit committed to on 2026-08-17` |
| 08:01:26 | `ExitRuleTriggered` | the machinery-test 25% loss rule — the rule the PM's R4 had flagged as an armed hazard **hours earlier** |
| 08:01:27 | `OrderFilled` (actor system) | avg_price **100.0** — the auto-policy's **first live fire ever**: exit-rule SELL, fresh, liveness proven, paper venue — every envelope check passed |
| ~08:01 | daily-loss halt | realized ledger loss **−$133.21** → daily NAV loss 6.62% > 4.00% limit → `TRADING HALTED` (buys blocked, sells allowed, resume manual) |

GLD's true price at the time: ~$413.84 (verified live after the fact;
prev close $398.55). Entry was $402.18; a mark of $100.00 reads as −75.14%.

## Root cause

`app/fund/connectors/paper.py` carried `_DEFAULT_PRICE = 100.0`: when the live
pricer missed (a transient feed failure — both Yahoo and stooq briefly
unavailable or unparsed) and the symbol was not in the seed dict, `price()`
**returned a fabricated $100.00 instead of an absence**. That connector method
is the pricer for the entire spine (`_connector.price` feeds NavService, the
risk monitor, attribution, postmortem). GLD is not seeded. One transient miss
therefore became a real-looking mark, and everything downstream behaved
correctly on a lie:

- the risk monitor computed −75.14% honestly from the mark it was given;
- the exit rule fired honestly per its own arithmetic;
- the auto-policy approved honestly inside its envelope (side=sell,
  exit-provenance marker, not halted, liveness green, fresh);
- the paper venue filled at the same fabricated quote.

This violated the fund's FIRST non-negotiable — *"never fabricate or hardcode
a financial number... an absent number is reported absent"* — at the exact
point every mark in the system is born. The constant predates the firm's
discipline (phase-1 scaffolding, "Phase 2 replaces this with a real oracle").

## What worked

- **The daily-loss halt caught it within seconds** and blocked further buys.
  Deterministic, no human, no agent. This is the real-time risk layer doing
  its job.
- **The PM predicted the vehicle.** R4 (same morning, before the fire):
  *"Retire the machinery-test GLD loss_pct 25% rule... It is the only live
  exit rule on the book that nobody chose as policy. Do not leave it armed."*
  A confirmed near-miss prediction — the team metric, scored in advance.
- **The trace/attribution layer made diagnosis minutes, not hours**: the
  event log carried the whole chain with actors and the exit marker.
- **The CTO's stale-ticket guard**: the pending T6 (CEO-accepted GLD close)
  would have SOLD SHORT after the phantom fill removed the position; declined
  before it could be clicked.

## What failed, ranked by money

1. **The fabricated default price** (root cause, fixed — see below).
2. **A test artifact was live portfolio policy** (the machinery-test rule;
   PM's R4 already open when it fired). Ruled on by the CEO via R4.
3. **No mark-sanity layer**: a mark implying a −75% single-tick move on a
   +2.9% position was consumed without a plausibility check. Follow-up below.

## The fix (this commit)

- `_DEFAULT_PRICE` deleted. `price()` now raises `PriceUnavailable(ValueError)`
  when the live pricer misses and no explicitly seeded price exists. A seed is
  a chosen number; a catch-all default was a fabricated one.
- `execute()` on an unpriceable symbol **fails the order and leaves the book
  untouched** (FAILED state with the reason on the record, idempotent like any
  fill). An order must never fill at a number nobody quoted.
- Consumers verified for the new absence: the risk monitor already dropped
  unpriceable symbols into `unpriced` (its exception guard now actually
  fires), which makes exit rules on them **unevaluable — reported, never
  fired**; correlation skips them; `StrategyAttribution.with_values` now
  carries `unmarked_symbols` instead of crashing. NavService deliberately
  RAISES: a fund that cannot price a position it holds must alarm loudly, not
  serve a made-up NAV.
- Regression tests: `tests/test_paper_pricing.py` (5 tests, incl. "a failed
  order must not move the book"). Full suite 936 passed.

## Deliberately NOT done

- **The ledger is not rewritten.** The $133.21 loss is a fact of the book —
  the paper fund paid real (paper) money to learn this. NAV history keeps it.
- **The halt is not resumed.** Resume is the CEO's manual action, by design.
- **No compensation entry, no threshold change.** The 4% daily-loss limit
  fired correctly and stays.

## Follow-ups (owners named)

1. **Riskofficer audit** of the auto-approval (dispatched 2026-08-20) — its
   founding mandate: audit every auto-approval after the fact. This is the
   first.
2. **Mark-sanity layer (CTO, design next)**: quarantine any mark implying a
   single-tick move beyond a bound (e.g. >N sigma / >X%) against the last
   known good mark; quarantined symbols → positions flagged stale, exits
   unevaluable, alarm raised. Versioned change with its own written reason.
3. **riskanalytics.py:116 marks an unpriceable symbol at 0.0** in shock
   analytics — the same absence-as-zero family, lower stakes (nothing fires
   on it). Fix with the mark-sanity work.
4. **R4** (retire the machinery-test rule) — the CEO's open decision; the
   rule's GLD position is gone, so its remaining risk is re-acquisition.
