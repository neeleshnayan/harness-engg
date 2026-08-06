# `app/fund` — the harness spine (Steps 1 + 3)

The event-sourced core the fund harness is built on. Everything the system
knows is derived by folding an append-only event log; audit, reconciliation,
NAV and the unit ledger are all projections over it. See the full design in
`ClarkHarness/docs/architecture.md`.

## Write path

```
propose_order → [risk gate] → ORDER_PROPOSED  (awaiting human approval)
approve_order → ORDER_APPROVED → connector.execute (idempotent)
             → ORDER_SUBMITTED → poll → ORDER_FILLED | ORDER_FAILED
decline_order → ORDER_DECLINED
```

The order id is the idempotency key handed to the connector, so a retry or
re-approval can never place a second order. A risk rejection and a human
decline are both events — the audit trail is complete by construction.

## Modules

| File | Role |
|------|------|
| `events.py` | `EventStore` + `EventType` — append-only Firestore `fund_events`, global `seq` via an atomic counter |
| `connectors/base.py` | the venue-agnostic `Connector` protocol + order/position types |
| `connectors/paper.py` | `PaperConnector` — in-Firestore simulation; `IBKRConnector` (Step 2) implements the same protocol |
| `projections/positions.py` | `PositionsProjection` — folds events into cash / positions / units outstanding |
| `projections/nav.py` | `NavService` — `compute()` / `strike()` NAV and NAV-per-unit → `fund_nav_snapshots` |
| `risk.py` | `RiskGate` — hard-reject tier (position/notional/cash limits); Step 4 adds thresholds |
| `pipeline.py` | `CommandPipeline` — the propose/approve/decline write path |
| `ledger.py` | `LedgerService` — subscribe/redeem: two-phase confirm, mint/burn units at NAV |
| `projections/holdings.py` | `HoldingsProjection` — per-LP units + value ("what do I own?") |

HTTP surface: `app/api/v1/fund.py`, mounted at `/api/v1/fund/*` (orders, NAV,
positions, LP subscribe/redeem, per-LP holdings, audit event log).

## Unit ledger

```
subscribe: SubscriptionRequested → (confirm) → CashConfirmed + UnitsIssued
redeem:    RedemptionRequested   → (confirm) → UnitsBurned  + PayoutSent
```

Units mint at the NAV-per-unit struck *before* the new cash is counted, so a
subscription never dilutes existing LPs (and a redemption is NAV-neutral).
Deposits/payouts move off-platform in v0; "confirm" is the manager attesting the
wire landed / the payout was sent.

## Swapping the venue

The only place a venue is named is the wiring block in `app/api/v1/fund.py`:

```python
_connector = PaperConnector()   # Step 2: IBKRConnector()
```

Nothing else changes — the pipeline, projections and API are venue-agnostic.

## Smoke test

The spine runs without a live Firestore via an in-memory fake (no
`firebase_admin` install needed):

- `scripts/smoke_fund.py` — deposit → propose → approve → fill → NAV strike, the
  idempotency guard, and a risk rejection.
- `scripts/smoke_ledger.py` — three LPs subscribe at different NAVs, the fund
  gains, everyone revalues pro-rata; a later subscription doesn't dilute, and a
  full redemption is NAV-neutral.

## Not yet (later steps)

- **Step 2** — `IBKRConnector` (paper account) + async fill poller + reconciler.
- **Step 4** — risk threshold/escalation tier.
- Scheduled NAV strike + reconciliation (reuse the 30-min scheduler pattern).
- LP-facing read UI on top of `/fund/lp/*`.
