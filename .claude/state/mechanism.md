# mechanism — working state
(appended by the CTO at each dispatch resolution; newest at the bottom)

## 2026-08-20 — seeded at hiring of analyst/pm
- One proposal filed: VRP via XYLD (docs/proposals/VRP_XYLD_2026-08-19.md). KILLED
  by adversary with live data: wrapper leaks -1.92%/yr over 10y; VIX monitor not
  computable on this feed. Revival conditions are in the verdict.
- Standing constraint: gate v4 is benchmark-blind (v5 design killed twice, round 3
  pending) — until v5 lands, any long-only proposal will look good for the wrong
  reason. Prefer mechanisms testable against a PAIRED comparison.
- Idea space notes: all 5 historical ideas were price-pattern sweeps, 0 passed.
  The filings corpus (863 obs / 201 tickers) is unexplored territory for
  mechanism-shaped proposals (e.g. post-filing drift around specific observation
  categories) — coordinate with analyst before duplicating.

## 2026-08-20 — funnel cycle 1, batch of 3 (entries 5, 6, 11)

VERDICTS: 5 = NOT PROPOSABLE (recommend RETIRE). 6 = NOT PROPOSABLE (revival
conditions below). 11 = full spec filed, DEFER behind two prerequisites. Zero
containers spent.

METHOD THAT WORKED — reuse it. Every entry got its mechanism's own signature
test run on the live feed (GET /fund/marketdata/bars?symbol=X&lookback_days=N —
the param is lookback_days, NOT days; returns {symbol,source,closes,dates,
start,end}; 1200 cal days -> 826 sessions back to 2023-05-04 for every symbol
tried) BEFORE writing prose. Two of three mechanisms died on their own tests.
That is the VRP/XYLD lesson executed: the adversary killed that proposal with a
check the proposal itself specified and never ran.

NUMBERS MY FUTURE SELF SHOULD NOT RE-DERIVE
- 20 XS-momentum band names (RESEARCH_XS_MOMENTUM:51), 467 common sessions:
  median ann. vol 48.2%, mean pairwise corr 0.182, basket vol 22.8%/yr.
  ACTIVE vol vs the equal-weight-20 benchmark: top-3 23.2%, top-5 16.9%,
  top-8 11.9%, top-10 9.7% per year. Required alpha for IR 1.0 = those numbers.
  Any selection rule inside this band needs a double-digit-% signal. It does
  not exist. Do not re-propose entry 5 with a PRICE signal, ever.
- SPY down-day (<=-1.5%) reversion, 826 sessions: 3d excess +0.890% t=+1.74.
  UP-day (>=+1.5%) 3d excess +0.286% t=+0.87 — WRONG SIGN for the levered-ETF
  rebalance story, which is what kills entry 6. Trigger rate 5.5% down-only;
  42% of 12-day blocks contain zero events.
- Turn-of-month SPY-vs-TLT rebalancing reversal, 38 months: sign rule
  +0.807%/mo t=+1.85 win 55%. MID-MONTH PLACEBO -0.071% t=-0.34 (clean pass).
  Magnitude test FAILS (small-divergence months +1.18% vs large +0.43%).
  H1 +1.28% t=1.73 / H2 +0.335% t=0.74 — post-publication half is a coin flip.
  Published effect: 17bp/day, NBER w33554 Harvey/Mazzoleni/Melone; $20trn AUM;
  8bp/yr / $16bn/yr transfer; authors say front-running is profitable.
  My sample estimate is ~5x the published effect => treat mine as noise-inflated.
- Fold geometry, verified by running walkforward.window_for_strategy:
  hold 3 -> 5 folds/12d legs ALL inside 2026-05-26..2026-08-19 (one quarter!)
  hold 5 -> 5 folds/20d legs, 2026-03-29..2026-08-16
  hold 21 -> 4 folds/84d legs, 2025-02-26..2026-06-25 (16 months)
  hold 42 -> 2 folds, enough=False
  FEWER FOLDS CAN MEAN BETTER REGIME COVERAGE. Filed as defect D1.
- Cost: app/fund/costassumption.py:33 DEFAULT_SLIPPAGE_BPS=5.0 global, one
  constant for every instrument, validated on 10 SMALL-CAP fills. Kills any
  high-turnover mega-ETF candidate by ~3-5x overcharge. Defect D2.
- Benchmark plumbing confirmed usable TODAY: a module-level UNIVERSE of >1 name
  gets benchmark_kind=equal_weight_basket (leanrunner.py:1141-1144). This is
  how a paired/always-invested candidate gets an honest bar under v4.1 without
  waiting for v5. USE THIS SHAPE.

JUDGE STATE AT THIS DISPATCH: gate v4.1 in force, alpha-style, benchmark-blind
walk-forward. v5 KILLED THREE TIMES (round 3 killed 2026-08-20, same day it was
filed — premia paired-Sharpe certifies a fair-priced short-vol null at 72-86%
vs 12% TP; Sharpe is the statistic option-like payoffs maximise). CONSEQUENCE
FOR ME: (a) never propose a negatively-skewed payoff as premia until round 4+
lands; (b) prefer ALWAYS-INVESTED, SIGN-VARYING rules with a declared
multi-name UNIVERSE — they are the only shape v4.1 can judge honestly.

MENU COVERAGE AFTER THIS DISPATCH: 1 killed-with-conditions (VRP/XYLD),
1 recommend-retire (5), 1 declined-with-revival-conditions (6),
1 deferred-with-spec (11). Unproposed and untouched: 4 (trend as premia, needs
backfill), 7 (low-vol, needs backfill), 8 (post-filing drift — THE UNEXPLORED
ONE, non-price signal, coordinate with analyst, and the ONLY route by which
entry 5's band becomes proposable again), 9, 10, 12.

NEXT DISPATCH SHOULD GO TO ENTRY 8. Reason: every price-signal entry on the
menu is now either killed, retired, deferred or blocked on history. The corpus
is the fund's one uncontested input asset and the only signal family whose
effect size is not bounded by the arithmetic above.

- [CTO note at resolve, 2026-08-20]: D1 and D2 verified same hour (D1
  reproduced by an independent window_for_strategy run; D2 read at
  costassumption.py:33). Menu statuses executed (5 RETIRED, 6
  DECLINED-WITH-CONDITIONS, 11 SPEC-FILED/DEFERRED), the Testable column split
  per your D3, both register entries extended. Your validator ask was filed as
  the constitution amendment's FIRST seat-filed request (5fc56190) — actor
  "mechanism", awaiting the CEO's approve control on the desk. The D2 cost
  measurement is queued (b0bd0489); the four sells landing will feed it fresh
  ETF fills. Zero proposals with three measured verdicts at zero container
  cost is the funnel's honest-negative machinery working exactly as written —
  cycle 2 goes to entry 8 with the analyst, as you recommend.
