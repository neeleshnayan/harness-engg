# Autopolicy v5 — the engine-entry envelope (DESIGN, NOT ADOPTED)

**Status: DRAFT. Nothing here is in force.** `AUTOPOLICY_VERSION` is `"v4"` and
`app/fund/autopolicy.py` is untouched by the diff that carries this memo. The
draft implementation lives at `app/fund/autopolicy_v5_draft.py`; nothing in
`app/` or `scripts/` imports it, and a test asserts that by walking the source
tree (`tests/test_autopolicy_v5_draft.py::test_nothing_in_the_repo_imports_the_draft`).

**The path to adoption is unchanged and is not negotiable here:** adversary
blind → riskofficer → the CEO's click on the version. This memo is the artifact
the first two attack. Direction, stated in the first line because it decides the
routing: **v5 WIDENS the auto-approval envelope** — it admits a class of order
v4 refuses (entries) — and is therefore a loosening in the constitution's sense,
whatever tightenings it also contains.

Author: builder, dispatch ENG3. Written against live head `ef4d610f`.

---

## 1. Why v5 exists

v4 admits exactly one thing: an **exit-rule-triggered SELL**, and every safety
argument it makes rests on that. `reduces_exposure` is the spine of the module,
and it is only meaningful about an order that closes something.

That was correct for the phase it was written in. It is now the binding
constraint on the CEO's decision of 2026-08-26 — *"funds dont manually approve
each trade… I cant genuinely be in the critical path"* — because **an engine
whose exits are automatic and whose entries are manual has not left the critical
path; it has moved the human to the more consequential half.** A live LEAN
session raises a signal, the signal becomes a proposal, and the proposal waits.
On 2026-08-16 exactly that happened and the proposal sat until it was declined
by a test harness (seq 157/158, verified by the chair against Postgres).

So v5 proposes a **second admission class**, beside v4's and not replacing it:

> An **ENTRY** raised by a **LIVE ENGINE SESSION** belonging to a **DEPLOYED
> strategy**, inside an envelope that bounds what one bad day can cost.

An order is auto-approvable if it passes v4's exit envelope **or** v5's
engine-entry envelope. v4's checks are unchanged, and any order v4 approves
today it still approves.

## 2. What changed in the world that makes this proposable now

v5 leans on one thing that did not exist a day ago: **the durable session
registry** (`app/fund/leansessions.py`, `fund_lean_sessions`, this same
dispatch). Before it, "this order came from a live engine" was unprovable —
`LeanRunner._live` died with the spine, so after any restart the fund could not
say whether any engine was running, and `engineledger.ORPHAN_CHECK` published
that gap as `False`.

That matters because **the whole forgeability problem of v5 is the same problem
v4 already solved once and named**: `EXIT_MARKER` is a string anyone can type,
and only the `EXIT_RULE_TRIGGERED` *event* is provenance. The equivalent here is
the actor prefix `external:`, which anything holding the signal token can write.
`signal_from_live_session` is v5's answer, and it is only worth anything because
the session table now survives.

## 3. The checks

Every check **fails closed**. Every failure sends the order to the CEO queue —
the exception path is the *existing* path, so v5's failure mode is exactly
today's behaviour. Evaluation is **non-short-circuiting**: every check runs and
is recorded even after one has failed, because that is what made v4's first
audit possible from the event log alone.

