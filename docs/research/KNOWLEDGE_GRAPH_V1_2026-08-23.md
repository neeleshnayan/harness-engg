# THE KNOWLEDGE GRAPH v1 — Ed's team's accumulating memory
**Designed 2026-08-23 (CEO instruction: "what are they learning from the
experiments and how they can leverage that information accumulating over
time to make better search and predictions"). Work-layer research memory.
Postgres, per the standing rule that analytics persist so nobody
re-derives. Nothing in it gates anything — it informs briefs, never
decides.**

## What it is, in one sentence

Every hypothesis this firm ever tests becomes a permanent row with its
grammar header intact; every verdict, kill reason, and measured outcome
attaches to it; and the accumulated structure answers the four questions
that make the NEXT search better than the last one.

## The four queries that pay for it

1. **THE FAMILY LEDGER** — `family_ledger(family)`: how many variants of
   this family were EVER tested, what killed each, what survives. Feeds
   Ed's grammar header's mandatory family count MECHANICALLY instead of
   from memory — the family-wise discovery correction gets its denominator
   from the record, not from recall. An untested family reads UNTESTED,
   never zero.
2. **PREDICTION CALIBRATION** — `prediction_calibration(seat)`: Ed's
   pre-committed numbers (breakeven, capacity, vol-ratio) against the
   belt's measured values, over time. This is the firm's leading indicator
   made queryable: THE DAY ED OUT-PREDICTS THE ADVERSARY ON HIS OWN
   PROPOSALS' ECONOMICS, THE FUNNEL HAS LEARNED SOMETHING ABOUT MARKETS.
3. **THE KILL TAXONOMY** — `kill_taxonomy()`: recurring death causes,
   ranked by frequency and by container cost at time of kill. When a cause
   recurs three times, it earns a pre-flight card item — the card evolves
   from data instead of anecdote. (The card's items 8–11 were all earned
   this way, by hand; this automates the earning.)
4. **THE CHEAP-KILL ROUTER** — `cheap_kills()`: which standing instruments
   (the matched-calendar control, the no-null panel, the placebo battery,
   the out-of-sample-era check) killed which KINDS of families, at what
   cost. New proposals get attacked by the historically-lethal cheap
   instruments FIRST — Entry 21 died at zero containers; the router makes
   that ordering systematic.

## The schema (three tables, deliberately boring)

- **`kg_hypothesis`** — one row per proposal, the grammar header
  persisted: id, family (canonical slug), mechanism, counterparty,
  claim_type, entities[], observable, horizon, predictions (jsonb),
  falsifier, source (menu | shelf-lead | kill-descendant | paper),
  source_ref, proposed_at, run_id (citation, mandatory).
- **`kg_outcome`** — hypothesis_id → stage (adversary | belt | gate |
  deploy), verdict (kill | survives | pass | fail | cannot_tell | VOIDED),
  kill_reason (slug + verbatim), killing_instrument, measured (jsonb —
  the same keys as predictions, so calibration is a join), cited_run, at.
- **`kg_edge`** — from, to, kind (descendant_of_kill | same_family |
  prior_art | control_kills | supersedes), note. The
  `descendant_of_kill` edge is the mutation-on-kill-reasons rule made
  visible: the graph shows which kills BRED and whether their offspring
  did better.

## The rules it inherits (lesson hygiene, applied at birth)

1. **Every row cites its run** — a graph entry without a `run_id` is
   inadmissible; the graph is an index over the record, never a second
   record.
2. **VOIDED cascades** — when a measurement is voided or re-baselined
   (Entry 20's v4.1 pass), the outcome row flips to VOIDED and every
   calibration/ledger query excludes it automatically. The sweep the
   chair does by hand becomes a column.
3. **Absence renders as absence** — an unmeasured prediction is NULL and
   the calibration query says "n of m scoreable", never a silent shrink.
4. **The graph never gates.** No threshold reads it; the gate never
   consults it. It shapes what Ed PROPOSES and what the chair puts in
   BRIEFS. (Work layer — one commit to revert; the control layer cannot
   grow a dependency on it without a versioned human decision.)

## Consumption (where it changes behavior)

- **Ed's brief** gains one line: "consult `family_ledger` before writing
  any family count; consult `cheap_kills` to name the control your
  proposal must survive." His grammar header's family field becomes a
  query result with a citation.
- **Stan's incumbency review**: "would this position be entered today?"
  gets the current family ledger beside each incumbent.
- **Grace's learning-value axis**: expected-uncertainty-reduced gets its
  history — which experiment shapes actually moved calibration, per token.
- **The experience layer** (Loop Charter Phase 4): episodes cite graph
  nodes; the distilled operating memorandum queries the graph instead of
  re-reading every memo.

## Backfill, honestly

The 41 stored gate verdicts, the adversary's kill record, and the belt
results backfill as `provenance: backfill` rows — best-effort, marked as
such, never silently mixed with grammar-era rows. The six fenced
2026-08-20/21 candidates enter with their fence intact (`VOIDED-class`,
comparison forbidden). Pre-grammar proposals get partial headers with
NULLs, not reconstructed guesses.

## What would dismantle it (falsifier at birth)

Two consecutive Ed batches where the graph's family counts or cheap-kill
routing demonstrably changed nothing about what was proposed or how it
was attacked — then it is a report generator, not a memory, and it gets
torn down to the one query that earned its keep.
