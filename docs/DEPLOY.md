# Go-live runbook — Krypton Fund on Alpaca paper

v0: pooled managed fund for 20 F&F, execution on **Alpaca paper**, deposits
recorded off-platform. This is the checklist to get the service live and verify
the full loop.

## 1. Environment variables

Set these in the deploy env (Railway variables / local `.env` — never commit):

| Var | Purpose |
|-----|---------|
| `FIREBASE_SERVICE_ACCOUNT_JSON` | path to the Firebase Admin service-account JSON |
| `ALPACA_API_KEY` | Alpaca key id (e.g. the paper key) |
| `ALPACA_SECRET_KEY` | Alpaca **secret** — set here only, never in chat/repo |
| `FUND_MODE` | `test` / `alpaca-paper` / `alpaca-prod`. REQUIRED, no default. Decides both the venue and the ledger. `ALPACA_PAPER` was retired 2026-08-22 and is no longer read anywhere. |
| `FUND_STORE` | `postgres` / `firestore`. REQUIRED, no default. |
| `ALPACA_PRICE_TTL` | price cache seconds (default `5`) |
| `CORS_ORIGINS` | comma-separated origins for the LP view / cockpit |
| `ENABLE_SCHEDULER` | `true` (default) runs settle/strike/reconcile worker |
| `SETTLE_INTERVAL_SECONDS` / `STRIKE_INTERVAL_SECONDS` | worker cadence (default 30 / 1800) |

With `ALPACA_API_KEY` set, execution routes through Alpaca automatically;
unset, it stays on the in-Firestore paper connector.

## 2. Deploy

```sh
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port $PORT   # railway.toml already does this
```

Deploy the Firestore composite index once:

```sh
firebase deploy --only firestore:indexes   # uses firestore.indexes.json
```

## 3. Preflight (read-only)

```sh
python3 scripts/preflight.py
```

Confirms Firebase reads and the Alpaca account are reachable (prints status,
cash, buying power). Places no orders.

## 4. First-run seeding

1. **Record deposits** as friends wire you (off-platform), one per LP:
   `POST /api/v1/fund/lp/subscriptions {lp_id, usd_amount, lp_name}` then
   `…/subscriptions/{id}/confirm {actor}` once the cash lands → units mint at NAV.
2. **Create a strategy:** `POST /api/v1/fund/strategies {name}` →
   `…/backtest/run {prices, strategy}` → `…/state {state:"deployed"}` →
   `…/allocation {target_pct}`.

## 5. Verify the live loop

1. Open the **cockpit** at `/ops` — NAV strip populated, LP book shows the seeded LPs.
2. **Propose** a small order: `POST /api/v1/fund/orders/propose {symbol, side, qty, strategy_id}`.
3. It appears in the cockpit's **pending queue** with an impact preview.
4. **Approve** it (button, or `POST /api/v1/fund/orders/{id}/approve {approver}`).
   Alpaca accepts it; the order goes **working**.
5. The scheduled worker (or `POST /api/v1/fund/orders/settle`) polls it to
   **filled**; positions + NAV update.
6. `POST /api/v1/fund/reconcile` → book matches Alpaca `positions()` (no mismatches).
7. Each LP's view at `/lp?lp=<id>` shows their revalued position.

## 6. Risk knobs

Defaults live in `app/fund/risk.py` (`RiskLimits`): max single-name 35% of NAV,
max single order 50% of NAV, min cash buffer 0. Tune before real sizing —
consider a non-zero cash buffer.

## 7. Guardrails in place

- Human approval on every order (nothing auto-executes).
- Idempotent execution (Alpaca `client_order_id` = our order id).
- Decimal money; event-sourced audit log; reconciliation against venue truth.

## Not yet (do before external LP links)

- **Auth** — `/fund/lp/{id}` and the write/approve routes are currently open.
  Add authn/z before sharing LP links or exposing the cockpit publicly.
