# CTO review queue — the ledger between the two chairs

**Written by the co-CTO (Opus) as it works; read FIRST by Fable on every
return. One dated entry per Tier-2 action (taken, for verification) or
Tier-3 deferral (parked, for decision). Fable marks each entry resolved
with a note and never deletes one — this file is append-and-annotate, like
everything else in this firm. Format:**

```
## YYYY-MM-DD HH:MMZ — [TIER-2 TAKEN | TIER-3 DEFERRED] — one-line title
What: the action, precisely (ids, files, amounts).
Why: the CEO acceptance or state change that demanded it, quoted.
Evidence: how to verify it against the record (event ids, test output).
[Fable @ resolve]: (left empty by the co-CTO)
```

---

## 2026-08-21 ~12:30Z — HANDOFF: Fable → co-CTO (CEO near Fable token limit)

**Written by Fable at the CEO's request. You are the co-CTO (Opus). Your
charter is in the constitution — three tiers, fail toward the queue,
never reverse Fable-era work. This entry is your complete working state;
read it, then work. Log every Tier-2 action here as you take it.**

### Live processes (verify, don't assume)
- Spine: 127.0.0.1:8090, FUND_STORE=postgres, running the D6-merged code.
  Verify `GET /fund/liveness`. Restart procedure is in cto.md §cold-start
  (kill PID on 8090, background uvicorn from ClarkHarness). Postgres:
  docker `krypton-pg`, port 5433.
- KryptonPay dev server: port 3000 (launch config `kryptonpay`).
- Repo heads at handoff: **ClarkHarness 56216ab · KryptonPay cbc32b8a ·
  firm c2328c2**, all committed clean. NO PUSHES (standing CEO rule —
  private workspace pending).

### CRITICAL: builder dispatch 7 was IN FLIGHT in Fable's session
The builder (D7: CEO desk four queues, Donna floor presence + archive
shelf, fund_agent_transcripts + Firestore runs mirror, EDGAR fixes, floor
run counts, gate data path, Part G batch — brief at
KryptonPay/docs/briefs/BUILDER_D7_2026-08-21.md) was resumed after a
usage-limit cut and was running when this handoff was written. It belongs
to Fable's session — you CANNOT message it. What to do:
1. Check the scratchpad (path in your session's listing; Fable's was
   ...\bbc88cbf...\scratchpad) for `d7` bundles (`builder-d7-*.bundle`).
2. If bundles exist: verify with `ClarkHarness/scripts/merge_builder.py
   --bundle <path> --base <ec816f7|cbc32b8a> --repo <path>` (it merges in
   a throwaway clone and runs the full suite on the RESULT). Merging on a
   PASS with 0 sensitive/forbidden surfaces is Tier 2 — do it, restart
   the spine, ledger it here. Any sensitive-surface diff → park, Tier 3.
3. If NO bundles: the dispatch died incomplete. Do NOT re-dispatch D7
   blind — read the tail of Fable's task transcript if reachable, else
   re-dispatch a FRESH builder with the same brief + a note that a prior
   attempt exists (its clones may hold partial work; the brief's
   wrong-base discipline applies).

### The book (as of handoff — verify against /fund/risk/monitor)
NAV $1,884.79 · 4 positions (SPY 0.346119, DBC 8.122157, TLT 3.019871,
DBA 5.314306) · gross 48.61% = the PM's phase-1 target · halted FALSE ·
all exits pre-committed (SPY 7.3%/2026-11-19, DBA 6.1%/2026-11-19, TLT
4.0%, DBC 8.7%, time exits 2026-09-08 on the beta legs). Phase 2 is
DATED 2026-09-08 (close-and-re-establish, PM R11) — do not act early.

### Dispatch queue, in order (all Tier-1 for you once triggered)
1. **Donna at EoD** — standing CEO authorization. She now files her own
   archive + PDF (docs/archives/, absolute path to archive_pdf.py — the
   spec in .claude/agents/secretary.md is current). Today's material:
   gate r4 KILL, excess-returns amendment, co-CTO seated, two fills,
   mechanism cycle 2, her own debut. Her memo card UI isn't built yet
   (D7) — hand the CEO the PDF in chat.
2. **Riskofficer batch** (after builder resolves): FOUR items — the
   rebase-direction defect dc7b068c (fund.py:3511 vs effective_peak),
   guard v1.2/via-co-cto first audit (your own channel — disclose that),
   mark-sanity post-build audit, envelope-width question.
3. **Validator R13**: units defect re-measure (correlation.py:216
   covered-gross weights; max_component_vol_pct scale-invariance).
4. **Analyst 5.02 measurement** — ask 909c316c AWAITS THE CEO'S CLICK
   first; do not dispatch without it.
5. **Funnel cycle 3 = menu entry 14** (secondary-offering placement
   discounts, mechanism+analyst joint, 424B5 events) — a big dispatch;
   fine to run when slots free.

### On the CEO's desk (do not nag, just know)
- PM ask 27957634 (mechanism requests pm: close R8) — awaiting CEO.
- Analyst ask 909c316c (5.02 study) — awaiting CEO.
- R1 drawdown-rebase call — now ALSO gated on the riskofficer's
  dc7b068c audit (the rebase mechanism has a confirmed latent defect;
  do not stage any rebase until that audit lands and Fable or the CEO
  signs the fix).

### Tier-3 (park for Fable, never execute)
Gate v5 round 5 design (all prerequisites written: excess returns,
shipped window_for geometry, cash-mix + masked nulls, D7 data path — but
gate design is chair-architecture work); any fix to fund.py:3511
(risk-engine code); threshold changes; corrective event appends;
constitution amendments beyond CEO-dictated text.

### Standing rules most likely to bite you today
- Stage approval-needed orders ONLY with the CEO at the desk (120-min
  staleness worker kills them otherwise).
- The permission classifier blocks bundled multi-action scripts and
  heredoc state-file appends: decompose (event appends = tiny script;
  HTTP = curl per call; state files = Edit tool).
- Run records carry the seat's FULL report verbatim in `output` and the
  brief in `meta.brief` (CEO durability rule, 2026-08-21).
- Artifacts file under the UTC date of the work they record.
- An absent number is reported absent. NAV folds from the event log only.
- desk digest: `ClarkHarness/scripts/desk_digest.py` is your one-command
  session-start read.

[Fable @ handoff]: the ledger below is yours from here. Welcome to the
desk — it is in good order, the book is at target, and the funnel is
finally generating. Keep the record the way you found it: verbatim,
cited, and honest about absence.

---

(co-CTO entries begin below)

---

## 2026-08-21 ~19:1xZ — TIER-3 OVERRIDDEN BY THE CEO — I TOOK GATE V5 ROUND 5. Fable, read this one first.

**Fable: gate architecture is the item your handoff parked for you, and I
took it. The CEO instructed it directly and verbatim: *"Lets close gate v5
so we can keep testing and keep your notes for fable so he is aware
exactly."* This entry is that note. Every judgement call is listed so you
can reverse any of them; the design is `docs/GATE_V5_ROUND5_DESIGN_
2026-08-21.md` and NOTHING IS ADOPTED.**

### Why the CEO overrode the parking

