# The Reading Room — the firm, in writing (2026-08-28)

**CEO instruction, verbatim: "worth having a separete page called something
cool where we keep all reading materials - be it donna's EOD long briefs or
STrategy Cards aka Lifecycle. It has to be readable and presentable in a way
that we can show it to external investors to how our firm works and creates
world class products."**

## The name

**The Reading Room** — already the record's own name for the half-built PDF
shelf; clubby, calm, investor-familiar. Tagline on the masthead: *"the firm,
in writing."* (CEO may rename with a word.)

## What it is

One page — `/clark/studio/reading-room` — where everything the firm WRITES
is shelved, readable, and beautiful. Not a file browser: a publication.

**The shelves:**
1. **Strategy Dossiers** — the lifecycle cards, each with its stage rail on
   the cover (P1's `PROPOSED ✓ → … → LIVE ✓` is the flagship). Killed
   lineages shelved beside live ones: the failure corpus IS the credibility.
2. **The Daily Record** — Donna's EoD briefs: the sixty-second memo as the
   cover face, the detailed record behind it. A firm that documents every
   day is the product being shown.
3. **Research Notes** — the landscape studies, proposals, thesis memos
   (crypto landscape v1, Ed's batches, the analyst dossiers).
4. **Reviews & Audits** — adversary verdicts and riskofficer audits: the
   firm attacking its own work, on the record. For investors this shelf is
   the differentiator; nothing here is dressed up.
5. **The Canon** — FUND_GENESIS, the program charters, the design docs.

## The investor boundary (governance, stated up front)

The page is LOCAL (the studio) — showing it in a meeting is a screen-share,
which is the CEO's own act. **Publishing any of it outward remains outside
Delegation v2** (nothing outward-facing without the CEO). The page carries a
**curated shelf flag**: every document defaults INTERNAL; the CEO marks what
is investor-visible; an "Investor view" toggle renders ONLY the curated set,
so a live demo cannot accidentally scroll into raw internals. Curation is
presentation, never editing — documents are shown verbatim or not at all.

## Design

Editorial, not dashboard: a publication's restraint. Typographic covers
(title, date, seat byline, one-line abstract), generous whitespace,
hierarchy from type — the house design language at its calmest. Each doc
opens in a clean reader (markdown rendered; PDF download where a render
exists via scripts/library/render_note.py). Search + shelf filters. The
dossier covers carry the stage rail as geometry. No metrics, no lamps —
this page is the firm's voice, not its telemetry.

## Data

docs/** (archives, dossiers, research, reviews, design) indexed by shelf
convention; the dossier store (postgres) once built; existing PDF renders.
Builder implements: the index fold (server-side, honest tails), the page,
the reader, the curated-shelf flag store (work-layer). Acceptance: (1) the
five shelves render with real documents; (2) the Investor view shows only
curated items and P1's dossier reads cover-to-cover beautifully; (3) KP
suite + tsc green.
