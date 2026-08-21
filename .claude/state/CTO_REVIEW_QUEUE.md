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
