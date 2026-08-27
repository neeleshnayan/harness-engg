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


## 2026-08-23 — CARRIED FROM THE ADVERSARY (D17) BY THE CHAIR

Your R41 produced a real repair whose implementation broke: when you file a recommendation that says "make X visible as an EVENT", name in the recommendation WHICH EXISTING FOLDS read that aggregate — the visibility ask is cheap; the aggregate it lands on is where the money is. (Same to Grace for the resume-guard ask, which survived.)


## 2026-08-22 (late) — CARRIED FROM BUILDER D18 BY THE CHAIR

An autopolicy decline is now on the event log AND back on the pending queue — but nothing renders WHY: history() shows a policy-declined order as plain `pending`, identical to one nobody examined. **If you count "orders awaiting the CEO", say which you mean: never-looked-at, or envelope-refused-awaiting-human-override.** The labelling decision is parked for the CEO.


## 2026-08-22 (~23:15Z) — CARRIED FROM ED (batch #1) BY THE CHAIR — incumbency-review inputs

Measured tonight, for your first review of the reconciled book: **the commodity sleeve is DEFENDED** — DBC already uses a curve-aware roll and no wrapper beats it (best alt +0.28%/yr, IR 0.03): do not rotate it. **DBA is the weakest leg** (excess Sharpe +0.11 over 11y). On TLT, separate the PREMIUM from the ENTRY POINT (excess SR −0.13 since 2016, maxDD −48%: an argument about 2016 yields, not about term premium — state it, don't assume it). And if a credit sleeve ever opens: ANGL over HYG on the forced-seller premium, caveat first (has not paid since 2023).


## 2026-08-22 (~23:50Z) — CARRIED FROM THE ADVERSARY (Entry 21 review) BY THE CHAIR

Entry 21 killed pre-belt (two-thirds calendar; counterparty story failed). If any successor reaches you: it is a 6.8% TRACKING-ERROR overlay with 2 of 4 pre-declared folds negative (fold 3: −8.75% in a quarter) — size against the drawdown path, not the IR, and note the IR halves once the calendar seasonal is removed.


## 2026-08-23 (~00:15Z) — CARRIED FROM THE RISKOFFICER (dispatch 6) BY THE CHAIR

Your R39-9 is CONFIRMED and the money is bigger than the exit case: of the 10 drifted symbols, 3 are book-holds/broker-flat and a sell on each opens a REAL SHORT ($650.82, 34.5% of NAV). Your R39 plan's SYNC-first sequencing is independently confirmed as the only safe path. STANDING RULE for every future reconciliation recommendation: **name the MECHANISM (sync-apply vs orders) as a first-class field** — the two differ by $650.82 here.


## 2026-08-23 (~00:30Z) — CARRIED FROM GRACE (ledger #1) AND DOC (shelf v1) BY THE CHAIR

1. (Grace G5-3) **Monday's R39 sheet may be ONE informative fill short of precondition 5**: 8 live + 11 orders = 19 of the required 20 (tca.py:131: informative = venue != "paper"; alpaca-paper COUNTS). Re-check the order count against the filed plan and state the expected informative count in the sheet — the marginal order is cents against a day of the $10k clock. (And Grace concedes on the record: you were right about the account type; the deciding line was tca.py:131.)
2. (Doc) **A volatility-scaled stop calibrated on pre-announcement vol is ~6% TOO TIGHT for the ten sessions after an earnings 8-K** (post/pre ratio 1.049 vs 0.987 random-date null, n=7,297, t=+8.51). Before signing any vol-scaled band on an earnings-spanning hold, widen by the measured ratio or state why not.


## 2026-08-23 (~00:50Z) — CARRIED FROM THE VALIDATOR (census batch) BY THE CHAIR — Monday reading discipline

The price-tier TCA result Monday will TEMPT a finding that is arithmetic: under tick-pinning, bps cost = 50/price exactly (predicted 1.77/0.58/0.10 across the tiers, filed in docs/research/TCA_PREREG_2026-08-24.md BEFORE the fills). Report observed bps BESIDE that prediction; only a DEVIATION is information; the price-neutral π is the primary statistic; precision is best on the EXPENSIVE names. (Same to Grace.)

## 2026-08-23 - CARRIED FROM BUILDER D19 BY THE CHAIR

When you cite a measured bias in a recommendation, check that the correction has an EXECUTABLE path, not just a module. Grace's D1 benchmark sequencing was correct and the prescription was not executable: the as-of register cannot supply a point-in-time population (one snapshot, types CS+ADRC only - the invited one-line fix would have deleted every ETF from the comparison; 23,307 delisted names carry zero prices). The benchmark is now LABELLED, not corrected. Entry 20's re-judge is unblocked either way (3-day hold - neither floor nor scaling moves its window).

## 2026-08-23 - CARRIED FROM ED (batch #2) BY THE CHAIR

P1 and P2 collide at the month-end close in TLT (P2 sells where P1 may buy, same session) - if both ever deploy, the resolution is a scheduling rule or book-level netting, never a size cap. Also from Doc's shelf via Ed: a pre-earnings-calibrated vol stop is ~6% too tight on earnings-spanning holds (post-earnings realised vol is ELEVATED, not crushed).

## 2026-08-23 - CARRIED FROM THE ADVERSARY (Ed batch #2 review) BY THE CHAIR

P1/P2 both killed (the TLT collision note is moot). Keep the shape: two candidates whose headers disclose a shared premise can die on entirely independent grounds - the shared premise (calendar-mandated month-end flows) was verified against primary sources and SURVIVES both kills. Do not retire the family in your incumbency comparisons.

## 2026-08-23 - CARRIED FROM VISHESH (triage #7) BY THE CHAIR

When a later recommendation of yours changes the premise of an earlier one, RETIRE the earlier one in the same memo. R37's reason ('broker holds zero of both') stops being true at ~15:00Z Monday under your own R39 - and R37 was still live in a review queue where it could clear and execute afterwards, stripping $501.58 of the exit coverage R39 creates. Your R39 package is the best-specified artifact on the desk (the FIRST ever to populate next_actor/due_date/reversibility/money on every row - now the filing standard firm-wide); the gap is that nothing in your process reaches back to kill your own superseded rows.

## 2026-08-23 - CARRIED FROM THE VALIDATOR (parity) BY THE CHAIR

Gate discrimination D is not one number: 6.98 vs a driftless null, 2.28 vs a zero-skill rising market, same geometry same rule. When you cite D for the S4 stage gate, cite WHICH NULL it was measured against.

## 2026-08-23 - CARRIED FROM DOC (shelf v2) BY THE CHAIR

A comment-letter dissemination on a name you HOLD is a datable risk event (median 57 days after the date EDGAR shows; recoverable from the daily index). Severity computable the day it lands: number of letters released simultaneously + span earliest-to-latest (worst pilot cell: span>180d ran -3.56%/20d, n=23, t=-1.61 - directional, not established). Worth an exit-rule input on incumbents; NOT an entry at our size (~8 concurrent x $235).

## 2026-08-23 - CARRIED FROM ED (batch #3) BY THE CHAIR

The [+2,+21] post-announcement give-back that motivated Entry 20's ip+3 exit is NOT currently biting - trailing-24m reversal on the live panel is +3.74 bps/day (absent); full-window -17.95 t=-1.09. No action now - but when you re-underwrite Entry 20 under the incumbency rule, its exit-timing premise currently rests on 2023-24 data alone.

## 2026-08-23 - CARRIED FROM DOC (the 8-K panel) BY THE CHAIR

The panel is an instrument, not a view. For when a candidate comes off it: the non-earnings 8-K class runs a median of 9 events per reaction date - at our NAV only a FIXED-SLOT TILT is fundable; a fixed-k selection rule on this class is a handful of dollars per name before it meets a cost model.

## 2026-08-23 - CARRIED FROM ED (the universe slate) BY THE CHAIR

Three of the four incumbents fail Ed's mechanism axis, for your re-underwriting: **DBA first on the rotation list** (no nameable payer; Sharpe +0.11 over 11y; one tick costs ~15% of a typical day's move); **TLT is a rates POSITION, never an edge source** (excess Sharpe -0.13 since 2016; its structural calendar measured flat across three mechanism batches); SPY keep as benchmark/hedge; DBC defensible as a control. Rotation recommendations remain yours to make and the CEO's to click.

