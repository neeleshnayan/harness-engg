# The docs, and which of them you can trust

Twenty-five documents accumulated in five days with no map, which is its own kind
of debt: a reader cannot tell a live specification from a one-off note written for
a Thursday that has already passed. Worse, several are *dated snapshots* whose
numbers were true when written and are not true now.

So every entry below carries a **status**, and the statuses mean specific things:

| status | means |
|---|---|
| **canon** | Current. Written to be maintained. If it disagrees with the code, that is a bug in one of them and worth resolving. |
| **finding** | A measurement, valid *as of its date*, kept as evidence. Never updated — a re-measurement gets a new document, because editing a finding destroys the record of what we believed and when. |
| **runbook** | Steps to follow. Rots quietly, so check it against reality before trusting it. |
| **spec** | Written to hand work to somebody. Historical once the work lands. |
| **snapshot** | True on its date, almost certainly stale now. Kept for the trail. |
| **owned** | Somebody else's. Do not edit. |

Nothing here is deleted on age alone. A superseded document is evidence about how
the fund's thinking moved, and this project has already learned the hard way that
absences are expensive — but an unlabelled stale document is a trap, so the label
is the fix rather than the bin.

---

## Start here

| doc | status | what it is |
|---|---|---|
| [FUND_GENESIS.md](FUND_GENESIS.md) | **canon** | **How this fund decides it is allowed to believe something.** The seven-stage workflow, each stage earned by a specific failure. Read this first; it explains why everything else is shaped the way it is. |
| [SYSTEM.md](SYSTEM.md) | canon | How the whole thing works, end to end. |
| [architecture.md](architecture.md) | canon | The harness architecture — event spine, projections, connectors, pipeline. |
| [ROADMAP.md](ROADMAP.md) | canon | What is built, what is next, and what was deliberately deferred. |

## The mandate and the money

| doc | status | what it is |
|---|---|---|
| [SLEEVE_500_FRAMEWORK.md](SLEEVE_500_FRAMEWORK.md) | **canon** | Deploying $500 end to end: the pre-registration, the σ-sized stops, the four falsification conditions, the measured instrument shortlist, and the unfunded alpha sibling. Carries dated **strike-through corrections** where earlier claims turned out false — read those, they are the most instructive part. |
| [REORIENT_DECISION_2026-08-17.md](REORIENT_DECISION_2026-08-17.md) | finding | The evidence for re-orienting the book, and what was left to the operator. |
| [BOOK_SEPARATION.md](BOOK_SEPARATION.md) | canon | Keeping the real book apart from staging. |

## Calibration — what the instruments can actually see

These are the fund's most load-bearing measurements. All **findings**: valid as of
their dates, never edited.

