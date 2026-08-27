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
