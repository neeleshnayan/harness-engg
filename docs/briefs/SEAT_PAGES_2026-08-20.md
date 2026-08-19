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
