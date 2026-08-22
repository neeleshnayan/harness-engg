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
