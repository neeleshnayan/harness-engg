# Trading session checklist — Friday 2026-08-14

All times **ET** (the venue's clock). Market opens **09:30**, closes **16:00**.

---

## The one hard constraint today

**Day-trade budget: 1 used, 2 spare.**

F was bought and sold on 2026-08-13 — that was day trade 1 of 4. The **4th day
trade in five business days flags the account** and restricts it to
closing-only for 90 days. The fund holds ~$2,036, far under the $25,000
threshold that would exempt it.

> **Spend zero today if you can.** A day trade is only created by closing a
> position *opened the same session*. Buying and holding overnight costs
> nothing from the budget. If you open something today, plan to exit tomorrow.

The gate will block the 4th automatically and the Monitor header shows the
count — but it is much cheaper to not approach the cliff than to rely on the
railing.

⚠️ **The paper venue does not simulate this rule.** Alpaca returns
`daytrade_count: None` and `multiplier: 4` on this account, which a real $2k
account would never get. Our own count from the event log is the only
enforcement here. Do not read "the venue let me" as "the rule allowed it".

---

## Pre-open (before 09:30)

- [ ] **Start the spine the safe way** — `bash scripts/run_local.sh`, never
      bare uvicorn. The `.env` on disk says `FUND_ENV=production`; only the
      script overrides it. Confirm the banner reads
      `MOCK MODE — in-memory ledger, real market prices`.
- [ ] Set `ENABLE_TRADE_STREAM=true` — today is the day it gets proved.
- [ ] `GET /api/v1/fund/session` → expect `phase: "pre-market"` between 04:00
      and 09:30, with `seconds_to_open` counting down.
- [ ] `GET /api/v1/fund/compliance` → confirm `used: 1, remaining: 2`.
- [ ] `GET /api/v1/fund/book` → confirm you are on the **local** ledger, not
      `hedgefund-ae96c`. Migration is unresolved (see below) — do not switch
      mid-session.
- [ ] Monitor loads; header clock shows **Pre-market · opens in Xh Ym**.

## At the open (09:30)

- [ ] Header clock flips to **Open · closes in 6h 30m**. This is the live test
      of the session logic — watch the transition rather than reloading later.
- [ ] Within one strike interval, a `NavStruck` event appears. Overnight there
      should be **none** — that is the fix from this morning working. Compare
      the count before and after.
- [ ] Signals panel starts evaluating; `market_open: true` in the response.

## First order — the trade-stream proof

This is the item carried from yesterday: the fill stream **connects but has
never carried a real fill.**

- [ ] Propose one small order. Prefer a **buy you intend to hold overnight** —
      it costs nothing from the day-trade budget.
- [ ] Before approving, read the approval card for `compliance_warnings`.
- [ ] **Time the approval deliberately.** Click promptly on one order today.
      MSFT cost 11.5bps after 103 seconds of deliberation; F cost 3.6bps after
      3 seconds. With arrival-price capture now live, this is the first order
      that can actually attribute the difference.
- [ ] After the fill: `GET /fund/book` → `fill_stream.applied` should be **1**.
- [ ] Then the poller should report `duplicate: true` on its next tick — that
      is the idempotency guarantee proving itself, not a warning.
- [ ] `GET /api/v1/fund/tca` → the new order should have `has_split: true`,
      with `delay_bps` and `execution_bps` populated for the first time.

## Through the session

- [ ] **Clear the INTC breach** — 34.6% of NAV against a 20% cap. The sells are
      proposable now that the risk gate no longer blocks de-risking. Note this
      is a *sell of a position opened yesterday*, so it does **not** cost a day
      trade.
- [ ] Watch the Execution quality panel as fills accumulate. It says
      "observation, not an estimate" under 20 fills — that warning should stay
      up all day; do not re-cost any backtest on today's numbers.
- [ ] Reconciliation: `symbols_out_of_sync` should stay **0**. Anything else is
      the day's most important finding.

## At the close (16:00)

- [ ] Header flips to **After-hours**.
- [ ] Exactly **one** closing `NavStruck` — the official daily mark. Two would
      mean the strike window re-armed wrongly; zero means the transition was
      missed.
- [ ] After 20:00 the phase should read **Closed** and strikes stop entirely
      until Monday.

## Post-session

- [ ] `GET /api/v1/fund/tca` → record the day's realised cost against the 2bps
      assumption. Note the sample size honestly.
- [ ] Confirm the day-trade count is where you expect it.
- [ ] Update `HANDOFF.md`.

---

## Decision needed from you (not a test)

### Firestore migration is not a merge

The quota **has reset** — reads are being served. But comparing the ledgers
found **zero shared event IDs**:

| | events | window | contents |
|---|---|---|---|
| **production** | 22 | 08:12–08:27 Aug 13 | setup only; **no fills** |
| **local** | 52 | 13:16–19:53 Aug 13 | the real trading; **9 fills** |

Both number from `seq 1`, and **each has its own fund inception**
(`SubscriptionRequested` → `CashConfirmed` → `UnitsIssued`). Replaying local
into production would append a second inception onto an existing one: two
`UnitsIssued`, double-counted units outstanding, and a NAV per unit that is
simply wrong.

Decisively: the broker's actual positions (SOFI, F, INTC, MSFT) match the
**local** ledger. Booting against production would show a fund holding nothing
while Alpaca holds ~$2k of stock.

**Three options:**

1. **Promote local to production.** Archive the 22 abandoned production events
   to `fund_events_archive_2026-08-14`, replay local's 52 into a clean
   collection. Preserves the history that matches the broker, and deletes
   nothing that ever moved money — production has no fills. It does violate
   append-only, so it needs an explicit decision and a recorded reason.
2. **Keep local as the book** and defer.
3. **Start production fresh** from current broker state, losing trade history.

(1) looks right to me, but it is your call, and it stays **blocked on
credential rotation** — do not migrate onto a service account whose key sat in
a chat transcript.

### Still open

- **Rotate the Firebase service-account key and the Alpaca keys.** Carried for
  two sessions now. Everything else in the queue is downstream of it: a
  tamper-evident ledger is worth nothing if the key that can rewrite it is
  public.
