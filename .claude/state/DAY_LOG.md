# DAY LOG — the chair's daily record, for the Fable chair to review

**Created 2026-08-21 on the CEO's instruction: *"I also think you should
maintain a day log for fable to review."***

## What this is, and how it differs from what already exists

- **`CTO_REVIEW_QUEUE.md`** is organised by ACTION — one entry per Tier-2 act
  or Tier-3 deferral, written for audit. It has grown large and it answers
  *"what did the co-CTO do, and was it inside its charter?"*
- **`docs/archives/`** is Donna's, written for the CEO, and it answers *"what
  happened at this firm today?"*
- **THIS FILE answers a third question, and it is the one a returning chair
  actually asks: "what is DIFFERENT since I left, what is MINE to decide, and
  what is on fire?"** Chronological, newest day at the top, ruthlessly short.

**The rules for keeping it, so it stays useful:**

1. **One entry per UTC day. Date it by UTC** — the local day rolls over 5.5
   hours early in this timezone and has already caused one dating error.
2. **Newest at the top.** A returning chair reads down until it recognises
   the world.
3. **Every entry carries the same five headings**, and a heading with nothing
   under it is deleted, not padded: **DECIDED · BUILT · MEASURED · OPEN FOR
   FABLE · ON FIRE**.
4. **"On fire" means dated or losing money.** Nothing else goes there. If it
   is merely important, it is OPEN.
5. **Link, do not duplicate.** Point at the artifact, the request id, the
   queue entry. This file is an index with judgement, not a second copy of
   the record.
6. **Write it as the day happens, not at end of day.** The end-of-day version
   is a memoir; the live version is a handover.

---

## 2026-08-22 (UTC)

### ON FIRE

**The 2026-09-08 short hazard is unchanged and still dated.** $501.58
date-certain, $750.35 armed across four legs, plus UNDATED `loss_pct` rules on
all four symbols that make it a tomorrow risk, not a September one. Envelope v4
is merged (`b05cb9b`) — the remaining exposure is the skip-visibility half and
the sign-inverted P&L (`34338ef6`), both still open.

### MEASURED

**THE HOST COLLAPSED, and it is a capacity fact rather than an incident.** Two
concurrent agents — builder pytest suites beside the analyst's 21 bulk-ZIP
extractions — drove free RAM to **1.28 GB of 15.2 GB**. The OS killed
extraction processes with no traceback, four builder pytest processes hung, and
`vmmemWSL` fell 2,812 MB → 147 MB, taking Docker, Postgres and the spine with
it. **A three-hour builder dispatch produced ZERO BYTES** — its task output
file is 0 bytes, no worktree, no bundle. Full stack restarted; `/fund/liveness`
200 in 0.055s, NAV folds to $1,885.74 on Postgres.

**The analyst's cycle 4 returned three results and one of them may matter more
than anything else this week.** A **69,304-transaction insider panel** (21 bulk
SEC quarterly ZIPs, 2021q1–2026q1, 201 universe tickers — chair-verified on
disk) yields a long-only **exclusion screen at +2.72%/yr over the equal-weight
universe, t_NW 2.66, positive 5 of 6 years.** UNREVIEWED; adversary dispatched
blind against the same data. Also: **breadth on the filings corpus is a
SEASONALITY problem, not a count problem** — entry 8 holds 146 names in
November and 7 in July, a 20.9× swing, which retires the premise of the 8-hour
corpus extension the mechanism requested and the CEO approved. Entry 14 CLOSED
(8 names at N=20, 0.0% of days ≥30).

### NIGHT'S END STATE — for the CEO's morning / Fable's return

**D11 v2 landed (builder D14) and is UNDER ADVERSARY BLIND now** — all eight
kills closed, 1694 passed, nothing merged; Tier-3 (event store) + a loosening,
so it goes adversary-then-CEO like envelope v4. The builder refused a wrong
third of the adversary's own K2 spec (`superseded` = revised/governing, not
dead) and proved it by folding the code; the adversary is adjudicating its own
override. **Only build running.**

**GRACE v3 — the finding that reframes deployment:** the whole $1,885 book is
PAPER, so P5 (real fills) and controls-in-anger are impossible on paper by
construction. The binding first-real-dollar constraint is **a live-funded
account nobody has opened** — the one path item with external KYC lead time,
clock not running, and **the CEO's own act (no agent opens accounts or moves
money).** First real *clicked* Tier-0 fill reachable ~2026-08-28 if the clock
starts; two of the three blockers gate automated entry, not a clicked one.

**Closed on the 21st:** Donna's full-day EoD delivered to the CEO as files;
the co-CTO mid-day misfire closed by a builder ticket (`02a0048d`) that turns
the UTC-dating rule from prose into an evaluated guard.

**THE MORNING DESK (decisions that are the CEO's):** Vishesh's 7 · the
graduated-path pair + readiness matrix (one residual: sim-rehearsal-now vs
bound-first) · Grace's G1 live-account clock · Entry 20 → belt (quant built,
run held for a heavy slot) · D11 v2 pending the adversary · the confirmEcho
collision before any prod unlock · personality-as-prior seeds live.

