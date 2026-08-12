# Krypton Studio — Remediation Task List

**Audience:** an AI coding agent (Gemini) working across three sibling repos in
`C:\Users\user\Documents\Krypton Fund\`:
- `ClarkHarness` — the Python/FastAPI **spine** (source of truth; 68 tests passing).
- `Krypton_Clark` — the Strands **orchestrator** (agents API).
- `KryptonPay` — the Next.js **frontend** (this is where most work is).

All three are on branch `claude/krypton-fund-agentic-j8r2mu`.

## Why this list exists
A large batch of features was added quickly. The backend is healthy, but the
frontend **does not type-check (18 errors → `next build` fails)**, several panels
show **fabricated/hardcoded numbers**, and the visual design **fragmented into 3+
competing looks** across the Studio pages. This list fixes that. Do the tasks
**in priority order**. **P2 (design retheme) is BLOCKED pending a human palette
decision — do not start it until told which system to standardize on.**

## Ground rules (do not violate)
1. **The spine is the only source of truth.** The frontend and Clark must *read*
   NAV / P&L / positions / risk from the spine (`/api/v1/fund/*`). Never invent or
   hardcode financial numbers, timestamps, win-rates, or fallback values.
2. **No new features.** This is remediation only. Do not add pages, charts, or
   endpoints. If something is broken and unused, prefer deleting it over patching.
3. **Every task has an acceptance check.** A task isn't done until its check passes.
4. **Run the verification suite (bottom of file) before declaring done.**

---

## P0 — Make the frontend build (BLOCKING, do first)

Run `cd KryptonPay && npx tsc --noEmit`. There are 18 errors. Fix each below. The
root cause of most is reading fields off the **wrong level** of an API response.

**Reference — actual API response shapes** (`KryptonPay/src/lib/fund_api.ts`):
```ts
BacktestBySymbolResponse = { result: BacktestResult; strategy; source; symbol; bars: {closes,dates,start,end} }
// metrics (total_return, sharpe, max_drawdown, n_trades) live on `.result`, NOT top level
StrategyRiskResponse   = { strategy_id, name, state, exposure_usd, pnl_usd, concentration_hhi, n_assets, assets[], flags[], scenarios[] }
// NOTE: no `correlation` field here — correlation is on StrategyOptimizeResponse.correlation
StrategyBarsResponse   = { strategy_id, assets[], bars: Record<symbol, {closes, dates, source, start?, end?, error?}> }
```

### P0.1 — `strategies/page.tsx` (12 of the 18 errors)
- **`updateStrategyState` does not exist.** Lines ~528 and ~543 call
  `fundApiClient.updateStrategyState(id, "deployed"|"paused", ...)`. The real
  method is **`fundApiClient.setState(strategyId, state, actor)`**. Rename both.
- **Backtest fields read at the wrong level.** Lines ~493-497 and ~1538-1556 read
  `res.total_return` / `res.sharpe` / `res.max_drawdown` / `res.n_trades`. These
  live on `res.result.*`. Change to `res.result.total_return`, etc. (`res.symbol`
  and `res.bars` remain top-level — those are correct.)
- **`bars` type mismatch (line ~510):** a `number` is assigned where a
  `{closes,dates,start,end}` object is expected. Read the bars object, not an index.
- **`positions` type mismatch (line ~1099):** the object being passed does not
  match `NavPosition[]` (`{symbol, qty, mark, usd_value}`). Map to that exact shape.
- **`correlation` on the wrong type (line ~1785):** `StrategyRiskResponse` has no
  `correlation`. Feed the Correlation Matrix from
  `optimizeStrategy(...).correlation` (`StrategyOptimizeResponse.correlation`)
  instead, or hide the matrix when no correlation data is present. Do **not** add a
  `correlation` field to `StrategyRiskResponse` unless the spine actually returns it
  (check `ClarkHarness/app/api/v1/fund.py` `GET /fund/strategies/{id}/risk`).
- **Optimize setter (line ~329):** `method` is not a field of
  `StrategyOptimizeResponse`. You are storing the request param in the response
  state — keep request params (`method`, `lookback`) in separate state, not merged
  into the response object.
- **Remove the hardcoded fallback id (line ~484):** `selected || "strat-1"` — there
  is no `"strat-1"`. If no strategy is selected, disable the backtest button
  instead of calling with a fake id.

### P0.2 — `components/ResultsDisplay.tsx` (line ~802)
`Property 'symbol' does not exist on type 'BacktestResult'`. `BacktestResult` has
**`target_assets: string[]`**, not `symbol`. Use `backtestResult.target_assets?.[0]`.

### P0.3 — `components/PDFReportExporter.tsx` (lines ~28-29)
`Property 'data' does not exist on type 'BacktestResult'`. There is no `.data`.
Use the real fields (`data_points`, `metrics`, `trades`). If this exporter is
half-built and unused, **delete the file and its imports** (preferred).

### P0.4 — `components/DevtoolsOverlay.tsx` (line ~19)
`Cannot find name 'ChatMessage'`. Add the import:
`import { ChatMessage } from "../types";` (or the correct relative path). If the
overlay is a dev-only shell that isn't wired in, delete it.

### P0.5 — `components/charts/AllocationCharts.tsx` (line ~24)
Return-type union mismatch: a `useMemo`/callback returns
`BacktestAllocation[] | {...}[]`. Make both branches return `BacktestAllocation[]`
(map the fallback objects into that exact interface), or annotate and cast once.

**P0 acceptance:** `cd KryptonPay && npx tsc --noEmit` prints **0 errors**, and
`npm run build` completes successfully.

---

## P1 — Remove fabricated / hardcoded data

The UI must show real spine data or an honest empty/loading state — never invented
numbers. Search: `grep -rnE "Math\.random|102978|100% Win Rate|\+\$450|7:00:00 PM|const MOCK|SAMPLE|dummy" KryptonPay/src/app/clark/studio`.

### P1.1 — `risk/page.tsx`
- Delete the hardcoded `auditLogs` seed array (the "7:00:00 PM … Hourly compliance
  scan …" entries). Either drive the feed from a real spine source or render an
  empty state ("No audit checkpoints yet").
- Delete the **"Clark Reasoning Accuracy / 100% Win Rate / +$450.00"** banner unless
  those numbers come from a real endpoint (they don't today). If you want a
  win-rate, compute it from `/fund/theses` post-mortems; otherwise remove it.
- Remove the fallback `{ nav_usd: 102978, strategies: [] }` on the
  `getStrategies().catch(...)`. On error, keep prior state or show "spine
  unreachable" — do not substitute a fake NAV.

### P1.2 — `strategies/page.tsx`, `charts/CorrelationMatrix.tsx`, `charts/QuantConnectChart.tsx`, `components/VisualStrategyCanvas.tsx`
Audit each for hardcoded series, `Math.random()` data, or placeholder rows. Replace
with real spine data (`getStrategyBars`, `getStrategyRisk`, `optimizeStrategy`,
`getBars`) or an explicit "no data" state. `TVAreaChart.tsx` may legitimately use a
gradient id — inspect, don't blindly strip.

**P1 acceptance:** the grep above returns no hardcoded financial values; every
number visible in the Studio traces to a spine response or is shown as empty/loading.

---

## P2 — Unify the design system  ⛔ BLOCKED: confirm palette with the human first

**The problem:** the five Studio pages use three different visual languages:
- `page.tsx` (Overview): zinc/teal dark — the original system.
- `strategies/page.tsx`: Terracotta Orange (`#D97757`) + `font-mono` + its own
  light/dark switcher (207 orange refs).
- `risk/page.tsx`: dark-zinc "glassmorphism" (0 orange).
- `theses` / `approvals`: thin zinc wrappers.

Tabbing between them feels like three different apps. `StudioHeader` and
`ClarkActionBar` were rethemed to orange/cream and now clash with the Overview.

**Do NOT start until the human confirms ONE of these:**
- **Option A (default):** standardize on the original **zinc/teal dark** system
  (matches the rest of KryptonPay). Remove per-page light/dark switchers.
- **Option B:** commit fully to the **Terracotta light/dark** system and apply it to
  ALL five pages + shared components, with a single global theme toggle (not
  per-page).

Once confirmed, define the tokens in ONE place (`src/app/clark/studio/theme.ts` or
Tailwind config) and apply everywhere. Acceptance: identical header/nav/action-bar
on all five pages; one palette; at most one global theme toggle; no page overrides.

---

## P3 — Fix remaining seams

- **Plumb the `theme` prop or drop it.** `StudioHeader`/`ClarkActionBar` accept a
  `theme` prop but only `strategies/page.tsx` passes it. Either pass it consistently
  from every page (tied to the P2 global theme) or remove the prop and the dual
  styling. Do not leave it half-wired.
- **No hardcoded entity ids** anywhere (`"strat-1"`, `selectedAssetSym = "AAPL"` as a
  hard default that assumes a position exists). Default to the first real item from
  the spine, or an empty state.
- **Verify every `fundApiClient` call in the Studio** resolves to a real method and
  reads the correct response shape (cross-check `src/lib/fund_api.ts`).

---

## P4 — Repo hygiene

- **`ClarkHarness/.gitignore`:** add `.firestore_local_db.json` (the disk-persistence
  DB is currently untracked-but-not-ignored and will get committed). Add any other
  local runtime artifacts.
- **Commit `KryptonPay/package.json` + `package-lock.json`** (they add
  `@monaco-editor/react`) so installs are reproducible — or remove the dep if the
  Python IDE is being dropped.
- **Delete decorative dead shells.** Any Studio component that renders placeholder UI
  and is not wired to the spine should be removed, not left as scaffolding (candidates
  to inspect: `PDFReportExporter`, `DevtoolsOverlay`, `VisualStrategyCanvas`,
  `EfficientFrontierChart`, `QuantConnectChart` — keep only what has a real data source).

---

## Verification suite (run before declaring done)
```bash
# Frontend must type-check AND build
cd KryptonPay && npx tsc --noEmit && npm run build

# No fabricated data left
grep -rnE "Math\.random|102978|100% Win Rate|\+\$450|7:00:00 PM|const MOCK" src/app/clark/studio || echo "clean"

# Spine still green
cd ../ClarkHarness && ./venv/Scripts/python.exe -m pytest -q

# Clark imports cleanly
cd ../Krypton_Clark && ./venv/Scripts/python.exe -c "import app.main; print('clark ok')"
```

## Appendix — raw `tsc --noEmit` errors (the P0 checklist)
```
AllocationCharts.tsx(24,62)   TS2345  return type union
DevtoolsOverlay.tsx(19,14)    TS2304  Cannot find name 'ChatMessage'
PDFReportExporter.tsx(28,62)  TS2339  'data' not on BacktestResult
PDFReportExporter.tsx(29,70)  TS2339  'data' not on BacktestResult
ResultsDisplay.tsx(802,36)    TS2339  'symbol' not on BacktestResult (use target_assets[0])
strategies/page.tsx(329,11)   TS2353  'method' not in StrategyOptimizeResponse
strategies/page.tsx(493,28)   TS2339  'total_return' -> res.result.total_return
strategies/page.tsx(494,30)   TS2339  'sharpe'       -> res.result.sharpe
strategies/page.tsx(497,187)  TS2339  'n_trades'     -> res.result.n_trades
strategies/page.tsx(510,11)   TS2322  bars: number vs {closes,dates,...}
strategies/page.tsx(528,27)   TS2339  updateStrategyState -> setState
strategies/page.tsx(543,27)   TS2339  updateStrategyState -> setState
strategies/page.tsx(1099,25)  TS2322  positions shape != NavPosition[]
strategies/page.tsx(1538,140) TS2339  'total_return' -> .result.total_return
strategies/page.tsx(1544,134) TS2339  'sharpe'       -> .result.sharpe
strategies/page.tsx(1550,137) TS2339  'max_drawdown' -> .result.max_drawdown
strategies/page.tsx(1556,128) TS2339  'n_trades'     -> .result.n_trades
strategies/page.tsx(1785,57)  TS2339  'correlation' not on StrategyRiskResponse (use optimize.correlation)
```
