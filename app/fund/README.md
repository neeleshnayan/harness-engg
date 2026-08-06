# `app/fund` — the harness spine (Step 1 scaffold)

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

HTTP surface: `app/api/v1/fund.py`, mounted at `/api/v1/fund/*`.

## Swapping the venue

The only place a venue is named is the wiring block in `app/api/v1/fund.py`:

```python
_connector = PaperConnector()   # Step 2: IBKRConnector()
```

Nothing else changes — the pipeline, projections and API are venue-agnostic.

## Smoke test

The spine runs without a live Firestore via an in-memory fake (no
`firebase_admin` install needed): see `scripts/smoke_fund.py`, which
exercises deposit → propose → approve → fill → NAV strike, the idempotency
guard, and a risk rejection.

## Not yet (later steps)

- **Step 2** — `IBKRConnector` (paper account) + async fill poller + reconciler.
- **Step 3** — subscribe/redeem commands: two-phase cash confirm, mint/burn units at struck NAV.
- **Step 4** — risk threshold/escalation tier.
- Scheduled NAV strike + reconciliation (reuse the existing 30-min scheduler pattern).
