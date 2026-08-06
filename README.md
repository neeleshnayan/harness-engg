# ClarkHarness — Krypton Fund

An agentic operator + LP interface for the Krypton Fund. A single event-sourced
command spine orchestrates venue-agnostic execution, a unit ledger, NAV, risk,
and a complete audit log — with a human approving every financial action.

> **v0 scope:** 20 friends & family, one pooled managed-fund experience.
> Deposits are wired to the manager and recorded off-platform (no wallets, no
> on-chain rail, no payments/money-transmission surface). Investing runs through
> IBKR with harness-proposed, human-approved orders. Wallets / self-custody come
> much later behind the same connector seam.

## Architecture

See **[docs/architecture.md](docs/architecture.md)** for the full design — the
command lifecycle, event catalog, projections, connector interface, risk engine,
unit-ledger/NAV accounting, and the multi-strategy model.

**New here?** Start with the **[handoff](docs/HANDOFF.md)** — the cross-repo
summary of what's built, where, what's verified, and what's left.

For **current build state, the decisions log, gap analysis and the prioritized
backlog**, see **[docs/STATUS.md](docs/STATUS.md)**. To run it locally end-to-end,
see **[docs/LOCAL_E2E.md](docs/LOCAL_E2E.md)**; to deploy and verify on Alpaca
paper, the **[go-live runbook](docs/DEPLOY.md)**.

```
Command → Risk Gate → Human Approval → Connector → Event Log → Projections
```

The event log is the single source of truth; NAV, the unit ledger, positions,
and the audit trail are all projections folded from it.

## Layout

```
app/
  main.py                FastAPI app (health + fund router)
  core/firebase.py       Firebase Admin init
  api/v1/fund.py         /api/v1/fund/* — propose/approve orders, NAV, positions, events
  schemas/fund.py        request models
  fund/                  the spine (see app/fund/README.md)
docs/architecture.md     the design spec
scripts/smoke_fund.py    end-to-end spine test (no Firebase needed)
```

## Run

```sh
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# place firebase_service_account.json in the repo root (git-ignored), then:
uvicorn app.main:app --reload
```

## Smoke test (no Firebase / no install)

Exercises the whole spine against an in-memory Firestore fake:

```sh
python3 scripts/smoke_fund.py
```

Runs deposit → propose → approve → fill → NAV strike, plus the idempotency
guard and a risk rejection.

## Tests

```sh
pip install -r requirements-dev.txt
pytest
```

`tests/` runs the spine and ledger-fairness suites against the in-memory
Firestore fake (no Firebase needed).
