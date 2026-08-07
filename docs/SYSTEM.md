# Krypton Fund — how the whole thing works

*A map across all four repos, the end-to-end trade lifecycle, what's real today, what's
still a gap, and how we keep it lean. Written 2026-08. Pairs with `architecture.md`
(spine internals) and `RUSHI_TESTING.md` (how to drive it).*

---

## 1. The four repos and who owns what

| Repo | Role | Language | Status |
|---|---|---|---|
| **ClarkHarness** (this repo) | **The spine.** Deterministic financial truth: event log, NAV/unit ledger, risk gate, order lifecycle, theses, memos, risk analytics, post-mortems, backtester, market data. Everything auditable is here. | Python / FastAPI | **Active — the core** |
| **Krypton_Clark** | **The brain.** Strands orchestrator + skills. Reasons in natural language, calls the spine's HTTP API, proposes orders behind the human-approval interrupt. Holds *no* financial truth. | Python / Strands | Active |
| **KryptonPay** | **The face.** Next.js app. `/clark` chat harness + `/clark/studio` Bloomberg-style cockpit. Talks to the spine (`/proxy/harness`) and to Clark (agents API). | Next.js / TS | Active |
| **Krypton_HedgeFund** | **Legacy web3.** Old on-chain vault + a lot of frontend logic. Being retired; web3 concerns move to **Krypton_Web3**. | Solidity / TS | **Freeze / retire** |

**The one rule that keeps this sane:** *deterministic financial truth lives only in
ClarkHarness.* Clark reasons and drafts; the spine decides what is true. If a number
must be auditable (NAV, a fill, a P&L, a thesis status), it is an **event** in the spine —
never state invented in Clark or the frontend.

```
        ┌──────────────┐   HTTP    ┌───────────────────────────┐
 chat → │ Krypton_Clark │ ───────→ │        ClarkHarness        │
        │  (the brain)  │          │         (the spine)        │
        └──────┬───────┘  propose  │  event log · NAV · risk    │
               │ interrupt         │  theses · memos · orders   │
   approval ───┘                   └─────────────┬─────────────┘
        ┌──────────────┐                         │ same HTTP API
        │  KryptonPay   │ ────────────────────────┘
        │  (the face)   │  Studio cockpit + Clark chat
        └──────────────┘
```

---

## 2. The trade lifecycle (the whole point)

This is the "AI researches → human decides → the log remembers" loop. Every arrow is an
event in the spine, so the audit trail is complete by construction.

```
 RESEARCH        THESIS            MEMO              ORDER            RISK GATE
 (Clark /   →   the falsifiable →  Clark's written → proposed vs   →  deterministic
  human)        idea + assets      case, conviction   thesis_id        pre-trade checks
                + invalidation     + recommendation                    (position/notional/cash)
                                        │                                    │
                                        ▼                                    ▼
                                  APPROVAL CARD  ──────────────────→  HUMAN APPROVES
                                  (thesis + memo shown)              (interrupt / cockpit)
                                        │                                    │
                                        ▼                                    ▼
                                   EXECUTION  ─── idempotent ───→  FILL → NAV moves
                                   (paper / Alpaca)                        │
                                                                          ▼
                                                                    POST-MORTEM
                                                          verdict vs prediction + realized P&L
                                                          → thesis: reviewed (terminal)
```

### What each stage *is*, concretely

- **Thesis** (`app/fund/thesis.py`) — a versioned, event-sourced investment idea:
  `title`, `claim` (falsifiable), `assets`, `invalidation_conditions`, `target_exposure_pct`.
  Lifecycle `draft → active → invalidated/exited → reviewed`. Orders link to it by
  `thesis_id`; memos and the post-mortem fold back onto it.
- **Memo** (`app/fund/memo.py`) — the written case Clark drafts *against a thesis*:
  `recommendation`, `conviction`, `summary`, and markdown `sections`. Draft → final
  (human sign-off). Rendered at the approval card so the human decides on the *argument*,
  not just the ticket.
- **Order** (`app/fund/pipeline.py`) — `propose → risk gate → approve → execute → poll →
  fill`. Carries `thesis_id` (or is explicitly `discretionary`). Order id doubles as the
  idempotency key, so retries never double-execute.
- **Risk gate** (`app/fund/risk.py`) — deterministic *enforcement* before a trade: position
  %, order notional %, cash buffer. Breaches → `OrderRejected`.
- **Risk analytics** (`app/fund/riskanalytics.py`) — read-only *situational awareness* for
  the cockpit: concentration (weights, HHI, largest position), cash buffer, breach flags,
  and scenario shocks ("what if AAPL −20%?"). Never writes events.
- **Post-mortem** (`app/fund/postmortem.py`) — grades the thesis (`correct / partially /
  wrong / invalidated / too_early`), derives *realized* P&L from the thesis's own fills
  (mark-to-market = net cash flow + net position × mark), and moves the thesis to
  `reviewed`. This is the reasoning dataset the fund learns from.

### Where each stage lives in the UI

- **Studio** (`/clark/studio`): Thesis panel (create → memo → status → post-mortem),
  Risk cockpit (concentration + shocks), approval card now renders thesis + memo, plus
  strategies / positions / LP book / NAV chart.
- **Clark chat** (`/clark`): drives the same flow in natural language — see §4.

---

## 3. Backtesting: old vs new flow

**Old (retired):** Clark's `backtest_service.py` + `lean_engine.py` POST to a remote
QuantConnect **LEAN CLI** on a now-decommissioned EC2 box. The hardcoded default
(`54.234.55.86:5000`) hung for the full timeout. We removed that default — LEAN only runs
now if you *explicitly* set `LEAN_CLI_ENDPOINT`.

