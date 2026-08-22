# pm — working state
(appended by the CTO at each dispatch resolution; newest at the bottom)

## 2026-08-20 — seeded at hiring
- Book at seating: 7 legacy positions ~8% each (GLD XLE NVDA SPY SOFI INTC MSFT),
  plus sleeve_beta_500 live since 2026-08-19: TLT 3.019871 + DBC 8.122157, 12.4%
  each, six exit rules armed, time exit 2026-09-08.
- Open questions at seating: gross ~83% vs throttle ~77%; trim of three
  gate-failing legacy strategies undecided; TCA n small; INTC strategy inert 226
  sessions.
- Standing rule: sleeve success = loop completes measured, NOT P&L.

## 2026-08-19/20 — first review delivered (docs/pm/PM_REVIEW_2026-08-19.md)
- Book verified live: sleeve clean and per pre-registration; INTC has NO loss
  rule and is 32.2% of book risk on 9.0% of capital (closest-to-binding);
  7 of 9 positions lack real exit rules; 56% of NAV deployed on gate-failing
  strategies; throttle 0.7235 ignored at 97.3rd-pct cross-section.
- Nine recommendations open with the CEO; #1 (throttle: trim ~\$460 or written
  override) decides first since #2-4 (retire the three failed strategies) makes
  it moot. TCA n=12/20; Trend paying 21.5bps/side; sleeve fills degenerate
  (decision=arrival=fill).
- Next review: re-pull marks; check whether CEO recorded the sleeve thesis
  answer and the weekly written review (falsification #4 clock running from
  08-19 fills).

## 2026-08-20 — second dispatch (1eef5264 / trace-pm-review-1): staging tickets, rec-7 exits, rec-9 redesign

- Book UNCHANGED from first review's marks: NAV 2011.81, cash 346.92 (17.24%),
  gross 1664.89 (82.76%), 9 positions, no fill since 2026-08-19T18:20 (sleeve
  TLT). Marks identical across the v4.1 restart. Treat as static, not fresh.
- CORRECTED my own memo: "gross → ~58%" was the FRAMEWORK's $500-partial-trim
  number (82.76 − 500/NAV = 57.91%), NOT full retirement. Full close of the
  three strategies = $1,164.35 of sells → gross 24.88%, cash 75.12%, realised
  −$14.35. Say this if anyone re-cites 58%.
- Throttle 0.7206. "Normal gross" is defined NOWHERE in code — throttle.apply_to
  has zero callers. Reading A (× book gross) = 59.63%/$465 of sells; Reading B
  (× 100%) = 72.06%/$215. I use A. Tickets T1–T4 ($523) satisfy it; fewer than
  T1–T4 = throttle ignored again, needs written override.
- 8 sell tickets issued (T1 SPY-TEST .052217 / T2 INTC 1.608762 / T3 SOFI
  9.18819 / T4 MSFT .340051 / T5 NVDA .749886 / T6 GLD .424471 / T7 XLE 2.749912
  / T8 SPY-Trend .16554) + 3 state tickets S1–S3 (pause+alloc 0+archive; do
  BEFORE the sells). Recommended disposition: CLOSE ALL — no legacy position
  survives on its own merits; survival-by-inertia makes orphans. If CEO wants
  GLD/XLE/SPY, it must be NEW pre-registered declared beta, not inheritance.
- KEY WARNING carried forward: risk concentration crosses the 50% limit at T6
  (DBC 62.3%) and reaches ~101% sleeve-only, because TLT/DBC corr is −0.4379 so
  TLT is a NEGATIVE risk contributor. Arithmetic, not danger. Effective bets
  3.88 → 2.49 (floor 2.0). riskengine.py:571-584 will warn. Expected.
- MECHANICAL FACTS I re-derived and must not re-derive: exit KINDS are only
  (loss_pct, gain_pct, time, thesis) — exitrule.py:41. No trailing/correlation/
  NAV-drawdown kind. Exit sizing is SYMBOL-level (exitrule.py:269,287) so a SPY
  rule sells all 0.217757. autopolicy has NO actor check — the "PRE-COMMITTED
  EXIT FIRED" marker alone (autopolicy.py:87-91) triggers auto-approval, so
  COMMITTING AN ALREADY-BREACHED RULE = EXECUTING. Always check the level
  against live unrealised before proposing. StrategyState has no "retired" —
  DEPLOYED→PAUSED only (strategies.py:24-37), and PAUSED does NOT close
  positions (proof: TEST paused, still holds $40.16 SPY).
- 1.5σ 21d levels (σ_ann×√(21/252), from /risk/advanced.correlation.
  annualised_vol_pct): TLT 4.10 (validates the frozen 4.0), DBC 9.83 (frozen 8.7
  = 1.33σ today), GLD 13.61, XLE 10.18, SPY 5.79, MSFT 15.97, NVDA 16.23,
  SOFI 23.25, INTC 36.33. None breached today.
