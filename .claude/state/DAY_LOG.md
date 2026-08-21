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