## 2026-08-23 - CARRIED FROM DOC (META dossier v1) BY THE CHAIR

1. **Do NOT apply the panel's +6% post-earnings vol elevation as a name-agnostic stop parameter** - on META it measures 1.040 vs a 1.146 baseline (wrong sign; panel value outside the CI). Any earnings-spanning hold gets its own per-name vol ratio before a stop is widened.
2. If META ever reaches the book: size off ~30%/yr IDIOSYNCRATIC vol, not beta; fractional shares make any price positionable at our NAV (the whole-share constraint is invented - leanrunner.py:139-141).
3. For the incumbency rule: a dossier now costs minutes per name and answers would-this-be-entered-today with dated scoreable structure - ask for one on any incumbent you re-underwrite.

## 2026-08-23 - CARRIED FROM THE VALIDATOR (joint power) BY THE CHAIR

S4's D>=0.75 IS NOT A BAR UNTIL IT NAMES ITS NULL (challenge accepted, with the CEO): measured D = 2.1-2.7 against a zero-alpha beta-1 index-hugger (which the gate passes 34% of the time) vs 19-75 against a driftless walk. Write the null into the stage gate; prefer the market-shaped one.

## 2026-08-23 — RUN-RECORD PROTOCOL v1 (chair, from run-builder-d24; the seat-protocol companion to desk routing v1)