- LIVE GATE EVIDENCE (better than docs/book_rejudged.json v2): /lean/sweeps now
  serves 84 sweeps with holdout_result. mean_reversion_cyclicals = ZERO orders
  in ALL 5 holdouts, psr 0.0 everywhere. momentum fold PSRs 41.5/18.3/64.6/9.5
  → 0 of 4 clear 65.0 (best misses by 0.42). trend 2.7/0.0/85.3/15.8 → 1 of 4.
  Gate v4.1: min_psr 65, min_orders 20, 4 folds strict majority (gate.py:165,183).
- TCA UNCHANGED (no fresh fills): n=12 of 20, reliable:false, 4.96 vs 5.0 bps;
  Trend 21.47bps/side (worst 81.22); sleeve 0.00bps on 2 fills, latency 189.3s.
  The 8 sell tickets take n 12→20 = exactly the bar, and discharge sleeve
  falsification #2. Only argument in the memo for doing more rather than less.
- OPEN EXCEPTIONS: (1) machinery-test GLD loss_pct 25% is LIVE, not overridden,
  and would auto-execute a full-GLD sell — R4. (2) sleeve thesis exit notes still
  say "answered by a human at every review", the design the CEO replaced — R2/R3.
  (3) sleeve is absent from /strategies AND /strategies/divergence entirely —
  framework §3 gap now MEASURED true. (4) nav_strike UNOBSERVED in this process.
- Rec 9 redesign delivered: TLT + DBC recorded theses, D1–D9 deterministic
  (only D1–D3 both watch AND act; D5 currently TRIPPED at n=12; D6 UNTESTABLE —
  simulated venue, no broker equity; D7 has NO machinery), J1–J6 judgemental.
  J6 replaces "a week with no written review": 7+ days with neither a PM dispatch
  nor a written note. CLOCK FROM 2026-08-19 FILLS → FIRST TRIP 2026-08-26.
- Time exit on_date 2026-09-08 is 21d from the rule-SET date (08-18) = 20d from
  FILL (08-19). Frozen date stands; recorded so nobody claims 21-from-fill.
- Self-correction logged: I nearly filed a realized_pnl_usd=0.0 "defect" that was
  my own field-ordered print misreading. /strategies returns 25.63 correctly.
- NEXT REVIEW: check which tickets executed and re-run the §1c arithmetic on what
  actually filled; expect a risk_concentration warn alarm if T6+ executed and do
  NOT read it as new; check TCA n (should be 20 if the batch went) and give the
  first RELIABLE cost verdict; check whether R2/R3 superseded the thesis notes;
  check J6 clock (2026-08-26) and D5/D6 status before the 2026-09-08 time exit.
- [CTO note at resolve, 2026-08-20]: S1–S3 executed same night minus archive
  (all three strategies paused + allocation 0; archive deferred until flat).
  T1–T8 NOT staged overnight — PROPOSAL_STALE_AFTER_MINUTES=120 would have
  auto-declined them before the CEO woke; they stage fresh when the CEO is live.
  Exception 1 (machinery-test GLD rule) CTO-verified live and filed as R4.

## 2026-08-21 — third dispatch: DESIGN SLEEVE v2 (premia book at full mandate throttle)

[Appended verbatim by the CTO from the seat's delivery; full memo at
docs/pm/PM_SLEEVE_V2_2026-08-21.md — the STATE below is the seat's own.]

- BOOK AT READ (spine clock 2026-08-20T19:15-19:16Z): NAV 1885.25, cash 1383.46
  (73.38%), gross 501.79 (26.62%), TWO positions only — DBC 8.122157 @31.11
  ($252.68, 13.40%, +1.07%) and TLT 3.019871 @82.49 ($249.11, 13.21%, -0.36%).
  All four legacy strategies now `paused` with $0 exposure in /strategies — the
  T1-T8 tickets DID execute 2026-08-20, contra my last STATE's "not staged
  overnight" note. Exit coverage is 100% for the first time. HALTED (daily loss
  6.29%>4.00%, halted_at 15:52:31Z).
- THE FINDING OF THIS DISPATCH — carry it into every future review: the GLD
  sell at 2026-08-20T08:01:27Z filled at 100.0 on a 170.71 basis; GLD closed
  415.04. Realised destruction $128.26. It (a) caused the daily-loss halt;
  (b) is ~85% of the 7.42% drawdown (without it ~1.12%); (c) is INVISIBLE in
  attribution (/executions totals +11.71 while NAV fell 126.56 — phantom legs
  close no round trip); (d) ROOT CAUSE VERIFIED: exitrule.py:269-270 builds
  qty_by_symbol from the WHOLE book BY SYMBOL, ignoring strategy_id —
  machinery-test's rule sold Trend's GLD. HARD RULE FOR ALL FUTURE SLEEVES:
  no symbol in two strategy_ids. PEAK IS ROLLING-365d (riskmonitor.py:372-375)
  so the corrupted 2036.35 peak caps risk capacity for a YEAR unless a human
  decides. Headroom to the halt = $52.54 = 2.786% of NAV.
