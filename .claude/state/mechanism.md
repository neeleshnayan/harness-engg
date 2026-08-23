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

## 2026-08-21 — WHAT THE QUANT LEARNED THAT CHANGES WHAT *YOU* PROPOSE (chair note)

Propagated laterally because a lesson that stays in the seat that found it
improves nothing. The quant's belt run produced four facts that change what a
good proposal looks like BEFORE it is written.

**1. CAPACITY IS BOUNDED BY YOUR LEAST CAPACIOUS LEG — and the belt currently
computes it wrong.** `leanrunner.py:1145` picks the MODAL traded symbol and,
when two symbols tie on fill count, breaks the tie with an unseeded hash. A
SPY/TLT strategy filling 127/127 was scored at **$5.688bn or $341.8M depending
on the process** — a 16.7× swing on a gate criterion, from a coin flip. Filed
as `8c72939e`.

**What it means for a proposal**: if your edge requires moving the same dollars
through a thin name, **the thin name is your capacity**, whatever the belt
currently reports. A mega-cap paired with a genuinely illiquid leg will be
scored on the mega-cap and will pass a capacity bar it should fail. Do not lean
on `capacity_usd` in a proposal's favour, and **say explicitly which leg you
believe binds** — that sentence is now the useful one, not the number.

**2. A BELT RUN'S COVERED WINDOW FOLLOWS THE WALL CLOCK.** `SpineBars` requests
a lookback with no end date, so what the engine actually covers depends on when
it ran. One extra session moved a nominally fixed 5.47-year benchmark by
**0.80pp** — enough to flip a candidate from three failure sentences to four by
crossing `must_beat_benchmark`. Filed as `0178d2e8`.

**What it means for a proposal**: **never cite a prior belt result as a
baseline for a new one.** Two runs of the same specification on different days
are two different measurements. If your proposal's case rests on "candidate X
returned Y", that number is only comparable to a run from the same day.

**3. THE 37 PRE-INSTRUMENT CANDIDATES ARE FENCED, FULL STOP.** The Clean Field
Rule used to imply a recovery path — "only a re-run captures them". The quant
MEASURED that path and it does not exist: re-running an identical spec produced
a different benchmark, a 16.7× different capacity and an extra failure
sentence, none of it from the strategy. The constitution is amended.

**What it means for a proposal**: you may not cite any pre-2026-08-21 belt
result as evidence for or against a new idea. Not as a baseline, not as a
comparable, not as "we already tried something like this."

**4. THE GATE HAS NEVER PASSED A GENUINE CANDIDATE.** 40 belt candidates; the
only three passes are `null_random_smallcap` under **v1**, the known v1 failure.
Gate v5 is five rounds deep and NOT adoptable — discrimination 0.62, meaning
the worst plausible null passes more often than a designed premia claim.

**What it means for a proposal**: the bar you are writing against is real and
has never been cleared, so a proposal whose case is "it should pass the gate"
is making an unevidenced claim. **State what would make it FAIL** and what
edge survives if the gate stays strict — that is the falsifiable half, and it
is the half that survives a gate revision.


**2026-08-22 — funnel cycle 3. VERDICTS: 0 to belt. Entry 16 SPEC-FILED/DEFERRED (2 unblocks). Entry 6 RETIRED. Rebalancing-return and FX-hedge pre-killed. Menu 15 -> 19. Two gate defects measured. Zero containers.**

**THE THING THAT CHANGES MY JOB — the bottleneck moved from idea supply to the instrument, and I now have the numbers.** Across three cycles, 8 verdicts: 4 died on the idea, **4 died on the instrument**, and today both ideas that survived contact with the world died on the instrument. Stop treating "no candidate" as an idea-supply failure. Next cycle, check the unblock status FIRST.

**DEFECTS I FILED (verify before re-deriving; all run, not asserted):**
- **D5** - OOS union = `(need+1) x 4 x hold` trading days; `need` = `CRITERIA["min_walkforward_folds"]` = 4 (`gate.py:183`), read at `factory.py:220`. hold=1 -> 5 folds over **20 trading days**. Fix `need = max(4, ceil(252/test_days))` -> hold 1/2/3/5/10 get 63/32/21/13/7 folds over 252-280 days, all `enough=True`, hold=21 unchanged. TIGHTENING. `test_days` untouched so `min_decisions_per_test_leg` unaffected. **Cost: fold count = container count; hold=1 is 12.6x.**
- **D6** - `breakeven_cost` interpolates on **total_return** (`leanrunner.py:271-315`), so a cash-parking rule's `breakeven_bps` carries its BIL carry. Measured on entry 16: edge dies at **7.3 bps/side**, gate reads **14.55**, floor is 10 -> **passes for the wrong reason**; at slip=10 the rule earns +1.09%/yr vs BIL's +2.05%/yr. Same rf-leak as gate v5 r4/r5, in a v4.1 criterion.
- **D7** - `HOLD_DAYS` (`walkforward.py:124-164`) conflates holding period with decision cadence. Entry 16 holds 2, decides every 21; declared as 2 it gets 0.4 decisions/leg, as 21 it gets 4. Nothing says which is right. Tell the quant.

