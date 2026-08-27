# THE CONTEXT ENGINE — operationalising what each agent knows

**Chartered 2026-08-27 by the CEO, verbatim:** *"how can we operationalise
building context for agents so they can fetch the most relevant parts for
their work and unblock themselves. Since we are fully agentic managing
context is king; maybe it should be part of UI too as to what
context/working memory of each agent."*

## The measured problem (why this is the binding constraint, not a nicety)

Context assembly is today CHAIR LABOR, and the chair is measurably bad at
it under load. One night's record: **three brief defects, all
context-assembly failures** — a stale frozen base, a payload field name
written from memory (`session` vs `session_state`), a design pattern stated
as fact — each caught by the seat it misled, each costing minutes to hours.
Meanwhile the seats' own memory is append-only prose: `builder.md` passes
1,200 lines, read-cold at every dispatch, skimmed by necessity. And the
firm's counter-example is one night old: **the chair itself re-derived the
knowledge graph from scratch 96 hours after building it** — the definitive
proof that remembering does not survive this speed, only QUERYING does.

What already exists (the engine assembles, it does not invent):

| store | holds | queryable? |
|---|---|---|
| the guide store (`app/fund/guide.py`) | distilled claims with receipts + falsifiers, typed edges | yes (module; endpoints pending) |
| the knowledge graph (`app/fund/knowledge.py`) | every hypothesis tested and what killed it; family ledgers | via `scripts/kg/report.py` |
| seat STATE files | per-seat lessons, unbounded prose | grep only |
| BINDS | cross-seat instructions with (implicit) consumption state | no |
| the ticket highway | work items with lineage | yes (`/fund/tickets`) |
| the API card | endpoint facts | grep only |
| the live spine | payload shapes, current state | curl |

## The design — four parts, buildable in this order

### 1. THE CONTEXT PACK (the assembler — the chair's brief-writing, made a service)

`POST /fund/context` with `{seat, task, tags[], entities[], q}` returns one
structured pack:

- **guide claims** matching tags/entities/q — each with receipt + falsifier
  (the seat can trust or re-verify, never re-derive);
- **kg family ledger** for any named edge family (the family-wise
  denominator, mandatory on proposals);
- **the seat's WORKING MEMORY** (part 2) — not the raw STATE file;
- **unconsumed BINDS addressed to this seat** (consumption = the receipt
  mechanism Vishesh's flow mandate already demands);
- **open tickets** for the seat, from the highway;
- **LIVE SHAPE SAMPLES**: for any endpoint the task names, the pack embeds
  a fresh one-item `curl` of the real payload — **the paste-from-a-live-curl
  rule, automated**, which retires the field-name defect class entirely;
- **API-card facts** matching the entities.

Every pack section carries its source and its freshness; an unreadable
store reads UNREADABLE in the pack, never silently absent. The chair's
brief embeds the pack; the seat can ALSO call the endpoint mid-run (seats
have Bash) — that is the self-unblocking half: **query before asking the
chair, and cite what you queried.**

### 2. WORKING MEMORY (the distillation — what a seat KNOWS, not what it has SAID)

Each seat gets a bounded working-memory document, distilled FROM its STATE
file, structured as: the map (current surfaces it owns, verified shapes it
relies on), the standing lessons (its EVOLVE-applied rules), the open
threads (what it owes and is owed). Stored as guide-store claims tagged
`seat:<name>` so it is queryable like everything else, regenerated at
resolve by the same distillation duty Donna already carries for the books.
The STATE file remains the append-only record; working memory is its
readable present tense. **Bounded is the feature** — a working memory that
grows without pruning is the 1,200-line problem wearing a new name.

### 3. THE UI — the CEO's ask, and it fits the seat-page spec exactly

The seat pages (SEAT_PAGES_DESIGN) gain their ninth section — or rather
section 6 (lessons & growth) gains its other half: **WORKING MEMORY** — what
this seat currently knows, carries, and relies on, rendered from the tagged
claims. Plus, on every dispatch row, a **context inspector**: "what this
seat was told" — the pack, foldable, the same disclosure idiom as the
engine page's caveats and the Clark console's "SHOW WHAT CLARK IS TOLD"
(the pattern already exists in the studio). The CEO can open any running
lamp and see exactly what context the worker started with — which is also
demo material: no other fund can show an allocator what its analysts knew
and when.

### 4. THE MEASUREMENT (or it is decoration)

- **pack hit rate**: did the seat's output cite pack items (receipts make
  this mechanical);
- **unblock rate**: chair-questions per dispatch, before vs after;
- **defect classes retired**: the field-name class should go to zero — it
  is the falsifier: a payload-shape defect in any brief carrying an
  auto-curled sample reopens this design.

## Boundaries (unchanged, stated so nobody wonders)

Seats still hold no pen: the pack is read-only assembly; working-memory
distillation routes through the chair's resolve like STATE and BINDS.
Nothing here touches the control layer. The guide's entry discipline
(receipt or refusal) is the quality floor — a context engine over
unreceipted claims would industrialise rumor.

## Build order

Slice CE-1 (spine): the guide/kg query endpoints + `POST /fund/context`
assembler. Slice CE-2 (distillation): working-memory generation at resolve
+ the seat-tagged claims. Slice CE-3 (UI): the seat-page panel + dispatch
context inspector — rides the seat-pages slice it shares a spec with.
Fires when a builder slot frees (two crews out as of this writing).
