# Krypton Fund — session handoff

Written 2026-08-13, updated at the end of the second live session.
Everything below was verified at the time of writing, not remembered. Where
something is unverified it says so.

---

## 0. Start here — exact state

**The end-to-end path works.** On 2026-08-13 the platform placed, gated,
approved, filled and reconciled its first two orders through its own flow.

| | |
|---|---|
| Ledger | local file `ClarkHarness/.firestore_local_db.json` (NOT Firestore) |
| Broker | Alpaca paper `PA39CZ4T5WJK`, orders are **real** |
| Positions | INTC 6.7 · SOFI 16 · MSFT 0.340051 — `symbols_out_of_sync: 0` |
| NAV | $2,028.39 · NAV/unit 1.014194 · cash $863.00 |
| Live breaches | INTC 34.6% vs 20% cap · Mean Reversion 49.1% vs 40% cap |
| First round-trip | F closed −$0.70 (−0.21%), entry 13.899 → exit 13.87 |

### Resume
```bash
cd "C:/Users/user/Documents/Krypton Fund/ClarkHarness"
bash scripts/run_local.sh          # <- USE THIS, see the warning below
cd ../KryptonPay && npm run dev
./venv/Scripts/python.exe scripts/live_monitor.py --interval 120   # optional
```

> **Do not start the spine by hand.** `.env` carries `USE_FAKE_FIRESTORE=0` and
> `FUND_ENV=production`, because that is the deployed fund's configuration. The
> local session was safe only because someone exported `USE_FAKE_FIRESTORE=1` in
> a shell — a setting that existed nowhere on disk. The first restart lost it and
> the spine came up pointing at the **production ledger**. `run_local.sh` is that
> setting written down. Do not delete `.firestore_local_db.json`; it is the book.

### The first thing to do
The book is still **in breach**: INTC is 34.6% against a 20% cap. The sells that
clear it are sitting in the signals panel on Monitor — propose, approve, done.
This is now a two-click operation and no longer needs the rebalance planner.

### What this session proved, and what it exposed
Two orders went the whole way — `OrderProposed → OrderApproved → OrderSubmitted
→ OrderFilled`, reconciling to `symbols_out_of_sync: 0` and a $0.01 NAV delta.
The MSFT buy showed 23c of slippage against its own impact preview ($169.07
previewed, $169.30 filled), which is real and worth checking against the 2bps
cost assumption in the backtester before trusting it.

Five things were found that were quietly wrong:

1. **No signal→order loop existed at all.** Strategies had allocations and
   universes; nothing ever ran them. Every fill in the book had arrived from
   elsewhere. `app/fund/signals.py` is the missing link.
2. **A risk limit prevented de-risking.** The single-order notional cap applied
   to every order regardless of side, so a position larger than the cap could
   never be exited — in one order or any number of them. It bit hardest exactly
   when a position had grown large.
3. **Dividends were not ingested.** No event type, nothing reading the venue's
   activities. F pays quarterly; every payment would have appeared only as NAV
   drift that never resolves.
4. **A corrupt ledger became an empty one.** A JSON parse error silently reset
   the store to `{}` and the next save overwrote the damaged file. Total silent
   loss of the fund's history from a recoverable error.
5. **Prices were unadjusted.** Alpaca defaults to `adjustment=raw`; every split
   appeared as a crash and every signal fired on it.

**Lesson worth keeping from the previous session: NAV drift is a terrible
detector.** Buying converts cash to stock 1:1, so equity barely moves while
composition diverges completely. That is why `live_monitor.py` diffs positions.

**Lesson from this one: a self-reported health check proves nothing.** The
settlement poller ran on a 300-second interval for a whole session — a fill sat
unrecorded for five minutes while every "scheduler: OK" check would have passed.
The System status panel now derives each row from an artefact the component
actually produced.

---

## 1. Start here (getting running in 2 minutes)

The real ledger is **blocked on Firestore quota**, so develop in **mock mode**:
an in-memory book with fake fills that mark at **real market prices**.