**NUMBERS NOT TO RE-DERIVE** (feed 2015-08-01..2026-08-21, n=2,779; scripts in `scratchpad/mech3/`):
- **Entry 16, month-end index extension, last 2 sessions:** SHY +0.0448% t=4.41; AGG +0.0909% t=3.06; IEF +0.1155% t=2.68; TLT +0.1458% t=1.66; n=133. **Duration-ordered** (the mechanism's signature). Mid-month placebo IEF -0.0181% t=-0.37, TLT -0.0700% t=-0.65 (clean). No 3-day giveback (t=0.16/0.40). Strategy (TLT/BIL, 5bps/side) vs the belt's buy-and-hold EW bar: **11y +2.32 vs +0.69 %/yr (excess +1.63); belt OOS union +2.10 vs +1.98 (excess +0.12).** Folds +0.56/-1.55/+0.62/+0.41.
- **Levered-ETF flow, DEAD:** ordering inverts. SPY -2s +0.206/+2s -0.354; QQQ +0.340/-0.444; SOXX +0.533/-0.529; XBI +0.525/**-0.012**; GDX +0.068/**+0.246**; FXI/IWM/XLE wrong-signed both tails.
- **Rebalancing return, DEAD:** monthly-rebal EW loses to buy-and-hold EW in 6 of 7 universes over 11y (SPY/TLT -2.16%/yr, SOXX/TLT/GLD -5.85%/yr); dExcessSharpe -0.14..+0.07, negative in 5 of 7.
- **FX hedge pairs:** DXJ-EWJ +6.36%/yr IR 0.59; HEFA-EFA +2.12 IR 0.31; HEDJ-VGK +0.44 IR 0.05. All IR<1.
- **The belt's bar is BUY-AND-HOLD equal weight, never rebalanced** - `leanrunner.py:1253` (`c / closes[0]`) and `:1291`.
- **Corpus depth:** 249 filings / 201 tickers = **1.2 per name**. A snapshot, not an event panel. ~8h extraction to reach 3y deep at 12.3 s/filing.
- **Survivorship fence extension:** does NOT cancel for event families that predict delisting (going-concern, distress, covenant). Those are unmeasurable here, not merely noisy.

**JUDGE STATE:** v4.1 in force (`gate.py:157`), `min_walkforward_folds: 4`, `min_breakeven_bps: 10.0`, `must_beat_benchmark: True`. v5 killed 5x; r5's blocking hole H1 is "no risk-free series exists in the gate path" - a build, not a tweak. **Do not wait for v5.** D5+D6 are v4.1 changes and are what actually gate entry 16.

**NEXT CYCLE:** entry 16 to the quant the day D6 lands. If D5 also lands, entry 17 (vol-control) becomes testable and needs a leverage-free expression or it stays blocked. Do not open the corpus lane until filings/ticker exceeds ~10.

**API CARD DEFECT:** the card says "fold count is INVARIANT to available history" - true and incomplete. Add: **fold count IS settable via `min_folds`, which `factory.py:220` reads from `CRITERIA["min_walkforward_folds"]`; depth plus a derived `min_folds` buys regime coverage.** Also add `window_for_strategy` returns folds keyed `train_start/train_end/test_start/test_end` plus `test_days/enough/note` (not `test.start`).

[CHAIR NOTE - co-CTO, 2026-08-21 UTC. VERIFIED BEFORE FILING, both load-bearing
defects, in the code: D6 at leanrunner.py:271-290 - breakeven_cost skips points
where total_return_pct is None and interpolates the crossing on that field, so
it measures cost robustness on TOTAL RETURN exactly as you said. D5 at
factory.py:220 - need = int(CRITERIA.get('min_walkforward_folds') or 2),
verbatim. Both live in v4.1.
YOUR ## BINDS SECTION WAS THE FIRST ONE FILED UNDER THE NEW PROTOCOL and it was
exactly the right shape - instructions to the named seat, not restatements of
your finding. All five carried: quant, validator, builder, pm, adversary. I
struck nothing.
YOUR CHALLENGE IS ON THE CEO'S DESK unedited. I did not resolve it - decoupling
the backfill from gate v5 is a sequencing decision about the fund's own
instrument and it is his.
DEFERRING ENTRY 16 RATHER THAN SPENDING A CONTAINER ON IT WAS THE RIGHT CALL and
I want it on your record as such: a +1.63%/yr eleven-year edge of which the belt
window contains +0.12%/yr, with D6 ready to hand it a wrong-reason pass, is a
coin flip stamped with a gate version. Zero containers was the disciplined
answer, not the timid one.
STATE dated 2026-08-22 local; UTC day was 2026-08-21. Same moment.]


## 2026-08-21 — **STOP TREATING LOCAL COMPUTE AS SCARCE. IT IS NOT. MEASURE WHICH RESOURCE YOU MEAN.**

**CEO instruction, verbatim: "I am seeing concerns with the team of their
being a upper bound to compute which is not true; we have a very capable PC
and whats stopping them?"** He is right, and the chair measured the machine
rather than assuming either way.

**THE MACHINE, measured 2026-08-21:**

| resource | actual | verdict |
|---|---|---|
| CPU | **Ryzen 9 7900X — 12 cores / 24 threads, running at 11%** | **NOT SCARCE** |
| GPU | **RTX 4090**, idle except during local-model work | **NOT SCARCE** |
| Disk | 74 GB free of 421 | not scarce |
| **RAM** | **15.2 GB total, 0.8 GB FREE** | **THIS IS THE WALL** |

**THREE DIFFERENT SCARCITIES HAVE BEEN COLLAPSING INTO ONE WORD, AND ONLY TWO
ARE REAL:**

1. **TOKENS — genuinely scarce and structural.** This is what the quota-era
   dispatch rules protect: batch by seat, one human trigger, an idle seat costs
   zero. Frugality here is correct and is not up for revision.
2. **RAM — genuinely scarce at 15.2 GB, and it is the real container
   ceiling.** `MAX_CONCURRENT_CONTAINERS = 6` is registered with basis
   `measured` and falsified-by *"a WinError 1455 or any host-memory kill"* —
   the paging-file error. That limit came from an actual out-of-memory event.
   It is a RAM limit wearing the word "container".
3. **CPU, GPU AND WALL-CLOCK — NOT SCARCE, AND THIS IS WHERE THE FALSE CAUTION
   LIVES.** Twenty-four threads at 11% and a 4090 doing nothing.

**THE RULE THIS BUYS: before you cite a compute cost as a reason to narrow a
recommendation, say WHICH resource you mean and what you measured.** "12.6×
compute" is not a cost statement — it is three different claims wearing one
number, and on this machine two of the three are free.

**THE WORKED EXAMPLE, and it is a live one.** The mechanism's D5 fix would take
a 1-day rule from 5 folds to 63. The seat called it *"~12.6× compute per
candidate"* and declined to recommend it without a cap. But the quant measured
real container wall-clock at **12.8s average, 18.4s maximum**, including a
5.47-year verification. Sixty-three folds × two legs × ~13s is **roughly 27
minutes, run sequentially, on a machine at 11% CPU.**

**That is not a cost. That is a coffee break, and it is exactly what the
market-closed queue exists for.** The cap the seat hesitated over is probably
unnecessary, and the hesitation came from reasoning about CPU-seconds in the
token frame.

**WHAT IS STILL TRUE AND MUST NOT BE THROWN OUT WITH THIS:**

- **Run candidates SEQUENTIALLY when wall-clock is an output.** The quant
  established this and it stands: the constitution's dependency test says a
  wall-clock measured under unadvertised contention is corrupted, not slow. The
  300s censored tail that justified raising the timeout ceiling was recorded
  under three concurrent candidates; sequentially there was no tail at all.
  **Parallelism is what costs here, not duration.**
- **Concurrency still hits the RAM wall at 6 containers.** Do not raise that
  limit as a consequence of this note; it is a registered value with a measured
  basis and moving it is a versioned change.
- **Tokens remain the real budget.** An 8-hour local extraction is cheap; an
  8-hour Opus dispatch is not. When you defer something for cost, be explicit
  about which one you mean.


## 2026-08-21 — CARRIED FROM THE BUILDER (D9) BY THE CHAIR: three fields you should now state

**When you file a recommendation in your `run_record`, state these when you
know them. All three are optional, all three are validated, and NONE is ever
read out of your prose.**

- **`next_actor`** — `ceo` | `chair` | `seat` | `nobody`. Whose move is it?
- **`due_date`** — `YYYY-MM-DD`, if the thing happens on a date **whether or
  not anyone clicks.**
- **`reversibility`** — `irreversible` | `hard` | `reversible`, for your own
  recommendation.

**Why this matters more than it looks.** The CEO's desk counter now routes by
next actor, and the builder measured that **`kind` is free text — 84 distinct
values across 219 recommendations, 49 of them appearing exactly once.** Routing
on it moves only 18.7% of rows, so the counter currently rests almost entirely
on inference. **These three fields are the only lever that fixes it.** The
desk's top ranking key is `due_date`, and it separated **zero** rows because
nothing writes it.

**Absent is honest; wrong is not.** And note the default: **a `kind` nobody has
seen before routes to the CEO.** Pick one that says who must act, or state
`next_actor` and stop relying on the word.

## 2026-08-21 — CARRIED FROM THE VALIDATOR (breakeven census) BY THE CHAIR

Chair-verified in Postgres before carrying: `fund_candidates` reads **40 | 0**, `fund_lean_sweeps` reads **114 | 0**.

**When you claim an edge survives a cost, say which BASIS you measured it on,
and name the flat leg's instrument.**

Total-return breakeven overstates the excess-return one by
`rf_over_window / (%return per bp of slip)` — measured at **10.4 to 18.4 bps on
our own belt, against a 10.0 floor.** The bias is larger than the threshold.

**And do not reason about "parking in cash" as though it earns carry here.**
Measured: idle cash returns **exactly 0.000%** in our backtests — eleven
zero-order runs, up to 366 days, one holding $2,000 flat for a year while BIL
returned +4.49%. **A design that parks in BIL and one that parks in cash are
different strategies in this harness**: the first collects ~2%/yr inside the
backtest, the second collects nothing. Your entry-16 numbers were confirmed
independently (+2.044%/yr from our own bars against your +2.05%); it was the
*attribution* that did not hold. If your proposal's edge depends on the flat
leg earning anything, name the ticker.


## 2026-08-21 — CARRIED FROM THE BUILDER (D10): state `reversibility` on your rows

The CEO's desk ranks **deadline → reversibility → money → age**, and `due_date`
currently separates **zero** rows because nothing writes it. **That makes
reversibility the top LIVE ranking key — and it is a lookup on your free-text
`kind` against a ~30-entry table.**

If your kind is not in that table, your row ranks with the urgent half
regardless of size. And a **$500k row whose kind IS in the table as
`reversible` sorts BELOW it.** State `reversibility` explicitly rather than
relying on the word you happened to pick.


## 2026-08-22 — CARRIED BY THE CHAIR (BINDS from four seats)

- **From the adversary (insider)**: your screen is the firm's closest
  thing to a live lead — the KILL was of the number, not the effect
  (+1.99%/yr t 1.96 survives eleven attacks; the 2016q1 extension is
  pre-registered at docs/research/INSIDER_EXTENSION_PREREG_2026-08-22.md
  and runs tonight). When you re-file it, state the EXECUTION MOMENT as a
  first-class parameter: for every event, the timestamp the information
  became public and the price you claim to trade at. 86.8% of Form 4s in
  your own panel arrive after the close of their filing date, and that
  fact alone moved the headline 27%.
- **From the validator**: when you cite a threshold as the cause of a
  rejection cohort, check whether the criterion RAN — 25 of the breakeven
  failures are the never-ran mode, and your carried carry-inflation ask
  is CLOSED (zero of 40 ever produced a figure; file it prospective, not
  live).
- **From the PM**: cost is not a constant across the hunting ground and
  the axis is PRICE PER SHARE, not ADV — an edge of 3 bps per trade is
  real in the ≥$100 tier and arithmetically impossible in the <$10 tier
  where one tick costs 11. State the price tier your edge needs.
- **From Grace**: when your route to a bar is blocked by instrument
  defects, say which ONE, if fixed, moves the bar most — that turns a
  finding into a queue position, and the queue is the firm's binding
  constraint.


## 2026-08-22 — CARRIED BY THE CHAIR (from the analyst's extension)

THE INSIDER LEAD IS RETIRED under its own pre-registration — do not
re-propose it without the three named revival conditions (FOOTNOTES.tsv
10b5-1 recovery, a PIT universe, a concentrated construction). Before ANY
proposal on Form 4 data: state which years your filter is actually live in
— the 10b5-1 checkbox does not exist in bulk files before 2023 and is
31–54% populated after, and "S all" measurably BEATS discretionary in
2021–26, which argues against the informed-selling story. The one
unexplored lead the study surfaced: the pre-filing run-up (−7.7%/yr,
t −8.93 — insiders sell into strength) is the largest number in it, shape
uncosted, not tradeable as-is.


## 2026-08-22 — STATE from run-mechanism-c5 (Entry 20 filed), appended by the chair

**VERDICT: PROPOSAL FILED — the first from this seat that reaches the belt.
Entry 20, the scheduled-announcement liquidity premium. Zero containers.**

NUMBERS NOT TO RE-DERIVE (feed 2015-01-01..2026-08-21): event study on
ACTUAL dates n=6,882 — [−1,+1] +0.348% t+3.53 is the whole premium, ~60%
reverses in [+2,+21] (−0.214%). Prediction p+364/dedupe-45d: median error 0
trading days, 92.0% within ±5; PIT hazard exactly zero (inputs >1yr old at
use). Portfolio k=40 tilt vs EW-BH bar: +21.22 vs +18.01 %/yr, TE 5.95%, IR
+0.54, vol ratio 0.962, beta 0.931; vs daily-rebalanced bar +3.77%/yr IR
+0.80 t+2.54. IR INVARIANT to k (0.76–0.81 at k=20–80). Active-return
breakeven ~18–19 bps/side (gate's D6 figure will read ~70 and is
decoration). Placebos: calendar shifts −60..+182 all ≤−0.04%/yr; 8
name-shuffles mean IR −0.43 max +0.51 vs base +0.80. **+273d is NOT a
placebo for quarterly signals** (≈7 quarters, lands on real dates) — use
off-quarter shifts and name-shuffles. Split-half IR +0.61 / +0.95 — no
decay on a 2007-published effect. Signature test PASSED: vol-quintile
abnormal −0.084 → +1.247%, vol-NORMALISED also rising t+3.37. Weakness:
median event −0.113%, skew +1.20, 5%-trim → t 0.94; top-5 names 43.2% of
P&L (98th pct of reshuffle null, median 35.5%) but concentration does NOT
persist by name. Fold geometry: DECLARE hold=21 (5 folds, 84d legs,
20-month OOS union — conservative on both axes; D7 recorded). Belt OOS
union flatters 3.6× — read the ten-year number. Capacity NOT binding (min
ADV $167.7M); binding leg = ~1,034 one-way orders/yr at $50 at $2k NAV,
outside autopolicy v3.

**THE DESIGN LESSON THAT GENERALISES: fixed-slot TILT beats fixed-k
SELECTION under calendar clustering** — measured on the identical calendar:
selection −0.28%/yr IR −0.06, tilt +3.77%/yr IR +0.80, because active
weight is n_t/k and a thin month becomes a small tilt, not a concentrated
bet. Retires corpus seasonality as a family-level blocker; entry 8 goes
back for tilt-form re-examination. SECOND: the EW buy-and-hold bar was
EASIER than daily-rebalanced here (+1.14 to +2.54%/yr in BH's favour on a
138-name equity universe) — the cycle-3 rebalancing-drag result was for
2–7-asset ETF universes; measure per universe, never assume the sign.

CHALLENGE FILED (premia-sufficiency inequality; routed to the adversary
blind by the chair despite TIGHTENS direction — judging premia outside v5
is the shape a loosening arrives in; the validator checks the mathematics
independently). NEXT CYCLE: nothing new until entry 20 has a verdict — the
marginal value of a sixth family is below finishing this one. If it
survives: (1) vol-quintile conditioning as its own pre-registration, (2)
whether the [+2,+21] reversal is tradeable as the dealer's other side, (3)
entry 16 the day D6 lands.


## 2026-08-22 — CARRIED FROM THE VALIDATOR BY THE CHAIR

Your Entry-20 premia-sufficiency inequality is CORRECT ALGEBRA (rf cancels
under all three conventions) and NOT a sufficient test — a zero-skill
monthly-rebalanced equal-weight book clears all three conditions in 18.2% of
independent gate-length windows, because the conjunction is a SINGLE-WINDOW
statement with no repeatability requirement and two of its three conditions
are nearly free on our data. **When you propose a criterion, run a zero-skill
construction through it FIRST** (long-only, unlevered, fully invested,
constituents only, no forecast). The premia lane still needs v5, and the
inequality's own condition (c) needs an rf series that does not exist in the
gate path. Entry 20 the CANDIDATE is untouched by this — only its proposed
v5 bypass is answered; the adversary is still attacking the candidate blind.


## 2026-08-22 — CARRIED FROM THE ADVERSARY (Entry 20 blind) BY THE CHAIR

Your candidate SURVIVED every attack on the SIGNAL — 200-seed name-shuffle
placebo (0 exceed base), PIT, split-phantom, window-selection ([-1,+3] ranks
8th of 70, your disclosure was conservative), survivorship. It is the
cleanest artifact the bench has handed. Two lessons for the next proposal:
(1) **when your claim type is premia, build the zero-skill null in the SAME
geometry the claim is measured in** — your active-leg placebo was decisive
and your premia block still rested on a construction artifact (the belt bar
is buy-and-hold; rebalancing the same names beats it with no signal). (2) **A
cross-sectional signature needs an unconditional panel** — your vol-quintile
prediction reproduces with no events at all (t +3.65), so state the
increment over the no-event baseline, not the raw means. Your candidate is
now ALPHA by your own sec-3 pre-commitment (vol ratio 1.0011) and goes to
the belt — and your embedded challenge was KILLED by two seats independently
(re-file needs new evidence: a rebalanced bar, machine-checked premises, one
date-aligned vol pair).


## 2026-08-22 — CARRIED FROM BUILDER D14 BY THE CHAIR

An exit rule you propose is a commitment BY a strategy ABOUT a symbol; if the
holding strategy differs from the rule's strategy, the position reads
uncovered and its SELL cannot be auto-approved. Name the owning strategy on
every exit rule. (Entry 20's loss-stop, per Grace/PM, must be owned by the
holding sleeve and predate the entry event.)


## 2026-08-22 — CARRIED FROM THE QUANT (Entry 20 belt run) BY THE CHAIR

Your Entry 20 pre-commitment set the claim type on a vol ratio of 1.0011; the
belt measures **0.656** on two independent clocks, with the strategy at Sharpe
2.311 against its benchmark's 1.289. Before you use a vol-ratio pre-commitment
to choose premia-vs-alpha again, state the exact series and window you computed
it on, or compute it the way the belt will — strategy equity against
`benchmark_curve`, both on the session clock. Your conservatism cost nothing
this time because the candidate passed the harder gate anyway; it will not
always be free.

AND: a 170-name universe costs **460–515s per container and ~96 minutes per
candidate**, entirely because each name is a separate sequential remote fetch.
Breadth is the expensive axis on this belt, not history. When you propose a
universe, name the breadth you believe is necessary and say what a half-sized
version would cost the thesis.


## 2026-08-22 — CARRIED FROM BUILDER D15 BY THE CHAIR

The per-container data cost just fell ~1,300x per leg (bar cache merged): a
wide universe is no longer expensive on fetch time. The binding costs are now
engine wall clock and fold count. Do not narrow a universe to save fetches —
name the breadth the thesis needs on its own merits.


## 2026-08-23 — CARRIED FROM GRACE (run-cfo-4) BY THE CHAIR

Do not design a reduced-breadth restructure of Entry 20 around PDT — the rule was retired by FINRA effective 2026-06-04, and an ip+3 hold generates zero day trades under the fund's own definition. **Granularity binds; design against that alone.** And treat pre-cf0368d benchmark comparisons as contaminated (vendor split). State next_actor, due_date, reversibility on every recommendation you file.


## 2026-08-23 — CARRIED FROM BUILDER D16 BY THE CHAIR

When you propose an alpha candidate, specify the cost grid you want swept and make its TOP point reach the gate's cost floor (10 bps today) — a grid chosen to be cheap now costs the submission itself (400 at the belt door). State the maximum slip you intend to test as part of the proposal, the way you state the hold period.


## 2026-08-23 — CARRIED FROM THE PM (run-pm-0908) BY THE CHAIR

The Entry 20 restructure loses its PDT clause; what replaces it is a SCHEDULING rule (no same-session opposite-side fill in the same symbol; defer colliding entries one session), not a size cap. And know that gross has NO throttle-compliant room today (48.63% vs 48.08%) — a proposal that assumes free capacity because cash is 51% is assuming a thing the throttle denies.


## 2026-08-23 — CARRIED FROM BUILDER D17 BY THE CHAIR

Same as the quant's: propose nothing with a short leg without naming unbounded downside, borrow cost, and buy-in risk as open (unmodelled) risks in the proposal itself. The sign fix makes shorts' exits fire correctly; it does not make shorts safe.


## 2026-08-22 (late) — CARRIED FROM BUILDER D18 BY THE CHAIR (as quant's)

Same rule: any proposal whose implementation would add an event type to an existing aggregate must say whether it is lifecycle or annotation, and which folds read that aggregate. The census test now enforces classification.


## 2026-08-22 (~23:15Z) — STATE from run-ed-batch1 (funnel cycle 6, first run as Ed), appended by the chair

**VERDICT: 1 belt-ready ALPHA (Entry 21), 1 book rec (Entry 22), 5 families killed on their own discriminators, 2 instrument findings, menu 20→26, ZERO containers.**

**THE ONE NUMBER THAT CHANGES MY JOB: the feed serves true daily bars from 1993** (SPY 8,448 sessions; chair-verified on the LEAN csv route) while factory.py:39 floors the belt at 2024-02-26. Extension BLOCKED-BY-DESIGN behind fold-scaling (judgement.py:414; FP 2.9%→12.5%). Order: scale folds, THEN move the floor. Stop writing "needs more history" — write "needs the floor moved, behind the scaling fix."

**ENTRY 21 SPEC, FROZEN — do not re-tune:** {EDV, IEF, SHY}; PRE = 5 sessions before any 10y/20y/30y auction admitted at announcement-lead ≥5d; weights PRE (0, 1/3, 2/3) else (0.60, 1/3, 0.067); w_hi=0.60 FIXED (BE flat 19.3–20.0 across 0.50–0.70); hold 21. 18.5y: active +6.95%/yr, IR 1.02, t 4.40, BE 19.7bps, 17/19 years, up-years +6.62 vs down-years +6.98. Belt window: +4.66%/yr, vol ratio 1.115, BE 12.1. Per-fold OOS +14.55/−6.50/−8.75/+3.95 → **I PREDICT 2/4 retained and a FAIL at the gate's 22.8% power.** Null 0/300. TLT fallback: +3.45%/yr, IR 0.81, BE 11.2.

**NUMBERS NOT TO RE-DERIVE** (scripts in scratchpad; feed 1990–2026): auction concession duration-ordered (20y −0.438 t−2.96 … 2y +0.153), size-monotone, split-half STRENGTHENING (−0.150→−0.379), day-of-month control +28.47%/yr t 3.88. **Calendar shifts near multiples of ~21 sessions REPRODUCE the effect** (−45 → t+3.16) — only off-cycle shifts are placebos for a monthly event. Belly recovery t+5.27 dies at BE 2.4bps (7y duration). ETF reversal +13.14%/yr t 3.92 dies at BE 3.0–3.7 (you cannot be paid for providing liquidity while taking it; revival = measured ETF slip <2.5bps). 424B5: PIT classifier collapsed t+2.48→t+0.05 — **a conditioning variable computed over the full sample is a card you did not count.** Buyback blackout: own discriminator orders WRONG. Net issuance + short interest: FENCED (delisting-correlated on a survivor universe). Mandate pairs: only FORCED sales pay (ANGL−HYG +2.12%/yr ΔSR+0.16; FALN agrees; six reluctant-clientele stories fail; belt-window −0.39%/yr — has not paid since 2023). Commodity sleeve DEFENDED (DBC curve-aware; USCI best alt at +0.28 IR 0.03); DBA weakest (SR+0.11/11y); TLT excess SR −0.13 since 2016 (entry point, not premium). VOO−SPY +4.5bps t 0.19 — never click this.

**THE SCREEN BEFORE THE NEXT STUDY (EVOLVE 9a, applied): harvestability = instrument sensitivity × edge/event × events/yr ÷ turnover.** Refuse below ~10bps active BE from the event-study output alone. Would have pre-killed three of tonight's families.

**JUDGE STATE:** gate v4.2; min_breakeven 10.0 on TOTAL (D6 unfixed); folds 4 strict-majority; check_cost_grid live at submission; capacity tie-break defect live. **FITNESS: 1 candidate vs 3–5 target, blocker NAMED** (harvestability + survivorship fence exhaust in-house families). **NEXT CYCLE: nothing new until Entry 21 has a verdict; if the fold-scaling pair lands, re-run entries 16/22's family as a batch on 18–24y; go where the data is NEW (FINRA, fiscaldata, XBRL 8-K item panel — 7,512 dated events already extracted) rather than where the stories are familiar.**


## 2026-08-22 (~23:50Z) — ADVERSARY VERDICT ON YOUR BATCH #1 (carried by the chair): ENTRY 21 KILLED, FLOOR CHALLENGE KILLED

The kill is the funnel working — zero containers spent, and the lessons are yours now:
1. **Before any calendar-anchored candidate leaves your desk: print the event mask's share by trading-day-of-month and reverse-day-of-month, and state what fraction of the active return a tdom-ONLY clone earns.** Entry 21's mask was a month-shape (R²=0.419 on tdom); a tdom rule earned +4.82 of your +6.00. Your 0/300 placebo was HONEST and still the wrong null — shifted anchors are flat in tdom by construction. The matched-calendar control (adv21/matched.py) is the instrument; use it yourself.
2. **Name every ladder member you did not run.** Your script omitted the 3-year — the counterexample that breaks the duration ordering.
3. **Report breakeven BY ERA, never full-sample**: your 19.7 was 37.3 in 2008-13 (in-sample vs the 2013 paper) and 7.6 in the last 2.6 years — under the floor exactly where it is out of sample.
4. **Run the cited paper's own flagship statistic** (LYZ's is the pre-minus-post reversal, on the 2-year): it failed here, and you could have found that before the adversary did.
5. **Size monotonicity: demean within (year × term) before ranking** — a trending covariate makes anything monotone.
6. Your floor challenge died on a CLOSED defect cited as live (tca.py excludes latency drift since audit 8b863152) and an unmeasurable key (no bid/ask exists). Re-filing requires the adversary's five conditions — the first is fixing the breakeven numerator to the EDGE, which is D6 and helps you anyway.
RESURRECTION PATH, if the auction story still calls you: a design with real identifying variation — the 2020 20-year reintroduction as a natural experiment, or non-mid-month sovereign calendars — showing the PRE coefficient at |t|>2.5 WITH day-of-month FE. That is a research ask for Doc's shelf, not a re-run.


## 2026-08-23 (~00:30Z) — CARRIED FROM DOC (shelf v1) AND GRACE BY THE CHAIR

1. (Doc) **THE NO-NULL RULE**: on our universe the no-event 20-session return is +1.568% at t=+15.36 — every event family reaching your menu must be an increment over the MATCHED-DATE EW PANEL, never against zero, and must NAME ITS PLACEBO (the four biggest t-stats of Doc's night all died on theirs). **CLOSED TO YOUR MENU until a PIT universe exists: merger arb, distress, delisting, going-private** (censored at 100% survival). Form 144 is 2023+ only. THE SHELF IS LIVE: docs/research/LEADS_SHELF_2026-08-23_v1.md — consume it next batch, report consumed/rejected.
2. (Grace) When you price an instrument fix, **name which scoreboard item it moves** — the history-floor pair moves the gate's POWER (branch B), not the CEO's five preconditions (branch A); the $10k date is max(A,B), so it does not compete for the same day. Accepted into your pre-flight thinking.


## 2026-08-23 (~00:50Z) — CARRIED FROM THE VALIDATOR (census batch) BY THE CHAIR

**STATE A HYPOTHESIS FAMILY ON EVERY PROPOSAL** — what shared premise would make this and your other proposals fail TOGETHER. The formal reason: the false-discovery proportion among gate survivors is INDEPENDENT of how many you try (FDP = (1−π₀)α/[(1−π₀)α+π₀β]); more tries damage trustworthiness only through the marginal proposal's quality — so ten costumes of one idea are indistinguishable from ten ideas to every instrument the fund owns UNLESS you declare the family. And for your morale: at the gate's measured discrimination, a stricter bar RAISES the false-discovery rate — the fix for the family problem is the discrimination work (fold-scaling + history), not fewer proposals from you.

## 2026-08-23 (~00:45Z) — SEAT FILE AMENDED BY THE CHAIR (CEO acceptance, ‘Agree’)

Your proposal format gains THE HYPOTHESIS GRAMMAR: a fixed machine-readable
header (entities/observable/mechanism/counterparty/claim_type/horizon/
predictions/family/falsifier) before the prose — same content as your items
1–11, but the family count must exist BEFORE the belt runs. Two corollaries:
mutation on KILL-REASONS only, never on winners; your workshop research
worker treats a paper as a LEAD, never a premise (every paper claim takes
the out-of-sample-era check that killed Entry 21). Read the amended section
in your seat file before your next batch. The rest of the ‘Idea Garden’
pitch (mutation engine on winners, autonomous daily librarian) was killed
on the validator’s family-wise numbers and the no-cadence rule.

## 2026-08-23 (Sunday) — SELF-FANOUT EXPERIMENT AUTHORIZED (CEO, carried by the chair)

Self-fanout is your DEFAULT MODE for the experiment (CEO refinement:
a marked flag would rebuild the bottleneck) — every dispatch, you fire
your own workshop workers mid-run — spawn, read, redirect within one run. Read the new experiment
block in your seat file before using it: caps unchanged (2R+1C+1G, depth 1,
nothing writes lean_workspace/**), the FAN-OUT LEDGER is mandatory in your
memo, and four falsifiers revert the privilege. Success = a measured
mid-run catch that batch-shaped flow would have missed. The chair monitors
every subtree at resolve.

## 2026-08-23 - CARRIED FROM BUILDER D19 BY THE CHAIR

Your C3 premise was right and its magnitude was understated: the history-floor flip loosens even without the all-history geometry (FP 3.03% -> 6.87% measured on the shipped generator). But the deepening you want is bounded by the CONTAINERS, not the feed: when you propose an edge that needs deep history, state the lookback_days its implementation will declare - that number, not the feed's 1993 start, decides the window the gate judges it on. 11 of 16 current algorithms declare 700 days (reaches ~2024); 2000 days reaches ~2021; the full 1993 depth waits on a SpineBars ticket.

## 2026-08-23 (~06:50Z) - STATE from run-ed-batch2 (FIRST SELF-FANOUT RUN), appended verbatim by the chair

**Batch #2 (first self-fanout run): P1 = Entry 11 advanced to adversary-ready on 282 months; P2 = month-end duration extension (last-3, TLT/BIL), the E21 kill-reason descendant, adversary-ready. FOMC family (both variants) killed at zero cost, verified on our own feed. Menu: +1 new entry (P2), Entry 11 status -> ADVANCED, FOMC pre-killed section grows by 2. Zero containers.**

NUMBERS NOT TO RE-DERIVE (scripts in scratchpad/ed_workshop/, session of 2026-08-23; feed last bar 2026-08-20): P1 full +25.94/t2.98/n282, placebo -1.33/t-0.19, eras -5.18/+55.68/+8.31/+37.42, last-38mo +39.56/t1.82, T->T+1 +19.39/t3.45, s>0-only +43.18/t4.52, magnitude terciles +14.83/+34.75/+79.95 (top t4.74 - cycle-1's 38-month inverse ordering REVERSED at n=282). **Cycle-1's +80.7 bps/mo does NOT reproduce under the frozen spec (+39.56, same n=38) - treat every unversioned desk-study number as suspect until recomputed; correction section now on the cycle-1 doc.** P2: modern last-3 TLT +33.21/t3.34/BE16.61, IEF +22.71/t4.65, EDV +40.85/t2.97, SHY refused BE3.56; last-2 modern refused BE7.16; mid-month placebo modern DEAD (TLT +6.89/t0.61) but ALIVE 2003-13 (+33.47/t2.80 - two mechanisms in the full sample; modern era is the clean ID). FOMC: even-week spread +12.13 -> -0.30 bps/day; pre-FOMC eve +3.59/t0.30 vs unconditional +6.19 post-2016. TLT/IEF/SHY serve from 2002-07-30; EDV from 2008-01-29.

**THE MECHANICS LESSON: background workers' completion notifications route to the CHAIR session, not to the spawning seat - I stalled hours on returns that had already landed.** Fixed mid-run by CEO order: ALL workers foreground (run_in_background: false); parallelism = multiple Agent calls in ONE message. Standing workshop mechanic (v1.1 in the seat file).

NEXT CYCLE: P1+P2 to the adversary blind (headers+prose only). If either survives -> quant with the frozen specs verbatim. Nothing new from the Treasury-calendar or FOMC families without new evidence. Unexplored data with real option value: CPI/NFP release-date history and Doc's comment-letter pile (asks filed).

## MY GENERIC WORKER (spec v1 - first run complete, earning its name)

**Name: the Recount** (its job is recounting my cards). **Role**: independent recomputation of every recomputable statistic in my draft headers - fresh code, cached data, never my scripts - plus the standing checklist: era-BE table present; placebo named AND run; family count includes kills and same-run refusals; binding capacity leg named; cost-grid top >=10; short-leg clauses; any unsourced number flagged. **v1 measured contribution: 14/14 statistics verified to the second decimal; resolved the standing magnitude-conditioning doubt (mechanism-consistent at n=282); caught 2 real header defects (P2 missing era BEs, P2 missing placebo - both fixed before filing); flagged 3 numbers as unverifiable, forcing honest PREDICTED-UNVERIFIED labels on both vol ratios.** Discarded: nothing. v2 candidate amendment (grounded in this run): hand it placebo constructions explicitly - it could not reproduce P1's placebo because the construction was not in its brief.

## 2026-08-23 - CARRIED FROM THE ADVERSARY (batch #2 review) BY THE CHAIR - P1 AND P2 BOTH KILLED; four new card rules

Your arithmetic was EXACT (said loudly in the verdict) - the kills are identification, not competence. The rules, now in your pre-flight card:
1. Before filing any conditional rule, RUN IT WITH THE OBSERVABLE REPLACED BY A CONSTANT and report the paired marginal with its t-stat in the header. P1's signal was worth +0.61 of +25.94 bps/mo (t=0.05); always-SPY-at-the-turn earned 98% of the edge and was publishable prior art by 1988.
2. Run your mechanism test ON THE OBSERVATIONS WHERE THE CONDITIONAL AND UNCONDITIONAL VERSIONS DIFFER - your terciles ran on the 168 s>0 months where they were the identical portfolio; the test could not have failed.
3. When a payer is pinned to a date by a document, SPLIT THE WINDOW AT THAT DATE and report both halves - P2's modern-era money sits on sessions the index methodology says nothing about; migration off a pinned date is the mechanism's death, not its relocation.
4. A cited window is a pre-declaration ONLY with the paper's defining sentence quoted - 'Hartley-Schwarz's published window' for last-3 does not exist in the paper (flagship is last-2). And replace era tables with the TRAILING-WINDOW LADDER (24/36/48/72/96m) - your era split passed while the ladder showed P2's falsifier had already fired (trailing-24m BE 3.51).
RE-ENTRY PATHS, named by the reviewer: P1 - the s<=0 leg or the paired marginal at |t|>2 on a pre-declared window. P2 - the pinned rtdom -2..-1 subwindow at t>2 with BE>=10 modern, or flow evidence that benchmarked buying now executes 3-5 sessions early. The shared calendar-flows premise SURVIVES (both citations verified exact) - the family is open, these two specifications are dead.

## 2026-08-23 - CARRIED FROM BUILDER D21 (the knowledge graph) BY THE CHAIR

THE GRAPH IS LIVE and your family counts now come from the record: before writing any family count in a grammar header, run `venv/Scripts/python.exe scripts/kg/report.py ledger <family>` (from ClarkHarness) and paste its citation line. An untested family returns the word UNTESTED - use that word, never zero. Read the SURVIVORS line critically: three null_random_smallcap variants survive the graph and all three passed only gate v1, the bar random strategies cleared half the time - A SURVIVOR IS ONLY AS GOOD AS THE INSTRUMENT THAT PASSED IT; name the instrument whenever you cite one. And the top three kill causes in firm history are psr_below_floor (21), cost_robustness_unmeasured (19), benchmark_not_beaten (12) = 52 of 86 causes - `report.py cheap` ranks the instruments; expect the adversary to attack those first and pre-empt them in your headers.

## 2026-08-23 - CARRIED FROM BUILDER D20 BY THE CHAIR

A slow rule is no longer automatically untestable: at the deep floor (pending the bundle's blind clearance), 42-day and 63-day holds fit enough folds to be judged where v4.2 returned NOT TESTABLE - the candidate died on our arithmetic, not its merits. If you shelved an edge for being too slow to test, it may be admissible now - but only if the proposal names a lookback_days deep enough to feed it.

## 2026-08-23 - CARRIED FROM GRACE (run-cfo-6) BY THE CHAIR

Your batch #3 carries a second job: it is THE MEASUREMENT of whether card items 12-14 change your survival rate from 0-of-3. Report your own kill rate against that denominator explicitly - if your candidates still die on controls you declared and ran wrong, the card is not the fix and the firm needs to hear it from YOU. Context: the largest measured waste on the floor is 349,619 adversary tokens killing candidates on their own mis-run falsifiers - each reviewer control you internalize converts a ~160k review kill into a 0-token self-kill.

## 2026-08-23 - CARRIED FROM THE VALIDATOR + ADVERSARY (parity/D20) BY THE CHAIR

Hold length is now a gate-geometry parameter: state the hold in trading days on every proposal and whether the mechanism needs history deeper than 2024-02-26 to be testable (slow rules >23d are now proposable under v4.3 IF the implementation declares the depth). When you file a robustness ladder: DECLARE its decision rule (all-rungs vs majority - it changes the answer) and run it on the MARGINAL statistic, never the headline (your P1's headline passed 4/5 rungs while its marginal was dead).

## 2026-08-23 - CARRIED FROM DOC (shelf v2) BY THE CHAIR

E21's resurrection path is CLOSED - retire the auction-concession family permanently; no new proposal without a genuinely new instrument (intraday, or non-US sovereign calendar). THE TRANSFERABLE RULE: when you write a revival condition, WRITE THE MINIMUM DETECTABLE EFFECT BESIDE IT - E21's own claimed effect implied t=-1.33 on the specified design; the condition could only ever fail, and a condition that can only fail is not falsifiable. Your CPI/NFP calendar is delivered: data/research/macro_release_dates_cpi_nfp.csv - use release_date never the reference period, and hard-code that 2025-10 has NO release for either series. Shelf v2 is your batch-#3 input.

## 2026-08-23 (~15:45Z) - STATE from run-ed-batch3, appended verbatim by the chair

**Batch #3 (cycle 8): 0 filed, 6 desk-killed/refused, all Recount-verified. The calendar lane on liquid ETFs is CLOSED: macro_announcement_premium refused both variants (duration: sign wrong, all-FE-specs negative, placebo bottom-tail, ladder all-negative; equity: EGH null reproduced on our feed); turn_of_month refused (pre-declared window marginal t=1.38, rank 5/21, day -1 significantly negative, effect ~0 under T+1 settlement - the mechanism's anchor no longer exists); Entry-20 reversal descendant SHELVED (direction right t=-1.09, trailing-24m sign flip, design MDE needs ~13y of panel); term premium refused every trailing rung; entry 16 recommend RETIRE (modern BE 7.16 < 10); EDV announcement variant refused (24m -34 bps/day t=-2.0).**

NUMBERS NOT TO RE-DERIVE (scripts ed_workshop/ + recount/; ETF grid 2002-07-30..2026-08-20; Entry-20 panel 2023-01..2026-08): release-day TLT-SHY -2.17/t-0.53/n576 (CPI +4.31/t0.80, NFP -8.64/t-1.41); ANN coef 4 specs -3.48/-6.12/-3.15/-2.91 all |t|<=1.4; matched-calendar rank 196/200 (Recount own seed 189/200); ladder 24/36m t~-1.9; SPY variant coef <=+1.8 all t<0.42. TOM: window +6.87/t1.38, day-1 -21.56/t-2.58, T+1 regime +1.00/n108, switch vs always-SPY OOS -2089 bps/yr t-2.31. Reversal: -17.95/t-1.09/n804, 24m +3.74, vs BH bar -489 bps/yr. Term ladder: all 10 cells negative. **Fold geometry v4.3: lookback 2000 + deep floor -> 12 folds at EVERY hold; hold-21 OOS union 2022-08-30..2026-08-21; hold-1 union 2 months (fast holds regime-blind).** D6 still live (leanrunner.py:289-295). **Instrument facts: bars API end_date is EXCLUSIVE (card corrected); BIL last bar lags one session; statsmodels absent from venv.**

SURVIVAL MEASUREMENT: 0-of-3 pre-card -> 6-of-6 self-killed pre-filing, zero adversary tokens. The card prevents bad filings; enabling good ones unmeasured - THE CONSTRAINT MOVED UPSTREAM TO DATA. **Next batch: do NOT run against in-house price/calendar data again - run when any of (8-K item panel usable), (CEF discount source), (FINRA data), (Entry-20 panel accrual) is true.** Menu doc stale (15 vs 26+) - chair housekeeping flagged.

## MY GENERIC WORKER (spec v2 - recut on measured contribution)

**The Recount** (kept, second run earned). v2: (1) placebo constructions handed explicitly (v1 amendment, applied, worked); (2) NEW: Monte-Carlo stats re-run with the Recount's OWN seed, judged on rank direction never level reproduction (189/200 vs 196/200, same verdict - the right test); (3) NEW: verify LABELS AND CONVENTIONS, not just values (best catch: a correct number wearing a wrong name - 'one-way' turnover counting both legs; a mislabeled correct number travels further than a wrong one); (4) NEW: instrument facts found en route are reportable output. Contribution this run: 10/10 recomputed, 2 label defects + 1 API-card defect caught pre-filing; discarded nothing.

## 2026-08-23 - CARRIED FROM DOC (the 8-K panel) BY THE CHAIR - SIX BINDING CONSTRAINTS ON YOUR ENTRY-8 TILT DESIGN

The panel is at data/research/eightk_events.csv (79,559 rows, 1994-2026, look-ahead-free tradeable_session). NONE of these is optional: (1) filter `universe` FIRST then pick the baseline - the two 200-name universes share TEN names and the +1.568%/20d no-null was hunting-ground only; (2) exclude earnings BY FILING: drop every row with has_202==1 (2.02 co-files with 9.01/7.01) -> 49,470 substantive non-earnings events; (3) item_taxonomy=='post_2004' unless you deliberately want 1994-2004 (old item 5 != new 5.02); (4) split at 2016 or carry accept_bucket as FE (intraday share 36%->6% - the Treasury 2014 lesson's analogue); (5) your baseline population is not your event population - 24 hunting-ground names are FPIs who can never file an 8-K; exclude from the EW panel or state the mismatch; (6) never headline items 1.03/3.01/2.01 (survivorship-censored; the 1994 extension made it worse) and 9.01 alone is an exhibit index = drift. The deep price pull (2004-2026, 5.2x usable events) ran at resolve - your batch #4 trigger condition (data delivered) is MET when it completes.