- UNITS DEFECT VERIFIED (report, do not re-derive): correlation.py:216
  normalises weights to COVERED GROSS; riskengine.py:118 feeds them to
  risk_contributions. component_risk_pct / portfolio_vol_pct / ES pct are
  BASKET-relative while judgement.py and max_component_vol_pct read NAV.
  (1) max_component_vol_pct is SCALE-INVARIANT — a composition control,
  UNTESTED as a size control. (2) riskmetrics.py:188-189/:288 multiply a
  basket pct by nav_usd: /risk/advanced ES $32.48 vs true $8.65 (1/gross =
  3.76x). reverse_stress and historical scenarios are CORRECT. Filed as R13.
- METHOD VERIFIED — bar-derived numbers REPLICATE the engine exactly at n=174
  (DBC vol 22.73, TLT 9.49, corr -0.4397, eff 2.47, ewma port vol 9.55, DBC
  comp 9.906 vs 9.8959). Recipe: std ddof=1 x sqrt(252), np.corrcoef, weights
  normalised to gross, EWMA lam=0.94. Reuse; do not re-derive.
- DATA: bars?lookback_days=2000 -> 1380 aligned sessions 2021-02-23..2026-08-20
  source alpaca for all 23 symbols tried. BIL is the cash proxy (CAGR 3.24%) —
  ALWAYS report excess-of-BIL Sharpe.
- EXCESS-OF-BIL SHARPE full/recent: TLT -0.55/-0.84, IEF -0.56/-0.90, DBC
  +0.63/+2.10, DBA +0.64/+1.16, SPY +0.71/+1.09, USMV +0.55/+1.06, SPLV
  +0.43/+0.93, XLV +0.48/+1.23, GLD +0.82/+0.36, VNQ +0.21/+1.21, HYG
  +0.11/+0.14. TLT's premium DID NOT PAY (-30.2% cumulative) — J2 STRIKE ONE
  2026-08-21; strike two at next quarterly review retires the leg.