```bash
# spine — mock mode
cd "C:/Users/user/Documents/Krypton Fund/ClarkHarness"
rm -f .firestore_local_db.json          # the "in-memory" store is file-backed
USE_FAKE_FIRESTORE=1 FUND_LIVE_MARKS=true DISABLE_DEMO_SEED=1 \
  ./venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8090

# seed it: $2k, THREE strategies, 9 fills at live prices, ~$120 cash left.
# Refuses if the book already has NAV — it is not idempotent, and running it
# twice would double the fund.
./venv/Scripts/python.exe scripts/mock_seed.py

# frontend
cd "C:/Users/user/Documents/Krypton Fund/KryptonPay" && npm run dev
```

Then http://localhost:3000/clark/studio

**Confirm which book you are on before trusting any number:**
```bash
curl -s localhost:8090/api/v1/fund/book
```
`env` is one of `mock` (in-memory, disposable), `staging`, `production`. Mock
reports `project_id: "in-memory"` regardless of `FUND_ENV` — an in-memory ledger
can never present itself as the fund.

### Gates before any commit
```bash
cd ClarkHarness && ./venv/Scripts/python.exe -m pytest -q     # 187 passing
cd ../KryptonPay && npx tsc --noEmit                          # 0 errors
```
Do **not** run `npm run build` while `npm run dev` is running — it overwrites
`.next` and desyncs the dev server's module map. That broke the app twice.

---

## 1b. Live-flow mode (local ledger + REAL Alpaca orders)

Added 2026-08-13. Where state lives and where orders go are now **separate**
decisions — conflating them meant you could not do the one thing that proves the
system works: place real orders and watch them fill, without writing to the
production ledger.

```bash
rm -f .firestore_local_db.json
USE_FAKE_FIRESTORE=1 FUND_REAL_BROKER=1 FUND_LIVE_MARKS=true DISABLE_DEMO_SEED=1 \
  ./venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8090

./venv/Scripts/python.exe scripts/live_seed.py       # funds $2k, 3 strategies, ZERO orders
./venv/Scripts/python.exe scripts/live_flow_check.py # read-only ledger-vs-broker diff
```

`GET /fund/book` now reports `venue`, `orders_are_real` and `seeder_may_run`, so
"mock" can never hide that real orders are leaving the building. `mock_seed.py`
**refuses to run** when `orders_are_real` is true — it invents fills and would
place nine real orders.

`live_seed.py` deliberately places **no orders**: order flow is the thing being
tested, so it must go through Allocate → Rebalance → propose → gate → approve.

---

## 2. Where things stand

### Blocked
**Firestore free-tier quota is exhausted on `hedgefund-ae96c`.** Anything touching
the event log returns 503 with a clear cause. Quota resets daily (midnight
Pacific); the Blaze plan removes the ceiling for cents at this scale.

Root cause was ours, and is fixed: `RiskControl` did four full-log scans per
call and `/fund/risk/monitor` (polled by the risk bar on every page) paid for
all four; snapshots only engaged after 50 events so a 22-event book never
snapshotted. Both fixed, **neither verified against the real ledger yet** — that
is the first thing to check when quota returns.

### The real fund (production book)
- Project `hedgefund-ae96c`, database id **`default`** (not `(default)` — the SDK
  assumes the latter and 404s, hence `FIRESTORE_DATABASE_ID`), region asia-south1
- Opened clean: **$2,000, 2,000 units @ $1.00**, one LP (`rushi`)
- Strategy `Live Test SMA Crossover` (sma 10/30) deployed at 50%, scoped
  INTC/F/SOFI/PLTR
- Risk limits sized for $2k: position 20%, order notional 15%, cash floor 20%,
  **drawdown halt 10%**, daily loss 4%
- **One INTC order (2.7 shares) approved and submitted, never filled** — it was
  placed while the market was shut, and the spine went down on quota before the
  settlement poller could catch it. Check its state first thing.
- Broker: Alpaca paper account `PA39CZ4T5WJK`, funded $2,000, reconciled to
  **$0.00 drift** at open

