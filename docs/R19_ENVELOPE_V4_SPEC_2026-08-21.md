# R19 — auto-approval envelope v3 → v4: the exposure invariant, sign-agnostic

**Specified by the riskofficer on the co-CTO chair's dispatch, 2026-08-21
(UTC). Folds desk requests `86f7662e` (seq 726) and its CEO amendment
`e4416b34` (seq 774) into one document. Filed by the chair.**

**STATUS: SPECIFIED, NOT ADOPTED. A v3 → v4 envelope change is a versioned
change and the CEO's click adopts it. The seat specifies; it does not adopt.
This chair cannot adopt it either — autopolicy is Tier 3.**

---

## 1. The hazard, re-verified first-hand

The seat re-read the live Alpaca account and the event-folded book rather than
taking the COO's table:

| Symbol | Book | Broker | Exit sells | Mark | Short opened |
|---|---|---|---|---|---|
| TLT | 3.019871 | **0** | 3.019871 | 82.045 | $247.77 |
| DBC | 8.122157 | **0** | 8.122157 | 31.25 | $253.82 |
| DBA | 5.314306 | **0** | 5.314306 | 28.32 | $150.50 |
| SPY | 0.346119 | 0.217757 | 0.346119 | 765.55 | $98.27 |
| | | | | | **$750.36 = 39.79% of NAV** |

Corroborated at `ReconciliationMismatch` seq **798–807**. The date is real:
`ExitRuleSet` seq **178** (TLT) and **181** (DBC), `kind: time`,
`on_date: 2026-09-08`, committed 2026-08-18.

**v3 approves all four today, 12 checks out of 12, zero failures.** The seat
rebuilt the exact context `context_for` would gather and ran
`autopolicy.evaluate()`. Every check v3 makes is factually true.

> **The envelope is not malfunctioning — it is answering a question that does
> not determine the outcome.** It checks our own books and never asks the
> broker what it holds.

## 2. Why this now reaches a real venue

`.env` flipped `USE_FAKE_FIRESTORE 1 → 0` on 2026-08-21. `_mock_mode()`
(`fund.py:128-129`) reads that same variable, and the connector ternary
(`fund.py:151-163`) therefore selects `AlpacaConnector`. Confirmed live:
`get_all_positions()` returned six real positions, and `reconcile.run()` only
writes mismatches when `account_info().configured` is true
(`reconcile.py:107-110`), which `PaperConnector` never returns.

**One environment variable named for the ledger silently moved order routing** —
the exact conflation `_real_broker()`'s own docstring (`fund.py:132-140`) says
it exists to prevent. Filed separately as `b72847bc`.

## 3. Two objects wear the word "venue", and only one is forgeable

- **`order["venue"]`** — a client string on the proposal. `exitrule.py:301`
  **hardcodes `venue="paper"`** on every exit it raises, whatever connector
  will execute it. A `venue == "paper"` check would have passed on the exact
  orders that go to Alpaca. **Never add one.**
- **`connector.positions()`** — the broker's own answer over an authenticated
  round trip, not supplied by the proposer. Corroboration in the same sense R1
  already established for marks.

R19 reads the second and never the first.

## 4. The invariant

> **An exit must REDUCE exposure and must never cross zero into a position in
> the opposite direction.**

With `pre` the signed position and `delta = +qty` buy / `−qty` sell:

```
P(pre, delta)  ≡  (pre * delta) < -EPS          # opposite direction, pre ≠ 0
              AND  abs(delta) <= abs(pre) + EPS  # never crosses zero
EPS = 1e-9   (matches autopolicy.py:219)
```

`pre * delta < -EPS` does the sign work *and* kills the flat case for free — a
flat ledger yields `0`, which fails. **That single conjunct is what refuses
today's TLT.**

**One predicate, three ledgers**, in the order a human would ask:

| Ledger | Check | Source |
|---|---|---|
| the rule's own strategy | `rule_owner_holds_position` (v3's R5, **made sign-aware**) | fills folded by `strategy_id` |
| the fund's book | `exit_reduces_exposure` (**new**) | fills folded fund-wide |
| the venue | `venue_holds_position` (**new**) | `connector.positions()` |
| the two against each other | `book_venue_in_sync` (**new**) | both |

## 5. The specification

**New constant**: `MAX_POSITION_DRIFT_QTY = 1e-6`, set **equal to the
reconciler's own `_TOL`** (`reconcile.py:20`) because two definitions of "in
sync" is the second-opinion defect `marksanity.py:12` already names.

**New context fields, all fail-closed on absence**: `book_qty_signed` (already
computed as `qty_running` at `autopolicy.py:311-315` and thrown away — expose
it, no new pass over the log); `venue_readable`; `venue_qty_signed` (**`0.0`
when the list was read and the symbol is absent; `None` when it could not be
read** — both connectors omit flat symbols). And **drop the `max(0.0, …)`
clamp at `autopolicy.py:330-331`** so R5 carries the sign.

**The three checks** sit after `rule_owner_holds_position` (`:223`) and before
`notional_within_cap` (`:226`). Non-short-circuiting is preserved — every check
is still evaluated and recorded even when an earlier one fails, which is what
made the first audit possible from the log alone.

`venue_holds_position` has **three distinct outcomes with three distinct detail
strings**, because *"we could not look"* and *"we looked and it is zero"* have
different fixes:

```
venue_readable False   -> False, "the venue's positions could not be read —
                          an unmeasurable position is not a zero position"
venue_qty_signed 0.0   -> False, "the venue holds ZERO {symbol}; this SELL
                          would open a short of {qty}"
otherwise              -> P(venue_qty_signed, order_delta)
```

**Wiring**: one broker round trip per tick, not per order, with
`venue_readable` carried **separately from the dict** so an empty dict can
never be read as "everything is flat."

