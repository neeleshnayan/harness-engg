# Separating the real fund's book from staging

The fund's ledger is append-only. Connecting to the wrong Firestore project is
not an undoable mistake — demo LPs, seeded cash and test strategies written into
the real book can only ever be *compensated for*, never removed. The current
staging book is the proof: it carries `fbtest` and `fix5` holding 10,000 units of
capital that was never funded, plus a synthetic `lp_alpaca_import` LP holding
99,985.85 units — roughly 92% of the fund.

So the real fund gets its own project, and the code makes the active book
impossible to mistake.

## Configuration

| Variable | Staging | Production |
|---|---|---|
| `FIREBASE_SERVICE_ACCOUNT_JSON` | `firebase_service_account.json` | `firebase_service_account.hedgefund.json` |
| `FUND_ENV` | `staging` (default) | `production` |
| `USE_FAKE_FIRESTORE` | `0` (or `1` for offline dev) | **must be `0`** |

`FUND_ENV` defaults to `staging`, so the safe value is the one you get by
forgetting to set it.

## Setting up the production book

1. In the new Firebase project (`hedgefund-ae96c`), create a service account:
   **Project settings → Service accounts → Generate new private key**.
2. Save the JSON as `ClarkHarness/firebase_service_account.hedgefund.json`.
   **Confirm it is gitignored before saving it** — it is a credential.
3. Set the environment:
   ```
   FIREBASE_SERVICE_ACCOUNT_JSON=firebase_service_account.hedgefund.json
   FUND_ENV=production
   USE_FAKE_FIRESTORE=0
   ```
4. Start the spine and **verify the book before doing anything else**:
   ```
   curl -s localhost:8090/api/v1/fund/book
   ```
   Expect `{"project_id": "hedgefund-ae96c", "env": "production",
   "is_production": true}`. The boot log also prints
   `Fund book: project=… env=production (PRODUCTION — REAL MONEY)`.

## What the code enforces

- **Demo seeding is refused on production.** `seed_if_empty` returns early when
  `FUND_ENV=production`, regardless of whether the store looks empty.
- **Seeding is refused when emptiness cannot be proven.** If the check throws,
  it does not fall through to seeding.
- **The active book is always reportable** via `GET /fund/book` and the boot log.

## Starting the production book clean

Do **not** migrate the staging events. They contain the fabricated LPs and the
synthetic import entity described above. The real fund should begin from an empty
log, with:

1. Real subscriptions only — one `SubscriptionRequested` + `CashConfirmed` per
   actual investor, for money that genuinely arrived.
2. A funded Alpaca account whose starting cash matches the sum of those
   subscriptions, so `GET /fund/venue/reconcile` reads zero drift from day one.
3. Strategies created through the UI, not seeded.

Keep the staging project as it is. It is useful precisely because it is messy —
it is where the reconciliation, kill-switch and composer paths were exercised.

## Before real money

- `GET /fund/venue/reconcile` → `symbols_out_of_sync: 0` **and** `delta_usd` ≈ 0.
  Positions reconciling is not enough; cash must reconcile too.
- Risk limits reviewed and set deliberately (`GET /fund/risk/limits`), not left
  at defaults.
- The legal question checked. This goes live the moment friends-and-family cash
  is pooled, and it is not a code problem.
