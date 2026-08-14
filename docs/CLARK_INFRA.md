# Clark as the agentic team running the fund

Design note, 2026-08-14. Answers two questions: do we want CrewAI, and what does
the infrastructure actually look like.

---

## The short answer on CrewAI: no

Not because it is a bad framework, but because **we already have the thing it
would provide, and adding it would cost us the thing we actually care about.**

Clark today runs on **Strands** with an orchestrator that routes to specialised
agents — verified live, a single query produced `start → Krypton Orchestrator →
Finalise Agent`. That is already multi-agent orchestration. CrewAI would be a
second orchestration layer over the first.

The deeper reason is about where reasoning lives.

**The event log is the orchestration substrate.** Every state change in this
fund is an event: sequenced, actor-stamped, hash-chained, replayable. If an
agent's steps are events, we get audit, replay, idempotency and tamper evidence
for free, and "why did the fund do this in March" stays answerable in November.
If orchestration state lives inside CrewAI's memory instead, the ledger only
ever sees the output. **We would lose the "why" at exactly the point where
"why" is the entire product.**

CrewAI's delegation is also emergent by design — agents decide among themselves
who handles what. That is a feature for a research assistant and a liability
for a fund, where "which agent decided this, on what basis, at what time" has
to be reconstructible rather than reverse-engineered.

**What we need instead is roughly 300 lines**: typed tools over the spine, an
agent loop that calls them, and agent steps recorded as events. Sub-agents stay
— a risk critic, a researcher, a memo writer — but as prompted roles with
scoped tool sets, composed in plain code that can be read and tested.

---

## The principle everything else follows from

> **Deterministic where money moves. Agentic where judgment happens.**

The benchmark made this concrete. Asked "what is the fund's NAV and are there
active alarms", three different models — qwen2.5:14b, gemma4:12b, gemma4:26b —
returned **byte-identical answers**:

```
NAV $2,027.60: 3 positions, cash 43%, HHI 4474. Largest INTC 35%.
Flags: INTC is 34.6% of NAV (> 25% guideline).
Stress: market -10% → $-116.46 (-5.7%); market -20% → $-232.92
```

They were identical because the **fund skill computed all of it**. The model
routed; it did not do arithmetic. That is the right split and it should be
preserved deliberately: NAV, HHI, stress and limits are computed by code that
is tested, and no model is ever asked to calculate a number that decides
anything.

The model's job is to choose the right tool, read the result, and explain it.

---

## Layers

```
  Operator
     │  asks, approves, declines
     ▼
┌──────────────────────────────────────────────────────────┐
│  ClarkConsole (KryptonPay)          ← UX only            │
│  docked panel, live context, shows what Clark was told   │
└──────────────────────────────────────────────────────────┘
     │  /api/v1/agents/query
     ▼
┌──────────────────────────────────────────────────────────┐
│  Krypton_Clark (Strands)            ← judgment           │
│  orchestrator → specialised agents → skills              │
│  LLM: Ollama local (qwen2.5:14b) | Bedrock in prod       │
└──────────────────────────────────────────────────────────┘
     │  typed tools, HTTP
     ▼
┌──────────────────────────────────────────────────────────┐
│  ClarkHarness spine                 ← truth              │
│  event log · projections · risk gate · compliance gate   │
│  DETERMINISTIC. No model input reaches this layer's      │
│  arithmetic or its gates.                                │
└──────────────────────────────────────────────────────────┘
     │
     ▼  Alpaca (paper)
```

The console is a **UX layer over the agent**, exactly as you framed it — and it
matters that it is only that. Anything Clark does must be visible in the ledger
and on Monitor, not only in a chat transcript. A reasoning trace that exists
solely in a chat window is not an audit trail.

---

## Tool boundary

Three tiers, and the split is the safety mechanism.

| Tier | Tools | Writes? |
|---|---|---|
| **read** | nav, positions, risk, tca, executions, signals, session, compliance, ledger/verify, fees | never |
| **research** | backtest, evaluate, tearsheet, optimise | never touches the book |
| **propose** | `propose_order` — **and nothing else** | one event: `ORDER_PROPOSED` |

Clark never gets `approve_order`, `set_risk_limits`, `halt`, `resume`,
`set_fee_terms`, or any capital event. Those are the operator's, permanently.