### Studio (five tabs, one per job)
| Route | Job | State |
|---|---|---|
| `/clark/studio` | **Decide** — what needs a human | rebuilt |
| `/clark/studio/allocate` | **Allocate** — how much goes where, + the rebalance workflow and approval queue | rebuilt |
| `/clark/studio/lab` | **Lab** — backtest and iterate | rebuilt |
| `/clark/studio/monitor` | **Monitor** — is it okay, did it fill | rebuilt |
| `/clark/studio/risk` | **Risk** — structural risk (Vishesh's surface) | new |
| `/clark/studio/compose` | multi-strategy allocator | **not reviewed** |

`/strategies` 307-redirects. `/theses`, `/approvals`, `/review` are deleted.
Review's content was distributed: attribution to Allocate, NAV record and audit
trail to Monitor.

**Risk is split deliberately.** Limit utilisation and the kill switch stay in the
always-visible RiskBar and in Monitor, because they apply to every tab and must
never be somewhere you navigate *to*. `/risk` holds the part that is a standing
job rather than a glance: correlation, effective bets, tails, market regime,
survivability.

**Rebalance lives inside Allocate**, not on its own route — the targets you are
changing are on that page, and moving to a separate screen means deciding without
the numbers you are deciding about in front of you. `RebalanceModal` is deleted:
resizing strategies changes fund mechanics, and a modal cannot show that.

### The mock book (what the seeder now builds)
$2,000 across **three** deployed strategies at 31.3% each, ~$120 cash (6%), nine
positions, all filled at live prices:

| Strategy | Type | Universe |
|---|---|---|
| Momentum — Large Cap Tech | sma 10/30 | AAPL, MSFT, NVDA |
| Mean Reversion — Cyclicals | rsi 14 | F, INTC, SOFI |
| Trend — Sector & Commodity | macd | SPY, XLE, GLD |

Deliberately shaped to produce real findings rather than a clean book. Limits are
set by the seeder for a ~95%-deployed $2k fund (5% cash floor, 10% drawdown halt,
20% max per name).

---

## 2a. Strategy composition: research -> evidence -> queue -> book

The flow a strategist actually needs, and what was missing.

A backtest answers "is this good on its own", which is the wrong question. The
two that matter were unanswerable until now:

1. **Is it alpha, or beta I already own?** `app/fund/factors.py` regresses any
   return series on six tradeable ETF proxies (market SPY, size IWM-SPY, value
   IWD-IWF, momentum MTUM-SPY, rates TLT, commodity GLD) and reports betas with
   t-stats, alpha with a t-stat, R-squared and idiosyncratic share.
   *Finding on the live book: market beta **1.06** (t 11.7), alpha -5.6%/yr with
   t -0.36. Three strategies, nine names, and it is the market with extra steps.*
2. **Does it improve the FUND?** `AdvancedRiskEngine.candidate_fit()` measures a
   candidate against the deployed book: correlation to each existing strategy,
   and book vol / Sharpe / ES before and after adding it at N%. It also classifies
   the `effect` — **diversifying** (Sharpe up, vol down) vs **return-seeking**
   (Sharpe up because risk went up). Conflating those is how a book quietly levers
   up while every dashboard reports an improvement.

Both are surfaced in the Lab under every run (`CandidateVerdict`), and
**"Propose at N%"** registers the strategy *with its backtest attached* and drops
the sizing into the rebalance queue. `POST /fund/research/promote`.

### Composer vs "New strategy" — RESOLVED (partly)
"New strategy" on Allocate now links to the **Lab**; `CreateStrategyModal` is
deleted. Strategies are born from evidence via `research/promote`, which attaches
the backtest and queues the sizing.

`/compose` is **still live and still unreviewed** — deliberately not touched
during the trading session. Folding its genuine part (multi-strategy weighting)
into Allocate is the remaining piece.

Original analysis, for the record:
- `CreateStrategyModal` creates an **empty named shell** (name + optional parent,
  no definition, no universe). The thing that makes a strategy a strategy is then
  filled in somewhere else, so the evidence that justified it is never attached.
- `/compose` (628 lines, still unreviewed) creates a *parent* and weights children.
  That job is allocation, which is now the rebalance workflow in Allocate.

**Recommendation:** a strategy should be born in the Lab, from evidence — which
is what `research/promote` now does. Retire the empty-shell modal, and fold
Composer's genuine part (multi-strategy weighting) into Allocate. Not yet done;
`/compose` and the modal are both still live.

---

## 2b. The risk engine (built 2026-08-13)

Six new modules under `app/fund/`. Everything is measured from realised returns
of the names actually held; nothing is proxied, assumed, or defaulted. Every
block returns `measurable: false` **with a reason** rather than a zero.

| Module | What it answers |
|---|---|
| `statistics.py` | Is this Sharpe real, or a lucky draw from a parameter sweep? |
| `correlation.py` | Is this book diversified, or one bet wearing nine hats? |
| `riskmetrics.py` | Which position drives the *risk*? How fat is the tail? |
| `regime.py` | Is the **market** becoming fragile? |
| `stress.py` | What move breaches our halt? Would we survive a real crisis? |
| `riskengine.py` | Composes all of it; emits alarms; runs rebalance what-ifs |
| `factors.py` | Is it alpha or beta? Plus the PCA factor map |
| `rebalance.py` | A rebalance as a reviewable, event-sourced PLAN |

**API:** `GET /fund/risk/advanced` (the full view), `POST /fund/risk/whatif`
(proposed allocation vs current, read-only).

### What each one actually implements

- **Effective bets** — `diversification_ratio²`. Nine positions currently behave
  like **4.0** independent bets. Position-count is not diversification.
- **Stress correlation** — book vol is 20.3%; at correlation 1 it is 40.4%. That
  20-point gap is the diversification benefit being assumed, and it is the first
  thing a crisis removes (the "phase-locking" Chan/Getmansky/Haas/Lo document).
- **Euler risk decomposition** — components sum *exactly* to portfolio vol
  (residual asserted at 0). Currently INTC is **11% of capital and 35% of risk**;
  XLE has a *negative* risk share, i.e. it hedges the rest.
- **Expected Shortfall at 97.5%**, not VaR — the Basel FRTB standard. VaR ignores
  everything past the threshold and is not subadditive, so it can penalise
  diversification. Historical simulation, so fat tails are included by construction.
- **EWMA covariance** (RiskMetrics λ=0.94) alongside equal-weighted. The *ratio*
  is the regime signal — EWMA well above the long window means every risk number
  built on the long window is stale-low.
- **Financial Turbulence** (Mahalanobis distance) over 11 SPDR sector ETFs, and
  separately over our own holdings. Causal by construction: each day is scored
  against only the days preceding it.
- **Absorption Ratio** (Kritzman, Li, Page & Rigobon 2010) — verified against the
  paper, including that Equation (1)'s variances are **exponentially weighted with
  a 250-day half-life**, which I initially got wrong. ΔAR is Equation (2), the
  15-day vs 1-year standardised shift, +1σ threshold. Their base rates are carried
  in `AR_EMPIRICAL` so the UI states them instead of implying a forecast — every
  one of the 1% worst monthly drawdowns 1998–2010 was preceded by a spike, and
  stocks frequently rose after one. **Near-necessary, not sufficient.**
- **Reverse stress** — not "what if −20%" but "what move halts us". Currently a
  **10.6% fall across every holding**.
- **Historical replay** — real returns from real dated windows (COVID, Q4 2018,
  2022, SVB, Aug 2024 carry unwind) applied to today's exact weights.
- **Sharpe honesty** — Lo (2002) standard error and the autocorrelation-corrected
  annualisation (positive serial correlation makes √252 *overstate* Sharpe);
  Bailey & López de Prado minimum track record length and expected-max-Sharpe
  under N trials.

### Findings this produced immediately
- A pure-noise series shows an apparent annual Sharpe of **1.13** — flagged as
  indistinguishable from zero, 399 observations short of provable.
- **Every** historical crisis replay breaches the 10% drawdown halt (2022 would
  cost −29.2%, COVID −27.3%) while the book sits comfortably inside every limit.
  That gap is now its own alarm (`historical_survivability`) — a book can pass
  every limit and still be unable to survive a repeat of something real.

### New limits (`RiskLimits`)
`min_effective_bets` 2.0 · `max_avg_correlation` 0.75 ·
`max_strategy_correlation` 0.90 · `max_risk_concentration_pct` 0.50 ·
`max_expected_shortfall_pct` 0.05

Also: **the percentage cash floor is now enforced pre-trade.** It previously
existed only as a post-hoc alarm, so the book could be traded to zero cash and
merely told about it afterwards. A floor that only warns after the fact is not a
floor.

### Bugs this work surfaced in itself
- `np.cov` collapses a single-column input to a 0-d scalar — a **one-position
  book** would have broken every matrix operation downstream. Caught by a test,
  fixed with `atleast_2d`.
- The rebalance what-if normalised weights to *gross*, so de-risking into cash
  reported identical volatility and ES. Now NAV-relative, so cash dilutes risk.
  (Effective bets is deliberately still scale-invariant — holding cash does not
  make the remaining names any more independent of each other.)

---

## 2c. Firestore migration (tomorrow's job)

The ledger is a complete, replayable event log in
`ClarkHarness/.firestore_local_db.json`. Migration is: point at Firestore and
replay events in `seq` order. Two things to know before starting.

**The backfill endpoint hard-refuses production by design** (`403`), so the
migration must be a deliberate script, not an API call.

**A safety bug was fixed today that you must not reintroduce.**
`initialize_firebase()` reported `env=mock` under `USE_FAKE_FIRESTORE=1` while
still returning a client wired to the real project — the in-memory swap happens
in `main.py`, so the *app* was safe but a *standalone script* was not.
`reconcile_broker.py --apply` would have written to the real append-only ledger
believing it was local; it only surfaced because production was quota-exhausted
and threw 429 instead of succeeding. `db()` now refuses when the in-memory store
was never installed. Keep that guard.

Also still true: **Firestore free-tier quota was exhausted** on `hedgefund-ae96c`,
and the snapshot/polling fixes for it have **never been verified against the real
ledger**. Verify before trusting any production read.

---

## 2d. Intraday NAV telemetry (new)

`app/fund/intraday.py` + `GET /fund/nav/intraday?minutes=N`, charted on Allocate
with 30m / 2h / 6h / 1d windows.

These are **samples, not struck NAV**, and the distinction is enforced rather
than documented: they live in memory, vanish on restart, and carry
`struck: false`. Striking NAV every minute to make a chart smooth would flood an
append-only ledger with hundreds of events a day and destroy the meaning of "the
day's NAV". The sampler self-throttles to ~1/minute and the buffer is bounded.

The chart prefers the intraday trace and falls back to struck marks, saying which
it is showing. Below three points it states the fact instead of drawing a
two-point line and calling it a trace.

---

## 3. Next tasks, in the order I would do them

### 1. Python IDE in the Lab (asked for; scope it honestly first)
The ask is a TradingView/Pine-Script feel: write code, hit run, the tester runs
**your** code — one coherent piece.

Today's Lab uses **templates + parameters** (`sma`, `rsi`, `macd`, …). The old
`PythonCodeEditor` component still exists but was never connected to anything —
the code in it was decoration, and the deployed strategy is a config blob
(`{"type":"sma","fast":10,"slow":30}`). **The editor and the strategy have never
been the same artifact.** That is the real gap behind "end-to-end".

Making it genuine means executing user Python server-side, which is a security
problem, not a UI one. Three options, cheapest first:

- **(a) Show the generated code.** The editor displays the signal function for the
  chosen template and params, read-only. Honest, no execution, makes the
  connection visible. A day.
- **(b) Restricted DSL.** User writes a signal expression over `prices`/indicators,
  evaluated in a sandbox with no imports, no I/O, a step budget. Real authoring,
  bounded risk. Perhaps a week.
- **(c) Full Python sandbox** (subprocess, seccomp/container, resource caps). What
  QuantConnect actually does. Weeks, and it is infrastructure work.

**Do not skip straight to (c) because it sounds right.** Decide (a) vs (b) first.

### 1b. Rebalance approval queue (done)
`app/fund/rebalance.py`. A rebalance is a BATCH decided as one thing, so the plan
is the unit that gets proposed, analysed and approved — event-sourced via
`RebalanceProposed/Approved/Declined`. The queue exists to put a gap between
deciding and doing, which creates the hazard it then engineers against: **the
world moves while a plan sits.** So approval never trusts the proposal —
it re-prices, re-checks the kill switch, re-runs the pre-trade gate on every
order, and reports price drift and plan age to the reviewer.

Orders are rebuilt from the plan's **targets**, not replayed from its stored
quantities: at proposal AAPL might be underweight and the plan BUYS it; if it
then doubles it is overweight and the correct action *inverts to a SELL*.
Replaying the stored quantity would buy more of the thing that just ran up.

It also checks the **destination** against the mandate. The pre-trade gate sees
one order at a time and structurally cannot see that nine individually legal
orders add up to a strategy above its cap — that gap let a test push tech to 45%
against a 40% cap, and now warns before proposing.

### 2. 3D surfaces beyond the loss surface
`/risk` now renders an Expected-Shortfall surface over (correlation x horizon)
via plotly, with the book's measured correlation marked. The obvious next one is
in the **Lab**: a parameter-sweep surface (fast MA x slow MA -> Sharpe) with the
selection-noise threshold drawn as a plane. `statistics.expected_max_sharpe`
already computes that plane. A sharp isolated peak is an overfit; a broad plateau
is robust — and that is far easier to *see* than to explain.

### 3. Decision outcomes on Decide
Nothing tells Rushi whether his approvals worked out. A "recently decided" strip
showing each past approval with what happened to it closes the loop where the
decision was made. This is the piece of the Decide/Review merge idea that is
unambiguously right.

### 4. Strategy detail view (the missing object)
There is still no single place showing one strategy's whole life — thesis, code,
backtest, allocation, positions, risk, P&L, state history. Everything is smeared
across tabs. This is the object the IA is missing, and it would serve both the
researcher and the operator.

### 5. Verify the quota fixes against the real ledger
When quota resets: confirm snapshots engage (`fund_snapshots` collection appears)
and that `/fund/risk/monitor` no longer does four full scans.

### 6. Supabase migration (decided in principle, not started)
An append-only log keyed by monotonic `seq` is a table, not a document store.
`events where seq > N` is a B-tree scan in Postgres and a metered per-document
read in Firestore, so replay cost grows forever. **15 call sites across 5 files**
(`events.py`, `snapshots.py`, `projections/nav.py`, `connectors/paper.py`,
`demo_seed.py`) — everything else already goes through `EventStore`. No data to
migrate. Also unlocks a `UNIQUE` constraint on `seq`, which nothing enforces today.

---

## 4. Open questions for the humans

- **Thesis agent (Abhishek).** Parked. Before it writes into the system, `ThesisView`
  needs **provenance** — source URL, author, date, the reasoning chain, and what
  argues against it. Today it has `claim` and `key_risks` and no source at all, so
  Rushi cannot judge a machine-generated thesis. Expected volume matters too: 3–5
  a day is a readable list, 20–50 is a triage engine, and those are different
  products.
- **Vishesh's "all portfolios."** The spine models one fund with one NAV and one
  unit ledger. If he oversees several books, that is a multi-book model and it is
  far cheaper to design before F&F money than to retrofit after.
- **The legal question.** Live the moment friends-and-family cash is pooled. Not a
  code problem; get it checked.

---

## 4b. Dead code removed today
13 unreferenced Studio components deleted (verified zero imports app-wide):
`ApprovalsPanel`, `AuditLogFeed`, `BacktestModal`, `ClarkActionBar`,
`CreateStrategyModal`, `OrderBlotter`, `PythonCodeEditor`, `RebalanceModal`,
`RiskPanel`, `StrategyDetailModal`, `StrategyManageModal`, `ThesisPanel`,
`VisualStrategyCanvas`.

Two are worth knowing about because planned work referenced them, and both are
recoverable from git history:
- **`PythonCodeEditor`** — the Lab IDE starting point. It was never wired to
  anything, so it was decoration, but retrieve it if you build the IDE.
- **`StrategyDetailModal`** — a starting point for the strategy detail view,
  which is still a listed next task.

---

## 5. Traps — things that already bit us

- **Passing tests prove nothing about honesty.** The composite rollup synthesised a
  smooth equity curve for children lacking backtests, reporting **max drawdown
  0.0 and Sharpe 1.9e14** — a flawless strategy that did not exist. Suite was
  green throughout. Read the logic, not the checkmark.
- **A zero is a claim.** Decide rendered "Pending 0 · awaiting approval" with the
  database unreadable while a real order was in flight. Unknown must render `—`
  or say "unknown", never `0`. Same class as the fabricated numbers we deleted.
- **Silence must never look like safety.** The risk bar says "cannot confirm limits
  are being enforced" when it cannot read them, and Monitor says "this is NOT an
  all-clear". Keep that.
- **NAV folds from the event log only.** A previous change made `compute()` return
  live Alpaca equity with a hardcoded `units_outstanding` fallback that forced
  nav/unit to ~$1.00 and destroyed the unit ledger. Reverted in `f0b18c9`. Broker
  equity is a **comparison** (`GET /fund/venue/reconcile`), never the truth.
- **Reconciliation traps.** A prior repair adopted positions via synthetic
  `alpaca_adopt_*` events with no client_order_id; replaying the real fills on
  top would have written 15 phantom AAPL and 6 phantom MSFT into the permanent
  log. `BrokerBackfill.plan()` is read-only and idempotent by coid — always dry
  run first.
- **Deleted as fabricated, do not resurrect:** `sentinel.py`, `pair_arb.py`,
  `macro_regime.py`. They served invented numbers as observed market data, and
  sentinel auto-wrote signed theses into the real event log.
- **`simulation.py` is kept but its betas are assumptions**, not measurements. It
  reports `proxied_symbols` and `sensitivities_are_assumptions` for exactly that
  reason — keep both visible in any UI that renders it.
- **`total_return` is a fraction in one place and a percent in another.** The
  backtester returns `0.74` (74%); composite metrics return `74.0`; `demo_seed`
  stored percents. Each consumer is currently self-consistent, but the same field
  name means two things. Check units before doing arithmetic on it.
- **Strategy quality:** the deployed SMA 10/30 returns **+74%** on INTC where buy &
  hold returns **+389%** (Sharpe 1.22 vs 2.40). It underperforms doing nothing.
  Fine as a plumbing test; do not mistake it for alpha.
- **`lookback_days` is CALENDAR days, not trading days.** Asking for 250 yields
  ~173 observations. The UI states the real count ("173 trading days to
  2026-08-12"); do not assume the parameter is a sample size.
- **Correlation is backward-looking and the regime indicators are not forecasts.**
  A +1 sigma absorption-ratio shift preceded every one of the 1% worst monthly
  drawdowns in 1998-2010 — and stocks often rose after one. Present base rates,
  never predictions.
- **Risk analytics are read-only by construction.** `/fund/risk/whatif` places no
  orders; rebalancing still goes propose -> gate -> approve. Keep it that way:
  the approval path is the only one with a kill switch on it.

---

## 6. Credentials

- **Nothing secret is committed, and it must stay that way.** `.env`,
  `firebase_service_account*.json` and `.firestore_local_db.json` are gitignored
  and none are in git history — verified with `git check-ignore` and `git ls-files`.
  `ClarkHarness/.env.example` documents every variable with no values, so a new
  developer can get running; send the actual keys out of band (password manager),
  never through the repo. The Firebase key is **full admin on the fund's ledger**
  and git history is permanent.
- **Rotate the Firebase service-account key** for `hedgefund-ae96c`. It was pasted
  into a chat transcript and sits in `~/Downloads`. Full admin on the fund's ledger.
- Alpaca paper keys were also pasted; low stakes, but regenerate when convenient.
- `.gitignore` covers `firebase_service_account*.json` and `.env` — verified with
  `git check-ignore`. Nothing sensitive is tracked.

---

## 7. Useful commands

```bash
# which book am I on?
curl -s localhost:8090/api/v1/fund/book

# does the book match the broker?
curl -s localhost:8090/api/v1/fund/venue/reconcile

# stateless backtest — no ledger needed, works during an outage
curl -s -X POST localhost:8090/api/v1/fund/research/backtest \
  -H "Content-Type: application/json" \
  -d '{"symbol":"INTC","strategy":"sma","fast":10,"slow":30,"lookback_days":365}'

# quotes for specific symbols — also ledger-free
curl -s "localhost:8090/api/v1/fund/market/quotes?symbols=INTC,F,PLTR"

# repair the book against the broker (DRY RUN — omit --apply)
./venv/Scripts/python.exe scripts/reconcile_broker.py
```

---

## What is new this session (2026-08-13, second half)

**Backend** — `app/fund/`
| module | what it is |
|---|---|
| `signals.py` | the signal→order loop. Proposes only; holds no approval path, so no change here can make the fund trade by itself. Dry run default, closed-market block, duplicate suppression, per-template parameter translation. |
| `custody.py` | dividends / interest / splits from the venue's activities, idempotent by Alpaca's activity id. Unmodelled types surfaced, splits refused rather than guessed. |
| `execution.py` | fills and closed round-trips per strategy, with distribution, streaks, holding periods, long/short split. |
| `tearsheet.py` | the research metric set: CAGR, Sortino, Calmar, drawdown recovery, benchmark alpha/beta/IR, PSR and the selection penalty. |
| `backtest.py` | `CostModel` — costs charged on notional traded, applied BEFORE returns are recorded so Sharpe and drawdown are post-cost. A zero cost is never silent. |
| `marketdata.py` | split/dividend adjusted, OHLCV carried through, intraday timeframes (`1Min`/`5Min`/`15Min`/`1Hour`). |

**Endpoints**: `/signals`, `/signals/run`, `/executions`, `/executions/chart`,
`/custody/plan`, `/custody/apply`.

**Frontend** — Monitor is the landing page. Nav is Monitor · Allocate · Lab ·
Risk; Decide is gone (approvals → Monitor, theses/memos → Lab, **not yet
moved**). New: `SignalsPanel`, `OrderFlow`, `MonitorGraphs`, `HaltControl`,
`LimitsEditor`, `SystemStatus`, `ExecutionAnalytics`, `ExecutionChart`.

### Known-good verification
- 324 backend tests, `tsc` clean, no new lint warnings
- all 18 touched endpoints return 200
- the two P&L projections (attribution and execution) agree on longs, short
  covers and cover-then-flip

### Open, in the order I would do them
1. **Clear the INTC breach** — propose + approve the sells on Monitor.
2. **Lab migration is half-done.** The nav says Lab holds "theses, memos" but
   only the label moved; the thesis UI has no home. `createThesis`, `getTheses`,
   `recordPostmortem` etc. exist in `fund_api.ts` and are unused — that is the
   client library waiting for this UI, not dead code.
3. **Replace fill polling with the `trade_updates` websocket.** `TradingStream`
   is available in alpaca-py 0.43.5. Polling means a fill is invisible for up to
   an interval; keep the poller as an idempotent backstop.
4. **Market hours exist only inside the signal runner.** Settlement,
   reconciliation and NAV striking still run identically at 3am.
5. **`/compose` is orphaned** — live route, not in the nav, linked only from the
   Allocate header. Fold in or delete.
6. **No fee accrual.** Fine for friends & family, but it should be a stated
   decision rather than an absence.
7. **Rotate credentials.** The Firebase service account and Alpaca keys were
   pasted into a chat transcript.

### Things that are deliberately NOT bugs
- Splits are refused, not applied — Alpaca reports the change in quantity, not
  the resulting position, and a guessed ratio corrupts the share count.
- The signals panel does not auto-refresh; evaluating pulls bars for every
  symbol and would rate-limit the free feed.
- Resume is as many clicks as halt. Turning risk back on should never be easier
  than turning it off.
