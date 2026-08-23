# ADVERSARY BATCH 4 — 2026-08-24 (run-adversary-batch4)

Four blind reviews, all CEO-approved, all loosenings, batched per the
batch-by-seat rule after the chair's drain found four approved-undispatched
blind items where one had been flagged (Grace cfo-8 O1, widened at resolve).
Filed verbatim by the chair; the seat's STATE is appended to
`.claude/state/adversary.md`, its BINDS carried to validator, builder, coo,
cfo and quant, its run record filed as `run-adversary-batch4`. Chair
spot-verified before acting: the `main.py:209-213` swallow shape, the
`gate.py:772` margin and `:1351` strict compare, `judgement._wired`
(`judgement.py:325-347`), the symmetric subtraction at
`leanrunner.py:2198-2200`, the probes in `scratchpad/adv33/`, and live
heartbeats (`risk_monitor ok, 0.6s`). All held.

```
TL;DR
1. Prod-gate pack: KILL as filed. The proposed "kill switch is wired" test reads source code, and I demonstrated it passes for four kinds of code that never runs — including the exact shape already in our scheduler. A live heartbeat already answers this question correctly. No money at risk today.
2. PDT retirement: SURVIVES. Every regulatory date checks out against FINRA, the SEC and Alpaca. Two of the memo's own supporting details are wrong and should be struck; the conclusion stands.
3. Desk filing rule: KILL, re-confirmed on a fresh sample. 2 of today's 7 open requests would be auto-marked "CEO approved" on a quote where the CEO was wishing, not approving.
4. Belt cash-interest fix: the diagnosis is right and important, but shipping it alone is a loosening. Measured: zero-skill cash mixes go from always-refused to 50% passing. It needs a threshold decision alongside it, which the filing says it does not.
```

---

# ITEM 1 (a26debb9) — prod-gate preconditions made closeable — **KILL (pack as filed)**

Ground is the **P4 leg**. P2 and P3 do not die on the evidence I have, and I say that plainly below.

**The direction is right and I want that on the record.** Three of the five preconditions at `app/fund/mode.py:408-447` carry no evaluator and render `unchecked`, which blocks (`mode.py:328-343`). A lock that can never open is a wall, and `mode.py:274-279` says the precondition list exists precisely as the counterweight to the constant. A wall labelled as a lock is the pattern this fund's own doctrine forbids.

**Money today: $0, and structurally so.** `PROD_UNLOCKED = False` (`mode.py:305`), `reachable = bool(PROD_UNLOCKED) and not unmet` (`mode.py:473`), and `POST /fund/mode` raises 403 for `alpaca-prod` *unconditionally*, gate or no gate (`app/api/v1/fund.py:906-913`). Live, the fifth precondition is also genuinely unmet on world evidence:

```
$ curl -s .../fund/mode | jq .prod_gate
reachable: False  n_met: 1  n_blocking: 4
 - controls_fired              = met
 - book_venue_reconciled       = unchecked
 - exit_sign_fixed             = unchecked
 - kill_switch_wired_and_tested= unchecked
 - informative_fills           = unmet | 8 informative fills ... against 20 required
```

So closing all three buys nothing until 12 more informative fills exist. Per my own D18 lesson, I weighed the residual before promoting anything to a verdict.

## KILL ground — P4's named method is wrong in both directions, and a better one already ships

The proposal names "an AST call-graph check (the D18 census pattern)". I built that check and ran it against the real file and seven planted shapes (`scratchpad/adv33/p4_astgraph.py`):

```
REAL app/main.py                                     -> (True, '_scheduler calls run_risk_monitor_tick at line 211')

A: guarded by if False                               -> True   <- FALSE WIRED
B: call present, body raises every tick (swallowed)  -> True   <- FALSE WIRED, and this is the SHIPPED shape
C: call after an unconditional return                -> True   <- FALSE WIRED
D: dead branch on a constant flag                    -> True   <- FALSE WIRED
E: genuinely wired                                   -> True
F: wired via getattr (computed name)                 -> False  <- FALSE NOT-WIRED
G: wired via a dispatch table                        -> False  <- FALSE NOT-WIRED
```

Case B is not hypothetical. `app/main.py:209-213` is:

```python
try:
    fund_router.run_risk_monitor_tick(actor="worker")
    heartbeat.beat("risk_monitor")
except Exception as e:  # noqa: BLE001
    _log.warning("risk monitor tick failed: %s", e)
```

