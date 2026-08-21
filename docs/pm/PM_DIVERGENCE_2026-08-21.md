# PM decision memo — broker-book divergence, and who owns drift (filed verbatim)

**2026-08-21, run-pm-divergence. Dispatched by the co-CTO chair. Read at
2026-08-21T15:42:33Z; every endpoint pulled once between 15:42:33Z and
15:46:56Z — a snapshot, not a feed. co-CTO verification note at the end.**

---

**TL;DR**

1. The $131 broker-book gap is not a mystery: $137 of it is the one phantom GLD trade we already diagnosed, and every other symbol nets to minus six dollars.
2. Do NOT trade to close it. Both trading options require the fund to sell things its own book says it does not own, which would corrupt the book in the opposite direction — the cure is worse than the disease.
3. The urgent item is different and dated: our four positions exist in our book but barely exist at the broker, and when their pre-committed exits fire the machine will automatically try to sell about $751 of stock the broker does not hold — with no human in the loop, guaranteed by 8 September.
4. Recommendation: record the gap as a fenced, dated artifact (zero trading), and put one condition into the auto-approval rule so it refuses to sell what the venue does not hold.
5. Separately, our cost measurement is quietly wrong twice over and must be fixed before we re-run the execution-cost experiment.

## 1. The book in one table

| Position | Qty | Mark | Value | Weight | Unrealised | Exit coverage | **At the broker** |
|---|---|---|---|---|---|---|---|
| SPY | 0.346119 | 767.33 | $265.59 | 14.08% | +0.62% | loss 7.3% + time 2026-11-19 | **0.217757 — short by 0.128362** |
| DBC | 8.122157 | 31.30 | $254.22 | 13.48% | +1.69% | loss 8.7% + time 2026-09-08 | **0.0** |
| TLT | 3.019871 | 82.10 | $247.93 | 13.14% | −0.83% | loss 4.0% + time 2026-09-08 | **0.0** |
| DBA | 5.314306 | 28.215 | $149.94 | 7.95% | −0.58% | loss 6.1% + time 2026-11-19 | **0.0** |
| — | | | **$917.69** | **48.65%** | +$2.92 | **100% (8 rules, 0 fired)** | **$167.06 of $917.69 exists** |

Cash $968.69 (51.35%). NAV $1,886.37. Since inception −$113.63 / −5.68%.

Broker-only holdings, in nobody's book: GLD 0.424471, INTC 1.608762,
MSFT 0.340051, NVDA 0.749886, SOFI 9.188190, XLE 2.749912 — $1,002.26.

`/fund/strategies`: all three sleeves now appear (**my three-review R9 gap
is CLOSED**), but each reads `state: draft, allocation_pct: 0.0` while
holding real money. A `draft` strategy holding 48.65% of NAV is a register
that does not describe the fund. Noted, not a recommendation this round.

## 2. Mandate check

Every registered limit is comfortable: drawdown 1.1383% of 10%, daily loss
0.0838% of 4%, max position SPY 14.08% of 20% (highest utilisation, 0.704),
effective bets 4.02, avg pairwise corr −0.005. Gross 48.6485% vs throttle
target 48.26% — **over by $7.27, i.e. AT TARGET. The throttle is being
honoured for the first time in this book's life.** Do not act on $7.27.

Idle cash $874.37 above the floor carries a written reason (phase 1; phase 2
dated 2026-09-08) — not a leg-3 defect. **R13 remains open**: `/risk/advanced`
ES is overstated by 1/gross = 2.06× today (true ES ≈ $11.18, not $22.98).

**What is closest to binding is not on that table.** The binding constraint
is unregistered, unlimited, unalarmed and 100% breached on three of four
positions: **the fund's book and its venue do not hold the same securities.**

## 3. Exceptions

### E1 — THE ARMED HAZARD. Pre-committed exits will attempt to short $750.63, auto-approved, no human present.

Chain, each link verified: exit sizing comes from the **book**
(`exitrule.py:268-269`, `:287`); `pipeline.submit` calls `_connector`
unconditionally (`pipeline.py:223`), now `AlpacaConnector`;
**`autopolicy.py` contains no venue check and no venue-holding check** —
grep for `venue|paper|alpaca` returns exactly one hit, a comment at line 14;
v3's "the rule's own strategy must hold the quantity it sells" is checked
against the **book**. Compliance does not block a sell beyond flat, it
appends a warning only (`compliance.py:222-226`), and
`shorting_enabled: true`. `positions.py:85-90` folds a sell as an unbounded
signed subtraction — no floor at zero.

