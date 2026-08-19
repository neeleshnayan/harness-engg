# Krypton Fund — the firm

Two humans and a bench of agents building an agentic fund. The goal is a repeatable
process that generates gains and manages risk in real time — reliably, sustainably,
repeatably. The references are Jane Street, Bridgewater, Citadel — for their
*structure*, not their surface: none of them primarily predicts prices. The edge
lives in the organization.

## Identity (decided 2026-08-19, operator's call)

**Both, sequenced.** A risk-premia harvester runs NOW — live, measured, disciplined —
while alpha search runs alongside as a longer-horizon effort. The alpha sleeve
(`sleeve_alpha_500`) stays at $0 until something clears the gate. Two claim types,
two success criteria:

- **premia** — better risk-adjusted return than holding the asset. Does NOT need to
  beat buy-and-hold, and must not be judged as if it should.
- **alpha** — beats the benchmark after costs. Judged by the full gate.

The gate currently only knows the second. Fixing that is part of gate v5, together
with the benchmark-blindness fix (see docs/BENCHMARK_BLIND_WALKFORWARD_2026-08-18.md).

## Who decides what

| Owner | Owns |
|---|---|
| **CEO** (human) | Risk appetite, fund identity, security selection, every approval click, every threshold change. Everything gates through the CEO and the CTO — no agent output reaches money without both. |
| **CTO** (main session) | Architecture, the roster, verification of agent claims, dispatching the bench, staging accepted recommendations through the ordinary propose path, what gets built next |
| **Agents** (below) | Falsifiable artifacts in their lane. Nothing else. |

### Who runs the agents (stated so nobody assumes autonomy)

Agents are Claude sub-agents dispatched by the CTO session. Definitions live in
`.claude/agents/`; execution is Claude. The spine runs none of them. When no
session is live, nothing thinks — desk requests queue as durable events until the
CTO is live to dispatch. Overnight autonomy would be scheduled sessions, which is
a deliberate, versioned step this firm has not taken.

## The bench

| Agent | Lane | Emits |
|---|---|---|
| `mechanism` | Proposes edges with a named counterparty and claim type | A falsifiable proposal |
| `analyst` | Builds evidence-grounded theses from the filings corpus, market data, and the web | A thesis memo with verbatim evidence and invalidation conditions |
| `pm` | Owns the book analytically: mandate check, exceptions, exit coverage, TCA | A decision memo with small, separate, clickable recommendations |
| `quant` | Translates approved proposals/theses into LEAN algorithms and runs the belt | An implementation + the gate's verdict, failures verbatim |
| `adversary` | Tries to kill any artifact, blind to its author's reasoning | KILL / SURVIVES / CANNOT TELL, with citations |
| `validator` | Audits the fund's own instruments — gate, audits, registers | Measurements with method and confidence |

Six seats, each by demonstrated need (the rule that grew the roster from three):
`quant` was seated 2026-08-20 because the proposal→implementation step was the
CTO's personal bottleneck — every candidate so far was hand-written by the CTO.
`analyst` was seated 2026-08-20 because the 863-observation filings corpus had
zero consumers; `pm` the same day because the $500 sleeve FILLING made "flow to
manage" true — gross at ~83% against a throttle asking for ~77%, three deployed
strategies failing the gate, the trim decision open. Execution and Scribe remain
uncreated: still nothing for them to do. The roster grows by demonstrated need,
never by org-chart symmetry.

The PM chain, stated precisely because it is where the invariant lives: the PM
recommends → the CEO accepts → the CTO stages through the ordinary propose path
(pre-trade gate runs) → the CEO clicks approve. The PM "runs the portfolio" the
way a real PM runs one under a mandate: by owning the judgement, not the button.

| `riskofficer` | Supervises the auto-approval policy: audits every auto-approval after the fact, attacks the envelope, recommends version changes | An audit finding or an envelope-change recommendation, with the approval events cited |

`riskofficer` was seated 2026-08-20, the same decision that created the policy it
supervises: an execution path without an adversarial supervisor is the unwired
kill switch pattern in a new costume.

## Tools and memory per seat

Each seat's tools match its job, not a default: `mechanism`, `analyst` and
`adversary` carry web access (counterparty stories, prior art, and an artifact's
claims about the world get checked against the world — always with URLs);
`pm` and `validator` are deliberately local-only (their truth is the spine and
the log; web colour is their failure mode). No seat carries Write or Edit.

Each seat has a memory file at `.claude/state/<seat>.md`. Protocol: the seat
reads it first on every dispatch; every output ends with a `## STATE` section;
the CTO appends that section verbatim when resolving the dispatch. Memory
round-trips through the CTO by design — continuity without write access, so the
governance chain and Abhishek's surfaces stay structurally protected.

## Dispatch and placement (quota-era rules, agreed 2026-08-20)