A tick that throws on every iteration forever leaves the call node exactly where it is. The static check says WIRED. The fund's own comment eleven lines above (`main.py:200-207`) names "one post-fill path swallowing its own exceptions" as half of the original defect — the proposed evaluator is blind to the same swallow in the scheduler.

**And the correct evaluator already exists, ships, and is registered.** `app/fund/judgement.py:325-347`:

```python
def _wired(job: str):
    """Reads whether a scheduled job is actually TICKING, not what it is set to.
    ... it could not have caught the risk monitor, whose value was fine and
    whose CALLER did not exist."""
```

It is bound to `risk_monitor_is_wired` at `judgement.py:685-700`, `basis="measured"`, and it reads live right now — `/fund/liveness` returns `{"job":"risk_monitor","ok":true,"age_seconds":9.5}`, and `/fund/judgement` returns that entry `value: true, readable: true`. Its registered `falsified_by` is the sentence that kills the proposal: *"the kill switches are only real while the tick runs."* P4's own text (`mode.py:435`) demands "WIRED AND TESTED, **not registered**" — an AST call-graph check measures registration of a call node. It is the category the precondition text rejects, substituted for an instrument the fund already has and already trusts.

## P2 — the filer's own kill condition: **NOT MET on the evidence I have.** Say it plainly.

The design requires a cited-artifact field, so "satisfied by assertion WITHOUT cited evidence" is not demonstrated, and there is no code to attack. Two things I *can* measure, neither of which is that:

1. **P2's stated premise is half-false.** `mode.py:420-423` says "there is no reading of the log alone that settles it." True of the judgement half, false of the measurement half — `GET /fund/venue/reconcile` reads both sides and returns a number, live, right now: `book_nav 1885.74 / broker_equity 2012.28 / delta_usd 126.54 / delta_pct 6.7104 / symbols_out_of_sync 10 of 11`. So the state P2 would be attested over is materially red today, and an attestation is a point-in-time signature read at a later time — an expiry bounds the clock, never the divergence.
2. **This fund's base rate for attestation fields being live is measured and it is 2 of 19.** `/fund/judgement` today: 17 of 19 entries carry `trigger_spec: []`, and the endpoint reports `triggers_unchecked: []` — absence rendered as zero, at the level of the decision register. That is the constitution's own open defect (`judgement.py:227-228, :252, :770, :787`), and it is still open. A new record type carrying `falsifier` and `expiry` fields lands in a codebase where the existing one leaves 89% of them unevaluated.

Also worth stating: **the destination already exists by a guarded path.** `POST /fund/venue/sync/apply` takes `_guard_approval("venue_sync", ...)` (`fund.py:5061`) — allowlist, `run_id` echo, verbatim instruction, plan re-read server-side. Any new attestation path must clear that bar or it is the guard-asymmetry kill in a new costume (`fund.py:1799` filing unguarded vs `fund.py:1901` approving guarded).

## P3 — **CANNOT TELL as specified**, and the ambiguity is the finding

"via a suite assertion" reads two ways and they are not close:

- **Sound reading**: the evaluator asserts the property directly — `unrealised_pnl_pct(qty=-10, mark=110, avg_cost=100) < 0`. That is a world-fact about the code that no commit can fake without actually fixing the sign. The assertions exist at `tests/test_hazard_batch.py:759-800`.
- **Hazardous reading**: shell out to pytest at gate-read time. `prod_gate_report` is called unconditionally on every `GET /fund/mode` (`fund.py:869` → `mode.py:810`) — measured at 0.09–0.14s today; a pytest subprocess on this host is seconds, on a machine the constitution already records collapsing at 1.28 GB free RAM. Beyond cost: suite-green is not assertion-present, a skipped test is not a passed one (`pytest -k` on a missing node exits 5, not 0), and this repo already ships a suite whose count is `1436 + 97 PG-skipped`.

## The structural point, offered as input to the CEO's decision, not as a verdict

After the pack, `controls_fired` and `informative_fills` remain facts about the **world** (an append-only log; real fills through TCA). P3 and P4 become facts about the **repository** that the person flipping `PROD_UNLOCKED` is editing, and P2 becomes a signature. Three of five counterweights become satisfiable by the same actor in the same commit that opens the first lock. `mode.py:274-279` is explicit that two *independent* locks is the design.

