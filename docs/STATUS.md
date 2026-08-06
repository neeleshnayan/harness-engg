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
- **G6 · No scheduled NAV strike / async fill poller / reconciliation.** The LP value trend needs
  periodic strikes; real IBKR fills settle async and need a poller; the reconciler (event book vs.
  venue truth) is designed but unbuilt.

### Platform — the stated priority
- **G7 · Strategy layer** — ✅ spine built (5 tests). `strategy_id` tags orders/fills;
  `StrategyService`/`StrategyRegistry` (event-sourced lifecycle: draft→backtested→deployed→paused +
  target allocation); `StrategyAttribution` folds tagged fills → per-strategy exposure/P&L; endpoints
  under `/fund/strategies`. Still: the studio UI + real backtest wiring into `krypton_clark`'s LEAN.
- **G8 · Operator cockpit** — ✅ built. Dark, live-refreshing `/ops`: NAV strip, pending-approval
  queue (Approve/Decline), per-strategy cards (target vs. actual + P&L), positions, LP book, activity
  log. Reads `/fund/*`; demo fallback. Pending-queue endpoint + `OrdersProjection` (1 test).
- **G9 · IBKR connector absent** — paper only; blocked on an IBKR paper account.
- **G10 · Brain not wired** — `krypton_clark` ↔ spine is the agentic premise and isn't connected yet.

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
4. ✅ Strategy layer: `strategy_id` tagging + attribution projection + registry (G7). Still: studio UI + LEAN backtest wiring.
5. ✅ Operator cockpit `/ops`, strategy-aware (G8).

**P2 — make it live:**
6. `IBKRConnector` (paper→live) + async fill poller + reconciliation (G9, G6). _Needs IBKR paper account._
7. Scheduled NAV strike (G6).
8. AuthN/Z (G4). **Gate: must land before any external LP access.**

**P3 — the vision:**
9. Wire the brain (`krypton_clark`) to the spine — fund skills + generalize the pay-interrupt to order approval (G10).
10. quantconnect v2 — thin signal adapter posting tagged proposed orders.

---

## 5. Recommended next move

P0 is done — the base is hardened (Decimal money, test suite, indexes). Next is
**P1: the strategy layer** (`strategy_id` tagging + per-strategy attribution +
registry) then the **strategy-aware operator cockpit** — the stated priority arc.
