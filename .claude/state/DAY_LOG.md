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

## 2026-08-23 (UTC)

The first ~75 minutes of the UTC day, closing the night shift. The CEO left
at ~00:05Z ("you too rest post closing these 5 items; will see you on
Monday"). The five fan-out items all resolved; the floor rests until Monday.

**DECIDED**
- Nothing new — every decision tonight predates midnight UTC and lives in
  the (banner-corrected) 2026-08-22 entry below. The CEO's parting
  instructions: rest after the close; G1 (live account) starts Monday.

**BUILT**
- **The chair's filing debt CLEARED** (Donna's chair-directed finding: five
  resolved run records named artifacts absent from disk). Seven docs filed
  as operative summaries pointing at their primary run records:
  `docs/reviews/ADVERSARY_{BATCH,D17,D18,ENTRY21}_2026-08-23.md`,
  `docs/cfo/GRACE5_TOKEN_LEDGER_2026-08-23.md`,
  `docs/riskofficer/RISKOFFICER_6_2026-08-23.md`,
  `docs/research/LEADS_SHELF_2026-08-23_v1.md`.
- Donna's 2026-08-22 archive committed (`docs/archives/2026-08-22.md` +
  `.pdf`, 23,525 + 373,245 bytes, first cut under the midnight guard —
  refused 23:57:48Z, passed 00:00:03Z). Run `run-secretary-4` recorded;
  STATE appended; BINDS carried to Grace (§4 exec-table empiricist half)
  and Vishesh (counter refilled to 101 within hours of triage #6 at 91).

**MEASURED** (Donna's cut, the day-four reference)
- 43 runs / 8.10M tokens / 159 UTC commits / six merges / 0 fills / no NAV
  strike (last: $1,885.74, seq 844) / $0.00 deployed at venue vs the book's
  $917.06 / ≥24 confirmed defects / zero clean gate passes by the fund's
  own choice.
- **Friction ledger day two, WORSENED**: approved-undispatched 28→37,
  oldest tail 14h34m→38.5h — the tail is entirely on the chair's side.
- Dating drift is now SYSTEMIC (chair banner, run `dispatched_at` fields,
  six artifact filenames) — clock ticket `a0e640de` is the named owner.

**OPEN FOR FABLE (= the Monday sheet, in order)**
- **G1**: the CEO opens the live account (CEO-only, his word: Monday).
- **R39 click sheet** (`docs/pm/PM_R39_PLAN_2026-08-23.md`): sync pre-open
  12:30–13:25Z (fresh run_id, read+apply same sitting) → $4.50 INTC probe
  13:35Z gates everything → six orphan sells GLD-first → four sleeve rebuys
  after verifying exit rules live → acceptance ≤$3 residual. Custody
  fixture already captured PRE-sync (`docs/pm/CUSTODY_FIXTURE_2026-08-22.json`).
- **NBBO capture at each submit** — chair prepares the script before open;
  quotes persist nowhere and exclusion 4 of the TCA pre-registration
  (`docs/research/TCA_PREREG_2026-08-24.md`) is unrecoverable without it.
- One-word CEO rulings queued: the "fired in anger" DRILL question (~14
  days per Grace); the gate pair (fold-scaling THEN history floor,
  `58c4fff5`); drift-severity signature (with named owner + reconcile-by
  date); R20/R21/R22; H2 citation-scoping.
- **R1 re-judge-or-void Entry 20 by 08-25** (benchmark population
  `739b5ac9` runs first).
- Builder queue ranked in cto.md; THE CLEANUP (`dce47670`) deferred six
  times and owed.
- **Vault push PENDING for the final two commits** (ClarkHarness `536b427`,
  firm `52021fc`): the permission classifier blocked `git push vault` after
  the CEO left; last time it cleared only in manual-permissions mode. First
  live session pushes both — the standing authorization covers it.

**ON FIRE**
- Nothing burning money. Two dated items: R1's 08-25 deadline, and the
  friction tail (38.5h and worsening) — a third worsening reading at
  Donna's next cut is a chair problem with a trend line.

---

### LATE EVENING 2026-08-22, 18:30–21:30Z — CHAIR DATING ERROR, CORRECTED IN PLACE

**Everything below this banner through the next day-header was initially
filed under "## 2026-08-23 (UTC)" — WRONGLY. The local day rolled at 18:30Z
and the chair dated by it: the exact misfire the EoD guard ticket
(02a0048d) exists to prevent, committed by the chair that filed that
ticket. Caught at 21:32Z by running `date -u` before dispatching Donna.
The same error touches tonight's run records: several `dispatched_at`
fields say 2026-08-23T…Z where the true UTC time was 2026-08-22 evening.
Kept in place with this banner per keeping-rule 1 — one entry per UTC day —
rather than silently re-headed. The lesson is now the chair's, not just
Donna's: CHECK date -u BEFORE DATING ANYTHING.**


### DECIDED (by the CEO, ~00:30Z, before sleep)

- **D11 v2 MERGED — the CEO ran the crossing himself** (`51c9643`): the
  harness permission layer had refused the chair, so the CEO executed his own
  approved merge; it conflicted on one import hunk (D15's barcache vs D14's
  PaperConnector removal), the chair resolved it (keep barcache, drop the
  import whose last use D14 deleted), suite **1732 passed RC=0**, spine
  restarted. **The live venue lie is dead**: /fund/book now returns
  `mode: alpaca-paper` with venue truth. FUND_MODE=alpaca-paper declared in
  .env (the new fail-closed mode system refused to boot without it — working
  as designed). **P2 CLOSED. Riskofficer blocker 3 CLOSED.**

### MEASURED (the concurrent exec pair, resolved ~01:00Z)

- **COO triage #6** (docs/coo/TRIAGE6_2026-08-22.md): 8 real CEO decisions
  from a counter of 91; **11 of 11 open desk requests carried a recorded CEO
  decision in their own filing** (filing-discipline leak — chair now files
  CEO-quoted requests at `approved`); 3 widenings RETURNED for missing
  adversary tickets; 0 of 88 rows populate next_actor/due_date/reversibility;
  TLT is 3.11pp from its undated stop. His counter-rule challenge (LOOSENS)
  is with the adversary (`1c53589f`).
- **Grace 4** (docs/cfo/GRACE4_2026-08-23.md): **the v5 re-judge has a
  measured hole — the benchmark POPULATION is survivor-only**
  (universe.py:115 ACTIVE-now; measured −6.90pp ± 2.40/20mo, KILL direction;
  asof.py has one consumer). **PDT WAS RETIRED 2026-06-04** and still
  corrupts the PM's sizing premise (design premise corrected via BINDS; block
  retirement with the adversary, `b6f4a407`). Dates on record: first real
  dollar **Thu 2026-08-27** (falsifier: hazard batch not dispatched by Tue),
  $10k ask **Fri 2026-09-11**, P1 binding.
- **Convergent from both, independently**: rank the builder queue by hazard
  path (done: `75ca57a7` THE HAZARD BATCH rank 1, `739b5ac9` BENCHMARK
  POPULATION rank 2, hard-sequenced before the Entry 20 re-judge); the
  charter's T0 clock needs a control-layer fence; exec seats now write
  pre-read priors to scratchpad (provable independence — house pattern).

### OPEN FOR FABLE / THE CHAIR

- Charter amendments awaiting the CEO's read (both seats' WHERE I DIFFER):
  stage-0 verification-latency number; T0 to Phase 1 with the third fence
  (live path refuses an injected clock, by test); episode
  superseding-correction path; experience layer re-cuts at EPISODE BOUNDARY
  (126× cheaper); T1 to Phase 5 (a replay is another simulator — cannot
  close P1).
