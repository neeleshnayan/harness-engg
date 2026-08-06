# Krypton Fund — Status, Decisions & Gaps

_Living document. The single place to answer "where are we and what's next."_

---

## 1. Where we are

A standalone, event-sourced fund spine runs end-to-end (paper venue), with the
LP-facing view on top. Everything is on branch `claude/krypton-fund-agentic-j8r2mu`.

**Built and verified** (smoke tests against an in-memory Firestore fake — no live
Firebase needed):

| Piece | Module | Verified |
|-------|--------|----------|
| Append-only event store (global `seq`) | `app/fund/events.py` | ✅ |
| Venue-agnostic connector + paper venue | `app/fund/connectors/` | ✅ idempotent replay |
| Positions / cash / units projection | `app/fund/projections/positions.py` | ✅ |
| NAV (`compute`/`strike`/`history`) | `app/fund/projections/nav.py` | ✅ |
| Per-LP holdings | `app/fund/projections/holdings.py` | ✅ |
| Risk gate (hard tier) | `app/fund/risk.py` | ✅ rejects oversized order |
| Command pipeline (propose→approve→execute) | `app/fund/pipeline.py` | ✅ + idempotency guard |
| Unit ledger (subscribe/redeem) | `app/fund/ledger.py` | ✅ fairness + NAV-neutrality |
| HTTP surface | `app/api/v1/fund.py` | compiles |
| LP view | `web/lp.html` (`GET /lp`) | renders (demo + live) |

Smoke tests: `scripts/smoke_fund.py`, `scripts/smoke_ledger.py`.

**Repo map (whole system):**
- `ClarkHarness` — the fund (spine + views). ← all fund work lands here.
- `krypton_clark` — the strands brain (skills, memory, interrupt approval, LEAN/backtest engine).
- `clark_mcp` — thin MCP proxy to the brain.
- `quantconnect` — old LEAN/Yearn rig; to be rebuilt as a thin signal adapter.
- `kryptonpay_backend` — the payments product; **out of scope** for the fund (spine moved out of it).

---

## 2. Decisions log

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Event-sourced spine; log is the single source of truth | audit/reconciliation/idempotency all fall out of it |
| D2 | Home = ClarkHarness, standalone | keep the fund clear of KryptonPay's regulatory surface |
| D3 | Custody pooled; deposits **off-platform**, recorded by the manager | no payments/money-transmission surface in v0 |
| D4 | IBKR execution **connector-owned**; LEAN only signals | human approval has no seam inside LEAN's autonomous loop |
| D5 | Execution posture = harness proposes, **human approves**, then executes | AI orchestrates, never custodies |
| D6 | Strands for the *episodic* brain; 24×7 = deterministic workers | don't put an LLM in a live fund's hot loop |
| D7 | Multi-strategy **before launch**; one pooled account, strategies as tags | attribution via a projection, forensics via event replay |
| D8 | Money at F&F scale; legal is a parallel, non-blocking workstream | ship and learn |
| D9 | Execution venue = **Alpaca** (paper first), not IBKR | API-first, no Gateway to babysit in a 24×7 cloud service, commission-free + fractional; IBKR remains a future connector via the same seam |
| D10 | Alpaca **MCP server** is for the brain later, not the spine | keep the LLM out of the deterministic money path |
| D11 | **No LEAN in v0** — backtesting behind a `Backtester` seam, lightweight impl | Alpaca covers execution + data; LEAN's only role would be backtesting, and it's heavy to operate; plug it in later as another `Backtester` if needed |

---

## 3. Gap analysis (honest)

### Foundational correctness — fix before piling on features
- **G1 · Money/units precision** — ✅ addressed. `Decimal` end-to-end via `app/fund/money.py`: exact
  arithmetic and exact stored truth (Decimals serialized to strings in Firestore); connectors stay
  `float` at the venue edge; JSON responses downcast to `float` for display only. Guarded by the tests.
- **G2 · NAV-strike timing not enforced.** `confirm_subscription` mints at the live `compute()` rather
  than a discrete *next strike*; "don't strike over in-flight fills" isn't scheduled. Acceptable for
  v0 manual ops, but the discipline should be explicit.
- **G3 · No transactional state guard on approve.** The propose→approve state check reads then writes
  without an aggregate-level transaction; two racing approvals could both pass. Low likelihood at F&F
  scale, real at scale.

### Security / ops — blockers before any external user
- **G4 · No authN/Z.** `GET /fund/lp/{id}` exposes any LP's position; approve/decline are
  unauthenticated. **Must-fix before a single friend gets a link.**