**New (active):** the spine's built-in backtester
(`app/fund/backtest.py` → `signals_for()` + `SimpleBacktester`) over **free daily bars**
(`app/fund/marketdata.py`: Alpaca IEX when keyed, else Yahoo). Seven templates: `sma`,
`buy_hold`, `rsi`, `breakout`, `macd`, `bollinger`, `momentum`, `atr_trail`. Reached via:
- Studio → BacktestModal (visual template picker), or
- Clark chat → `backtest AAPL with rsi` (see §4), or
- API → `POST /fund/strategies/{id}/backtest/by_symbol`.

LEAN/Python authoring stays on the roadmap for when a strategy needs full-engine fidelity;
for the PoC the built-in backtester is the default and needs no Docker.

---

## 4. Driving it from Clark chat (deterministic NL)

The fund skill (`Krypton_Clark/app/skills/fund/implementation.py`) parses intent with
rules — provider-independent, so it works the same under Bedrock or local Ollama. Examples:

| You type | It does |
|---|---|
| `how's the fund` | NAV / cash / deployed / positions summary |
| `create thesis Long AAPL into services re-rate` | creates a thesis |
| `draft a memo for thesis <id>` | Clark composes a memo from the thesis, stores it (renders at approval) |
| `buy 10 AAPL thesis <id>` | proposes an order linked to the thesis → approval interrupt |
| `buy 5 NVDA for momentum` | proposes a discretionary/strategy-tagged order |
| `backtest AAPL with rsi` | runs the spine backtester on free bars |
| `show the risk` / `what if AAPL drops 20%` | concentration snapshot / scenario shock |
| `theses`, `pending`, `positions`, `strategies`, `lps` | reads |

Memo prose today is a **deterministic composition** from the thesis fields (honest first
cut). LLM-generated memo reasoning is the next enhancement (see ROADMAP).

---

## 5. What's real today ✅ vs gaps ⚠️

**Real & tested (54 spine tests green):**
- ✅ Event-sourced spine: NAV, unit ledger, positions, reconciliation.
- ✅ Order lifecycle with risk gate + human approval + idempotent execution.
- ✅ Paper venue (instant fills) **and** Alpaca (async fills at market open), persistent on real Firebase.
- ✅ Thesis / memo / risk-analytics / post-mortem — end-to-end, spine → Clark → Studio.
- ✅ Seven backtest templates over free bars; layered-cake nested strategies + NAV rollup.

**Gaps / not yet:**
- ⚠️ **LLM memo prose** — memos are composed deterministically, not reasoned by the model yet.
- ⚠️ **Clark's web-of-agents** — see §6; today it's one orchestrator + flat skills.
- ⚠️ **Evidence ingestion** (Firecrawl) and **conversational memory** (Zep/mem0) — staged, not wired.
- ⚠️ **On-chain tokenization** (Yearn-style ERC-4626 per-strategy NAV) — designed, parked (legal-gated).
- ⚠️ **Charts**: Studio + Clark portfolio/price charts are TradingView-style; the technical
  indicator sub-charts (RSI/Bollinger/etc.) are still plain recharts.
- ⚠️ **Krypton_HedgeFund** still contains legacy logic (and, per handoff, plaintext keys to scrub/rotate).

---

## 6. Keeping it lean & maintainable (the strategic questions)

**"The codebase is confusing across HF / Clark / harness / frontend — how do we stay lean?"**

Draw a hard line on responsibility and delete overlap:

1. **Spine = the only source of truth.** Anything auditable is an event here. Neither Clark
   nor the frontend recomputes NAV/P&L/positions — they *read* the spine. (Already true;
   keep enforcing it in review.)
2. **Retire Krypton_HedgeFund.** Move any live web3 concern to **Krypton_Web3**; freeze HF.
   Two active backends (spine + Clark) + one frontend + one web3 lib is the target shape.
3. **One API contract.** The spine's `/api/v1/fund/*` is the single interface. Clark's fund
   skill and the frontend's `fund_api.ts` are thin clients over it — no business logic in
   either. Adding a capability = one spine endpoint + one line in each client.
4. **Kill dead paths.** The QuantConnect/LEAN default was a dead EC2 that hung; removed.
   Sweep for others (old `run_local_fake`, unused crypto-portfolio backtest models).
5. **Tests are the contract.** 54 spine tests pin the truth. New aggregates ship with tests
   (thesis/memo/risk/post-mortem all did).

**"Clark's subagents aren't great — modernize the interplay with the harness."**

Today Clark is a single Strands orchestrator dispatching flat skills. The target (the
"web of agents complementing each part of the fund") is a small, *bounded* set of
subagents that all speak to the spine as their shared truth:

- **Researcher** — gathers evidence (Firecrawl/web), drafts a thesis + memo → writes to spine as *draft*.
- **Risk officer** — reads `/risk/analytics`, annotates a proposal with concentration/shock context before approval.
- **Execution/ops** — watches the pending queue and settlement; never approves (human-only).
- **Historian** — after exits, drafts the post-mortem from the thesis's fills for human confirmation.

Each is a thin reasoning layer whose *outputs are spine writes gated by the human*. They
coordinate through the event log, not through shared mutable state — same discipline as the
rest of the system. Build them one at a time behind the existing approval interrupt; don't
add an agent that can move money. This is the next major Clark workstream (see ROADMAP).

---

## 7. Run it

See `RUSHI_TESTING.md`. Short version:
- Spine on `:8090`, Clark on `:8000`, frontend on `:3000`.
- Persistent + instant fills: real Firebase + `ALPACA_API_KEY=` (empty) → paper venue.
- Ephemeral demo: `USE_FAKE_FIRESTORE=1`.
- Real paper orders (fill at market open): set real Alpaca keys.
