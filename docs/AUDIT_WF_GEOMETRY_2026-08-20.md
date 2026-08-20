# Walk-forward window geometry for short holds — validator audit

**Seat: validator · trace 5fc56190 (the fund's FIRST seat-filed ask to
complete the full governance chain: mechanism filed → CEO approved → CTO
fired) · 2026-08-20 · local only. Every number is a run of the shipped
function or a query against the local mirror. Filed verbatim by the CTO at
resolve; CTO verification note at the bottom. Reproduction scripts in the
session scratchpad (wf_geometry.py, wf_regime.py, wf_episodes.py,
wf_counterfactual.py, deep.py, kscale.py, issued.py, wins.py, hw2.py).**

## 0. Verdict, up front

1. **The inversion reproduces exactly, with a closed form.** Out-of-sample
   calendar span is `K × floor(4·hold·365/252)` days — verified exact on
   276 combinations, 0 mismatches. At the shipped gate
   (`min_walkforward_folds=4`), a hold-1 strategy's ENTIRE out-of-sample
   evidence is **25 calendar days**; hold-21's is **484**.
2. **The record is clean.** Zero verdicts have ever been issued under a
   short-hold geometry (all 34 candidate rows ran 91d/121d/225d test
   legs). This is a PROSPECTIVE defect — the cheap time to fix it.
3. **Biggest finding, not the one asked for:** `window_for`'s fold count is
   **invariant to available history** — reach-back is fixed at
   `train + test·(K+1)` (walkforward.py:223-228); the floor only clips.
   Moving the floor from 2024-02-26 to 2016-08-22 leaves hold-3 at 5
   folds with IDENTICAL dates. Belt fold counts for TEST=84 at
   630/1260/2520 trading days: **4/5/5**, versus **4/12/27** in
   `scripts/gate_v5_audit_r4.py`'s `_folds(n)`, which packs the history.
   **GATE_V5_ROUND4 §3's history table therefore measures a fold generator
   the belt does not implement**, and §3 was the sole cited evidence for
   the WALKFORWARD_HISTORY_FLOOR change and backfill sequencing. The 10y
   backfill through the shipped function buys zero folds and zero
   out-of-sample coverage — it extends TRAIN legs only. (The r4 doc's
   MPPM/VR/margin work is untouched by this.)
4. **Item 4 confirmed, sharpened:** span(hold-21)/span(hold-1) =
   **exactly 24.2×** at K = 4, 6, 8, 12, 17 and 27 (= cal(84)/cal(4)).
   Count-scaling multiplies both sides by K and closes nothing — a
   count-based floor can never be a coverage criterion. Worse: at today's
   floor, raising min_folds gives short holds the higher count while
   hold-21 stays pinned at 4 and flips NOT TESTABLE — the scaled floor
   applied BEFORE a window-function change inverts testability toward the
   least-covered rules.

## 1. The curve (run, not asserted)

Gate v4.1, min_folds=4, floor 2024-02-26, end 2026-08-19. Selected rows
(full table in wf_rows.json):

| hold | test_days | K | OOS span (days) | quarters touched | reach-back |
|---|---|---|---|---|---|
| 1 | 4 | 5 | **25** | 1 | 393 |
| 3 | 12 | 5 | **85** (2026-05-26→08-19) | 2 | 451 |
| 4 | 16 | 4 | 92 | 2 | 480 |
| 5 | 20 | 5 | 140 | 3 | 509 |
| 10 | 40 | 5 | 285 | — | — |
| 12 | 48 | 5 | 345 | 5 | 712 |
| 21 | 84 | 4 | **484** (2025-02-26→2026-06-25) | 6 | 905 (clipped) |
| 23 | 92 | 4 | 532 | 7 | 905 (clipped) |
| **24+** | ≥96 | ≤3 | — | — | **NOT TESTABLE** |

Closed forms, both verified numerically:
`span_oos(h,K) = K·floor(4h·365/252)` (276/276 exact);
`K(h) = (cal(252+20h) − 366) // cal(4h)` (23/23 exact, unclipped).
Fold count is NON-MONOTONE: K drops 5→4 at holds 4, 9, 14, 19 — a pure
`cal()` rounding beat; a strategy declaring HOLD_DAYS=4 gets 20% fewer
folds than one declaring 3 or 5. Effective belt hold range today: 1..23.
Doc drift: walkforward.py:123-124's "6 folds for a 5-day hold" reproduces
at min_folds=5, not the shipped 4 (measured 5/4/1).

## 2. What the inversion costs in evidence

Using the fund's own regime statistic (`regime.mahalanobis_series` over
SECTOR_BASKET, 11/11 ETFs, 1004 scored days; reachable window = 623
sessions, 143 elevated ≥ p80, 39 extreme ≥ p95):

| hold | OOS sessions | % of reachable | % of all elevated days |
|---|---|---|---|
| 1 | 21 | 3.4% | 7.7% |
| 3 | 63 | 10.1% | 25.9% |
| 10 | 198 | 31.8% | 55.2% |
| 21 | 336 | 53.9% | 60.1% |

**The largest stress event in reachable history (turbulence 86.9,
2025-04-03→05-13) is invisible to every strategy with hold ≤ 17** — not
under-weighted; never in any test leg. Distinct-episode counts are
monotone in hold at every merge gap but the level is merge-dependent — do
not headline them. Honest counter-point, flagged by the auditor against
its own thesis: hold-3 covers 41% of EXTREME days in 10% of sessions
because the last quarter happened to be hot — narrow coverage lands hot or
cold, which IS the one-draw property.