| # | check | what it reads | fails when | evidence the reader works |
|---|---|---|---|---|
| 1 | `engine_entries_armed` | the arming flag, from config | anything but `True` | **UNMEASURED** — the flag does not exist yet; §6 |
| 2a | `venue_kind_is_permitted` | the resolved `mode.VenueKind` **value**, never `order["venue"]` and never the connector name | kind ≠ `alpaca_paper` | `mode.py:161` (`ModeSpec.venue_kind`); the *resolution helper* v5 needs is **UNBUILT** |
| 2b | `venue_is_not_real_money` | `ModeSpec.real_money` | anything but an explicit `False` | `mode.py:181`; measured live 2026-08-27 — see §4(d) |
| 2c | `strategy_matches_the_order` | the strategy row's id vs `order["strategy_id"]` | either absent, or they differ | new; bounds a gatherer that fetches the wrong row |
| 3 | `strategy_deployed` | `StrategyRegistry.get()` → `state`, `archived` | not `deployed`, or archived, or absent | `strategies.py:235-305` (`StrategyRegistry._build`), folded from `STRATEGY_STATE_CHANGED`; read live 2026-08-27 |
| 4 | `symbol_in_scoped_assets` | `strategy["assets"]` (`STRATEGY_ASSETS_SET`) | symbol outside the scope, **or the scope is empty** | `strategies.py:275-276`. **MEASURED HAZARD**: live registry holds GLD with `assets: []` and HYG with `assets: ["HYG"]` (ENG2) — an empty scope must refuse, not permit |
| 5 | `signal_from_live_session` | `fund_lean_sessions` via `LeanRunner.live_sessions()` | no live session for this strategy was running when the signal was raised | new this dispatch; `tests/test_leansession_registry.py` (33 tests, real Postgres) |
| 6 | `signal_fresh` | the proposal's age | > 5 min, or unknown | `pipeline` already computes `age_minutes` for v4 |
| 7 | `side_is_readable` | `order.side`/`order.qty` | side ∉ {buy, sell}, or qty unreadable | `order_delta`, pinned against v4's by a shared table |
| 8 | `order_notional_within_cap` | notional, last struck NAV | > 15% of NAV, or NAV unreadable | `NavStruck` fold; v4 already uses it for `notional_pct_of_nav` |
| 9 | `daily_cumulative_within_cap` | today's auto-approved entry notional + this order | > 30% of NAV, **or the day could not be read** | **UNBUILT** — nothing today folds a per-UTC-day auto-approved total; §6 |
| 10 | `post_fill_name_within_concentration` | book qty, mark, `RiskLimits.max_position_pct` | post-fill position > 20% of NAV | `risk.py:53`; `riskmonitor` computes the same quantity live |
| 11 | `post_fill_strategy_within_allocation` | strategy qty/exposure, `allocation_pct` | post-fill strategy gross > its allocation | `StrategyAttribution.positions_by_strategy` (ENG1) |
| 12 | `post_fill_gross_within_throttle` | gross, `mandate_gross_fraction`, `throttle.target_gross` | over, **or the regime is unmeasurable** | `throttle.py:71-113`; the unmeasurable behaviour is **pinned by a test**, see §4 |
| 13 | `mark_corroborated` | `marksanity.check(store, order_id)` | > 30% from the last struck mark, or uncomparable | `marksanity.py:390`; this is v4's R1 unchanged |
| 14 | `book_venue_in_sync` | fund book vs `connector.positions()` | drift > 1e-6, or venue unreadable | v4's own check, same tolerance as `reconcile._TOL` |
| 15 | `exit_committed_for_entry` | `ExitRules.active(strategy_id)` | no LIVE rule for the symbol committed BEFORE this order | `exitrule.py:203`, `_rule_is_live` at `:417` |
| 16 | `not_halted` | `RiskControl.is_halted()` | halted | v4's, unchanged |
| 17 | `liveness_*` ×4 | `heartbeat.status(job)` | `ok` is not exactly `True` | `heartbeat.py:90-115`; `ok: None` = unobserved and does **not** pass |
| 18 | `risk_monitor_fresh` | the risk monitor's heartbeat age | > 300s, or unreadable | as above |

**Twenty checks plus four `liveness_*` rows** — the count is asserted in
`tests/test_autopolicy_v5_draft.py::test_the_check_list_is_complete_and_not_short_circuited`
rather than stated here, because a number in a memo goes stale and an assertion
does not.

### Failure direction, in one line
Every check above answers **False on absence**. There is no branch in the draft
where an unreadable input produces an approval, and the tests assert the
unreadable case separately from the over-limit case for the five that matter
most — because *"we could not measure it"* and *"it was too big"* have different
fixes and the riskofficer reads the detail string, not the boolean.

## 4. The four places this is easiest to get backwards

**(a) The unmeasurable regime points the permissive way.**
`throttle.target_gross` returns `gross_multiplier: 1.0` when NEITHER signal is
measurable. That is correct for a module whose doctrine is *reduction only* —
and reading it here would let an unreadable regime feed authorise **full gross,
unattended**. v5 refuses on `throttle_measurable is not True`. The cost is real
and is stated: **the auto-entry path dies whenever the regime feed is down**, and
a human clicks instead. The premise is pinned by a test against the real module
(`test_the_throttle_module_really_does_return_1_0_when_unmeasurable`), so if
`throttle` ever changes, the reason written into the draft cannot go stale
silently.

**(b) An empty asset scope is an unstated one, not an unlimited one.** Reading
`assets: []` as "no restriction" would give the LEAST-specified strategy the
WIDEST mandate. Measured, not hypothetical: GLD carries `assets: []` on the live
registry today.

**(c) An unreadable day is not an empty day.** A failed history query read as
"nothing approved yet today" lands on the single number that bounds worst-case
daily damage.

**(d) THE VENUE HAS THREE SPELLINGS AND ONE OF THEM DOES NOT DISCRIMINATE.**
Measured against the live spine (`GET /fund/mode`, 2026-08-27):

| mode | `venue_kind` | `venue_label` | `permitted_connectors` | `real_money` |
|---|---|---|---|---|
| `alpaca-paper` | `alpaca_paper` | `alpaca` | `["alpaca"]` | `false` |
| `alpaca-prod` | `alpaca_live` | `alpaca-live` | `["alpaca"]` | **`true`** |

**The paper account and the real-money account permit the SAME CONNECTOR**, and
`mode.py:167-170` already says so in its own words: *"`connector.name` is
'alpaca' for both"*. The first draft of this design used the string `"alpaca"` —
the connector name, and the paper mode's label — so a gatherer supplying either
one from `alpaca-prod` would have passed the venue check **with real money
behind it**. That is why check 2 is now two checks reading two different fields
of the mode spec: a gatherer that gets one wrong has to get the other wrong the
same way. It is the only place in this envelope with a deliberate second
opinion, and the reason is that it is the only boundary where being wrong costs
the CEO's money rather than a wasted click.