A Clark proposal goes through **the same risk and compliance gates as
everything else** — the PDT check, the concentration cap, the cash floor. It
lands in the approval queue looking like any other proposal, tagged with its
reasoning. It is not privileged for having come from an agent.

---

## Human-in-the-loop, precisely

Not everything needs a human, and pretending it does trains the operator to
click through.

**No human — Clark acts freely**
Reading, analysing, backtesting, drafting memos, writing observations,
answering questions, flagging anomalies.

**Human required, blocking — nothing proceeds without a click**
Any order. Any risk-limit change. Halt or resume. Fee terms. Any capital event
(subscription, redemption, payout). Anything that moves money or changes the
mandate.

**Human notified, non-blocking**
Alarms, cost anomalies, strategy-decay flags, reconciliation drift. These
inform; they do not wait.

The gate that already exists — `propose → approve → execute` — is the whole
mechanism. Clark plugs in at `propose` and stops.

---

## What is missing

Three things, in order.

**1. Agent actions as events.** New types: `AGENT_RUN_STARTED`,
`AGENT_OBSERVED`, `AGENT_PROPOSED`, `AGENT_RUN_FINISHED`, each carrying the
reasoning. This is what turns a chat transcript into an audit trail, and it is
the prerequisite for everything else. Without it, Clark's reasoning is
invisible to the ledger, to reconciliation, and to anyone reviewing the fund
later.

**2. A typed tool layer.** Clark reaches the spine through `app/skills/fund/`
and `app/skills/backtest/` today. Those need to become an explicit, versioned
tool surface split along the read/research/propose tiers above, so "what can
Clark do" is a list someone can read rather than a property of whatever the
skill happens to import.

**3. The memo at the approval card.** This is where Clark earns trust and it is
already half-built: the thesis/memo/postmortem backend works end to end and has
no UI (see task #13). Clark drafts the written case; the operator reads it
beside the numbers and decides. That is the review loop, and it is worth
building before Clark proposes anything.

---

## Sub-agents worth having

Composed in code, not emergent. Each is a prompt plus a scoped tool set.

- **Analyst** — read tools. Explains the book, answers the operator.
- **Risk critic** — read tools, adversarial prompt. Its job is to argue against
  a proposal, not to produce one. Run it on every proposal before it reaches
  the queue.
- **Researcher** — research tools. Backtests an idea, reports honestly
  including when the idea fails.
- **Memo writer** — thesis/memo tools. Writes the case a human will review.
- **Watcher** — read tools, on a schedule. Flags what numeric limits miss.

The risk critic is the one most worth having early: a second agent whose only
incentive is to find the flaw is the cheapest check available, and it costs a
prompt.

---

## Model choice

Measured on this machine (RTX 4090, 22.5 GiB), same queries through Clark:

| Model | Size | Simple | Tool query | Notes |
|---|---|---|---|---|
| **qwen2.5:14b-instruct** | 9.0 GB | 1s | 4s | fastest, currently configured |
| gemma4:12b | 7.6 GB | 9s | 5s | tools + thinking + vision |
| gemma4:26b | 18.0 GB | 34s | 5s | 34s was model load |

**Identical answers from all three**, because the skill did the work. The extra
9 GB gemma4:26b costs buys nothing on this path.

**Caveat worth stating**: this tested a single-hop route. The differences will
show up on the things not yet built — multi-step tool chains, choosing between
several plausible tools, writing an investment memo. Re-run this comparison
when the memo writer exists, because that is a reasoning task and this was not.

Do NOT use the qwythos models: they report `completion` only, no tool calling,
so Strands would fail on them.

---

## Order of work

1. Agent events (`AGENT_*`) — makes everything after this auditable
2. Typed read tools — Clark answers without a hand-built context block
3. Memo at the approval card — the review loop, before any proposing
4. Risk critic sub-agent — adversarial check, cheap
5. `propose_order` — one write tool, fully gated
6. Watcher on a schedule — last, because it is only useful once its
   observations can be explained and trusted

Steps 1–3 involve **no write capability at all**. By the time Clark can propose
anything, its reasoning will have been read at the approval card dozens of
times. That is the point of the ordering.