**Exposure, measured**: if all four loss exits fired today, the fund would
submit $917.69 of sells to a venue holding $167.06 → **$750.63 of attempted
short sales.** The TLT and DBC **time exits fire on 2026-09-08** for
**$502.15** at today's marks (COO triage #3 independently: $501.34). Both
rules predate their positions and sit inside the v3 envelope, so they
auto-approve. Two possible outcomes, both bad and neither verifiable from
the spine: the venue rejects a fractional short (leaving a fired exit that
silently failed — exit machinery reporting a discharge nobody performed), or
it fills and the fund holds ~$502 of unintended short exposure.

### E2 — The reconciler is now writing the divergence into the permanent ledger, ~178 events/day.

**The brief was wrong and I am correcting it**: reconciliation did NOT stop
at seq 141. At 15:21:40Z it appended **ten `ReconciliationMismatch` events,
seq 715–724**, the first since seq 141. The six days of silence were a
CORRECT skip — `run()` skips any venue whose `account_info().configured` is
false (`reconcile.py:107-110`). With Alpaca configured it no longer skips.
Rate: 0.743 NavStruck/hr × 10 out-of-sync symbols = **~178 mismatch
events/day** against a 725-event log. `reconcile.py:96-99` documents this
exact failure against itself: *"A mismatch event must mean the BROKER
disagrees, or the audit trail trains its readers to ignore it."*

### E3 — The reconciliation heartbeat does not exist, and `nav_strike` beats green even when reconciliation throws.

`/fund/liveness` lists six jobs, all green; reconciliation is not among them.
Worse than absent: `main.py:257-262` wraps `run_reconcile()` in a
try/except that logs a warning, then beats `nav_strike` unconditionally at
`:262`. A dead reconciler is indistinguishable from a live one **and from a
green board**. The fix pattern exists eleven lines above at
`main.py:250-254`.

### E4 — TCA counts a paper fill as an informative alpaca fill. Contamination measured.

`tca.py:209-212` resolves venue as `f_pay.get("venue") or s_pay.get("venue")`
— **the self-declared label on `OrderFilled` first**, with the executed leg
only as fallback. Today's DBA order: proposed `alpaca` → **submitted `paper`
(seq 593)** → filled-label `alpaca` (seq 594). TCA takes "alpaca".
Measured: the informative set is n=9 not 8, and **the fund's headline
realised cost moved 5.56bps → 4.95bps** — exactly the tautology
`tca.py:281-284`'s own comment exists to prevent.

### E5 — `/fund/tca` silently truncates the event stream; today's fills are invisible on the default read.

`fund.py:516` defaults `limit=500` and passes it to the **event stream**
(`tca.py:147` → `pgstore.py:259-277`, `ORDER BY seq ASC LIMIT` — the
**oldest** n). The log holds 725. Verified: default → 20 orders, newest
2026-08-20, n=8, 5.56bps. `?limit=5000` → 22 orders, newest 2026-08-21,
n=9, 4.95bps. **The default view gets more truncated every day the log
grows**, silently, with no absence marker.

### E6 — `/fund/book` reports `orders_are_real: false` while `venue: alpaca`.

`_real_broker()` requires `FUND_REAL_BROKER` (`fund.py:140-141`), absent from
`.env`; connector selection does not (`fund.py:157-159`). The endpoint's own
docstring says its purpose is that *"'mock' must never hide that real orders
are leaving the building"*. It now does exactly that. Downstream,
`/fund/venue/backfill/plan` — the one tool built for reconciliation —
refuses with "no real broker configured".

## 4. The divergence: what each option costs, what each destroys

### 4.1 It is one defect plus six dollars

| Symbol | Book sold @ | Broker mark now | Delta |
|---|---|---|---|
| **GLD** | **100.00 (fabricated)** | 422.70 | **+136.98** |
| INTC | 92.800 | 90.626 | −3.50 |
| MSFT | 484.310 | 484.965 | +0.22 |
| NVDA | 219.600 | 216.140 | −2.59 |
| XLE | 64.635 | 63.695 | −2.58 |
| SOFI | 18.560 | 19.034 | +4.36 |
| SPY (2 orders) | 769.06 / 767.19 | 767.20 | −0.10 |
| | | sum sells | **+132.78** |
| Buys never made at broker | cost $914.77 | book marks $917.69 | −2.92 |
| | | **predicted** | **+129.86** |
| | | **measured** | **+130.78** |

Residual **$0.92 = 0.049% of NAV** — the measured mark-timing noise floor,
and the basis of the alarm band below.

**$136.98 of a $130.78 gap is the phantom GLD fill.** Everything else nets
to −$6.20. This is the first **external** measurement of the phantom's cost
the fund has ever had: R1 rebased by $128.26 from our own marks; the broker,
which we do not control, says the GLD leg is worth $136.98 more than the cash
the book received. The two agree in sign and magnitude, and **R1 erred
conservative** — consistent with the riskofficer's independent ~$5 finding.

### 4.2 The rock both trading options founder on

**The fund has no instrument that writes to the venue without writing to the
ledger, and building one is more dangerous than the drift it would cure.**

