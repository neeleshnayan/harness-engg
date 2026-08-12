# GEMINI.md — KryptonPay (Krypton Fund frontend)

You are the implementer. This file is your standing brief; the detailed specs are
linked below. Work in small commits and keep the build green at all times.

## The system (one paragraph)
Three sibling repos in `C:\Users\user\Documents\Krypton Fund\`: **ClarkHarness**
(Python/FastAPI **spine** — the ONLY source of truth: NAV, positions, P&L, risk),
**Krypton_Clark** (agent orchestrator), and **KryptonPay** (this Next.js frontend).
The frontend only *reads* the spine at `/api/v1/fund/*` (dev proxy: `/proxy/harness`).

## Non-negotiable ground rules
1. **Never fabricate or hardcode a financial number, timestamp, win-rate, or
   fallback value.** Every number on screen must come from a spine response, or be
   shown as an honest empty/loading/"spine unreachable" state. (We already deleted a
   batch of fake data — do not reintroduce any.)
2. **Keep it building.** After every change: `npx tsc --noEmit` = 0 errors and
   `npm run build` passes. Never commit a red build.
3. **No new features.** This phase is *cleanup + wiring*, not surface area. Prefer
   deleting unused/decorative components over patching them.

## Priorities (in order)
### P1 — Simplify the UI to ONE clean system  ⬅ current focus
The Studio fragmented into competing looks (Overview = zinc/neutral, Strategies =
Terracotta Orange with 200+ orange refs, Risk = dark glassmorphism) plus ~30
decorative components. It reads as several different apps. **Kill the bs.**

**PALETTE DECISION (made — do not re-litigate):** standardize the ENTIRE Studio on
the artifact **"Krypton Fund — Your Position"**
(`https://claude.ai/code/artifact/7b347281-b6fb-4827-be14-f4369fcd9381`). The human
will paste the artifact's source/screenshot to you — **treat it as the exact visual
spec** (palette, spacing, typography, component style). Apply it uniformly to ALL
five pages. Concretely:
- **One design system, one place.** Extract the artifact's tokens into
  `src/app/clark/studio/theme.ts` (or Tailwind config) and use them everywhere.
- **Delete the competing palettes.** Remove the **Terracotta Orange** styling from
  `strategies/page.tsx` (200+ refs) and the **dark-glassmorphism** from
  `risk/page.tsx`; both must adopt the artifact's system. **Remove every per-page
  theme switcher / per-page palette.** At most ONE global toggle, applied uniformly.
- **Consistent shell.** `StudioHeader`, `StudioNav`, `ClarkActionBar`, and cards must
  look identical on all five pages (Overview / Strategies / Approvals / Theses / Risk).
- **Restraint.** Drop neon/terminal/glass effects, excessive gradients, and animated
  numbers. Reserve `font-mono` for numbers/tickers only.
- **Delete decorative dead shells** not wired to the spine (audit `studio/components/`:
  `VisualStrategyCanvas`, `QuantConnectChart`, `SentinelRadarFeed`,
  `EfficientFrontierChart` — remove any that render placeholder UI with no real data
  source). Keep only components fed by a real endpoint.
- **Verify visually:** run `npm run dev`, open each of the five pages, confirm they
  look like one product and match the artifact.

### P2 — Close the RISK and STRATEGIES tabs against real data
The spine is gaining a full risk engine (kill-switch, continuous monitor, alarms).
Implement the **frontend wiring in `../ClarkHarness/docs/RISK_ENGINE_SPEC.md`,
Tasks 7 & 8** — add the `fundApiClient` methods and build:
- **Risk tab:** kill-switch banner (halt/resume), drawdown + limit-utilization gauges,
  a LIVE alarm feed from `/fund/risk/alerts` (this replaces the deleted fake audit log),
  a per-asset risk table, and a limits editor. Poll `/fund/risk/monitor` every 3–5s.
- **Strategies tab:** per-strategy risk (exposure, weight, P&L, limit utilization,
  breach flag) from `assess().strategies[]` or `/fund/strategies/{id}/risk`.

### P3 — Finish the remaining cleanup
Work the still-open items in **`docs/GEMINI_CLEANUP_TASKS.md`** (P3 seams: theme-prop
plumbing, no hardcoded ids; P4 hygiene: commit `package.json`, remove dead code).

## Verify before every commit
```bash
npx tsc --noEmit && npm run build
grep -rnE "Math\.random|102978|100% Win Rate|\+\$450|const MOCK|sampleData" src/app/clark/studio || echo clean
```

## Where to read more
- `docs/GEMINI_CLEANUP_TASKS.md` — the itemized cleanup list (P0/P1 done; P2/P3 open).
- `../ClarkHarness/docs/RISK_ENGINE_SPEC.md` — the risk engine + the Risk/Strategies wiring.
- `src/lib/fund_api.ts` — the API client; every response shape is defined here. Cross-check
  field paths against it (a common past bug was reading `.total_return` instead of
  `.result.total_return` on backtest responses).
