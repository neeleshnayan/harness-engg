# Quant dispatch #9 — P1 (the ETH staking-wrapper premium) down the belt + the crypto annualisation probe

**Filed by the CTO chair (Fable) 2026-08-28. Seat findings verbatim below the
note; nothing edited. Algorithms committed at 8fe7eea1.**

**CTO note at filing**: The crypto program's first candidate went through the
full chain — proposal (Ed batch 7) → adversary (SURVIVED) → implementation →
belt → gate — six days ahead of the Sep 3 charter date. The verdict is FAILED,
and the chair's reading agrees with the seat's: **the failure is about the
window, not the wrapper.** The premia leg itself returned zero failures on the
full window, and on the only window where the mechanism exists (staking began
2025-10-06) both substantive premia criteria pass with room (advantage +0.0202,
luck 76.8% vs the 65% bar). The two consistency failures judge ether's PRICE
(total-return holdout/walk-forward on a falling asset), not the 1.9%/yr spread
the claim is about — the quant's dispatch-#5 finding reproduced on a premia
claim, where it bites harder. Verified by the chair before filing: the gate
verdict via `/fund/factory/candidates/a39f301168fa` (verbatim match, premia
failures None), both crypto refusal lines in the raw container logs, the
freshness-guard defect at `marketdata.py:178-190`, the engine-default fix in
the committed file. **The probe half located a hard blocker on the crypto
program's critical path**: a crypto brokerage model gives the correct 365-day
clock AND refuses our PythonData feed (`SecurityType.Base`) at two independent
gates — the 365 clock and fills are mutually exclusive until the harness
grows a native crypto security path or a shim. That decision is the chair's,
queued for the next builder batch with the fold-floor and freshness repairs.

---

## The candidate

`lean_workspace/algorithms/eth_wrapper_premium/main.py`, class
`EthWrapperPremium`. Candidate **`a39f301168fa`**, gate **v5r4-premia**,
**FAILED — 3 failures, verbatim**:

> 1. the probability that the risk-adjusted ADVANTAGE over the bar is above
>    zero is 61.245%, below the 65.0% this bar requires, which on 525
>    observations of this shape demands an annualised advantage of about
>    +0.01; this run measured +0.01 — on this much history that is not
>    distinguishable from luck
> 2. kept only -152% of its edge out of sample; 50% is the floor
> 3. only 2 fold(s) could be measured, below the 8 required — the consistency
>    test did not run, which is not the same as passing it

**The premia leg itself: ZERO failures** — `sharpe_advantage +0.00654`,
drawdown 66.978 vs bar 67.915, gross 0.9921 vs 1.0 ceiling, coverage true,
realised rf BIL 4.1642%/yr, cash-credit bias +0.00074 (11% of the advantage).

**Post-staking window** (2025-10-06 → 2026-08-26, 224 sessions, container
`9c13e2542206`, every prediction exact): **sharpe_advantage +0.0202, luck
76.768% ≥ 65.0 — zero failures on both legs.** The full-window failure is
dilution: 301 of 526 sessions predate staking (mechanism ON for 43% of the
window dilutes +1.82%/yr to +0.70%/yr).

Data verified before design: mini trust ("ETH") and ETHA both EQUITY
namespace, 527 joint sessions 2024-07-23 → 2026-08-27, split+dividend
adjusted (required — the 2026-08-06 amendment pays staking rewards as cash).
Independent reproduction off our own feed before any code: pre-staking
−0.107%/yr, post-staking +1.815%/yr, DiD +1.92%/yr, 10/11 months positive —
matching Ed and the adversary (four computations, one answer).

Implementation decisions (defended in the file): benchmark = ETHA
(`engine_single_name` verified; an ETHA bar IS the claim, not a thumb on the
scale); `HOLD_DAYS 17` = the longest multi-week cadence the history admits
(4 folds; 18+ NOT TESTABLE); weight 0.99 (at 1.00 a maintenance rule places 3
orders — min_orders unreachable; the buffer costs 2.6 luck points,
pass-unfavourable, so safe); `minimum_order_margin_portfolio_percentage = 0`
set LOUDLY (the engine default silently declined 12 of 31 maintenance trades;
counterfactual at the default: 19 fills, one more failure, everything else
within 0.11pp). Pre-registered prediction: **10 of 11 quantities exact**; the
one miss (fold geometry) became finding #1 below.

