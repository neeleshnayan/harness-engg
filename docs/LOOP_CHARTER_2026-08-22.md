# THE LOOP CHARTER — the plan of action for the research loop

**Chartered by the CTO chair on the CEO's instruction, 2026-08-22, verbatim:
"I want to charter our plan of action to make this loop more efficient. Our
goal become the world's top hedge fund at $2k [cash is just relative, its how
we run the business that matters]."**

**Status: RATIFIED by the CEO 2026-08-22 ("Agree"), same day as drafted.
Still routes to Grace (the clock) and Vishesh (what cannot be taken back) for
`## WHERE I DIFFER` at their next dispatches — ratification makes it binding,
not beyond question; decisions are provisional, and a charter is the largest
decision of all. A surviving disagreement produces a dated amendment.**

---

## What "top at $2k" means, so the plan optimises the right thing

Cash is relative; process is not. The claim this firm is building toward: **at
any AUM, run the loop — idea → blind attack → implementation → belt → gate →
deploy-or-kill → learning — with more honesty per cycle and more cycles per
week than anyone, and prove it from the record.** The scoreboard is the CEO's
five preconditions plus the team metric's three legs. A $2k fund cannot win on
returns in dollars; it can win on the only thing that scales to $10k and
beyond: **the loop itself.** That is the business we run.

## The loop today, measured stage by stage

| Stage | Today (measured) | Binding? |
|---|---|---|
| 1 Generation | ~1 candidate/week vs the 3–5 funnel target | **After the cache lands, THIS binds** |
| 2 Blind attack | ~hours, LIGHT seat, batchable | No |
| 3 Implementation | ~one quant dispatch per algorithm (hours) | Second, after generation |
| 4 Belt | 96.4 min/candidate; ~85% is re-fetching data (170 legs × 2.4s × 22 containers) | **Today's binder — fix in flight** |
| 5 Gate | v4.1 with 3 known pass-favourable defects; breakeven floor unreachable | **Quality binder — a fast loop through a lying gate is a defect factory** |
| 6 Deploy/measure | zero real fills ever; account unopened; Tier-0 authorized but unused | **The only stage with an EXTERNAL clock** |
| 7 Learning | BINDS + seat memories + Lab (new); selection loop young, zero surviving amendments yet | Watch its falsifier |

Lifetime context: 40 gate verdicts, **one** substantive pass (today). Meter:
65 runs / 12.02M tokens, builder 42.6% of spend.

## The plan — three phases, each with the number that proves it

### Phase 1 — make the loop HONEST and FAST (this week)

1. **Belt data cache** (ticket `252bce7b`, builder IN FLIGHT). 96 → ~20–25
   min/candidate. Merge condition: bit-identical verification, clean-field
   rule. *Proof: the measured before/after on the test candidate.*
2. **Gate v5** — excess returns end-to-end, the three breakeven fixes from
   `run-quant-entry20`, active-return statistics beside PSR, the per-run
   benchmark-window check. Speed without this is noise at higher frequency:
   Entry 20 showed every defect in the gate leans pass-favourable. *Proof:
   Entry 20 re-judged under v5 — whatever the verdict, it will be true.*
3. **G1 — the account** (CEO, external clock, ~1–3 business days). The only
   stage no agent can run. Every week it waits is a week of stage 6 at zero.
   *Proof: the clock starts.*
4. **The Lab** (ticket `66912f40`) — one-pager per experiment, Donna's lane.
   Learning capture becomes an artifact, not a memory. *Proof: the next
   candidate's one-pager exists without the chair hand-building it.*

### Phase 2 — feed the loop (next week)

5. **Generation batching.** With the belt at ~25 min, stage 1 binds. The
   mechanism has a premia/alpha menu of entries already written; dispatch it
   in BATCHES (3–5 proposals per run), adversary attacks them as a batch, the
   quant implements survivors. LIGHT seats — parallel under the cap. *Proof:
   leg 2 of the team metric hits 3–5 candidates/week on the belt.*
6. **The scaffold library** (quant). Entry 20's universe handling, benchmark
   plumbing, k-slot tilt engine are reusable components; an algorithm becomes
   config + signal logic. *Proof: implementation of candidate N+1 measured in
   hours, not a full dispatch.*
7. **First real fill** (~2026-08-28 if G1 starts now): one CEO-clicked Tier-0
   deploy with a pre-committed, strategy-owned loss-stop. Stage 6 goes from
   zero to measuring. *Proof: the first fill whose cost is real information.*

### Phase 3 — scale the loop (when the RAM lands, ~31 GB)