**What would change my mind on Item 1:** P4 evaluated from `heartbeat.status()` / the existing `judgement._wired` reader rather than from source, or an AST check that additionally proves runtime execution; P3 pinned to the direct-assertion reading; P2's attestation routed through `_guard_approval` and carrying the machine-measured `symbols_out_of_sync` at attestation time. Any of those and I would look again at the remaining legs individually.

---

# ITEM 2 (b6f4a407) — retire the PDT block — **SURVIVES**

Disclosure first: **this is a re-review.** I filed a verdict on this artifact on 2026-08-22 late UTC (`docs/reviews/ADVERSARY_BATCH_2026-08-23.md`, run `run-adversary-batch2`), verdict SURVIVES with the first-party datum struck. I re-verified every regulatory fact from scratch rather than citing myself. The verdict stands, and I found one *new* evidence defect.

## The regulatory facts — all four verify

| Claim in D5 (`GRACE4_2026-08-23.md:155`) | Verified |
|---|---|
| SEC approved the Rule 4210 amendments 2026-04-14 | Yes |
| FINRA published Regulatory Notice 26-10 on 2026-04-20 | Yes |
| Effective 2026-06-04 | Yes |
| Eliminates the PDT designation, the day-trade count and the $25,000 minimum | Yes, verbatim: *"to replace in their entirety the outdated day trading margin requirements, including the day trade count requirements for designating a customer as a 'pattern day trader' and the $25,000 pattern day trader minimum equity requirement"* |
| 18-month phase-in to 2027-10-20 | Yes |
| Alpaca implemented it | Yes — Alpaca implemented the Intraday Margin Framework **on 2026-06-04**, and removed `pattern_day_trader` / `daytrade_count` / `daytrading_buying_power` from the API by **2026-07-06** |

**Alpaca's phase-in enforcement: none found.** Alpaca did not phase in — it went live on the effective date and deleted the fields five weeks later. The filer's caution about the 2027-10-20 window is therefore conservative but not load-bearing for *this* broker.

## Two evidence defects, both self-inflicted, neither fatal

1. **The `pattern_day_trader: null` datum is VOID — struck again, and now over-determined.** `compliance.py:25-32` attributes the same nulls (measured 2026-08-14) to paper-venue non-simulation. Alpaca deleted the fields on 2026-07-06. A null cannot discriminate: rule-retired, field-deleted, and paper-not-simulating all produce it. Live now: `/fund/compliance` → `daytrade_count: null, pattern_day_trader: null`.
2. **NEW: "Alpaca... lowered the equity floor for 4× intraday buying power from $25,000 to $2,000" (`:155`) does not verify against Alpaca's own documentation.** Alpaca's Intraday Margin Rule page states the $25,000 day-trade minimum is removed and that *"Standard Regulation T requirements still apply; for example, margin-enabled accounts typically require a minimum of $2,000 in equity to maintain intraday debits or short positions."* That is the general Reg T margin-account floor, not a 4× threshold. Two different statements welded into one.

Neither touches the conclusion, which is carried entirely by FINRA and the SEC. But this is now the **second** memo in this family whose one first-party-flavoured datum is weaker than its web citations — grade the two layers separately, every time.

## What the block still protects: nothing, and the replacement hazard is unguarded anyway

`_pdt_blocks` (`compliance.py:233-278`) reads exactly one quantity: a count of same-session opposite-side round trips, gated on `account.equity < PDT_EQUITY_THRESHOLD` (`:59`). It reads no cash, no buying power, no margin deficiency. Grep across `compliance.py` finds `margin` / `deficit` / `buying_power` only in comments and the `AccountState` dataclass (`:12, :89, :104, :119`) — **there is no margin-deficiency check anywhere in the module.**

The replacement framework's hazard, from Alpaca's own doc: an Intraday Margin Deficit issues a call satisfiable in two business days; unresolved by the fifth, *"the account will be subject to a 90-day freeze, restricting the account from increasing short positions or creating new debit balances."* De minimis: *"An intraday margin call is generally not triggered if the unmet deficit is less than $1,000 or 5% of account equity."*