**`side_is_sell` stays exactly as it is.** v4 adds three checks and relaxes
none. Relaxing it to `side_reduces_exposure` — required for a shorting strategy
to have auto-exits at all — is a **widening** and goes to the adversary blind
first. **Do not smuggle it in under a tightening.**

## 6. The one sentence a human can check

> **v4 forbids the machine auto-approving an exit whose quantity the broker
> does not actually hold on the same side; v3 checked only the fund's own book,
> so TLT / DBC / DBA — book 3.019871 / 8.122157 / 5.314306 against a broker
> holding 0 / 0 / 0 — pass v3 twelve checks out of twelve and would open
> $652.09 of real short exposure, and under v4 they decline and wait for the
> CEO's click.**

## 7. Twenty test cases, and the keystone

The seat measured the gap first: `tests/test_autopolicy.py` has 19 tests, the
only two occurrences of "venue" are inside an error string, and **`context_for`
is referenced by no test in `tests/` at all** — the gatherer, where the venue
read will live, is entirely untested.

Seven sign-flipped predicate cases, three venue-absence cases (**asserting the
detail strings DIFFER** — that assertion is the whole point of the
absence/zero split), the live SPY drift case, and the first three tests
`context_for` has ever had.

**T4 is the keystone**: `pre = −10`, **buy 10** → `exit_reduces_exposure`
**True** *and* `side_is_sell` **False** → overall decline. It pins that the
predicate is sign-agnostic **and** that v4 did not widen to buys, in one test.

## 8. THE OTHER HALF, AND IT IS NOT OPTIONAL

**A v4 decline is currently invisible, and a declined exit dies in two hours.**

- `run()` logs only approvals (`autopolicy.py:387`) and errors (`:396`), never
  skips; `main.py:225` **discards the return value.** On 2026-09-08, v4
  refusing to short the fund produces **no event, no log line, no alarm.**
- The proposal then expires at `PROPOSAL_STALE_AFTER_MINUTES = 120`.
- **And it does not come back.** `pipeline.py:400-403` and `fund.py:3768` both
  claim a still-true condition re-proposes itself within a tick. **Both are
  false**: `exitrule.py:183-194` stamps `triggered_at` and `:275` skips any rule
  carrying it; only a fresh `EXIT_RULE_SET` clears it. **Seq 195 is the live
  proof** — its own note records a human re-committing by hand.

> Shipping v4 alone converts *"the machine silently opens a $652 short"* into
> *"the machine silently stops honouring the fund's exits."* Both are the
> unwired-kill-switch shape.

**Mandatory floor**: `logger.warning` on every skip, naming the failed checks —
strictly additive, touches no behaviour. **Right fix**: a broker-drift alarm.
There are seven alarm types in `riskmonitor.py:1131-1250` and **none watches
the book against the venue** — re-verified by grep, and chair-verified
independently.

## 9. Named, not fixed

1. **`side_is_sell` → `side_reduces_exposure`** is required before a shorting
   strategy has any auto-exit. It is a widening — adversary blind first.
2. **The book cannot tell an intended short from an accident.**
   `positions.py:85` is unbounded with no floor at zero.
3. **Borrow cost, buy-in risk and unbounded loss are unmodelled**, and the
   drawdown machinery assumes bounded downside.
4. **THE EXIT TRIGGER IS SIGN-INVERTED, and R19 does not touch it.**
   `riskmonitor.py:878` computes `unrealized_pnl_pct` with **no reference to
   the sign of `qty`**, and `positions.py:87` only updates `avg_price` when
   `signed > 0`, so a short retains its long basis. **On a short, a rising
   price is a loss but reads as a gain**: a `loss_pct` stop would never fire
   while the short bleeds, and the `gain_pct` exit would fire when it is
   losing. **The most expensive thing found, and it must close before any short
   deploys.**
5. `venue_holds_position` reads settled positions, not positions net of working
   orders. Harmless today; belongs in the docstring.

## 10. Approval-channel audit (standing mandate) — CLEAN

23 `OrderApproved`, max seq **592**, **unchanged across 123 new events**. All on
the allowlist as it stood. 3 `ApprovalRefused`, all previously classified. Still
exactly **one** auto-approval in fund history (seq 256, v1). Code is v3; no
version drift.

**One ledger-integrity absence, low money**: `.firestore_local_db.json` is not a
subset of the live book — five events (seq 156–160) exist only there, and those
seq numbers carry different events in the live book. No fills, no approvals.
**Cite by `event_id`, never `seq`, when crossing the flag boundary.**

## 11. The seat's challenge — v3's adoption premise is measured false

**Direction: TIGHTENS.**

v3 was adopted 2026-08-20 with the basis recorded at `autopolicy.py:84-87`:
*"Blast radius today is $0 (only the sleeve's rules can pass
rule_predates_position, and the sleeve owns its positions) — adopted as
structure, not as an emergency."*

**Both halves are now measured false.** The sleeve's rules do pass
`rule_predates_position` (verified: TLT `set_at` 2026-08-18T02:11:39 against
`opened_at` 2026-08-19T18:20:54), and the sleeve **does not own its positions at
the venue** — broker 0/0/0 against a book of 3.019871/8.122157/5.314306.
Measured blast radius: **$750.36, 39.79% of NAV**, of which **$652.09 is
date-certain**.

> *"The sleeve owns its positions" was true of the ledger the check reads and
> false of the world.*

**The seat asks**: put the CEO's click on v4 **ahead of** the other Batch-1
items, and correct the record with a **new dated note at the v4 bump** rather
than editing `:84-87` — findings are never edited. *"'Structure' tolerates a
queue; seventeen days does not."*