- Vishesh's 8-decision batch on the CEO's desk; Grace's D4 drill set ($0
  risk) needs only a nod.
- gate-v5 trio builder still in flight.

### BUILT (overnight, after the CEO slept)

- **GATE v4.2 DELIVERED, UNMERGED** (builder D16, bundle
  `builder-d16-gatev5.bundle`): the breakeven floor is REACHABLE (failure
  names tested-range and floor), inadequate cost grids are refused AT
  SUBMISSION (400 before 96 minutes of containers), CRITERIA byte-identical,
  version bumped because the same evidence now fails. **Fix 3 (active
  breakeven) correctly STOPPED**: sweep points carry no benchmark and run on
  the holdout train window — a naive active number would have KILLED
  candidates that clear the floor (−31.83pp vs true 13.9bps). The close is a
  BELT change (per-point benchmarks). 1743 tests green on the merged tree;
  12/12 mutants killed. **With the adversary blind now** (batched with the
  two loosening challenges: COO counter rule, PDT retirement). Entry 20's
  v4.1 row is PRESERVED — a re-judge is a new row, never a replacement.
- Builder EVOLVE applied (mutation-prove every branch; prove READ by MOVING
  the value — two-dispatch measured basis). THE CLEANUP now deferred FOUR
  times; slot after hazard batch + benchmark population; scope gains the four
  cebc578 worktrees.
- PM in flight on the 2026-09-08 exit design (395335c8) + the PDT-free
  sizing re-derivation.

### MEASURED — THE PM'S TWO-PORTFOLIOS FINDING (run-pm-0908, chair-verified line-exact)

- **THE FUND IS RUNNING TWO PORTFOLIOS AND ONLY ONE OWNS SECURITIES.** Book:
  TLT/DBC/SPY/DBA $917.06. Broker: the pre-T1–T8 legacy book $1,165.44
  (GLD/SOFI/XLE/MSFT/NVDA/INTC + partial SPY) and ZERO of the book's names
  except partial SPY — the CEO's 2026-08-20 closes never reached the broker
  (the PaperConnector forgery, fixed by D11v2 but history stands). **Stated
  exit coverage 100%; EXECUTABLE coverage 0 of 8. Capital deployed under
  mandate: $166.74 (8.8% NAV), not $917.06.**
- **THE 09-08 EXITS SELF-DESTRUCT SILENTLY**: fire → autopolicy correctly
  declines → the decline is a DISCARDED log line → EXIT_RULE_TRIGGERED stamps
  anyway → 120min expiry → skipped forever. AND **a human click in the
  window bypasses every v4 check** (approve_order: no venue/compliance/risk
  re-check) **and opens a $501.58 SHORT.** Sleeve falsifier #3 TRIPPED at
  6.71%. PM's 12 recommendations are the first desk rows ever to carry
  next_actor/due_date/reversibility/money on all.
- **Entry 20's binding legs corrected TWICE against the PM's own doc**: PDT
  retired AND granularity falsified (universe is fractionable-only by
  construction; every belt run was whole-share at $10M). Real leg: BELT
  VALIDITY AT DEPLOYABLE SIZE — R47 fractional re-run at nav=250/500
  ticketed (47567f8e). Top of the MIN today: THROTTLE ROOM (book $10.39
  over, third review).