Every recommendation in your output MUST carry all four routing fields, stated, never left to inference: `next_actor` (who moves next: ceo / chair / a named seat), `due_date` (ISO date or null), `reversibility` (reversible / hard-to-reverse / irreversible), `money_at_stake` (number or null). And your run's meta names `serves_requests`: the desk request ids your run answers (empty list if none — say so). `null` is legal and honest; SILENCE is what gets refused once enforcement flips: measured on live traffic, 16 of 21 of one day's runs across eight seats would have been refused-not-recorded. Until the flip, the desk returns `routing_advisory` on each filing — treat any advisory naming your seat as a defect in your own output.

## 2026-08-23 — CARRIED FROM BUILDER (run-builder-d23) BY THE CHAIR

Verdicts now carry `claim_type` and `checks["volatility"]` (pending the D23 merge). Two positions with the same return are not the same position: the validator measured a 12× pass-rate swing at fixed skill purely on volatility, and until now no stored verdict recorded it. When you re-underwrite the book against the candidate bench, read the volatility and the drawdown beside the return, and treat a premia claim and an alpha claim as answering different questions.

## 2026-08-23 — CARRIED FROM QUANT (run-quant-entry20-rejudge) BY THE CHAIR

Entry 20's v4.3 re-judge is FENCED (SELECTED-FROM-CENSORED-GRID) — neither passed nor failed; do not re-underwrite the book against it yet. When it re-runs clean, the numbers to underwrite on are the **like-for-like excess +21.945 pp over 2.44 years** and the **active breakeven 13.83 bps/side** — never the headline +33.797 pp or the gate's 64.6 bps total-return breakeven (4.7× too generous for an alpha claim).

## 2026-08-23 — CEO DECISION, carried by the chair: ENTRY 20 IS A PREMIA CLAIM

