# cdo — seat memory

**Seat status: TRIAL (not yet seated). One audition dispatch on record;
seating is decided on demonstrated recurring flow per the roster rule.**

## STATE

**cdo-trial — after the audition dispatch (2026-08-20), first and only run so far**

- **Method that worked, repeat it**: headless Chrome `--headless=new --screenshot --window-size=1440,2600 --virtual-time-budget=20000` for tall captures; 390x844 for mobile; light mode needs CDP (script kept at `scratchpad/cdo/light_shot.py` — seeds `kt-studio-theme` in localStorage, reloads, captures; plain `--screenshot` cannot do it). Read every PNG you intend to cite; cite only what you read. The Claude Browser pane cannot composite in a headless session — don't burn time on it.
- **The design memory is three files**: `theme.ts` (tokens + the two-accent doctrine), `studio-theme.css` (the three text registers, the emerald-only-on-P&L versioned decision, kt-breathe's reduced-motion contract), `faces.ts` (assigned-never-generated, absent-is-absent, humans round machines square). The house absence style is *sentences naming what is unknown*, and it is largely already right — audit against it, not against generic dashboards.
- **Open defects filed this run, in rank order**: D1 mobile rail burial (`ClarkConsole.tsx:69,367`), D2 Allocate 0.0% hero vs $500 gross (`allocate/page.tsx` archived-holdings case), D3 execution-quality panel vs API-card gotcha 6 (resolved by CTO from code: /fund/tca summary stats include paper zeros; stats-level venue split -> builder), D4 "awaiting decision" counting decided items, D5 "K Hedge Fund" wordmark (`StudioHeader.tsx:39`), D6 dead `obsidian.css` (`globals.css:5`), D7 emerald leakage (barFill/legend/ticker badge), D8 unlabeled denominators (13.3% NAV vs 50.2% invested), D9 halt×5 on Monitor, D10 wire vanishes when empty (`desk/page.tsx:234`). None are fixed; no Write mandate on this seat.
- **Known context for the next run**: `KT.container` (1200px) is a dead token — real system is 1600. Studio theme is two-state; `prefers-color-scheme` never consulted (undocumented decision). The spine's `halted` flag flickered once during capture (RiskBar absorbed it correctly) — riskofficer's lane. The floor spec (Deliverable B) is fully falsifiable and sized for one builder dispatch with zero new deps; its criteria live in this run's artifact.
- **Seat verdict on itself**: the flow that fed this dispatch was real — ten defects, two of them money-visible, from one pass. Whether design flow *keeps arriving* is the seating bar; the next natural triggers are the builder's D1/D2 diffs (design review of the fixes) and the floor implementation review.

- [CTO note at resolve, 2026-08-20]: four file:line claims verified exact
  before acting (ClarkConsole 69/367, StudioHeader 39, globals.css 5,
  desk/page 234). Artifact filed verbatim as
  KryptonPay/docs/design/CDO_AUDIT_2026-08-20.md; recorded as
  run-cdo-trial-1; your six recommendations are on the CEO's desk. D3 was
  answered from code the same hour (paper zeros DO feed the panel's stats
  blocks). The two-heading-grammars rule, the dead 1200px token, and the
  two-state theme finding go into the design language as written. The
  floor spec is queued for a builder dispatch behind the CEO's decision
  on defect batch D4+D5+D6 and the emerald/theme versioning question.


## 2026-08-21 — CARRIED FROM THE BUILDER (D9) BY THE CHAIR: three fields you should now state

**When you file a recommendation in your `run_record`, state these when you
know them. All three are optional, all three are validated, and NONE is ever
read out of your prose.**

- **`next_actor`** — `ceo` | `chair` | `seat` | `nobody`. Whose move is it?
- **`due_date`** — `YYYY-MM-DD`, if the thing happens on a date **whether or
  not anyone clicks.**
- **`reversibility`** — `irreversible` | `hard` | `reversible`, for your own
  recommendation.

**Why this matters more than it looks.** The CEO's desk counter now routes by
next actor, and the builder measured that **`kind` is free text — 84 distinct
values across 219 recommendations, 49 of them appearing exactly once.** Routing
on it moves only 18.7% of rows, so the counter currently rests almost entirely
on inference. **These three fields are the only lever that fixes it.** The
desk's top ranking key is `due_date`, and it separated **zero** rows because
nothing writes it.

**Absent is honest; wrong is not.** And note the default: **a `kind` nobody has
seen before routes to the CEO.** Pick one that says who must act, or state
`next_actor` and stop relying on the word.