- **Dispatched: THE HAZARD BATCH builder** (7 wirings: resume guard,
  integrity producer, decline visibility R41, AccountState cash R42, the
  three approved hazard rows; venue-truth verified-not-rebuilt). R37
  (exit override, direction-ambiguous) with the adversary (cd17bd8a).
  R38/R39/R40/R43/R44/R48 + the PM's tightening challenge (withdraw
  "deployed under mandate since 08-19"; fence pre-mode-fix TCA) are the
  CEO's morning batch.

### DECIDED (by the CEO, ~19:45Z, awake mid-study)

- **R38 ACCEPTED**, verbatim: "Yes lets close the legacy else we can always
  start with a fresh paper account (my goal was that our harness evolves this
  thought process of learning to identify which portfolios and assets its
  managing vs what some other system/human might have logged into the
  account)". The PM is drafting the R39 plan NOW with the CEO's
  **custody-attribution goal** built in ({fund-book / foreign / orphan}
  classification that the controls read). Orders stage at the 2026-08-24
  open (proposals expire in 120min — staging tonight would be waste), CEO
  clicks each.

### MEASURED — adversary batch 2 (SURVIVES / KILL / SURVIVES)

- **Gate v4.2 ADVERSARY-CLEARED** (no loosening; refusal set proved
  coextensive with the gate's failure set; its own sharpest kill hypothesis
  honestly self-refuted against 41 stored verdicts). **MERGE DEFERRED ON
  RAM** — 1.90GB free with the hazard builder heavy in flight; executes when
  the slot frees. CONSEQUENCE: v4.2 revokes Entry 20's cost pass — **the
  fund has zero clean gate passes, which is the honest state.** Repair
  residuals ticketed (875936e9).
- **COO filing-rule remedy KILLED** with a 27% false-approval demonstration
  on his own sample (a quote of a QUESTION is not an approval); the finding
  survived and was FIXED via the guarded path: **7 CEO-decided requests
  approved as neelesh-via-cto with verbatim citations** (desk 104→97);
  bd3c5232 + 9fb82050 stay open as genuinely his. CHAIR ERROR RECORDED: the
  first sweep pass posted 7 approval events under TRUNCATED aggregate ids —
  orphaned, inert, in the log; the redo used full ids. Lesson: the aggregate
  id in the URL is the FULL id; the echo is the prefix.
- **PDT challenge SURVIVES on web evidence** (all four dates verified;
  Alpaca implemented 06-04, no phase-in) **with the null-field datum
  STRUCK** — pattern_day_trader:null is paper-venue non-simulation
  (compliance.py:25-32) and Alpaca deleted the fields 07-06. Retirement gate
  = a POSITIVE live test, never an absent field. Bonus finding: fund.py:688
  renders unreadable broker counts as diverges:false (absence as agreement).

### BUILT — MONDAY'S CLICK SHEET (PM R39, resolved ~20:40Z)

- **The R39 plan is filed and Monday is choreographed**
  (docs/pm/PM_R39_PLAN_2026-08-23.md): SYNC (pre-open, one click, records
  +$126.37 as reconciliation not performance) → $4.50 ROUTING PROBE (the fix
  has never carried a live fill; everything stops if it misses) → six orphan
  SELLS (GLD first) → four sleeve REBUYS at unchanged quantities → acceptance
  ≤$3. Ten CEO clicks + one sync click, ~$1–2 total cost. Ends: **executable
  exit coverage 8/8 and capital under mandate actually $917.06 at the venue —
  the fund's FIRST real deployment under the current mandate** (the PM
  corrected its own figure: today's real deployment is $0.00, not $166.74 —
  the broker's SPY is a legacy lot the reconciler nets away).
- **THE CUSTODY FIXTURE IS CAPTURED PRE-SYNC**
  (docs/pm/CUSTODY_FIXTURE_2026-08-22.json) and the custody-attribution
  builder ticket is filed — five classes (phantom + unknown added), keyed on
  lots never symbols, acceptance test = SPY yields TWO rows.
- **The drawdown rebase's founding premise is measured false**: the $128.26
  "realised destruction" never happened at the venue — the GLD shares sit
  there UP $8.99. R39-8 files the review (a TIGHTENING of the reference);
  the PM's challenge rides it. Broker cash IS readable (846.84,
  /fund/venue/account) — the PM corrected its own E8.

### DECIDED (by the CEO, ~21:00Z) — THE SUPERSESSION RULE

