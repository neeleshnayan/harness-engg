# Builder brief — the CEO desk and the CTO desk (CEO-blessed design, 2026-08-20)

**The hierarchy made visible: the floor becomes CEO → COO → CTO → the bench.
Two new surfaces, both pure folds over data the spine already serves — no new
storage, no new endpoints unless a named absence forces one.**

## The CEO desk (`/clark/studio/desk/ceo` — the ceo face already exists)

*What waits on the CEO's click*, ranked the way the coo seat ranks (money,
reversibility, staleness):

1. **Pending orders** (approval queue summary with memo headlines + the
   120-minute freshness clock VISIBLE per order — a ticket about to expire
   says so).
2. **Open recommendations across all runs**, grouped by run with seat faces,
   linking into the seat pages to decide in place.
3. **The halt state** when engaged, with the resume control's location named.
4. **COO batch memos** when the coo seat has filed one (its runs, newest
   first) — the intended top of this page once triage is flowing.
5. **Decision velocity**: decided today / this week, from the
   DESK_RECOMMENDATION_DECIDED events — the CEO's own productivity strip.

## The CTO desk (`/clark/studio/desk/cto`)

*What waits on the CTO's hands*:

1. **Open desk requests** (the durable queue) with age and requesting actor —
   including seat-filed requests once the constitution amendment (2026-08-20)
   starts producing them; a seat-tagged ask renders with the seat's face.
2. **Unresolved dispatches** (DeskDispatched without a matching resolve).
3. **Accepted-but-unimplemented recommendations** (status accepted, kind
   fix/harness/envelope) — the CTO's build backlog, straight from the
   recorder.
4. **Dispatch economics for the whole bench** (tokens and estimated cost this
   week, from the runs — the cost lever the CTO owns).

## Rules

- Both pages reuse the seat-page frame and components (faces, RecRow,
  ProductionShelf idiom); the ceo/cto ids join the route map WITHOUT joining
  SEATS (they are humans, not bench seats — the route guard distinguishes).
- Absence discipline everywhere; dead-spine run + headless screenshots per the
  adopted process; tsc + tests; no thesis surfaces; no thresholds.
- The floor's grid gains the two desks at the TOP row (hierarchy reads
  top-down), visually distinct from bench desks (human faces, no
  working/idle badge — humans are not dispatched).