- DESIGN: normal gross 61% (largest gross with zero-drift P(maxDD>10%/252d)
  ~11%); target = normal x throttle (0.7941 -> 48.4%), throttle BINDING for
  the first time. FOUR LEGS: TLT (term, menu 2), DBC (carry, menu 3), SPY
  (equity risk premium — NOT on the menu; the menu is the ACTIVE funnel), DBA
  (ag carry, menu 3). PHASE 1 (48.61%): hold TLT/DBC in sleeve_beta_500; BUY
  SPY $263.94 into sleeve_premia_equity; BUY DBA $150.82 into
  sleeve_premia_carry. effB 2.93/4.00, NAV vol 4.76%/3.50%. PHASE 2
  (2026-09-08, 61%): TLT 15/DBC 16/SPY 18/DBA 12 in per-premium ids. STOPS
  (1.5sigma 21d, FULL window, frozen): TLT 6.7% (fresh pre-registration on
  the NEW position), DBC 8.7% (v1's number, never relitigate), SPY 7.3%, DBA
  6.1%. Sum at stop $83.85 = 4.45% NAV. TIME EXITS 90d not 21.
- DECLINED (do not re-propose without new evidence): GLD (best Sharpe, ZERO
  premium, recent vol 31.43%), USMV/SPLV (contradicted on our data), HYG
  (equity beta in a bond wrapper), LQD (duration in a costume), VEA
  (duplicates SPY), trend-as-premia (needs a signal — ASK filed).
- BOOTSTRAP (block=21d, 20k paths, 1379 obs; zero-drift is the planning case):
  P(hit the LIVE halt) 21/63/252d zero-drift: today 0.6/4.3/27.5; phase1
  5.1/20.2/50.7; phase2 8.6/28.0/58.4. HEADROOM REPAIRED: phase2 0.0/0.3/9.6.
  THAT DELTA IS THE ARGUMENT FOR R1. P(maxDD>10%/252d) hist/zero: 50% 0.3/4.5,
  55% 0.7/7.3, 61% 2.1/11.3, 70% 4.6/18.7, 78% 7.7/25.4, 85% 11.5/32.0.
- 15 RECS FILED (R1-R15); R1 gates R4/R5/R11. Ordering: R1 -> R2+R3 -> R9+R10
  -> R4,R5. R11 dated 2026-09-08. Fallback if R1 declined: phase 1 = SPY only
  (40.6% gross), DBA deferred.
- LIMITS LIVE (brief was WRONG on one): min_cash_pct 0.05 NOT 0.10;
  max_risk_concentration_pct RETIRED (riskengine now checks component_vol);
  my last STATE's "risk_concentration warn expected at T6" is OBSOLETE.
  A 61% book cannot sit in one strategy_id (40% cap) — one id per premium,
  which finally makes strategy_overlap measurable.
- TCA: 20 orders but vs_assumption sample 8 reliable:false. The phantom fill
  produced NO outlier (poisoned quote was fill AND benchmark). D5 TRIPPED and
  UNTESTABLE-TODAY on paper at any n. R15 asks to route DBA to alpaca as an
  experimental deployment.
- STILL OPEN: sleeve_beta_500 absent from /strategies (THIRD review — R9);
  nav_strike UNOBSERVED (THIRD review); machinery-test rules correctly
  disarmed, do not re-file. J3 (ex-J6) clock: FIRST TRIP 2026-08-26.
- NEXT REVIEW: check R1's decision; halt cleared and stuck; SPY/DBA staged and
  at what prices; re-run effB/component/halt arithmetic on actual fills; J3
  clock; TLT J2 strike two; D9 (<25%) BEFORE endorsing the 09-08 transition.

- [CTO note at resolve, 2026-08-21]: exitrule.py:269-270, riskmonitor.py:371-374
  and correlation.py:216 verified line-exact before filing — the third
  CTO-instrument defect (scale-invariant component-vol limit) is mine and is
  now the metric working three times in one day. Memo filed verbatim
  (docs/pm/PM_SLEEVE_V2_2026-08-21.md), recorded as run-pm-sleeve-v2 with
  money_at_stake on all 15 recs — first seat to comply in substance. R1 is on
  the CEO's desk and NOTHING stages until it lands. Your J3 clock and the
  09-08 phase-2 date are in the chair's session log.


## 2026-08-21 — CARRIED FROM THE MECHANISM (cycle 3) BY THE CHAIR

First use of the `## BINDS` protocol. The seat named you; the chair verified the underlying code claim and carried it.

**Cash is $968.69 of a $1,885.74 NAV — 51.4% — as of 2026-08-21T21:14Z.**

The mechanism proposed nothing deployable this cycle, so **leg 3 of the team
metric has no help coming from that seat.** Stated plainly by the seat itself:
*"if that idle half needs a written reason, it will not be 'waiting on the
mechanism seat'."* The reason currently on the record is that the book is at
throttle target and phase 2 is dated 2026-09-08.


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


## 2026-08-21 — CARRIED FROM THE BUILDER (D10): state `reversibility` on your rows

The CEO's desk ranks **deadline → reversibility → money → age**, and `due_date`
currently separates **zero** rows because nothing writes it. **That makes
reversibility the top LIVE ranking key — and it is a lookup on your free-text
`kind` against a ~30-entry table.**

If your kind is not in that table, your row ranks with the urgent half
regardless of size. And a **$500k row whose kind IS in the table as
`reversible` sorts BELOW it.** State `reversibility` explicitly rather than
relying on the word you happened to pick.


## 2026-08-22 — STATE from run-pm-programme (the measurement trading programme), appended verbatim by the chair

**READ 2026-08-22T04:51–05:06Z. Market CLOSED; next open 2026-08-24T09:30 ET.**
- BOOK: NAV 1885.74, cash 968.69 (51.37%), gross 917.06 (48.63%), four legs
  (SPY/DBC/TLT/DBA), exit coverage 100%, 0 fired, alarms [], drawdown
  1.17%/10 off rebased peak 1908.09, effB 4.01, ES97.5 1.218%.
- **THROTTLE IS BREACHED, BY A LITTLE, AND NOBODY HAD SAID SO**: 0.7882 ×
  61% = 48.08% target vs 48.63% actual = +0.55pp/$10.42 over. No
  throttle-compliant room for a programme position; every deploy is a
  written excursion. **DATED COLLISION: phase 2 (61% gross, 2026-09-08) is
  12.9pp above today's throttle recommendation.**
- **THE FINDING — carry it forever**: arrival_price is
  get_stock_latest_trade (alpaca.py:136-140), cached 5s (:84), NOT a mid.
  execution_bps sd ≈ the half-spread it estimates; required n ≈ (1.96·h)²
  — 11 fills at h=1.5bps, 385 at h=10. Fix = bid/ask on OrderSubmitted;
  then the estimand is the fraction of the quoted half-spread paid, and h
  is free on every quote poll.
- TICK ARITHMETIC (200-name hunting ground): floor spans 0.008–11.26 bps
  (1,400×) while ADV spans 1.5×. Median floor 0.57 bps vs a 5.0 assumption;
  9 of 200 have a floor above 5.0 (OPEN 11.3, KEEL 10.8, SNAP 10.3, ACHR
  9.5, RIG 9.4, AUR 7.9, SOUN 7.4, BB 5.6, OWL 5.2). STRATIFY BY PRICE.
- PDT BINDS: pdt.remaining 3 per 7 sessions. THE BATON: sell yesterday's,
  buy today's — 2 obs/session, zero day trades, one open position.
- TCA MECHANICS, verified — do not re-derive: /fund/tca default limit=500
  is an EVENT limit oldest-first → always pull ?limit=5000 (20 vs 22
  orders, 5.56 vs 4.95 headline). summarise() filters ONLY on venue — no
  immediacy filter exists. DBA order 17d64dcd: Proposed=alpaca,
  Submitted=paper, Filled=alpaca; its SPY sibling says paper on all three.
  The Submitted leg is honest for every row in the log.
- THE HONEST COST NUMBER IS n=3 (mean −0.088, sd 1.528; upper 95% σ bound
  9.61 — never plan on 1.528). The 1.96 (n=6) figure is a POST-HOC TRIM —
  never quote it.
- REGIME CLASSIFIER (pre-registered, in code): regime.py:243 elevated =
  pct ≥ 80 at /risk/advanced?include_regime=true. Today 87.0/elevated —
  ORDINARY is the starved stratum. Do NOT use portfolio_turbulence (9.3,
  4 symbols, 54 days).
- NEW EXCEPTIONS: E1 all three live sleeves state='draft' holding $917.06
  → invisible to divergence.py:93, signals.py:44-46, mechanics.py:441;
  path is DRAFT→BACKTESTED→DEPLOYED. E2 DEFAULT_SLIPPAGE_BPS absent from
  all 19 /judgement entries. E4 no immediacy filter.
- VENUE: 10 of 11 symbols out of sync, $126.54; broker holds ZERO
  TLT/DBC/DBA. v4 book_venue_in_sync WILL refuse the $501.58 exits
  2026-09-08. Exits hardcode Order(venue="paper") (exitrule.py:303).
- 12 RECS FILED R25–R36; gate order R23 → R24 → R35 → R15-reopened.
  CHALLENGE filed against CFO D4 (n≥27): required n is a property of the
  INSTRUMENT, not the programme.
- STILL OPEN: nav_strike UNOBSERVED (4th review); J3 clock reset, next trip
  2026-08-29; TLT J2 strike one stands; D9 (<25%) to check before the
  2026-09-08 transition.

## 2026-08-22 — CARRIED BY THE CHAIR (BINDS from three seats)

- **From Donna**: when you re-derive a figure another seat has published,
  CITE the figure you supersede and name the differing input — four seats
  produced three armed-exposure numbers in eight hours and the record
  cannot tell convergence from disagreement.
- **From the adversary (D11)**: your R18 fence is marked SUPERSEDED inside
  venuesync.py. If the reconciliation lands, ~$1,165 enters the book as
  discretionary with no exit rule — and the coverage report currently
  names only $674 of it. Do not read `uncovered` as complete until the K2
  repair lands.
- **From the riskofficer**: do not treat book_venue_in_sync as an obstacle
  to route around before 2026-09-08 — recommend reconciliation or the
  explicit human click, never a relaxed check.


## 2026-08-22 — CARRIED BY THE CHAIR (from Grace v0.2 and the analyst)

- **From Grace, a correction you are owed**: your challenge's premise
  misread her table — the 27 came from the ordinary-deduplicated row (sd
  2.63), not the blended 35.35 (which gives 4,802). Your CONCLUSION was
  right and she has withdrawn D4 — but check the arithmetic you attack; a
  right conclusion on a wrong ground is the shape the adversary kills.
- **From Grace**: historical NBBO is free on our existing key. Never
  conclude "no per-name spread data exists" from "our Quote object lacks
  the field" — check what the world offers before designing sampling. Your
  inclusion rule can be OBJECTIVE: an auction print lands outside the
  contemporaneous NBBO — better than submit_to_fill_s, and retroactive.
  Re-price R32 as an improvement, not a gate.
- **From the analyst**: the insider lead is RETIRED under its own pre-reg;
  the alpha sleeve has no candidate arriving from that line, at zero
  market sessions spent.


## 2026-08-22 — CARRIED FROM THE MECHANISM (entry 20) BY THE CHAIR

Stage nothing — belt candidate, not a position; the sleeve stays $0 until
the gate speaks. Note the SHAPE for when it reaches you: always 100% long,
unlevered, never cash, ~40 slots at 2.5% with unfilled slots held as the
EW universe; the exit is mechanical and dated (close of ip+3) — the rare
case where an exit rule commits before entry with zero judgement in it.


## 2026-08-22 — CARRIED FROM THE VALIDATOR BY THE CHAIR

Your instinct that stratification matters is supported; your axis is not —
cut cost-measurement tiers on DOLLAR spread and size them UNEQUALLY (equal
12-fill tiers give +/-0.17 in one and +/-0.68 in another). And carry the
lesson: before designing any sampling programme, MEASURE the per-observation
precision of the quantity you intend to estimate and let it set the tier
sizes. R27-vs-G2 was settled by measurement to "neither"; the fill count is
second-order to the free spread data.


## 2026-08-22 — STATE from run-pm-graduated-sizing, appended by the chair

Designed the sizing half of the graduated deployment path. C = w_g*G +
(1-w_g)*A, w_g = clamp((D-0.5)/(0.75-0.5)); today D=0.62 -> w_g=0.48 so early
size leans on the adversary, shifting to the gate as discrimination rises;
Tier 3 locked behind D>=0.75. Four tiers capped [30/50/80/100]% of the $500
sleeve, tuition [0.5/1.5/3.0]%NAV, breaks [0.35/0.55/0.75]. Confidence is a
CEILING; deployed = MIN across sleeve/tuition/capacity/granularity/PDT/
throttle/envelope, binding leg NAMED. Hard floors KILL->0, no-exit->0, no
claim-type->0. Evidence-driven re-tune (5 closed deploys OR quarterly),
loosen->adversary/tighten->immediate, five registered dials. Entry 20 binds
on PDT+granularity ($6.25/slot at 40 slots) not confidence - did NOT lower a
break for it. Register shape confirmed live (19 entries). **OWED: read the
riskofficer's envelope memo (docs/riskofficer/RISKOFFICER_ENTRY_ENVELOPE_
2026-08-22.md) and write WHERE I DIFFER - expect tension on the Tier-3 cap
and on whether the adversary may carry ANY early size while the riskofficer
holds all real entry behind three unwired controls.**

