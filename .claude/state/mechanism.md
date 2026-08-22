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
