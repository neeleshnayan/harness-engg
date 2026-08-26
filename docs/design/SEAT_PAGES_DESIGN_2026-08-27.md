# The seat pages and the shared ticket component — design brief

**2026-08-27, from the CTO chair, on the CEO's instruction. His words, the
mandate:** *"ticketing UI should be similar across mine and yours desk"* and,
on the section anatomy he ratified: *"I really appreciate well done UIs; so we
need these sections be custom built to serve that purpose well."*

That second sentence is the brief. **Every section is custom-built for what
it shows.** A generic card grid with eight headings is the failure mode; the
engine page's first version — honest prose, walls of it — is the measured
precedent ("too much text; we need analytics and graphs and meaningful and
minimal UI"). Form follows the content's own shape, section by section.

## The design system (stands, not negotiable per-page)

The house language lives in KryptonPay's `theme.ts` and the studio's existing
surfaces: **calm, generous, hierarchy from type and space — never from
colour.** Semantic state (good / warning / critical / unknown) is separate
from accent and used sparingly. Absence discipline renders: UNKNOWN is a
rendered state, an empty section is a fact ("no lessons yet") not a blank.
Numbers first, sentences on demand (expanders, tooltips); `tabular-nums`
wherever digits align. Inline SVG for any graphic — the allocate NAV chart is
the house chart idiom.

## ONE ticket component, everywhere

The ticket card is built once and consumed by the CEO desk, the chair desk,
and every seat page. It carries: the title; the **capsule chips**
(what-broke / where / blast-with-number / proven-vs-suspected / who-moves-next);
the **lineage stepper** — the seven stages as a horizontal rail, empty stages
as dim dots with the honest why behind a tap, repeated decisions collapsed to
one chip with a count (`8× decided`), and stage six — *evidence it was
carried out* — visually loudest, because it is the stage that bites; the
**decide-later** control (park with note + revisit date; parked leaves the
lane and resurfaces on the date — a first-class state, never a quiet
terminal). Rendering a ticket any other way anywhere is a defect.

## The seat page — eight sections, each with its own form

1. **Greeting** — a typographic moment, not a widget: the seat's voice,
   addressed to the CEO, set large and quiet like a letter's opening line.
   Personas differ; the greeting is where that shows. One or two sentences,
   generated from the seat's persona + current state, never boilerplate.
2. **Now** — a single status object: lamp (working / returned-awaiting-review
   / idle), last-run clock, current task title. Fed by the Postgres dispatch
   switch, so it is true by construction. The three states look distinct at a
   glance; "returned, awaiting the chair's review" must not resemble
   "working" (the measured failure: three finished dispatches lit for hours).
3. **Scoreboard** — data-viz tiles, seat-specific: the adversary's
   kills / survives / refuted-own-priors as a truthful two-direction figure;
   the builder's defects-caught-per-dispatch and add/delete ratio as a
   sparkline; Grace's dates-moved. **The metric is the seat's own fitness
   line from its STATE — never one template across seats.** A seat page
   without a scoreboard is a profile; with one it is an employee.
4. **Work artifacts** — newest first, each row: title, date, one-line
   verdict, link to the doc and its run. Dense list, generous spacing; no
   thumbnails, no cards-for-the-sake-of-cards.
5. **Tickets** — in-tray / out-tray, the shared component, filtered to the
   seat. Counts in the tray headers; aging visible.
6. **Lessons & growth** — the distilled STATE as a timeline: EVOLVE
   amendments as dated markers with before→after on tap; persona version;
   the two or three standing lessons the seat itself carries forward. This
   section is the self-evolving harness made visible.
7. **BINDS traffic** — sent and received as two small flows with consumption
   receipts; an unconsumed lesson AGES here, on the sender's page, where the
   gap shames someone specific. This is Vishesh's flow mandate given a
   surface.
8. **The charter line** — one sentence, footer-set: lane, and what this seat
   may never do. Plus the ambient **meter** (runs · tokens · what they
   bought) small and factual in a corner.

**Windows, never doors**: no approve buttons, no dispatch triggers on seat
pages. The doors stay on the CEO's and the chair's desks.

## Acceptance

Per section, the look-pass question is specific: *does this section's FORM
serve this section's content better than a generic list would?* A reviewer
who cannot answer yes for a section returns it. Screenshots at empty / one /
many for every section; both themes; the zero-is-quiet tone rule; plurals by
`plural()`. This absorbs desk request `708aa38f` (D40, the team room).
