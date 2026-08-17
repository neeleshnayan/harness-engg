# Sprint brief — 2026-08-17 → +3 days

You are continuing work on **Krypton Fund**, an agentic hedge-fund harness
running a real $2k friends-and-family book (paper venue). Three repos, all on
branch `claude/krypton-fund-agentic-j8r2mu`:

- **ClarkHarness** — Python/FastAPI event-sourced spine. Port 8090, run with
  `FUND_STORE=postgres`. Venv at `ClarkHarness/venv`.
- **KryptonPay** — Next.js frontend, port 3000. Studio design tokens live in
  `src/app/clark/studio/theme.ts` — never branch on theme in components.
- **Krypton_Clark** — Strands agent orchestrator, port 8000, local Ollama.

Read these first, in order — they are the source of truth for this sprint:

1. `ClarkHarness/docs/ROADMAP.md` — the plan, with a critical-read section.
   You are executing **Horizon 1 (#26–#29)**, then **#31 and #33**.
2. `ClarkHarness/docs/ARCHITECTURE_REVIEW_2026-08-17.md` — consolidation rules
   to apply *as you touch code*, not as standalone rewrites.
3. `ClarkHarness/docs/RESEARCH_XS_MOMENTUM_2026-08-17.md` — how research notes
   are written here, and the four harness bugs just fixed (do not reintroduce).

## The mission

The bottleneck has moved from infrastructure to edge discovery. The phase
metric is **truthful verdicts per week** — never gate passes. A pass is an
outcome; the moment it becomes a target, the gate is what's being optimized.

Suggested day plan — adjust with judgement and say when you deviate:

- **Day 1:** #26 (as-of universe membership + survivorship haircut on the
  control) and start #27 (the null audit can run in the background overnight).
- **Day 2:** finish #27 (injected-edge audit, feed cross-check, walk-forward
  holdouts), #28 (aim filings sweep at the band — long-running, background),
  #29 (re-judge INTC and the three legacy strategies; write flatten/keep memos).
- **Day 3:** #31 (morning digest) and #33 (paging file, LEAN container
  semaphore, schedule the Firestore snapshot). Stretch: first #30 candidate
  family through the factory.

Each roadmap item has a **Done when** — that is the acceptance bar, not the
activity around it.

## Hard invariants — violating any of these is failure, whatever else ships

1. **Never fabricate or hardcode a financial number, timestamp, win-rate or
   fallback value.** An absent number is reported absent.
2. **NAV folds from the event log only.** Broker equity is a comparison, never
   the truth.
3. **LEAN proposes; it never executes.** No brokerage key reaches strategy
   code. Clark proposes; the human clicks Approve — you never take the click.
4. **You deploy and allocate nothing.** The flatten/keep decisions on the
   legacy book belong to the user; your deliverable is the evidence memo.
   Sequence any trade recommendations around the PDT constraint (one day trade
   left before the 90-day flag).
5. **Abhishek owns everything thesis-side**: `app/fund/thesis_generator/**`,
   `tests/test_thesis_generator.py`, `src/app/clark/studio/thesis/**`, and his
   types in `fund_api.ts`. No edits there — not even import cleanup.