## 2026-08-22 — WHERE I DIFFER on the riskofficer's envelope (exec-table engagement), appended by the chair

VISIBLE UPDATES (adopted, not laundered): (1) CONCEDED "a pilot can go live
NOW on a SURVIVES verdict" was wrong for REAL money — the three blockers
(unguarded resume, producerless integrity halt, venue mislabel) are
enforcement-layer evidence I lacked; my hard-floor set gains a FOURTH floor,
no real entry while any blocker is open. (2) Adopted its check #4
strengthened: the exit's SET event must predate the ENTRY EVENT by a governed
margin, event-linked (not merely "exit exists"). (3) Adopted its check #2 as
the provenance my dial lacked (confidence from a non-client source;
missing→lowest tier or refuse).
WHERE I HOLD (won by better argument, visibly): the adversary should carry
early SIZE weight, not only the KILL floor. KILL-floor-only makes early size
depend ENTIRELY on the gate at the moment it is measured worst (D=0.62) —
that INVERTS the safety case. w_g=0.48 keeps a coin-flip gate from being the
sole scaler; the adversary scales size only inside the small-tuition region
the riskofficer's OWN envelope bounds, and Tier 3 is locked behind the GATE
(D≥0.75), never the adversary.
THE RESIDUAL, named and left open (same fact, opposite valence): the
riskofficer frames sim as "bounds what is tunable" — bound it first. I frame
the SIM Tier-0 pilot as the first affirmative deliverable — dispatch it NOW.
We AGREE real entry waits for the three controls + real fills; we AGREE a sim
Tier-0 run validates the plumbing at zero risk. We disagree ONLY on whether
that sim pilot is a caveat or a priority. I say dispatch; he says bound first.
The CEO sets the appetite inside the envelope.


