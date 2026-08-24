TL;DR
```
The last three and a half hours of Sunday were the most consequential of the day.
The execution-quality instrument merged and went live before Monday's open, the
Entry 20 premia re-run finished at 23:58Z after four and a half hours on the belt,
and the CEO handed the chair a class of decisions back ("not my decision per v2").
No money moved: no fills, no NAV strike, no alarms.
For the CTO: eleven items on the CEO's desk of forty-two do not need him, each cited.
```

# THE RECORD · 2026-08-23 (COMPLETING SECTION)

> **Scope.** This file completes `docs/archives/2026-08-23.md` (commit `231f415`,
> filed 20:38:01Z), which was cut INTERIM at 20:24:48Z host-UTC while the day was
> still running. It covers **20:25:00Z – 24:00:00Z only**. Nothing in the interim
> archive is amended, withdrawn or false; per the never-edit rule this is a new
> dated file, not a revision. Written at cut **2026-08-24T00:21:19Z** (`date -u`).
> Full-day figures appear here only where the window changed them.
>
> **One placement rule, stated once.** The premia re-run went terminal at
> 23:58:21Z — inside this window. Its verdict was READ, propagated and
> dispositioned after midnight (`run-cto-entry20-premia-resolve`, resolved
> 2026-08-24T00:08:32Z; commit `7c83c79`). **This record reports the run
> finishing; the pass, its five caveats and the CEO's item belong to
> 2026-08-24's archive.** The row is stated below as the database holds it.

## I. NAV, the book and the tape — nothing moved, and that is a fact, not a gap

| | |
|---|---|
| NAV strikes in window | **0** — the fund was not marked. Last strike $1,885.74 (seq 844, 2026-08-21T20:39:12Z), now 51.7h stale |
| Fills | **0** (0 on the full UTC day) |
| Orders, alarms, halts, reconciliation mismatches | **0** in window (query over `fund_events`, 20:25–24:00Z) |
| Capital deployed under mandate (leg 3) | **unchanged and UNMEASURED at the venue in this window** — no event moved it |

The window contains six events in total, `seq 1255–1260`: two `DeskRequested`,
four `DeskRequestResolved`. **Not one recommendation was decided in the last
3h35m of the day** — full-day `DeskRecommendationDecided` stands at 163, exactly
the interim figure. The floor was building and measuring, not deciding.

## III. Research & verdicts — six runs closed, five belt rows went terminal

| run | seat | tokens | resolved | what it delivered |
|---|---|---|---|---|
| `run-secretary-0823` | secretary | 200,746 | 20:38:01Z | the interim archive; both chair-claim corrections accepted (`231f415`, `d181400`) |
| `run-analyst-ethdossier1` | analyst | 245,588 | 22:11:49Z | ETH Dossier v1, 734 lines — "true and not tradeable at our size"; two live feed defects; collector fabrication measured (`b52e9b4`) |
| `run-builder-d35` | builder | 592,322 | 22:21:29Z | the execution-quality instrument, MERGED `54edb78` — 10 files, 5,998 insertions, 206 tests |
| `run-quant-metacontrols` | quant | 344,964 | 23:02:00Z | four known-good positive controls run down the belt; PSR exposed as mislabeled; cash-carry bias measured |
| `run-cfo-8` | cfo | 201,330 | 23:25:55Z | Grace's growth-mandate audition (`7896d4d`); verdict field EMPTY on the run record |
| `run-adversary-batch4` | adversary | 197,917 | 23:51:51Z | four blind verdicts: KILL / KILL(remedy) / KILL(as filed) / SURVIVES (`485e063`) |

**Tokens 1,782,867 over 6 of 6 runs. Tool uses 581 over 4 of 6 — `run-cfo-8` and
`run-adversary-batch4` carry no tool count and contribute nothing rather than
zero.** Neither carries a `verdict` string either; both verdicts live in their
filed documents, not on the run record.

**The belt (leg 2).** Five candidate rows went terminal in the window, seven on
the full UTC day. Four of the five were **deliberate positive controls**, not
candidates seeking deployment — instrument calibration, and they are counted here
as such:

| candidate | algorithm | claim | terminal | passed |
|---|---|---|---|---|
| `0427da00eb66` | meta_ctrl_buyhold | alpha | 22:29:59Z | False — 1 fill against a 20 minimum |
| `331b61ee31b1` | meta_ctrl_volscale | premia | 22:37:21Z | False — PSR 1.398%, out-of-sample retention −104% |
| `ca0fba4598e7` | meta_ctrl_earnwindow | alpha | 22:41:07Z | False — PSR 0.051%, −17.501% return |
| `c1bf12c33306` | meta_ctrl_pead | alpha | 22:44:37Z | False — PSR 0.315%, 27.266% vs 71.97% benchmark |
| `a9db39fdfab5` | announcement_premium | **premia** | **23:58:21Z** | see below |

`a9db39fdfab5` started 19:26:12Z and ran **4h32m**. It is the fund's first
`premia`-claim resubmission of Entry 20, following `9b767717ff08` (alpha, passed
17:21:48Z). At terminal the row reads `state=done`, `gate_version=v5r3-premia`,
`failures=[]`, `passed=true`, winner `slip 0.0003`, 7,001 priced orders, PSR
77.753, capacity $20,501,957.78, walkforward 8 of 9 folds retained. **All-time
passed rows moved 5 → 6.** What that pass means, what it does not mean, and the
five caveats filed beside it are 2026-08-24's record and are not restated here.

**One thing the row says that the window's reader should not skip**:
`benchmark_population` reads `survivor_only`, `point_in_time: false`,
`survivorship_corrected: false`. The measured survivorship bias was never applied
to this re-run. See §V.

## IV. Decisions & governance — two mandates seated, and a class of decisions handed back