## 5. The numbers, and who owns them

**None of these is decided here.** Each is a threshold and every threshold is
the CEO's, in either direction. What the draft decides is *which quantity each
bounds and which way it fails*.

| constant | proposed | reasoning | attack it on |
|---|---|---|---|
| `MAX_ENGINE_ORDER_NOTIONAL_PCT` | 15% of NAV | set EQUAL to `RiskLimits.max_order_notional_pct`, so the machine's door is never wider than the human's | is parity right, or should the machine's door be narrower? |
| `MAX_ENGINE_DAILY_NOTIONAL_PCT` | **30% of NAV** | **this is the worst-case-daily-damage number.** Two full-size orders | the whole point of the memo. At $1,885 NAV that is ~$565/day of new exposure |
| `MAX_SIGNAL_AGE_MINUTES` | 5 min | tighter than v4's 10 because a refused ENTRY comes back next bar and a refused EXIT does not (v4's own corrected comment) | is 5 too tight for a daily-bar engine that posts once? |
| `MAX_MARK_MOVE_VS_STRIKE_PCT` | 30% | **the same value as v4's**, pinned by a test — two definitions of "the mark is sane" is the defect `marksanity` was written to name | inherited, not proposed |
| `MAX_RISK_MONITOR_AGE_SECONDS` | 300s | equal to the job's own declared budget today, but stated HERE so it does not silently inherit a budget that moves | |
| `REQUIRED_HEARTBEATS` | v4's three **+ `nav_strike`** | every v5 cap is a percent of NAV, so a stale NAV makes all of them percentages of a number nobody struck | **note for the riskofficer**: `BUDGETS_SECONDS["nav_strike"] = 5400` — passing means "within ninety minutes". Whether that is fresh enough for unattended execution is a judgement the draft does not make |

## 6. What does NOT exist yet — the honest gap list

The draft is a pure evaluator. Adoption needs **four things that are not built**,
and none of them is in this diff:

1. **The gatherer** (`context_for_v5`). v4's equivalent is one pass over the
   event log; v5's needs the session registry, the strategy registry, the
   throttle and a per-day fold. Its failure mode must be identical to v4's: any
   failure degrades to an ABSENT field, so it can only ever narrow.
2. **The daily auto-approved-notional fold.** Nothing computes it today. It must
   be a fold over the event log per UTC day and it must be able to say
   *unreadable* distinctly from *zero*.
3. **The arming flag and its control surface.** A flag with no way to flip it
   is not a kill switch. It must be readable per-order (so flipping reverts the
   book on the next tick, not the next deploy), and flipping it in either
   direction is a control-layer act with a recorded actor.
4. **The resolved-execution-venue helper.** It must return the `VenueKind`
   VALUE and the `real_money` flag from the ACTIVE `ModeSpec` — not
   `order["venue"]` (a client string; v4 measured exactly what happens when you
   trust it), not `connector.name` (identical for paper and live), and not the
   label. Two fields, from one read of one spec.

Two more that are policy rather than code:

5. **The riskofficer's post-audit hook.** v5 must write the full check list into
   the approval event payload exactly as v4 does, and an `AutopolicyDeclined`
   event on refusal (PM R41's pattern), so the daily digest can be a query and
   not an excavation. **Proposed digest shape**: per UTC day — orders evaluated,
   approved, declined; declines grouped by first failing check; total approved
   notional against the daily cap; the arming flag's state at the start and end
   of the day; and every `draft: true` evaluation (which must be zero).
6. **The kill-switch drill.** A control is not done until something calls it.
   Before adoption, the flag should be flipped once against a live session and
   the resulting decline observed in the log.

## 7. The residual this design does NOT close

**The signal token is a bearer credential.** Anything holding
`EXTERNAL_SIGNAL_TOKEN` can raise a signal that matches a genuinely live session,
and `signal_from_live_session` cannot distinguish that from the session itself.
What the check DOES close is the much larger hole of a signal with no live
session behind it at all — the 2026-08-16 case, and every case after a restart.

Closing the rest means **per-session tokens**: a token minted at `start_live`,
scoped to that session id, invalidated when the session ends. That is an
operational design rather than a policy check, it is not proposed here, and it
should be on the table before v5 governs anything larger than the paper venue.

Second residual, smaller: v5 bounds **notional and exposure**, not **loss**. A
30%-of-NAV day inside every check can still be a 30%-of-NAV day that goes wrong.
The drawdown kill switch is what bounds that, and it is unchanged.

## 8. What would change this design's mind

*(Recorded at proposal time, per the constitution's clause 4.)*

- Any auto-approved engine entry that the CEO would not have clicked, in the
  first month, reverts v5 to unarmed pending a written re-decision.
- Any evaluation recorded with `draft: true` on the live approval path revokes
  the draft entirely — it would mean this module became reachable without the
  chain.
- A measured false-refusal rate that keeps the engine's entries manual in
  practice (e.g. the regime feed being down more often than up) makes check 12's
  fail-closed direction a decision to revisit **with data**, not an argument to
  have now.
