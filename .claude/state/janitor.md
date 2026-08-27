# janitor - seat memory (read first on every dispatch; the chair appends STATE verbatim at resolve)


## 2026-08-27 — STATE from run-builder-jan1 (the audition run; the seat's founding memory), appended by the chair

**builder/janitor — after dispatch JAN1 (2026-08-27), the janitor program's first full pass. AUDITION PASSED; this file is the seat's memory from here on.**

- **Base `89d45f0a` was correct and I created the worktree myself.** Live head moved to `d0fda2b7` mid-dispatch (3 commits) with zero file overlap — the chair's mid-dispatch scope fence (`app/api/v1/fund.py`, `app/fund/desk.py`) was accurate and held.
- **THE TOOLING: `ruff` AND `vulture` LIVE IN THE PROJECT VENV, NOT ON PATH.** `ClarkHarness/venv/Scripts/python.exe -m ruff|vulture|pytest`. Bash's default `python` is the hermes venv and has none of them. Charter-baseline ruff version pinned in `.ruff_cache/0.16.4`. `ts-prune` is in the npx cache (`AppData/Local/npm-cache/_npx/1532855dfcb86dac`), entry `lib/index.js` NOT `lib/cli.js`, needs `NODE_PATH` to that cache's node_modules.
- **A CENSUS REGEX NEEDS ITS OWN NULL CHECK BEFORE ITS RESULT IS A RESULT.** My first two tolerance regexes anchored `^\s*_?[A-Z]` and missed every leading-underscore constant — including `reconcile._TOL`, the type specimen the brief itself named. 8 of 15 found, invisibly. Grep for the ONE symbol you already know must appear; if absent, the regex is wrong, not the tree.
- **TO PROVE A UNIFICATION BOUGHT SOMETHING, RUN THE OWNER-MOVES MUTANT AGAINST THE BASE.** Three times this dispatch the base was fully green under a mutant the fixed tree kills: test_execution 21/21 while two folds disagreed on the bucket name; test_tca 25/25 while tca ignored SIMULATED_VENUES; test_venuesync 40/40 while venuesync kept its own 1e-6. The before-arm is the whole finding. `git worktree add --detach <path> <base>` costs 20 seconds.
- **`Decimal(d) is d` IS TRUE in CPython's C _decimal when d is already an exact Decimal** — so `Decimal(x)` is NOT a copy and a mutant built on it asks nothing. `+d` and `Decimal(str(d))` ARE real copies. Decimals are not interned, so `a is b` is a genuine read-vs-copy proof for a Decimal constant; for a str it proves nothing (interning) — use mutation there.
- **MY OWN SOURCE-SCAN RULE BIT ME IN THE SAME DISPATCH I APPLIED IT**: `assert '"paper"' not in src` failed because my NEW docstring explained the removed literal. Code-only scan (`src.rsplit('"""',1)[-1]`) + pin the whole statement with indentation. Write the source pin AFTER the comment, never before.
- **AN EQUIVALENT-TODAY MUTANT IS STILL WORTH A PIN WHEN THE MECHANISM IS THE POINT** (M14: a derived tuple replaced by its equal literal — silently re-creates the drift; three lines of source pin converted it to a kill). Distinguish from a genuine no-op (M6) and a control arm whose survival is required (M8).
- **A COMMENT CITING A TEST FILE IS A CITATION AND GOES STALE**: executionquality named `tests/test_executionquality.py` as its guard — the file does not exist (the pin lives in test_executionquality_store.py). And two line citations in pipeline._runtime_venue were stale by the same 23 lines. Cite by SYMBOL; when fixing a line citation, record the old number.
- **THE SUITE IS GREEN ONLY WITHOUT THE REPO'S OWN `.env`** (test_venuesync with .env: 1 failed / 28 errors, all PriceUnavailable — IDENTICAL on base, pre-existing; every builder works env-less so nobody had seen it). Full extent UNMEASURED (3 files, not the suite).
- **A RED BASELINE IS A PREMISE, NOT A PROBLEM — MEASURE IT AND MOVE**: base opened 1 failed / 6378 passed; the failure was psycopg 0x00002740 Address-already-in-use = client-side ephemeral-port exhaustion (74/74 in isolation, never recurred). Say which it is.
- **EDITING A SOURCE FILE WHILE THE FULL SUITE RUNS INVALIDATES THE RUN, EVEN A COMMENT** (linecache/subprocess re-imports read disk). I discarded a green 6387 and re-ran clean rather than explain it away.
- **Verified shapes**: `execution.py` is a read-only fold despite the name (submits nothing; safe to edit). `deskhygiene` and `executionquality` deliberately import nothing from app at module level — the codebase idiom for pure modules is MIRROR-AND-PIN, not import (`desk.TERMINAL_STATUSES` / `deskcard.DECIDED_STATUSES` are the reference pattern). `deskstore.REC_STATUSES` owns the recommendation vocabulary. `reconcile` imports connectors.base/events/money/projections.positions, so venuesync→reconcile is cycle-free.
- **New/changed surfaces**: `deskstore.LIVE_REC_STATUSES` (derived) + `deskhygiene.LIVE_REC_STATUSES` (pinned mirror); `tca` reads `executionquality.SIMULATED_VENUES`; `execution` reads `projections.strategy.DISCRETIONARY`; `venuesync.QTY_TOLERANCE` IS `reconcile._TOL` (autopolicy's copy stays DELIBERATE, test-pinned — a control's threshold must not silently follow another module).
- **THE CONTEXT BASELINE (lane 2's founding numbers, 2026-08-27T11:59:59Z)**: 29 files, 22,902 lines, ~471k tokens. Top by TOKENS: builder.md 63,898 (1,422 ln — 43 regular dated STATE appends = the clean archive shape), DAY_LOG 58,521 (3,589 ln), CTO_REVIEW_QUEUE 38,426, adversary.md 35,824 (885 ln — would never trip a line threshold), mechanism.md 28,542. A builder dispatch pays 76,272 tokens before its brief. RANK BY TOKENS; density varies 3x.
- **THE TS CENSUS (lane 1's KP input)**: 562 ts-prune lines = 30 TRUE dead (6 studio incl. two retired-by-comment components + Sparkline/SpineTelemetryBlock/stationIndex/BILLBOARD_TRANSFORM; 24 legacy web3; + src/app/docs/page.backup.tsx), 58 framework entry points, 416 in-module, 57 TEST-ONLY FALSE POSITIVES (ts-prune cannot resolve this repo's `.ts`-suffixed test imports — a raw-list deletion pass would delete tested code), 1 Abhishek. Null arm run; domain 57 test files / 845,456 chars.
- **DEBT CLAIMS (13, for the guide store)**: D1 tradestream backoff never resets (the dead else IS the fix that never ran — report, never delete); D2 exitrule.py:297 born-dead local (control, versioned deletion); D3 pgstore EventType (event-store, Tier-3); D5 THE GUARD'S INLINE CHAIR-IDENTITY SET x2 (LOOSENING direction — riskofficer); D6 deskcard._VIA_RE admits ceo-via-cto (refused by the guard); D7 tca alias (3-file removal); D8 optimize_portfolio returns equal weights on ANY exception while reporting the requested method (live endpoint, absence-collapse); D9 six remaining unpinned status-axis sites (desk.py x3, tickets.py x2, fund.ADVANCING_REC_STATUSES); D10 the 1e-6 family map (owner / reader / deliberate-copy / coincidence — recorded so nobody "cleans it up"); D11 the 30 KP dead exports; D12 ts-prune under-resolution; D13 stale line citations (fixed, symbol-cited now); D14 the .env-on suite.
- **Fitness**: production +65/−36 = 1.81:1 overall — best this seat has posted by two orders of magnitude — and the PURE-DELETION LEG INVERTED at 0.44:1 (+4/−9). Tests +179/−0. The overall non-inversion is structural and correct: a unification trades a deleted literal for a comment naming the owner, which is the charter's own instrument working. ruff 30→20; three silent disagreements now impossible; 16 mutants 0 survivors; 6381→6389 collected, none dropped.

**CTO note at resolve (Fable chair, 2026-08-27)**: AUDITION PASSED against
the pre-registered criteria — census spot-checked to the digit, U4
verified in the diff, the tradestream refusal is the judgement that sealed
it. Seat created (.claude/agents/janitor.md, three lanes, plain identity);
this file is its memory from here on. Merged; merged-tree suite in
flight. The context lane ranks by TOKENS (your bind, adopted); D5 rides
tomorrow's riskofficer batch; the KP deletion pass rides B2; the .env
suite measurement queues after B1. Zero-helper with self-run null arms
was the right call and is noted as the seat's cost discipline baseline.


## 2026-08-28 — STATE from run-janitor-2 (context pass + skill miner), appended by the chair

**janitor — after dispatch #2 (2026-08-28), context lane's first commissioned split + skill-miner first run.**

- **THE SPLIT METHOD THAT SURVIVED**: byte-level Python split on `splitlines(keepends=True)` — awk/sed are NOT byte-faithful on this repo's mixed CRLF/LF state files (measured: awk lost 1,396 bytes reassembling builder.md; ~112 lines are LF-only in a CRLF file). Headers written with the Write tool (the builder's heredoc rule held for me too), bodies concatenated in binary. `builder.md` boundary: line 1104 = the first 2026-08-26 heading; the file's own append order made the cut exact.
- **THE VERIFY SHAPE**: ends-with on each half + concatenation identity + heading census (81 -> 59/22) + line coverage + a null arm that corrupts a copy and must fail (it failed with 61 problems). PASS on the live file. The script refuses any original that is not 270,765 B / 1,508 lines rather than guessing a boundary.
- **THE TARGET CONFLICT, reported not fudged**: hot ~= 25.3k tokens vs the brief's ~20k, because the keep-whole 08-26+ block alone is ~19.7k. Chair's lever: accept, or move the boundary to 08-27.
- **I DEVIATED FROM THE BRIEF'S "newest first" FOR THE ARCHIVE** — original append order kept, because entries cross-reference positionally ("supersedes the bullet above, by append not edit"). Move-never-delete outranks a formatting instruction; flagged for the chair.
- **BINDs ARE BROADCAST COPIES**: identical carried blocks live verbatim in multiple seat files (the compute-scarcity block in builder.md AND quant.md). Archiving one file does not archive the copies; future split savings must be computed per file, and a lesson "archived" in one file may still be hot in another — which also softens the lane's falsifier reading (a seat re-deriving a lesson archived in ITS file but hot in another's is a routing gap, not a distillation failure).
- **NEXT SPLIT CANDIDATES BY TOKENS** (0.245 tok/B on current bytes): adversary.md 152,146 B ~= 37k (grown from the census's 35.8k — but the immune-system exclusion means any adversary.md split proposal needs explicit chair/CEO framing: moving its content is not amending its mandate, and I will not touch it without that ruling in writing), mechanism.md ~= 28.7k, validator.md ~= 27.5k, quant.md ~= 24.6k (heavily duplicated carried blocks — cheapest real win may be deduplicating broadcast copies against builder's archive, which is a NEW operation class the charter doesn't yet cover: flag before doing).
- **Desk run window is 25 runs** — run-record mining beyond that window must go through Postgres/`fund_agent_runs`, not `GET /fund/desk` (the builder's own OPEN_RECS_RUN_CAP lesson, applying to my own instrument).
- Deliverables in scratchpad/janitor2/: builder_hot.md, builder_archive_2026-08.md, builder_split_verify.py (+ working files). Deletion-ratio question: N/A this pass — context lane deletes nothing by charter; zero code touched.

**CTO note at resolve (Fable chair, same hour)**: your split is APPLIED —
isolated context commit 451a81d8 under the versioned-context discipline the
CEO adopted this morning (your verify re-run by the chair first: PASS, null
arm fired). Both your deviations were accepted with your reasoning: 25.3k
hot (the relevant-items-stay bar outranks the numeric target) and
oldest-first archive order. The DAY_LOG and queue proposals ride the desk
for the chair's next EoD pass; your six skill candidates are filed; the
adversary-split ruling is routed to the CEO in plain English. The
broadcast-copies finding is the sharpest thing in this return — it goes to
the chair's own memory too, because the resolve pipeline (mine) is what
creates the copies.
