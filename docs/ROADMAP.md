# Krypton Fund — roadmap

*What's next after the thesis → memo → risk → post-mortem slices landed (2026-08).
Ordered roughly by leverage. Pairs with `SYSTEM.md` (how it works today).*

---

## Near-term (harness + Clark)

### 1. LLM-reasoned memos
Today `draft_memo` composes a memo deterministically from the thesis fields. Next: the
orchestrator LLM drafts the *reasoning* (valuation, catalysts, risk weighing) into the
memo `sections`, still stored on the spine and human-signed at the approval card. The
storage/lifecycle is already built — this is a prompt + a call, not new plumbing.

### 2. Clark's web of agents (the big one)
Replace the single orchestrator + flat skills with a small, bounded set of subagents that
share the spine as their only truth (see `SYSTEM.md` §6):
- **Researcher** → drafts thesis + memo (evidence-backed).
- **Risk officer** → annotates proposals with concentration/shock context from `/risk/analytics`.
- **Ops** → watches pending queue + settlement (never approves).
- **Historian** → drafts post-mortems from a thesis's fills.

Discipline: agents coordinate through events, not shared state; **no agent can move money** —
every write is human-gated by the existing approval interrupt.

### 3. Evidence + memory
- **Firecrawl** → ingest research into an Evidence object linked to a thesis (`evidence_ids`
  already exists on the thesis).
- **mem0 (already wired) → Zep only if needed** → *conversational* memory only. Never let
  memory hold financial truth; that stays in the event log.

---

## Alpaca is the whole data+execution+backtest stack

Confirmed direction: **Alpaca replaces the separate LEAN + IBKR split.** One integration
gives us free IEX bars (data), paper + live execution (broker), and enough history to
backtest — so we don't run a LEAN engine *and* an IBKR connector.

- Today: `AlpacaConnector` (execution) + Alpaca/Yahoo bars (data) + spine `SimpleBacktester`.
- Keep LEAN **optional and explicit** (`LEAN_CLI_ENDPOINT`) only if a strategy ever needs
  full-engine fidelity (options, tick data, complex portfolio rebalancing). For the PoC and
  equities momentum/technical strategies, Alpaca end-to-end is enough.
- **Features we're knowingly deferring** with Alpaca-only (fine for now): options/derivatives,
  sub-daily/tick backtests, non-US venues, and LEAN's rich analytics. Revisit only if a
  strategy demands it.

---

## Tokenization (parked — legal-gated, PoC-first)

Yearn-style per-strategy tokens, **Option B**: reuse existing web3 infra rather than build new.
- **v1 (off-chain, buildable now):** per-strategy NAV + units already roll up in the spine
  (layered cake). Expose a "strategy token" view: pricePerShare = strategy NAV / units.
- **v2 (on-chain, gated):** ERC-4626 vault in **Krypton_Web3** whose `pricePerShare` oracle
  reads the spine's struck NAV; the old **Krypton_HedgeFund** vault retires into this.
- Truth stays in the spine; the chain mirrors it. Do not let on-chain state become a second
  source of truth.

---

## What to "steal" from the many-agents agentic-fund pattern

*(General patterns worth adopting — not sourced from any specific private write-up.)*

- **Agent registry + scorecards** — treat each agent like a strategy: track its proposals,
  hit rate, and P&L attribution. The post-mortem dataset we're building is exactly the
  substrate for this.
- **Hard human seam + kill switch** — one place agents can be paused globally; no agent path
  that executes without human approval. (We have the approval interrupt; add a global pause.)
- **Everything through the event log** — agents never share mutable state; they read/write the
  spine. This is what makes 4 agents — or 250 — auditable instead of chaos.
- **Per-agent risk budgets** — extend the `RiskGate` so each agent/strategy has its own
  position/notional caps, not just fund-level limits.
- **Cheap, boring orchestration** — deterministic dispatch + typed tool calls over the spine
  beats a clever emergent swarm for anything touching money.

---

## Cleanup / hygiene (ongoing)

- Retire **Krypton_HedgeFund**; move live web3 to **Krypton_Web3**. Scrub the plaintext
  private keys flagged in its README and rotate them.
- Sweep Clark for dead crypto-portfolio/LEAN code paths now that backtests run on the spine.
- Port the TradingView area style to Clark's technical sub-charts (RSI/Bollinger/etc.).
- Keep the "one spine endpoint + thin clients" rule — no business logic in Clark's skill or
  the frontend's `fund_api.ts`.
