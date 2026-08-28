# The Strategy Dossier — a lifecycle document per strategy (2026-08-28)

**CEO instruction, verbatim: "I am thinking we need a strategy lifecyle just
how we track work; as in an evolving document that changes shape as it moves
desks and can be reviewable for both stratgies that we tried and failed so we
can understand and those that passed."**

## The gap this closes

A strategy's life is already fully recorded — but in five places. P1's story
today lives in Ed's batch doc (`docs/mechanism/ED_BATCH7_2026-08-27.md`), the
adversary's review (`docs/reviews/`), the quant's belt report
(`docs/quant/QUANT_P1_CRYPTOPROBE_2026-08-28.md`), the candidates table
(`a39f301168fa`), and the desk's decision records. Reading one strategy's
story means visiting every desk it crossed. And a KILLED strategy's story is
worse: the kill is recorded where it died, so the lesson is filed under the
killer, not under the strategy — which is why failures are hard to review as
a corpus.

## The design

**One dossier per strategy lineage.** It changes shape as the strategy moves
desks — each stage APPENDS a dated section; nothing is ever rewritten
(the findings-doc rule applied to a living document):

```
PROPOSED      Ed/analyst: the claim, the counterparty, the falsifier
REVIEWED      adversary: verdict verbatim (blind review preserved — the
              dossier links the artifact reviewed, never the reasoning)
IMPLEMENTED   quant: algorithm, declared interpretation choices
BELTED        candidate id, gate version, verdict VERBATIM, failures verbatim
DECIDED       the CEO's ruling with his words and date
SIZED         Stan: notional, basis, what it displaces
DEPLOYED      session/strategy ids, exits committed pre-entry (cited)
LIVE          fills, monitoring, incidents — appended as they happen
TERMINAL      one of: KILLED at stage N (reason verbatim + what it taught,
              linked to the guide claim) · RETIRED (exit story) · superseded
```

**Derived from the record, never a parallel truth.** The dossier is a
RENDERED VIEW: a script assembles it from what each desk already files, the
way Donna's archive and the lab one-pager render from the record. Nobody
maintains it by hand; a hand-maintained copy of the record drifts, and the
drift is invisible precisely when it matters. The one hand-written thing per
stage is what the seat already writes — its artifact; the dossier links and
quotes, never paraphrases a verdict.

**Failed and passed sit in the same book.** The strategy book's index shows
every lineage with its stage rail and terminal state — a kill at REVIEWED is
as browsable as a deploy. The failures are the review corpus the CEO asked
for: "so we can understand."

## Build plan

1. **Pilot, today, by hand-assembly from the record**: `docs/dossiers/
   P1_ETH_WRAPPER.md` — P1 is mid-life (DECIDED, awaiting SIZED), so the
   pilot demonstrates the "changes shape as it moves desks" property live.
   Second pilot: one KILLED strategy, to prove the failure half.
2. **Builder generalizes** (next slot after the crypto unblock): a `dossier`
   renderer (`scripts/lab/` pattern), a stage model derived from existing
   records (no new writes to the event store — the dossier READS), and a
   studio Strategy Book page (card per lineage, stage rail as geometry —
   the B2 card idiom).
3. **Governance**: work-layer entirely. The dossier writes nothing to any
   decision path; blind review is preserved (the adversary section links the
   artifact, never the author's reasoning); agents never gain write access —
   the renderer runs under the chair's or the secretary's existing lanes.

What would change this decision's mind (clause 4): if maintaining the
dossier view costs more than one chair-hour a week after the renderer ships,
or if a dossier is ever caught DISAGREEING with the underlying record (the
drift failure), the design reverts to per-desk artifacts pending re-design.

## AMENDED same day (CEO, verbatim): durable in Postgres, with backfill

**"Also on the strategy page I was thinking we make it durable via postgres
so we can historically review each stratgey document"** and **"YOu can
backfill for those we have iterated till now?"**

Both adopted into the build plan:

1. **The dossier's storage of record is Postgres, append-only**: a
   `fund_dossier_sections` table — (dossier_id, stage, section_seq,
   filed_at, author, body, citations) — where each desk crossing appends one
   row and nothing updates. Historical review falls out for free: the
   document AT any past date is the fold of sections filed by that date, so
   "what did we believe about this strategy on day X" is a query, not an
   archaeology. The markdown files in `docs/dossiers/` become RENDERS of
   the store (kept in git as before — two independent histories of the same
   record); the studio Strategy Book reads the store.
2. **Backfill is commissioned**: one record-mining dispatch assembles
   dossiers for every lineage the firm has iterated to date — Ed's batch
   entries (killed and surviving), the analyst theses, HYG v1/v2, the E2E
   harness sleeve, the deployed premia sleeves, Entry 20 and the gate-era
   candidates — each with its verbatim verdicts and terminal state. Runs
   after the builder ships the store, so the backfill lands durable
   directly. The killed lineages are the point: that is the reviewable
   failure corpus the CEO asked for.