**Total-return decomposition (for sizing, not for the gate)**: strategy − bar
= +1.721pp, of which the wrapper premium proper is **+1.066pp** and +0.655pp
is the 1% cash cushion compounding better through a fall — an artifact that
reverses sign in a rising market. The Sharpe advantage is not contaminated.

Ed's instrument pre-commitment scored: right outcome (refusal), wrong reason
— the premia luck basis is `target_zero_module` on the ADVANTAGE series, not
the engine's 1.0-Sharpe hurdle; the window is the problem, not the statistic.

## The crypto probe — answered in both directions, blocker located

`crypto_clock_probe` (BTC/USD daily, our feed, 3 containers):

| arm | trading_days_per_year | clock state | fills |
|---|---|---|---|
| no brokerage model | 252 | `engine_understates` | yes |
| `set_brokerage_model(COINBASE, CASH)` | **365** | **`agree`** | **ZERO** |
| + SecurityMarginModel(1.0) | 365 | `agree` | **ZERO** |

Cause: our crypto data is `PythonData` ⇒ `SecurityType.Base`, refused by
`CashBuyingPowerModel` ("The security type must be Cryptoor Forex") and again
by `CoinbaseBrokerageModel.CanSubmitOrder` ("does not support Base security
type") — both lines verified in the raw logs. **Getting the 365 clock and
getting fills are mutually exclusive on the current feed.** Corollaries:
`engine_understates` is NOT asset-class evidence (fires on equity ETFs too)
but **`agree` IS** (only a crypto brokerage model produces 365); and a
rejected order emits NO order event (`rejects=0` in both failing arms) —
`portfolio.invested` is the only in-algorithm detector.

## Instrument defects surfaced by running (5, all cited)

1. **The walk-forward floor is derived from `lookback_days` against the wall
   clock, not from symbol availability** (`factory.effective_history_floor`:
   `data_path 2021-03-06`, `per_symbol: null`, "UNMEASURED at plan time") —
   planned 12 folds reaching to 2022-06-06 on a pair whose first bar is
   2024-07-23; ~16 wasted containers; `folds_required` doubled to 8 by folds
   that could never carry data. Counterfactual at the true floor: 4 planned /
   1 measurable / 4 required — still fails, so the defect cost containers,
   not the verdict.
2. **`folds_before_data_path_reach` reports 0** while 3 folds placed zero
   trades — absence rendered as zero, in the starvation instrument itself.
3. **`benchmark_population.population` names the TRADED symbol on the
   `engine_single_name` branch** (`leanrunner.py:1828-1830`) — stored label
   `["ETH"]`, actual series ETHA. A silent lie for every wrapper/share-class
   claim; the adversary is bound on it.
4. **`robustness.total_orders` counts INVALID orders** (`leanrunner.py:3425`)
   and `min_orders` reads that field — a strategy whose every order is
   rejected can still count toward the 20-fill floor. Pass-favourable.
5. **The equity freshness guard is unreachable on the live endpoint** — the
   Alpaca equity fetcher stamps `series_freshness` (3-day crypto bound)
   unconditionally (`marketdata.py:178-190`), so `?symbol=ETH` reads
   `freshness: "live"` today and a holiday-week equity would read `stale`.

## Container census

59 containers (56 candidate + 3 probe), 55 done (6.5/11.5/18.0 s), **4 killed
at the 900 s ceiling (6.8%)** — 80.7% of the 74-minute wall clock was deadline
on hangs vs 10.5 min of useful engine time. Points declared 39, realised 36;
**no censored point was cheaper than every survivor in any sweep** and the one
censored test leg was already-unmeasurable — no SELECTED-FROM-CENSORED-GRID.

## What happens next

- **The post-staking evidence goes to the CEO for a human look** (the seat's
  recommendation, the chair concurs): P1 clears both substantive premia
  criteria on the only window where the mechanism exists, and cannot be
  walk-forwarded until the instrument is ~3 years old. If pursued, Stan sizes
  on the +1.9%/yr post-staking figure (not the belt's +1.72pp headline, 0.66pp
  of which is the cash-buffer artifact).
- **Builder batch (chair-owed)**: the crypto SecurityType decision (critical
  path for the 2-3 week demonstration); walk-forward floor from a live
  first-bar probe; the equity freshness guard repair; the total_orders /
  min_orders fix. Validator: census stored candidates for total_orders >
  fills.
- Ed's F1 replacement (declared distributions) unchanged, due 09-05.

*Seat STATE, BINDS (mechanism, analyst, pm, validator, builder ×2, adversary)
and EVOLVE carried at resolve per protocol; run record run-quant-p1-0828.*
