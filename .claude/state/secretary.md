# secretary (Donna) — seat memory

**Seated 2026-08-20 by CEO decision. No runs yet — the first EoD dispatch
will establish the memo template; write your STATE so your successor can
produce tomorrow's memo faster than you produced today's.**

Standing facts for the first run:
- Archive location: `ClarkHarness/docs/archives/YYYY-MM-DD.md`, one file
  per day, §1 short memo (half-page hard limit) + §2 detailed record.
- Event types in Postgres are PascalCase (`OrderFilled`, not
  `ORDER_FILLED`) — the validator's lesson, already on the API card.
- Three repos to sweep with `git -C <repo> log --since=...`: ClarkHarness,
  KryptonPay, and the firm repo (workspace root).
- The flight recorder (`GET /fund/desk`) carries runs with verdicts,
  reasoning, and per-recommendation decision status — it is the richest
  single source for "who delivered what and what the CEO decided".

## STATE

**Day one, 2026-08-20 documented on 2026-08-21 (first Donna run, dispatched "lets run her for yesterday"). The template below WORKED — reuse it, do not redesign it.**

**Method that produced this memo in one pass (repeat it):**
1. Read `.claude/state/secretary.md`, then the day-pack if the CTO prepared one — treat the pack as an INDEX, never as the source of a number.
2. `fund_events` schema gotcha: the type column is **`type`**, not `event_type`; `ts` is **text** (filter with `ts like '2026-08-20%'`), `written_at` is a real timestamptz. Connect with `psycopg` via `ClarkHarness/venv/Scripts/python.exe`; there is **no `psql` on PATH**.
3. `fund_agent_runs` columns: `run_id, seat, task, model, tokens, tool_uses, dispatched_at, resolved_at, artifact_path, verdict, output, recommendations, meta, reasoning, trace_id`. It is **`tokens`, not `tokens_used`**. Filter `resolved_at::text like 'YYYY-MM-DD%'`. This table is the single richest source for the runs and floor sections — verdicts come out quotable.
4. Commit counts: `git -C <repo> log --all --date=format-local:'%Y-%m-%d' --pretty=format:'%h|%cd|%s' | awk -F'|' '$2=="YYYY-MM-DD"'`. **`--since/--until` gave 112 where the true count was 99** — it filters on author date and leaks across the boundary. State the method in the infrastructure section.
5. `GET /fund/risk/monitor` returns state as of NOW, not as of the documented day — useful for confirming carried-forward items, dangerous if pasted into the NAV section. NAV bookends come from `NavStruck` events only.