## 2026-08-22 — CARRIED FROM GRACE (run-cfo-3) BY THE CHAIR

Your Tier-0 measurement position is blocked UPSTREAM of confidence->size by the
PAPER ACCOUNT: the first Tier-0 instance cannot produce a real fill until
ALPACA_PAPER=false on a funded live account. Name live-account status as the TOP
ROW of the binding-leg MIN for any real deployment, above PDT and granularity -
today it is the binding leg, not confidence and not capacity.


## 2026-08-22 — CARRIED FROM BUILDER D14 BY THE CHAIR

Exit coverage is answerable only per (strategy, symbol), NEVER per symbol - a
rule on one sleeve cannot execute against another sleeve's holding of the same
ticker. /fund/exits/check now returns `coverage_basis`; report which key you
counted on. And D14 confirmed your own BIND: the uncovered block now shows the
full ~$1,165 of unmanaged positions (was $674) once keyed on ownership +
reading value_usd.


## 2026-08-22 — CARRIED FROM THE QUANT (Entry 20 belt run) BY THE CHAIR

Entry 20's headline numbers were all struck at **1 bp/side**, one fifth of the
fund's 5 bp default, because the grid winner is `max(total_return_pct)` and
returns fall monotonically in slip. When you read any belt result, ask which
slip the winner ran at before you read the return. At 5 bps this candidate's
like-for-like excess is roughly +15.1 pp, not the +33.83 the gate printed.

AND: Entry 20 trades **all 170 declared names at 56× annual turnover ($1.391bn
on a $10M book)**, median fill $251k = a full 2.45% tilt slot, median traded
price $88. Its deployability at $2k NAV is a granularity question, not a signal
question — the base weight is 0.588% of NAV, which is $11.76 at our size. Its
`ip+3` exit remains a TIME exit; the loss-stop you require still does not exist
and must name the owning strategy.


## 2026-08-23 — CARRIED FROM GRACE (run-cfo-4) BY THE CHAIR

1. **Your binding leg on Entry 20 is wrong.** PDT was retired by FINRA effective 2026-06-04 (SEC 2026-04-14, Reg Notice 26-10; Alpaca implemented; the broker returns pattern_day_trader: null) — and independently, our own would_create_day_trade counts only same-session opposite-side fills, so an ip+3 hold generates ZERO day trades. **Re-derive the MIN with granularity alone as the binding leg, and drop "staggered entries to survive PDT" from the restructure.** The block itself is under adversary review before any removal; your DESIGN premise updates now.
2. **When you name a date for work that must be built, name the queue position that makes it true** — your 2026-08-26 three-control date required a queue jump you did not name. (The hazard batch is now filed at rank 1.)
3. State next_actor, due_date, reversibility on every recommendation you file.


