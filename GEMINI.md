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

**PALETTE IS DECIDED AND ENCODED FOR YOU — this is mechanical now, no taste required.**
The design system is captured in **`src/app/clark/studio/theme.ts`** (the `KT` tokens),
distilled from the "Krypton Fund — Your Position" artifact:
> **emerald-on-near-black** · big *light* white numerals · small UPPERCASE mono labels ·
> thin-bordered rounded cards on a `#0A0A0B` ground · generous whitespace · calm & minimal.
> Accent color is **emerald** (green), NOT orange, NOT teal. Dark-only.

Apply it by find-and-replace, page by page. **Acceptance is measured by grep** (below):
- **Strategies page (`strategies/page.tsx`, 200+ orange refs): rip out ALL Terracotta
  Orange.** Replace every `#D97757` / `orange-*` / cream (`#FAF8F5` etc.) class with the
  matching `KT.*` token. After: `grep -c "D97757|orange-" strategies/page.tsx` → **0**.
- **Risk page:** replace ad-hoc zinc/glass with `KT.*` tokens so it matches.
- **Shared shell** (`StudioHeader`, `StudioNav`, `ClarkActionBar`): style ONLY from `KT.*`.
  Remove the `theme?: "dark"|"light"` props and all light-mode branches — this is dark-only.
- **Kill the decoration** (it's INCREASING — 8 files now use these): remove `GlassPanel`
  wrappers (use `KT.card`/`KT.panel`), remove `AnimatedNumber` (use plain `KT.numberLg`
  tabular-nums), drop gradients/neon/`StatusPulse` glow. Reserve `font-mono` for numbers
  and labels only.
- **Delete decorative dead shells** with no real spine data: audit and remove
  `VisualStrategyCanvas`, `QuantConnectChart`, `SentinelRadarFeed`, `EfficientFrontierChart`,
  `HeroChart` if they render placeholders. Keep only components fed by a real endpoint.
- Set `body` background to `KT_BODY_BG` (`#0A0A0B`) in the layout/globals so no light seam.

**Do NOT add new features or components during this pass.** This is a *subtraction* task.

**Verify (all must pass):**
```bash
grep -rc "D97757\|orange-[0-9]" src/app/clark/studio && echo "FAIL: orange remains"  # expect all 0
grep -rl "GlassPanel\|AnimatedNumber" src/app/clark/studio | wc -l                    # expect 0
npx tsc --noEmit && npm run build                                                     # 0 errors
```
Then `npm run dev`, open all five pages, confirm they read as ONE calm emerald-on-black
product that resembles the "Your Position" artifact.

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

## Next build: Strategy Composer page
See `../ClarkHarness/docs/STRATEGY_COMPOSER_SPEC.md` (Frontend task). New route
`/clark/studio/compose` — a multi-strategy allocator: pick child sleeves, weight them
(manual or HRP/optimizer), see the blended equity curve + risk roll up, deploy. KT tokens only.
