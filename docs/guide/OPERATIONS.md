# OPERATIONS — the runbooks, each born from an incident

The rule: a runbook enters when a sequence has burned us done wrong, or
saved us done right. The incident is cited; the runbook is the correction
made muscle.

## Cycle the spine (born: the orphan-container finding, ENG2, 2026-08-27)

1. **Stop live LEAN sessions FIRST** (`DELETE /fund/lean/live/{id}`), verify
   container death (`docker ps` shows no `lean-live-*`). A container started
   by the spine OUTLIVES the spine; restarting first strands an unstoppable
   orphan still holding a valid signal token.
2. Kill the listener on :8090, restart with `FUND_STORE=postgres` (no
   default — the last default silently relocated the whole ledger).
3. Verify `/fund/liveness` 200 AND `/fund/health` says backend postgres.
4. Restart sessions ONCE, one caller — two callers 2ms apart both got 200
   (the TOCTOU race, ticket dc12903f, 2026-08-26).

## Start a daily-bar live session (born: quant dispatch #7)

- After the bar settles: US equities ≥16:15 ET; crypto after 00:00 UTC.
- The strategy is REGISTERED first (unregistered → every signal 404s
  silently and nobody sees anything).
- The algorithm file is COMMITTED before the session starts (it traded
  untracked once — ENG2 finding, 2026-08-27).
- `set_benchmark` to its own custom symbol or live-paper dies on the SPY
  minute subscription.

## Merge a builder stack (born: the hw4 three-way near-miss, 2026-08-26)

- `git merge` ONLY — never apply the diff, never `checkout -- app/`, never
  squash. Frozen base SHAs; a stacked dispatch names them or serializes.
- Full suite on the MERGED tree via `scripts/suite_lock.py` (two builders
  serialize on Postgres through it, not just RAM).
- The merge gate's "0 sensitive" on fund.py is UNPROVEN, not clear
  (adversary-confirmed blind spot) — the builder states which control the
  diff touches in its own words, and the chair reads that, not the count.
- After merging: run every suite that CONSUMES the changed rule, not just
  the ones that test it (routing v2 left the branch red for 2h because the
  chair ran six suites and missed the seventh — 2026-08-27).

## Sweep the CEO's desk (born: Donna's mandate + the MONDAY cards)

- No citation, no close. Already-actioned closes with the receipt, never
  re-executes. Anything unclassifiable STAYS, flagged.
- Check where a filing ROUTES before filing it (five chair tickets landed on
  the CEO's desk on cleanup day — routing v1, 2026-08-26).
- Read ids from the API; never type an id you can read (a guessed UUID tail
  is in the record forever).

## The resolve pipeline (standing, every dispatch)

verify sharpest claims → file artifact verbatim → record the run (with
`dispatched_at` and `status` — the recorder cannot know them later) → append
STATE verbatim → carry BINDS (strike what you disagree with, in writing) →
close the lamp → confirm the load moved.

## Host revival (born: the two-day outage, automated 2026-08-27)

Bottom-up: Docker Desktop → krypton-pg → spine. Automated in
`scripts/host_watchdog.ps1` (5-min scheduled task). The watchdog revives;
it cannot save in-memory sessions — a vanished session after a revival is a
watchdog event, read the log before hunting ghosts.
