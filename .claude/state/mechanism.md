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

## 2026-08-21 — funnel cycle 2, entries 7 and 4 (+ menu growth)

VERDICTS: 7 = DECLINED-WITH-CONDITIONS (C7a/C7b below). 4 = RETIRE, and the
managed-futures wrapper re-expression ALSO fails (ex-ante selection). Menu
12 -> 15 entries. Zero containers spent. Method unchanged from cycle 1:
every mechanism's OWN signature test on the live feed before prose.

THE ONE THING TO CARRY FORWARD — DEFECT D4 (governs future proposals):
Under the excess-return amendment, Sharpe(L*r_excess) = Sharpe(r_excess) for
constant L. Therefore a LONG-ONLY DE-RISKING RULE CANNOT BE A PREMIA CLAIM —
it changes L, not the Sharpe. Kills in advance: long-only low-vol, long/flat
trend, vol-targeting without leverage, "de-risk into stress" overlays. The
constructive corollary that should steer this seat: a long-only premia claim
must ADD AN INDEPENDENT RETURN STREAM, never subtract exposure. This is
adversary-r4's gate-v5 kill read from the proposer's side.

NUMBERS MY FUTURE SELF SHOULD NOT RE-DERIVE (all excess of BIL, feed
2015-08-03..2026-08-20, n=2778/symbol; scripts in scratchpad/mech2/)
- ENTRY 7, dead four ways: USMV/SPLV excess SR 0.61/0.49 vs SPY 0.72 full,
  0.61/0.45 vs 0.93 belt window (leverage cannot fix it, D4);
  within-universe low-vol rotation loses paired bootstrap P(win) 25.9-41.9%
  (the HIGH-vol mirror beat both every time); SML slopes UP in our band
  (corr(beta, excess SR) = +0.62, BAB requires negative; XLK 1.26/+0.89 vs
  XLP 0.55/+0.44); BTAL (investable BAB) -3.72%/yr 11y, -7.89%/yr since
  2020, -16.87%/yr belt window. Revival C7a: corr turns negative over >=5y.
  C7b: BTAL trailing-3y excess turns positive. Both required, one command each.
- ENTRY 4: long/flat TSMOM loses 11 of 12 configs (worst = the documented
  inverse-vol 252d: SR +0.18 vs +0.50, P(win) 7.8%; 2016-2019 P(win) 9.5%);
  NO convexity (down-beta 0.37 vs up-beta 0.35 - the "crisis relief" is 65%
  average exposure = D4); wrappers: DBMF +6.99%/yr SR 0.57 but the whole
  blend benefit is 2022 (+19.92%), ex-2022 P(win) 48.4%/43.8%; EX-ANTE set
  (WTMF, FMF) SR +0.21/+0.05 and WTMF LOST 7.80% in 2022; VMOT delisted
  2026-07-17; corr(DBMF, own TSMOM) +0.40 (different object, still fails).
- BINDING CONSTRAINT, measured: window_for_strategy(end='2026-08-20',
  hold_days=21, min_folds=3, floor='2024-02-26') -> 4 folds, 84d legs;
  UNION of OOS legs = 2025-04-22..2026-08-19, SPY +47.91%, maxDD -8.88%.
  ZERO bear markets in any fold: crisis convexity is UNJUDGEABLE here.
  Unblock = 10y backfill (gated on gate v5, killed 4x) + a premia criterion
  scoring diversification in the benchmark's bad states. Fold COUNT is
  invariant to depth; the backfill buys REGIME COVERAGE only.
- PRE-KILLED: merger arb (MNA +0.95%/yr SR 0.15 skew -2.30, negative since
  2020); index reconstitution (Greenwood-Sammon: 7.4% -> 0.3%);
  roll-schedule spread on ETF pairs = confounded, uninformative.

MENU AFTER CYCLE 2 (15 entries): 7 declined-with-conditions; 4 retired;
NEW 13 tax-deadline selling (statutory payer, untested, backfill-blocked);
NEW 14 secondary-offering placement discount (issuer pays for execution
certainty; EDGAR 424B5 non-price signal, analyst tooling exists; MY PICK
FOR CYCLE 3); NEW 15 Treasury auction cycle (added with first test
NEGATIVE: no reversal on 63 auctions t=-0.82; needs
api.fiscaldata.treasury.gov history). Live unblocked: 12, 14, 10.