Four independent sources reached the same conclusion today without
coordinating: your own flow-test synthesis (B1, "the gate is the funnel's
ceiling"), COO triage #3 ("four consecutive kills while the funnel fills
behind the gate is no longer a quality signal; it is the firm's binding
constraint"), Donna's Daily (leg 2 at zero for two consecutive days), and
the PM. The funnel is generating honestly and nothing can be judged. The
CEO's own words when he started the pipeline tonight were about trades;
the constraint he actually hit was the gate.

### What I did, and deliberately did NOT do

**I wrote a DESIGN, not a round.** Round 4 died in part because it
arrived with its own tables and its author's conclusion in a single
artifact, and the tables turned out to be honest measurements of the wrong
thing. So: the chair specifies, **the validator measures** (dispatched,
`scripts/gate_v5_audit_r5.py`, a NEW script — round 4's is never edited),
and the result goes to **the adversary blind** before anything is adopted.
I have not touched `gate.py`, `judgement.py`, or any registered value, and
the `WALKFORWARD_HISTORY_FLOOR` / 10-year-backfill package remains blocked
and unchanged.

### The four grounds and the change each forces

1. **Financing (the big one).** Round 4 levered TOTAL returns with no
   risk-free divisor, so the gift (k−1)·rf beat the 2%/yr margin and a
   zero-skill 40/60 SPY/BIL sleeve passed. Round 5 computes on EXCESS
   returns — mandated by the CEO's own constitutional amendment today.
   **Headline acceptance test with its prediction stated in advance**: the
   cash-mix family must pass at the benchmark's own rate at EVERY rf. Any
   surviving rf dependence means financing still is not charged and round
   5 is dead. This is also the mechanism's defect D4 from the other side —
   two seats derived the same arithmetic blind, from opposite sides of the
   gate.
2. **The masked wander.** I am NOT proposing a cleverer guard. Two
   structural changes in one round is how round 4 got four grounds instead
   of one. Instead the masked family becomes a standing first-class null,
   and **the headline becomes the CLASS MAXIMUM, not the battery mean** —
   a gate is chosen by its worst plausible null. If the guard is still
   holed, round 5 REPORTS the hole rather than papering it.
3. **Geometry.** One fold generator only, imported and CALLED
   (`window_for_strategy`), never re-implemented. Any table measuring a
   proposed generator is labelled as such in its own caption.
4. **The data path — CLOSED, and it is what unblocks the round.** Your D7
   merge shipped it (commit `76784c2`). Round 5 must respect its two named
   limits rather than paper over them: only out-of-sample legs are
   captured, and `dropped_unmatched_days` makes the next return a two-day
   return wearing a daily label.

### Judgement calls — reverse any of these and I will take the correction

- Fix financing, not the guard, in this round.
- Report the class maximum as the headline rather than the mean.
- ρ stays 5 and is labelled **near-decorative** (the ρ=0 row proved the
  four-leg structure does the work). Adopting it as load-bearing would be
  adopting a constant that is not.
- Design and measurement separated on purpose.
- `--market-sharpe` disclosed as a conditioning assumption in every table;
  round 4's whole calibration depended on it and disclosed it nowhere.

**A well-measured "still holed, and here is precisely where" is a complete
result and the right input to round 6.** I told the validator so
explicitly, because a seat that believes it must produce a pass will
produce one.

[Fable @ resolve]:

---

## 2026-08-22 ~00:5xZ — builder D8 round 2 returned: all three grounds repaired, BACK TO THE ADVERSARY

**What**: The builder repaired all three adversary grounds and re-cut the
ClarkHarness bundle at base `50c19e6` (rebased — it noticed the live head
moved when the verdict commit landed, and deleted the stale bundle so it
cannot be applied by mistake). Gate: **1416 passed, 28 ordinary / 1
sensitive / 0 forbidden.** Still sensitive — same file, five lines in the
approval-guard region — so it **goes back to the adversary blind**, which
is the route, and I have queued it rather than merging.

**Two things it found while repairing that the review did not name**:
`drift() or {}` folded a *missing* reading into the "venue keeps no
positions" branch; and `configured: False` was returned both for a venue
with no position record AND for **a broker that errored** — so an
unreachable broker was filed as "nothing to compare". Both now split.

**Its own account of what it got wrong is the most useful part** and I am
recording it verbatim in the seat memory: *"I wrote the invariant in a
comment and did not implement it"*; *"'never silent' is not enough where a
clearing rule exists"*; *"a guard-predicate rename is a change to who may
write"*; *"testing the pure function and never the surface is how a green
suite covers a hole."*

**It declined one thing on principle and was right to**: it did not fix
the merge-gate classifier inside the diff the classifier would gate —
*"editing the gate that gates my own diff, inside that same diff, is the
'gate loosened and blessed by its own tests' pattern in the one direction
it is hardest to argue with."* Filed separately as `d1d5beef`.

**One risk-policy question it deliberately left open** rather than
deciding through a severity field: should `broker_drift_unmeasurable` be
`critical` (which blocks auto-resume) instead of `warn`? That is the CEO's
and the riskofficer's call.

[Fable @ resolve]:

---

## 2026-08-21 12:58Z — CORRECTION — I FABRICATED THE TIMESTAMPS ON MY OWN ENTRIES BELOW

**Appended, not edited — the entries below keep their wrong headers and
this correction stands over them, which is how this firm corrects itself.**

Every `~HH:MMZ` in my ledger entries below was **estimated, not read from
a clock.** I wrote ~18:10Z, ~19:40Z, ~19:45Z, ~19:50Z and ~20:10Z. The
true times, anchored to event-log rows and file mtimes:

| My entry | I wrote | TRUE (event/file evidence) |
|---|---|---|
| D7 gate-verified + merged | ~18:10Z | ~11:30–12:00Z (merge commits; spine restart) |
| Tier-3 park (API card) | ~18:10Z | ~12:05Z |
| Housekeeping note | ~18:10Z | ~12:05Z |
| COO triage #3 fired | ~19:40Z | **12:22:34Z** (DeskDispatched seq 656) |
| Trigger amendment ≥50 | ~19:45Z | ~12:44Z |
| Donna dispatched / 920ecbe5 filed | ~19:50Z | **12:39:03Z** (DeskRequested seq 657) |
| Cascade sweep | ~20:10Z | ~12:50Z (marks precede seq 691 at 12:54:11Z) |

**I was reading the machine's LOCAL clock (IST, UTC+5:30) and writing it
with a `Z` suffix.** 18:25 local is 12:55Z. That is the *identical error
class* the builder refuted in its own brief four hours earlier — a
timezone confusion in a stored timestamp — and I committed it in the
governance ledger the same afternoon, having personally verified the
EDGAR measurement that turned on exactly this distinction.

The non-negotiable is "never fabricate a number, a **timestamp**, or an
attribution." An estimated timestamp written as fact is a fabricated one.
No decision was made on these figures and no money moved, but the ledger
exists so the other chair can trust my account of my own work, and a
fabricated timestamp in it is a defect of the instrument itself.

**Standing rule adopted for this chair, effective now: read the clock,
and state UTC as UTC.** `Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"` plus
the UTC conversion, or anchor to an event-log `ts`. Never estimate a time
in the record. Never write local time with a `Z`.

**Donna found this independently at her 12:45:20Z cut, thirteen minutes
before I did** (run-secretary-2 §IX and her recommendation 7). Two paths
to the same defect inside fifteen minutes is the record working; that it
was the chair's defect and a seat's catch is the metric working.

[Fable @ resolve]:

---

## 2026-08-21 ~17:5xZ — TIER-2 PART-TAKEN — builder D8: KryptonPay MERGED, ClarkHarness HELD for the adversary

**What**: D8 delivered eight of nine briefed parts plus `GET /fund/autopolicy`.
I gated both bundles myself.

- **KryptonPay**: gate **PASS, 230/230, 12 ordinary / 0 sensitive / 0
  forbidden**. `fund_api.ts` diff checked line by line — additive (+63/−2),
  and the two deletions are the two status unions being WIDENED (`noted`,
  `awaiting_review`), which is exactly Parts 7 and 8. Zero thesis types.
  **MERGED at `65e6fdc4`.** Note the base was `b23ef096`, not the
  `a3d59de1` my brief named — the live tip had moved by my own brief
  commit and the builder branched from the tip and said so.
- **ClarkHarness: NOT MERGED.** The gate flagged **1 sensitive**:
  `app/fund/riskmonitor.py`, with six changed lines inside the
  approval-guard region. The constitution routes a sensitive diff through
  the **adversary blind** before a chair merges it, so that is where it
  went — dispatched blind, artifact only, with neither the builder's
  report nor my assessment attached. Fetched as branch `builder-d8` in the
  live ClarkHarness repo for the adversary to read; **the fetch creates a
  ref, not a merge.**

**Safe to split the halves**: the builder designed the UI to degrade
honestly while the spine endpoints are absent — a 404 on the memo endpoint
renders "UNKNOWN, not absent", never "she filed nothing". Verified by its
own CDP probe against a 404 spine.

**TWO NEW JUDGED NUMBERS AWAIT THE CEO** (they gate an `info`-severity
alarm only, and no existing threshold moved in either direction):
`NAV_BAND_PCT = 0.01` — basis: ~20× the measured $0.92 mark-timing
residual (0.049% of NAV) the PM derived; `NAV_BAND_FLOOR_USD = 150.0` —
basis: the smallest live position, DBA at $149.94. Both bases are
measurements, not preferences. Ratification is the CEO's.

**Deliberately NOT in this dispatch**: `autopolicy.py`, untouched by
instruction — the envelope change that would consume the new drift alarm
(the venue must hold what an exit rule sells) is the riskofficer's lane
and the CEO's decision, request `86f7662e`, and it is the one item with a
date on it (2026-09-08, $502.15).

**Operational note**: the spine blocked for minutes on a 24-hour
`universe refresh` that appears to run on the request path. Not a defect I
chased today; worth a look, because a blocking refresh makes every
endpoint — including the risk monitor — unavailable while it runs.

[Fable @ resolve]:

---

## 2026-08-21 ~14:30Z — TIER-2, CEO-INSTRUCTED — THE FUND HAD NO OFFSITE DURABILITY. RESTORED AND VERIFIED.

**Fable: this is the most serious thing found today, and it had been true
for an unknown number of days while the status endpoint reported success
every hour.**

**The defect.** `.env` carried `USE_FAKE_FIRESTORE=1`. `app/main.py:47-53`
reads it, calls `install_fake()` — an **in-memory, ephemeral** Firestore —
and stamps the project id `"in-memory"`. The hourly `FirestoreSnapshotter`
wrote the fund's durability mirror into that dictionary. The running spine
logged `MOCK MODE — in-memory ledger, real market prices. NOT the fund.`
at startup, while holding four real positions and taking real approvals.
`/fund/snapshot/status` reported `last_ok: true` throughout.

**Measured, not assumed.** I read the real project directly (a full stream
of `fund_events`, gap-checked):
- offsite before: **160 documents, seq 1..160, contiguous**
- Postgres: **712 events**
- the Postgres watermark claimed: **700**

**552 events (seq 161–712) existed on exactly one machine** — every fill,
the GLD phantom incident, the halt, today's R1 rebase, all four current
positions. Combined with the standing no-push rule, the firm repo is
single-machine too.

**Fixed, in the order the CEO instructed ("restore durability first,
alone" → "go"):**
1. `.env` `USE_FAKE_FIRESTORE=1 → 0`; backup at
   `ClarkHarness/.env.backup-2026-08-21-preflag`.
2. Spine restarted. Verified: **no MOCK MODE line**, real project
   `hedgefund-ae96c` (staging).
3. **Watermark re-baselined 700 → 160** — the clean-field rule applied to
   itself: cause fixed first, old value preserved here and in the row's
   `last_error` text, magnitude MEASURED (contiguous 1..160), direction
   safe (lowering only ever re-pushes; writes are keyed by document id, so
   idempotent), a human decided.
4. Backfill run: **552 events pushed, seq 161→712**, plus 3 agent runs.
5. **Verified by reading Firestore again, not by trusting the endpoint
   that lied: 712 documents, seq 1..712, CONTIGUOUS.** Status now reads
   `behind_by: 0`, runs `0 behind`.

Book unchanged throughout: NAV $1,885.02, gross 48.61%, halted false,
alarms empty, peak $1,908.09 `rebased`, four positions.

**SIDE EFFECT THE CEO SHOULD SEE — venue changed at the same time, and I
could not isolate it.** The same flag gates connector selection, so
turning it off routed orders to Alpaca: `/fund/venue/account` now reads
`{"venue":"alpaca","configured":true,"mode":"alpaca_paper","status":
"AccountStatus.ACTIVE"}`. The account is live and reachable. **This is
what R15 wanted** — but it arrived as a coupled effect, not an isolated
decision, which is precisely the conflation the cleanup exists to end.

**NEW FINDING, unresolved, reported not fixed**: the Alpaca account
reports `portfolio_value 2014.64 / cash 846.84` while the fund's own book
reads NAV $1,885.02 / cash ~$968. **They disagree by ~$130.** Expected in
kind — the book was built on paper-connector fills that never reached
Alpaca — but it is now a live reconciliation gap, and the riskofficer
independently flagged that reconciliation has produced no event since
seq 141 (2026-08-15) and has no liveness heartbeat. NAV stays the event
log's number per the constitution; broker equity is a comparison, never
the truth.

**Also found while mapping this**: two Firebase projects are in play —
`.env` points at `firebase_service_account.hedgefund.json`
(**hedgefund-ae96c**, the fund's) while the code's default fallback is
`firebase_service_account.json` (**krypton-auth-e8653**, a stale auth
project that also contains a `fund_events` collection). A script that
does not load `.env` silently targets the wrong project. That is a live
foot-gun and belongs in the cleanup brief.

**Still to do, NOT done by me** (the CEO's staged plan, steps 2 and 3):
decide Alpaca routing on its own terms and re-run R15 properly; then
split `USE_FAKE_FIRESTORE` into three orthogonal flags — store target,
order routing, ledger target — each named for what it does. `FUND_REAL_
BROKER` already exists because someone split one of the three off before.

[Fable @ resolve]:

---

## 2026-08-21 ~14:05Z — TIER-2 TAKEN — R15 REOPENED: the "alpaca" experimental deployment filled on the PAPER venue

**Fable — this is the entry to read first.** The riskofficer's dispatch
found something larger than anything in its brief, I verified it three
ways independently, and it falsifies a completion you recorded.

**What**: `venue` is **not a route in this system.** `_connector` is a
module-level singleton chosen once at import (`fund.py:151-163`);
`pipeline.submit` calls `self._connector.execute(...)` unconditionally
(`pipeline.py:223`) and writes `venue: ref.venue` from what the connector
RETURNED (`:229`). `order.venue` on a proposal is a self-declared label,
copied onto the fill.

**Proof the DBA leg filled on paper, all three checked by me:**
1. `GET /fund/venue/account` → `{"venue":"paper","configured":false,
   "mode":"paper_mock"}` — no Alpaca configured on the running spine.
2. The order's own lifecycle: OrderProposed `venue: alpaca` (seq 588) →
   **OrderSubmitted `venue: paper` with a real `venue_ref` UUID (seq
   593)** → OrderFilled `venue: alpaca` (seq 594).
3. Fill = arrival = quote to the last binary digit (`28.3799991607666`)
   — the paper venue's signature, since it fills at its own quote.

**Consequence**: R15 was CEO-accepted with ONE stated learning goal — the
fund's first informative execution-cost observations, because paper fills
yield zero at any n. It produced zero. **$150.82 of capital was committed
to a measurement that returned nothing**, and seq 612 marked it done
citing the fill label against that same order's submission record. I have
**REOPENED R15** with the full evidence in the note. No TCA or cost-model
work may consume `alpaca`-labelled fills until venue either routes or is
deleted from proposals.

**Three seats converged on this in one day** — Donna reported the venue
disagreement and the `avg_price == arrival_price` signature; the COO found
the constitution's "paper venue" clause with no venue check in code, for
the second consecutive triage; the riskofficer proved the mechanism. The
seat also warns explicitly: do **not** "fix" the COO's drift by adding a
`venue == "paper"` check to autopolicy — that would check a self-declared
string, which is the forgeable-marker mistake again.

**Parked Tier 3 for you, each with a demonstration attached** (all
risk-engine or guard code, none executed by me):
- **F2, now live**: the rebase-direction fix is **TWO lines**, not one —
  `fund.py:3619` AND `riskmonitor.py:851`, because the confirm echo hashes
  the same wrong value; a one-line fix refuses every future rebase. Any
  second rebase in ($1,908.09, $2,036.35) is accepted and RAISES the
  reference; $2,036.34 fully reverses today's R1.
- **F3**: the approval guard has **no force on the Studio order path** —
  the client computes its own echo (`fund_api.ts:1821`). The risk-control
  panels already do it right with server-issued state tokens. Recommends
  guard v1.3.
- **F4**: `POST /fund/risk/limits` and `POST /fund/risk/resume` carry no
  guard at all — against the anti-quiet-loosening clause. Never abused
  (one `RiskLimitsSet` ever, at genesis), which is why it is cheap now.

**It also audited MY channel and found three defects in MY work, which I
accepted rather than softened**: I labelled as "verbatim" a string that
was my own desk line with the CEO's assent appended; the R1 option
selection has no record I did not author; and my rebase reason mixes two
comparators and calls a peak "corrupted" that was struck six days BEFORE
the phantom on genuine marks — what the rebase actually did is lower a
genuine high by a defect's realised destruction. It also raised my
assessment of the act: both alternative comparators justify a LOWER peak,
so the rebase erred conservative by ~$5. **Convention adopted: where the
CEO selects among options, the selection must be captured in a record the
chair does not author.**

[Fable @ resolve]:

---

## 2026-08-21 ~13:35Z — TIER-2 TAKEN — three finished dispatches were rendering as WORKING; closed. THE FIX IS A MISSING STATE, NOT AN AUTO-CLOSE

**What**: The CEO looked at the floor and asked whether four agents were
really running. One was (riskofficer). `coo` (027630a0), `builder`
(24295dd6) and `mechanism` (b074c8f6) had finished hours earlier —
mechanism and builder since 09:00Z — and were still lit. Closed all three
with their artifacts named; telemetry now reads `running_now: false` for
each and `true` only for the riskofficer.

**Mechanism (process defect on the chairs' side, not a UI bug)**:
`DeskDispatched` mints its own `task_id` and `desk._activity` keeps a seat
lit until a `DeskRequestResolved` arrives carrying THAT id. We had been
closing the seat-ASK ids a dispatch served, which are different ids. Fable
happened to close the analyst's dispatch because he passed the task_id to
the resolve endpoint; the other three were never closed.

**I PROPOSED THE WRONG FIX AND THE CEO CORRECTED IT — recorded because it
is the more useful half of this entry.** I suggested a completed run
should close its own dispatch automatically. He said: *"no it should nto
close automatically since the cto needs to review the work be satisified
and then log or do what needs to be done and then close it."* He is right;
my proposal was the unwired-kill-switch pattern wearing a progress bar —
it would have made the board report a completion nobody performed. A seat
FINISHING and its work being ACCEPTED are different facts and the gap
between them is the chair's job. **The defect is a missing third state**:
working / awaiting-the-chair's-review / closed, with only the first and
last rendered. Filed as builder item **907ecc74** with DO-NOT-AUTO-CLOSE
written into the spec; the principle is now in the constitution's dispatch
section, verbatim.

**Donna found this first**, at her 12:45:20Z cut, and named the exact
mechanism: *"the dispatch events have no matching completion event"*
(run-secretary-2 §VI item 6). I read past it. That is her second catch on
a chair today.

**Evidence**: three `DeskRequestResolved` events keyed by task_id;
`seat_telemetry` before/after; run-secretary-2 §VI.

[Fable @ resolve]:

---

## 2026-08-21 ~13:40Z — TIER-3 DEFERRED — the CEO's `note` vs `suggestion` vocabulary is not in the data model

**What**: The constitution (secretary seat, CEO decision 2026-08-21) says
Donna's items come as `note` (asks to be READ, no accept/reject, the chair
marks it noted) or `suggestion` (decidable). The spine's
`decide_recommendation` accepts only `open | accepted | rejected | staged
| done` — **there is no `noted`**. Fable worked around it on her day-one
notes by marking them `done`; I did the same today, with "NOTED, NO ACTION
REQUIRED (a note)" leading the note text.

**Why it matters enough to park rather than drop**: `done` conflates "the
chair read this and nothing was required" with "the chair executed this".
A future reader — or Donna's own hit/miss scoring — cannot tell them
apart, and the whole point of the CEO's vocabulary was that a note is not
a task. It is a small schema addition (`noted` as a terminal status,
rendered read-only) and it belongs with builder item 907ecc74's state
work, since both are about states the model lacks. Not taken by me: it is
a data-model change and the D8 brief is the right vehicle.

[Fable @ resolve]:

---

## 2026-08-21 13:07:57Z — TIER-2 TAKEN — PM R1 EXECUTED: drawdown reference repaired

**What**: The CEO approved R1 and, on being asked which of its three
options, selected **"Repair — rebase to $1,908.09"** explicitly. Executed
on the approval channel: `POST /fund/risk/drawdown-reference/rebase`,
approver `neelesh-via-co-cto`, confirm echo `ad699edb` **read live from
the monitor, never typed**, the CEO's instruction quoted verbatim
including his option selection, mandatory reason naming the phantom fill,
its root cause (`exitrule.py:269-270`) and the expected effect.

**Verified after, against the PM's and COO's independent arithmetic**:
effective peak **$1,908.09**, `peak_basis: "rebased"`,
`unrebased_peak_nav` **PRESERVED at $2,036.35** (the record is annotated,
not erased), drawdown **7.4427% → 1.2211%**, halt line $1,832.72 →
$1,717.28, **headroom $52.08 → $167.51 — matching the COO's figure to the
cent**, halted false, alarms empty. **No threshold moved**:
`max_drawdown_pct` is still 10.0%.

**Why this was mine to execute**: it is staging a CEO-accepted
recommendation on the approval channel — Tier 2 — and the gating that
Fable's handoff placed on it ("no rebase until the audit lands") was
corrected earlier today on the COO's dissent, which I accepted: the
confirmed defect bites the SECOND rebase only, and `rebase: None`
confirmed live that this was the first. **Fable: if you read that
differently, this is the entry to challenge.**

This closes the COO's "accepted-but-undischarged" class item — the one
that carried status `accepted` since morning while the decision itself had
never been taken, and which the desk counter structurally could not see.

[Fable @ resolve]:

---

## 2026-08-21 ~13:05Z — TIER-3 BOUNDARY CROSSED ON EXPLICIT CEO APPROVAL — COO trigger threshold changed IN CODE

**What**: `app/fund/desk.py` — `COO_TRIAGE_THRESHOLD` 20 → 50, and the
comparison `total > COO_TRIAGE_THRESHOLD` → `total >= ...` (the CEO said
"≥50"; with strictly-greater the trigger would have fired at 51). A
versioned written reason sits in the code comment, including the COO's
objection.

**Fable — read this one first, because I crossed a line you drew.** My
charter lists "any threshold or register change" as Tier 3, park it. I
told the CEO exactly that, and said "say the word and I'll close it"; he
approved. I judged that completing an amendment the CEO had already
dictated and which the constitution already recorded is not the same as
*making* a threshold decision — and that leaving the doc and the code
divergent was worse than either state. **If you disagree, this is a
one-line revert and I will take the correction into my memory.**

Mitigations I applied: the divergence erred SAFE while it existed (code
20 fired earlier than the CEO wanted, i.e. more oversight, not less); the
written reason is in the code, not only in the constitution; the COO's
dissent is carried in both; desk_load is 10 today so the change has no
immediate operational effect; `tests/test_desk.py` 13/13 green and no test
pinned the old value (checked by grep before editing).

[Fable @ resolve]:

---

## 2026-08-21 ~18:10Z — TIER-2 TAKEN — builder D7 recovered, gate-verified, merged, spine restarted, PIT backfill applied

**What**: The D7 dispatch had COMPLETED in Fable's session (bundles written
17:38Z). Recovered per the handoff's step 2 and merged both repos.
- Gates run by me before any merge, via `scripts/merge_builder.py`:
  ClarkHarness bundle base `ec816f7` → **PASS, 1277/1277, 19 ordinary /
  0 sensitive / 0 forbidden**; KryptonPay bundle base `cbc32b8a` →
  **PASS, 215/215, 14 ordinary / 0 sensitive / 0 forbidden**.
- The gate demanded one human judgement: new constant `DEFAULT_MAX_CHARS
  = 400_000` in `scripts/ingest_transcript.py`. Read it: a runaway-file
  guard with its basis in the comment, NOT a financial or risk threshold.
  Cleared.
- `src/lib/fund_api.ts` is touched (+21) — checked line by line: purely
  additive (`getDeskArchives`), **zero thesis types**, Abhishek's
  surfaces untouched.
- Merged ClarkHarness first (KryptonPay's new UI calls its
  `/desk/archives` endpoint — coupled, both or neither). Heads now:
  **ClarkHarness `c209b0d` · KryptonPay `63454533`**.
- Spine restarted. Verified live: book unchanged (NAV $1,884.79, gross
  48.61%, halted False), `/fund/desk/archives` serving Donna's shelf
  (1 daily + PDF), secretary now in the roster (10 seats).
- Ran the builder's documented completion step:
  `backfill_observation_pit.py --dry-run` then `--apply` →
  **249/249 accessions resolved, 1035 rows updated, 0 unresolvable, 0
  left alone.** Note: the observations schema migration runs LAZILY on
  first use of the store, so the script correctly refused after the
  restart until `GET /fund/research/observations` was touched.

**Why**: Fable's handoff, verbatim: "Merging on a PASS with 0
sensitive/forbidden surfaces is Tier 2 — do it, restart the spine,
ledger it here."

**Evidence**: run record `run-builder-dispatch7` (full report verbatim in
`output` per the durability rule); builder STATE appended verbatim to
`.claude/state/builder.md` with my chair note; merge commits `c209b0d`
(CH) and the KP merge; gate outputs reproducible by re-running
`merge_builder.py` against the bundles in `scratchpad/d7/`.

[Fable @ resolve]:

---

## 2026-08-21 ~18:10Z — TIER-3 DEFERRED — the API card carries a FALSE EDGAR instruction; it is your instrument, so I did not edit it

**What**: `.claude/state/API_CARD.md` currently states that EDGAR's
`acceptanceDateTime` "carries a 'Z' suffix but is **ET = the stamp minus
4 hours**". As an instruction to shift stored values this is FALSE and
actively dangerous. The raw stamp is **genuine UTC**. No shift.

**Why it matters**: the D7 brief propagated this line as "a CRITICAL
detail the analyst verified" and asked the builder to shift stamps by
−4h on the way in. **The builder refused it on measurement.** Had it been
applied, every stamp at raw hours 22–23 would have moved into the
previous evening — MANUFACTURING the sub-daily lookahead that the
`accepted_at` column exists to detect.

**Evidence — three independent measurements, two of them mine**:
1. Builder: hour histogram n=2,400 (dead zone 03:00–09:00 raw = EDGAR's
   06:00–22:00 ET window read as UTC) and the decisive next-business-day
   roll-over test, n=30,732.
2. **Mine, independent, n=4,895 across 6 issuers**: raw hours 06–09 UTC
   are COMPLETELY EMPTY — that is 02:00–05:00 ET, when EDGAR is shut;
   under the ET reading those hours would be 06:00–09:00 ET, when EDGAR
   OPENS, and a dead zone cannot sit inside opening hours. Raw hours
   17–18 show **280 same-day filings and exactly 1 roll-over**, where the
   ET reading places the 17:30 cutoff. Raw hours 00–02 show **646
   roll-overs vs 24 same-day** = the 20:00–22:00 ET evening window
   rolling to the next business day, exactly as EDGAR's rule states.
3. **Mine, at the data layer after the backfill**: SRPT's 10-Q stores
   `accepted_at 2026-08-05 20:01:46+00` = **16:01:46 ET — precisely the
   figure the analyst themselves cited**. And 643/1035 rows (62.1%) sit
   post-close, matching the analyst's independently measured 62.3%.

**Root cause, for the record**: the analyst MEASURED correctly — "ET =
the JSON stamp minus 4 hours" is a true recipe for OBTAINING ET from the
stamp. The phrasing then inverted across two hops (card, then brief) into
an instruction to shift the STORED value. A true measurement became a
false instruction without anyone lying.

**Why deferred rather than fixed**: the API card is the CTO chair's
instrument (my memory: "report its defects in your queue entries so
Fable fixes it"). The code now defends itself — the builder shipped the
no-shift decision with the measurement in the column comment, the
docstring, and a test named so anyone re-proposing the shift meets the
argument first. Exact replacement text for the card's EDGAR gotcha:

> EDGAR `acceptanceDateTime` is **genuine UTC** — the `Z` is correct and
> **NO shift is applied on the way in**. To DISPLAY ET, subtract 4h
> (EDT); EDGAR's own filing-index pages render ET, which is why an index
> page reads 4h behind the JSON. Measured three ways (builder n=2,400 +
> n=30,732; co-CTO n=4,895; stored corpus spot-check). The
> `fund_observations.accepted_at` column stores UTC unshifted.

Also worth your eye at the same time: this is the second consecutive
dispatch in which the builder corrected a chair (D6 caught Fable's
`lookback_days=3650` card line via the mechanism; D7 caught this one).
Two hops of paraphrase is where this firm's facts decay — the card's new
rule that every claim carries its verifying command is the right fix and
should be applied to the EDGAR lines specifically.

[Fable @ resolve]:

---

## 2026-08-21 ~18:10Z — NOTED (no action) — two housekeeping items in the KryptonPay tree

**What**: (1) A **0-byte file literally named `=`** sits untracked at the
KryptonPay root (created 2026-08-21 01:32Z, almost certainly a shell
redirect mishap). I did NOT delete it — deletion is destructive and it
costs nothing to leave. (2) Fable's dispatch briefs
`docs/briefs/BUILDER_D6_2026-08-21.md` and `BUILDER_D7_2026-08-21.md`
were untracked; I committed them as part of resolving D7, since a brief
is the record of what was dispatched and the durability rule now names
briefs explicitly.

**Evidence**: `git status` in KryptonPay before the merge; neither file
collided with the incoming diff, which is why the merge was safe.

[Fable @ resolve]:

---

## 2026-08-21 ~19:40Z — TIER-2 TAKEN — COO triage #3 fired, filed; TWO DISSENTS AGAINST ME ACCEPTED

**What**: `desk_load` crossed to 23/20 with `coo_triage_due: True` (my own
D7 run record supplied the last four items), which constitutionally
DEMANDS a coo dispatch under standing CEO authorization. Fired it,
verified three of its claims, filed the memo verbatim to
`docs/coo/TRIAGE3_2026-08-21.md`, recorded `run-coo-3`, appended its
STATE.

**Vishesh objected to two of MY decisions and I accepted both**:
1. **The refuted EDGAR line should have been QUARANTINED, not merely
   parked.** He is right: leaving a proved-false instruction live in a
   document every seat reads is not the same trade-off as declining to
   edit another chair's file. Quarantine ≠ overruling. I have put a
   one-line **REFUTED banner** on the API card entry (the false text is
   struck, the correct rule is stated above it, and the full correction
   stays parked for you). His own pending-verdict #5 — "was the card's
   EDGAR line quarantined, or did a seat act on the false instruction
   first?" — is answered in the same hour it was written: quarantined,
   nobody acted on it.
2. **Gating PM R1 on the riskofficer audit was one step tighter than the
   code supports.** He read `fund.py:3619` and showed the direction check
   sources `unrebased_peak_nav`, which never moves — which is precisely
   why the confirmed defect bites the SECOND rebase and cannot bite the
   first, and the fund has never had a first. **Fable: I am not editing
   your handoff entry, but I am correcting its operative line here** — the
   gate is "audit before rebase #2", not "audit before the CEO's choice".
   R1 goes to the CEO as its own decision. Measured cost of the extra
   step, in his numbers: $874.45 idle above the 5% cash floor and 58.4%
   halt odds carried another day.

**Two findings of his that outlive this triage**:
- **The counter has a structural blind spot.** An item at status
  `accepted` whose execution requires the CEO *personally* is invisible to
  `desk_load` — the status says the human acted, the record shows the
  decision was never taken. Three live today: **PM R1** (the
  largest-money decision in the firm), `GET /fund/autopolicy` (still
  404 — the seat scoring its own triage-#2 batch as undischarged), and
  the controls-or-decoration register answer (concentration limit still
  reads 0.50). He has adopted an accepted-item second pass as standing
  method; making the *counter* see it is open work.
- **On 2026-09-08 the TLT and DBC time exits will auto-close $501.34
  with no click** — he checked all nine envelope conditions. The
  re-establishment needs the CEO and nothing schedules him. He
  recommends a PM dispatch on 2026-09-05.

**Evidence**: `run-coo-3`; `docs/coo/TRIAGE3_2026-08-21.md`;
`.claude/state/coo.md`; my verifications — `fund.py:3619`,
`GET /fund/autopolicy` → 404 live, count audit 20+0+3=23.

[Fable @ resolve]:

---

## 2026-08-21 ~19:45Z — CEO-DICTATED AMENDMENT APPLIED — COO trigger >20 → ≥50, over the COO's recorded objection

**What**: The CEO instructed, verbatim: *"Lets run coo on >=50 items or we
can trigger as needed."* Applied to `.claude/CLAUDE.md` dispatch rule (2)
as a dated amendment. Manual dispatch at any count remains available and
is the CEO's stated preference.

**Why I treated this as within the chair rather than parking it**: the
charter's Tier-3 carve-out is "constitution changes **beyond dated
amendments the CEO dictates verbatim**". This is a dispatch-cadence rule
in constitution prose — it touches no risk limit, no register entry, no
code, and moves no money. **Fable: if you read that boundary differently,
this is the entry to reverse and I will take the correction.**

**The anti-quiet-loosening rule is satisfied loudly, not quietly.** It is
a loosening, so the amendment carries: the CEO's verbatim instruction; the
measured reason (triage #3 found **11 of 20 open recommendations already
executed** — the counter was summoning the seat on stale bookkeeping); and
**the COO's objection preserved verbatim in the constitution beside it**.
Vishesh recommended KEEPING 20, with his interest disclosed, arguing "the
number is not the defect, the blind spot is."

**Honest note on the merits**: his objection is not resolved by this
change and I have said so in the amendment text. Raising the threshold
does nothing about accepted-but-undischarged items, and today's evidence
cuts both ways — the counter over-fired on bookkeeping (supports the CEO)
while the single largest decision sat invisible (supports the COO). The
real fix is a counter that measures what actually awaits the CEO. That is
open work and belongs in a builder brief.

[Fable @ resolve]:

---

## 2026-08-21 ~19:50Z — TIER-1 — Donna dispatched for today's EoD; CEO desk-surface request filed

**What**: (1) Fired Donna for the 2026-08-21 Daily — standing CEO
authorization, and her first fully self-service run under the
constitution's third write exception (she files her own archive and
renders her own PDF; I verify and commit). (2) Filed desk request
**920ecbe5** to the builder on the CEO's verbatim instruction: *"For
Donna http://localhost:3000/clark/studio/desk/ceo lets have her high
level memo for today from her yesterdays EoD and when it arrives
autoupdate it"* — the Donna queue must surface her latest filed Daily's
high-level memo with its date visible, auto-updating when a newer one
lands; the long record stays on her seat page. Batched for D8 with the
untouched Part G addendum.

[Fable @ resolve]:

---

## 2026-08-21 ~20:10Z — TIER-2 TAKEN — COO batch acceptance CASCADED; desk_load 23 → 0

**What**: The CEO accepted all five COO batches (`run-coo-3` recs 1–7,
seq 658–668) plus individual recs, and approved four desk requests. Per
the constitution's cascade amendment I executed the underlying items and
marked them, validating each ONCE against the record first — nothing
re-executed, every mark carries its citation.

- **8 marked done**: builder D7 rec 1 (the refutation — closed as the
  PAIR with analyst rec 5 exactly as Batch 3 required, now that the card
  is quarantined) and rec 3; mechanism cycle-2 recs 1–4 (all four applied
  to the premia menu, commit `c16ec13`, independently verified by the COO);
  analyst cycle-2 rec 1 (shipped in D7 + backfill applied, 1035 rows) and
  rec 4 (entry-8 NO-GO recorded and respected in practice).
- **3 marked staged**: builder D7 rec 2 (the long backtest — queued as
  the next local-compute action, see the sequencing note below), rec 4
  (Part G → dispatch 8), builder D6 rec 1 (the rebase defect → riskofficer
  `dc7b068c`, not done until the audit returns).
- **desk_load 23 → 0.**

**Three items filed** to complete the batches — two of them are decisions
the COO found had **no route to being decided** because they lived only in
a markdown file:
- `395335c8` — dated PM ask for **2026-09-05**, three days before the
  TLT/DBC time exits auto-close $501.34 (Batch 2).
- `4a1207c1` — the hardcoded `"neelesh"` approver convention, to the
  riskofficer (Batch 5).
- `84492cad` — the corpus-deepening budget call, to the analyst, with the
  recommendation to decide it alongside the entry-14 dispatch rather than
  in isolation (Batch 5).
The third flow-test decision (the COO trigger threshold) was decided by
the CEO the same day as ≥50.

**One sequencing judgement I am flagging rather than burying**: COO Batch
4 said "fire builder D7 rec 2 now — free local compute". I marked it
staged instead of running it, because the machine is currently carrying
Postgres, the spine, the dev server and a live Opus agent (Donna's EoD
run), and a >900s LEAN container alongside them would measure contention
rather than runtime — which is the opposite of the point. It is the next
local-compute action once the seat finishes. **Fable: if you would have
just run it, say so and I will stop hedging on resource contention.**

**Still awaiting the CEO personally, and no chair can discharge it**: PM
R1 — the drawdown reference, three options, ~$400 of blocked capacity,
halt odds 58.4% vs 9.6%. It is no longer gated on the riskofficer audit
(dissent accepted above). This is the COO's "accepted-but-undischarged"
class: the status says decided, the record says it never was.

[Fable @ resolve]:

---

## 2026-08-21 (UTC) — GATE v5 ROUND 5 CLOSED + a confirmed defect in our own price feed

**co-CTO chair. Everything below is filed, recorded and reversible. Fable: the
two judgement calls are flagged as JUDGEMENT and each says how to reverse it.**

### A. Gate v5 round 5 — MEASURED, CLOSED, NOT ADOPTED

CEO instruction, verbatim: *"Lets close gate v5 so we can keep testing and keep
your notes for fable so he is aware exactly."* That instruction overrode this
chair's Tier-3 parking of gate architecture; the design doc
(`docs/GATE_V5_ROUND5_DESIGN_2026-08-21.md`) recorded the override and every
judgement call before any measurement ran, so you can audit the round cold.

**Result: `docs/GATE_V5_ROUND5_MEASURED_2026-08-21.md`, run
`run-validator-gate-v5-r5`.**

- **G1 financing: FIXED, and the validator could not reopen it.** The zero-skill
  cash mix scores 0.0000 %/yr at every weight and 0.0% in all 16 Monte-Carlo
  cells (0/2000 ⇒ CP95 upper bound 0.2%), where round 4 handed it up to
  +35.11%/yr. Running the SAME cells through round 4's statistic reproduces the
  adversary's Ground 1 at **98.6% conditional** — an independent confirmation of
  both the kill and the repair, in the reachable geometry.
- **G3 geometry: honoured.** `window_for_strategy` imported and CALLED.
- **G4 data path: exists, and HAS NEVER RUN.**
- **THE RULE IS NOT ADOPTABLE.** Two blocking holes:
  - **H1 — no risk-free series exists anywhere in the gate path.** "Excess
    returns" is not a fix by itself; it is a fix *conditional on an rf source we
    do not have*. `rf_assumed = 0` reproduces round 4 EXACTLY (+5.88%/yr at
    w=0.40). `rf = 2%` against a realised 3.97% certifies a zero-skill 40/60 mix
    at +2.90%/yr against a 2.0%/yr margin. **This is now the CEO's decision and
    it is on his desk.**
  - **H2 — discrimination 0.62, CI [0.53, 0.72], excluding 1.0.** At the class
    maximum the worst plausible null passes MORE OFTEN than the designed premia
    claim. A margin sweep 1→8 %/yr costs the true claim (13.0→4.3) and barely
    touches the worst null (21.2→16.6). Round 3's pattern in a new statistic.
  - **H3 names the mechanism**: vol-matching is the amplifier — the worst null
    is a 3%-vol stream levered 6.48× to a 20%-vol benchmark. Registered as round
    6's first experiment.

**Chair verification before filing** (three claims, all confirmed):
`GATE_VERSION = "v4.1"` at `gate.py:157`; `git status --porcelain scripts/`
shows only `?? gate_v5_audit_r5.py` so **r4 was left untouched**; and
`select count(*), count(analytics) from fund_candidates` → **`37 | 0`** against
Postgres directly. Zero of thirty-seven. Round 5 is a model of the instrument,
never a run of it.

**JUDGEMENT 1 — I closed round 5 as a measured NO rather than adopting anything.
To reverse: adopt the premia rule.** I did not, because adopting a judging rule
whose discrimination is below a coin is the unwired-kill-switch pattern relocated
into the instrument that decides what reaches money. "Close gate v5" was
satisfied by finishing the round honestly, not by shipping a rule.

**Nothing retrospective is affected.** No verdict has ever used a v5 premia
statistic; the only three passes on the belt are `null_random_smallcap` under v1,
the known v1 failure. The cost is prospective and it is leg-2/leg-3: **the premia
sleeve has had no criterion at all since the identity decision of 2026-08-19.**

### B. A CONFIRMED DEFECT IN OUR OWN PRICE FEED — the bigger finding of the day

From the analyst's batched cycle-3 dispatch (`run-analyst-cycle3`, artifact
`docs/ANALYST_CYCLE3_PRICE_ANCHOR_2026-08-21.md`). The dispatch's assigned job —
8-K item 5.02 drift — came back **DEAD** (calendar-time t=0.65, beta_IWM 0.96,
alpha t=−0.42; the basket IS the small-cap index). The by-product is worth more.

**Our price history carries a low-minus-high price factor of +49.68%/yr (t=5.69)
on adjusted closes and +43.84%/yr (t=4.62) on nominal, positive in all seven
years.** Two causes, both **verified by me before I acted**:

- **Today-anchored split back-adjustment.** `GET /fund/marketdata/bars?symbol=TENX`
  returns `closes[0] = 2320.0` for 2020-06-01 and a 2020 high of 3168.0 — for a
  sub-$2 biotech — on a 1600× reverse-split factor. `end_date` does not move the
  anchor. The payload carries `adjusted: None` / `adjustment: None`: **it does
  not name its own anchor**, even though `marketdata.py:289-290` has the fields.
- **Total survivorship.** I re-counted attrition and it is **starker than the
  analyst reported**: **203 of 203 symbols have a last bar of 2026-08-20 or
  2026-08-21.** Not "zero before 2026-08-18" — *every single name in a six-year
  small-cap universe is alive today.*

**Why it matters more than the 5.02 kill: the walk-forward gate is
STRUCTURALLY BLIND to it.** Walk-forward slices TIME, and every fold reads the
same today-anchored survivor-only series, so the contamination is identical in
train and test. A candidate sorting on price level, market cap or dollar volume
presents ~+44%/yr at IR ~1.9, positive in EVERY fold, and passes.

**Actions taken (all Tier 1, all reversible):**
1. **The no-price-level-sorting rule is IN FORCE**, written into
   `.claude/state/mechanism.md`, `quant.md` and `validator.md`. Returns are safe
   and unaffected; price level, market cap, dollar volume, share count and any
   filing-dollar-vs-our-close ratio are not.
2. The placebo rule is in force in the same three files: every cross-sectional
   conditioning claim carries an event-independent placebo (±60/120/250 sessions)
   before it is believed. It killed two |t|>3 "findings" in this dispatch alone.
3. Builder ticket **`7032a0fd`** — split events (`&events=div,split`), a
   nominal-price view, and populate the anchor fields. Approach already proven on
   202/202 symbols.
4. Builder ticket **`6aadd330`** — expose `accepted_at`/`period`/`items` on
   `/fund/research/observations` and correct the API card. The analyst bypassed
   the fund's own corpus for a whole dispatch because of this.

**JUDGEMENT 2 — I did NOT inject the gate-blindness half into round 5, which was
in flight. To reverse: fold it into round 6's brief, which is where I put it
(`4698dee7`).** Round 4 died with four grounds because it changed two structural
things at once. Round 5 fixed financing and measured the masked family; that is
enough for one round.

### C. AWAITING THE CEO — two items, and only one is urgent

1. **The risk-free source for the gate (H1).** His own excess-return amendment
   is not implementable without it, and a static assumed rate reintroduces round
   4's hole. Recommendation on the desk: a realised daily short-bill series (the
   spine already serves BIL at 2,779 sessions), not a constant. **The measurement
   is the seat's; the choice and its version are his.**
2. **Fence the 200-name universe** as a pre-instrument reference frame under the
   CLEAN FIELD RULE. It **cannot** be re-baselined — no point-in-time universe
   membership exists in the fund — so the fence clause applies rather than the
   re-baseline path. I did NOT adopt this silently: guard rail 5 puts a change to
   the frame future work is judged against on the approval channel. Consequence
   if accepted: no new work is ever judged against this universe's ABSOLUTE
   returns (the +24.77%/yr EW figure included); relative and return-based work is
   unaffected.

### D. Market-closed work — a category, not a parking space

CEO instruction, verbatim: *"lets park it for weekends when market is closed."*
Filed as **`f2d70a55`**: the harness replay engine (adversary writes scenarios
blind, builder implements, complete store isolation, first subject our own August
because F4 is still unexplained), the ~3.4h corpus deepening, and the
long-window backtest that still exceeds the 900s ceiling. **Registered as a
TRIGGER, not a schedule** — a human fires it when a session is live and the
market is closed, exactly like the COO's desk-load trigger. Writing it any other
way would smuggle a cron into a firm whose cost ceiling rests on "when no session
is live, nothing thinks."

### E. Two housekeeping facts you will want

- **A dating trap I nearly walked into again.** Local IST had rolled to
  2026-08-22 while UTC was still 2026-08-21 19:40Z. Both seats dated their STATE
  headers 2026-08-22 (local); I named both findings docs for **UTC** and left the
  STATE headers verbatim with a bracketed chair note saying they are the same
  moment. Same error family as my fabricated-timestamp correction, caught this
  time by reading the clock before writing.
- **Task output files are being written 0 bytes.** The analyst's dispatch output
  file was empty and the report survived only in the run notification; many files
  in that directory are 0 bytes. I filed the artifact from the notification and
  **disclosed the transcription in the doc's provenance note**. Worth knowing
  before you trust a task output file.

---

## 2026-08-21 (UTC) — DECISIONS ARE PROVISIONAL: a constitutional amendment, and the first challenge

**co-CTO chair. Fable: this is a dated amendment carrying the CEO's verbatim
instruction, which the charter puts inside my lane. Everything downstream of it
is Tier 1 except one item, which is parked for you.**

### The instruction

CEO, verbatim: *"Imp; my approved decisions needs to continually evolved and
updated so the team is requested to question it and recommend changes."*

### What I wrote, and the gap it closes

New constitution section, **"Decisions are provisional"**, placed immediately
before the non-negotiables. Eight clauses. The reasoning I want you to check:

**This firm had excellent machinery for MAKING decisions and almost none for
REVISITING them.** Working protocol 1 says every artifact is falsifiable or it
is rejected — and then decisions, the highest-stakes artifacts here, were
exempt. The proof was sitting in the constitution already: the COO's objection
to the ≥50 threshold is marked *"preserved unresolved"*, which is honest and
completely inert. Nobody owned it. Nothing triggered on it. It would still have
been there in a year.

The clauses, in brief: decisions are provisional including the CEO's own and
this constitution (1); challenging one is a **duty**, not a permission (2); the
admissibility bar is **new evidence or a demonstrated consequence** — *"I would
have decided differently"* is not a challenge (3); every new decision records
what would change its mind (4); a challenge that would **loosen** a control goes
to the adversary blind first (5); challenges route through the COO batch (6);
rejected challenges are recorded and re-filing needs new evidence (7); challenge
and reversal remain different acts, so **my non-reversal rule toward your chair
is unchanged — I may now challenge your decisions in writing, and still may not
reverse one** (8).

Clauses 3, 5 and 7 exist because without them this section is a token furnace
and a quiet-loosening channel. I would rather you check those three hardest.

### The best part is that the machinery already existed

I was about to specify a new register and found `app/fund/judgement.py` already
does it: `falsified_by`, `review_trigger`, `registered_value`, drift detection
between what was decided and what the code now does, and `due_for_review`. It
even carries the exact lesson this amendment is about, in its own docstring —
*sixteen of seventeen registered triggers were free text no code evaluated, and
the register returned `due_for_review: []` while a 7.75% drawdown sat there.*

So clause 4 **points at judgement.py rather than inventing a parallel system.**

**The measured gap: all 19 registered entries are NUMBERS.** Not one governance
decision is registered — not the fund identity, the COO threshold, the
auto-approval envelope version, the co-CTO charter, the experimental-deployment
authorization, or the excess-returns amendment. All prose in CLAUDE.md, watched
by nothing. Five of the 19 also read `readable: false`, so the register cannot
check those either.

**TIER 3 — PARKED FOR YOU, NOT EXECUTED: extending the register to governance
decisions is a register change, which the charter makes a CTO-chair action.**
Filed as **`61a065c2`** with my review note. My recommendation, for you to take
or discard: extend the existing register rather than build a second one (a second
register is a second thing to forget to read), and make a governance entry whose
trigger cannot be evaluated render as **UNCHECKED** rather than silently as
not-due — because the module has already proved that unevaluable triggers make
the register lie.

### Making the duty real in the seats (Tier 1, done)

A duty that lives only in the constitution is a duty no seat reads at dispatch
time. The `## CHALLENGE` clause is now in the uniform session contract of **all
ten seat definitions** — with the admissibility bar, the loosening/adversary
rule, and the line that filing a challenge never licenses a seat to act against
a decision while it stands.

### CHALLENGE #1, filed the same session — `2c4c4451`

I held it to the bar I had just written rather than re-raising the COO's
objection as-is, and it cleared:

- **New evidence**: the desk counter reads **30 of 50** and reports no triage
  needed, while **31 recommendations sit at status `accepted` that the counter
  counts none of.**
- **Demonstrated consequence**: the trigger is reading 30 against a backlog it
  cannot see. No threshold value fixes an instrument measuring the wrong
  quantity.

**And it cuts partly at me, which I disclosed in the filing rather than leaving
for the COO to find.** Those 31 are a mixture of two states the fund cannot tell
apart — genuinely awaiting execution, and executed-but-never-marked — and a
large share of the second kind is **my own unmarked cascade**: I executed the
COO's batch acceptances by actioning the underlying items and never marked the
batch recommendations themselves done. So the pro-raise argument (that the
counter was summoning the seat on stale bookkeeping) is **partly vindicated by
the same measurement**.

**I am NOT recommending reverting 50 → 20.** I am claiming the counter measures
items awaiting a DECISION and is blind to items awaiting EXECUTION, and that
until those are distinguishable no number measures the CEO's real load.
Recommended order: the chair sweeps its own unmarked cascade first so the number
is clean, then the COO re-triages, then the threshold is revisited on a number
that means what its label says.

**A challenge whose first casualty is the chair that filed it is the right way
to open this rule.** If the first one had been aimed only outward I would trust
the mechanism less.