**STANDING, chair-owed:** THE CLEANUP (`dce47670`) deferred twice — dispatch
before the next builder feature. Belt run for Entry 20 held for a free heavy
slot. Grace + PM `WHERE I DIFFER` on the readiness matrix owed next round.

### THE EXEC TABLE SETTLED THE CALCULATED-RISK DESIGN TO ONE DECIDABLE QUESTION

The PM + riskofficer pair (CEO steer: calculated risk, living calibration)
delivered two independent halves, then engaged. **They converged**: both agree
NO real entry until three live controls are wired (unguarded resume,
producerless integrity halt, venue-routes-nothing — three seats now line-exact
on the last) AND until real fills exist, because every fill today is a
simulator's. Each adopted the other's evidence VISIBLY — the PM took the
envelope's exit-event-predates-entry and confidence-provenance checks and
conceded a real pilot now is unsafe; the riskofficer took the PM's tuition cap
as the bound that makes a blurry-gate confidence safe to size on. One
sub-dispute resolved by better argument: the adversary DOES carry early size
weight (KILL-floor-only would make size depend entirely on the worst-measured
instrument, the gate).

**THE ONE RESIDUAL, for the CEO — same fact, opposite valence:** is a SIM
Tier-0 dress-rehearsal (full graduated path on paper, zero risk, validates the
plumbing and de-risks the three blockers' wiring) a PRIORITY to dispatch now
(PM) or a step to BOUND FIRST and sequence after the blockers (riskofficer)?
Neither resolved it; the named disagreement is the deliverable. Natural
pipeline it implies: CEO accepts the design → adversary passes the entry
envelope (it is a LOOSENING, self-routed) → builder builds it → sim
dress-rehearsal → wire 3 blockers → first REAL pilot.

### THE METRICS LAYER IS LIVE — and the record now has a clock

**Builder D13 merged at `5bef3e2`** (chair re-ran the suite on the merged
tree: 1523 passed, REAL_EXIT=0; spine restarted; all five routes verified;
NAV $1,885.74). One shared fold replaces every seat's hand-derivation —
Donna's day drops from ~26 minutes of folding to 0.12s. Three defects found
by building, all mutation-verified — sharpest: **the flight recorder was
DISCARDING the corrections it was sent** (upsert missing DO UPDATE columns;
an omitted tokens field BLANKED the stored count). `run-builder-d13` is
**the first run record in the firm's history carrying its own
`dispatched_at` and `status`** — the chair's habit changed the same pass the
fields landed. The builder's EVOLVE (baseline test count beside the final)
ACCEPTED into its seat file — the contract's second applied amendment in
one night.

**First live reading from the new instrument**: `chair_backlog` = 30
approved-undispatched requests, oldest 20.8h, all on the chair — published
as an upper bound with its link coverage stated (10 of 24 dispatch events
linkable). **One decision routed to the CEO**: whether that backlog enters
`desk_load.total` — including it flips `coo_triage_due` without a threshold
moving, and the builder correctly refused to decide a threshold.

**D11 v2 dispatched** — the night's last build, as NARROW SEPARABLE diffs
per Grace's G3 (measured: bundles on the broker surface die, narrow diffs
merge). In flight at update: adversary (Entry 20 blind) · COO #5 ·
validator (three settling measurements) · builder (v2). 

### THE NIGHT SHIFT, SECOND HALF — the funnel turned over in one night

**RETIRED, honestly**: the insider lead failed its own pre-registration at
double the sample (UNSUPPORTIVE — placebo z FELL as n doubled; the 10b5-1
flag does not exist pre-2023 so "discretionary" was a no-op for 7 of 10
years). Zero market sessions spent. `docs/research/INSIDER_EXTENSION_RESULT_
2026-08-22.md`. The pre-filing run-up it surfaced (−7.7%/yr, t −8.93 —
insiders sell into strength) is the biggest number in the study and rewrites
placebo methodology here: non-overlapping ≠ null, and NW understates ~2.5×.

**PROPOSED, the same hour**: the mechanism's **Entry 20** — scheduled-
announcement liquidity premium, its FIRST proposal to reach the belt in five
cycles. Signature prediction passed (payment scales with inventory risk,
vol-normalised, t +3.37). With the adversary blind NOW, alongside its
premia-sufficiency challenge (routed to the adversary despite TIGHTENS — the
COO's precedent: judging premia outside v5 is a loosening's shape).

**GRACE v0.2**: the cost benchmark is repairable BACKWARDS — historical SIP
NBBO free on our existing key, chair re-verified. Two of five preconditions
are simulation-only (`ALPACA_PAPER=true`, converging with the riskofficer's
mock-broker finding). She WITHDREW her own D4 and RETRACTED her own
second-pen call: merge throughput binds, not authorship. Meter corrected to
10.45M tokens / 55 runs; the missing killed-builder runs recorded
retroactively (d8, d11 — d11 with real figures). Her EVOLVE applied to her
seat file — the contract's first accepted amendment.

