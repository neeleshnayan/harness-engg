# AUDIT — auto-policy v1, first live fire (GLD, seq 256)

**Author: riskofficer agent, first dispatch (1b9183da / trace-incident-gld-phantom),
2026-08-20. Filed verbatim by the CTO at resolve. Companion to
docs/INCIDENT_GLD_PHANTOM_PRICE_2026-08-20.md (whose §2 corrections come from
this audit). CTO verification note at the bottom.**

Population audited: **the complete log**, 295 events. `OrderApproved` by actor: `rushi` ×16, `auto-policy-v1` ×1. Exactly one auto-approval exists in fund history and it is fully covered here.

## 1. The approval against its recorded evaluation

**Event 256** — `event_id a6ca5495-409b-4c6a-b97a-ddbbb6080fb0`, `2026-08-20T08:01:27.013836Z`, aggregate `2ec1ec3f-ddda-48ac-8511-9c19fb87d59b`, actor `auto-policy-v1`. `policy_evaluation` **is present** and complete: 7 checks, all `ok:true`, `policy_version:"v1"`. No missing-evaluation finding. Code version `AUTOPOLICY_VERSION = "v1"` (`app/fund/autopolicy.py:55`) — **no version drift**.

Check-by-check, against the world at 08:01:27:

| recorded check | verdict | evidence |
|---|---|---|
| `side_is_sell` | **TRUE and true** | seq 254 payload `"side":"sell"`; seq 258 fill `"side":"sell"` |
| `exit_rule_provenance` | **TRUE and true** | seq 255 `ExitRuleTriggered`, actor `worker`, same `order_id`. Marker genuine, not forged. Across all 295 events the marker appears twice (seq 171, 254), both actor `worker`, both with a matching `ExitRuleTriggered`. |
| `not_halted` | **TRUE and true** | first `TradingHalted` is seq 265 at `08:16:08.932374Z` — 14m41s after the fill |
| `liveness_*` ×3 | **TRUE and true, and irrelevant** | beats are written only after a non-raising tick; `ok=True` honestly meant "the loop ran", not "its inputs were real" |
| `freshness` | **TRUE and true** | `age_minutes` server-computed from ORDER_PROPOSED ts; 0.26s. Not spoofable |

**Verdict: the policy executed correctly and every check was factually true.**
The failure is not in `evaluate()`. v1's seven checks span provenance, state and
time, and **not one of them touches the number the decision was made on**.

## 2. Findings, ranked by money

### F1 — CRITICAL, LIVE AT AUDIT TIME: the root-cause fix was incomplete. `_SEED_PRICES` still fabricated marks, in this very incident.

`fa6b877` deleted `_DEFAULT_PRICE = 100.0` but kept the seed table
(`paper.py:35-42`, returned at `:85-87`). The same feed miss that fabricated
GLD **also fabricated SPY and NVDA in the same two ticks**. Proof, arithmetic
to 4 decimals, from cost bases and the alarm metrics on the log:

| seq | ts | symbol | alarm `metric` | cost basis | implied mark | source constant |
|---|---|---|---|---|---|---|
| 250 | 08:01:04 | SPY | 28.0742% | 778.58 | **559.9999** | `_SEED_PRICES["SPY"] = 560.0` |
| 253 | 08:01:25.781 | NVDA | 47.1505% | 227.06 | **120.0001** | `_SEED_PRICES["NVDA"] = 120.0` |
| 252 | 08:01:25.747 | GLD | 75.1355% | 402.18 | **100.0000** | `_DEFAULT_PRICE = 100.0` (deleted) |

Both cleared at 08:16:08 (seq 263, 264) when the feed recovered. True marks:
SPY 769.06, NVDA 217.56 — the seeds understated by **27.2%** and **44.8%**.
**GLD was not special. It was the only phantom-marked symbol that carried an
armed `loss_pct` rule.** Exposure if a rule were committed on either name:
SPY $34.61, NVDA $73.16 of NAV destroyed per fire, scaling with book size.
The docstring rationalizing the seeds ("a seed is a chosen number") is the
defect in one line — for a MARK that is a distinction without a difference.

### F2 — HIGH: the envelope's stated premise was FALSE for this order, and nothing checked it.