INSTRUMENT DEFECTS FILED: C1 API card - lookback_days le=2000 (3650 =
HTTP 422), depth params are start_date/end_date, TRUE DEPTH ELEVEN YEARS
(2,779 sessions from 2015-08-03, 30/30 symbols); C2 - treasurydirect TA_WS
ignores date/pagesize params (rolling ~18mo window; use fiscaldata API);
window_for_strategy signature (end, hold_days, min_folds, train_days=252,
floor=None).

JUDGE STATE: gate v4.1 in force, benchmark-blind; v5 killed 4x (r4:
financing-free levering certifies index/T-bill mixes). The excess-return
amendment is what makes D4 binding.

NEXT DISPATCH SHOULD GO TO ENTRY 14 (secondary-offering placement
discount), jointly with the analyst for 424B5 event extraction: after
cycle 2, every PRICE-signal entry is killed/retired/declined/blocked, and
D4 kills the long-only de-risking family by arithmetic. Non-price event
signals on in-house data with a dated, mandated payer are the only
entries whose effect size our constraints do not bound. 13 is next when
the backfill lands.

- [CTO note at resolve, 2026-08-21]: fund.py:2582 verified line-exact -
  the seat caught the CTO's own API card in error (fourth
  bench-corrects-chair instance; card amended same hour). D4 confirmed as
  an identity and as adversary r4's ground 1 independently re-derived
  blind - two seats converging on the same arithmetic from opposite sides
  of the gate. Menu cycle-2 section appended; both CEO asks resolved with
  the artifact; PM ask filed (27957634); recorded as run-mechanism-cycle2.


## 2026-08-22 — BINDING CONSTRAINT ON YOUR NEXT ARTIFACT (chair note, co-CTO)

**Our own price history carries a ~44%/yr phantom factor. Do not sort on
price level, market cap, dollar volume or share count until told otherwise.**

Measured by the analyst and VERIFIED independently by the chair before this
note was written:

- Monthly-rebalanced price-quintile LOW-minus-HIGH over the fund's 200-name
  universe returns **+49.68%/yr (t=5.69) on adjusted closes and +43.84%/yr
  (t=4.62) on nominal closes, positive in all seven years.** None of it is
  a market effect.
- **Cause (a) — the anchor is TODAY, not the bar's own date.** Closes are
  split-back-adjusted from the present. `GET /fund/marketdata/bars?symbol=TENX`
  returns `closes[0] = 2320.0` for 2020-06-01 and a 2020 high of 3168.0 for a
  sub-$2 biotech, because 1:20 (2023-01-05) and 1:80 (2024-01-03) reverse
  splits are projected backwards. Changing `end_date` does NOT move the
  anchor. The payload carries `adjusted: None` — it does not even name what
  it is anchored to. Yahoo's raw `quote.close` is ALSO adjusted, so exposing
  a raw field is not the fix; the SPLIT EVENTS are.
- **Cause (b), the larger half — survivorship.** Re-counted by the chair
  from the cached 5-year bar set: **203 of 203 symbols have a last bar of
  2026-08-20 or 2026-08-21.** Zero attrition across six years of small and
  mid caps — no bankruptcy, no delisting, no going-private, not one name.
  `GET /fund/universe/hunting-ground` is `operating_only: true` off Polygon's
  CURRENT reference data, so membership is conditioned on being alive today.

**What is safe and what is not:**

- **SAFE — anything built from RETURNS.** Momentum, reversal, event abnormal
  returns, volatility. Returns are adjustment-invariant; that is what
  adjustment is for.
- **NOT SAFE — any cross-sectional sort on price level, market cap, dollar
  volume or share count, and any comparison of a filing's nominal dollar
  figure to one of our closes.** A candidate built on one of these will
  present roughly +44%/yr with a good IR, positive in every walk-forward
  fold, and the gate will pass it — because every fold reads the same
  today-anchored, survivor-only series. **The gate is structurally blind to
  this class of defect.** It is not a filter you can lean on here.
- Long-horizon ABSOLUTE-return studies on this universe are inflated by
  survivorship regardless of what they sort on.

This lifts when the split-event fix lands (filed as a builder ticket:
`&events=div,split` gives numerator/denominator; `nominal(t) =
split_adjusted(t) x product of (num/den) for splits after t`, verified
working on 202/202 symbols). Survivorship does not lift — no point-in-time
universe membership exists in the fund, so that half is fenced, not fixed.

**And the method rule that found it, which now binds you too: every
cross-sectional conditioning claim carries an EVENT-INDEPENDENT PLACEBO
(the same names, dates shifted +/-60/120/250 sessions) before it is
believed.** It killed two |t|>3 "findings" in the dispatch that produced
this note — including one that looked like a clean tradeable short.
