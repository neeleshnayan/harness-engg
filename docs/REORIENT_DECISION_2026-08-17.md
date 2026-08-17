# Re-orientation: the evidence, and the decision that is yours

**Prepared 2026-08-17 while the market was open. Nothing here has been executed.
Every position change is your click.**

NAV **$2,030.33** — positions $1,183.41, cash $846.92 (42% cash).
Chain verifies 165/165. 811 tests green.

---

## 1. What the book holds, and the one number that frames everything

| position | value | share |
|---|---|---|
| GLD | $172.22 | 14.6% |
| XLE | $170.85 | 14.4% |
| NVDA | $170.02 | 14.4% |
| SPY | $168.73 | 14.3% |
| INTC | $168.45 | 14.2% |
| SOFI | $168.37 | 14.2% |
| MSFT | $164.76 | 13.9% |

**Zero of seven positions sit inside the fund's own capacity band.** The entire
book is off-thesis: a fund whose stated edge is names a multi-billion manager
cannot build a position in is holding SPY, GLD, NVDA, MSFT and XLE — the most
crowded water there is.

That is not an accident to be embarrassed about; it is the honest starting point.
The book predates the thesis.

## 2. The three strategies behind it, re-judged today

All three carried `backtested=NEVER` and had **no warm-up**, so their recorded
history was subject to the bug that produced the false "kept 0% out of sample"
verdict. Warm-up was sized from each one's own lookback — RSI period, slow MA,
MACD `slow + signal` — which changes *when* a rule may first trade, never what
the rule is. Then all three went down the belt under gate v2.

| strategy | holds | strategy | simply owning it | PSR | verdict |
|---|---|---|---|---|---|
| Mean Reversion · Cyclicals | INTC | **+64.6%** | **+411.2%** | 31.1% | FAILS |
| Momentum · Large Cap Tech | NVDA | **+30.0%** | **+67.9%** | 17.0% | FAILS |
| Trend · Sector & Commodity | SPY | **+9.7%** | **+34.7%** | 3.0% | FAILS |

Unanimous, and not marginal. Every one of them **captured a fraction of what
holding the same asset would have returned.** In the gate's own words:

> *"returns 64.561% against 411.22% for simply owning it: an expensive way to
> hold the underlying"*

> *"kept its edge in only 0 of 4 independent folds (0%), under the 50% floor —
> consistent with a lucky window rather than an edge"*

Two of them barely act: 2 fills and 13 fills respectively. And a finding that
matters more than the returns:

**The INTC strategy has not traded at all in 2026.** A fully warmed-up run over
226 sessions placed zero orders — its RSI never crossed the entry threshold. That
position is an inert static long wearing a strategy's name. It is not being
managed by anything. (The gate used to call this "needs warm-up"; it now
distinguishes a silent signal from a starved one, because they send you to fix
different things.)

## 3. What the gate can and cannot tell you right now

Be careful with the word conviction here.

- Gate **v1 passed random noise 50% of the time** — so every verdict issued
  before today, including the ones that justified this book, rests on an
  instrument that could not distinguish a strategy from a coin.
- Gate **v2** closes those leaks and is what the table above was judged with. Its
  fold machinery demonstrably works now (4 measurable folds, 0 retained on NVDA).
- **v2 has never been cleared by anything.** The oracle audit — a strategy with
  tunable, known foresight — is running to establish whether it *can* be. Until
  that lands, "nothing passes v2" is not yet evidence that nothing is good enough.

**So there is no evidence-backed alpha claim available today.** Not for these
strategies, and not for a replacement.

## 4. The distinction that unlocks the decision

The gate governs **alpha claims**. Choosing which market you want exposure to is
a **mandate** decision. Conflating them is a category error, and it is what makes
this feel deadlocked.

You do not need a gate pass to decide the fund should stop holding mega-cap ETFs.
You need a gate pass to claim an *edge*. Those are different sentences, and only
the second is blocked.

## 5. Three structural options

Each is a real choice with a real cost. None is recommended here — the mandate is
yours.

**A · Flatten the failing strategies, hold cash.**
The strategies add nothing over owning the asset, so stop crediting them. Sell
into cash and wait for something to clear v2.
*Cost:* ~100% cash earning nothing, with no ETA — nothing has ever cleared the
bar, and until the oracle lands we do not know if anything can.
*Clicks:* up to 7 sells.

**B · Keep the exposure, drop the pretense.**
The evidence indicts the *strategies*, not the *exposure*. Relabel the holdings as
an explicit passive sleeve with no alpha claim attached, and stop reporting them
as strategy performance.
*Cost:* the book stays 100% off-thesis. A capacity-edge fund holding SPY is not
executing its mandate.
*Clicks:* none — this is a bookkeeping and honesty change, not a trade.

**C · Re-orient the exposure onto the thesis.**
Replace off-thesis holdings with the measured capacity band — the 20-name
equal-weight basket, which is on-thesis, diversified 20-wide rather than 7, and
whose survivorship bias is now *priced* (−6.3 to −6.9pp, upper bound).
*Cost, stated plainly:* this is **beta, not alpha**. The +37% the control returned
in 2026 is small-cap beta plus survivorship, not skill, and it has not passed the
gate because it is not a strategy — it is an exposure choice. Declaring it as such
is what keeps it honest; calling it an edge would be the exact self-deception the
harness exists to prevent.
*Clicks:* 7 sells plus up to 20 buys, ~$59 per name (the band filter already
guarantees fractional-share support).

## 6. Constraints on sequencing

- **PDT: one day trade remains** before the 90-day flag. Any same-day
  buy-and-sell of the same name burns it. Sequencing sells today and buys
  tomorrow avoids the counter entirely.
- **The regime throttle** was asking for reduced gross when last measured; check
  `/risk/throttle` before sizing anything up.
- **The venue is the paper connector.** Orders route to paper, not Alpaca live.
  Switching that is a separate, deliberate decision.
- **Nothing executes without your approval click.** LEAN proposes and cannot
  execute; Clark proposes and cannot execute; I have taken no click and will not.

## 7. What I would want before calling anything an edge

1. The oracle result — is v2 clearable at all? (running)
2. A candidate family aimed at the band, with filings evidence attached, through
   the belt (#30 in the roadmap).
3. Band coverage above zero. It is currently **0 of 874** — the filings reader has
   never read a single name in the water we claim as our edge.

## Reproduce

```bash
python scripts/rejudge_book.py          # the table in section 2
python scripts/oracle_audit.py 1.0,0.5  # whether v2 can be cleared
```

Full records: `docs/book_rejudged.json`, `docs/CALIBRATION_2026-08-17.md`,
`docs/SURVIVORSHIP_2026-08-17.md`.