At holds 1–4 the verdict sentence "kept ≥50% of its edge in all 5
measurable folds — the one result a single window could not have
manufactured" describes ≤92 consecutive days: the claim and its evidence
are the same window, subdivided.

Counterfactual (same history, same per-fold engine cost, folds PACKED via
the existing `step_days` parameter): hold-1 could run 107 folds spanning
535 days — the belt's cap discards 95% of available evidence for fast
rules. A design option for the CTO, not a threshold; measurement only.

## 3. Verdicts already issued: clean

34 candidates, 84 sweeps in the mirror. Test legs group at 91d (n=19, the
gate-v2-era five), 121d (n=34, all null_random_smallcap — exactly the
hold-21 four-fold set), 225d (n=30, single-window holdout). No verdict
ever ran a leg under 91d; the 6 not_testable nulls are hold-63 behaving
correctly. Qualifier trust check: 73/79 stored holdout_results have
dates_honoured=True; median engine-actual/requested test-leg ratio 1.000 —
requested dates are a sound basis for a qualifier, gated on
`dates_honoured`.

## 4. Gate v5 round 4 interaction — two separate defects

(a) The mechanism's independence claim CONFIRMED and sharpened: the 24.2×
span ratio is invariant to K (see §0.4). (b) The r4 audit's `_folds(n)`
packs history; the belt's `window_for` does not (see §0.3). §7's
`available` was undefined against any function: read as len(window_for
folds) the scaled floor is a permanent no-op; read as packed count it
makes every 21-day strategy NOT TESTABLE. The corrected framing is now
§8 of GATE_V5_ROUND4 (the floor change, the window-function change, and
the backfill are ONE package; `available` is defined against the NEW
generator; §3's table is the measurement of that proposed generator).

## 5. The coverage qualifier — recommendation

**Yes — every walk-forward verdict should carry one, and it is a rendering
change.** All inputs already exist in the fold rows
(walkforward.py:347-358: train/test start+end, dates_honoured, measurable,
test_orders); `summarise()` receives them and computes nothing from the
dates. Recommended fields, computed over MEASURABLE folds with
dates_honoured=True only: `oos_start`, `oos_end`, **`oos_span_days`** (the
headline — monotone, parameter-free), `oos_folds`,
`oos_folds_dishonoured`, `hold_days` + `hold_days_source` (an "assumed"
source is itself a caveat). Rejected as qualifiers: quarter-count
(boundary luck) and episode-count (merge-parameter dependent). Verdict
text becomes: "kept ≥50% of its edge in all 5 measurable folds (median
74%) — across 85 calendar days of out-of-sample evidence, 2026-05-26 to
2026-08-19."

Two plumbing gaps verified live: `factory._run` (165-171) DISCARDS the
fold table after judging (only verdict+winner survive), so the qualifier
must be written into `verdict["checks"]` by `gate.evaluate` (beside
gate.py:447-449); and `factory.history` (366-372) serves five count
fields only — adding to checks surfaces it in the API for free.

A coverage THRESHOLD is deliberately not recommended — whether "an alpha
verdict requires ≥N days of out-of-sample span" belongs in the gate is a
CEO decision with a written reason, in either direction.

## 6. What this does not cover

§1/§4 are exact function evaluations (no sampling error); §2's regime
percentages are one history's realisation — the direction is structural,
the specific numbers are not general. Turbulence is a proxy for regime,
not a definition (no absorption series at this depth — 750d burn-in). No
cost/drift/survivorship modelling (fold geometry is date arithmetic), but
the ETF basket carries the vendor's survivorship view — irrelevant at this
floor, decisive at a 10y one. `DECISIONS_PER_TEST_LEG = 4` — the constant
that justifies the whole leg sizing — is unvalidated and currently
unfalsifiable (`total_orders` counts symbol fills: median 67 on legs
designed for 4 decisions). The corrected r4 history tables were NOT
re-run.

## GAPS (aimed at strategy generation)

1. A committed `scripts/wf_geometry_audit.py` — today "how much calendar
   does the gate see at hold 7?" costs a validator dispatch; it should be
   a question a quant asks before writing the algorithm.
2. `hold_days`/`hold_days_source` served by the candidates API — set at
   factory.py:218-219, dropped at 366-372; the strongest predictor of a
   verdict's evidentiary weight is invisible, and an ASSUMED hold is a
   silent fabrication of the test's shape.
3. The fold table persisted on the candidate row (dates survive only in
   fund_lean_sweeps.holdout, with no candidate_id — carried from the
   floor review, still open).
4. A decision counter distinct from total_orders, so
   DECISIONS_PER_TEST_LEG can be measured at all.
5. A named, versioned definition of `available` folds (now in r4 §8).
6. A stored regime series (regime.py returns only `latest`) — so a premia
   claim's "harvests carry in calm coupling" becomes checkable against
   whether the test legs ever contained the claimed regime.

---

## CTO verification note (2026-08-20, at resolve)

The central claim was reproduced independently before acting: at floors
2024-02-26 and 2016-08-22, hold-3 returns 5 folds with IDENTICAL test-leg
dates; hold-21 gains exactly the one clipped fold (4→5) then caps. My own
r4 audit modeled a packed generator — the defect is mine, found by the
bench, and GATE_V5_ROUND4 now carries §8 correcting and reframing its
history limb (the window-function change + floor + backfill as one
package, `available` defined against the new generator). The API card's
fold-planning bullet was corrected the same hour. The coverage-qualifier
recommendation and the remaining GAPS go to the CEO on
run-validator-wfgeom. Recorded against trace 5fc56190; the first
seat-filed ask closed its full loop today: mechanism filed → CEO approved
→ CTO fired → measured answer + a defect in the CTO's own instrument.
