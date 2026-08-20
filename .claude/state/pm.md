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
