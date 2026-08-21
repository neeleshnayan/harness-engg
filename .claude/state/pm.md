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