| decision | decided by | recorded | written reason as filed |
|---|---|---|---|
| **Donna gains THE DESK HYGIENE MANDATE** | CEO, verbatim | `e48035e` 23:39:16Z | "clean my desk. unhobble neelesh. decision paralysis is not going to help her boss." She finds with citations; the chair validates and sweeps. Falsifier at birth: one genuinely CEO-awaiting item wrongly swept suspends the mandate |
| **Vishesh gains THE FLOW MANDATE** | CEO, verbatim | `423f861` 00:00:18Z *(00:00:18Z — 18 seconds past the boundary; recorded here because it belongs to the same sitting, and dated to 08-24 by the clock)* | JOINS + NEXT FIVE + BATCH PLAN, advisory, on his existing cadence. Falsifier: two decorative triages remove the sections |
| **V2 CLARIFIED: machinery-calibration decisions are the CHAIR'S** | CEO, verbatim: *"not my decision per v2; its something you need to good at deciding"* | `8e6dfd8` 23:06:03Z; `cto.md` §"V2 CLARIFIED BY THE CEO" | Gate criteria design and levels, and instrument thresholds, are decided by the chair, not escalated. Still his: money thresholds, the envelope, risk limits, authority |
| **THE PSR RULING** (the chair's first gate-calibration ruling) | CTO chair, under the clarification above | `8e6dfd8` 23:06:03Z | Sentence fix unconditional; PSR reverts to its documented target-0 job with the level set by measurement under a hard constraint (full-gauntlet zero-skill FP may not rise); premia claims get the luck filter on the excess-Sharpe advantage. Falsifier written at decision time: if no level holds FP constant, the ~1.34 hurdle stays with its sentence corrected |
| **THE SWITCH-ON CHECK adopted** (Grace C1, a tightening) | chair at resolve of `run-cfo-8` | `9477555` 23:26:56Z | An instrument-delivering dispatch records served? / filled? / read? before closing. Measured cause: D35 at 592k tokens read 0-of-3 |
| **THE COURSEWORK RULE**; **the library ritual**; **the lock escape hatch**; **verification tiers v1**; **the growth mandate to Grace** | chair / CEO | `89cc051` 22:45:32Z · `053376f` 22:22:00Z · `611cb79` 22:31:22Z · `bc1e73a` 21:50:07Z · `bd0552c` 22:53:56Z | five process decisions in one hour; each carries its own written reason at its commit |

**Adversary batch 4, resolved 23:51:51Z** (`ec57f7c`, events `seq 1256–1259`, all
actor `neelesh-via-cto`). Four blind verdicts on four approved-undispatched
requests drained in one batch:

| request | verdict as recorded |
|---|---|
| `a26debb9` | **KILL** as filed — the AST call-graph evaluator passes on code that never runs (4 of 7 planted shapes) while `judgement._wired()` already answers the question at runtime |
| `1c53589f` | **KILL of the remedy**, re-confirmed on a fresh sample: 2 of 7 open requests = 29% would be false-approved. The underlying counter finding SURVIVES and remains open |
| `9fb82050` | **KILL as filed; diagnosis SURVIVES.** Repair-only shipping would flip zero-skill cash mixes to 6-of-6 passing at 700d (+14pp Dirichlet false-pass). Clearance conditions folded into D36 **in flight** |
| `b6f4a407` | **SURVIVES.** All four regulatory dates verified; two supporting claims STRUCK from the record. Retirement is a loosening — the CEO clicks |

**D36 was chartered inside this window** (`6aa9362` 23:02:01Z, on the PSR ruling
and the measured cash-carry bias) and then **amended mid-flight** at 23:54:07Z
(`ec57f7c`) to carry the adversary's own clearance conditions: credit-series pin
to realised BIL, a paired margin table, and a proposed `premia_min_sharpe_advantage`,
shipped as one bundle. Pack v2 was re-specced and filed straight back into the
blind queue at 23:51:51Z (`seq 1260`, actor `cto`, note: "Batch with the next
adversary dispatch"). **No D36 run record exists at this cut** — the dispatch is
in flight and unrecorded, which is the working state, not a gap.

## V. Instruments & infrastructure

- **D35 MERGED — `54edb78`, 22:19:28Z.** The execution-quality instrument:
  `app/fund/executionquality.py` (1,129 lines), the NBBO capture service, the
  retro spread reader, a `/fund/tca` default-limit fix, and 206 tests across five
  files. 10 files, **5,998 insertions, 1 deletion**. Nine commits `01a7c3d` →
  `2bd9b68` landed inside the window; mutation ran 64 killed / 1 retired with
  proof / 0 survived (`dbec638`).
- **The full suite is the reason this is a merge and not an incident.** `2bd9b68`
  records the merge gate at **60 failed, 28 errors** on the merged tree against
  **3,905 passed / 1 skipped** on live head with no diff — so the failures were
  the diff's, established by running the base arm rather than arguing about it.
- **Three more instruments landed after the merge**: a single home for the PSR
  formula and its two inverses (`a21b220` 23:34:10Z), the belt's uncredited
  capture surviving a credit outage (`29a734c` 23:46:34Z), and the luck filter
  wired to our own module "with the sentence that says what it tested"
  (`725fd09` 23:57:26Z).
- **PLATFORM_FACTS seeded** (`7fad220` 22:45:30Z): 20+ commodity platform facts
  the firm paid discovery price for, each with source and verification.
- **Five documents filed in the window**: `docs/archives/2026-08-23.md` + `.pdf`,
  `docs/research/ETH_DOSSIER_V1_2026-08-23.md`, `docs/cfo/GRACE8_2026-08-24.md`,
  `docs/reviews/ADVERSARY_BATCH4_2026-08-24.md`.

## VI. The defects ledger (leg 1) — nine confirmed in three and a half hours

| # | defect | found by | what it could have cost |
|---|---|---|---|
| 1 | **The passing premia row's benchmark is survivor-only.** `a9db39fdfab5` reads `survivorship_corrected: false`, `point_in_time: false`, 170 names as-of 2024-02-26. The firm has MEASURED this bias at −6.90pp ± 2.40 over 20mo, direction KILL (request `739b5ac9`, still `approved`, never dispatched) | the record, at this cut | the fund's first premia pass, judged against a benchmark it already knows is wrong in a known direction |
| 2 | **Repair-only cash-carry crediting flips zero-skill cash mixes to 6-of-6 passing** at 700d, +14pp Dirichlet false-pass | adversary, blind (`9fb82050`) | the premia gate certifying T-bill carry as edge — the exact failure the 2026-08-21 excess-returns amendment exists to prevent |
| 3 | **PSR is a Sharpe~1.34 skill hurdle wearing a luck filter's sentence** — it killed all four known-good positive controls | quant (`run-quant-metacontrols`) | every genuine modest edge, refused with a false reason |
| 4 | **The precondition pack's AST evaluator passes on code that never runs** — 4 of 7 planted shapes, including the shipped `main.py:209-213` swallow | adversary, blind (`a26debb9`) | a production-gate precondition reporting green on a control that does not tick |
| 5 | **The COO filing remedy false-approves 29%** of open requests on a quote of a wish or a complaint (2 of 7, fresh sample; reproduces 27%) | adversary, blind (`1c53589f`) | approvals manufactured from prose |
| 6 | **`macro_fred` hardcodes three wrong macro numbers with zero network calls; `news_rss` invents Reuters-attributed bullish headlines on empty results; health reports healthy throughout — the pattern appears in 5 of 8 collectors** | analyst (`b52e9b4`) | fabricated evidence entering a thesis. A standing embargo was adopted the same hour |
| 7 | **An in-process `from app.main import app` in five new tests stomped the shared store** — 59 failures / 28 errors across a dozen unrelated modules, every one green when run alone; the first test in the repo ever to do it | builder, on the full suite (`2bd9b68`) | a green targeted run certifying a red tree |
| 8 | **Seven defects in code written the same day** — five from the late read-through (`268e9ac`), two only the live-spine acceptance run could find (`5e8469d`); plus three zero-consumer fields deleted (`6c1eed2`) | builder, on itself | seven defects shipped into the instrument Monday's fills depend on |

*Eight rows shown per the chair's cap; the ninth (the Gauntlet's first outing and
what it caught) is cited at commit `1808ac7`.*

Honest reading: **six of the nine were found by a seat auditing its own or
another's fresh work, not by an instrument.** That is the constitution's "the
seats are its test suite" clause behaving exactly as written.

## VII. The floor

| | window (20:25–24:00Z) | full UTC day | prior cut (interim) |
|---|---|---|---|
| Runs resolved | 6 | 42 | 36 |
| Tokens | 1,782,867 (6 of 6 carry the field) | 10,954,250 (40 of 42; 2 carry none) | 9,171,383 |
| Tool uses | 581 (4 of 6; 2 carry none) | 3,938 | 3,357 |
| Builder share of tokens | — | **45.8%** (5,021,578) | 48.3% |
| Commits (UTC-normalised `%cI`) | 33 — ClarkHarness 19, firm 14, KryptonPay 0 | 213 — 111 / 87 / 15 | 180 UTC / 206 local |
| Vault pushes | **21** — firm 14, ClarkHarness 7, KryptonPay 0 | — | — |

**On the vault: there is no day-close push in the record.** Every one of the 21
pushes landed **within two to three seconds of its own commit** (`git reflog
refs/remotes/vault/*`) — the ritual as practised is push-per-commit, continuous
through the window, not an end-of-day batch. `vault/kryptonpay` received nothing in the
window; the firm repo pushes to `vault/master`, while a separate `vault/firm`
branch still carries a tip commit dated 2026-08-23T00:16:53Z — two branch names
for one repo, one of them a day behind. Reported, not resolved.

## VIII. Carried forward into 2026-08-24

- **D36 in flight, unrecorded** (chartered `6aa9362`, amended mid-flight
  `ec57f7c`): PSR level + the cash-carry credit + the paired margin table as one
  bundle, adversary-blind before merge.
- **Precondition pack v2 in the blind queue** (`seq 1260`, filed 23:51:51Z),
  to batch with the next adversary dispatch.
- **The chair's queue: 62 approved-and-undispatched requests, oldest 62.97h**
  (`/fund/desk` `chair_backlog`) — an UPPER BOUND: 14 of 24 dispatch events carry
  no `request_id`. Prior cut: 63 rows / 59.0h. **Depth fell by one; the tail
  worsened by four hours — the fourth consecutive worsening reading.**
- **18 seat memos on the shelf, all 18 chair-unverified** (`/fund/desk/ceo`
  `briefings`).
- Monday's desk: the R39 click sheet (~12:30Z), the 13:30Z open with capture
  running, and the two items in §X that are genuinely his.

## IX. The observer's note

**One.** Between 20:25Z and midnight the floor produced 33 commits, one merge,
six closed runs and nine confirmed defects — and **decided nothing**. Not one
`DeskRecommendationDecided` event fired in three and a half hours (`seq 1255–1260`
are all request-lifecycle). Production and disposition ran in opposite directions
in the last stretch of the day, and the desk that greets the CEO in the morning is
the arithmetic result: 42 rows, of which 10 read as on fire.

**Two.** The largest reduction in the CEO's decision load this firm has ever made
happened at 23:06Z and nobody proposed it. He simply refused an item —
*"not my decision per v2; its something you need to good at deciding"* — and the
chair recorded the class (`8e6dfd8`). **Four rows still sitting on his desk are
gate-criteria decisions filed before that sentence existed.** The clarification
has not been applied backwards, which is §X's single biggest finding and cost
nothing to discover except reading the desk after reading `cto.md`.

**Three.** `run-cfo-8` and `run-adversary-batch4` both closed with an **empty
`verdict` field** on the run record, and neither carries a tool count. Their
verdicts are real and filed — `7896d4d` and `485e063` — but the flight recorder,
which is the one place a reader goes to ask "what did that dispatch conclude",
answers NONE for two of the window's six runs. This is the third cut where I have
had to reconstruct a verdict from a commit message.

---

# X. THE DESK, SWEPT — for the CTO, not the CEO

*First run of the mandate (`e48035e`, CEO verbatim: "clean my desk. unhobble
neelesh"). Read at `GET /fund/desk` and `GET /fund/desk/ceo`, snapshot
`at: 2026-08-24T00:24:32Z`. **The desk shows 42 items needing the CEO, 10 of them
on fire. I can cite a disposition for eleven. I hold no opinion on the substance
of any of them — only on whether the record already answers them.** Nothing here
is executed by me; the chair validates each citation before acting.*

## X.1 The clutter list — eleven rows, each with its citation

**A. Already actioned — the record answers the row**

| # | row | disposition | citation |
|---|---|---|---|
| 1 | `rec:run-quant-metacontrols#1` — "THE PSR RULING: decide what `min_psr_pct` IS" · **ON FIRE, due 08-24** | **Close as decided.** The CEO refused it and the chair ruled | CEO verbatim *"not my decision per v2; its something you need to good at deciding"*, recorded `cto.md` §"V2 CLARIFIED BY THE CEO + THE CHAIR'S FIRST GATE-CALIBRATION RULING (PSR)"; commit `8e6dfd8` 23:06:03Z; the ruling's four clauses and its falsifier are in the same section |
| 2 | `rec:run-ed-batch4#2` — the coverage-model routing CHALLENGE | **Close as accepted-and-executed.** The charter amendment is in HEAD | commit `f16d311`, "Charter amendment 2026-08-23: coverage-model routing (CEO acceptance of the mechanism's batch-4 challenge)" — verified ancestor of HEAD |
| 3 | `rec:run-builder-d23#3` — "DECIDE the risk-free stress rate for premia claims. **v5r1 uses 4.0%/yr**" | **Close: the row's stated premise is false on the current tree.** The constant was replaced by the realised series | commit `a25e8c3` "gate v5r2: the premia rf stress becomes the REALISED cash series" (ancestor of HEAD); candidate `a9db39fdfab5` verdict reads `premia.rf.basis = "realised_series", source: yahoo, symbol: BIL, n=611`. The live question survives as row `rec:run-adversary-d23-d24#2`, which stays |

**B. Superseded — cite what replaced it**

| # | row | disposition | citation |
|---|---|---|---|
| 4 | `rec:run-cto-ab-snapshot-off#1` — "SECOND-LOOK: the fund's first full gate pass exists — candidate `9b767717ff08` under v4.3 … the premia judgement (your ruling) follows the D29 merge" · **ON FIRE, due 08-24** | **Close into `rec:run-cto-entry20-premia-resolve#1` (E20-1).** The thing it promised has happened and has its own row | D29 merged (`a25e8c3`…`ebb233a`); the premia re-run `a9db39fdfab5` went terminal 2026-08-23T23:58:21Z at `gate_version v5r3-premia`; E20-1 filed `7c83c79`. Two second-look rows for one candidate is one row too many |
| 5 | `rec:run-triage7-decisions#4` — "BY 08-25: ENTRY 20 — approve dependency `739b5ac9` NOW, then choose re-judge under the repaired gate or VOID" | **Both verbs are already discharged — but DO NOT close it until the successor row below is filed** | `739b5ac9` reads `status: approved` on the live `/fund/desk` payload; the re-judge ran (`a9db39fdfab5`, 19:26:12Z → 23:58:21Z). **The reason to pause: the approved fix was never dispatched, so the re-judge ran on the survivor-only benchmark it was sequenced to avoid** (`benchmark_population.survivorship_corrected: false`). Closing this row without filing that as its own finding buries §VI item 1 |

**C. Duplicates — cite the surviving twin**

| # | row | disposition | citation |
|---|---|---|---|
| 6 | `rec:run-builder-d24#1` — "POST /fund/desk/supersessions and /retract carry no allowlist and no echo" | **Close as duplicate.** Same finding, same sentence, two seats | Survivor: `rec:run-adversary-d22#1`, "GOVERNANCE GAP: POST /fund/desk/supersessions + /retract carry no allowlist/echo — the brake in front of `desk_approve` is writable by any spine-reaching caller." Both `accepted`; keep the adversary's, which is the blind verdict |
| 7 | `rec:run-builder-d32#1` — "THE LEVERAGE RULE'S SHAPE: keep the refusal, or authorise the financed-backtest workstream" | **Merge into one row.** Same decision, two authors, same day | Twin: `rec:run-adversary-d29#3`, "Whether to later REPLACE the refusal with engine-priced financing … is yours: that replacement is a widening and takes your click." **The merged row STAYS on his desk** — a widening is his click under the v2 floor. He should see it once, not twice |
| 8 | `rec:run-triage7-decisions#6`, **clause (c) only** — "retro effective-spread counts for P5 + commission the backfill reader" | **Strike clause (c) from the convenience batch.** Clauses (a) and (b) stay | Duplicate of `rec:run-cfo-7#1` (ON FIRE, due 08-24), which asks the identical question with its risk stated. The second half is already done: the backfill ran — `run-cto-retro-0824`, 34 rows in `fund_execution_quotes`, 31/34 measured (day log 2026-08-24 BUILT) |

**D. Bookkeeping wearing a decision's costume — say whose job it is**

| # | row | disposition | citation |
|---|---|---|---|
| 9 | `rec:run-secretary-0823#1` — "Awaits the CEO, Monday: R39 click sheet + G1 account, the data-buy reminder …" · **ON FIRE, due 08-24** | **Mark `noted`, not accepted.** It is my own index of rows already on his desk — every item it names has its own row above it | `kind: "note"` on the row itself; the seat protocol (secretary memory, 2026-08-21 carried from builder D10): *"`noted` is a real terminal status … a note marked `done` says EXECUTED."* My row is currently occupying one of ten fire slots to tell him about the other nine |
| 10 | `rec:run-cfo-8#1` (O4, `serves_requests` validation) and `rec:run-cfo-8#2` (O5, widen the `app.main` import guard) | **Route to builder as D34 riders; off the CEO's desk entirely** | **Each row's own payload states `'next_actor': 'builder'` and `'detail': '… Queued as D34 rider.'`** The desk resolved them as `next_actor_resolved: "unknown"`, `next_actor_basis: "explicit_unrecognised"` — and an unrecognised actor defaults to the CEO. Two builder tickets on his desk by routing default, not by anyone's judgement |
| 11 | `rec:run-cfo-8#3` (S1, Grace's adoption scorecard) | **Mark `noted`.** It is a falsifier the seat wrote against herself; nothing binds on his click | The row's own title: *"the audition's own falsifier"*; day log 2026-08-24 OPEN lists it as "Grace's adoption scorecard (S1) **for his read**" |

## X.2 The routing class — eight rows on his desk by default, not by judgement

Eight of the 42 carry `next_actor_basis: "request_lifecycle"` — six builder
tickets (`62fe366f` D30, `19ed403a` factory orphan reconciler, `14a796d8`
NameError in the snapshot-skip path, `5429fcf3` price-feed identity defect,
`cf4f7de8` D33, `4a4f6b0d` D34 addendum), one validator register (`d7599daf`),
one adversary blind review (`3eeb42d4`). **None of them names the CEO; they reach
him because an open request's default next actor is him.** The desk's own
`execution_note` says the opposite: *"Requests are picked up by the CTO session
and dispatched to the bench."*

One of the eight I can dispose of on its own text: **`3eeb42d4` (pack v2 blind
review) was filed BY the chair, FOR the adversary, at 23:51:51Z in this window**
— `seq 1260`, actor `cto`, note verbatim: *"Batch with the next adversary
dispatch."* An item the chair wrote to itself should not be on the CEO's desk.
The other seven stay pending the chair's call on the default.

## X.3 Cannot tell — these stay on his desk, flagged

| row | why I cannot classify it |
|---|---|
| `rec:run-pm-0908#1` — THE 2026-09-08 PACKAGE, $1,847.36 | R37, R39 and Entry 20 have their own dated rows (`run-triage7-decisions#1/#2/#4`); **R38, R40, R43, R44 and R48 do not.** Partially duplicated is not duplicated. It stays whole |
| `rec:run-ed-batch4#1` — acquire a delisting-inclusive price history | Its stated evidence — *"0 of 545 names in the current feed ever stopped trading"* — was partly overtaken inside the day by commit `0eb4d5a`: 124 of 125 S&P leavers, 564,609 bars, 1990–2026, on Tiingo's FREE tier. Point-in-time membership is still unmet. **A spend decision whose premise moved should be re-stated by Ed before it costs the CEO a reading**, but I will not judge how much of it survives |
| `rec:run-cfo-7#2` — the PRE-COMMITMENT SHAPE for kill-repair rounds | Reads as a process/routing call, which Delegation v2 puts in the chair's lane — but it asks the CEO to change *when he rules*, which touches his own working pattern. His call whether it is his call |
| `rec:run-builder-d24#4` — hold the builder cap at two | A cap the CEO set on 2026-08-22 with a falsifier written at decision time. The measured RAM (0.49/0.72 GB, chair re-measure 1.09 GB) is the evidence that falsifier asked for. **It is a threshold and it is his** — listed here only so nobody sweeps it as a builder note |
| `rec:run-triage7-decisions#4` (repeated) | Both verbs discharged; see X.1 row 5. Do not close until the survivor-benchmark finding is filed as its own row |

## X.4 The UI read

He opens the page and the first sentence tells him nothing is new — *"No previous
visit was supplied, so nothing is marked new — this is everything currently open,
not a diff"* — so every visit is a cold start over 42 rows, with 376 items
classified behind them (`matrix.totals`: open 90, ticking 187, blocking 64,
closed 35). Above the fold sit ten rows marked on fire; **three of those ten are
in my clutter list** (the PSR ruling he already refused, the second-look on a
superseded gate pass, and my own index-of-the-other-nine), so nearly a third of
the burning list is not burning. Ranking helps for the first four rows and then
stops: the desk states its own limit — *"18 of them state neither a date nor a
dollar figure, so their order is arrival order and not a ranking"* — and because
the key is date-then-money, **the largest dollar figure on the whole desk,
`rec:run-pm-0908#1` at $1,847.36, sits nineteenth** for want of a due date, below
rows worth nothing. Lineage is not followable at all: `supersession` is null on
all 42 rows and `blocked.total` is 0, with the supersession channel reading
`true` and carrying nothing — every one of my superseded and duplicate findings
above required a git log or a Postgres query, which is exactly the work the desk
exists to spare him. And the sharpest thing on the page is the ugliest: **the two
items that are genuinely his — `E20-1`, the first premia pass, and `AB4-2`, the
PDT retirement click — render as raw Python dict reprs**, titles beginning
`{'id': 'E20-1', 'title': ...`, along with all three of Grace's cfo-8 rows. Those
five are the five most recently filed rows on the desk. The newest and most
consequential work is the least readable text on the page, and the two decisions
this whole sweep is meant to surface are buried inside a serialised dictionary.

**Three presentation tickets, routed to the chair as ordinary recommendations —
my pen never touches the UI:**

| ticket | what | measured cause |
|---|---|---|
| P-1 | Render a recommendation's `title` from the payload's `title` key when the payload is a dict, never `str(dict)` | 5 of 42 rows, including `E20-1` and `AB4-2` |
| P-2 | An `explicit_unrecognised` next actor must route to its stated value or to `unknown`-and-held, never default to the CEO | 2 rows (`cfo-8#1/#2`) both state `'next_actor': 'builder'` |
| P-3 | Render the supersession edge the clutter list proves exists — a `superseded_by` on the row, sourced from the resolution text and the run record | 4 of my 11 dispositions are supersessions or duplicates; `supersession` is null on all 42 |

---

**LENGTH, DECLARED not hidden.** This file is ~29,000 characters against the
§2 cap of ~15,000. The split: the record (§I–IX) is ~17,300 and the sweep (§X)
is ~11,700. The record half overflows by ~2,300 and I have compressed it to
citations rather than dropping rows. **The sweep has no budget yet and needs
one from the chair** — eleven dispositions each require a row, a disposition and
a citation, and the mandate's own rule is "no citation, no listing". My proposal:
cap the clutter list at twelve rows with the rest as one cited line, and keep the
UI read to a single paragraph as written here.

*Filed by Donna, 2026-08-24T00:21:19Z host-UTC. Completing section only —
`docs/archives/2026-08-23.md` stands unedited. Eleven dispositions, five
cannot-tells, eight routing-class rows, three presentation tickets; the chair
validates every citation before it sweeps anything.*
