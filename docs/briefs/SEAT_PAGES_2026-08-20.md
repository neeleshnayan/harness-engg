# Builder brief — one page per seat (CEO direction, 2026-08-20)

**Status: QUEUED. Dispatch is explicit — CEO or CTO triggers; this doc existing
is not a trigger.** Batch with the UI-consolidation brief (desk request
c91d5c07) into ONE builder dispatch: consolidation decides where the seat pages
hang; building them twice would be waste.

## The CEO's ask, verbatim intent

One page dedicated to each worker agent, with views that complement the CEO's
understanding, and every metric relevant to that seat on its page. The desk
today shows the bench as a list; the CEO manages seats the way a manager
manages reports — one surface per report.

## Routes

`/clark/studio/desk/[seat]` for the 8 seats: mechanism, analyst, pm, quant,
adversary, validator, riskofficer, builder. The roster cards on `/desk` become
links. Unknown seat → 404, not an empty shell.

## Every seat page carries (the common frame)

- **Header**: seat name, its lane (one line, from the roster payload), model
  placement (Opus / hybrid / local-split — static config is fine), live status
  from `activity` (working on X since T / idle / last delivered).
- **Dispatch economics strip**: dispatches total, last dispatched at, tokens
  per dispatch (avg + range), total tokens. A cost figure is allowed ONLY if
  computed from tokens with the price table stated on-page and labeled
  "estimate" — never a hardcoded dollar number.
- **Run log** filtered to the seat (reuse `RunRow` — reasoning expanders, trace
  ids). Data: `GET /api/v1/fund/desk/runs?seat=<seat>`.
- **Chatter threads**: the seat's runs grouped by `trace_id`, each thread
  rendered as a small timeline (request → dispatch → run → verdict → decisions)
  so a chain replays visually. Data is already in the desk payload + runs.
- **Absence discipline**: a seat with zero runs states "never dispatched — an
  idle seat costs zero and that is a feature", not an empty table and never a
  zero-filled metrics strip.

## Per-seat views (the complementary part — metrics native to the lane)

| Seat | Native view |
|---|---|
| mechanism | Proposals emitted; killed / survived / awaiting-attack; claim-type split (premia vs alpha) |
| analyst | Theses emitted; verdict outcomes; corpus link-out (863 obs); runner-ups parked |
| pm | **Decision funnel**: recommendations made → accepted / rejected / staged / done, as counts and as a funnel bar; open recs surfaced on top |
| quant | Candidates submitted, gate verdicts verbatim, container-runs consumed per candidate |
| adversary | **Kill board**: KILL / SURVIVES / CANNOT TELL counts, artifacts attacked with links, mind-changers produced (verdicts that changed a design) |
| validator | Measurements filed, method + confidence shown, defects confirmed in our own instruments |
| riskofficer | Auto-approvals audited vs fired (from the policy events), findings, envelope-change recommendations with versions |
| builder | Briefs completed, diffs merged vs rejected, tests-passed record |

Where the number does not exist in any API yet, the page states the absence
("not yet measured — needs X") rather than deriving something look-alike.
Deriving counts client-side from `runs` + `recommendations` + `artifacts`
payloads is correct and preferred; inventing a metric is not.

## Boundaries (constitution, restated for this brief)

- Worktree only. Diff + passing tests out; the CTO merges.
- `fund_api.ts` edits must be **additive** and must not touch Abhishek's types.
  Abhishek's surfaces (`src/app/clark/studio/thesis/**`, thesis_generator) are
  out of reach entirely.
- No new spine endpoints unless a listed metric is impossible client-side; if
  one is genuinely needed, it is a read-only fold over existing events/tables,
  named in the diff summary for CTO review.
- No hardcoded financial numbers, timestamps, or rates anywhere. Absence is
  never zero.

## The collaboration model each page encodes (CEO direction, same day)

A seat page is not a dashboard about an agent; it is the CEO's working surface
WITH that agent. Layout mirrors the loop, top to bottom:

1. **The seat's asks of the CEO** — its open recommendations, decidable in
   place (Accept/Reject, as on /desk). What needs the human, first.
2. **The CEO's asks of the seat** — the request composer pre-filled with this
   seat's kind, so "ask the pm to re-review" is one field and one click.
3. **The evidence** — runs with reasoning expanders, artifacts with verdicts,
   chatter threads by trace_id. Why the seat believes what it asks.
4. **The track record** — the lane-native metrics table above. Whether to keep
   trusting it.

So each page reads as: decide → ask → inspect → calibrate trust.

## The Desk as the office view (CEO direction, 2026-08-20, late)

The Desk index page becomes **the office**: how the firm is doing, day by day,
with past days as reviewable as today. Two elements:

1. **A day scrubber.** Default = today, live. Scrub back and the whole desk
   re-renders AS OF that day: which seats ran, how many times, who triggered
   each (actor field: ceo / cto), what was delivered, what was decided. All of
   this folds from the event log (DESK_REQUESTED / DISPATCHED / RESOLVED /
   RECOMMENDATION_DECIDED all carry timestamps and actors) plus
   `fund_agent_runs.resolved_at` — no new storage, one fold parameterised by
   date. A per-day productivity strip: dispatches, tokens, verdicts, decisions,
   kills (a kill is a win — render it as one).
2. **The DAG.** Each trace_id renders as a small directed flow: request →
   dispatch(seat) → run(verdict) → recommendations → decisions → (later)
   staged order. Nodes carry actor + timestamp; edges are the trace. The day
   view shows the DAGs that were alive that day. This is the CEO's "chatter
   flow, recreatable" — it is also the audit view, one drawing.

Charts principle, stated by the CEO: charts are how the CEO consumes fastest.
Each seat page IS the analytical surface where the CEO reviews the seat's work
and gives blessings — so the decision controls (Accept/Reject) sit next to the
charts that justify them, never on a separate page.

## Charts: keep / retire / add (one rule decides)

**The rule: a chart stays only if it informs a specific click or dispatch.**
A number without a decision attached is retired, not restyled.

KEEP (relocated where noted): the Mechanics funnel and causes-of-death (move
into the quant page — it is that lane's native metric); the gate-lineage
timeline (quant page); Risk's six measured modules stay on /risk — the
riskofficer page LINKS to them as its evidence base, never duplicates; NAV +
approval queue + strategy-wants stay on Monitor (with the new provenance
chips); the Desk artifact chain (filtered per seat on seat pages).

RETIRE: Lab's map/hunting-ground panels (already slated in c91d5c07 — they are
mechanism-agent inputs via API now); Mechanics as a standalone tab (its four
views disperse to the seats that own them); any duplicate rendering of the
same number on two tabs.

ADD: the PM decision funnel (made → accepted → staged → done); the adversary
kill board; the trace timeline (chatter replay: request → dispatch → run →
verdict → decision as one horizontal thread — the cross-seat view and the
audit view in one); a per-seat dispatch-economics sparkline (tokens/dispatch
over time); provenance chips everywhere an action is suggested.

## Provenance labels (added same day — found by the CEO, live)

The CEO read Monitor's "What the strategies want" panel and could not tell
whether an agent was recommending. Every surface that suggests an action must
carry a provenance chip: `deterministic — strategy signal`, `deterministic —
auto-policy`, or `agent — <seat> · rec N`. Monitor's strategy-wants panel gets
`deterministic — strategy signal (no agent)`. This is the same attribution rule
the desk recommendations already follow, extended everywhere an action is
suggested.

## Acceptance criteria

1. `npx tsc --noEmit` clean; existing tests pass.
2. All 8 seat routes render against the live spine AND degrade to stated
   absences with the spine down.
3. Roster cards on /desk link to the seat pages.
4. Every metric on every page traceable to an API field or a stated derivation;
   the diff summary lists each metric and its source.
5. Design language holds: hierarchy from type and space, never colour
   (theme.ts brief).
