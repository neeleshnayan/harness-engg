# ADVERSARY VERDICT: KILL — gate v5 redesign (round 2)

**Artifact attacked:** docs/GATE_V5_DESIGN_2026-08-19.md
**Reviewer: adversary agent (blind), 2026-08-19. Ran the committed audit script
plus its own constructions (local copy; committed file untouched). This is the
SECOND kill in the v5 chain — the first killed the original sketch; this kills
the redesign built around that kill.**

## The headline

The premia rule's defence — "a levered or watered null can match but never beat
the benchmark's Sharpe" — is true only for fakes with EXACTLY ZERO idiosyncratic
vol, which is the only kind the audit script tests. Add any tracking noise and the
strict inequality becomes a per-fold coin flip; majority-of-4 on a coin flip
passes ~31%. The doc's 0.0% null rows are an artifact of degenerate nulls.

## Demonstrated, with seeded runs (1,500 draws/arm)

| process (no premium, no alpha unless noted) | v5_alpha (floor 0) | v5_premia | regime |
|---|---|---|---|
| bench + 3%-vol zero-Sharpe noise | 5.7% | **29.4%** | rising |
| 0.9×bench + 3% noise ("watered") | 6.7% | **29.3%** | rising |
| 2×bench + 10% noise (the round-1 fake, plus realism) | 5.5% | **28.3%** | rising |
| beta drift 0.5→2.0, zero alpha | **14.9%** | 29.5% | rising |
| bench + 10% noise | 6.2% | **40.7%** | falling |
| **all cash** | 0.0% | **68.0%** | falling |
| negative alpha + rising beta | 5.3% | 15.5% | rising |

Minimal repro (imports the committed rules unmodified):
```
./venv/Scripts/python.exe -c "
import random, sys; sys.path.insert(0,'scripts')
import gate_v5_audit as g
rng = random.Random(20260819); hits = 0
for _ in range(1500):
    bench = g._series(1.0, 0.20, g.N, rng)
    strat = g._make(bench, 1.0, 0.0, 0.03, rng)
    hits += g.rule_v5_premia(strat, bench, 0.0)
print(100*hits/1500)"   -> 29.3
```

## The five counts

1. **Premia rule false-passes ~30% of realistic no-premium strategies** (the coin
   flip above), and in falling markets rewards uncompensated risk — all-cash
   passes 68% because a degenerate Sharpe is scored as the value 0.0 and 0 beats
   every negative benchmark Sharpe. An absence scored as a value.
2. **The main table measures a gate the doc did not adopt**: it ran at floor 2.0
   (script default) while the doc adopts floor 0. The doc's two tables disagree
   about which gate exists.
3. **Beta drift leaks beta back into "alpha"**: a zero-alpha null with beta
   drifting 0.5→2.0 passes the alpha gate at 14.9% vs 19.3% power for genuine
   Sharpe-0.6 alpha — under 5 points of separation. Disclosed as unknown in the
   doc; measured here as material.
4. **"Alpha implies premia-quality" is false**: genuine alpha (S 0.5) at 40% vol
   on β=1 gives total Sharpe 0.894 < benchmark's 1.0 — real alpha, worse
   risk-adjusted return. The routing argument built on the implication fails.
5. **Day-one BENCHMARK ABSENT for the whole belt**: undeclared candidates default
   to alpha, alpha requires a declared benchmark, and no historical candidate
   declares one.

**What survived:** the reproduction discipline (both printed commands reproduce to
the digit; crc32 seeding sound), and the alpha rule against iid constant-beta
nulls.

## What would change the verdict

1. A null battery where every null carries idiosyncratic vol ≥ 1%, with v5_premia
   holding them at a stated false-positive budget — which requires changing the
   rule (a significance test or margin on the paired difference; more folds), not
   the battery.
2. Stated behaviour for folds where the benchmark's test-leg Sharpe is negative or
   either Sharpe is degenerate, with a measured falling-market row in the doc.
3. Either a proof restricted to the vol range where "alpha implies premia-quality"
   holds, or removal of the claim and the routing argument built on it.
4. The main table regenerated at the adopted floor.