v1 believes it approves *"closes commanded by a stop the operator committed to
BEFORE the position existed"* (`autopolicy.py:34-36`). Measured: GLD position
filled **2026-08-14T13:30:03** (seq 76, basis 402.18, strategy `e54f40af…`);
the rule was set **2026-08-17T17:03:55** (seq 167, `machinery-test`, note "far
away") — **three days after the position existed, under a different
strategy_id**. The pre-commitment sentence in every fired exit's rationale is
unconditional boilerplate (`exitrule.py:307-311`); `set_at` is never compared
to the position's open date.

**F2b:** `check()` matches rules to positions by **symbol only**
(`exitrule.py:221, 269-270, 287`); the rule's `strategy_id` is never compared
to the position's. A `machinery-test` rule liquidated a position belonging to
`e54f40af…` — which is literally what happened.

### F3 — HIGH (standing v1 concern, now demonstrated): the marker is forgeable; the propose endpoint is unauthenticated free text.

`rationale` and `actor` are unconstrained client strings
(`app/schemas/fund.py:12,16`) through `POST /fund/orders/propose` (no auth
dependency; CORS only). Demonstrated offline against the real `evaluate()`:
two forged orders (no exit rule anywhere; `qty 999`; marker as typed text, one
buried mid-sentence) — **both `approve = True`**. Honest bound: the risk gate
caps a forged sell at ~15% NAV/order, ~20% NAV/name aggregate (~$375 today).
The non-forgeable corroboration exists and is unused: `EXIT_RULE_TRIGGERED`
is written only by `ExitRules.enforce()`; no endpoint appends it.

### F4 — MEDIUM: the halt is post-hoc and cannot gate the auto-policy; the incident doc overstated it.

Fill seq 258 `08:01:27.147Z`; first `TradingHalted` seq 265 `08:16:08.932Z` —
**14m41s**, not "seconds". Structurally, the loss that trips the daily-loss
halt is realized by the fill the halt is imagined to prevent; `not_halted`
protects the second bad order, never the first. `approve_order` re-checks only
staleness at execute time. Seq 281 `TradingResumed` (rushi 08:33:34) → seq 282
re-halt 8.6s later: correct, and the auto-policy was armed for those 8.6s.
WHY 14m41s across ~29 monitor ticks is an open measurement, not a claim.

### F5 — MEDIUM: `freshness` measures the proposal's age, never the mark's age or validity. `MAX_AGE_MINUTES = 10.0` was satisfied in 0.26 seconds. Every v1 check answered a question about the order; none answered a question about the price.

### F6 — LOW: the incident doc's −$133.21 is **NAV destroyed vs the true mark** (0.424471 × (413.84−100.00)); realized-vs-cost-basis is −$128.28. Reconciles exactly: 2011.81 × 6.6214% = 133.21; 2011.81 − 133.21 = 1878.60 = live NAV. Right number, wrong label.

## 3. Envelope v2 — recommendations, each falsifiable, none loosening

- **R1 — Corroborate the mark against the fund's own last NAV strike.** GLD's
  true mark (413.8399963378906) was in `NavStruck` seq 248, **29m46s before
  the phantom**. Quarantine any mark implying a single-tick move beyond a
  CEO-set bound vs the most recent strike mark; quarantined ⇒ exits
  unevaluable, no auto-approval. Deterministic; no second feed. Falsifier:
  replay seq 252 with the bound — the alarm must not raise; replay a genuine
  −30% gap-down — the exit must still fire for a human click.
- **R2 — Delete `_SEED_PRICES` for tradeable equities** (USD/USDC pegs stay);
  test seeds go in the fixture. *(Executed same day by the CTO with this audit
  as the written reason; suite 936 green.)*
- **R3 — Bind the marker to the trigger event**: `exit_trigger_linked` — an
  `EXIT_RULE_TRIGGERED` event must exist with this `order_id` and symbol,
  whose rule predates the order; fail closed on an unreadable log. Both
  demonstrated forgeries must flip to declined; seq 256's inputs still pass.
- **R4 — Test pre-commitment instead of asserting it**: `rule_predates_position`
  — the rule's `set_at` must precede the position's opening fill; fail closed
  when undeterminable. **Would have declined seq 256** on the doctrine v1
  already claims. Stop `exitrule.py` asserting it unconditionally; state the
  dates.
- **R5 — The rule's owner strategy must own the position** (or cap auto-qty at
  that strategy's holding).
- **R6 — do NOT blacklist `machinery-test` by string** — unversioned
  governance in a constant; R3+R4+R5 kill that rule on its merits.
- **R7 — versioned `MAX_AUTO_NOTIONAL_PCT`** in `evaluate()` — the machine's
  blast radius as an explicitly governed number, tighter than the human gate's
  15%.
- **R8 — correct the incident doc by new section** *(done — §2)*.

Explicitly NOT recommended: any LLM in the per-order path (permanently out);
relaxing any check; disabling the auto-policy (its checks were all true —
turning it off would restore the 46-hour-stale-INTC failure); a second price
feed as the primary fix; any ledger rewrite.

## 4. What worked — stated as plainly as the failures

Every check measured honestly; the full `policy_evaluation` on the approval
event made this audit possible from the log alone; liveness fails closed
(beats sit after the call inside the try); `/fund/liveness` still names
`nav_strike` unobserved rather than pretending; `age_minutes` is
server-derived; idempotency held; the CTO's stale-T6 guard prevented a
0.424471 GLD short; the PM predicted the firing vehicle hours in advance.

**The one-sentence lesson: v1 verified everything about the *order* and
nothing about the *number*. Deterministic, fail-closed, well-tested checks are
worth exactly as much as their inputs — and the fund had fabricated prices at
the point where every input is born.**

---

## CTO verification note (2026-08-20, at resolve)

Spot-checked before filing: (1) halt timing — `TradingHalted` seq 265 at
08:16:08.932Z vs fill 08:01:27.147Z, verified against the live event log,
14m41s confirmed (my incident doc was wrong and is corrected in its §2);
(2) F1 — the seeded-return path was in the shipped `paper.py` exactly as
cited, and the implied-mark arithmetic (basis × (1 − underwater%)) reproduces
SPY 560.00 / NVDA 120.00 to four decimals; equity seeds deleted same day,
suite 936 green, spine restarted. F3's forgery demonstration was offline
against `evaluate()` only — no order was proposed, nothing touched the log.
R1/R3/R4/R5/R7 are envelope v2 changes awaiting the CEO's decision as rows on
run-riskofficer-1.