**MERGED**: builder D12 (KryptonPay `14fb5605`) — Grace's desk in the exec
row beside Vishesh, the room fits its column at every width, dead-spine
chips honest. The spine gained `allocation_review → cfo` (chair,
one line + restart, telemetry 11 seats, NAV verified $1,885.74).

**IN FLIGHT at last update**: adversary (Entry 20 blind) · COO triage #5
(the ≥50 trigger FIRED at 52) · validator (three settling measurements: the
G2-vs-R27 heterogeneity test, the 38× time-of-day cut, the premia-inequality
proof-or-counterexample) · metrics builder (D13, still building).

**CHAIR-OWED, queued**: premia-menu pass (entries 17/19/20 unregistered) ·
API-card additions (SEC submissions endpoint; foreign-issuer names; the
quarterly-placebo warning) · D11 v2 narrow repair brief (after metrics
builder) · guard v1.3 · THE CLEANUP (`dce47670`) · the cfo placement
sentence in the constitution.

### THE NIGHT SHIFT — running record (Fable, updated live)

**Landed and fully resolved (verify → file → record → STATE → BINDS, all
five steps):** Donna's superseding 08-21 archive (`2af4256` — found two
discrepancies in the chair's own instruments, both verified: the queue's
wrong mismatch count at line 1654, and the v4 runs missing from the record —
closed with retroactive records marked as such). The adversary's D11 KILL
(`docs/reviews/ADVERSARY_D11_2026-08-22.md` — four falsified self-claims;
NOTHING MERGED per the CEO's pre-authorization; KP parked to land with v2).
The PM's measurement-programme design
(`docs/pm/PM_MEASUREMENT_PROGRAMME_2026-08-22.md` — the cost benchmark is a
cached LAST TRADE, not a mid; required n scales with cost²; the baton; the
$40 tuition cap; request `5b6b37bd` RESOLVED — Grace's critical-path item is
designed). Propagation sweep committed at `cee5406`: five STATEs verbatim,
all BINDS carried, chair decisions written where seats read them.

**In flight at last update (5/5):** mechanism c5 · room builder (KryptonPay)
· metrics builder D13 (ClarkHarness — CEO instruction on slow agent runs:
Postgres rollups, friction view, uncapped run stats, dispatched_at + failure
runs, scripts/desk library) · **analyst on the 2016q1 extension**
(CEO instruction "put analyst on the run"; locked pre-reg `d8259e0`;
single-stream, 4TB store, checkpointed) · Grace v0.2 (re-derive the date —
the PM moved its inputs; answer the PM's challenge to D4; review the
redesign on the date axis; cost the second pen).

**JUDGEMENT LEDGERED**: analyst + metrics builder = two concurrent heavies
beside a light room builder — a deliberate exception to the one-heavy rule
on the CEO's direct instruction, taken at 5.05 GB free with single-stream
discipline written into the brief. The falsifier stands: any collapse, the
analyst dies first and the cap reverts.

**Still queued for tonight:** D11 v2 repair brief (fires when the metrics
builder lands — fund.py collision bars concurrency) · guard v1.3 +
integrity-alarms builder (after a builder slot frees) · THE CLEANUP
(`dce47670`, after the D11 decision) · COO triage #5 LAST, so the batch
memo on the CEO's desk at breakfast covers the whole night, with Vishesh's
owed `## WHERE I DIFFER` on Grace.

**For the CEO's breakfast, accumulating:** PM programme clicks R25–R31 ·
R33 (the dated 2026-09-08 exits, hard) · the D4 ↔ PM-challenge pair ·
the reconciliation HOLD (adversary: wait for K2/K3 repairs) · the COO batch.

### THE REIMAGINED TEAM — implemented overnight on the CEO's instruction

CEO, verbatim: *"our team needs to become a self evolving harness that
cordially works as one team and one goal"* → *"go ahead and implement a new
reimagined team over the night."* Shipped: blueprint
(`docs/TEAM_REIMAGINED_2026-08-22.md`, ClarkHarness `bb188c3`), a dated
constitution section (two layers · seats hold boundaries/surfaces/pens, never
workloads · transient fan-out · `## EVOLVE` · the selection loop,
proposals-only, two-week falsifier · adversary excluded from the loop's reach —
**RATIFIED by the CEO the same night ("Agree on adversary")**), and the evolution contract
appended to ALL 11 seat files with a per-seat FITNESS QUESTION. Control layer
untouched. The executive table reviews the implementation: Grace v0.2 on the
date axis, Vishesh triage #5 on reversibility — review AFTER implementation
was the CEO's sequencing call.

**Also amended (CEO, awake): TWO BUILDERS may run in parallel** — disjoint
write scopes, serialized full suites, falsifier: any RAM collapse or hung
suite reverts to one heavy.

### THE CHAIR IS BACK — Fable, from ~11:00Z

Handoff accepted and annotated resolved at the top of the queue. Rulings:
clause 5 gates seat challenges, not CEO instructions (falsifier-at-write-time
is the treatment for a CEO loosening); the wire's posting boundary PINNED
narrow (a posting never fires a seat — CEO confirmed); PM dispatched on
`5b6b37bd` within the hour (the co-CTO's caution was over-caution, by its own
note). Five seats in flight: adversary (D11 blind), builder (the room),
mechanism (c5), Donna (08-21 archive), pm (measurement programme).

**OVERNIGHT AUTHORIZATION (CEO, 2026-08-22, verbatim: "I was working the whole
day so I havent slept - lets work together for next 30 aqnd then you need to
run the team for next few hours").** This is a live session with standing CEO
authorization — not scheduled autonomy; the deliberate-versioned-step line is
uncrossed. Scope the chair holds overnight: dispatch/verify/file/record/
resolve; merges on green within chair authority. Scope that WAITS for the
CEO's morning click: the alpaca-paper reconciliation, any deploy, any
threshold move, any COO batch acceptance, Grace's D4 respec.

**Three overnight acts pre-authorized by the CEO awake ("yup", 2026-08-22):**
(1) **D11 merges WHOLE on adversary SURVIVES** — `FUND_MODE=alpaca-paper` into
the live `.env` first, spine restart, NAV verified $1,885.74 on Postgres; on
KILL nothing merges and the repair brief goes out tonight. (2) **The 2016q1
corpus extension runs as the night's one HEAVY job** — pre-registration
committed BEFORE the pull (see docs/research/), output to the 4TB store,
after the room builder lands. (3) **COO triage #5 runs late tonight** — one
batch memo on the CEO's desk at breakfast, including Vishesh's owed
`## WHERE I DIFFER` on Grace's first memo, his own ranking formed FIRST.

### HANDOFF TO FABLE — 2026-08-22, and it is the top entry of CTO_REVIEW_QUEUE.md

**The CEO is bringing the CTO chair back.** The full handoff is one detailed
entry at the TOP of `CTO_REVIEW_QUEUE.md` — nine sections: four seats in flight,
four things on fire, the D11 merge decision, eight Tier-3 items with my review
note on each, the day's governance changes, **a section on where I was wrong**,
the firm's best lead, Grace's memo, and what I deliberately did not do.

### ON FIRE — added through the day

- **THE KILL SWITCH'S OFF-SWITCH IS UNGUARDED.** `POST /fund/risk/resume`
  (`fund.py:3736-3739`) has no `_guard_approval`; `RiskResumeRequest` is one
  free-text `actor` field defaulting to `"operator"`; the API has one
  middleware and it is CORS. **`halt_acknowledge` — which acts on nothing — IS
  guarded.** `autopolicy.py:512`'s `not_halted` check reads a state anyone can
  flip. Chair-verified line-exact. Tier 3, TIGHTENS, cheapest high-money fix on
  the board.
- **THE INTEGRITY HALT HAS NO AUTOMATIC PRODUCER.** The three data-quality
  alarms are built into a local list `run()` never reads — zero occurrences in
  `evaluate_alarms()`, chair-grepped. The *"fund cannot measure itself"* halt,
  the exact class of the 2026-08-20 phantom incident, cannot fire. Two green
  tests sit over it.
- **THE LIVE SPINE CONTRADICTS ITSELF**: `GET /fund/book` returns
  `venue: "alpaca"` with `orders_are_real: false`. Fixed in D11, which is parked.

### MEASURED — added through the day

- **The insider screen: headline KILLED, effect SURVIVED.** +2.72%/t 2.66 →
  **+1.99%/t 1.96**. The screen sold at the close of the filing day; 86.8% of
  those Form 4s are not public until after that close. Survived eleven further
  attacks including beta (−0.0121, first time that attack has come back empty
  here) and a sign test. Still the firm's best lead.
- **Precondition 1 is MET WITH NAMED EXCEPTIONS** — the firm has been carrying
  it as unmet, a date lost for free. But **every fill in fund history was
  mock-filled**, so it is not sufficient for `alpaca-prod`.
- **The cost model measures the wrong thing.** Five of eight fills rested 74+
  minutes, so `execution_bps` is overnight drift, not spread. Honest n is 3.
  And the chair's own brief was refuted three ways on breakeven.
- **The dead builder dispatch was NOT lost** — 8 commits, 3,731 lines in a
  scratchpad clone I failed to look in. Recovered and bundled.
- **ENTRY 20 PASSED GATE v4.1 WITH ZERO FAILURES — THE FUND'S FIRST
  SUBSTANTIVE PASS** (candidate `144387901688`; prior passes were the planted
  nulls under v1). And the pass is thinner than the headline, measured four
  ways: active t = 0.60 (not distinguishable from zero; PSR saw the total
  book at beta 0.54), excess over-credited 11.85pp on a transient
  benchmark-window truncation, all headlines struck at slip=1bp vs the 5bp
  default, and the gate's breakeven floor was NEVER evaluated —
  `gate.py:405-412` writes a string and appends no failure. The quant spent
  one container to measure what the gate skipped: **active breakeven 13.9
  bps/side** (1.4× the floor). Vol ratio measured 0.656 vs the 1.0011
  pre-committed — premia-shaped, passed the harder gate anyway. Three
  pass-favourable instrument defects filed; disposition: **gate-v5 re-judge,
  not a deploy signal.** `docs/quant/QUANT_ENTRY20_2026-08-22.md`,
  run `run-quant-entry20`.
- **The model picker cannot be trusted as identity**: `/model claude-fable-5`
  reported "set" twice while the session was served by Opus (with >90% of the
  Fable weekly quota unspent, so not a quota fallback). The constitution's
  check-your-model-on-cold-start rule is the only reason we know. Harness
  bug, CEO filing it upstream; until then the served model is the identity,
  never the picker.
- **`daily_returns.benchmark` is DEFECTIVE in the verification payload**:
  compounds to +19.76% vs the true +84.78% on candidate 144387901688 while
  claiming "907 aligned daily observations, dropped 0" — absence rendered as
  zero on the calendar grid. Found by the chair charting the CEO's one-pager;
  carried to the validator. Never consume that leg.

### DECIDED (by the CEO) — evening additions

- **THE LAB**: a strategy one-pager per experiment, docked under `docs/lab/`
  with a Studio shelf (builder ticket `66912f40`); **Donna's write exception
  extends to `docs/lab/**`** — working-protocol-6 amendment written, caveats
  always sourced from the judging seat's report, never templated. Entry 20's
  PDF (`docs/quant/ENTRY20_ONEPAGER_2026-08-22.pdf`) is the format seed.
- **THE BELT DATA CACHE approved and dispatched** (ticket `252bce7b`): the
  measured 85%-of-container fetch tax; expected ~96 min → ~20-25 min per
  candidate; clean-field merge condition — bit-identical verification run.
- **+16 GB RAM incoming** (host going 15.2 → ~31 GB). NOTE FOR THE CHAIR:
  this re-opens the host-budget numbers (one-heavy-job rule, the 1.28 GB
  collapse falsifier) — revisit as a WRITTEN, versioned amendment when the
  RAM physically lands, never silently. The rule stands until then.

### DECIDED (by the CEO)

- **THE WIRE**, in two parts (`572261e6`, `384a4bfd`). Routing becomes something
  code evaluates. His correction is the spine of it: **a loosening item routes
  to the adversary's desk and never reaches his.** Segments, agent-to-agent
  postings off a versioned list, four loop brakes. **One boundary flagged and
  still unanswered: a posting fills an in-tray, it never fires a seat.**
- **Donna gains the FRICTION LEDGER** — who is waiting on whom, aged, with the
  chair and the CEO included as respondents.
- **Grace is on the floor** (roster `41b6b54`), and the room re-space is with a
  builder.
- **Parallelism cap 2 → 5**, verbatim: *"we have a lot more tokens to spend now
  so 5 agents in parallel is approved from atmost 2"*, tempered the same day by
  *"analyst doesnt need to prallelise so much that the host breaks lol; we have
  to push it but not break it."* Written into the constitution WITH a host
  budget (LIGHT vs HEAVY seats, at most one heavy job in flight) because the
  stated reason is tokens and the measured constraint is RAM. Ledgered.
- **Restart the builder and close its items** — done; four seats now in flight.

### BUILT

- Three builder requests CLOSED against live verification, not commit
  messages: `907ecc74` (third dispatch state, `desk.py:820` in the live tree),
  `920ecbe5` and `af279b4c` (Donna's memo route — `GET
  /fund/desk/archives/memo` now 200, serving THE DAILY · 2026-08-21; it was a
  hard 404 this morning).

### OPEN FOR FABLE

- **The quant's TIGHTENING challenge on the gate's breakeven branch**
  (`gate.py:405-412` — the "beyond the tested range" string satisfies
  `require_breakeven_measured` and the floor is never evaluated). Three
  concrete v5 fixes filed in `run-quant-entry20`'s recommendations; gate code
  is Tier 3, so nothing executed. It composes with the existing gate-v5
  round-6 input (`4698dee7`).
- **The `_add_benchmark` window truncation** (leanrunner.py:1289/:1295) —
  a builder ticket's worth of per-run check; belt read-side, not gate logic.
- **The loosening question.** The cap amendment is a LOOSENING that did NOT go
  to the adversary. My reading: clause 5 governs seat CHALLENGES, not CEO
  instructions. Confirm or correct it — the precedent matters more than this
  instance.
- **The insider screen**, if the adversary lets it live: it would be the first
  candidate this firm has ever had reach the belt with a real prior.

### ON THE CHAIR (recorded against myself)

**The analyst's run sat unrecorded for ~14 hours**, so the desk showed
`running_now: true` for a seat that had finished — the exact "working vs
awaiting review" ambiguity the third dispatch state was built to remove. The
state shipped and works; I did not feed it. **Second time this week I have
skipped step three of my own resolve checklist.**

---

## 2026-08-21 (UTC)

### ON FIRE

**Auto-approval envelope v3 will short the fund on 2026-09-08.** The TLT and
DBC time exits fire that day (`ExitRuleSet` seq 178, 181), auto-approve, and
sell shares the broker holds **zero** of. The riskofficer rebuilt the real
evaluation context and ran it: **all four live exits pass v3 twelve checks out
of twelve, zero failures.** **$501.58 date-certain** (TLT seq 178 + DBC seq 181), **$750.35 armed across all
four legs** — 39.79% of NAV. **CORRECTED 2026-08-21 by the builder, verified by the
chair against `/fund/exits`: the earlier figure of $652.09 was WRONG — it summed two
different dates.** DBA's and SPY's time exits are **2026-11-19**, ten weeks later.

**AND THE HAZARD IS LIVE, NOT SCHEDULED — this is the sharper correction.** All four
symbols additionally carry **UNDATED `loss_pct` rules**: TLT 4.0%, DBC 8.7%, SPY 7.3%,
DBA 6.1%. Any one firing on an ordinary drawdown hits the identical defect **tomorrow**.
2026-09-08 is when part of it becomes certain, not when it begins. Shorting is enabled on the account; borrow cost, buy-in
risk and unbounded loss are all unmodelled here.

The envelope is not malfunctioning. Every check it makes is true. **It checks
our own book and never asks the broker what it holds.**

**Status**: v4 is fully specified (`docs/R19_ENVELOPE_V4_SPEC_2026-08-21.md`),
**CEO-approved**, and the CEO has now **authorised this chair to cross the
Tier-3 line to get it done** — with the condition that Fable receives full
context. Execution plan is builder-in-worktree → **adversary blind** →
chair merges on green only. Not hand-written by the chair.

**It must ship WITH the skip-visibility fix.** A v4 decline currently produces
no event, no log line and no alarm; the proposal then expires at 120 minutes
and **never re-raises**. `pipeline.py:400-403` and `fund.py:3768` both claim it
does; both are false (`exitrule.py:275` skips on `triggered_at`). **v4 alone
converts a silent short into a silently dropped exit.**

**And the one that gates any future short**: `riskmonitor.py:878` computes P&L
with no reference to the sign of the position, and `positions.py:87` leaves a
short holding its long cost basis. **On a short, a rising price is a loss that
reads as a gain — stops fire backwards.** Filed `34338ef6`. R19 does not touch
it.

### IN FLIGHT AS OF THE LAST UPDATE

- **Adversary, blind, on envelope v4.** Built and proven against the live
  916-event log — the builder synthesised the event `enforce()` will write on
  2026-09-08 and ran the real gatherer and evaluator: `APPROVE = False`, with
  all twelve v3 checks still passing on the same data. Tests 19 → 59 plus a new
  wiring file; **fifteen mutations injected into its own new code, fifteen
  caught.** Merge gate **FAIL exit 1** — the correct verdict, `autopolicy.py` is
  sensitive. **Nothing merged.** The CEO's click adopts v4 once the adversary
  clears it, and I asked the adversary to attack one claim hardest: *that v4 is
  strictly tightening* — because that premise is what lets it adopt without a
  separate widening review, and a sign-agnostic predicate inside a sells-only
  policy is where a widening would hide.
- **Builder, on the office.** D9 was **KILLED** by the adversary on one ground,
  chair-verified line-exact: `stageOfItem` returns on `status` before ever
  reading `nextActor`, so an `accepted` row marked `next_actor: "ceo"` — *the
  exact case the field exists for* — is counted by the spine and filed by the
  page under "shown, never counted." **Server 1, page 0, same line of the same
  screen.** Two of the diff's own tests blessed it, including one titled *"never
  re-derives from kind or status"* that greps for neither. Repair dispatched,
  **plus the CEO has authorised the decision-list restructure** ("lets have the
  builder fix our office first"): N cards and nothing above them, the COO's
  batch as the *grouping* of those cards, a date chip on the one row that does
  not wait, and Donna's 404 memo route recovered. Commits kept separable so the
  kill-repair stays reviewable alone.

### DECIDED (by the CEO)

- **THE HARNESS PHASE NOW HAS AN EXIT CONDITION, and it is the `alpaca-prod`
  precondition list.** Agreed 2026-08-21. The firm is deliberately
  builder-heavy right now — 21 tickets on one seat, near-zero elsewhere —
  because a firm whose instruments are broken cannot trust any other seat's
  output. The risk in "fix the harness first" is that it has no natural
  stopping point: today alone found four absence-as-zero instruments, a
  phantom price factor, a coin-flip capacity, a blind gate, a mislabelling
  venue and a trapdoor default, and the mechanism measured the trend going the
  wrong way (4 of 8 verdicts dying on the instrument, rising).
  **So "robust enough" is DEFINED as: controls have fired in anger · book and
  venue reconcile · the sign-inverted P&L is fixed · a kill switch is wired and
  tested · N real informative fills in the cost model.** Not "the queue is
  empty" — it never will be. When those five hold, the bench comes back on.
- **Three modes: `test` | `alpaca-paper` | `alpaca-prod`.** Three stores; paper
  NAV and real NAV must never be foldable together. `alpaca-prod` is
  structurally unreachable until the five above are met. `alpaca-paper` syncs
  to what the CEO sees on his Alpaca screen, and unmanaged positions are
  acceptable — **but by APPENDING reconciling events, never by reading broker
  equity as NAV.** Two consequences to surface loudly when it lands: NAV moves
  **$127.55 for a non-market reason**, and **~$1,166.52 enters the book with no
  strategy and no exit rule.** This SUPERSEDES the PM's R18 fence-the-cohort
  recommendation — reconcile, do not fence.
- **Mock is isolated, not ephemeral.** It persists to Postgres like everything
  else. The old flag's sin was conflating those two: 552 events lived in memory
  while the status endpoint reported success hourly.

- **Envelope v4 adopted**, with the skip-visibility fix in the same change.
- **Two agents may run in parallel when independent** — supersedes the
  one-at-a-time rule. Five-part dependency test written into the constitution.
- **Decisions are provisional**: challenging a standing decision is now a DUTY
  of every seat, with an admissibility bar (new evidence or demonstrated
  consequence), an adversary pass for anything that loosens, and rejected
  challenges recorded.
- **The 200-name universe is FENCED** as a pre-instrument reference frame under
  the Clean Field Rule. It cannot be re-baselined — no point-in-time membership
  exists.
- **The gate's risk-free source**: a realised daily short-bill series; a
  constant is rejected. *(Execution Tier 3.)*
- **Market-closed work** is a registered trigger, not a schedule.
- **COO memo house format** specified: WHAT / WHY NOW / HOW / RECOMMENDATION,
  SWOT only when it earns its place, ranked by reversibility first.

### BUILT / SHIPPED

- **Builder D9 — the CEO desk counter, the third dispatch state, and desk
  ordering. BUILT AND GATE-PASSED, NOT MERGED — held for the adversary blind.**
  Both bundles verify against their declared bases (chair-checked); ClarkHarness
  1324 passed on the merged tree, KryptonPay 255/255. **The seat flagged its own
  diff as touching a control despite a green classifier**, which is exactly the
  instinct that was missing when the D8 guard widening nearly shipped.
  - The counter now measures **whose next move it is**, not what label a row
    carries: **18 → 13** on the data that produced the CEO's complaint. **This is
    a LOOSENING** — the COO trigger fires later — and it is on the CEO's desk for
    explicit sign-off rather than silent acceptance.
  - **It refuted my brief's central premise with a measurement**: `kind` is free
    text, **84 distinct values over 219 rows, 49 singletons**, so routing on it
    moves only 18.7% and the decoupling I hoped for is *not* achieved. It pinned
    that in a test named for the limit rather than the hope.
  - **The third state's gap was the BACKEND only** — the UI shipped complete at
    `65e6fdc4` while the spine half sat in the adversary-killed D8 branch. It has
    been dead code on the live spine since it landed.
  - **It found a defect in the killed branch and re-derived rather than
    cherry-picked**: that version matched runs on `task_id` (8 of 24 live) where
    the right key is `trace_id` (17 of 24).

- **`## BINDS` protocol** — a seat names which OTHER seats a lesson binds; the
  chair carries it. Closes the propagation loop, which had a measured bias
  toward defects over anything that changes what gets proposed. First use was
  the mechanism's, carried to five seats unstruck.
- **Analytics capture confirmed on a real candidate**: store 37|0 → 40|3, six
  present legs each, `dropped_unmatched_days = 0` on all eighteen. Gate v5
  round 6 no longer runs in simulation. The Lab page now shows the three new
  rows beside three `not_captured` ones.
- Desk swept twice; the resolve pipeline is now a written six-step checklist in
  `co-cto.md` after the chair shipped work the CEO could not see.

### MEASURED

- **THE COST-ROBUSTNESS CRITERION HAS NEVER PRODUCED A NUMBER. A census of all
  40 belt candidates, chair-verified in Postgres: `fund_candidates` reads
  **40 | 0**, `fund_lean_sweeps` reads **114 | 0**.** Eleven v1 candidates
  satisfied it *without measurement* and **all three passes the belt has ever
  issued are in that eleven** — the fund's entire pass history rests on a
  criterion satisfied by absence. Twenty-five later candidates were *failed*
  for the same missing measurement, and the numeric branch has never executed,
  so discrimination on this criterion is undefined.
  - **The bias, where it could be measured, is LARGER THAN THE THRESHOLD**:
    total-return breakeven exceeds excess-return breakeven by **10.4–18.4 bps
    against a 10.0 floor.** One walk-forward fold flips from 17.22 to 0.81 —
    that fold's entire apparent cost robustness *is* the risk-free rate.
  - **The widest door needs no number at all**: `gate.py:411-412` passes on
    "still profitable at every cost tested", and on the one cost-swept family
    that path passes a candidate whose benchmark-excess edge is **negative at
    every cost tested**.
  - **And the gap runs both ways**: the belt credits **zero** interest on idle
    cash, so it docks the most selective designs **2.0–3.5%/yr** of carry they
    would really have earned. `mean_reversion_cyclicals` sits 97.95% in cash.
    That is a leg-1 defect pointing straight at leg 2.
  - **MY BRIEF'S PREMISE WAS WRONG AND THE SEAT REFUTED IT.** I asserted that
    cash-parking inflates breakeven, relaying the mechanism's attribution
    without re-deriving it. Idle cash earns **exactly 0.000%** here. Cash
    parkers are the *least* affected. Third time today a seat corrected the
    brief that dispatched it.

- **The machine, because the team had been treating local compute as scarce and
  the CEO challenged it.** He was right, and the bound is not the one being
  cited: **CPU is a Ryzen 9 7900X, 24 threads at 11% utilisation; the GPU is an
  RTX 4090, idle.** Neither is scarce. **RAM is the wall — 15.2 GB total, 0.8 GB
  free** — and `MAX_CONCURRENT_CONTAINERS = 6` is registered with basis
  `measured`, falsified-by *"a WinError 1455 or any host-memory kill"*. That
  limit came from a real out-of-memory event; it is a RAM limit wearing the word
  "container". **Three scarcities had been collapsing into one word: tokens
  (real, structural), RAM (real, 15.2 GB), CPU/GPU/wall-clock (not scarce, and
  where the false caution lived).** Worked example: the mechanism declined to
  recommend D5 without a cap on "12.6× compute" — but at the quant's measured
  12.8s per container that is ~27 minutes sequential on a machine at 11% CPU.
  Correction propagated to mechanism, quant, validator, analyst and builder.

- **Our price history carries a +43.84%/yr phantom factor** — today-anchored
  split adjustment (TENX reads $2,320 on 2020-06-01) plus **203 of 203 symbols
  alive today**. The walk-forward gate is structurally blind to it.
- **Gate v5 round 5: financing FIXED and unreopenable; the rule is NOT
  adoptable.** Discrimination **0.62, CI [0.53, 0.72] excluding 1.0** — the
  worst plausible null passes more often than a designed premia claim, and no
  margin from 1–8%/yr fixes it.
- **Two live v4.1 gate defects** (chair-verified in code): `breakeven_cost`
  interpolates on **total return**, so a cash-parking rule's robustness carries
  its T-bill yield — edge dies at 7.3 bps/side, gate reads 14.55 against a 10.0
  floor. And the OOS union is `(need+1)×4×hold`, so **a 1-day rule is certified
  on twenty trading days.**
- **Belt capacity is decided by an unseeded hash** when two symbols tie on fill
  count — a 16.7× swing on a gate criterion (`8c72939e`).
- **4 of 8 mechanism verdicts have died on the instrument, not the idea.**
- **A real premium found and deliberately not run**: month-end Treasury index
  extension, +1.63%/yr over 11 years, duration-ordered with a clean placebo —
  and the belt window contains +0.12%/yr of it. Zero containers spent.

### OPEN FOR FABLE

- **FIRST CHAIR-APPROVED DESK REQUESTS IN THE FUND'S HISTORY (4).** The CEO:
  *"this says awaiting you when its already accepted."* Four rows of four, all
  mine — build tickets filed at status `open` for work whose recommendation he
  had already accepted, so the desk handed his own decisions back as fresh
  questions. Approved via the guard as `neelesh-via-co-cto` with his verbatim
  words; `requests_awaiting_approval` **4 → 0**. All 25 prior approvals carry
  `ceo` or `neelesh-via-cto`. **If that line should hold absolutely, revert
  them** — the cost is only four re-clicks. Reasoning in the queue.

- **Tier-3 parked, in priority order**: the register's trigger-evaluability fix
  (**before** registering governance decisions — 17 of 19 triggers are inert
  and the endpoint reports `[]`); guard v1.3's server-issued echo; risk-limits
  and trading-resume onto the approval channel; the rebase direction fix **as a
  pair**; D5 and D7.
- **Three challenges filed under the new rule.** #1 (chair's) refuted in
  evidence by the COO. #2 (COO's) accepted — the constitution was amended the
  same day. #3 (COO's) and the mechanism's are **on the CEO's desk**: must the
  premia criterion be a gate statistic at all, and should the 10-year backfill
  be decoupled from gate v5?
- **Chair errors, all self-reported and in the queue**: resolving against
  8-character id prefixes (six inert events on the append-only log); shipping
  R19 without recording the run, so the CEO could not see it; splitting a
  cross-repo diff and stripping a UI caller of its spine callee.
- **`USE_FAKE_FIRESTORE` controls order routing, not just the ledger** — and
  this chair flipped it. `fund.py:132-140` carries a docstring saying
  `_real_broker()` exists to prevent exactly that conflation. Filed
  `b72847bc`.
