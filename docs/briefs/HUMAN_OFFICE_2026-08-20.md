# Builder brief — the human office: faces, desks, memos (CEO direction, 2026-08-20)

**Scope: a re-imagined visual layer over the office/trace/rewind surfaces.
Data model unchanged — this is aesthetics and metaphor, not plumbing.**

## The CEO's ask, verbatim intent

"A human type org where you have desks and you can see what each desk is doing,
what each desk is producing (across time) and how they are intercommunicating."
Humanise the agents — "a nice face icon"; traces as "a clean well designed
memo". Clean visual aesthetics throughout.

## The three surfaces

1. **The floor** (Desk index, replaces the current seat grid): eight desks in a
   calm grid, each with the seat's FACE, name, live status, and the one line of
   what it is doing or last produced. A working desk breathes (subtle pulse);
   an idle desk rests. Clicking a desk walks into it.
2. **Memos between desks** (replaces TraceFlow): a trace renders as a MEMO
   THREAD — each hop a small letterhead card: FROM face+name TO face+name,
   timestamp, the one-line subject (reuse the memoParts headline discipline
   from ApprovalQueue.tsx), verdict stamp where one exists (KILL as a red
   stamp, deliberately physical). Hops connect with a quiet vertical thread
   line. The audit view and the working view stay the SAME data
   (seatLib.traceThreads) — this is a re-skin, not a re-derivation.
3. **What each desk produced, across time** (seat page + rewind): a per-desk
   production shelf — artifacts in time order as small memo spines (date,
   title, verdict stamp), and the rewind scrubber re-renders the floor as of
   any day.

## Faces: the rules

- **Inline SVG, generated in code** — no image assets, no external hosts, no
  emoji. One `<SeatFace seat name size>` component: simple, warm, geometric
  faces (think line-drawn avatars: head shape, eyes, a distinguishing feature
  per seat — glasses for the validator, a pen for the pm, a magnifier for the
  adversary…), drawn with the design language's restraint. Deterministic per
  seat — the same face everywhere forever, because faces are how humans index
  colleagues. Colour stays within the existing token palette (faces may use
  the accent, never introduce new hues).
- Faces appear ONLY where a seat acts: desk cards, memo cards, wire rows, seat
  page headers, recommendation chips. The CEO and CTO get faces too (they are
  actors on the log): distinct, human-warm, same style.

## Boundaries (constitution + design brief)

- Worktree only; diff + tests out; CTO merges. NOTE from your own STATE: the
  dispatch worktree is ClarkHarness-based — clone KryptonPay inside it (method
  in .claude/state/builder.md) unless told the base is fixed.
- No thesis surfaces, no Abhishek types, no thresholds, no spine changes.
- Same data, same derivations (seatLib) — if a visual needs a datum that does
  not exist, render the stated absence and name the missing field.
- Design language: hierarchy from type and space; the theme.ts brief governs;
  both themes; reduced-motion respected (the pulse must honour
  prefers-reduced-motion).
- Provenance chips and absence discipline survive the re-skin untouched.

## Acceptance

1. tsc clean; seatLib tests pass untouched (this brief adds no derivations).
2. The floor, memo threads, and production shelf render with the live spine
   AND degrade to stated absences without it.
3. Every seat's face is identical on every surface it appears.
4. A screenshotable before/after of one trace as memo-thread vs old TraceFlow
   in the report.
5. Design decisions named where the brief is ambiguous.