At the live account — equity $2,012.28, cash $846.84, buying_power $6,650.59 — the $1,000 de minimis exceeds the fund's entire cash balance. So: retiring the block removes nothing that covered the new hazard, because it never covered it; and the new hazard is largely de-minimis-excused at this size. The residual worth naming separately is that `shorting_enabled: true` and the freeze bites shorts — but that is a risk-limit question, and `compliance.py:1-9` is explicit that risk limits and compliance rules are deliberately different modules.

**Live cost of the stale block, measured:** `/fund/compliance` → `"pdt": {"applies": true, "remaining": 3, "broker_count": null, "source": "our event log", "diverges": false}`. The fund is enforcing a retired rule against its own log. `diverges: false` on an unreadable broker count remains the absence-rendered-as-agreement bug I flagged in batch 2 (`fund.py:688`) — still live, still unrepaired.

**What would change my mind:** a FINRA or Alpaca statement that the day-trade count survives in any form for self-clearing correspondents, or evidence Alpaca reinstates enforcement during the phase-in.

Sources: [FINRA Regulatory Notice 26-10](https://www.finra.org/rules-guidance/notices/26-10) · [ACA Group — FINRA Ends the Pattern Day Trader Rule](https://www.acaglobal.com/industry-insights/finra-ends-the-pattern-day-trader-rule/) · [Alpaca — FINRA Retires the PDT Rule](https://alpaca.markets/blog/finra-retires-the-pdt-rule-introducing-alpacas-new-intraday-margin-framework/) · [Alpaca changelog — PDT fields deprecated](https://docs.alpaca.markets/us/changelog/2026-06-03-pdt-651df23) · [Alpaca — The Intraday Margin Rule](https://docs.alpaca.markets/us/docs/the-intraday-margin-rule)

---

# ITEM 3 (1c53589f) — file at `approved` when the filing quotes a CEO instruction — **KILL (the remedy)**

Also a re-review: I killed this remedy on 2026-08-22 late UTC (same batch doc). I re-ran the killing probe against **today's live desk** — a fresh, independent sample — rather than re-citing myself.

## The finding SURVIVES and is still live

`desk.py:1143-1148` still carries the challenged premise verbatim in the code:

> *"requests awaiting approval — all 25 `DeskRequestApproved` events in the log carry actor `ceo` or `neelesh-via-cto` ... so an open desk request is a CEO decision."*

Live `desk_load`: `total 39`, `components: {open_recommendations: 32, pending_orders: 0, requests_awaiting_approval: 7}`, `coo_triage_due: false`. The `next_actor` routing rebuilt at `desk.py:900-948` applies to **recommendations**; the request component is still counted whole on the challenged premise. The COO is right that the premise is measured false.

## The REMEDY dies on three grounds, all re-verified today

**1. Re-run of the predicate over a fresh sample reproduces the false-approval rate.** All 7 currently-open requests are filed by actor `operator`, not the CEO. Three hit the "quotes a CEO instruction" predicate; two of those would be filed `approved` on a quote that is a **wish, not an approval**:

- `4a4f6b0d` — *"D34 addendum ... (CEO, verbatim: many items feel open despite being closed off by you; maybe postgres is the right way...)"*. The quote is a complaint about desk hygiene. The request is a two-part engineering build he has not seen.
- `cf4f7de8` — *"D33 – THE LIVE FLOOR (CEO, verbatim: agents w sub-agents fanned out in the rooms UI, changing shape in realtime)"*. A description of something he wants to look at, quoted to motivate a spine + UI build.
- `62fe366f` — carries no CEO quote at all; it matched on the word "CEO". A predicate false positive, i.e. the rule's own trigger firing on prose.

**2 of 7 = 29%**, against **3 of 11 = 27%** measured on 2026-08-22. Two independent samples, forty-eight hours apart, same rate. A quote of a question, a complaint, or a wish is not an approval, and no text predicate separates them.

**2. The guard asymmetry, re-verified at today's line numbers.** `POST /fund/desk/requests` (`fund.py:1799-1825`) has **no `_guard_approval`**, no `status` field, and a caller-supplied free-text `actor`. `POST /fund/desk/requests/{id}/approve` (`fund.py:1878`) takes `_guard_approval("desk_request", request_id, req.actor, req.confirm, req.instruction, APPROVAL_ALLOWLIST)` at `fund.py:1901` — allowlist, `id[:8]` echo, verbatim instruction, `APPROVAL_REFUSED` on failure. The remedy moves an approval determination from the only guarded path to the only unguarded one.

**3. Status is a FOLD, not a filing field.** `desk.py:642` writes `status: "open"` on `DESK_REQUESTED`; `desk.py:656-658` promotes to `approved` **only** on a `DESK_APPROVED` event. Implementing the remedy means either adding a status field to the unguarded filing endpoint, or auto-emitting `DESK_APPROVED` from it. Both bypass `_guard_approval` by construction.

**And the destination is already reachable by the safe path** — 63 of 104 requests already sit at `approved`, staged through the guarded endpoint with the instruction inline. A loosening that buys a state you can already reach safely is free to kill.

**What would change my mind:** a filing-time predicate that is not text-matching — an explicit `approved_by` + `confirm` echo on the filing endpoint routed through `_guard_approval`, or an explicit `next_actor` field on desk requests (which the recommendation lane already has and the request lane does not).

---

# ITEM 4 (9fb82050) — credit rf on idle cash inside the belt — **KILL as filed. The diagnosis SURVIVES and matters.**

## What survives, said first and loudly

**The diagnosis is correct, structural, and I confirmed it independently.** No cash-interest model exists anywhere: grep for `CashInterest|InterestRate|SetCash|cash_interest` across all 21 algorithms in `lean_workspace/` and across `app/fund/` returns **zero** matches outside two comments naming `NullMarginInterestRateModel` (`gate.py:838`, `leanrunner.py:2448`). Belt cash earns exactly 0%. The measured "n=11 runs at exactly 0.000%" is therefore confirmation of a structural certainty, not an independent finding — no code path could have produced anything else.

**The consequence is real and it is currently biasing every cash-heavy premia claim.** Under the shipped rule, a zero-skill mix of weight *w* in the benchmark and *1−w* in cash scores `adv = (rf̄/σ)·(1 − 1/w)`. Measured on the fund's own feed:

```
lookback 700  (11 of 16 fleet algorithms):  BIL 4.083%/yr, benchmark excess Sharpe +0.8850
  w=0.10 adv -2.1694 | w=0.30 -0.5626 | w=0.50 -0.2382 | w=0.90 -0.0258
lookback 2000:                              BIL 3.255%/yr, benchmark excess Sharpe +0.7371
  w=0.10 adv -1.7331 | w=0.30 -0.4576 | w=0.50 -0.1979 | w=0.90 -0.0224
```

A genuine cash-heavy premia edge at w=0.3 must overcome −0.56 of pure arithmetic before it can register. That is a real defect and it deserves a fix.

## The premise that lets it through — "this is repair, not weakening" — is what I killed

**Because the bias is load-bearing for a margin the proposal declines to touch.** `premia_min_sharpe_advantage = 0.0` (`gate.py:772`), compared strictly (`gate.py:1351`: `if not adv0 > margin`). Credit rf on idle cash and the excess pair becomes `w·(r_risky − rf)` on the strategy leg against `(r_bench − rf)` on the bar — **whose Sharpes are identical**, so a zero-skill cash mix lands exactly on the margin. In exact arithmetic that fails on the strict `>`. In a real backtest it does not, because weights drift between rebalances.

Measured, monthly rebalance with drift (`scratchpad/adv33/item4.py`):

```
              SHIPPED           CREDITED
  w      adv      pass       adv      pass
0.10  -2.1694    False    +0.0078    TRUE      <- 700d
0.30  -0.5626    False    +0.0060    TRUE
0.50  -0.2382    False    +0.0042    TRUE
0.90  -0.0258    False    +0.0008    TRUE
```

**Six of six zero-skill cash weights flip from refused to passed** at the 700-day window — the window 11 of 16 fleet algorithms run. At 2000d the identical six all land at −0.01 and fail. The *sign of a zero-skill pass becomes a property of the window*, at |adv| ≈ 0.01 — an order of magnitude below the ±0.05 noise band the quant already measured on this statistic.

And on the realistic family — Dirichlet weights over SPY/TLT/GLD plus cash, judged against the buy-and-hold bar the belt actually forms, n=400 draws per cell:

```
lookback 700 (482 sessions):   SHIPPED false-pass 36.0%  ->  CREDITED 50.5%   (+14.5pp)
lookback 2000 (1377 sessions): SHIPPED false-pass 30.5%  ->  CREDITED 44.5%   (+14.0pp)
```

**Honest framing of my own number**, because the shipped baseline is itself bad: the credit does not *create* this hole — the 30–36% baseline is my Entry-20 finding (daily rebalancing beats a buy-and-hold bar with zero information). The credit **widens it by ~14pp and lands the zero-skill cash-parker exactly on a coin flip.** The buffer being removed is an accident, not a control. But the filing says "No threshold value proposed", and shipping a truthful measurement into a margin calibrated against an untruthful one is a loosening in effect regardless of intent. That is the specific claim I am killing: *repair-only*.

## The symmetry question the brief asked, answered with arithmetic

**The subtraction is already symmetric and does not need fixing** — `leanrunner.py:2198-2200` subtracts the *same* `rfmap[d]` from both legs. The benchmark leg is a market curve with no idle cash to credit (`leanrunner:1291`), so there is nothing to credit on that side. **The symmetry that binds is between the in-backtest CREDIT rate and the gate's SUBTRACTION series** (`gate.py:795-800`: `premia_rf_basis: "realised_series"`, `premia_rf_symbol: "BIL"`). If they differ, the residual `(credit − rf̄)·(1−w)/σ_strat` is a pure gift. Measured (`scratchpad/adv33/item4b.py`), crediting at the gate's own legacy constant 4.0% (`gate.py:813`) while it subtracts realised BIL:

```
lookback 2000 (BIL realised 3.255%/yr):
  w     credit=BIL   credit=4.0%      gift   passes
0.20      +0.0000       +0.1671    +0.1671    TRUE
0.30      +0.0000       +0.0980    +0.0980    TRUE
0.50      +0.0000       +0.0422    +0.0422    TRUE
0.70      -0.0000       +0.0181    +0.0181    TRUE
```

A matched credit reproduces `adv = 0.0000` to four decimals — my derivation, executed. A 0.75pp rate mismatch buys +0.17 Sharpe at w=0.2 against a margin of 0.0. This is my D23 constant-rf kill in a new costume, and it would arrive from inside the engine where the gate cannot see it.

## The hole that does NOT re-open — say the negative loudly

`premia_max_gross_exposure = 1.0` (`gate.py:847`), applied with no epsilon, unreadable-refuses (`gate.py:1232-1263`). My D29 kill — that excess is `Σwᵢrᵢ − rf` above 100% gross, with a gift of `(1 − 1/G)·rf/σ` growing in leverage — is **out of reach** because the ceiling refuses everything above 1.0, and above 1.0 there is no idle cash to credit. The credit cannot reopen the D29 channel. I looked for it and it is not there.

## Two claimed numbers that do not reproduce — both in the conservative direction

- **"3.52%/yr" maximum double-charge.** Measured on the fund's own alpaca feed: BIL realised **4.083%/yr at 700d**, **4.355%** at 900d, **3.255%** at 2000d. 3.52% matches none of them, and it *understates* the effect at the modal window by 0.55pp (16% relative). Self-penalising, so a precision defect and not a loosening — but a claim about a rate must be measured on the window the fleet actually runs.
- **"BIL is already in fund_bars (2,779 bars)."** Postgres 5433, `fund_bars` where `symbol='BIL'`: **4,839 rows** — 3,459 yahoo (2007-05-30 → 2026-08-21) plus 1,380 alpaca (2021-02-23 → 2026-08-20). 2,779 reproduces on no whole-symbol or per-source slice. More data exists than claimed.

**What would change my mind on Item 4:** the credit filed *together* with a margin decision measured against the credited false-pass rate (i.e. a `premia_min_sharpe_advantage` chosen so the zero-skill Dirichlet family sits below it), plus a pin that the in-backtest credit series is byte-identical to `premia_rf_symbol`'s realised series. With those two, this becomes exactly the repair it describes itself as, and I would clear it.

---

*Chair's resolution note (2026-08-24): Item 1 — pack v2 re-specced per the
adversary's stated conditions and filed to the adversary queue (blind again).
Item 2 — retirement recommendation AB4-2 on the CEO's desk, cleared-by-blind,
his click; the two struck claims recorded. Item 3 — remedy declined; the
underlying counter defect remains open work. Item 4 — clearance conditions
folded into D36's brief mid-flight (credit-series pin + paired margin table +
proposed margin, one bundle or the credit ships dark).*