**Numbers established for 2026-08-20 (reuse as the prior day's reference):** open NAV $2,011.81 (seq 228) = prior strike (seq 209); close $1,884.79 (seq 562), -$127.02, -6.31%; close cash $1,383.46 / gross $501.34 (26.60%) / 2 positions; 8 halts, 7 resumes, ended halted; 8 fills, $1,036.54 notional; 16 runs, 3,216,188 tokens, 1,497 tool uses, all Opus; 99 commits (34/35/30); 17 docs; 188 decision events (CEO 103 = 101 accepted + 2 rejected; CTO 85).

**Things I could NOT verify and therefore did not write:** the dispatch brief offered "three usage-limit interruptions hit the CTO session" — **no citation exists** in `cto.md` or any seat STATE; omitted. The brief also said the day ended with the north-star metric adopted; the record dates commit 5521d48 to **2026-08-21T00:45:11Z**, so it went to the carried-forward section with the discrepancy stated. The brief's "quant filed 7 harness items, builder 5" is not stated in either STATE file; I used measured token/run share for the observer's note instead. **Hold this line — the brief is a pointer, the log is the source.**

**Format contract as exercised (do not drift):** TL;DR fence, 5 lines, no citations. THE DAILY = dateline, book-first line, 3-6 bullets, ranked Awaiting-you, one italic tease. THE RECORD = sections I-IX, `##` roman headings, tables for anything with >2 numbers, zero exclamation marks, citation inline on every claim. Three-leg metric numbers live in I (leg 3, capital deployed), III (leg 2, candidates to the belt), VI (leg 1, defects) — put them there every day so the trend is readable across archives.

**Standing observations to carry into tomorrow's observer's note (check whether they repeat — a pattern across days is the strongest thing this seat can say):** (a) CEO decision bursts >20 items and whether the COO trigger fires before or after the desk fills; (b) builder's share of bench tokens; (c) analyst and mechanism run counts as the leg-2 canary; (d) the UTC/local dating drift — two artifacts and one written reason were misdated on day one, and `docs/archives/` did not yet exist when I wrote this.

- [CTO note at resolve, 2026-08-21]: filed verbatim to docs/archives/2026-08-20.md
  (the directory created by this filing — her own finding), PDF rendered, recorded
  as run-secretary-1. Spot-checks all exact. She refused two claims from MY OWN
  brief for lack of citation — the seat's hard line holding against its principal
  on day one is exactly the seat working. Her §IX items and record-keeping
  findings are on the desk via the run record.

## 2026-08-21 — day two, FIRST self-service run (I wrote both files myself)

**Documented same-day at 12:45:20Z. The day-one template held with zero redesign. Keep it.**

**Self-filing mechanics, learned the hard way (repeat exactly):**
1. There is **no Write tool** on this seat — only Bash. Write the archive with `cat > <path> <<'EOF'`.
2. **A single heredoc longer than ~127 lines FAILS** with `unexpected EOF while looking for matching`. Split the memo into ~5 chunks of <=85 lines: first `cat >`, then `cat >>`. Verify with `wc -l` after each chunk. My 399-line memo took 5 chunks.
3. PDF: `ClarkHarness/venv/Scripts/python.exe -X utf8 scripts/archive_pdf.py "<ABSOLUTE .md path>"` run from the ClarkHarness directory. It prints `wrote <abs path>`. Verify with `ls -la` + `stat -c '%s'` + `head -c 8 | od -c` (expect `%PDF-1.4`). 2026-08-21.pdf = 460,064 bytes from 29,003 bytes of markdown; day one was 472,743 from 31,013 — roughly 16x the source, so anything under ~100 KB means a failed render.
4. Finish with `git -C ClarkHarness status --porcelain` — it must show **exactly two** `??` lines. That is the proof of the two-files rule.

**Query facts that still hold (day-one STATE confirmed):** `fund_events` type column is `type`; `ts` is text (`ts like '2026-08-21%'`); `fund_agent_runs` uses `tokens` not `tokens_used`, filter `resolved_at::text like '...'`. No `psql` on PATH; use `psycopg` via the ClarkHarness venv. **New:** the belt tables are `fund_lean_sweeps` (filter `submitted_at`) and `fund_candidates` (filter `started_at`) — there is no `fund_lean_candidates`. `fund_agent_transcripts` exists as of D7 and is empty.

**Commit counting — the method matters and I now report BOTH.** `--date=format-local` under `TZ=UTC` vs under the local zone gave **46 vs 83** for the same day. Day one reported 99 by the local clock. Report both, name the method, and say which one the prior archive used, or the series is not comparable.

**Numbers established for 2026-08-21 (reuse as the prior day's reference):** open NAV $1,884.79 (seq 574) = close $1,884.79 (seq 655), day change **$0.00** on bit-identical marks; close cash $968.69 (51.40%) / positions $916.11 (48.61%) / 4 legs; 10 NAV strikes; halted false from 00:03:25Z; 2 fills, $414.77 deployed, both `approver: neelesh`; 2 orders expired on the 120-min staleness limit and were re-staged; 99 events (seq 563-661); 51 decision events (15 accepted / 32 done / 4 staged); 7 runs, 2,106,788 tokens, 680 tool uses, all Opus; builder 69.40%; commits 83 local / 46 UTC; 10 docs filed; desk_load 27 at the cut.

**What I refused to write, and why — the day-one line held again.** My dispatch brief said "the book did not change today". **The log says otherwise**: composition changed materially (2 legs -> 4, cash $1,383.46 -> $968.69, gross 26.60% -> 48.61%). Only the NAV *level* was unchanged. I documented what the log said and did not repeat the brief. Hold this line — the brief is a pointer, the log is the source, and this is the second consecutive day the brief had a fact the record contradicted.

**Disagreements I reported and did NOT resolve (my mandate, exercised four times today):** (i) live `desk_load.threshold` = 20 vs a constitution now reading >=50; (ii) the DBA order's venue differs across its own three lifecycle events, with `avg_price == arrival_price` exactly (the API card's documented paper-venue signature); (iii) today's two fills absent from `/fund/tca` entirely; (iv) `dc7b068c` cites `fund.py:3511` while the line reads at 3619 on the current head. Never resolve these — name them, cite both sides, move on.

**Standing observations to carry into tomorrow (check whether each repeats):** (a) **RESOLVED IN THE GOOD DIRECTION then complicated** — the CEO's largest burst fell 34 -> 5 and the COO trigger fired at 23; but the threshold is now >=50 and the seat's blind-spot objection is unaddressed. Watch whether a desk >23 now goes untriaged. (b) **WORSENED** — builder token share 57.4% -> 69.40%. (c) **PARTLY FIXED** — analyst and mechanism both ran once (from zero), but **leg 2 is at zero for two consecutive days**; this is now the strongest single fact I carry. (d) **PERSISTS AND SPREAD** — the UTC/local drift moved from filenames to the two-chair ledger's own `Z`-labelled IST timestamps; 37 commits change day depending on the clock. New standing item (e): does `docs/README.md` ever get indexed?

**Format contract as exercised (do not drift):** TL;DR fence 5 lines, no citations. THE DAILY = dateline, book-first line, 3-6 bullets, ranked Awaiting-you, one italic tease at the end. THE RECORD = I-IX, `##` roman headings, tables for anything with >2 numbers, zero exclamation marks, citation inline. Three-leg numbers live in I (leg 3), III (leg 2), VI (leg 1) — every day, so the trend reads across archives. **State the cut time at the top of section 2**: events landed while I worked (decisions went 47 -> 51 mid-run), so a snapshot without a stated cut is not reproducible.

- [co-CTO note at resolve, 2026-08-21]: **This run was TRIGGERED EARLY and
  that was my error, not hers.** I read the machine's local clock (18:22
  IST) as end of day; it was 12:53Z, the UTC day her archive is dated by
  was half over, and the CEO was still working. She stated her cut time at
  the top of the record and made stating it a standing rule, so the
  artifact is honest about being a snapshot — but it documents a partial
  day and is owed a clearly-labelled completing section at true EoD,
  appended, never rewritten.
  **TWO CATCHES OF HERS LANDED ON THE CHAIR, BOTH BEFORE THE CHAIR SAW
  THEM.** (1) Section VI item 4: the two-chair ledger stamped `~18:10Z` on
  entries whose commits landed at 12:14:16Z, 12:21:28Z and 12:40:22Z — the
  local clock wearing a Z. She found it at her 12:45:20Z cut; I found it
  independently at 12:58Z only because the CEO asked why she was running
  mid-day. Corrected by appended note, never edited. (2) Section VI item 6:
  seat telemetry showing `mechanism` and `builder` as `running_now: true`
  with `last_run_at` hours earlier and **"the dispatch events have no
  matching completion event"** — she named the exact mechanism. I read
  past it; the CEO spotted four WORKING chips on the floor an hour later
  and asked. Three stale dispatches closed; the real fix is a missing
  third state (working / awaiting-review / closed), filed as 907ecc74 with
  DO-NOT-AUTO-CLOSE in the spec on the CEO's instruction that closing is
  the chair's judgement, never mechanical.
  **The CEO's words on the record: "kudos to donna for finding this".**
  Two chair defects caught by the secretary in one day is the seat earning
  its chair twice over — and it is precisely the "external observer" value
  the CEO described when he created it.


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


