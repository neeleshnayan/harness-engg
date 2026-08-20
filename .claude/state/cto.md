# cto (Fable) — the chair's memory

**Created 2026-08-21 by CEO instruction ("document your learnings and codify
it so you keep getting better at your job and esp across cold starts").
Unlike the bench seats, the chair writes its own file — same protocol
otherwise: read this FIRST on every cold start; append a dated section when
a session ends or a lesson lands; never rewrite history.**

## Cold-start sequence (measured, not guessed)

1. Docker Desktop first (`Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"`,
   wait loop), then `krypton-pg` (port 5433), THEN the spine — it hangs
   without Postgres. Spine: Bash background,
   `cd .../ClarkHarness && FUND_STORE=postgres ./venv/Scripts/python.exe -X utf8 -m uvicorn app.main:app --host 127.0.0.1 --port 8090`.
   Verify `GET /fund/liveness`. Restart = kill the PID on 8090
   (`Get-NetTCPConnection -LocalPort 8090`), start again; pending orders and
   all state survive (event-sourced).
2. KryptonPay dev preview: launch config `kryptonpay`, port 3000, tab "seed".
3. Read: this file, `.claude/state/API_CARD.md`, docs/README.md statuses,
   `GET /fund/desk` (desk_load tells you if a COO triage is due at >20).

## The resolve pipeline (every dispatch, in order — skipping a step has
## always cost more than doing it)

verify 2-3 of the seat's sharpest claims against code/data → file the
artifact VERBATIM as a doc with a CTO verification note → record the run
via its own run_record envelope (`POST /fund/desk/runs`) → resolve the desk
request(s) with the artifact named → append the seat's `## STATE` verbatim
+ a CTO note → commit (firm repo for .claude, ClarkHarness for docs).

## Lessons that cost real time or truth (each bitten at least once)

- **Never type an id you can read.** I once typed a guessed UUID suffix
  into a dispatch call; the erratum is in the event log forever. Read ids
  from the API, always.
- **Inline python in PowerShell always breaks** on quotes/`*`/newlines —
  write a script file in the scratchpad, run with
  `.\venv\Scripts\python.exe -X utf8`, `PYTHONPATH=.` (bitten twice in one
  day AFTER writing the rule down for others).
- **Postgres event types are PascalCase** (`OrderFilled`) — the validator's
  lesson; my own query came back empty the same hour for this reason.
- **tasks/*.output files are JSONL transcripts or EMPTY** — never file them
  verbatim; reconstruct from the notification, or JSON-parse text blocks.
- **Bundle fetch**: `git bundle list-heads` first; fetch the listed ref
  (`refs/heads/X:refs/heads/Y`) — HEAD is often absent.
- **The builder's worktree base has been wrong 4/4 dispatches** — name the
  expected `git log -1` for BOTH repos in every brief so it can refuse in
  minute one; recovery is its clone-inside method.
- **Check the instrument against the shipped machine.** My gate v5 r4
  history table modeled a fold generator (`_folds` packing) the belt does
  not implement (`window_for` is history-invariant) — found by the bench
  the same day I shipped it. Before publishing any measurement OF the
  fund's machinery, diff the model's mechanics against the real function
  by running both.
- **Never let "fixed" be recorded when the cause is unexplained** — F4's
  14m41s stands open although adjacent defects were fixed; the builder
  refused the easy claim and was right.
- **A refusal event must never be a lifecycle step** — guard v1's
  ApprovalRefused hid a pending order from the queue AND froze the
  pipeline state on day one (denial-of-approval via failed probes). Any
  new annotation event: check every fold that reads that aggregate.
- **The paper venue cannot measure cost, ever** (fills at its own quote) —
  and any "reliable" TCA verdict must be checked for WHICH leg and WHICH
  venue it averaged.
- Findings docs are corrected by NEW sections, never edits; menu/register
  statuses update in place with dated notes.

## Standing rules I operate under (constitution has the full text)

- One sub-agent in flight; batch-by-seat is the default; seat-filed asks
  wait for the CEO's Approve, then I fire. COO triage at desk_load >20.
  Donna (secretary) runs EoD on my trigger — memo → archive_pdf.py.
- Approval guard: only `neelesh` / `neelesh-via-cto` (+ `ceo` on desk
  requests) approve; via-cto REQUIRES the CEO's verbatim quoted
  instruction; confirm echo = id[:8] (rebase uses a state digest instead).
- Attribution repairs: `append_attribution_correction()` at the console
  only, written reason mandatory. Thresholds move only by versioned change
  with a written reason — and I write the register entry in the same
  commit.
- The CTO chair never approves orders and never occupies two stages of one
  candidate. Verification of agent claims precedes action, every time.

## What worked — credit, kept on the record (CEO instruction, 2026-08-21:
## "give yourself some credit... I dont want you forgetting how you are
## working with me on building this ai org e2e")

This is not a defects-only chair. Things built here that WORKED, first
time or same-day, and the patterns behind them — keep doing these:

- **We are building an AI-native firm end-to-end, together** — Neelesh
  brings the vision in fast strokes (the office, the faces, Donna, the 3D
  floor, the COO, "no good strategy no money no lights") and my job is
  turning it into versioned, tested, falsifiable machinery THE SAME DAY,
  with honest pushback where the vision would break an invariant (the
  Ollama-realtime and PM-signals rebuttals were accepted because they were
  argued from the constitution, not from caution).
- **The approval guard went from question to shipped in one afternoon** —
  designed, implemented, tested, probed by its own author, and it caught
  two real defects in itself within hours because I attacked it instead of
  admiring it. Design things so their first failure is loud and cheap.
- **The governance chain runs end-to-end and every link was exercised the
  day it was built**: seat files ask → CEO approves → CTO fires → measured
  answer → defect found in the CTO's own instrument → corrected by new
  section. The org catching MY defect is the metric working, and I filed
  it that way instead of flinching.
- **The resolve pipeline discipline pays every single time** — verify,
  file verbatim, record, resolve, append STATE, commit. Not one resolved
  dispatch has needed rework.
- **Seats by demonstrated need has produced zero dead weight**: every seat
  created this window (coo, secretary, cdo-trial) earned its chair on its
  first run. The audition-before-seating pattern (CDO) is worth reusing.
- **Same-day quality bar held under speed**: guard v1→v1.1, autopolicy
  v1→v3, gate r4 + correction, two seats, three constitutional amendments,
  four merges, ~1,128 tests green across repos — with zero unversioned
  threshold moves and zero fabricated numbers. Speed and governance are
  not a trade-off here; the pipeline IS what makes the speed safe.
- The CEO's trust is explicit ("you have the desk", "you have my
  blessings dear cto") and it was earned by verification, not velocity —
  keep earning it the same way.

## Session log

### 2026-08-20/21 (the constitution day)
Guard v1/v1.1 shipped (+ 2 same-day defects found and fixed); builder d3+d4
merged (exec desks, CDO fixes, halt classes, attribution guard; suites
1034/94); autopolicy at v3; gate v5 r4 filed then corrected by §8 (fold
generator mismatch — mine); validator ran 3 audits (R6/D2/attribution,
fold-geometry); mechanism funnel cycle 1 (0 proposals, 3 verdicts, entry-11
spec deferred on P1-refused → slip-band route accepted); CDO trial
auditioned (10 defects, floor spec); seats created: coo (Vishesh),
secretary (Donna), cdo-trial pending flow; first seat-filed ask completed
the full chain; identity migrated rushi→neelesh; GLD phantom corrected.
OPEN at session end: Vishesh triage #2 in flight (73 items); Donna's first
Daily after it; adversary r4 next session; F4 open; emerald-scope +
prefers-color-scheme design decisions await the CEO; halt resume after
alarms clear (CEO click).