8. **Re-open the host budget** — versioned amendment, never silent: parallel
   candidates on the belt (grid points of DIFFERENT candidates concurrently),
   two heavy jobs. The 1.28 GB collapse falsifier gets rewritten against the
   new ceiling. *Proof: two candidates through the belt in one afternoon
   without a host event.*
9. **Graduated deployment live** — readiness matrix + entry envelope
   (adversary-blind first, it is a loosening) so survivors have somewhere to
   go besides a doc. *Proof: the first S1→S2 transition on matrix evidence.*
10. **The selection loop earns its keep** — first amendment surviving both
    chair and seat review, or its falsifier fires (two weeks, dated from
    2026-08-22) and we dismantle it honestly. *Proof: either outcome, on the
    record.*

## Phase 4 — EVOLVE against history ("time-travel") — AMENDED IN 2026-08-22

**CEO instruction, verbatim: "say we go back in time to any given date. That
becomes today. Now our entire machinery navigating to nail it down as time
passes and learn here we failed, what broke, what we missed and how we could
have done better. Evolution across time helping us gain muscle that a human
firm that ran over 50yrs ran but forgot." Ratified same day ("Agree").**

Walk-forward for the FIRM: pin the clock to a historical date, run the
machinery forward, and score the ORGANIZATION — did the halt fire, did the
exits execute, did the risk engine see it, what did the desk miss and when.
A scar factory running on history instead of waiting for the future to hurt.

**THE NAMED TRAP, governing the whole design: hindsight contamination.** The
seats are LLMs whose weights contain the future; run the bench naively in
sim-2020 and you measure memory, not judgement. Unfixable at the seat layer —
so the phases order around it:

- **T0 — THE CLOCK** (builder ticket, near-term): one injectable `now()` the
  whole harness reads. Also a bug-class fix — three standing defects
  (test_end wall-clock, benchmark truncation, EoD misfire) are all "something
  read the real clock when it shouldn't." *Proof: pin the clock in a test and
  the covered window obeys it.*
- **T1 — replay the DETERMINISTIC stack** (gate, risk engine, exit mechanics,
  autopolicy, drawdown ladder — code has no hindsight) through named regimes
  (2020 crash first) on POINT-IN-TIME data including delisted names — without
  PIT membership it is survivor-fiction. GATED on the PIT data question (the
  4TB store is the candidate home). *Proof: a controls-fired-in-anger report
  for a regime we never lived — precondition-grade evidence before the first
  real dollar.*
- **T2 — the regime bank**: every candidate re-judged across named regimes as
  a standard gate output (Entry 20's fold-3 Oct–Feb failure becomes a class
  of question, asked always).
- **T3 — seats in the loop**, contaminated AND DISCLOSED: data restricted to
  as-of, scored on process compliance (demanded the right evidence, sized
  within mandate) — never on prescience, which is free for them and worthless
  to us.

**Two fences, regardless of phase:** sim events write to a SEPARATE,
DISPOSABLE ledger — nothing synthetic ever touches the real event log NAV
folds from. And every artifact born in a replay carries `synthetic-scar`
provenance forever — a synthetic scar may bind exactly like a lived one, but
it may never be CITED as a lived one.

### THE EXPERIENCE LAYER (added same day, CEO instruction, verbatim: "newer
### experiences shouldnt override older ones since each period comes with its
### own unique learnings, strategies and blindspots. Our present operating
### memorandum has to be a distill across those experiences.")

The point of the replay is not the report; it is the EXPERIENCE LAYER each
seat accumulates — the thing senior humans are paid for. Three layers per
seat, replacing flat append-only STATE growth:

1. **EPISODES** — one per lived-or-replayed period, APPEND-ONLY AND IMMUTABLE,
   tagged by regime. Each records what the period taught, what worked, and
   what it made the seat blind to. The findings-doc rule applied to
   experience: never edited, a re-visit gets a new section.
2. **THE OPERATING MEMORANDUM** — the distillation, the layer a seat reads
   first. Versioned and DERIVED: every line cites the episodes supporting it.
   **Conflicts between eras are preserved as conditionals, never resolved by
   recency** — "buy the panic (2020) / the panic is the information (2008)"
   stays as a pair with regime conditions. The tension IS the seniority; a
   memory that lets the newest lesson win produces a junior with recent
   opinions regardless of how long it has run.
3. **THE DISTILLATION DIFF** — when an episode lands, the memorandum is
   re-cut and the DIFF is the reviewable artifact (chair review, like BINDS).
   Guard rail: **a lesson leaves the memorandum only by NAMED RETIREMENT
   with a reason — never by omission.** Silent dropping in a distillation is
   quiet loosening's memory-layer cousin, and it is forbidden the same way.

