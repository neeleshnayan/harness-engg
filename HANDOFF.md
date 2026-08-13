# Krypton Fund — session handoff

Written 2026-08-13. Everything below was verified at the time of writing, not
remembered. Where something is unverified it says so.

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

# seed it: $2k, one strategy, 3 fills at live prices, 1 order left pending
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
cd ClarkHarness && ./venv/Scripts/python.exe -m pytest -q     # 112 passing
cd ../KryptonPay && npx tsc --noEmit                          # 0 errors
```
Do **not** run `npm run build` while `npm run dev` is running — it overwrites
`.next` and desyncs the dev server's module map. That broke the app twice.

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

### Studio (four tabs, one per job)
| Route | Job | Lines | State |
|---|---|---|---|
| `/clark/studio` | **Decide** — what needs a human | 218 | rebuilt |
| `/clark/studio/lab` | **Lab** — backtest and iterate | 314 | rebuilt |
| `/clark/studio/allocate` | **Allocate** — how much goes where | ~300 | rebuilt |
| `/clark/studio/monitor` | **Monitor** — is it okay, did it fill | ~400 | rebuilt |
| `/clark/studio/compose` | multi-strategy allocator | 628 | **not reviewed** |

`/strategies` and `/risk` 307-redirect. `/theses`, `/approvals`, `/review` are
deleted. Review's content was distributed: attribution to Allocate, NAV record
and audit trail to Monitor.

Risk is deliberately **not** a tab — it applies everywhere, so it is a persistent
bar under the header on every page, plus the full cockpit in Monitor.

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

### 2. Decision outcomes on Decide
Nothing tells Rushi whether his approvals worked out. A "recently decided" strip
showing each past approval with what happened to it closes the loop where the
decision was made. This is the piece of the Decide/Review merge idea that is
unambiguously right.

### 3. Strategy detail view (the missing object)
There is still no single place showing one strategy's whole life — thesis, code,
backtest, allocation, positions, risk, P&L, state history. Everything is smeared
across tabs. This is the object the IA is missing, and it would serve both the
researcher and the operator.

### 4. Verify the quota fixes against the real ledger
When quota resets: confirm snapshots engage (`fund_snapshots` collection appears)
and that `/fund/risk/monitor` no longer does four full scans.

### 5. Supabase migration (decided in principle, not started)
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

---

## 6. Credentials

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
