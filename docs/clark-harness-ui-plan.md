# Clark UI → the real harness — front-end plan

Turn the Clark app into **(a)** the operator's harness (Rushi runs the fund by
conversation, approves trades inline, sees live fund state) and **(b)** the LPs'
"understand your portfolio" view — all backed by the **ClarkHarness spine**
(`/api/v1/fund/*`) and the **orchestrator** (`krypton_clark`, via the existing
agents route).

This is an **augment, not a rebuild**: the chat, interrupt-approval modal,
devtools (agent-flow), and strategy UI shells already exist. The work is
repointing data at the spine and generalizing one modal.

---

## What already exists (this repo)

| Piece | File | State |
|-------|------|-------|
| Chat core | `src/app/clark/components/ChatInterface.tsx`, `src/lib/agents_api.ts` → `/api/v1/agents/query` | ✅ works (agents route proxies to orchestrator, 5-min timeout, retry) |
| Interrupt approval | `src/app/clark/components/InterruptModal.tsx` | ✅ but hardcoded to `krypton-pay-approval` |
| Agent-flow devtools | `src/app/clark/components/DevtoolsOverlay.tsx`, `src/app/clark/devtools/page.tsx` | ✅ renders `agent_flow` |
| Strategies UI | `src/app/customer/grow/hedge-fund/*` (StrategyCard, AddStrategyModal, TradingSignals, AUM chart, `useStrategiesWithMetrics`) | ✅ shells — but backed by the **old** data (`hedgeFundApi` → KryptonPay backend `/api/v1/strategies`, on-chain), **not** the spine |
| Proxy pattern | `next.config.ts` rewrites `/proxy/{main,web3,hedge}` (dev) + `NEXT_PUBLIC_*_URL` (prod) | ✅ mirror this for the harness |

## Target data flow

- **Conversation + orders (writes):** UI → `/api/v1/agents/query` → orchestrator →
  `consult_fund` skill → spine. When the skill proposes an order it raises
  `krypton-fund-order-approval`; the response comes back as `stop_reason:
  interrupt`, the UI shows the approval card, and approve/reject posts the
  `interruptResponse` (same path pay uses). The skill then calls the spine's
  approve endpoint, which executes.
- **Fund reads:** UI → `/proxy/harness/*` (dev) / `NEXT_PUBLIC_HARNESS_API_URL`
  (prod) → ClarkHarness `/api/v1/fund/*` (NAV, strategies, positions, LPs,
  pending queue, nav history).

## Changes by area

### 1. Plumbing (foundation)
- `next.config.ts`: add `{ source: '/proxy/harness/:path*', destination: `${harnessUrl}/:path*` }`
  where `harnessUrl = NEXT_PUBLIC_HARNESS_API_URL`.
- `src/lib/fund_api.ts` (new): axios client, base `/proxy/harness` (dev browser)
  / `NEXT_PUBLIC_HARNESS_API_URL` (prod), typed calls:
  `getNav()`, `getNavHistory()`, `getStrategies()`, `getPositions()`, `getLPs()`,
  `getLP(id)`, `getPending()`, and (optional, primary path is chat)
  `registerStrategy/deploy/setAllocation`, `approve/decline`.
- `.env` / deploy: `NEXT_PUBLIC_HARNESS_API_URL` (the ClarkHarness base URL).

### 2. Linchpin — generalize `InterruptModal.tsx`
- Widen the `Interrupt.reason` type to a union covering the order case:
  `{ symbol, side, qty, strategy_id, impact_preview: { notional_usd, cash_before, cash_after, quote_price } }`.
- Add a branch for `name === 'krypton-fund-order-approval'`: render a trade card —
  `BUY/SELL {qty} {symbol}` for `{strategy_id}`, notional, cash before→after —
  with Approve/Decline. Keep the pay branch unchanged. The `onApprove/onReject`
  plumbing already resumes the interrupt.

### 3. Repoint the strategies surface (`customer/grow/hedge-fund/`)
- Swap `hedgeFundApi` / `useStrategiesWithMetrics` for `fund_api.getStrategies()`:
  each card shows **state pill** (draft/backtested/deployed/paused),
  **target-vs-actual allocation bar**, exposure, and **P&L** (from attribution).
- NAV / AUM chart → `fund_api.getNavHistory()`.
- `AddStrategyModal` → `registerStrategy` (then backtest/deploy/allocate, or drive
  it through chat).

### 4. Operator cockpit surface
- A React operator view (embed in `/clark` or a new `/admin`) with the
  pending-approval queue, per-strategy cards, positions, and LP book — port the
  logic from ClarkHarness `web/ops.html` onto `fund_api`. (Short-term: iframe
  `/ops` from the harness.)

### 5. LP view
- The customer hedge-fund page becomes each LP's portfolio via
  `fund_api.getLP(lpId)` — value, gain/loss, units, ownership %, holdings,
  activity (port ClarkHarness `web/lp.html`). Map the Firebase auth uid → `lp_id`.

### 6. Agent-flow
- Devtools already renders `agent_flow`; just confirm `consult_fund` nodes appear.

## Operator vs LP

- **Operator (Rushi):** chat + inline approvals + the cockpit — full control.
- **LP (friend):** read-only portfolio (their `/fund/lp`); optionally a
  read-only "ask Clark about my portfolio" chat.

## Build order

1. ✅ **Plumbing** — `/proxy/harness` rewrite (`next.config.ts`) + `src/lib/fund_api.ts` + `NEXT_PUBLIC_HARNESS_API_URL`.
2. ✅ **Linchpin** — `InterruptModal` generalized to render `krypton-fund-order-approval` (order impact preview + Approve/Decline) alongside pay.
3. ✅ **Strategy Studio (operator)** — `/clark/studio` create → backtest → deploy → allocate on the spine.
4. ⬜ **Customer strategies view** → repoint `customer/grow/hedge-fund/` from `hedgeFundApi`/on-chain to `fund_api` (real state/allocation/P&L).
5. ⬜ **Operator cockpit** surface (or embed ClarkHarness `/ops`).
6. ⬜ **LP portfolio view** → `fund_api.getLP(lpId)` + **auth** (uid → lp_id) gating.

## Dependencies / gates

- **Auth** — LP scoping (each friend sees only their `lp_id`) and gating the
  operator cockpit is the hard gate before external LP links. Tracked in
  `ClarkHarness/docs/STATUS.md` (G4).
- Backend is ready: the interrupt protocol, `agent_flow`, and every `/fund/*`
  endpoint already exist and are tested in ClarkHarness.

## Verify (dev)

Run ClarkHarness (spine) + `krypton_clark` (orchestrator); set
`NEXT_PUBLIC_HARNESS_API_URL` (+ `NEXT_PUBLIC_AGENTS_API_URL`); `npm run dev`;
exercise: ask Clark for fund status → propose a trade → approve card → fill →
strategies/positions update; open the LP view for a seeded LP.
