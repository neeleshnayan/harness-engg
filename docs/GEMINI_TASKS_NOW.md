# Gemini — current task queue (validated findings, work top-down)

Validation pass 2026-08-13. Composer spine (S1/S2/S3) landed and `pytest -q` is green
(76 passed). These are the defects found by reading the logic, NOT by running tests —
the tests pass *and the code is still wrong*. Fix in order. Each ships WITH a test.

---

## C1 — [CRITICAL] Composite rollup fabricates a flawless equity curve
**File:** `app/api/v1/fund.py`, `get_composite_strategy`, ~lines 839-888.

When a child has no real price series, the fallback SYNTHESIZES one from its stored
`total_return`:
```python
daily_r = (1.0 + ret / 100.0) ** (1.0 / max(1, n_bars)) - 1.0
series = pd.Series((1.0 + daily_r) ** np.arange(n_bars), index=idx)
```
That is a perfectly smooth exponential — a fabricated curve with no volatility. Proven
output for `total_return=15%, bars=100`:
- `max_drawdown = 0.0` (monotonic curve can never draw down)
- return vol = `1.16e-16` (floating-point noise), which passes the `if std_val > 0`
  guard and yields **`sharpe = 190,816,542,062,945`**

So a composite whose children lack real curves renders as a **zero-drawdown,
infinite-Sharpe strategy**. This is the single most dangerous number we could put in
front of a capital-allocation decision, and it violates ground rule #1 (no fabricated
financial numbers).

**Fix:** do NOT synthesize a curve. If a child has no real equity series:
- exclude it from `blended_equity` and from `metrics`,
- add an explicit flag: `"Child '<name>' has no backtest curve — excluded from rollup"`,
- return `metrics: null` (not zeros) when NO child has a real curve, so the UI shows an
  honest empty state instead of `0.00`.
Also guard the Sharpe: require `std_val > 1e-9` AND `len(pct_changes) >= 20`, else
`sharpe = None`. Never emit a Sharpe from a degenerate series.

**Test:** a child with only `total_return` recorded (no curve) must NOT contribute a
synthetic curve; assert `max_drawdown` is not 0.0-by-construction and that the flag is
present; assert no Sharpe is returned for a constant/degenerate series.

---

## C2 — [HIGH] Rollup averages raw PRICES instead of returns
**File:** same function, ~lines 829-837.
```python
for sym in c_assets[:3]: ...
series = pd.DataFrame(closes_list).T.mean(axis=1)
```
Averaging raw close prices makes a high-priced asset dominate. Proven: AAPL ($230, +10%)
+ F ($11, flat) → price-average reports **+9.54%** when the true equal-weight return is
**+5.00%**. Nearly 2x overstated.

**Fix:** normalize each asset series to 1.0 at its first bar, THEN average (or average
`pct_change` and cumulate). Also remove the silent `[:3]` truncation — either use all
scoped assets or, if you must cap, surface a flag naming the dropped symbols. Silent
truncation reads as full coverage.

**Test:** two assets with very different price levels and known returns blend to the
correct equal-weight return (the AAPL/F case above → 5.00%, not 9.54%).

---

## C3 — [HIGH] The S3 test does not test the blend math
`tests/test_strategy_composer.py::test_s3_composite_rollup_api` asserts only
`"metrics" in composite` and `len(blended_equity) > 0`. It would pass if the blend were
completely wrong. The spec required: *"two children with known curves blend to the
expected weighted curve + metrics."*

**Fix:** assert real numbers. Two children with known curves at weights 0.6/0.4 must
produce the exact expected blended value per date and the expected `total_return`.
Assert `weights_sum`, the cash remainder when weights sum < 1, and the HHI value.

---

## C4 — [MEDIUM] Broker reconciliation as a SIGNAL (replaces the reverted NAV hijack)
A prior change made `NavService.compute()` return live Alpaca equity AS the NAV, with a
hardcoded `units_outstanding` fallback that forced nav_per_unit to ~$1.00 and destroyed
the unit ledger. It was reverted (commit `f0b18c9`). **NAV folds from the event log ONLY.**

Build the correct version: `GET /fund/venue/reconcile` →
```json
{ "book_nav": 0, "broker_equity": 0, "delta_usd": 0, "delta_pct": 0,
  "per_symbol": [{"symbol":"", "book_qty":0, "broker_qty":0, "drift":0}], "as_of": "" }
```
It COMPARES book vs broker and surfaces drift as an observability/risk signal (a large
delta should raise a risk alarm). It must write NO events and MUST NOT touch
`compute()`/`strike()`. Ships with a test. If Alpaca is unconfigured, return an honest
`{"configured": false}` — never zeros that look like agreement.

---

## C5 — [MEDIUM] Frontend: finish killing the light/dark plumbing
Studio is **dark-only**. `strategies/page.tsx:223` already hardcodes `const theme = "dark"`,
so every light-mode branch is dead code, and `Sun`/`Moon` are imported but never rendered.
I already added `src/app/clark/studio/layout.tsx` (scoped `dark` + `KT_BODY_BG`) which
fixed the white-seam bug — do not revert it, and do NOT set `dark` on `<html>` globally
(wallet/customer are light by design).

**Fix (mechanical):** remove the `theme?: "dark" | "light"` prop and every light branch from:
`ClarkActionBar.tsx`, `StudioHeader.tsx`, `PythonCodeEditor.tsx`,
`charts/AllocationDonut.tsx`, `charts/CorrelationMatrix.tsx`,
`charts/EfficientFrontierChart.tsx`, `charts/QuantConnectChart.tsx`.
Then drop the now-unused `theme={theme}` call sites and the `const theme = "dark"` and the
unused `Sun`/`Moon` imports in `strategies/page.tsx`. Style only from `KT.*`.

**Verify:**
```bash
grep -rn "theme=\|theme?:\|'light'" src/app/clark/studio | grep -v theme.ts   # expect 0
npx tsc --noEmit && npm run build
```

---

## C6 — [LOW] Strategies page should import KT constants
`strategies/page.tsx` is visually correct (emerald) but uses ad-hoc `emerald-*`/`zinc-*`
classes instead of importing `KT`. Convert to `KT.*` tokens so the palette stays
single-sourced. No visual change intended.

---

## Standing gates — run before every commit
```bash
cd ClarkHarness && ./venv/Scripts/python.exe -m pytest -q
cd ../KryptonPay && npx tsc --noEmit && npm run build
grep -rlE "D97757|orange-[0-9]|GlassPanel|AnimatedNumber" src/app/clark/studio   # expect none
```
**Deleted as fabricated — do not resurrect:** `sentinel.py`, `pair_arb.py`,
`macro_regime.py` (hardcoded "signals" that auto-wrote theses/memos into the real event
log). `optimization.py` is real and stays.
