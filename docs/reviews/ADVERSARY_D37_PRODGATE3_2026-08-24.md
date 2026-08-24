# ADVERSARY — D37 RE-REVIEW + PROD-GATE PACK v3 — 2026-08-24 (run-adversary-d37-prodgate3)

Blind batch: builder-d37 (the level-revert repair, sensitive `app/fund/gate.py`)
and prod-gate precondition pack v3 (iteration 3). Filed verbatim by the chair;
STATE appended to `.claude/state/adversary.md`; BINDS carried (the validator's
supersedes its D36-era instruction); the seat's EVOLVE (whose-model clause)
applied to its probe-discipline section. **The chair re-verified the central
LEAN claim directly before acting** (raw source line 311; a stored summary's
`tradingDaysPerYear: 252`). Chair resolution at foot.

```
TL;DR

Item 1 (the gate revert): the mechanical repairs are all clean and I certify them —
the revert changes no verdict anywhere, and the premia bar is untouched. But the one
thing the change actually ships, a new explanatory sentence on 656 rejected
candidates, states a fact about the backtest engine that is wrong. The engine's
hurdle is a fixed, published constant; the sentence calls it unknown and prints a
number about 70% too high. Verdict KILL, narrowly — and the fix is free, because we
now know the real number, which unblocks a calibration we had written off as
impossible.

Item 2 (the prod-gate pack v3): the kill-switch leg would let a blocking safety
precondition flip to "satisfied" today, on four-day-old evidence consisting of a test
stub and a known data glitch, and it names two event types that do not exist in our
system. Verdict KILL on that leg. The other legs survive.
```

---

# ITEM 1 — builder-d37, the level-revert repair — **RE-REVIEW**

**Liftable verdict:** `KILL (narrow, one clause) — the revert, the premia split, the range check, the psr_pct guards and the criteria merge are all CERTIFIED by execution; the corrected engine sentence is killed because LEAN publishes its PSR target as the hard-coded constant 1.0/sqrt(tradingDaysPerYear) (PortfolioStatistics.cs:311) — an annualised Sharpe of exactly 1.00 for every candidate — while the sentence and the register draft assert it is unpublished and per-candidate at 1.17–2.26.`

## Scope proof

`git diff --name-only builder-d36..builder-d37 -- app/` → exactly two files. AST diff with signatures, decorators and module constants (`scratchpad/advd37/astdiff2.py`): `leanrunner.py` comment/docstring only; `gate.py` touches `CONST:CRITERIA`, `CONST:PREMIA_CRITERIA`, `_luck_leg`, `evaluate`, nothing removed or added. Constants: `CRITERIA` moves exactly two keys (`min_psr_pct` 50→65, `psr_basis` target_zero_module→engine_reported); `PREMIA_CRITERIA` gains exactly `premia_psr_basis`.

*Scanner defect self-caught this run:* stripping docstrings by rebuilding `ast.Module(body=...)` silently drops the **signature** — fixed in `astdiff2.py`, re-run confirmed.

## Certified by execution (the ten failed attacks)

Three-tree stored-result re-judge (`judge2.py` + `compare.py`, null-tested against a planted flip), 765 results × 2 claim types:

```
d36 -> d37 [alpha] : n=765 flips=0 changed_failure_lists=717 crashes=0
d36 -> d37 [premia]: n=765 flips=0 changed_failure_lists=0   crashes=0
pre(7fad220) -> d37 [alpha] : n=765 flips=0 crashes=0
luck-leg pass/fail flips pre -> d37 : 0 of 765 (656 fail it under both trees)
```

- The premia surface: 0 flips, 0 changed sentences; the only difference on all 765 is one additive disclosure key (`premia_psr_basis`) — the artifact's word "byte-identical" is one key too strong, self-penalisingly.
- The revert is real **per-leg**, not just per-verdict (0 luck-leg flips vs pre-v4.4; the draft was the outlier at 297).
- Zero stored artifacts stamped v4.4 anywhere (candidates, jobs, events); register `drifted: []` under d37 and populated under d36 — the D36 ground closed by execution in both directions.
- All 18 malformed `robustness.psr_pct` shapes refused without raising through the public `evaluate()`; the bool-as-1.0 hole closed.
- The range check covers both claim types, both ends, direction-correct prose.

Residuals ($0 reachability — no production caller passes a criteria override; the only `evaluate()` sites are `fund.py:3604` and `factory.py:609`): `nan/inf/1e308` accepted as measurable; `level=1e-12` is still an off-switch contra the guard's own comment; a polluted `premia_criteria` misreports the stored top-level `criteria`.

## The kill — the corrected sentence states a false world-fact

The inversion's arithmetic is **flawless** (independently re-derived by bisection: matches to 4.99e-05 on all 336; reproduces the engine's own published PSR to 2.13e-14). What it is *labelled* is not. The gate's docstrings rest on "the engine publishes no target" — absence in the OUTPUT scored as absence in the world.

LEAN, `Common/Statistics/PortfolioStatistics.cs:310-312` (fetched verbatim):

```csharp
// deannualize a 1 sharpe ratio
var benchmarkSharpeRatio = 1.0d / Math.Sqrt(tradingDaysPerYear);
ProbabilisticSharpeRatio = Statistics.ProbabilisticSharpeRatio(listPerformance, benchmarkSharpeRatio, (double)riskFreeRate / tradingDaysPerYear).SafeDecimalCast();
```

**The target is an annualised Sharpe of exactly 1.00, for every candidate**, on excess returns (`Statistics.cs:231-237` subtracts a daily rf). And `tradingDaysPerYear = 252` sits in `algorithmConfiguration` of **273 of 273** stored `-summary.json` files — beside the PSR the gate reads.

