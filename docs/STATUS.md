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
- **G1 · Money/units use `float`.** Rounding error accumulates across NAV/unit, ownership %, and
  payouts — a real latent bug for anything holding real money. Move to `Decimal` (or integer minor
  units) end-to-end. *Cheap now, painful later.*
- **G2 · NAV-strike timing not enforced.** `confirm_subscription` mints at the live `compute()` rather
  than a discrete *next strike*; "don't strike over in-flight fills" isn't scheduled. Acceptable for
  v0 manual ops, but the discipline should be explicit.
- **G3 · No transactional state guard on approve.** The propose→approve state check reads then writes
  without an aggregate-level transaction; two racing approvals could both pass. Low likelihood at F&F
  scale, real at scale.

### Security / ops — blockers before any external user
- **G4 · No authN/Z.** `GET /fund/lp/{id}` exposes any LP's position; approve/decline are
  unauthenticated. **Must-fix before a single friend gets a link.**
- **G5 · Firestore composite indexes missing.** Queries like `where(seq>) + order_by(seq)` and
  `where(aggregate_id==) + order_by(seq)` need a `firestore.indexes.json`, or they fail in prod.
- **G6 · No scheduled NAV strike / async fill poller / reconciliation.** The LP value trend needs
  periodic strikes; real IBKR fills settle async and need a poller; the reconciler (event book vs.
  venue truth) is designed but unbuilt.

### Platform — the stated priority
- **G7 · Strategy layer absent** — `strategy_id` tagging, per-strategy attribution, the registry, and
  the studio (create/backtest/deploy/allocate).
- **G8 · Operator cockpit absent** — the strategy-aware `/ops` dashboard.
- **G9 · IBKR connector absent** — paper only; blocked on an IBKR paper account.
- **G10 · Brain not wired** — `krypton_clark` ↔ spine is the agentic premise and isn't connected yet.

### Hygiene
- **G11 · No pytest suite / CI.** Smoke scripts assert but aren't a regression net; risk grows as the
  surface multiplies.
- **G12 · Minimal error handling / observability.** No structured logging or config module.

---

## 4. Prioritized backlog

**P0 — harden the base (do before features multiply the surface):**
1. Money precision: `Decimal` end-to-end (G1).
2. Real pytest suite from the smoke scenarios + CI (G11).
3. `firestore.indexes.json` + verify query patterns (G5).

**P1 — the platform (stated priority):**
4. Strategy layer: `strategy_id` tagging + attribution projection + registry (G7).
5. Operator cockpit `/ops`, strategy-aware (G8).

**P2 — make it live:**
6. `IBKRConnector` (paper→live) + async fill poller + reconciliation (G9, G6). _Needs IBKR paper account._
7. Scheduled NAV strike (G6).
8. AuthN/Z (G4). **Gate: must land before any external LP access.**

**P3 — the vision:**
9. Wire the brain (`krypton_clark`) to the spine — fund skills + generalize the pay-interrupt to order approval (G10).
10. quantconnect v2 — thin signal adapter posting tagged proposed orders.

---

## 5. Recommended next move

Do **P0** before building the strategy layer and cockpit. Money precision and a
test suite are cheapest to fix now and get more expensive with every feature that
depends on them; the index file is a one-shot go-live unblocker. Then P1
(strategy layer → cockpit), which is the priority arc.
