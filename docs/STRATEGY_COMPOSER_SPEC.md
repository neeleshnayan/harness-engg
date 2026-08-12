# Strategy Composer — Implementation Spec (for Gemini)

**Owner of the design:** the architect. Do not change contracts without flagging.
**Scope decision:** COMPOSITION-FIRST. The composer is a **multi-strategy allocator**:
you build a parent ("composite"/meta-strategy) by combining existing child strategies
("sleeves") with **weights**, and the blended risk/return rolls up. This is NOT a
single-signal authoring tool and NOT a Python IDE — those stay as-is.

## Concept
A composite strategy = a set of **weighted memberships** over existing child
strategies (the DAG we already have, now with weights on the edges). The composer
lets a non-quant (Rushi) allocate capital across sleeves, see the combined picture,
and deploy — the CIO's real job.

## Ground rules (same as the rest of the system)
1. **Spine is the only source of truth.** All state is event-sourced; the frontend reads.
2. **No fabricated numbers.** Real spine data or an honest empty state.
3. **Tests are the contract.** `pytest -q` stays green; new capability ships with tests.
4. **Frontend styles ONLY from `src/app/clark/studio/theme.ts` (KT tokens).** No orange,
   no glass, no new palettes. Emerald-on-near-black.
5. **Capital-preservation defaults:** default construction to **equal-weight or HRP**
   (robust), NEVER unconstrained mean-variance (fragile on small samples). Weights must
   sum to ≤ 100%; the remainder is cash.

## What already exists (build on it — do not recreate)
- DAG membership: `STRATEGY_ADDED_TO_PARENT` / `STRATEGY_REMOVED_FROM_PARENT`, a
  strategy's `parents` list, cycle guards, and NAV rollup over children (`fund.py`
  `list_strategies`). **Edges are currently UNWEIGHTED — that's the main gap.**
- `optimize_portfolio` (PyPortfolioOpt/HRP/skfolio CV) — reuse it, fed with child
  *return streams* instead of asset prices.
- Per-strategy backtest, risk (`/strategies/{id}/risk`), attribution.

---

## SPINE TASKS (ClarkHarness)

### S1 — Weighted membership
- New event `STRATEGY_MEMBERSHIP_WEIGHTED` (or extend `add_parent` to accept a
  `weight`). Each parent→child edge stores a target `weight` (fraction, 0..1).
- `StrategyService.set_member_weight(parent_id, child_id, weight, actor)` and fold the
  weights into the registry so each strategy exposes `members: [{child_id, name, weight}]`
  (for a container) and `member_weights` on the edges.
- Endpoint `POST /fund/strategies/{parent_id}/members` `{child_id, weight, actor}` and
  `POST /fund/strategies/{parent_id}/members/weights` `{weights: {child_id: w}, actor}`
  (bulk set). Guard: no cycles (reuse existing guard); warn (don't hard-fail) if weights
  sum ≠ 1.0.
- Tests: set/read member weights; bulk set; weights fold correctly; cycle still guarded.

### S2 — Composite construction (suggest weights)
- `POST /fund/strategies/{parent_id}/compose/weights` `{method, lookback_days}` where
  `method ∈ {equal, risk_parity, hrp, max_sharpe, min_volatility}`.
- Build each child's **return stream** from its backtest equity curve or NAV
  attribution over `lookback_days`; feed those streams to `optimize_portfolio`.
  `equal` = 1/N. Return `{weights: {child_id: w}, method, expected: {sharpe, vol, ret},
  cv: {pbo, oos_sharpe} }`. **Default method = `hrp`.**
- Does NOT persist — it suggests. The user reviews, then S1 persists.
- Tests: equal-weight sums to 1; hrp returns valid weights; handles a child with no
  backtest gracefully (skip/flag).

### S3 — Composite rollup + backtest
- Extend the strategy read so a container returns a **composite assessment**:
  `GET /fund/strategies/{parent_id}/composite` →
  `{ members:[{child_id,name,weight,exposure_usd,pnl_usd}], blended_equity:[{t,v}],
     metrics:{total_return,sharpe,max_drawdown}, risk:{concentration_hhi, drawdown_pct,
     flags[]}, weights_sum }`.
- `blended_equity` = Σ(weightᵢ × childᵢ equity curve), aligned on dates. Metrics computed
  from the blended curve. Reuse `SimpleBacktester`-style metric helpers.
- Tests: two children with known curves blend to the expected weighted curve + metrics.

---

## FRONTEND TASK (KryptonPay) — the Composer page
New route `/clark/studio/compose` (add to `StudioNav`). Styled ONLY with `KT` tokens.
Left-to-right / stacked blocks, all reading real spine data:

1. **Identity** — name the composite; create it (or open an existing container to edit).
2. **Members** — pick child strategies to include (from `getStrategies`, exclude self +
   descendants). Each becomes a weighted edge (S1). Show each child's state, exposure, and
   its own backtest Sharpe as a chooser aid.
3. **Weights** — a row per member with a slider + number input; a live "cash remainder"
   readout; and **auto buttons**: Equal · Risk-Parity · HRP · Max-Sharpe (call S2, populate
   the sliders, let the user tweep). Show the CV/PBO so overfit weights are visible.
4. **Rollup** (live, from S3) — blended equity curve (`KT` emerald area chart), combined
   metrics (return/Sharpe/maxDD), aggregated positions, and composite risk (concentration,
   drawdown vs limit). Honest empty state if a member lacks a backtest.
5. **Deploy** — persist weights (S1), set the parent to `deployed`; weights become the
   rebalance targets the runner/agents act on.

Reuse existing pieces where possible: `StrategyManageModal` membership UI, `RebalanceModal`,
`fund_api` methods. Add client methods: `setMemberWeight`, `setMemberWeights`,
`composeWeights`, `getComposite`.

## Acceptance
```bash
cd ClarkHarness && ./venv/Scripts/python.exe -m pytest -q          # green incl. new composer tests
curl -s localhost:8090/api/v1/fund/strategies/<parent>/composite | jq '.metrics, .weights_sum'
cd ../KryptonPay && npx tsc --noEmit && npm run build             # 0 errors
grep -rc "D97757\|orange-" src/app/clark/studio/compose           # 0
```
Done = you can create a composite, weight its sleeves (manually or via HRP), see a real
blended equity curve + risk, and deploy it — all from one page, all real spine data.
```
