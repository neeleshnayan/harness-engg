# CODE DISCIPLINE — the janitor program

**Chartered 2026-08-27 by the CEO, verbatim:** *"What we also need is code
discipline: old dead code being removed, duplicated parts that can override
each other found and fixed before it bites us in production and remove tech
debt."*

## The three debt classes, each with this firm's own scars

### 1. THE OVERRIDE CLASS — one rule, N derivations (the one that bites in production)

The CEO's "duplicated parts that can override each other" is this firm's
most-paid-for defect family, already a FAILURES.md class ("the two-truths
rendering"), and every instance was found *after* it bit:

- the CEO's page and the spine disagreeing by **eleven rows** the moment a
  shared rule was touched;
- **routing v2**: the router moved, two KP predicates kept v1 semantics —
  13 live rows in zero lanes on the CEO's page (adversary, night2);
- the desk counter not consulting the router it published (the chair's own
  commit, same night);
- two reconciliation tolerances (`reconcile._TOL` 1e-6 vs
  `engineledger._TOL` 1e-9) one conflation away from a silent disagreement;
- a green-tested re-implementation of a rule with zero callers sitting
  beside the live inline version (HW3's orphaned control).

**The guards, now standing rather than aspirational**: one named function
per rule, every surface consumes it (the deskLanes repair pattern); when a
rule MOVES, the cross-repo predicate sweep ships in the same diff as the
move (the adversary's BIND, carried to the builder seat); and the janitor's
census below hunts the not-yet-bitten instances.

### 2. DEAD CODE (cheap to find, cheap to carry, expensive to trust)

A dead export reads, from outside, exactly like a guarded door (HW3). The
program treats deletion as first-class output — the builder fitness
question ("did the ratio invert") already exists; the janitor makes it a
sweep rather than a hope.

### 3. ACCUMULATION DEBT (prose and files that grow without pruning)

Seat STATE files past 1,200 lines, read cold at every dispatch; stale
docstrings that describe v1 beside a v2 constant (`open_request_actor`,
caught by the adversary; the autopolicy header the COO caught stale three
times). The working-memory design (CONTEXT_ENGINE) is this class's
structural fix; the janitor prunes what it leaves.

## BASELINE, measured 2026-08-27 (the numbers the program moves)

| scan | scope | findings |
|---|---|---|
| ruff F401/F811/F841 | `app/fund` + `app/api` | **30** (24 unused imports, 6 unused vars; 25 auto-fixable) |
| vulture ≥80% | same | **3** — incl. an unreachable `else` (`tradestream.py:117`) and one on Abhishek's surface (EXCLUDED — not ours to touch) |
| ts-prune | studio | **0 dead exports** — the per-dispatch read-through discipline works |
| ts-prune | whole KP tree | ~500 lines, mostly legacy non-studio hooks — census before deletion |
| override census | both repos | UNMEASURED — the janitor's first real job |

## The instruments

1. **Merge-time advisory scan** — ruff F-set + vulture-80 + ts-prune on the
   files a diff touches, folded into `merge_builder.py`'s already-ticketed
   repair (`78e2650b`) so one instrument gains both fixes. Advisory first:
   the scan REPORTS, the chair decides — a gate that auto-blocks on a
   heuristic would manufacture false urgency.
2. **The weekly janitor pass** — one builder dispatch: apply the safe
   deletions, census one slice of the override class (grep the known
   duplicated predicates: status filters, tolerance constants, venue
   spellings, actor routing), unify or ticket each finding. Every deletion
   cites what proved the code dead (callers, not vibes); every unification
   names the one function that survives.
3. **The debt ledger** — findings that cannot be fixed in-pass enter the
   guide store as claims tagged `debt`, with receipts, so debt is queryable
   and its trend is a number. The context packs surface relevant debt to
   any seat working nearby — debt gets fixed opportunistically by whoever
   is already in the file.

## Boundaries

Abhishek's surfaces: excluded entirely, including their dead imports.
Control-layer deletions: versioned human decisions, never janitor acts.
Findings docs: never deleted, per the constitution. The 25 auto-fixable
Python imports WAIT until the in-flight builder crews merge — an auto-fix
sweep across files a worktree is editing manufactures conflicts.

## Falsifier, written at charter time

A production incident traced to an override-class duplicate that the
census had already swept (and not flagged) kills the census design and
sends the program back to the drawing board. A quarter with zero janitor
deletions while the baselines grow means the program is decoration.

## THE CONTEXT LANE (added same day, CEO instruction)

**CEO, verbatim: "Janitor could also sweep through each agents context and
help us refine on it? we dont want endlessly accumulating context for each
agent so maybe in periodic janitor runs it helps code + context cleanup" —
and the binding rider: "lets make it such that relevant items are not
removed so it needs to triage it really well."**

The janitor's periodic pass gains a second lane: seat-context hygiene.
The accumulation-debt class (charter section 3) gets its instrument.

**The rules, written against the rider:**

1. **NOTHING IS DELETED — content only MOVES.** A seat's state file splits
   into the LIVE file (standing rules, the current map, recent STATE
   appends) and a linked ARCHIVE file (`<seat>_archive_YYYY.md`) holding
   the rest verbatim. The record survives whole; the read-cost drops. A
   deletion of seat memory is not a janitor act at any confidence.
2. **EVERY MOVE IS A CHAIR-REVIEWED DIFF.** The janitor proposes the
   split; the chair reviews what stays live (the triage the CEO demands);
   nothing auto-applies — the work-layer evolution rule.
3. **THE SEAT REVIEWS ITS OWN DISTILLATION.** On its next dispatch after a
   split, the seat is told the split happened and may object through
   `## EVOLVE` — the seat knows best which "old" lesson still fires. An
   objection restores the item to the live file, no questions.
4. **DISTILLATION RUNS ON THE STRONG MODEL** until the template is stable
   (the Donna rule: a bad summary misleads quietly).
5. **FALSIFIER, written at charter time**: one instance of a seat
   re-deriving a lesson that had been archived out of its live file — or a
   defect a moved rule would have caught — SUSPENDS the lane pending the
   CEO's re-decision. Relevant-items-never-removed is the bar, and this is
   its tripwire.

Composition with the context engine: this lane is CE-2's janitorial
sibling — working memory (the bounded present tense) is built at resolve;
the janitor's lane keeps the underlying archives lean and measures the
read-cost. First pass (jan1, 2026-08-27) is MEASURE-ONLY: per-file
line/token counts, growth hotspots past the 1,200-line threshold, section
census of the three largest. The numbers become the lane's baseline.

## THE SKILL MINER (added same day, CEO instruction, gated on the audition)

**CEO, verbatim: "can we have janitor help us create skills by mapping work
history and tools used by say quant or pm or builder so its like a RLM."**

The third lane, and it is the SELECTION LOOP (constitution, reimagined-team
rule 5) given its concrete product. The firm already stores what a
reinforcement loop needs: run records with verdicts, seat STATEs with
measured lessons, the instrument shelf, and per-run scratchpad script
inventories. Nothing yet MINES them into named, reusable skills.

**The lane**: a periodic pass over a seat's work history that proposes
SKILL CANDIDATES — a named procedure with its measured basis and its
receipts ("the two-tree kill reproduction", "hidden-test local drafting",
"the conftest module-swap suite grader") — each filed as a PROPOSAL through
the desk: chair-reviewed, then applied as a shelf entry, a pre-flight card
item, or a seat-file addition through the ordinary EVOLVE-shaped path.
Skills EARN their place by the surviving-verdict record and are struck when
the record stops supporting them — that is the "RLM" half, run on the
firm's own outcomes rather than a reward model.

**The rules it inherits, stated so nobody wonders**: proposals-only,
nothing auto-applies (selection-loop rule); the IMMUNE-SYSTEM EXCLUSION
stands — the lane may not propose amendments to the adversary's seat
definition (mining the adversary's INSTRUMENTS onto the shelf is fine; its
mandate is not the lane's to touch); the selection loop's own falsifier
applies (two weeks without one mined skill surviving both chair and seat
review dismantles the lane). First run: after the janitor audition
resolves, as the seated janitor's third lane — or chair-dispatched if the
audition fails.

## CONTEXT CHANGES ARE VERSIONED (added 2026-08-28, CEO instruction, verbatim: "lets version context changes so we can rollback if things go messy")

The substrate already exists — the whole `.claude` workspace (seat
memories, agent definitions, day log, review queue) is tracked in the firm
git repo, and every resolve commits. What this section adds is the
discipline that turns "history exists" into "rollback is one command":

1. **A context RESTRUCTURING is its own isolated commit, never bundled.**
   A split, an archive move, or a distillation commits alone, message
   prefixed `context:` and naming the seat, the shape, and the verify
   result — e.g. `context: split state/builder.md into hot + archive
   (verify green, 0 lines lost)`. Rollback of a messy split is then exactly
   `git revert <hash>`, touching nothing else. Ordinary STATE/BINDS appends
   at resolve stay bundled with the resolve commit as today — they are
   additions, and additions never need untangling.
2. **The verify script runs BEFORE the commit, and its result is in the
   message.** A split commits only with the lossless proof green; a verify
   that cannot prove losslessness is a split that does not commit.
3. **The seat's veto is a revert, and it stays cheap by construction.**
   The first brief a seat receives after its split names the split commit
   hash and invites the veto: if the hot file is missing something the seat
   needs, the chair reverts the commit (one command, nothing else moves)
   and the split is re-cut. This is the lane's "relevant items are not
   removed" rule with an enforcement path instead of a promise.
4. **The day log records every context restructuring under DECIDED** with
   the commit hash — so a returning chair can walk the estate's history
   without `git log` archaeology.

What would change this decision's mind (clause 4): a context rollback that
`git revert` cannot cleanly perform because a restructuring was bundled
with other changes — that is the failure this section exists to prevent,
and one occurrence means the isolation rule was violated, not that the
mechanism is wrong.