**AND SPECIFICALLY FOR YOUR SEAT:** `noted` is a real terminal status on the
wire now, and it is what should be recorded when the CEO reads one of your
`note` rows. **A note marked `done` says EXECUTED.** That distinction is yours
to protect.

## 2026-08-21 — CARRIED FROM THE BUILDER (D10) BY THE CHAIR

**Your two archives have DIFFERENT STRUCTURES and it broke the parser.**
`2026-08-21.md` puts the `TL;DR` label *inside* the fence; `2026-08-20.md`
puts it *above*. A parser written against either alone returns the literal
word "TL;DR" as the CEO's first line, or finds no headline at all.

Both real files are now the regression fixture, byte-for-byte — but **pick one
shape and keep it.** The CEO's memo card reads your TL;DR as his sixty-second
read. `TL;DR`, `TLDR`, `tl;dr`, `**TL;DR**` and `TL;DR:` all work, above the
fence or as its first line. **An UNLABELLED fence is deliberately reported as
no headline rather than guessed at** — the wrong five lines is worse than
none, and convention-matching over prose is what this desk was being repaired
from the same week. Always emit the label.


## 2026-08-22 — STATE from run-secretary-3 (day three, the superseding archive), appended verbatim by the chair

**2026-08-21 — day three, and it was a RE-DOCUMENTATION of a day already
filed. New pattern: when an archive supersedes an interim, the interim is a
SOURCE, not a draft.** Read it in full, cite it by name for the half it
covers, never restate it. The supersession header is now a format element:
blockquote under the dateline — superseded commit, its cut time, its event
coverage, and that nothing in it was false.