| doc | status | what it measured |
|---|---|---|
| [reviews/ADVERSARY_GATE_V5_R3_2026-08-20.md](reviews/ADVERSARY_GATE_V5_R3_2026-08-20.md) | **kill — third in the v5 chain** | Round 3 died on: a fair-priced short-vol null clearing the premia rule at 72–86% vs 12% TP (Sharpe's negative-skew failure, absent from the null battery); a fixed-vs-scaled fold table that compared a rule with itself (seed noise as findings); and with the belt's 20.8% unmeasurable-fold rate injected, the fixed floor loosens with history exactly as the register feared. Generator corrections survive; history extension stays blocked. |
| [GATE_V5_ROUND3_2026-08-20.md](GATE_V5_ROUND3_2026-08-20.md) | **design — KILLED** | The rebuilt audit (noisy nulls, grid-max, history sweep) and the criteria proposed from it. §1's model validation (v4 21–30% vs belt 25%) holds; the criteria and §5's sequencing were killed same-day. |
| [AUDIT_R6_D2_ATTRIBUTION_2026-08-20.md](AUDIT_R6_D2_ATTRIBUTION_2026-08-20.md) | **audit — recommendations awaiting CEO** | Validator batch: min_effective_bets sound (it is exactly a correlation floor, 0.23 bets of headroom); max_risk_concentration_pct inverted (accident scores better than health — retire/re-specify); NEITHER threshold gates anything; register review_trigger column write-only; entry-11 P1 REFUSED structurally (paper venue fills at its own quote — zero cost information at any n); the ±$174.47 phantom is one mistagged GLD fill that rebalance/preview turns into a real $376.84 order. TCA verdict leg fixed by the CTO same hour. |
| [GATE_V5_ROUND4_2026-08-20.md](GATE_V5_ROUND4_2026-08-20.md) | **design — awaiting blind adversary round 4** | One answer per round-3 kill ground: vol-matched paired MPPM (ρ=5, margin 2%/yr) with a variance-ratio CANNOT-TELL guard; measurability per retention() + the belt's 20.8% dropout (fixed/scaled arms finally differ — fixed floor FPR 7→34% with depth, the register's defect measured live); drift class max 7.1%; claim-type taxonomy. At 10y: premia FPR 3.6% / TP 42.1% / break-even prior 8.0% (killed Sharpe rule: 25.0% / 5.4% / 82.2%). Names its own new hole: v5_alpha passes the slow-bleed seller 46.9% at depth. |
| [research/FUNNEL_2026-08-20.md](research/FUNNEL_2026-08-20.md) | **operating doc** | The generation machine: weekly candidate cycle (mechanism batch → analyst sweep → adversary batch → quant belt), throughput target 3–5 entrants/week, prerequisites owned by the CTO (10y bar backfill — measured free, gate v5 round 3, local survey phase, corpus cadence, factor pack). Updates itself with measured base rates per cycle. |
| [research/PREMIA_MENU_2026-08-20.md](research/PREMIA_MENU_2026-08-20.md) | **register — versioned** | The standing top of the funnel: 12 premia entries, each with economic reason, counterparty, instruments, testability on our history, and chain status. Generation as coverage, not creativity. |
| [research/REVIVAL_REGISTER.md](research/REVIVAL_REGISTER.md) | **register — appended** | Killed work kept warm: VRP (3 conditions, dormant until gate v5) and SRPT (dated catalyst: Q3 ELEVIDYS print vs $75M, Nov 2026 tickler). |
| [AUDIT_AUTOPOLICY_V1_FIRST_FIRE_2026-08-20.md](AUDIT_AUTOPOLICY_V1_FIRST_FIRE_2026-08-20.md) | **audit — riskofficer's first** | The auto-policy's only live fire, audited from the complete log: all 7 recorded checks were factually TRUE (the policy was correct about a false world); the CTO's fix was incomplete (seeds fabricated SPY/NVDA marks in the same incident — fixed same day); the "pre-committed" premise was false for this order; the marker is forgeable (demonstrated offline, risk-gate-bounded); halt latency 14m41s, not seconds. Envelope v2 (R1–R7) on the desk. |
| [INCIDENT_GLD_PHANTOM_PRICE_2026-08-20.md](INCIDENT_GLD_PHANTOM_PRICE_2026-08-20.md) | **incident — root cause fixed; §2 corrections from the audit** | The fund's first auto-approval fired on a fabricated $100.00 mark (`_DEFAULT_PRICE` in the paper connector): phantom −75% on GLD → machinery-test exit fired → auto-policy approved → fill at $100 → −$133.21 → daily-loss halt. Every control worked on a poisoned input; the default is deleted and absence now raises. PM's R4 had flagged the firing rule hours earlier. |
| [MIN_TRAIN_RETURN_REVIEW_2026-08-20.md](MIN_TRAIN_RETURN_REVIEW_2026-08-20.md) | **finding** | The train-return floor on the REAL belt (83 sweeps): 0 of 57 null folds ever hit it, its written derivation cites a case that never occurred (train was +10.171%, not +3.66%), and the bug it was built for is still live at gate.py:322 (raw te/tr, sign-inverts on a negative train leg). Also falsifies GATE_CALIBRATION's 2.9% null rate on the belt (25%, CI 8.5–65.1%) and blocks v5 round 3 on two model defects. |
| [GATE_CALIBRATION_2026-08-18.md](GATE_CALIBRATION_2026-08-18.md) | **finding — §7 aggregate falsified on the belt, see MIN_TRAIN_RETURN_REVIEW_2026-08-20** | Gate v4's false-positive rate (**2.9%**) and its power (**22.8%** at Sharpe 1.0, 80% unreachable on our history). Also records a better statistic that was proposed, measured, and **rejected** by an adversary. |
| [CALIBRATION_2026-08-17.md](CALIBRATION_2026-08-17.md) | finding | The first calibration: nulls cleared gate v1 about half the time, and an oracle with perfect foresight failed v2. |
| [SURVIVORSHIP_2026-08-17.md](SURVIVORSHIP_2026-08-17.md) | finding | Survivorship priced at about −6.3pp. The vanished names *gained*, mostly through acquisition. |
| [RESEARCH_XS_MOMENTUM_2026-08-17.md](RESEARCH_XS_MOMENTUM_2026-08-17.md) | finding | Cross-sectional momentum in the capacity band — the research write-up. |
| `parallelism_bench.json` | finding | Measured A/B: **3.20× at 4 slots, 5.30× at 8**, with peak container memory ~460 MiB against a cap that used to reserve 3 GiB. |
| `null_audit_results.json` | finding | Raw null-audit output. |
| `feed_audit_results.json` | finding | Total-return vs price-return check across the feed. |
| `book_rejudged.json` | finding | Every deployed strategy re-judged after the bugs were fixed. All three fail. |

