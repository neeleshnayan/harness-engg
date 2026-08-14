# Trading session checklist — Friday 2026-08-14

All times **ET**. Market opens **09:30**, closes **16:00**.

---

## ⛔ Read this first — one decision blocks the session

**The Firestore free-tier quota is exhausted and does not reset until 03:00 ET
tomorrow.** The production ledger cannot serve today's session as things stand.

**What happened.** Every projection folds by calling `stream()`, so a single
cockpit render cost several hundred document reads — NAV, risk, orders,
compliance, TCA and the chain each re-read the whole log. A browser polling
every thirty seconds burns the 50,000/day allowance in about an hour. 452 API
requests today at roughly 100 reads each accounts for it exactly. This is
almost certainly what exhausted the quota the first time too; it was invisible
while the ledger was a local JSON file, where re-folding was free. Moving to
Firestore did not introduce the amplification, it just started charging for it.

**Fixed, for tomorrow onward.** Reads are now incremental — the log is
append-only, so a refresh asks only for events after the highest seq we hold.
One document read per refresh instead of fifty-two. A six-hour session now
costs roughly **720 reads against a 50,000 allowance**, so the free tier should
be comfortable. Today's quota is already spent, though.

### Pick one

| | What happens | Cost |
|---|---|---|
| **(a) Upgrade to Blaze** ← recommended | Unblocks immediately, production ledger, nothing else changes | Reads are $0.06/100k. With the fix in place the bill stays near zero. |
| (b) Run local today, re-promote tonight | Session runs, but re-introduces the divergence we just solved | Free; more work tonight |
| (c) Skip the live session | Resume tomorrow when the quota resets | Free; loses the day |

I'd take (a). The cache fix means you're unlikely to ever pay meaningfully, and
it removes a class of "the fund stopped because of a quota" failure that has
now bitten twice.

**Once the DB is writable, do this first** — it is one event and it could not be
written before the quota went:

```bash
curl -s -X POST http://127.0.0.1:8090/api/v1/fund/fees/terms -H "Content-Type: application/json" -d '{"management_annual_pct":0.0,"performance_pct":0.0,"note":"Friends & Family PoC: no fees. Explicit zero so NAV per unit is provably net.","actor":"operator"}'
```

---

## The hard constraint, unchanged

**Day-trade budget: 1 used, 2 spare.** F was bought and sold on 2026-08-13.
The **4th day trade in five business days** restricts a sub-$25k account to
closing-only for **90 days**.

> A day trade only happens when you close something opened the *same session*.
> Buying and holding overnight is free. **Clearing the INTC breach costs
> nothing** — that position is from yesterday.

⚠️ The paper venue does **not** simulate this rule (`daytrade_count: None`,
`multiplier: 4` on a $2k balance). Our own event-log count is the only
enforcement. Do not read "the venue let me" as "the rule allowed it".

---

## Pre-open

- [ ] Resolve the billing decision above.
- [ ] Start the spine: `bash scripts/run.sh` (production ledger, Alpaca paper,
      trade stream on). `run_local.sh` is now only for deliberate offline work.
- [ ] Frontend: `npx next dev`. Use **either** `localhost:3000` or
      `127.0.0.1:3000` — both are allowed now; they were not this morning, and
      the wrong one made every panel report the spine unreachable.
- [ ] `GET /fund/ledger/verify` → expect `ok: true, chained 52/52, unchained 0`.
- [ ] `GET /fund/compliance` → expect `used: 1, remaining: 2`.
- [ ] `GET /fund/session` → `pre-market` before 09:30, counting down.
- [ ] `GET /fund/fees` → after the POST above, `terms_recorded: true`.
- [ ] Check the log for `scheduler lease ACQUIRED`. If it says NOT HELD, another
      process holds it — that is the lease working, not a fault.

## At the open

- [ ] Header clock flips to **Open**. Watch the transition rather than
      reloading later.
- [ ] A `NavStruck` appears within one strike interval. Overnight there should
      have been **none** — that is this morning's fix working.
- [ ] Signals panel starts evaluating; `market_open: true`.

## First order — the trade-stream proof

Still the one unproven thing: the fill stream **connects but has never carried
a real fill.**

- [ ] Propose one small order. Prefer a **buy you intend to hold overnight** —
      free from the day-trade budget.
- [ ] Read the approval card for `compliance_warnings` before approving.
- [ ] **Time the approval deliberately.** MSFT cost 11.5bps after 103 seconds;
      F cost 3.6bps after 3 seconds. Arrival-price capture is live now, so this
      is the first order that can actually attribute the difference.
- [ ] After the fill: `fill_stream.applied` should be **1**, then the poller
      reports `duplicate: true` — that is idempotency proving itself.
- [ ] `GET /fund/tca` → the new order should show `has_split: true` with
      `delay_bps` and `execution_bps` populated for the first time.

## Through the session

- [ ] **Clear the INTC breach** — 34.6% against a 20% cap, and it costs no day
      trades.
- [ ] Execution quality panel: the "observation, not an estimate" warning stays
      up under 20 fills. Do not re-cost a backtest on today's numbers.
- [ ] `symbols_out_of_sync` stays **0**. Anything else is the day's most
      important finding.

## At the close

- [ ] Header flips to **After-hours**.
- [ ] Exactly **one** closing `NavStruck`. Two means the strike window re-armed
      wrongly; zero means the transition was missed.
- [ ] After 20:00, phase reads **Closed** and strikes stop until Monday.

---

## What changed this morning

| | |
|---|---|
| Pre-trade compliance | PDT gate blocks the 4th day trade before the approval card |
| NAV strikes | Session-gated; verified no strike at 03:44 while closed |
| TCA | 7.55bps realised vs 2bps assumed, arrival price now captured |
| Ledger | Hash-chained, 52/52 verifying; promoted to Firestore |
| Scheduler | Single-writer lease, verified across two processes |
| Fees | Accrual + high-water mark; NAV per unit is net |
| Reads | Incremental — ~50x cheaper |
| Logging | Was entirely disabled; every `_log.info` had been dropped |
| CORS | `127.0.0.1:3000` now allowed |
| Dead code | 891 lines of unused chart components removed |

**510 tests passing.**

## Still open

- **Rotate the Firebase and Alpaca credentials.** Carried three sessions. The
  service account is admin on a ledger that now holds the fund's real history.
- **Prove the fill stream** on a real fill.
- **#12 limit orders** — the TCA number argues for them; gated on ≥20 fills.
- **#13 finish the Lab migration** — theses/memos work end-to-end with no page.