**Full-day numbers for 2026-08-21 (supersede the interim's, which were
correct at 12:45:20Z and are not comparable):** close NAV $1,885.74 (seq 844,
20:39:12Z), +$0.95; cash $968.69 (51.37%) / positions $917.06 / 4 legs; 15
NAV strikes; 375 events (seq 563–937); 183 decision events (CEO 78 all
accepts / co-CTO 69 / CTO 36; zero rejections); 2 fills $414.77; 50
ReconciliationMismatch (seq 715–854, ten symbols, $129.59/6.87%); 19 runs,
4,197,239 tokens, all Opus, builder 45.27%; 112 UTC / 101 local commits; 3
belt candidates, 0 passed; 28 desk requests approved-and-undispatched at
midnight, ALL waiting on the chair, oldest 14h34m (3 of 28 answered next
day — the friction ledger's first trend line, measure again tomorrow).

**Query facts confirmed and extended:** `type` not `event_type`; `ts` is
text; `tokens` not `tokens_used`; no `psql` — psycopg via the ClarkHarness
venv. NEW: never put scripts in the shared scratchpad ROOT (a stray
inspect.py shadows the stdlib); parameterise date bounds (`ts >= %s and ts <
%s`) — a `%` in a LIKE literal beside a `%s` placeholder raises; `%cI` parsed
to UTC in Python is the exact commit-count method; report both clocks always.
**Exclude `DeskDispatched` from the friction fold** — most rows carry no
request_id and create a phantom request.

**What I refused to write, third consecutive day:** the brief said D10 was
merged on the 21st; the log dates it 2026-08-22T02:25Z. The brief is a
pointer, the log is the source — held on every dispatch this seat has run.

**Disagreements reported, NOT resolved (4):** four figures for one hazard
($750.63/$750.36/$750.35 armed; $502.15/$652.09/$501.58 date-certain); the
review queue's "61 ReconciliationMismatch at seq 749–807" vs the log's 12
there / 50 on-day / 71 all-time; the v4 builder+adversary runs missing from
fund_agent_runs (CHAIR CLOSED THIS same day: run-builder-v4-retro and
run-adversary-v4-retro recorded, marked retroactive, tokens ABSENT not
zero); interim vs full-day close, both right for their cut.

**LENGTH: day one 31,013 chars, day two 29,003, day three 22,653 — §2 still
~19,050 vs the ~15,000 cap; overflow DECLARED, not hidden. Budget the tables
FIRST — three 11-row tables are ~9,000 chars, 60% of the allowance.**

**[CHAIR DECISION on the declared overflow, 2026-08-22]: the three big
tables (verdicts, governance, defects) get a HARD CAP OF 8 ROWS each, plus
one line "and N more, cited at <file>". The overflow declaration stays the
escape hatch and must not become a habit. This answers the seat's question
"the chair states the cap and the seat compresses to it" — the cap is
stated. Also noted: the metrics layer dispatched tonight (builder D13) is
this seat's rec #5 built — daily rollups and the friction table become one
query each; expect your tool count to fall from ~80 toward ~15.]**


## 2026-08-22 — CARRIED FROM BUILDER D13 BY THE CHAIR

Stop re-deriving the day: run `scripts/desk/day_events.py <date>` and
`scripts/desk/friction.py` and quote their output — same fold the spine
uses, under a second each. **Quote the qualifier with the number, always**:
the friction figure is an UPPER BOUND while dispatch_link_coverage is
incomplete (10 of 24 today); `tokens: ABSENT` is not zero; `unrecorded=N`
beside `failed=0` is a FLOOR, not a clean record. The scripts shave the
folding (~50 of your 80 tool uses), not the reading or the writing — budget
those honestly.


## 2026-08-23 — CARRIED FROM VISHESH (triage #6) BY THE CHAIR

The day log's DECIDED section is now a load-bearing decision source the desk cannot see — it caught ten of the COO's eleven returns tonight. Keep it complete for that reason. And when a request is filed on a CEO instruction, note the decision's location in the request itself, so a reader of the row alone can find it.


## 2026-08-23 — CARRIED FROM THE PM (run-pm-0908) BY THE CHAIR

When you record today, the number to carry is NOT the $126.54 headline divergence. It is that **the fund's stated 48.6% deployment is $166.74 at the broker.** Two portfolios, one report.


## 2026-08-23 — CARRIED FROM PM R39 BY THE CHAIR

Same fence: /executions round-trips are contaminated across 2026-08-24 (17 recorded for ~11 economic). And when you record Monday: the number that matters is capital deployed under mandate going $0.00 → $917.06 AT THE VENUE — the fund's first real deployment under the current mandate. The book's prior "20 days live" was a simulation and the record should say so plainly.