The printed 1.17–2.26 spread decomposes as measured artifact: `implied_target_sharpe` omits the daily rf (OLS on `1/sd_daily`: **R² = 0.701**, model K=252/rf=5% fits at median −0.0015/obs) plus the 252→365.25 annualisation (×1.2039 — the D36 clock factor from the other side). Direct confirmation from LEAN's own published Sharpe: |err|<5pp on 189/273.

**What ships wrong:** 288 refusals print a per-candidate target (e.g. "+1.78, NOT at zero" where the answer is +1.00 for all); 368 print "UNSTATED" where the answer is recoverable from a file the fund already stores; and the register draft asks a human to sign "the engine does not publish it … a different hurdle for every candidate", proposing as falsifier an experiment that is unnecessary.

**The money in the kill points toward deployment**: `min_psr_pct = 65` on `engine_reported` means *P(the strategy's true **excess** Sharpe exceeds an annualised 1.0) ≥ 65%* — calibratable today, against a constant, with no container.

Smallest reproduction: candidate `008a35252790` — gate prints "+1.78"; LEAN source says 1/√252; the fund's own summary carries `tradingDaysPerYear: 252`; therefore 1.00. Overstated by 78%.

**What would change my mind:** a LEAN fork or pinned tag differing at `PortfolioStatistics` line 311 (image is `quantconnect/lean:latest`); any stored summary with `tradingDaysPerYear` ≠ 252 (checked 273); a demonstration that `listPerformance` is not what the reconstruction stands in for, breaking the 189/273 reproduction.

---

# ITEM 2 — prod-gate precondition pack v3 — RE-REVIEW (v2 verdict: CANNOT TELL)

**Liftable verdict:** `KILL (P4-tested leg) — it names two event types that exist nowhere in the repo, and read charitably it is a strict subset of controls_fired, which the live gate already reports MET; it would flip a BLOCKING precondition to satisfied today on 4-day-old evidence consisting of a wiring stub and the phantom-fill artifact. P3 and P4-wired re-derived and CERTIFIED; P2's server-side-re-read mechanism is a real improvement over v2 but its bound is unstated and its fence has no content requirement — CANNOT TELL on P2 as filed.`

## P4-tested — KILL, three grounds

1. **The spec names event types that do not exist.** `RiskHaltTriggered` / `ExitRuleFired`: zero hits repo-wide. The real members are `TradingHalted` (`events.py:235`) and `ExitRuleTriggered` (`events.py:229`). Taken literally the leg can never be satisfied — the seat's founding pattern (an event type named by a control and emitted by nothing), one step further along.
2. **Read charitably, it double-counts an already-satisfied precondition, exactly.** `_controls_have_fired` (`mode.py:346-374`) requires all four of `RISK_ALARM_RAISED`, `TRADING_HALTED`, `APPROVAL_REFUSED`, `EXIT_RULE_TRIGGERED`; the proposed set is a strict subset, and P1 reports **met** live. And no `TradingHalted` or `ExitRuleTriggered` event among all 1,279 names `risk_monitor` or `exit_check` — "an event naming the switch" is satisfiable only by adding a field to the emitter: a **repo** fact, in the same commit that opens the lock.
3. **No recency bound, and the available evidence is a stub and a glitch.** Newest firing is four days old; the entire `ExitRuleTriggered` population is `wiring_verification_2026_08_18` (a deliberate test) and `machinery-test` GLD −75.14% (the phantom fill the fund re-baselined its drawdown for). Shipping v3 as specced flips `kill_switch_wired_and_tested` from blocking to **met today with no new work** — `n_blocking` 4 → 3. That is the loosening, and it is the whole leg.

## P3 and P4-wired — CERTIFIED, re-derived

P4-wired: `judgement._wired` raises on `ok is None` (unobserved renders UNVERIFIED, never satisfied); the beat sits inside the `try` after the call (`main.py:210-212`); live heartbeats ok ~20s. P3: fix present at `riskmonitor.py:414` and `projections/positions.py:44`; pinning test at `tests/test_hazard_batch.py:743`.

## P2 v3 — improved mechanism, CANNOT TELL as filed

The server-side re-read repairs v2's "carry" defect — certified as a shape. Still short: (1) the bound names no number, so the CEO would approve a loosening he cannot evaluate (live reconcile: 10 of 11, $127.05, 6.7374%); (2) the fence has no content requirement (`{"SOFI": ""}` satisfies it); (3) the gate reads a stored snapshot when `prod_gate_report()` could re-read live in 0.09–0.14s — the expiry-bounds-the-clock-not-the-divergence ground narrowed, not closed.

**What would change my mind:** P4-tested naming the real event types AND stating marginal content beyond `controls_fired` (a recency bound, a per-position requirement, or a fire-drill event type with its own emitter and audit trail); evidence a halt/exit payload names its switch; P2 with the bound as a measured number, minimum fence content, and a gate-time re-read.

---

*Chair's resolution (2026-08-24): Item 1's kill re-verified directly (LEAN
source line 311; stored config) and accepted — D38 dispatched implementing
the adversary's prescribed repair (constant in the sentence; corrected
inversion demoted to a verification instrument; register draft rewritten;
certified surfaces frozen); the engine-target-pin experiment RETIRED and its
desk request resolved — one curl replaced one container; the chair's own
ruling record corrected in cto.md (the 1.34–1.51 figures were the artifact).
Item 2: both kills accepted — the nonexistent event names were the chair's
own spec defect, recorded; pack v4 deferred past Monday pending a real
fire-drill design and a measured basis for P2's bound (the pack buys nothing
until 12 more informative fills exist). Never edited per the non-negotiables.*