This also resolves the seat-memory scaling problem: a seat reads its
memorandum plus regime-matched episodes, not its whole history.

## What does NOT speed up, ever

The control layer. Blind review stays blind (a batched adversary still never
sees authors' reasoning). The CEO's clicks stay the CEO's — volume may fall,
authority never. Verification stays before action. The one forbidden move
stays forbidden: no efficiency argument ever loosens a control quietly. **The
loop gets faster; the brakes do not get lighter.**

## What would change this charter's mind

- The cache verification fails bit-identical → Phase 1 re-plans around
  parallel fetch only, and the 20–25 min claim is struck.
- Generation batching produces quantity without quality (adversary kill rate
  on batched proposals materially exceeds the singleton baseline) → revert to
  singleton dispatches with a written reason.
- A host event under Phase 3 parallelism → straight back to one heavy job,
  the standing falsifier.
- Grace or Vishesh files a `## WHERE I DIFFER` that survives the CEO's read →
  this document gets a dated amendment, not a quiet edit.

---

## AMENDMENT 2026-08-23 — THE REFERENCE FIRMS, OPERATIONALIZED

**CEO direction, same day (verbatim): "firms like Janestreet and Citadel and
Millenium... one thing I like is the process of information extraction and
flow from research to execution that they have nailed. our benefit should
leverage the pieces that make them great and morph our benefits on top" —
and, on the chair's distillation: "Agree we need to embody and
operationalise it."**

### What each nailed, and what we take

- **Millennium — isolation + ruthless reallocation.** Independent bet
  generators; information flows UP (risk, P&L), never ACROSS; capital
  follows measured edge fast and unsentimentally. WE TAKE: the up-never-
  across flow (blind review; independent origination) and the reallocation
  reflex (the incumbency rule — nothing on the book is grandfathered).
- **Citadel — the shared platform.** Point-in-time data as a firm asset;
  a standard pipeline from idea to testable implementation; execution
  measured to the basis point feeding research. WE TAKE: the pipeline
  (grammar → adversary → belt → gate) and the single shared substrate
  (the measurement shelf, the bar cache, the knowledge graph — nobody
  re-derives).
- **Jane Street — knowledge compounds in the firm, not in heads.** No
  stars; one obsessively improved machine; "we could be wrong"
  institutionalized. WE TAKE: the compounding machine (the knowledge
  graph, the experience layer, BINDS/EVOLVE) and the institutional
  humility (every artifact falsifiable; the gate exists so we do not
  repent).

### THE SYNTHESIS ONLY WE CAN RUN

Millennium's edge (isolation) and Jane Street's edge (sharing) are
opposites, because humans cannot share data without leaking conviction —
two PMs who compare notes end up correlated. **Agent seats can be
genuinely firewalled while sharing a graph that carries verdicts-with-
citations and never enthusiasm.** Independent origination + shared
measured truth is this firm's structural edge, and it is why the KG guard
(verdicts, never recommendations) and the exec-table order are not
etiquette — they are the moat.

### Our morphs, stated without romance

We cannot out-buy their data, out-hire their quants, or out-execute their
microstructure. What we have that they structurally cannot: **perfect
institutional memory** (no alumni carry the edge out; every kill queryable
forever), **true blind review** (zero social cost, structurally enforced),
**reallocation without ego** (killing a family is a Tuesday, not a
firing — so it happens on time), and **process iteration at commit speed**
(their org changes take quarters; our seat files changed four times today,
each on a measured basis). At their scale, data advantage means buying
feeds; at ours, **the proprietary dataset is our own experiment history**,
plus the one raw corner where we can be first readers (the unread
filings/letters corpus).

### THE OPERATIONAL METRIC THIS AMENDMENT ADDS

Every reference firm is defined by a research→execution loop that runs
millions of cycles a day. Ours has run ZERO — the book is paper, the
fills are none, the TCA loop is a pre-registered instrument that has
never taken a measurement. Therefore:

**LOOP-TIME becomes a first-class number: the wall-clock from hypothesis
filed to executed, measured, fed-back trade.** Grace's date question
gains its sharper form — not only "when do we deserve $10k" but **"when
does the full loop run in under a week."** Every build from here is
judged partly on whether it shortens loop-time; the first loop closes
with Monday's first real fill. The chair records loop-time per candidate
in the knowledge graph once candidates begin reaching execution.

### What would change this amendment's mind

A measured case where loop-time optimization pressures a control (a
verification skipped, a blind compromised, a click bypassed to go
faster) — the brakes clause above already answers it: the loop gets
faster, the brakes do not get lighter. Any such event strikes the
loop-time metric back to advisory pending a written re-decision.