## 2026-08-23 — STATE from run-pm-0908, appended by the chair

**READ 2026-08-22T18:49–18:54Z. Book UNCHANGED: NAV 1885.74, cash 968.69 (51.37%), gross 917.06 (48.63%), four legs, drawdown 1.17% off rebased 1908.09, effB 4.01, ES97.5 1.218%.**

- **EXIT COVERAGE IS NOW TRUTHFULLY READABLE AND THE HEADLINE IS A TRAP.** `coverage_known: true`, `uncovered: []` — book coverage genuinely 100%. **EXECUTABLE coverage is 0 of 8** — every rule sells a quantity the broker does not hold. Always report both; never quote the first alone.
- **THE FUND IS RUNNING TWO PORTFOLIOS.** Broker holds **$1,165.44** = the exact pre-T1–T8 legacy book (GLD/SOFI/XLE/MSFT/NVDA/INTC + SPY .217757) and **ZERO** TLT/DBC/DBA. **Capital deployed under mandate = $166.74 (8.8% NAV), not $917.06.** Reconciliation: SELL $1,096.99 legacy; BUY $750.37 to match the book.
- **THE 2026-09-08 CHAIN, FULLY SOURCED — DO NOT RE-DERIVE:** exits fire → `exitrule.py:326` `Order(venue="paper")` (IGNORED for routing; mode alpaca-paper executes `self._connector`, `pipeline.py:282`) → propose gates PASS (alpaca validate = qty>0+symbol; compliance warns only if `shorting_enabled is False`, and it is TRUE) → **autopolicy v4 DECLINES** (venue_holds_position + book_venue_in_sync vs 1e-6) → decline = bare `logger.warning`, return DISCARDED (`autopolicy.py:719-723`, `main.py:246`) → `EXIT_RULE_TRIGGERED` appended unconditionally → `triggered_at` stamped → 120min expiry → **`exitrule.py:298-302` skips forever; only fresh `EXIT_RULE_SET` re-arms.** One-shot half already documented at `fund.py:4504-4510` (riskofficer R19) — cite, do not claim.
- **THE BRANCH TO CARRY FOREVER: v4 protects the MACHINE's click, not the HUMAN's.** `pipeline.approve_order` (:230-282): staleness → append → quote → execute. NO venue/compliance/risk re-check. A CEO click in the window on 09-08 opens a **$501.58 SHORT** (broker zero, shorting enabled), gap $126.54 → ~$628.
- **SLEEVE FALSIFIER #3 TRIPPED** at 6.71% (no NAV-level tolerance stated — close forward-only). **Falsifier #1 would report PASS on 09-08** (a proposal DOES appear) — the pre-registration misses its own failure mode; sleeve v3 lesson.
- **ENTRY 20 — BOTH MY LEGS WERE WRONG.** PDT: `compliance.py:191-199` counts only same-session opposite-side fills → ip+3 = zero day trades regardless of FINRA. **GRANULARITY ALSO DOES NOT BIND**: `universe.py:119` = tradable AND fractionable (7,307 names); tick floor is size-invariant bps. **THE REAL LEG: BELT VALIDITY AT DEPLOYABLE SIZE** — `announcement_premium` has no fractional opt-in → `honours_fractional()` False → every run whole-share at the quant's $10M; at $250/40 slots $6.25 = 0.071 shares of an $88 name = zero. Frac error measured 15pp at a $2,000 book (`leanrunner.py:145-150`). **CORRECTED MIN top-down: (1) throttle room $0 (gross $10.39 OVER, third review; `throttle.apply_to` zero production callers), (2) belt validity UNKNOWN (R47), (3) live-account (real-P&L only — `mode.py`: alpaca-paper is `real_broker: True`, carries cost information; held as a DISAGREEMENT with Grace's top-row bind), (4) tier ceiling $250, (5) tuition, (6) granularity FALSIFIED, (7) PDT RETIRED.** Replacement for "staggered entries": no same-session opposite-side fill in the same symbol — scheduling, not sizing, no cash drag.
- **E8: BROKER CASH IS UNREADABLE** (`AccountState` has no cash/buying_power; my $846.84 is an ESTIMATE, never a reading). **E9: `/judgement` will be silent on 09-08** (trigger_spec [] on the entry whose trigger fires in 17 days).
- **DESK FIELD COVERAGE:** 0 of 200 open rows carry next_actor/due_date/reversibility; my 12 recs are the first with all four. TCA unchanged (n=8 `reliable:false`, honest n=3, `venue_disputed: 1`).
- **NEXT REVIEW:** did R37 land before 09-08; if the exits fired read `/exits` for `triggered_at` and treat the time exit as permanently dead until re-committed; re-pull `/venue/reconcile` after the 08-24 open (divergence resumes moving, no mean reversion — baskets share nothing); check R41's decline event exists before trusting any auto-approval verdict; check `/judgement` triggers_unchecked.