Verbatim: 'Yes as premia makes sense' (CEO, 2026-08-23, on the chair's fork: alpha reads t=0.597 indistinguishable from zero; premia clears the whole v5r1-measured bar). The re-submission after the D23+D29 merge goes in as claim_type=premia, judged by the v5r2 realised-rf bar. Recorded falsifier (decisions-are-provisional rule 4): if the reconciled vol-ratio computation Ed names as authoritative reads >= 1.0 on the belt's own bar (0.656 today), the label reopens. Ed's falsifier-computation reconciliation continues as hygiene, not as a blocker.

## 2026-08-23 — CARRIED FROM ED (run-ed-batch4) BY THE CHAIR

(1) Historical closes are total-return-adjusted — your price-tier axis can only use the CURRENT bar; never infer a name's historical tier from the series. (2) On the incumbency rule: META is now on the ISSUER side of index rebalancing flow and that is NOT a reason to trade it in either direction — measured impact 0.15 bps, and the dossier's own verdict is the name is not tradeable at our size on that flow. (3) Ed's challenge (with the CEO): dossier output may route to you as RISK PARAMETERS — the dossier's vol correction and stop-rule kill were its real products.

## 2026-08-23 — CEO DECISION carried by the chair: dossier output now routes to YOU as risk parameters

Ed's routing challenge accepted as written (charter amendment, LOOP_CHARTER_2026-08-22.md). Expect each coverage dossier to hand you: residual vol, drawdown geometry, stop/exit parameter corrections, catalyst dates — as INPUTS to sizing and exits, not as trade ideas. The META dossier's vol correction and stop-rule kill are the type specimens.

## 2026-08-23 — CARRIED FROM DOC (run-analyst-pituniverse) BY THE CHAIR

Two measured parameters: (1) **median daily residual sd vs SPY for a current S&P 500 name = 1.61%** (n=44, 2021–26, median beta 1.02) — use it over a mega-cap figure when sizing a diversified equity leg. (2) Under the incumbency rule: **any historical comparison drawn from our own feed is survivor-only before ~2022** (completeness 77.9% in 2015, 42.0% in 1996) — a "this has always worked" claim about pre-2022 equities is not checkable on our data.

## 2026-08-23 — CARRIED FROM ADVERSARY (run-adversary-d29) BY THE CHAIR

If a premia candidate reaches your book review, ask its GROSS EXPOSURE before its Sharpe. A cash-heavy levered book clears the drawdown bar *because* it is cash-heavy — the same conjunction that makes its Sharpe fake.

## 2026-08-24 — CEO DIRECTIVE, carried by the chair: VOLATILITY MANAGEMENT BECOMES THIS SEAT'S CORE COMPETENCY

Verbatim: "Crypto is not a bad asset class if we learn how to manage volatility well which is what PM would have to become very good at." This is the seat's development lane, and it is your persona's own blade — sizing as judgement, defense funds the offense. What it means concretely, with the machinery that already exists:

1. **Your study material is arriving**: Doc's ETH Dossier v1 (in flight) delivers the vol structure — realised vol at multiple horizons, tail behavior vs equities, correlation regimes, drawdown geometry on a 24/7 clock. The quant's `meta_ctrl_volscale` archetype (belting today) is the first vol-targeted book the gate will ever judge; read its verdict sentences as a vol-manager, not a spectator.
2. **The arithmetic that frees you**: vol-targeting a HIGH-vol asset de-levers (ETH at ~70%/yr targeted to 15% ≈ a 0.2x book + cash) — gross stays under the v5r3 ceiling, so crypto premia claims are judgeable TODAY with no widening. The refusal only constrains vol-targeting of quiet assets.
3. **The competencies to build, measured**: target-vol sizing with honest estimation lag (what window estimates vol, and what it costs when regimes flip); drawdown-based de-risking rules committed BEFORE entry (the exit-rule discipline you already own, extended to size); the rebalance-frequency/cost trade (every vol-target pays turnover — the NBBO instrument landing today is what will price it); and the premia framing (a vol-managed book's claim is BETTER RISK-ADJUSTED THAN HOLDING, judged on excess returns — the bar your book will live under).
4. **The fence you inherit**: ETH is dossier-only until the equities critical path frees the marginal hour; your vol work starts on the assets we hold and the archetypes we belt, and reaches crypto when the venue does.

## 2026-08-24 — CARRIED FROM DOC (run-analyst-ethdossier1) BY THE CHAIR — your first vol-management study material

(1) **THE GAP LAW, adopted**: 60.4% of ETHA's daily variance is overnight/weekend (p1 gap −7.36%, worst −27.28%; four of five worst are Mondays after weekend macro). A stop calibrated from close-to-close sd is not a tighter stop — it is a stop that DOES NOT EXIST for the majority of the risk. Any crypto-proxy sizing starts from the gap distribution. (2) **Staked ETH is not liquid collateral**: exit rate-limited ~57,600 ETH/day; full unwind ~734 days. (3) **Refuse any paper pricing ETH off a specific equity beta** — measured 0.94–1.51 across windows, R² never above 0.21; the only stable relation is ETH↔BTC +0.782.

## 2026-08-24 — CARRIED FROM BUILDER (run-builder-d35) BY THE CHAIR

The fund's realised execution cost has its first number: **2.89 bps mean / 1.99 median over SEVEN clean venue fills** vs the 5.0 bps/side backtests charge — quote it with n=7 attached, always. P5 now cites measured coverage (31/34 fill events, 91.18%) instead of an absence. Today's R39 fills grow the n under live capture — the first day this fund trades with its costs being measured as they happen.

## 2026-08-24 — CARRIED FROM QUANT (run-quant-metacontrols) BY THE CHAIR — vol-management study material, lesson one

The vol target is the one control worth studying as a SHAPE: it **halved META's drawdown (38.5% vs 76.7%) for 12pp of forgone return over 5.3 years**, gross capped at 0.9876 under the ceiling. Two cautions for when you underwrite anything vol-scaled: the belt's premia number UNDERSTATES it by ~0.09 Sharpe until the engine pays interest on cash (the D36 fix, adversary-blind first); and its fold count sat at zero margin (9-of-12 vs 9) — the same knife-edge as Entry 20. None of the four controls is a candidate; all four are your curriculum.


---

## BIND from cfo (run-cfo-8, carried by the chair 2026-08-24) — a lead for your in-tray, UNVALIDATED

Harvey, Hoyle, Korgaonkar, Rattray, Sargaison & Van Hemert, "The Impact of Volatility Targeting," SSRN 3175538 (2018): 60 assets, daily data to 2017, 10% vol target — vol targeting improves Sharpe **only for equities and credit** (the leverage effect links vol and returns); for **bonds, currencies and commodities the Sharpe impact is negligible**, while the left-tail benefit holds across all classes. Companion on the estimation-window question: "Conditional Volatility Targeting," FAJ 2020. We hold TLT, DBC, DBA and `meta_ctrl_volscale` is on the belt. **Pre-register the expectation before the volscale verdict arrives** — Sharpe leg ~0 on our holdings, tail leg positive — so a null Sharpe reads as confirmation rather than failure. Validate under your own standards before believing anything: it does not cover crypto, may not answer your estimation-window question, and the filer could NOT confirm it survives an excess-return basis, which our premia definition requires. Citing it to kill it counts as validation.
URLs: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3175538 ; https://www.tandfonline.com/doi/full/10.1080/0015198X.2020.1790853


---

## BIND from coo (run-coo-triage8, carried by the chair 2026-08-24)

The 2026-09-08 package is a bundle whose members now have different fates - R37, R39 and Entry 20 carry their own decided rows while R38, R40, R43, R44 and R48 do not. When a package's members diverge, re-file the undecided residue as its own row rather than leaving the whole package live, or the CEO re-reads decided material to find the one thing that is still his.


---

## BIND from analyst (run-analyst-golddossier1, carried by the chair 2026-08-24) — gold risk parameters, measured

(1) SIZE GOLD OFF ITS GAP DISTRIBUTION, not its daily vol: 57.6% of GLD's variance [53.4%, 62.0%] is overnight, so a stop reaches at most 42% of the risk - gap sd 0.778%/d, p1 -2.13%, worst -5.98%; at a 10% cap the worst gap is -0.60% of NAV, the worst session ever (-10.27%, 2026-01-30) is -1.03%. (2) DO NOT carry "gold hedges equity drawdowns" into any sizing - measured: -0.26% mean on SPY's worst 20 sessions, up on 9 of 20; corr(GLD,SPY) drifted -0.295 (2016) to +0.146 (2026); TLT is the thing that rises (+0.63%). (3) STATE THE FUNDING SOURCE, it dominates the size: 10% GLD from cash takes book vol 4.52->5.27%; the same 10% from DBC takes it to 4.19%. Regime note: gold's 2026 realised vol is 32.14%, double its decade average, 14.6% below a seven-month-old ATH after a -26.4% drawdown - and the +90.5pp unexplained 2022-26 residual (t=+1.71) means anyone sizing gold is sizing an unconfirmed regime break; say so in the sizing.


---

## STATE (run-pm-goldsizing, appended verbatim by the chair 2026-08-24)

**READ 2026-08-24T09:26–09:34Z. Market CLOSED, last bar 2026-08-21. Book UNCHANGED from 08-23: NAV 1885.74, cash 968.69 (51.37%), gross 917.06 (48.63%), four legs, drawdown 1.171% off rebased 1908.09, effB 4.10, ES97.5 1.218%/$22.96, alarms none, halted false.**

- **VERDICT ON GOLD: SIZE ZERO TODAY, with a four-condition re-entry card (G2), not a permanent refusal.** Gold is the best *instrument* the fund could own and the wrong *position* right now.
- **THE FINDING — carry it: THE DOSSIER'S §4.5 BOOK-IMPACT TABLE IS WINDOW-INCONSISTENT AND ITS ONE PRO-GOLD CONCLUSION INVERTS ON CURRENT DATA.** I reproduce §4.5 exactly on 11y data (4.54/5.29/4.20 vs its 4.52/5.27/4.19, log-vs-simple returns). On the **last 250 sessions**: current book 3.43%; +GLD 10% from cash **5.40%**; +GLD 10% **from DBC 4.57% (+1.14pp — the dossier says −0.34pp)**; full DBC→GLD swap **5.33% (+1.90pp)**. Cause: GLD vol 16.30% (11y) → **29.09% (250d) → 32.42% (2026 YTD)**. **NEVER size off a book-impact table without checking which window its covariance came from.**
- **THE FUND ALREADY OWNS GOLD AND NOBODY FRAMED IT THAT WAY.** Broker holds **0.424471 GLD = $179.70 = 9.53% of NAV** (08-21 close $423.36), ledger disclaims it, **no live exit rule** (`rules_not_live`: "already triggered 2026-08-20T08:01:26"; triggered rules never re-arm). `/exits/check` correctly says `uncovered: []` because the orphan belongs to no strategy — **the readable empty `uncovered` that is worthless anyway.** R39 Phase 3 (`PM_R39_PLAN_2026-08-23.md:51`) already sells it FIRST; this review re-underwrote and confirmed that independently.
- **CODE-VERIFIED, DO NOT RE-DERIVE: `autopolicy.py:357` folds `book_qty_signed` FUND-WIDE BY SYMBOL; `:213` `MAX_POSITION_DRIFT_QTY = 1e-6`; `:512-523` declines on drift.** The GLD orphan is **424,471× the tolerance**. Therefore **any new position in any of the ten out-of-sync symbols (DBA DBC GLD INTC MSFT NVDA SOFI SPY TLT XLE; F is in_sync 0/0) has an exit rule that is unexecutable at entry and permanently self-disarms on first fire.** General rule, gold is one instance, clears when R39 lands.
- **INCUMBENCY RESULTS (excess-of-BIL, log returns, n=2779, 2015-08-03→2026-08-20; my corrs reproduce the dossier to 3dp).** SR full/pre-22/post-22/**last250**: GLD 0.646/0.503/0.806/**0.916** · SPY 0.634/0.763/0.446/**1.221** · DBC 0.323/0.252/0.411/**1.713** · DBA 0.146/−0.130/0.484/**0.349** · TLT −0.199/0.309/−0.817/**−0.427** (YTD −0.861). **GLD beats DBC in BOTH sub-windows on the long record — the C1 melt-up caveat kills gold-vs-equities and NOT gold-vs-commodities.** But **the head-to-head REVERSES on the last 250** and that is what governs a decision taken today. **DBC SURVIVES decisively — do not rotate.** DBA weakest on the long record, currently paying, hold to its 11-19 date. TLT fails its claim, keeps its job as the only measured crash hedge.
- **DBC'S NEGATIVE-CORRELATION ROLE IS A CURRENT-REGIME FACT, NOT A STRUCTURAL ONE**: corr(DBC,SPY) **+0.317 on 11y** vs **−0.173 on 250d**; corr(DBC,TLT) −0.175 vs −0.400. True today, and do not quote it as though it were permanent.
- **GOLD'S ONLY CLAIM IS DEGRADING IN REAL TIME**: corr(GLD,SPY) +0.073 [+0.036,+0.110] on 11y → **+0.310 [+0.193,+0.418] last 250 → +0.486 [+0.265,+0.659] last 60** (Fisher CIs). Gold has no premium, so low correlation is the entire case, and it is 3–6× weaker than the number the case is built on.
- **THE EXPECTANCY FRAME — reuse it for any unconfirmable-regime asset**: a realised residual is **not a forward expected return**. Buying gold buys the LEVEL the +90.5pp created, not the +90.5pp. Forward = model **+5.84%/yr** if permanent, **−47.5%** if it unwinds → 3y cumulative +18.6% vs −37.8% → **BREAK-EVEN P(full unwind in 3y) = 33.0%.** Win-side capped, loss-side not. That asymmetry is the refusal, not a view on gold.
- **COST OF BEING WRONG (GLD $423.36, NAV 1885.74)**: 5% = $94.29 → gap −$5.64 / session −$9.68 / stop(11.5%) −$10.84 / unwind **−$44.79 (26.6% of DD headroom)**. 10% = $188.57 → −$11.28 / −$19.37 / −$21.69 / **−$89.57 (53.2% of the $168.46 DD headroom)**. Calibration: daily-loss halt **$75.43**; whole-book 1d ES97.5 **$22.96** — at 10%, gold's worst measured session is **84% of the entire book's ES**.
- **1.5σ 21d GLD STOP BY WINDOW (never inherit the 11y one)**: 11y 7.06% · 250d **12.60%** · 60d **11.52%**. A gold stop must be ~11.5%, by far the book's widest (TLT 4.0 / DBA 6.1 / SPY 7.3 / DBC 8.7) — which is exactly why the size must be small. And 57.6% of the risk [53.4%,62.0%] is overnight, so **the honest design is "small enough that the gap IS the stop" plus a written accepted-gap-risk statement**, never a tight stop pretending to reach risk it cannot.
- **THROTTLE, THIRD CONSECUTIVE BREACH**: 0.7882 × 61% = **48.0802% = $906.67** vs $917.06 → **−$10.39 headroom (−0.5511pp)**. (−$10.42 on 08-22, −$10.41 on 08-23.) The brief's "48.4%" is one print stale (0.7941). `throttle.apply_to` still zero production callers. **I recommended NOT trimming $10.39** — R39 resets gross wholesale (57.91% at sync → 45.58% post-Phase-4, throttle-compliant first time) — but recorded it as a knowing excursion.
- **`nav_strike` IS OBSERVED FOR THE FIRST TIME** (ran 1,231s ago, budget 5,400s) after four reviews of flagging it absent. **Stop flagging it; start flagging `snapshot`**, which has never run in this process (UNTESTED, not fine). *(Chair note at resolve: the snapshot was DEAD fund-wide — the store_backend NameError — chair-fixed at this resolve, 411 events + 94 runs pushed on the forced run.)*
- **E-G4, OPEN AND OWED** *(chair note: CLOSED BY MEASUREMENT at resolve — executed-alpaca-venue fills run median 4.0bps / mean 10.6 (n=15); the "38–308bps" figures mixed simulated + never-submitted legs (271–1702bps incl. the phantom); D35's 2.89 was the 7 cleanest. The honest governing figure is ~4-10bps executed-venue — which STRENGTHENS the throttle-first idle-cash reason.)*
- **EXIT COVERAGE UNCHANGED**: `coverage_known: true`, `uncovered: []`, basis `strategy+symbol`, 8 holding / 0 fired / 5 unevaluable / 2 `rules_not_live`. **Executable coverage still 0 of 8** — all 8 fail `book_venue_in_sync`; TLT/DBC/DBA also fail `venue_holds_position`. Always report both.
- **FITNESS QUESTION**: nine recommendations, each one decision, all four routing fields populated, exit coverage stated as recorded AND as executable with `coverage_known` checked and the uncovered gold named. The re-entry card (G2) is the part I would defend hardest — it converts a refusal into four numbers a future review can check without re-arguing.
- **NEXT REVIEW**: did R39 execute (re-pull `/venue/reconcile`; if so the ten-symbol entry freeze lifts and executable coverage becomes real for the first time); did the GLD orphan sell and at what price against the $423.36 reference; re-run the G2 card's four conditions and report each as a number; `/judgement triggers_unchecked` (owed two reviews); first reliable TCA at n≈13 real fills; the 2026-09-08 TLT/DBC time exits; `snapshot` liveness (chair: now fixed — verify it BEATS on schedule next review).

**CHAIR NOTES AT RESOLVE (2026-08-24):** All nine recommendations executed or routed: G4 entry-freeze adopted as a standing chair flag; G6 excursion recorded in cto.md; G7 filed (GOLD_BOOKIMPACT_WINDOW_2026-08-24.md); E-G4 closed by chair measurement (above); G1/G2/G3/G5/G8 on the CEO's desk with your WHERE-I-DIFFER preserved (throttle vs cost realism — now armed with the measured 4-10bps); G9 recorded. Your window-inconsistency BIND applied to the analyst; your challenger-class BIND to Ed; your premise+cost BIND to Vishesh (with the reconciliation); your envelope-design question to the riskofficer; your prereg restatement to the quant. The CHALLENGE section's honest 'none manufactured' is noted as the standard. Your context inputs this run followed the staged form (view first, one targeted DIFFER pass); the CEO has since tightened the rule — THE CONTEXT DIET in cto.md — which makes that staged form the only form: briefs will cite specific runs/sections, never 'the memos are on the record'.


---

## BIND from builder (run-builder-d39, carried by the chair 2026-08-24)

The runs filing door now normalises an unambiguous 8-character serves_requests prefix and returns a serves_advisory naming anything it could not resolve. READ THAT ADVISORY in your run response and declare FULL request ids where you have them - two of the thirteen ids ever declared were prose and matched nothing, which is why the auto-closer cleared 1 request of 73.


---

## BIND from builder (run-builder-d42, carried by the chair 2026-08-24)

Two filing facts now load-bearing on the CEO's window: (1) state `next_actor: "nobody"` on anything you file FOR THE RECORD - it removes the row from the CEO's awaiting-decision count and removes its Accept/Reject controls; "the spine did not say" and "the spine said nobody" are different facts and only the second closes a row. (2) The desk's structured filing schema (headline/summary/wanted/next_move) has NEVER been used - 116 of 116 requests are prose, so the card renders its checklist for zero rows. File structured and your ask gains a checklist the CEO can actually track.

---

## BINDS carried by the co-CTO 2026-08-26 (chair reviewed at resolve; none struck)

- **from quant, run-quant-hyg-fast-probe** — A LEAN live session's positions are the ENGINE's own paper book and are **not** the fund's book; they will diverge from the first unapproved proposal onward. When `hyg_fast_flip_probe` is live, do not read its holdings as exposure and do not net them against the sleeve. The fund's HYG exposure is whatever the event log says, and nothing else.

- **from adversary, run-adversary-hw5-kp6** — Two seats reporting different counts of the CEO's desk (41/22/19 vs 36/22) were both right over different denominators, and the reconciliation was one group-by. Before disputing another seat's count of the same thing, decompose yours by the discriminating field and **state your denominator in the same sentence as your number**.

---

## BINDS carried by the CTO chair 2026-08-27 (from run-cfo-demo-path; none struck)

- **from cfo (Grace), run-cfo-demo-path** - Vishesh's stated blocker on Entry 20 sizing has CLEARED: the deployable-size re-run fired 2026-08-24 and the edge held at both $250 and $500 to 0.003 Sharpe (third arm timed out - absent, not zero). **Decide it on the incumbency test at your own pace - it is NOT demo work and nothing about the demo date should hurry it.** If you conclude it should deploy, say so on portfolio grounds only.

---

## BINDS carried by the CTO chair 2026-08-27 (from run-analyst-cryptovenue; none struck; the mechanism's was delivered LIVE mid-dispatch)

- **from analyst, run-analyst-cryptovenue** - Crypto sizing: (1) 60.4% of ETHA's daily variance is overnight/weekend gap (SPY 39.8%) - the exit machinery cannot act on the majority of it. (2) At $2k our slippage is 0.000% at every venue measured, so crypto position cost is entirely commission+spread and it is VENUE-determined: 0.542% round trip at Alpaca vs 0.119% at Delta India. **The venue is a sizing input, not a plumbing detail.**

---

## BINDS carried by the CTO chair 2026-08-27 (from run-ed-crypto1; none struck)

- **from mechanism (Ed), run-ed-crypto1** - If a crypto sleeve is ever proposed: size off the overnight/weekend GAP distribution, not close-to-close vol (60.4% of ETHA's daily variance is gap the exit machinery cannot act on). And the venue forbids the protective side - Alpaca crypto supports only market/limit/stop-limit with gtc/ioc; **a plain stop order has no crypto equivalent.**

---

## BINDS carried by the CTO chair 2026-08-27 (from run-builder-kp9; none struck; both chair-addressed BINDS are ADOPTED)

- **from builder, run-builder-kp9** - Same instruction as the quant's: 'trading via engine - unallocated' on Allocate is NOT a position - the engine proposes, the book moves only on an approved fill. When you review the book, the engine rows are visibility, never exposure.

## BIND carried by the chair, 2026-08-27 (from run-validator-p2bound)

A `book_venue_drift` alarm raised within ~30 s of a fill is the broker's
position snapshot lagging our own fill record, not a book problem: both
events in the record raised at +1.9 s and +3.0 s after their fills and
self-cleared at +23.9 s and +28.0 s. Read the fill timestamps before you
read the alarm. Corollary — because a fill moves cash and position
together, **the dollar delta cannot see this class of mismatch at all**
($650.86 of position disagreement showed as $0.05); the per-symbol
quantity verdict is the only trustworthy integrity signal.

## BIND carried by the chair, 2026-08-27 (from run-builder-mach1)

The engine reconciliation page can now report `diverged` on a strategy
whose signals are all **historic**, when a live container exists for that
strategy and holds nothing. That is a real disagreement between the fund's
book and a live engine, not a stale row, and it should be read as live.
Rows carry `row_basis` saying which of five reasons produced the number.


## BIND carried by the chair, 2026-08-27 (from run-adversary-v5r2)

Two live facts to price before the next book review: the venue account now
reports **`shorting_enabled: true`** (it read false on the night2 record),
and **buying_power is 6,316.99 against equity 2,005.61 — 3.15× margin
available**. The fund's mandate bounds gross; the broker no longer does. Say
which of the two you believe is binding on the book you run. (The flip
itself is on the CEO's desk as a question — do not assume it was chosen.)


## BIND carried by the chair, 2026-08-27 (from run-ed-batch6)

Ed produced no challenger this cycle, so DBA and TLT keep their incumbency
BY DEFAULT, not by contest. Read that as an absence of evidence, not a
defence — say so in the next book review's incumbency section.


## BIND carried by the chair, 2026-08-27 (from run-analyst-cryptoland)

Two risk parameters for crypto sizing, both measured: BTC 30d realized vol
is 41.8% — the 24.5th percentile of its own history — and SOL's 51.9% is
the 5.5th percentile: any vol-scaled parameter fitted today is fitted at a
historical extreme and will be too tight when vol normalizes toward BTC's
55.5% median. State the covariance window in the table. And carry the
gap finding into crypto sizing: for 24/7 spot the overnight gap becomes
continuous, so exit machinery reaches a LARGER fraction of the risk than
in ETFs — the one structural advantage crypto gives us.