## Running it

| doc | status | what it is |
|---|---|---|
| [LOCAL_E2E.md](LOCAL_E2E.md) | runbook | Bring the whole thing up locally, end to end. |
| [DEPLOY.md](DEPLOY.md) | runbook | Go-live on Alpaca paper. |
| [DEMO_RUNBOOK.md](DEMO_RUNBOOK.md) | runbook | Driving a demo without tripping over a cold start. |
| [CLARK_INFRA.md](CLARK_INFRA.md) | canon | Clark as the agentic team, and how the pieces talk. |

## Specs handed to other people

| doc | status | what it is |
|---|---|---|
| [RISK_ENGINE_SPEC.md](RISK_ENGINE_SPEC.md) | spec | The six measured risk modules. Implemented. |
| [STRATEGY_COMPOSER_SPEC.md](STRATEGY_COMPOSER_SPEC.md) | spec | Composing strategies out of strategies. |
| [ARCHITECTURE_REVIEW_2026-08-17.md](ARCHITECTURE_REVIEW_2026-08-17.md) | finding | A critical read of the architecture, and the consolidation it asked for. Several items still open. |
| [SPRINT_PROMPT_2026-08-17.md](SPRINT_PROMPT_2026-08-17.md) | snapshot | The brief for the 2026-08-17 sprint. Historical. |

## Other people's

| doc | status |
|---|---|
| [GEMINI_TASKS_NOW.md](GEMINI_TASKS_NOW.md) | **owned** — Gemini's task queue |
| [RUSHI_TESTING.md](RUSHI_TESTING.md) | **owned** — Rushi's local testing notes |

## Dated snapshots, kept for the trail

| doc | status | note |
|---|---|---|
| [STATUS.md](STATUS.md) | snapshot | Status, decisions and gaps. Superseded in practice by ROADMAP + FUND_GENESIS. |
| [HANDOFF.md](HANDOFF.md) | snapshot | An earlier handoff. |
| [LOCAL_TEST_REPORT.md](LOCAL_TEST_REPORT.md) | snapshot | A local end-to-end test report from an earlier build. |
| [SESSION_CHECKLIST_2026-08-14.md](SESSION_CHECKLIST_2026-08-14.md) | snapshot | A checklist for one specific Friday. |
| `null_audit_v4_run_ABORTED_untestable_grid.log` | finding | An audit run that produced a *true* 0% false-positive rate about the wrong criterion, because every null came back NOT TESTABLE. Kept deliberately: a measurement that answered the wrong question is evidence about the instrument. |

---

## Where the numbers actually live

Documentation drifts; code does not. Anything below is read from the running
system rather than transcribed, and should be trusted over any prose here:

- `GET /fund/judgement` — every threshold we chose ourselves, with its basis, what
  would falsify it, and whether it has **drifted** from the reason on file
- `GET /fund/doctrine` — the seven stages of FUND_GENESIS with live status
- `GET /fund/mechanics` — the pipeline as selection: funnel, causes of death, the
  gate's own lineage, and a UTC time axis
- `GET /fund/liveness` — which scheduled jobs actually ran, where *not yet
  observed* is a distinct answer from healthy or broken