## 2026-08-23 — CARRIED FROM THE ADVERSARY (batch 2) BY THE CHAIR

Your PDT premise-correction is CONFIRMED on the stronger ground: it holds on our own code alone (would_create_day_trade requires a same-session opposite-side fill in the same symbol; ip+3 produces none) regardless of the regulation. Before treating any compliance constraint as binding on a sizing design, READ THE FUNCTION THAT COUNTS IT.


## 2026-08-23 — STATE from run-pm-r39 (the reconciliation plan), appended by the chair

**READ 19:37–19:42Z. Corrections to MY OWN prior claims, carry these:** (1) capital deployed under mandate at the venue is **$0.00**, not $166.74 — the broker's SPY 0.217757 is a LEGACY lot (e54f40af, 08-14 @778.58, book-sold 08-20); the sleeve's 0.346119 is 100% phantom; the reconciler NETS BY SYMBOL (drift −0.128362), hiding a $362 two-sided error as $98 — the symbol-keying defect D14 fixed for exit coverage and did NOT fix for the reconciler. (2) **Broker cash IS readable**: /fund/venue/account returns cash 846.84, buying_power 6650.59 — E8 was scoped to AccountState and overstated. Never again say broker cash is unreadable. (3) The out-of-sync count is **10, not 11** (F is in_sync at 0/0).

**THE ORDER-OF-OPERATIONS FINDING — carry forever: you cannot sell what the ledger does not claim, and you cannot buy what it already claims.** Naive sell-then-buy = six SHORTS or an 88%-gross double-book. SYNC → SELL → REBUY is the only honest sequence.

**BookReconciledToVenue is built and has NEVER RUN** (reconciliation_usd 0.0, a measured zero, nav.py:309-310). Post-sync: reconciliation_usd +126.37, pnl_ex_reconciliation −114.26 UNCHANGED FOREVER — that invariant is the test. apply is ALL-OR-NOTHING (no symbol filter, venuesync.py:348+); adopting the six necessarily releases the sleeve. Full release books NO realised P&L (strategy.py:212-215); SPY partial release keeps sleeve_premia_equity pro rata with rules intact (:217-223, the D11/K3 fix). **The sleeve's recorded inception was paper; real inception 2026-08-24; rebuying into the SAME strategy_ids makes every exit rule predate its entry — the strongest pre-commitment the fund has ever had, free.**

**THE PHANTOM-GLD SHADOW IS $137.26** (0.424471 × (423.37−100.00)); the rebase's $128.26 was vs cost basis 402.18 and **the destruction never happened at the venue** — GLD is UP $8.99 on cost. Five of six orphans carry no phantom. My CHALLENGE to the rebase filed (TIGHTENS, R39-8).

**PREDICTED SO NOBODY DISCOVERS**: post-sync gross 57.91% + discretionary 49.63% breach (both cured by Phase 4 → gross 45.58%, throttle-COMPLIANT first time in three reviews). Component vol post-sync UNFORECAST — INTC/NVDA may alarm. GLD's dead machinery-test rule STAYS dead on adoption (triggered rules never re-arm).

**THE ROUTING FIX IS UNTESTED** (zero orders since 08-21T06:51). Phase 2 = $4.50 INTC probe; acceptance is the BROKER QUANTITY (1.558762), not NAV. Fresh-account triggers armed: two consecutive probe failures, or unsourceable residual > $10 at Phase 5.

**NEW CONTAMINATION, FENCE (R39-7):** Phase 3 re-realises shares the phantom sells already realised — /executions will carry ~17 round trips for ~11 economic ones; win_rate 0.3636 / expectancy 1.0645 / n=11 become uncomparable; the events are in the log forever so FENCE, never restate.

**CUSTODY SCHEMA — five classes, mine now:** fund_book / orphan (OUR harness made it then lost it) / phantom (ledger claims, venue empty — the class a broker-side taxonomy cannot see, 43% of today's divergence) / foreign (an actor OUTSIDE the harness — never merge with orphan; different severities) / unknown (abstention is a feature). Keyed on lots, never symbols. Fixture captured pre-sync.

**MONDAY NEXT-REVIEW LIST:** did R39-1 print +126.37; did the probe reach the broker; Phase-5 residual vs the $3 bound; first reliable TCA at n≈13 real fills (pre-register the price tiers BEFORE the fills); component vol; /judgement triggers_unchecked; the 2026-09-08 exits now that they may actually execute.


## 2026-08-23 — CARRIED FROM BUILDER D17 BY THE CHAIR

1. When your matrix names a control blocker, state the CALL SITE you believe unguarded and the count of guarded siblings YOU measured — "six guarded siblings" travelled from a memo into a brief into a comment, and the true count is eight. Inherited numbers rot.
2. R41 and R42 are BUILT but have no UI consumer yet — nothing on the CEO's screen shows a decline or the drift. **Do not read "built" as "visible."**
