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

> **REVISION r2 — READ SECTION 9 BEFORE SECTIONS 3, 5 AND 6.** The draft this
> memo described (`v5-draft-2026-08-27`) was **KILLED by the adversary**
> (run-adversary-night2) on two structural grounds, with four residuals filed
> alongside. The kill was accepted and the draft rewritten as
> `v5-draft-2026-08-27r2` (builder, dispatch MACH1, against live head
> `3fe23b41`).
>
> **Sections 1–8 below are r1's text and are preserved unamended**, per the
> clean-field rule's second guard rail: the contaminated version is annotated,
> never erased, so a reader can see what was believed and what it cost.
> **Section 9 carries every correction**, and where the two disagree section 9
> wins. Specifically: r1's check list in §3 is incomplete (r2 has 29 checks,
> not 23), r1's constant table in §5 is missing two, and one item in r1's gap
> list in §6 turned out to be a defect rather than a gap.

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

---

## 9. REVISION r2 — the kill, and what it changed

*(builder, dispatch MACH1, 2026-08-27, against live head `3fe23b41`. Everything
above this line is r1's text, preserved. Where the two disagree, this wins.)*

**Verdict on r1: KILLED, and the kill was right.** Two structural grounds and
four residuals. Both grounds were demonstrated by running probes against the
shipped module, not by reading it — the probes are kept at
`scratchpad/advn2/p1_short.py`, `p3_inflight.py`, `p4_bestcase.py`,
`p5_grid.py`, `p6_venue.py`, and they are now this design's acceptance tests.

### 9.1 KILL 1 — every bound read the FILLED book

r1's bounds were all computed from `book_qty_signed`, `strategy_qty_signed`,
`gross_exposure_usd` and `strategy_exposure_usd`. An order this envelope
approved forty milliseconds earlier is in **neither** ledger: nothing has
filled, so the fund's fold does not carry it, and the broker holds no unfilled
order, so the venue snapshot does not either. That invisibility **is** the
defect, and it defeats every check at once.

Measured on r1 at the fund's own NAV ($1,885.74) and an $80 mark, five signals
in one tick, each order 14.9% of NAV — one tick under the 15% per-order cap:

| signal | r1 verdict | position the fills would produce |
|---|---|---|
| 1 | approve | 14.9% of NAV |
| 2 | approve | **29.8%** — outside the 20% per-name ceiling |
| 3 | approve | 44.7% |
| 4 | approve | 59.6% |
| 5 | approve | **74.5%** against a 20% ceiling |

Every check green, every time, because the concentration bound measured a book
that had not moved. The daily cap is the only thing that eventually fires, and
the adversary's own best-case reading of it (`p4`) shows it firing at **order
3** — after the per-name ceiling has already been broken by 9.8 points.

**THE FIX IS A QUANTITY, AND THE QUANTITY IS SPECIFIED HERE AS A CONTRACT.**

1. **DEFINITION.** An order is IN FLIGHT when this envelope APPROVED it and the
   event log carries no TERMINAL event for it — no fill, no cancel, no
   rejection, no failure.
2. **EVENT SOURCES.** The set opens on the envelope's own approval record and
   closes on any terminal event for the same `order_id`. It must be built from
   the ORDER AGGREGATE, never from a position fold: a fold cannot represent an
   order that has not moved anything.
3. **SHAPE.** `context["pending_approved"]` is a list of rows or `None`.
   `None` = the ledger could not be read, and refuses. `[]` = the ledger was
   read and nothing is in flight, a measured zero. Each row:
   `{order_id, strategy_id, symbol, side, qty, mark_usd, age_minutes}`.
   **Any row that cannot be parsed makes the WHOLE fold unreadable** — a
   partial sum over in-flight exposure looks like a measurement and bounds
   nothing.
4. **FAILURE DIRECTIONS.** Unreadable refuses (`in_flight_ledger_readable`). A
   row older than `MAX_PENDING_AGE_MINUTES` refuses (`in_flight_orders_fresh`)
   — not because counting it is dangerous, but because a terminal event that
   has not arrived in thirty minutes means the ledger's *other* direction is
   also suspect, and the direction we cannot see from here is the permissive
   one: an in-flight order it has lost entirely. An unreadable AGE is stale and
   does **not** make the fold unreadable, because the exposure arithmetic does
   not need it.
5. **WHERE IT IS ADDED, AND THE ONE PLACE IT IS NOT.** It enters the three
   exposure bounds and the new reduce-only bound. It is **EXCLUDED by
   construction from `book_venue_in_sync`.** That check requires book == venue
   and the broker cannot hold an unfilled order, so folding in-flight into the
   book side — the obvious repair — makes every pending order look like a
   reconciliation break. The adversary probed exactly that (`p4` part B) and it
   refuses every order in the class. **A control that refuses everything is not
   a control.**
6. **WORST CASE, NOT NET.** For shortness the worst corner is *every in-flight
   BUY fails and every in-flight SELL fills*; for concentration it is whichever
   of {none, buys only, sells only, all} gives the largest magnitude. Netting a
   pending buy against a pending sell would let a cancellable order pay for a
   real one.
7. **WHAT IT DOES NOT BOUND.** In-flight orders in OTHER symbols are summed at
   their absolute notional rather than netted against those symbols' books,
   because the fold is not given those books. That **over-states** gross, which
   is the safe direction, and it is named so the number is never mistaken for a
   measurement of gross.

**Re-measured on r2**, same probe, same numbers (`scratchpad/probes/p3b_inflight.py`):
order 1 approves at 14.9%; **order 2 refuses on
`post_fill_name_within_concentration` at 29.80% against a 20.00% ceiling** —
before the position exists, rather than after.

**THE RESIDUAL, MEASURED RATHER THAN ASSERTED.** `[]` is a *claim* that nothing
is in flight. If the gatherer is wrong and reports `[]` while orders really are
in flight, r2 falls back to exactly r1's behaviour and the daily cap is again
the only bound standing. **The in-flight bound is exactly as good as the fold
behind it** — which is why item 2 above specifies the event sources rather than
leaving them to the gatherer, and why the gap list in §9.5 now names that fold
as a blocker rather than a nicety.

### 9.2 KILL 2 — a zero-crossing sell was auto-approvable

r1 approved a **naked short of 14.9% of NAV from a flat book with all 23 checks
green** (`p1`). The reason it is fatal rather than untidy: `exitrule.py:326` can
only raise a **SELL**, so a short position's own pre-committed exit *deepens*
it. r1's check 15 — the one that exists to guarantee a way out — was satisfied
by a rule that makes the trade worse.

r2 adds `post_fill_position_not_short`: **sells are reduce-only in this class.**
The bound is on the worst in-flight corner, so two sells that each take a long
to exactly zero are caught as the pair that crosses it. Three refusing cases get
three sentences, because they are three different mistakes: crossing zero from a
long, opening a short from a flat book, and deepening a position already short.
The last is named separately because a rule written as *"sign(book) must not
flip"* would let it through, and an un-exitable position getting larger is the
worst of the three.

The **cover path** — letting the exit machinery BUY to close a short — is
control-layer work and is deliberately not proposed here. Until it exists, a
position this envelope opens must be one the fund's own machinery can close.

### 9.3 The four residuals

| residual | what r1 did | what it cost | r2 |
|---|---|---|---|
| ISO timestamps compared as raw strings in `exit_committed_for_entry` | `set_at < raised` on text | a **false ACCEPT**: `"…T05:00:00+00:00" < "…T06:00:00+05:00"` is True as text and False as time (05:00Z is four hours *after* 01:00Z), so an exit written four hours after the signal counted as pre-commitment | a new strict `_iso_lt` on parsed instants; a naive instant beside an aware one raises inside `datetime` and lands on refuse |
| `mark_corroborated` unsigned | `move <= 30` | a mark reported at **−75.9%** of the struck mark passed — the GLD phantom's shape, in the check written to catch it | `abs(move) <= 30`, both directions probed at the boundary |
| context values outside their declared unit | `_fraction`/`_pct` stated, never enforced | `nav_usd = 1e308` made every percentage vacuously tiny and the order approved; `float(True) == 1.0` made a boolean a full-gross throttle multiplier and a 100%-of-NAV position limit | a new `_number(v, lo=, hi=)` that rejects `bool` and enforces the range, an aggregate `context_values_in_range` check naming every offending field, and the value ALSO becoming absent so its own check refuses independently |
| seventeen inputs made `evaluate` RAISE | `.get` on a non-dict `strategy` (9 cells), `for`/`len` on a non-iterable `live_sessions` (8 cells) | an exception aborts the tick and leaves every remaining order unevaluated — a fund-wide outage raised by one malformed field | each input normalised to its own type, plus an outer guard recording `evaluate_completed: false` with the exception named. **Refusing loudly, never swallowing.** Re-measured: **0 raises over 587 grid cells** |

**A fifth defect was found while writing r2's own tests, not by the review: a
NEGATIVE signal age passed `age <= MAX_SIGNAL_AGE_MINUTES`.** A signal from the
future is a clock skew or a gatherer subtracting the wrong way round, and it
bought an arbitrarily stale signal a pass on the one check that exists to stop
that. `signal_age_minutes` is now read with `lo=0.0`.

### 9.4 One input DELETED, and two constants added

**`notional_usd` is no longer an input.** r1 accepted it *beside* the `qty` and
`order_mark_usd` that determine it — two ideas of one number, in a module whose
own header warns against exactly that — and approved an order declaring a
notional of **zero** for 1.18 shares at $80. r2 computes it as `|qty| × mark`. A
gatherer that still supplies the key is ignored, which is the safe direction: a
computed figure cannot be talked down.

This assumes **no contract multiplier**, which is true for equities and ETFs and
false for futures and options. Admitting one of those is a versioned change that
must add the multiplier to the contract first. Stated here rather than
discovered later.

Two constants join §5's table. Neither is decided here:

| constant | proposed | reasoning | attack it on |
|---|---|---|---|
| `MAX_PENDING_AGE_MINUTES` | 30 min | settlement polls every `SETTLE_INTERVAL_SECONDS` (30s deployed), so a submitted order's terminal event should arrive within one or two polls; thirty minutes is sixty poll cycles. Older than that and the in-flight set we are bounding exposure with is not the in-flight set that exists | is refusing right, or should a stale row merely be counted? The cost of refusing is a human click; the cost of counting is trusting a ledger that has stopped agreeing with the venue |
| `MAX_PLAUSIBLE_NAV_USD` | $1e12 | **a corruption detector, not a risk limit** — NAV is the denominator of every cap, so an absurd NAV fails OPEN, and r1 approved on `1e308`. There is no principled ceiling on a fund's NAV; this is far above anything reachable and exists only to separate a number from a corrupted field | it is arbitrary and says so. A fund that approaches it raises it as a versioned change and has larger questions that day |

### 9.5 The gap list, amended

§6's four unbuilt pieces stand, with two corrections:

- **Item 2 (the daily fold) was understated.** r1's memo listed it as a gap;
  the kill shows it is also the *only* bound that catches the stacking case,
  and it catches it **after** the per-name ceiling is already broken. It is
  now joined by a fifth blocker:
- **NEW BLOCKER — the in-flight fold.** Nothing computes `pending_approved`
  today. Its contract is §9.1 items 1–3. Without it every order in this class
  refuses on `in_flight_ledger_readable`, which is the correct fail-closed
  behaviour and is also a feature that does nothing. **It must be built before
  the arming flag is ever set, not after.**

### 9.6 Verification, stated with its domain

| probe | r1 | r2 |
|---|---|---|
| `p1` naked short | approve, 23/23 green | **refuse**, on `post_fill_position_not_short`, sentence naming the settled book |
| `p3` five stacking signals | 5 approvals, 74.5% of NAV in one name | see `p3b`: order 1 approves, order 2 refuses at 29.80% |
| `p5` direction grid | 470 cells: 59 approving (18 no-op + **41 real fail-open**), **17 raises** | see `p5b`: 587 cells, 19 no-op, **3 approving-after-change, all three hand-verified as intended** (a 1% mark move either way; a legitimate small in-flight order; the deliberate case-folding of the venue kind), **0 raises** |
| `p6` venue table | airtight | **unchanged and airtight**: only the paper KIND value passes, and only with `real_money=False` |

**A NOTE ON THE PROBES, because the number in the dispatch brief was wrong and
the correction matters more than the count.** The brief described p5's r1 result
as *zero fail-open*. Measured on the shipped r1 it is **59 approving cells of
470**, of which 18 are no-ops (the mutated value equals the base value, so
nothing was mutated) and **41 are real**. A count that mixes the two is not a
number, which is why `p5b` reports three figures rather than one.

`p1`, `p3`, `p4`, `p5` and `p6` are all still run **verbatim** against r2. On
r2 they refuse or assert out at their first line, because r2 adds a required
input their fixtures predate — which is the fix itself. The `…b` twins carry
the same experiment on a base that satisfies the new contract, because a probe
whose base cannot pass measures nothing: `p6` on r1's fixture would report
all-False for every venue and could no longer tell an airtight venue check from
an envelope that refuses everything.

### 9.7 What would change r2's mind

*(Added to §8, not replacing it.)*

- **If the in-flight fold cannot be built to distinguish `unreadable` from
  `empty`, v5 does not proceed.** The whole of §9.1 rests on that distinction
  and a fold that cannot make it hands the envelope a lie in the permissive
  direction.
- **If reduce-only proves to block a class of entry the fund actually wants**
  (a deliberate short sleeve), that is an argument for the cover path in the
  exit machinery — a control-layer change with its own review — and never an
  argument for relaxing this check.
