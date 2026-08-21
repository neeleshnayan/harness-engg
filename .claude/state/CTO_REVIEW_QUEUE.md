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