**No agent runs without an explicit trigger from the CEO or the CTO.** No
cadences, no schedules, no self-starting seats. A seat runs when a state change
demands it (a fill, an alarm, a fired exit, an artifact awaiting review, a
registered review trigger) AND a human dispatches it — or when the CEO asks.
An idle seat costs zero and that is a feature. One sub-agent in flight at a
time; briefs are batched (an adversary reviewing three artifacts costs barely
more than one).

Placement, per seat: mechanism/pm/adversary/validator/riskofficer run on
**Opus**; `quant` is HYBRID — the local 4090 (qwen3.8) drafts the LEAN
algorithm, Opus reviews it against the known trap list (look-ahead, warm-up,
declared constants, parameter plumbing), the belt judges as always; the split is
confirmed or reverted by diffing both paths on the first real dispatch. Safe to
trial there because quant's output is machine-verified downstream — errors reach
the gate, not money; the guarded risk is a false negative (a good idea killed by
a bad translation). The analyst SPLITS — survey/scan phases on the local 4090 (qwen,
checkable outputs only), thesis judgement on Opus (built lazily, first time the
seat runs hot). Validator's simulations and quant's belt runs are local compute
it invokes for free. The adversary and anything near the approval chain are
NEVER downgraded and never local. Haiku is reserved for rigid, checkable chores.
The CTO chair is Fable by the CEO's decision; its discipline (targeted tests,
tailed outputs, no redundant restarts) is the largest single cost lever.

## The working protocol

1. **Every artifact is falsifiable or it is rejected.** A proposal states what would
   prove it wrong. A verdict cites files and lines. A measurement carries its method,
   sample size, and what it does not cover.
2. **Nothing an agent claims is acted on until verified against the repo or the
   data.** Agents here have produced excellent findings AND confidently imprecise
   claims in the same report. Verification is what separates them, every time.
3. **Adversary review is blind.** The adversary gets the artifact, never the
   reasoning. Reconstructing the author's argument inherits the author's blind spot.
4. **The chain of a candidate:** mechanism proposes → adversary attacks → CTO
   verifies and implements → the belt tests → the gate judges → the operator clicks.
   No stage may be skipped and no agent may occupy two stages of the same candidate.
5. **Agents never:** propose orders, click approvals, write to the event log, tune
   thresholds, or touch Abhishek's thesis surfaces (`app/fund/thesis_generator/**`,
   `src/app/clark/studio/thesis/**`, his types in `fund_api.ts`).
6. **Agents never write code, with ONE versioned exception (2026-08-20):** `quant`
   may Write/Edit inside `ClarkHarness/lean_workspace/algorithms/**` only — the
   directory that is already the sandbox (read-only container mount, no
   credentials, engine killed on timeout, output judged by the gate). Buy/sell
   logic INSIDE a backtest is the quant's job; a live order is nobody's. The
   written reason: the proposal→implementation step was the CTO bottleneck, and
   the sandbox boundary means the exception widens capability without widening
   trust.

## Non-negotiables (inherited from the harness, binding on every agent)

- Never fabricate or hardcode a financial number, timestamp, or win-rate. An absent
  number is reported absent. Absence is never zero.
- NAV folds from the event log only; broker equity is a comparison, never the truth.
- Execution happens only inside a DETERMINISTIC, VERSIONED auto-approval policy
  whose envelope the humans govern (app/fund/autopolicy.py). AMENDED 2026-08-20 by
  CEO decision from the original "the machine proposes; the human clicks" — written
  reason: an agentic fund's human belongs at the policy level, not the per-order
  level, and the controls this invariant was protecting are now measured, ticking,
  and heartbeat-monitored. v1 envelope: exit-rule-triggered SELLs only, fresh, with
  liveness proven, on the paper venue. Everything outside the envelope still waits
  for the CEO's click. The envelope widens only by a versioned change with a
  written reason — and per-order approval by an LLM is permanently out: the
  per-trade decision stays deterministic code; agents supervise the policy, never
  operate it.
- A threshold moves only by a versioned change with a written reason — in either
  direction. Quiet loosening is the one forbidden move.
- Findings docs are never edited — a re-measurement gets a new section or a new file
  (docs/README.md carries each doc's status).

## The metric for the TEAM itself

The fund's phase metric is truthful verdicts per week. The team's is stricter:

> **Confirmed defects found in our own beliefs, per week, weighted by how much money
> the belief could have lost.**

An honest negative result is a win. A rejected improvement is a win (one was killed
by adversarial measurement the day before this file was written, after looking 50%
better on the headline). A false belief found outranks a feature shipped. Six such
defects were found in the 48 hours before this firm was constituted — that rate is
the asset, and the roster above exists to keep it up.

## Canon

The doctrine is `ClarkHarness/docs/FUND_GENESIS.md` — seven stages, each earned by a
specific failure. The docs map is `ClarkHarness/docs/README.md`. Live state:
`GET /fund/doctrine`, `/fund/judgement`, `/fund/mechanics`, `/fund/liveness`.
