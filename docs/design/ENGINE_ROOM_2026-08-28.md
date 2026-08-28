# The Engine Room — re-imagining /clark/studio/engine (2026-08-28)

**CEO instruction: "re-imagine this page for me", queued to the co-CTO's
builder batch. Chair's design; builder implements in the worktree; ordinary
merge path.**

## What is wrong with the page today (read against the live render)

1. **It is a museum wearing a dashboard's clothes.** The dominant content is
   one dead GLD signal from 11 days ago and its fenced history. The engine's
   actual day — 59 belt containers for P1, a crypto probe, a live HYG session
   priming 1,379 bars — is invisible or one line.
2. **The belt does not exist on the page.** Backtests and candidates ARE the
   engine's main workload; "what did the engine do today" is unanswerable.
3. **The quiet-vs-dead blind spot is displayed as a caveat although the
   instrument to close it now exists** (the v2 BAR heartbeat + a known
   delivery contract). A page that states a solved problem as unsolvable is
   stale honesty.
4. **No expectation clock.** For a daily-bar session the one number that
   proves liveness is "next bar expected at T; last bar received at T−1".
5. **A distribution drawn from one point** (the signals axis) is noise
   rendered as instrumentation.

## The re-imagined page: four bands, in the CEO's question order

### 1. NOW — the pulse (one card per live session)
Algorithm · strategy · started · container dot (docker state) · **last BAR
received (age)** · **next bar expected (countdown)** — expectation derived
from the session's declared delivery contract (daily custom feed: within 30
min of 00:00 ET). The card's centrepiece is a PULSE RAIL: expected ticks vs
received ticks as geometry. **A session past its expected bar renders
MISSED, loudly (the one amber on the page); a quiet-but-on-schedule session
renders calm.** Dead and quiet stop looking identical — that caveat retires.
Sessions read the results log's `BAR ` heartbeat lines (v2 pattern; a
session without heartbeat lines says "no heartbeat instrument — liveness
unprovable", honestly, instead of implying it for all).

### 2. PRODUCED — the last 7 days, never "ever"
Two lanes side by side:
- **Signals lane**: proposed → declined-by-envelope (labelled BY DESIGN when
  `side_is_sell` is the failed check — a refused BUY is a working control) →
  awaiting click → filled. Rolling 7 days; the full history behind a caret.
- **THE BELT LANE (new)**: recent backtest jobs and candidates — algorithm,
  containers spent, duration, gate verdict with failure count, link to the
  candidate and (when one exists) the strategy DOSSIER. Yesterday's P1 run
  would read: `eth_wrapper_premium · 59 containers · FAILED 3 (premia leg
  clean) · dossier →`.

### 3. AGREE — three books, per symbol, live only
Engine-implied vs fund fold vs venue for LIVE sessions only; per-symbol rows
(quantity today; the mark column lands with the reconciler's per-symbol mark
rider when built). Fenced history collapses behind one caret with its count
— kept, never front-page. Per-strategy performance chip per the CEO's
baseline framing: realised P&L from fills + "vs benchmark" where the
strategy declares one, with an honest "too early to read" state.

### 4. WHAT THIS PAGE CANNOT SAY — kept, but curated
The honesty section stays; each caveat carries a retire-condition, and a
caveat whose instrument has since shipped is REMOVED rather than displayed
forever. (First removal: quiet-vs-dead, retired by the pulse rail for
heartbeat-carrying sessions.)

## Style
The B2 idiom: hierarchy from type and space; band-as-geometry; semantic
colour only (MISSED amber, failure red); every list bounded with an honest
tail; empty states are sentences, not blank regions. No new endpoints unless
forced — the page reads session logs' BAR lines via the existing results
path, `/fund/lean/live`, `/fund/factory/candidates`, `/fund/venue/reconcile`.

## Acceptance
(1) A screenshot answers "is it alive, what did it do today, do the books
agree" in one viewport without scrolling. (2) The GLD fenced history is one
collapsed line. (3) A session with a missed expected bar renders MISSED
within 30 minutes of the miss (pin the fold with a fixture). (4) The belt
lane shows yesterday's P1 run correctly from the stored record. (5) KP
suite + tsc green; no spine changes beyond read-only additions if any.

## AMENDED same day (CEO): the status dot + the Lab merge

**1. The engine dot (nav-level, visible from every tab).** The nav's Engine
item carries a status dot: **green pulsing** = at least one LEAN session
running; **red steady** = none running; **grey** = the spine is unreachable —
unknown is its own state and must never render as red or as stale green
(absence is not a value). Fed by the session list on the studio's existing
polling cadence; the dot's tooltip names the session(s) and the last-bar age.

**2. Lab folds under Engine — one page, the factory as a flow (CEO: "run
your tests and leans run on one page and final deployed on another -
seemless end to end").** The merged page's sub-views, left to right, ARE the
lifecycle:

    BENCH (author + backtest — today's Lab) → THE BELT (candidates + gate
    verdicts, the new belt lane grown into a full view) → LIVE (the Engine
    Room: pulse rail, signals, agreement)

The nav gains one Engine entry with three sub-tabs and loses Lab. **The
governance boundaries render as explicit GATES in the flow, not seams to be
smoothed**: between Belt and Live sits the gate verdict and the CEO's click,
drawn as a visible gate the flow passes through — the friction is the
product, and the demo is better for showing it. A strategy's position in
the flow mirrors its dossier stage; each stage links to the dossier.