6. **The gate moves only by versioned change with a written reason — in either
   direction.** If calibration (#27) shows the PSR floor unclearable on our
   history length, propose `v2` with the evidence. Quiet loosening is the one
   forbidden move.
7. **The paper connector stays.** Flipping to live Alpaca is the user's
   explicit decision, never a side effect of a fix.
8. **Absence is never zero.** No-trades ≠ 0% retention; unclassified ≠
   non-operating; unreviewed ≠ dismissed; a crashed run ≠ a 0% result. This
   pattern is the house style — extend it, never break it.
9. The demo seeder never runs against production. `.env` and service-account
   keys stay gitignored.

## Working style that is expected

- **Tests as their own command, output read, then commit as a separate step.**
  A combined command once hid two failures behind a passing tail.
- **When a result surprises you, isolate before you fix.** This week's page
  count was "fixed" by shrinking fonts three times before a slice test showed
  a structural bug; the flat benchmark and the 57-second NAV were the same
  lesson. Bisect, slice, measure — then change one thing.
- **When a contract changes deliberately, change its test and say so** in the
  commit/note. Never work around a failing test, and never leave one failing.
- **Write findings as research notes** in `docs/`, in the established style:
  negative results reported as carefully as positive ones, corrections
  recorded rather than papered over, every number the system's own.
- The user may be away for stretches. Keep going; maintain a short
  **"needs the user's click"** list instead of blocking on questions.
- Velocity over security-hardening for now (user's explicit stance) — but the
  invariants above are not security hardening, they are the product.

## Traps that will bite you (all hit this week)

- LEAN parameters: `--parameters fast:17,slow:44` comma form ONLY. Space-
  separated errors; repeated flags silently keep the first.
- Algorithms need `self.set_warm_up(lookback + 5, Resolution.DAILY)` — without
  it a test window shorter than the lookback places **zero trades** and scores
  a fake 0% the gate now flags as "never examined", not as evidence.
- Spine bars start 2024-02-26 (~4 bars before 2024-03). In-sample windows for
  long lookbacks must start 2025+ — that is a data limit, not a bug.
- LEAN emits zero-filled / zero-padded benchmark curves for custom data types.
  The harness discards them and rebuilds from fund bars against the algorithm's
  declared `UNIVERSE` — do not re-trust the engine's series.
- A job's `state` flips to `done` only **after** enrichment. That ordering
  fixed a race where the gate judged half-built results — do not "optimize" it
  back.
- **15.2 GB RAM is the ceiling.** Stacked LEAN containers die with
  `WinError 1455` — it killed a holdout run mid-day. One sweep at a time until
  #33's semaphore lands.
- Polygon/Massive: throttled to 4 req/min in `app/fund/polygon.py` (it blocks,
  by design). Bulk reference endpoints return 1,000 rows/call — the only way
  to work at universe scale. History ≈ 730 days. Primary `api.massive.com`,
  fallback `api.polygon.io`, key in `.env` as `POLYGON_API_KEY`. Polygon.io
  rebranded to Massive 2025-10-30 — same key both hosts.
- Jobs/sweeps mirror to Postgres (`fund_lean_jobs` / `fund_lean_sweeps`) and
  survive restarts; a sweep restored mid-flight reports `interrupted` with the
  points it finished. Live LEAN sessions are still memory-only.
- Restart discipline for the spine: kill the :8090 process, relaunch with
  `FUND_STORE=postgres`, then verify NAV reads **$2,026.89** (± real market
  movement) and the chain verifies before continuing. If either is off, stop
  and investigate — do not proceed on a broken spine.
- PowerShell scripts ASCII-only: BOM-less UTF-8 gets read as ANSI and em-dashes
  break parsing.
- qwen returns empty/max-token turns on no-tool steps: use Ollama
  `think=false` there; never re-run the orchestrator to repair a turn.
- Postgres event appends: `encode()` **before** `event_hash()` — Decimals must
  become strings or stores disagree about identical events.

## Sprint definition of done

- As-of universe membership exists; the control re-run's survivorship haircut
  is published in a research note (#26).
- The gate's operating characteristics are **stated, not assumed**: null-audit
  pass rate, injected-edge result, feed cross-check outcome, walk-forward
  holdouts in place (#27). If the verdict is "the floor is unclearable", that
  is a successful outcome — write it up and propose gate v2.
- Band coverage is the map's headline number and the nightly band-aimed
  filings sweep is scheduled (#28).
- INTC and the three legacy strategies are re-judged with warm-up; a one-page
  flatten/keep memo per strategy sits in the "needs the user's click" list (#29).
- The morning digest exists and renders (#31); the semaphore, paging-file fix
  and snapshot schedule are in (#33).
- Full suite green (761+ tests — grep-guard that NAV still folds from the
  event log), every new behavior carrying a test whose docstring explains the
  reasoning, in the codebase's voice.

## Report back

End with: what shipped, what the numbers say (the haircut, the null pass rate,
the injected-edge result, band coverage), what died and why in the gate's own
sentences, and what needs the user's click. An honest negative result is a
win — the harness exists to make them cheap.
