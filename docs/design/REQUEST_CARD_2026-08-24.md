# The request card, redesigned (CEO-ratified 2026-08-24)

CEO, on seeing request `0c295ec7` render as a wall of prose: *"it could have
been designed in a far more intuitive and cleaner way"* — then **"Yes"** on
this spec. Binding for D39's UI half and every desk card after it.

## The four questions a card must answer, in order, without scrolling

1. **What is this?** — a NAME, not the first line of a dump. One headline
   sentence (≤10 words), one subtitle sentence of why-it-matters.
2. **Where does it stand?** — a LIFECYCLE RAIL: filed → approved →
   awaiting dispatch → dispatched → delivered/resolved. The CURRENT stage is
   visually hot and carries its AGE (`awaiting dispatch · 2.5d`). The rail
   made `0c295ec7`'s real story legible in one glance: approved 22 minutes
   after filing, then idle 2.5 days — the old card rendered that as gray
   footer text.
3. **What exactly is owed?** — the WANTED items as a tracked checklist,
   each with an independent state (done / in progress with a note / open).
   Partial progress must be visible; a card is not binary.
4. **Whose move is it?** — an explicit next-move line naming the actor and
   the act ("Next move: the chair batches this into a builder dispatch").
   The old "CEO-APPROVED — TRIGGER IT" chip implied the CEO's move when it
   was the chair's. NEVER ambiguous.

Everything else — the full incident narrative, evidence, commands, state-loss
checks — collapses behind a `details` toggle ("The incident"). Nothing is
deleted; nothing is charged to readers who didn't ask for it.

## Chair-adjudicated states are first-class (CEO instruction, same session)

*"your desk on the UI only marks items as CEO approved - trigger it so I
cant form a view of whats closed and adjudicated by you."* Dispositions by
`neelesh-via-cto` / the chair render as their own visible category —
"closed by the chair · citation" — distinct from CEO-approved, filterable,
with the citation one click away. The v2 delegation's audit trail must be
readable off the desk itself.

## The structural half: the filing-door schema

Cards cannot be clean while requests are filed as one prose blob. The
filing door (`POST /fund/desk/requests`) gains OPTIONAL structured fields:

```
headline:  string        (≤10 words — the card's name)
summary:   string        (one sentence of why-it-matters)
incident:  string        (the full narrative — the collapsed section)
wanted:    [{text, state?, note?}]   (the tracked checklist)
next_move: {actor, act}  (whose move + what act)
```

Prose-only `subject` remains valid forever (the fallback renders the old
way, one blob). Every seat's filing template adopts the shape via briefs;
the chair's own filing scripts adopt it first. No migration of old rows —
they render via fallback; the sweep retires them naturally.

## Visual grammar (inherits theme.ts's ILLUMINATION PRINCIPLE)

Calm surfaces, hierarchy from type and space, never colour; the ONLY
colour on a card is semantic: the hot lifecycle stage (warning tint), a
severity chip when the request declares one (danger tint), success ticks.
Kind chips (build/attack/audit) stay neutral. Sentence case throughout.
Mono only for ids. The reference mockup lives in the session record
2026-08-24 (the chair's widget render, CEO-ratified).
