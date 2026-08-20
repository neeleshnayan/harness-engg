# builder — working state
(appended by the CTO at each dispatch resolution; newest at the bottom)

## 2026-08-20 — seeded at hiring
- No dispatches yet. First brief queued on the desk: UI consolidation (7 tabs ->
  5; fold Mechanics into Desk; retire map/hunting-ground from Lab) — request
  c91d5c07, CEO-approved direction.
- House style: read neighbouring files first; comments carry the why and the
  measured reason; tests must be unable to bless the bug they guard against.

**builder — after dispatch cd92e175 (2026-08-20), first real dispatch**

- **The worktree I am dispatched into is a ClarkHarness worktree, seeded from that repo's initial commit (LICENSE only).** The UI code and briefs live in the SEPARATE `KryptonPay` repo at `C:\Users\user\Documents\Krypton Fund\KryptonPay`. The bash guard blocks `cd`/`-C` git ops against shared checkouts. Working method that succeeded: `git clone --no-hardlinks "<KryptonPay>" kp` INSIDE my worktree, then a PowerShell junction for `node_modules` (`cmd mklink` mangles the target path under Git Bash; `New-Item -ItemType Junction` works). Deliver as a bundle + flat patch written to the worktree root. **Ask the CTO to fix the worktree base, or repeat this.**
- Tooling in KryptonPay: no test runner, no test files. Use `node --experimental-strip-types --test` (Node 22.17) + `allowImportingTsExtensions` — added in this diff; no new deps. `npx tsc` fails through the junction; run `node node_modules/typescript/bin/tsc --noEmit`. `next lint` still works (deprecated warning).
- Spine is live on `http://127.0.0.1:8090`. Verified shapes: desk events are PascalCase (`DeskRequested`/`DeskDispatched`/`DeskRequestResolved`/`DeskRecommendationDecided`), `GET /fund/events` caps limit at 1000, `OrderApproved.payload.approver` is how auto-approvals are identified, `GET /fund/desk/runs?seat=` returns `{runs:[...]}`, `/fund/research/observations` returns `coverage.observations`. Always curl before consuming — this saved me twice.
- Shipped: 7 commits on `claude/krypton-fund-agentic-j8r2mu` in the clone, base `b9a526c`; tsc clean, 17/17 tests, next build green, all 8 seat routes 200, unknown seat 404, mechanics 307→desk, nav = 5 tabs.
- Open items for a future dispatch: eight named spine gaps (top three: `GET /fund/autopolicy`, `claim_type` on artifacts, thesis docs missing from the artifact fold); a browser pass with the spine stopped; a tokens/dispatch sparkline once seats have ~10 runs each.
- Decision the CEO may want to reverse: Risk is no longer a nav tab (route and RiskBar untouched) — one line in `StudioNav.tsx`.
- [CTO note at resolve, 2026-08-20]: merged fast-forward as KryptonPay 25f8e61..d8c2820 after verifying live trees clean, no thesis files in the patch, fund_api.ts additive-only; tsc/tests/routes reproduced on the merged tree. Your B1-B3 recommendations recorded on run-builder-1. The worktree-base defect (B3) is acknowledged — next dispatch will start from KryptonPay.