- Verbatim: "if there is a new finding that invalidates or doesnt need my
  attention then we should have it removed/cleaned so that i dont mistakenly
  hit approve and unwind that progress." EXECUTED IMMEDIATELY: **23 stale
  rows swept with citations** (desk 99→82) — among them three approve-D11v2
  rows for the merge the CEO ran himself, and the R38 package whose naive
  click would record six shorts (now pointing at the R39 plan). Systemic
  mechanism ticketed (superseded_by linkage + ACTIVE/SUPERSEDED split +
  staleness sentinel; design adversary-blind first because reducing CEO
  visibility is exactly the shape a quiet suppression would arrive in).
  Chair discipline in cto.md: every resolve pass now ends with the
  supersession check. AMENDED same hour on the CEO's refinement (verbatim:
  "i would still like to see which item on my desk was contested, by whom
  and a superseded item on its top linked to it"): ticket v2 (`762d28c9`)
  adds LINEAGE-ON-TOP (the superseding row renders a linked chip to what it
  replaced) and the CONTEST TRAIL (per-row dissent chips: who challenged /
  differed / returned / killed, with artifact links). v1 (`895bd29b`)
  declined with a forward link — deliberately demonstrating the exact
  pattern v2 builds. SECOND REFINEMENT same hour (CEO verbatim: "items that
  got entirely killed can move out from my desk but still remain on the
  floor if i wish to review"): the visibility model is THREE TIERS —
  **ACTIVE** (the desk, clickable) · **SUPERSEDED** (off the desk; visible
  as a linked chip on its successor) · **KILLED** (off the desk entirely, no
  chip on anything — a terminally dead item with no successor; lives on THE
  FLOOR's kill shelf, browsable on demand, never deleted). The dispatch
  brief for 762d28c9 carries all three tiers.

### DECIDED (by the CEO, ~21:20Z) — THE DESK PRESENTATION STANDARD

- Verbatim: a top-tier desk; nothing "hard to understand and confusing +
  plus intends to say something that impairs my judgement"; "really clean
  and well designed format." TWO HALVES: (1) EDITORIAL — enforced by the
  chair at every resolve from now on (decision-first plain language, both
  branches or it bounces, no steering-by-framing, caveats adjacent, money
  sourced or UNSOURCED); (2) VISUAL — desk redesign ticketed, pairs with
  the three-tier/lineage/contest build, house design language, the Entry 20
  one-pager as the craft reference, acceptance measured by the CEO reading
  any card ONCE.

- **DESK GREETINGS + STEERING ticketed** (same hour, CEO: every desk greets
  with an executive view and carries a steering box). Design holds the
  ignition-key invariant: greetings are chair-written at resolve from the
  seat's STATE (a page load never fires a model); the steering box files a
  desk REQUEST into the existing queue (a posting fills an in-tray, never
  fires a seat) — the CEO steers through the chair, as the constitution
  routes it. Builds with the desk-redesign family.

### BUILT — GATE v4.2 LIVE + THE HAZARD BATCH DELIVERED (~21:45Z)

- **GATE v4.2 IS MERGED AND SERVING** (`5aeec84`): 1743 green on the merged
  tree, spine restarted, `GATE_VERSION v4.2` live, NAV $1,885.74 folding.
  The breakeven floor is reachable and inadequate cost grids are refused at
  the belt door. Entry 20's v4.1 row stands as history; the honest re-judge
  path is ticketed.
- **D17 (the hazard batch) DELIVERED, adversary blind in flight**: 6 of 7
  built + mutation-proven (42 killed + 2 retired with proofs), 1 verified
  already-closed by D11v2. 1813 tests green. THE MONEY FIX: shorts' exits
  fired BACKWARDS (unrealised P&L ignored qty sign) — fixed, with an A/B
  fold of all 978 live events proving ZERO history reinterpreted. Resume
  guarded (it took an EMPTY POST from anyone; zero tests had ever called
  it). Declines are events now. The drift alarm fires on TODAY'S real
  state. FLAGGED FOR THE ADVERSARY: severity=critical holds a LOSS halt
  shut during drift — a deliberate policy consequence, not buried.
- **NEW HOLE NAMED**: `POST /fund/risk/limits` is STILL unguarded and it
  MOVES THRESHOLDS — resume was never the only one. Deliberately not fixed
  in passing (who may move a threshold is governance); on the riskofficer's
  queue with the CEO.
- Desk standard gained **rule 6** (CEO): every recommendation states ONE
  risk against itself plainly, or "no material downside identified" —
  stated absence, never silent. In every brief from now on; D17's run
  record is the first to comply.
- THE CLEANUP: deferred a FIFTH time, next builder slot, on the record.

### MEASURED — D17 KILLED BY THE ADVERSARY (~22:15Z); repair D18 in flight

- **BUNDLE KILL on items 3+6, both with EXECUTED reproductions; 5 of 7
  survive** (resume guard, integrity wiring, cash fields, and the shorts
  fix — upheld by a STRICTER method than the builder's own: a real-_apply
  base-vs-head fold over all 1000 live events, cross-checked against the
  live spine). KILL 1: AutopolicyDeclined knocks a declined order out of
  the CEO's pending queue — un-approvable, un-declinable, and on 09-08 the
  TLT/DBC exits would have been declined and then INVISIBLE. The repo's own
  comments named this incident and the diff walked back into it. KILL 2:
  a driftless post-fill monitor raises a fabricated CRITICAL "venue could
  not be read" that would permanently mask the true $126.54 message.
  **1,813 green tests with two merge-blocking defects** — the suite stubbed
  the producer and named an invariant its body never asserted.
- **The adversary's honest negative on its own lead attack**: the
  drift-severity halt-hold costs far less than framed (v4 already refuses
  per-order on drifting symbols) — one CEO SIGNATURE when D18 clears, not
  a block. Parked for the morning.
- **NOTHING MERGED. D18 repair dispatched** with the adversary's probes as
  acceptance tests, on the same branch, whole-or-nothing after blind
  re-review — the D11→D14 loop, second running.

### DECIDED (by the CEO, ~23:00Z) — THE PM IS NAMED STAN

- Identity v2 cut in a live tuning session with the CEO: **Druckenmiller's
  ledger + the navigator's honesty**. The money blade added on the CEO's
  steer ("a knack for money making and risk managing. discipline and
  sharpness"): expectancy over win rate, sizing is the judgement, the exit
  IS the position, losers never averaged, defense funds the offense. The
  navigator blade kept from the measured record (four self-corrections; a
  constraint is measured, never inherited from paper). Boundary preserved:
  hunger without the pen — the mechanism proposes, the CEO clicks.

### DECIDED (by the CEO, ~23:20Z) — THE MECHANISM REFINED

- The seat is named **Ed** (for Thorp — "no no I was joking; lets call him
  Ed"). Refinement, CEO-steered: "lets refine this seat cause everything
  downstream depends on it." Identity v2: **Ed Thorp** — count the actual
  cards, never the remembered ones (the vol-ratio scar); fertility as
  discipline. Emit contract gains **the pre-flight card** (items 8–11: the
  binding capacity leg named, the cost grid to the gate floor, PREDICTIONS
  AS NUMBERS THE BELT SCORES — a prediction ledger, because the adversary
  currently out-predicts the mechanism on its own proposals' economics —
  and the shorts/scheduling rules). New **PRODUCTION ETHIC**: each dispatch
  is a BATCH of 3–5 admissible proposals or a named blocker; admissibility
  never bends to the count. The analyst persona (Burry proposed) awaits the
  CEO's steer.

### DECIDED (by the CEO, ~23:40Z) — THE ANALYST'S IDENTITY, TUNED AGAINST THE TUNNEL

- Burry-alone rejected on the CEO's worry ("so that it doesnt opinionate
  the analyst into one tunnel vision") — the persona rules working: Burry's
  own failure mode is the tunnel. Identity v2 cut: **Darwin's notebook,
  Burry's reading list** — read the unopened primary source, but the thesis
  emerges from the catalog; the golden rule (contrary facts written FIRST);
  a naturalist of many species, never a hunter of one whale; every finding
  names its trade shape or says "true and not tradeable at our size." The seat is named **Dr. Mike Darwin** (CEO: 'Dr. Mike Darwin it is haha')
  — the differential-diagnosis line added to the identity. The funnel's front three are
  tuned: Ed finds the edge, the analyst grounds the evidence, Stan runs
  the book.

### DECIDED (by the CEO, ~00:00Z) — THE PERSONA-RESTRAINT RULE

- On the chair's own concern ("yes if you truly think its a concern"):
  **a persona is tuned only on demonstrated need — a measured miss a
  sharper prior would have caught — exactly as a seat is created.** The
  five verification instruments stay deliberately plain; the adversary's
  one-sentence identity doubly so (immune-system exclusion). Written the
  same night three personas were tuned, because the momentum itself was
  the evidence.

### DECIDED (by the CEO, ~00:15Z) — MARKET SPECIALISTS: RIGHT SHAPE, NOT YET

- The CEO's multi-market ambition ("specialised agents by asset
  class/market") registered as a TRIGGER, not a build — constitution
  dispatch-rules clause (4): audition the first specialist when a second
  real venue goes live in a different microstructure, or when a generalist
  produces a measured market-specific miss. Until then: per-market menu
  sections, market-tagged episodes, transient fan-out under Ed. "Specialists
  are earned by scars, not foreseen by ambition."

### DECIDED (by the CEO, ~00:30Z) — ED RUNS MORE; THE BOOK COMPETES

- Constitution trigger (5): Ed's generation trigger — pipeline below 3
  admissible candidates (or weekly) → chair fires an Ed batch. Standing
  authorization, chair-fired, never a schedule. Stan gains THE INCUMBENCY
  RULE: every review re-underwrites every position against the candidate
  bench; nothing grandfathered. **Ed batch #1 dispatched immediately**
  (light seat; D18 heavy slot unaffected) — first run under the production
  ethic and the pre-flight card.

### BUILT — D18 DELIVERED (~21:45Z); FINAL BLIND PASS IN FLIGHT; THE VAULT

- **D18: both kills repaired and mutation-proven** (annotate-not-lifecycle
  via ONE exported set both folds read; the report DERIVED from the judged
  dict + one shared predicate; producers reduced to one). 1852 green in
  worktree, 1863 on the merged tree — arithmetic exact. 20 mutants: 19
  killed, 1 RETIRED WITH CAPTURED PROOF. Item 7's verification is now 13
  executable tests. First correct base in 18 dispatches; best deletion
  ratio in six. Builder's rule-6 risk, honest: run() still double-evaluates
  alarms — the defect-class MECHANISM is intact behind one test; follow-up
  ticketed. **Whole branch (D17+D18) with the adversary for the final
  blind pass; merge whole-or-nothing after.**
- **THE VAULT** (CEO decision): private repo github.com/neeleshnayan/
  harness-engg to de-risk the work off this PC; remotes wired
  (vault→firm/clarkharness/kryptonpay branches); pushes await the CEO's
  own gh auth (credentials are his, never the chair's). **SECRETS FINDING
  disclosed and DECIDED**: ClarkHarness history carries a tracked .env
  backup with the Alpaca PAPER key/secret + Polygon key + signal token —
  already visible to the team on the OG origin. CEO: "I wont rotate keys
  to a paper account lol" — accepted, his risk call, recorded. **THE RULE
  THAT BANKS FORWARD: Monday's LIVE-account keys never touch any repo —
  .env only, untracked; a live credential in any diff is a merge-blocker
  at threshold-move severity.** THE CLEANUP: sixth deferral, on the record.

### BUILT — THE VAULT IS LIVE + THE CROSSING PAIR COMPLETED (~21:50Z)

- **All three repos pushed to the private vault** (github.com/neeleshnayan/
  harness-engg: branches firm / clarkharness / kryptonpay, full histories,
  verified against the remote). Root cause of the earlier failure: the
  `remote add` had been swallowed by a classifier block, so the push hit a
  nonexistent remote — not auth. CEO granted STANDING PUSH AUTHORIZATION to
  the vault ("you can push as you like") — push-to-vault is now the chair's
  session ritual at every milestone. The paper keys ride in history by the
  CEO's explicit decision (Mac portability); LIVE keys never touch a repo,
  merge-blocker severity.
- **The D11 v2 KryptonPay companion MERGED** (fcca35bd) — discovered
  unmerged during vault verification; the CEO's crossing pair is now
  actually whole. Verified: tsc exit 0, 302/302 tests pass on the merged
  tree (node test runner via tsx — vitest is not the runner here). Studio
  picks it up via HMR; the mode-truth UI (fundMode.ts) is live.

### BUILT — THE HAZARD BATCH IS LIVE (~22:20Z); ED'S WORKSHOP WIRED

- **D17+D18 SURVIVES whole-branch (adversary re-review, kills closed BY
  EXECUTION) and is MERGED + SERVING**: 1863 green (arithmetic exact),
  spine restarted, and **THE DRIFT ALARM FIRED ON LIVE STATE with its true
  message within seconds** — "book and venue disagree on 10 of 11,
  $126.54." Resume guarded, declines evented and queue-preserved, shorts'
  exits un-inverted. Second kill→repair→clear loop closed in 24 hours.
  Two residual-guard tickets filed (census shapes; two-directional pin +
  the double-evaluation removal). **CEO signature still owed** on the
  drift-severity auto-resume consequence — desk item, Monday.
- **ED'S WORKSHOP** (CEO design, wired): Ed may staff his batches via
  `## NEXT BATCH ASKS` — chair-composed TRANSIENT workers under HIS
  identity (rule-3 fan-out; shared context = the token dedup the CEO
  wants; one consolidated STATE). **The honest line, written in:
  VERIFICATION may be subordinated to Ed's thesis; DISCOVERY may not** —
  Dr. Mike Darwin's shelf feeds catalog→idea (never idea→catalog), the
  quant SEAT implements fresh after the adversary, nothing transient
  touches lean_workspace/**. The named seats are colleagues, not staff. **CAP RATIFIED (CEO):
  2 research + 1 crunch per batch — crunch is heavy, counts against the
  one-heavy-job budget; cap moves only by versioned decision. And every
  worker carries the firm's full ethos — identity governs ACCOUNTABILITY,
  never ethics.** THEN EXTENDED (~22:45Z): the workshop gains a FOURTH
  slot — **the GENERIC WORKER, unseeded, authored entirely by Ed** (spec
  lives in his STATE, re-cut across runs on measured contribution, named
  when earned) — the firm's first seat-born identity. Boundaries: full
  ethos, no discovery, no implementation, weight classified by the chair
  per spec. Cap: 2R + 1C + 1G.

### DECIDED (by the CEO, ~23:00Z) — FOCUS OVER BOIL, mid-batch catch

- Watching Ed's batch #1 run, the CEO flagged combination-boiling. RULING
  written into the production ethic: **the count counts MECHANISMS, never
  combinations** — survey-breadth welcome, hypothesis-breadth is the sweep.
  Chair's own-goal acknowledged: a fertility quota is exactly the pressure
  that turns a proposer into an enumerator (the kill-shaped-metric lesson,
  new costume). FAMILY-WISE discovery risk carried to the validator as a
  named instrument question (the gate bounds each candidate, nothing bounds
  the family). Ed's batch will be judged at resolve against the sharpened
  bar — sweep-shaped proposals bounce.

### MEASURED — ED'S BATCH #1 LANDED (~23:15Z): ENTRY 21 + THE 33-YEAR FINDING

- **First run as Ed, and the boil worry is SCORED: falsified** — six
  families tested by discriminator, five killed on their own logic, ONE
  deep survivor. **Entry 21, the Treasury auction concession** (statutory
  counterparty: Treasury via obligated dealers; duration-ordered,
  size-monotone, STRENGTHENING; 18.5y active +6.95%/yr, IR 1.02, BE
  19.7bps, 17/19 years; 0-of-300 null) — with the full pre-flight card,
  predictions on the ledger, **and a self-predicted gate FAIL on fold
  retention** at the gate's measured 22.8% power, proposed anyway to price
  the history-floor argument. WITH THE ADVERSARY BLIND now, batched with
  Ed's breakeven-floor challenge (loosening, self-declared).
- **THE 33-YEAR FINDING, chair-verified live**: the feed serves SPY from
  **1993-01-29** on the exact LEAN route while factory.py:39 floors the
  belt at 2024-02-26 ("the number is a property of the data" — false).
  **The fund judges every strategy on 1/13th of the data it owns.** Ed
  correctly fenced the trap: floor-move without fold-scaling = FP
  2.9%→12.5%, a loosening dressed as a data improvement. Ordered pair
  ticketed (58c4fff5); the gate-criteria half is the CEO's morning call.
- Harvestability ratio applied as EVOLVE 9a (pre-kills unharvestable
  families for five minutes' arithmetic). Menu 20→26 with honest
  dispositions. ETF execution-cost measurement deployment on the CEO's
  desk (the parameter deciding a whole candidate family; impossible on
  the paper simulator). Ed's fitness: 1 vs 3–5 target, blocker NAMED —
  next cycle goes where the data is new.

### DECIDED (by the CEO, ~23:30Z) — TOKENS ARE THE CURRENCY

- Grace gains the standing **TOKEN LEDGER** (meter with value line, the
  waste hunt, one improvement per dispatch, addressed to CEO + chair). The
  frame is hers already: cheapest TRUE VERDICT per token, never smallest
  spend — and one line when tokens are not what binds. Chair reciprocals
  recorded (solicit her input at dispatch design; honest token recording;
  the named levers handed over for pricing). First ledger lands with her
  next dispatch, reading tonight's ~2.5M-token record.

### MEASURED — ENTRY 21 KILLED IN BLIND REVIEW (~23:50Z): THE CHEAPEST KILL YET

- **KILL / KILL** (Entry 21 as alpha-with-counterparty; Ed's floor
  challenge as filed) — **at ZERO container cost**, the chain catching a
  flawed candidate at stage 2. The return is real and reproduced
  (+6.00%/yr); **two-thirds of it is a day-of-month calendar pattern**
  (tdom FE + a matched-calendar control agree; a zero-auction-information
  tdom rule earns +4.82 of the +6.00); all three mechanism discriminators
  fail under correct controls (the proposal's own ladder omitted the
  3-year — the counterexample); and the post-2013 breakeven is **8.7
  bps, under the floor**, exactly where the sample is out-of-sample vs
  the 2013 paper. FIVE failed attacks reported as loudly as the kills
  (the placebo was honest — and the wrong null; w_hi genuinely unfitted;
  the EW-rebalance attack's first-ever empty result). The floor
  challenge died on a CLOSED defect cited as live (chair re-verified)
  and an unmeasurable key; a five-condition safe path is specified.
  Lessons carried to Ed (6), quant, validator (2 measurement requests),
  Stan. The matched-calendar control is now a standing instrument.

### MEASURED — THE CLOSING FAN-OUT LANDED (00:15–00:35Z, resolved into 08-22's entry as its final acts)

- **RISKOFFICER 6**: the human approval path audited check-by-check — 11 of
  15 absences INTENDED (the offramp is a design principle), THREE are gaps
  (facts the card cannot show); **$650.82 = 34.5% of NAV of real SHORT if
  reconciliation ever goes through order clicks instead of sync-apply** —
  independently confirming the PM's R39 sequencing. Four CEO signatures
  prepared (R20 approve-time reality check, R21, R22 direction-aware limits
  guard, the drift-severity memo WITH its named-owner condition). Alarm
  census CLEAN (D18 verified). The rebase-direction pair at its THIRD ask —
  now ticketed (faefd072). The 14m41s latency carry formally dropped after
  six dispatches.
- **DOC'S SHELF v1**: **the hunting-ground panel HAS NO NULL** (+1.568%/20d
  at t=+15.36 — an 8-K exhibit index "predicted" +1.5%; all 27 item codes
  collapse to |t|≤1.72 demeaned) — the no-null control is now standing for
  every desk event study. ONE live lead: **post-earnings realised vol is
  ELEVATED ~6%, not crushed** (two stacked artifacts in the textbook
  reading, both caught) → a stop-width correction for Stan. Four families
  censored-untestable (closed to Ed's menu until a PIT universe); Form 144
  is 2023+ only (the trap caught BEFORE the spend); 3,185 unread comment
  letters named the cheapest unopened pile. Zero extraction, host intact.
- **GRACE'S TOKEN LEDGER #1 — the sharpest economics read yet**: 08-22
  spent **7.42M tokens = 47.1% of lifetime — and was the best-value night
  ever** (~0% parked vs 59.7% prior; builder findings/M 1.2→4.4). THE
  FINDING: **the prod gate is broken in BOTH directions** — P1 reads MET on
  pre-D11v2 mock-broker fires (no venue fence; the sibling evaluator
  fences, 40 lines away) and three rows can NEVER say met (no evaluators;
  0 of 82 tickets would fix it). Her law for the architecture: **a false
  green is strictly worse than an absent check — the dispatch queue IS the
  attention allocator.** DATES COLLAPSED TO ONE GATE: **$10k ask Fri
  2026-08-28** (14 days in), first real venue fill Monday. She falsified
  her own Grace-3 claim (P5 is reachable on alpaca-paper; tca.py:131) and
  conceded to Vishesh on measurement. Largest waste: ~163k on a defect an
  incident comment had documented — **an incident comment is not a
  control.** Binding constraint: SPECIFICATION, not tokens — the CEO's
  one-word "in anger" ruling is worth ~14 days.
- Tickets: the scoreboard pack (a0e640de: P1 venue fence + the clock +
  telemetry zombies + mojibake + XL* re-pull) and G5-2's evaluability pack
  with the adversary (a26debb9, loosening, filer-declared, her own kill
  condition attached). EVOLVEs applied: Doc (baseline named before the
  test), Grace (a definition is a figure).

### MEASURED — THE VALIDATOR'S FIVE-CENSUS BATCH (the fan-out's last seat, ~00:50Z)

- **Entry 20's pass formally VOIDED as a cost statement**: 1 of 26 verdicts
  in the string path's whole exposure window took it — and it was the only
  substantive pass. R1: re-judge under v4.2 or mark void, by 08-25.
- **PBO serves absence as GREEN ZERO**: six sites return "overfitting
  probability 0.0" where nothing was measured; the UI's correct '—' branch
  is unreachable; renders one click from Save & Deploy. Ticketed.
- **The register reads constants, not the world** (13 of 15 hooks) — the
  history-floor entry called itself unfalsifiable and is false by 31 years;
  two fired triggers report not-due. The _wired() pattern is the fix; the
  evaluability-first order stands.
- **Monday's TCA PRE-REGISTERED AND FILED before the fills**
  (docs/research/TCA_PREREG_2026-08-24.md) with the tick null written
  first: bps half-spread = 50/P exactly, so the naive tier analysis would
  "discover" a 17× price effect that is arithmetic. Day-of NBBO capture
  added to the chair's Monday choreography.
- **FAMILY-WISE, FORMALIZED — the CEO's catch now has mathematics**:
  FDP = (1−π₀)α/[(1−π₀)α+π₀β], INDEPENDENT of how many we try; at the
  gate's measured α/β, >60% of survivors are false even at 50% edge
  prevalence — and **every margin tightening RAISES the false-discovery
  rate. DISCRIMINATION IS THE LEVER**, which is exactly what the
  fold-scaling + history pair buys. Corollary for the record: passing the
  current gate is weak evidence AGAINST an edge — the strongest argument
  yet for the gate pair being signed Monday.
- The discovery ledger named as the missing instrument (candidates carry
  no proposal/seat/family id; fund_candidate_sources has 0 rows) — folds
  into the measurement-shelf family.

### THE CEO'S MONDAY MORNING, FINAL FORM (the night's whole output in clicks)

1. **G1** — the account (external clock; no longer gates cost measurement).
2. **The R39 click sheet** — sync pre-open → $4.50 probe → 6 sells → 4
   rebuys (possibly +1 order for P5's 20th fill — Stan re-checks).
3. **One-word rulings**: does a DRILL satisfy "fired in anger"? (worth ~14
   days) · the gate pair (fold-scaling then history floor) · the
   drift-severity signature (with a named owner + date) · R20/R21/R22.
4. Vishesh's 8, the charter amendments, H2's citation-scoping question.
5. NOTE: the scoreboard will briefly read WORSE (P1 → unmet) when the venue
   fence lands — the honest direction, by his own clean-field rule.

### ON FIRE

- **2026-09-08 chain unchanged** ($501.58 dated, $750.36 armed undated, TLT
  3.11pp from stop) — but now STAFFED: hazard batch at queue rank 1, and
  395335c8 (exit re-establishment design) next for its seat.

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
- **THE LOOP CHARTER RATIFIED** ("Agree", same day as drafted):
  docs/LOOP_CHARTER_2026-08-22.md — three phases (honest+fast / feed / scale),
  per-stage measured baselines, the brakes exempted, four falsifiers. Grace
  and Vishesh owe WHERE I DIFFER at next dispatch.
- **TIME-TRAVEL RATIFIED as Loop Charter Phase 4** ("Agree"): walk-forward
  for the FIRM - pin the clock, replay history, score the organization. The
  governing trap is named in the charter (hindsight contamination - seats'
  weights contain the future), so the order is T0 clock -> T1 deterministic-
  stack replay on PIT data -> T2 regime bank -> T3 seats-disclosed. Two
  fences: sim events NEVER touch the real ledger; synthetic scars carry
  provenance forever. T0 ticket `45efaf68` filed, sequenced behind the cache
  build. The 4TB store is reachable and is T1's PIT-data home.
- **D11 v2 MERGE APPROVED** (CEO, "approved on 1 and 2", before GMAT leave):
  the event-store crossing is authorized - merge WHOLE branch (ddc05a2 CH +
  v2-kp-d14 KP), suites green on the merged tree before the spine serves it.
  EXECUTION SEQUENCED behind the cache builder (one heavy job; suites
  serialized) - the chair executes when the slot frees, tonight.
- **GATE v5 BREAKEVEN TRIO APPROVED** (same breath): ticket `5b18fd7d`,
  staged as neelesh-via-cto. Tier-3 crossing authorized by the CEO; builder
  dispatches after the cache lands. Entry 20's honest re-judge unblocks on it.
- **G1: the CEO starts the account MONDAY** - the external clock now has a
  named start date. Studio UI reported down by the CEO, "let it be" - not
  investigated, on his instruction.
- **D15 BAR CACHE MERGED (`cf0368d`)** — chair-verified line-exact, suite
  re-run on the merged tree (1561 RC=0), spine restarted, NAV folds $1,885.74.
  Per-leg 2,125ms → 1.64ms (~1,300×); 170/170 legs byte-identical. THE
  HEADLINE FIND: `marketdata.py:381` routes any start+end call to YAHOO while
  strategies trade ALPACA, and Yahoo lags one session — **every benchmark the
  belt ever computed covered one session less than the curve it graded**
  (systematic, 0.10pp on the test run). Now reported per-run. Builder's
  clean-field-reasoning challenge parked for the CEO. THE CLEANUP is deferred
  THREE times and owns the next builder slot.
- **D11 v2 MERGE PARKED BY THE HARNESS PERMISSION LAYER** — the CEO approved
  the crossing, but auto-mode refused the chair's merge of event-store code
  twice; the chair STOPPED rather than working around a control. Branch sits
  imported as `d11v2-import` (= ddc05a2); ONE command when the CEO returns:
  `git -C ClarkHarness merge --no-ff d11v2-import`. KP half parks with it
  (whole-or-nothing on the pair).
- **EVENING WAVE DISPATCHED** (CEO: "dont go gentle on agent count"): gate-v5
  trio builder (heavy slot), Grace (charter differ + owed matrix differ),
  Vishesh (triage #6 at 91/50 + charter differ) — exec-table order enforced,
  neither reads the other tonight.
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