- **G5 · Firestore composite indexes** — ✅ addressed. `firestore.indexes.json` ships the
  `fund_events (aggregate_id, seq)` composite; single-field range+order queries use auto indexes.
  (Still needs `firebase deploy --only firestore:indexes` at deploy time.)
- **G6 · Async settlement / reconciliation / scheduled strike** — ✅ built (3 tests). Approve does one
  poll (instant venues settle now; async stay `working`); `poll_open_orders()` drives in-flight orders
  to terminal (partial→fill books once; fail-after-partial books the executed portion). `Reconciler`
  compares the event book vs. venue `positions()` → `ReconciliationMismatch`. A guarded scheduler in
  the app lifespan settles every ~30s and strikes NAV + reconciles every ~30min (env-configurable).
  Endpoints: `POST /fund/orders/settle`, `POST /fund/reconcile`.

### Platform — the stated priority
- **G7 · Strategy layer** — ✅ spine built (5 tests). `strategy_id` tags orders/fills;
  `StrategyService`/`StrategyRegistry` (event-sourced lifecycle: draft→backtested→deployed→paused +
  target allocation); `StrategyAttribution` folds tagged fills → per-strategy exposure/P&L; endpoints
  under `/fund/strategies`. ✅ Backtest step: `Backtester` seam + `SimpleBacktester` (no LEAN, D11) +
  `POST /fund/strategies/{id}/backtest/run`. Still: studio UI + wiring Alpaca historical bars into it.
- **G8 · Operator cockpit** — ✅ built. Dark, live-refreshing `/ops`: NAV strip, pending-approval
  queue (Approve/Decline), per-strategy cards (target vs. actual + P&L), positions, LP book, activity
  log. Reads `/fund/*`; demo fallback. Pending-queue endpoint + `OrdersProjection` (1 test).
- **G9 · Live venue** — ✅ `AlpacaConnector` built (execution + venue-side idempotency via
  `client_order_id`; pure mappers unit-tested). Env-selected (`ALPACA_API_KEY` set → Alpaca, else
  paper). Still: async fill poller + reconciliation, and set `ALPACA_SECRET_KEY` in the deploy env to
  go live on the paper account.
- **G10 · Brain wired** — ✅ `krypton_clark` has a `fund` skill (auto-discovered as `consult_fund`,
  4 tests) that reads the spine and proposes orders through the same human-approval interrupt as
  `krypton_pay` (resumed by `clark_mcp`'s `krypton_approve_interrupt`). Config via `CLARK_HARNESS_URL`.
  Still: point it at the deployed harness; a studio UI is separate.

### Hygiene
- **G11 · Test suite** — ✅ addressed. `tests/` runs 8 pytest cases (spine + ledger fairness) against
  the in-memory fake. CI wiring still to do.
- **G12 · Minimal error handling / observability.** No structured logging or config module.

---

## 4. Prioritized backlog

**P0 — harden the base — ✅ done:**
1. ✅ Money precision: `Decimal` end-to-end (`app/fund/money.py`) (G1).
2. ✅ pytest suite (`tests/`, 8 cases). Still: wire CI (G11).
3. ✅ `firestore.indexes.json` (G5). Still: deploy the indexes.

**P1 — the platform (stated priority):**
4. ✅ Strategy layer: tagging + attribution + registry + backtest seam (G7, D11). Still: studio UI + Alpaca-data into backtests.
5. ✅ Operator cockpit `/ops`, strategy-aware (G8).

**P2 — make it live:**
6. ✅ `AlpacaConnector` (execution) + ✅ async fill poller + ✅ reconciliation (G6). _Alpaca paper ready; set the secret in env._
7. ✅ Scheduled NAV strike + settlement + reconcile worker (G6).
8. AuthN/Z (G4). **Gate: must land before any external LP access.**

**P3 — the vision:**
9. ✅ Wire the brain (`krypton_clark`) to the spine — `fund` skill + pay-interrupt generalized to order approval (G10).
10. quantconnect v2 — thin signal adapter posting tagged proposed orders.

---

## 5. Recommended next move

P0 + P1 done; execution + async settlement + reconciliation + scheduler done;
Alpaca connector (with price cache) done. **Go-live prep** shipped:
`scripts/preflight.py` + the [`DEPLOY.md`](./DEPLOY.md) runbook — set
`ALPACA_SECRET_KEY`, run preflight, seed LPs/strategy, verify the approve →
Alpaca → fill → NAV loop.

Remaining before real LPs: **auth** (G4 — `/fund/lp/{id}` and writes are open;
the hard gate before sharing links). Then **wire the brain** (P3, the agentic
premise), plus studio UI, Alpaca-bars into backtests, and CI.
