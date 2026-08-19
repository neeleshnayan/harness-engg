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
| **Operator** (human) | Risk appetite, fund identity, security selection, every approval click, every threshold change |
| **CTO** (main session) | Architecture, the roster, verification of agent claims, what gets built next |
| **Agents** (below) | Falsifiable artifacts in their lane. Nothing else. |

## The bench

| Agent | Lane | Emits |
|---|---|---|
| `mechanism` | Proposes edges with a named counterparty and claim type | A falsifiable proposal |
| `adversary` | Tries to kill any artifact, blind to its author's reasoning | KILL / SURVIVES / CANNOT TELL, with citations |
| `validator` | Audits the fund's own instruments — gate, audits, registers | Measurements with method and confidence |

Deliberately three, not six. Risk, Execution, and Scribe roles get created when there
is flow to manage — a role with nothing to do decays into ceremony. The roster grows
by demonstrated need, never by org-chart symmetry.

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

## Non-negotiables (inherited from the harness, binding on every agent)

- Never fabricate or hardcode a financial number, timestamp, or win-rate. An absent
  number is reported absent. Absence is never zero.
- NAV folds from the event log only; broker equity is a comparison, never the truth.
- The machine proposes; the human clicks. The moment an agent path executes a trade,
  every claim this system makes about itself stops being true.
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