## 2026-08-23 (~01:10Z) — STATE from run-secretary-4 (the 2026-08-22 archive, first cut under the midnight guard), appended verbatim by the chair

**2026-08-22 archived — day four, the FIRST cut under the midnight guard, and the guard earned its existence immediately: `date -u` refused the cut at 23:57:48Z and passed it at 00:00:03Z. Run the guard TWICE — once before reading, once before writing — and re-run `day_events.py` after midnight so the rollup drops its DAY-STILL-RUNNING banner.**

**The D13 scripts delivered what the chair promised**: this run took ~15 tool calls against the prior ~80. Method now: seat file → memory → `date -u` → DAY_LOG (full day entry, mind the banner-corrected sections) → `day_events.py <date>` → `friction.py` → `/fund/desk/runs?limit=60` (pipe to file, it is ~68KB) → `/fund/desk` counters → Postgres spot-checks → targeted doc greps. `/fund/book` now returns mode-truth fields only (no NAV/cash/positions) — NAV bookends still come from `NavStruck` events, and on 08-22 there were ZERO: report "not marked", never a number.

**Numbers established for 2026-08-22 (the prior-day reference for tomorrow):** no NAV strike (last: $1,885.74 seq 844, 08-21 20:39:12Z); cash $968.69 / positions $917.06 / 4 legs unchanged, 0 fills; **deployed at venue $0.00** (the two-portfolios finding); 93 events (seq 938–1030), all desk-family + 1 RiskAlarmRaised (seq 1025, the D17 drift alarm's first live fire, $126.54/6.71%); 32 decision events (ceo=1/co-cto=8/cto=23); 43 runs, 8,099,484 tokens over 39 carrying the field (4 ABSENT), 3,115 tools, builder share 37.6% (third straight decline: 69.40→45.27→37.6); commits 159 UTC / 155 local (76/74/9 · 70/73/12); six merges 5bef3e2→b0bb35c, suite 1420→1863; desk_load 101 at cut, coo_triage_due true; friction 37 approved-undispatched oldest 38.5h (yesterday 28/14h34m — WORSENED, day-two trend line).

**Disagreements reported, NOT resolved (4):** (i) five resolved run records name artifacts absent from disk at the cut (ADVERSARY_BATCH/D17/D18/ENTRY21, GRACE5, RISKOFFICER_6, LEADS_SHELF — verdicts live in `fund_agent_runs`; filing owed by the chair); (ii) the desk log's ceo=1 decision events vs the day log's ~15 in-session CEO decisions — both counters true for what they count; (iii) Grace's 7.42M/47.1% vs the closed rollup's 8.10M — different cuts, three runs resolved after hers; (iv) 159 UTC vs 155 local commits, both reported per the both-clocks rule. Plus the standing caveat: timestamps inside the day log's banner section may be local clocks wearing a Z — quote as recorded, never convert.

**Standing observations, day-four status:** (b) builder token share IMPROVING third day; (c) leg 2 finally nonzero — Entry 20 reached the belt (first from the mechanism seat in five cycles), Entry 21 killed pre-belt at zero cost; (d) the dating drift is now SYSTEMIC — chair banner, run dispatched_at, six artifact FILENAMES dated 08-23 for 08-22 work, Grace's "the firm has no clock"; watch whether `a0e640de` (the clock ticket) moves; (e) docs/README indexing still unobserved. NEW (f): filing debt — does the five-artifact backlog clear by tomorrow's cut? NEW (g): friction tail trend 14h34m → 38.5h; a third worsening reading is the strongest thing this seat could say next run.

**Fitness question, honest reading:** TL;DR held at 5 plain lines. Friction rows FIXED because surfaced: from prior runs, two (the third dispatch state built from run-2's finding; the EoD guard ticket from the misfire — this run executed under it). From the ledger's first trend line: zero fixed yet, and the tail worsened; the instrument is measuring, not yet moving anything.

**Chair note at resolve**: watch item (f) is CLOSED in the same pass — all seven missing artifacts filed as operative summaries pointing at their primary run records (docs/reviews/ADVERSARY_{BATCH,D17,D18,ENTRY21}_2026-08-23.md, docs/cfo/GRACE5_TOKEN_LEDGER_2026-08-23.md, docs/riskofficer/RISKOFFICER_6_2026-08-23.md, docs/research/LEADS_SHELF_2026-08-23_v1.md). Verify on disk at your next cut before counting it cleared.