Option (a) requires selling six symbols the book does not hold; through the
mandated propose path those fills fold as unbounded signed subtractions
(`positions.py:85-90`) taking the **book** short and crediting ~$1,002.26 of
proceeds the fund never earned. Option (b) requires buying four the book
already holds — same fold, opposite sign, book doubles to 6.04 TLT / 16.24
DBC and NAV inflates by ~$918 of assets that exist once.

### 4.3 Costed

**(a)** $1,752.86 notional, ~$0.87 slippage, ten approvals. Destroys book
integrity on six symbols and moves ~$130 of genuine market risk for a
bookkeeping outcome at the 87th turbulence percentile. **REJECT.**

**(b)** $917.71 notional, 4 approvals. The reset is not a fund action —
`AlpacaConnector` exposes no reset method; it is a dashboard operation
outside the record. Destroys the same ledger integrity **and the only
external record of the nine informative Alpaca fills the entire cost model
rests on**, in the week we learned a venue label can lie. **REJECT.**

**(c)** $0 traded — but loosely done it costs the E1 hazard and ~178 junk
audit events/day.

### 4.4 Recommendation: (c), reframed as FENCE THE COHORT

The Clean Field Rule has a branch written for exactly this: *"Where the
defect CANNOT be re-baselined, the honest move is to fence the contaminated
cohort rather than launder it."* The broker's position book **is** a
pre-instrument artifact — a photograph of a fund whose orders never routed.
Fence it, date it, preserve it beside the live number, measure forward from
a stated epoch. This is the same act performed on the drawdown reference
this morning, applied to a measurement that cannot be repaired.

### 4.5 R15 is not coupled to any option

R15 needs the route real (it now is) and the fill's venue recorded from what
executed. Its real blockers are E4, E5, E6 — all in our code. And **option
(a) would APPEAR to complete R15 while corrupting it**: ten bookkeeping
orders would enter the same TCA sample, taking it n=9 → 19 against a bar of
20. It would look like a measurement and be an artifact of housekeeping.

## 5. The org question

**On "it should be our pm": correct, for the RESPONSE, and I take it.**

**RATIFIED — detection cannot be a seat.** The stronger reason than the
chair's: *when no session is live, nothing thinks.* The E1 hazard fires on a
scheduler tick nobody has to be awake for. A seat-based detector would be an
unwired kill switch — the same class the CEO corrected on the dispatch
auto-close ten hours ago.

**ATTACKED — the chair routes the alarm to the PM's inbox first. Wrong
order.** The first consumer must be the **auto-approval envelope**, because
deterministic code is the only actor guaranteed awake. The PM trigger is the
second consumer — the judgement layer, and useless at 03:00 on 2026-09-08.

**ATTACKED — two lanes are missing.** The envelope change is the
**riskofficer's** by construction; I recommend it and must not specify it.
The heartbeat and alarm are the **builder's**.

### 5.1 The trigger, specified

**Primary instrument is PER-SYMBOL QUANTITY, not NAV dollars** — immune to
marks; an in-flight order moves it by an amount the fund already knows. A
NAV band cannot be primary because `max_order_notional_pct` is 15% =
**$282.96**, so any band under $283 fires on every legitimate in-flight
order and any band above it is larger than half this book.

**STRUCTURAL drift** — per-symbol divergence beyond `_TOL = 1e-6` not
explained by (i) an `OrderSubmitted` with no terminal event, (ii) a recorded
corporate action, or (iii) the fenced epoch. No dollar band on this leg: a
quantity that still disagrees after netting *is* an order that did or did not
happen. Today all ten symbols are structural.

**NAV band, secondary and info-only: `max(1.0% of NAV, $150)`.** 1.0%
because the measured residual is 0.049% (~20× the noise floor); $150 because
it is the smallest live position (DBA $149.94) — below one position a NAV
delta cannot mean a whole leg is missing. At $1,886 NAV the $150 leg binds;
the legs cross at **NAV $15,000**.

| Condition | Autopolicy | Alarm | PM dispatch |
|---|---|---|---|
| Structural quantity drift, any symbol | **fail closed on that symbol** | warn | **DEMANDED** |
| Structural drift on a symbol with an armed exit rule | **fail closed** | critical | DEMANDED |
| NAV band breached, zero structural drift | no effect | info | not demanded |
| Explained drift | no effect | none | none |

### 5.2 Spurious-fire modes, named

1. **Fill in flight** — net `OrderSubmitted` with no terminal event. The most
   likely false positive and the one that determines whether the trigger
   survives.
2. **Mark timing** — measured $0.92 / 0.049%; structurally impossible on the
   quantity leg.
3. **Corporate action** — `positions.py:108-113` folds splits; a one-sided
   split gives a small rational ratio. Route as "corporate action suspected".
