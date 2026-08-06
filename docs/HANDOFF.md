# Krypton Fund — Handoff

Read this first. It's the cross-repo summary of what was built, where it lives,
what's verified, and what's left — enough to continue the work (locally or in a
fresh session) without the original chat history.

**Everything is on branch `claude/krypton-fund-agentic-j8r2mu` in each repo.**

## What this is

A "Claude Code for the fund": an agentic harness for a pooled, multi-strategy
managed fund (v0 = 20 friends & family, ~$100 each). Rushi runs the fund by
talking to Clark and approving every trade; LPs get a read-only portfolio view.
The AI orchestrates and proposes; a human approves; a deterministic spine
executes and keeps an immutable audit trail. Money moves off-platform (no
payments/custody surface in v0).

## Repos & roles (branch: `claude/krypton-fund-agentic-j8r2mu`)

| Repo | Role | State |
|------|------|-------|
| **ClarkHarness** | the fund **spine** (event store, connectors, projections, risk, pipeline, ledger, reconciler, scheduler) + LP view + operator cockpit + all docs | built, 27 tests green |
| **Krypton_Clark** | the **brain** (strands orchestrator); the `fund` skill talks to the spine | built, 4 tests green |
| **KryptonPay** | the **Clark UI** (Next.js): chat, approval modal, Strategy Studio, fund client | Studio + approval modal built; customer/LP views pending |
| **Clark_MCP** | thin MCP proxy to the brain (`krypton_query`, `krypton_approve_interrupt`) | unchanged — the generic approve tool already resumes fund-order interrupts |
| KryptonPay_Backend | payments product | spine removed; out of scope for the fund |
| quantconnect | old LEAN/Yearn rig | superseded (see D11); not rebuilt |

## The architecture in one line

`Command → Risk gate → Human approval → Connector → Event log → Projections`.
The event log is the single source of truth; NAV, the unit ledger, positions,
per-strategy attribution, and the audit trail are all projections folded from it.
Full design in [`architecture.md`](./architecture.md); decisions D1–D11 and the
gap analysis in [`STATUS.md`](./STATUS.md).

## What's built & verified

**ClarkHarness (`app/fund/`, `/api/v1/fund/*`)**
- Append-only event store (Firestore, global seq) — the audit trail.
- Money is **Decimal** end-to-end (exact; strings in Firestore; float only at the JSON edge).
- Venue-agnostic `Connector`: `PaperConnector` (default) + `AlpacaConnector`
  (env-selected; venue-side idempotency via `client_order_id`; price cache).
- Projections: positions/cash/units, NAV (`compute`/`strike`/`history`), per-LP
  holdings, per-strategy attribution, orders (pending + in-flight).
- Risk gate (position/notional/cash-buffer limits, duplicate guard).
- Command pipeline: propose → risk → **human approval** → idempotent execute →
  **async settlement** (partial/fill/fail) → events.
- Unit ledger: subscribe/redeem, two-phase confirm, **non-diluting** (proven).
- Reconciler (event book vs. venue) + a guarded lifespan scheduler
  (settle ~30s, strike NAV + reconcile ~30min).
- Strategy registry (event-sourced lifecycle) + `SimpleBacktester` (no LEAN).
- LP view `GET /lp`, operator cockpit `GET /ops` (both read `/fund/*`).

**Krypton_Clark** — `app/skills/fund/` (auto-discovered `consult_fund`): reads
status/strategies/positions/LPs/pending, manages strategy lifecycle, and proposes
orders through the same human-approval interrupt as `krypton_pay`
(`krypton-fund-order-approval`).

**KryptonPay** — `fund_api.ts` + `/proxy/harness` rewrite; **Strategy Studio**
`/clark/studio` (create → backtest → deploy → allocate); **InterruptModal**
generalized so chat orders render an inline Approve/Decline card.

Tests: `pytest` in ClarkHarness (27) and `tests/test_fund_skill.py` in
Krypton_Clark (4) — all green. Frontend verified by convention/compile; run
`npm run build`.

## Run it locally

See [`LOCAL_E2E.md`](./LOCAL_E2E.md). Tier 1 (spine + frontend) exercises the whole
fund loop; Tier 2 adds the orchestrator for chat. To go live on Alpaca paper, see
[`DEPLOY.md`](./DEPLOY.md).

## Remaining backlog (priority order)

1. **Auth** — `/fund/lp/{id}`, the cockpit, and write routes are open. The hard
   gate before any external LP link.
2. Repoint KryptonPay's **customer strategies** + **LP portfolio** views to the
   spine (Studio + approval modal already done).
3. Alpaca **historical bars** into `backtest/run` (prices are client-supplied now).
4. **CI** for the test suites; open **PRs** from the branch (none opened yet).
5. quantconnect-v2 **signal adapter** (deployed strategy → POST proposed order).
6. Tune `RiskLimits` (a non-zero cash buffer) before real sizing.

## Key decisions (see STATUS for the full log)

Pooled custody + off-platform deposits · Alpaca over IBKR (API-first, no gateway)
· connector-owned execution (human-approval seam) · Strands for the *episodic*
brain, deterministic workers for 24×7 · multi-strategy as tags on one pooled
account · no LEAN in v0 (Backtester seam) · Decimal money · legal is a parallel,
non-blocking workstream.