4. **A venue that does not persist positions** — keep `reconcile.py:107-110`
   exactly as written.
5. **Fractional rounding at the broker** — **UNTESTED**: this fund has never
   held a book at Alpaca under this code.

### 5.3 The heartbeat, corrected

Reconciliation is not silent (E2). The defect is that `main.py:257-262`
swallows the exception and beats `nav_strike` regardless. Three states are
needed — ran / skipped-with-reason / dead — and the pattern already exists at
`main.py:250-254`. Two of the three currently render as one.

## 6. Recommendations R16–R26

| # | Recommendation | money_at_stake |
|---|---|---|
| **R16** | **DECLINE option (a)** — six sells of securities the book does not hold; takes the book short and credits ~$1,002.26 of unearned proceeds | $1,752.86 avoided |
| **R17** | **DECLINE option (b)** — the buy-side fold doubles the book, and the reset destroys the only external record of the nine informative fills the cost model rests on | $917.71 avoided |
| **R18** | **ADOPT (c) as a FENCED COHORT** — one dated epoch record, netted out of `Reconciler.run()` so only post-epoch drift raises a mismatch | $0 traded; stops ~178 junk events/day |
| **R19** | **Envelope v3 → v4: the VENUE must hold the quantity the rule sells.** Route to the riskofficer to specify. **The only dated recommendation — if one thing is accepted, this one** | **$750.63 armed; $502.15 certain 2026-09-08** |
| **R20** | Reconciliation liveness heartbeat, three states; stop `main.py:262` beating green when `run_reconcile()` raised | 0 direct |
| **R21** | Broker-book drift alarm per §5.1 | 0 direct |
| **R22** | Register: structural drift DEMANDS a pm dispatch — the SECOND consumer of R21, never the first | 0 direct |
| **R23** | `tca.py:212` must prefer the SUBMITTED leg over the declared label | $0.06/round-trip today; decides the 5bps constant pricing every belt candidate |
| **R24** | `/fund/tca` truncation — limit applies to the event stream, oldest-first | 0 direct; worsens daily |
| **R25** | Reconcile `_real_broker()` with connector selection — same conflation class that produced this day | 0 direct |
| **R26** | **Do not re-run R15 until R23 lands** — a paper fill and an alpaca fill are indistinguishable in the only endpoint that grades them | $150.82 protected |

## 7. What I did not look at

`/risk/advanced` sub-blocks; `/fund/executions` (attribution and realised
round-trips unexamined); the nine informative observations individually —
including the unexplained 81.22bps GLD buy of 2026-08-14; **whether Alpaca
accepts or rejects a fractional short — UNKNOWN, not benign**, it decides
which branch of E1 occurs; the `draft` state on three sleeves holding 48.65%
of NAV; whether `/fund/venue/backfill/plan` would return an empty plan if
enabled; R13 (with the validator); the J3 clock (2026-08-26) and TLT J2.
**I did not verify the 2026-09-08 auto-approval against all nine v3
conditions myself** — I verified autopolicy contains no venue check and rely
on COO triage #3 for the rest.

---

## co-CTO verification note (2026-08-21, at resolve)

**E1 verified before filing, and it is the finding of the dispatch.**
`grep -n "venue\|paper\|alpaca" app/fund/autopolicy.py` returns **exactly
one line — a comment at line 14** reading "The venue is Alpaca paper".
There is no venue check, no venue-holding check, and no `account_info`,
`broker` or `venue_qty` reference anywhere in the file. `compliance.py:222`
appends a warning only when `shorting_enabled is False`, and the live
account reports it **true** — so even the warning stays silent. The chain
the PM describes is intact and the hazard is armed.

**Timing, checked so the urgency is stated honestly**: all four loss exits
are far from firing today (TLT −0.71% of 4.0%, DBC 1.50% of 8.70%, SPY
0.28% of 7.30%, DBA −0.74% of 6.10%). The dated exposure is the
2026-09-08 time exits, seventeen days out — enough time to fix this
properly through the riskofficer rather than in haste.

**The seat corrected the chair's brief on a fact**: reconciliation did not
stop at seq 141 — it fired ten mismatch events at 15:21:40Z once Alpaca
became configured, and the six days of silence were a correct skip. My
brief carried the riskofficer's morning finding as though still current.
The seat re-derived it instead of repeating it, which is the standing rule
working.

**On the org question the seat took the CEO's assignment and then attacked
the chair's design in the right place**: the alarm's first consumer must be
the deterministic envelope, not the PM's inbox, because nothing thinks
when no session is live — and it explicitly declined to specify the
envelope change, naming it the riskofficer's lane. A seat refusing a lane
it was implicitly offered is the constitution's separation working without
anyone enforcing it.

R19 is routed to the riskofficer at resolve. R16 and R17 are recorded as
declines. R18 and R20–R25 are builder/CEO items on the desk.
