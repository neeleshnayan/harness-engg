# coo — working state
(appended by the CTO at each dispatch resolution; newest at the bottom)

## 2026-08-20 — seeded at seating, before the first dispatch

- Seated the day the CEO's desk hit ~20 open recommendations across four runs
  (pm staging R1–R7, riskofficer envelope-v2 R1–R7, builder ×2) plus pending
  sell tickets and a halted book awaiting manual resume. The seat exists to
  convert that into a handful of batch decisions.
- The line: endorse, never decide. The click is the CEO's. If asked to "just
  approve it", the answer is the constitution, cited.
- Standing context for the first triage: the fund is paper, NAV ~$1.88k after
  the phantom-price incident (docs/INCIDENT_GLD_PHANTOM_PRICE_2026-08-20.md);
  three strategies retired same-day (paused + alloc 0, positions partly sold);
  gate is v4.1, v5 round 3 under adversarial attack; the funnel operating docs
  are docs/research/FUNNEL_2026-08-20.md + PREMIA_MENU + REVIVAL_REGISTER.
- Items known to be time-sensitive by construction: pending order proposals
  expire at 120 minutes (PROPOSAL_STALE_AFTER_MINUTES); the halt persists
  until the CEO resumes; everything else keeps.
- Read the desk whole before ranking: GET /fund/desk (runs, recommendations
  with statuses, requests), GET /fund/orders/pending, GET /fund/risk/monitor,
  docs/README.md for register statuses.

## 2026-08-20 — first dispatch (f35c4fad / trace f35c4fad-bcae-4509-a1cd-7272da8b065a): founding triage

WHAT THE DESK LOOKED LIKE: 20 open items → 6 batches + 1 explicit non-decision.
Batches named: A four sells+R7 / B envelope v3 (RO-R5 + PM-R4) / C register
questions / D gate v5 r4 (5 as a set, rec 2 SPLIT) / E sleeve record (PM R2,R3,R5)
/ F ignition (8804b28d, 2f0959d6). Decide order: A → D-rec2 → C → B → F → E → D-rest.

THE FOUR THINGS I VERIFIED THAT CHANGED A DESK ITEM'S MEANING — re-check these
first next dispatch, they are the seat's proven value:
1. pipeline.py:72 — the halt blocks BUYs ONLY. SELLs are approvable while halted.
   riskmonitor.py:575-581 auto-halts within one 6s tick while a critical
   daily_loss/drawdown alarm is live, so "resume" today is undone in seconds.
   riskmonitor.py:441-448 measures daily loss vs the PRIOR-DAY strike → it clears
   on the UTC date roll, not on a click. HALT RESUME IS NOT A DECISION while the
   alarm is critical. This is a permanent triage rule, not a one-off.
2. autopolicy.py rule_predates_position (set_at < opened_at, fails closed)
   makes PM_STAGING §2 fact 1 ("committing a rule is an executable act")
   FALSE at v2 for every position opened before the rule. Live auto-execution
   coverage today is TLT ($250.71) + DBC ($249.84) ONLY — the sleeve rules set
   2026-08-18T02:11:39Z vs fills 2026-08-19T18:20Z. Therefore riskofficer R5
   protects $0 today; endorse it as structural, never as an emergency.
3. exitrule.py:275-278 skips already-triggered rules → the machinery-test GLD 25%
   rule (triggered 08:01:26Z, GLD qty 0) is INERT, not armed. PM R4 re-scoped from
   live-risk to record-keeping. BUT exitrule.py:181-183: re-committing CLEARS
   `triggered`, so the override still needs recording.
4. /fund/judgement is a decision source no seat owns. It carried a DRIFTED entry
   (MAX_CONCURRENT_CONTAINERS registered 1, live 6 at leanrunner.py:83 — a
   constitution violation with no rec attached) and TWO fired review triggers
   (min_effective_bets, trigger "first drawdown episode over 3% from peak", live
   7.75%; max_drawdown_pct, whose trigger text still says "currently 3.3%
   utilised" against a live 0.7747). READ /fund/judgement EVERY DISPATCH.

THE SHARPEST OBJECT FILED: docs/research/FUNNEL_2026-08-20.md listed "history
backfill to ~10y" as prerequisite #1, first in order. That trips
min_walkforward_folds' BLOCKING review and its measured consequence (gate FP
2.9% → 12.5%), and adversary rec 2 blocks it independently. Must be settled
BEFORE the funnel is fired.

NUMBERS AS OF 10:44Z (all re-read, never carried forward):
NAV $1,878.60 / cash $743.51 / gross $1,135.09 (60.42%) / drawdown 7.75% of 10%
/ daily_loss alarm 6.62% vs 4.00% critical / halted true.
4 pending sells $634.55 total, staged 10:21:40Z, EXPIRE 12:21:40Z — they had
ALREADY expired once. Post-batch gross = $500.54, sleeve-only. /fund/exits:
9 rules, ZERO on SOFI/NVDA/XLE/SPY. /fund/tca sample 16, bar 20 → the four
sells hit exactly 20 and discharge sleeve falsification #2 (D5), which makes
PM R5's D5 half wrong if A is approved. Three paused strategies hold $810.21
= 43.13% of NAV (builder C1 defect verified).

METHOD THAT WORKED, REUSE IT: read /desk once into a file and parse it (69KB,
33 "open_recommendations" of which only 13 are actually status=="open" — the
field name is misleading, filter on status). Then /orders/pending, /risk/monitor,
/judgement, /exits, /exits/check, /tca, /liveness, /positions, /strategies,
/nav, and the empty queues for absence discipline. Base path is /api/v1/fund.
Then go to the CODE for anything that determines whether an item is still live —
three of my four best findings came from reading pipeline.py / autopolicy.py /
exitrule.py, not from an endpoint.

STANDING RULE FOR NEXT TIME: a seat's recommendation text ages faster than the
code it describes. PM_STAGING was ~7h old and two of its load-bearing mechanics
had been fixed underneath it. Always re-derive an item's premise before ranking
its urgency — that IS the job.

- [CTO note at resolve, 2026-08-20]: your funnel-ordering objection was
  SUSTAINED and fixed the same hour (FUNNEL doc §3 reordered, gate-before-data,
  with the error kept on the record). MAX_CONCURRENT_CONTAINERS drift and
  pipeline.py:72 both CTO-verified. Memo filed verbatim at
  docs/coo/TRIAGE_2026-08-20.md; envelope posted as run-coo-1; your batches
  are on the CEO desk page. One correction for your next read: the desk UI now
  has a "Requests between desks" section with CEO approval — approved asks
  show on the CTO desk as "trigger it".

## 2026-08-20 — triage #2 (desk_load=73), CTO append of the seat's STATE + note

[The seat's full STATE is embedded in docs/coo/TRIAGE2_2026-08-20.md and the
run record run-coo-2; headline items copied here for cold reads:]
- desk_load counted open+accepted+staged: 73 -> 10 truly open (3.65x). FIXED
  by the CTO at resolve (status=="open" only; rows with no status count).
  Next dispatch: recompute the true count FIRST before accepting a triage
  was due.
- SELF-REVERSAL, the seat working: founding r6 deferred sleeve falsification
  D5 expecting the 4 fills to reach the TCA bar - all were paper-venue,
  execution_bps -0.0 by construction. STANDING RULE: never count a paper
  fill toward any cost or execution bar, ever, at any sample size.
- Halt arithmetic, exact: reference = last strike with UTC date < today; at
  00:00Z it rolls to the 08-20 close ($1,884.55) vs NAV $1,884.98 = +0.02%,
  clears free; early resume re-halts within a tick. The rebase control is
  for trading INSIDE the day you lost - objected to spending it on a wait.
- Verified: GET /fund/autopolicy 404 (envelope v3 unreadable); CLAUDE.md
  still documents v2 (stale, not loosening); ExecutionQuality.tsx reads the
  diluted top-level TCA summary; judgement due() has no acknowledged concept
  (min_effective_bets reads due:True permanently while drawdown > 3% - a
  light that never goes out stops being read; WATCH).
- money_at_stake: write-path only; 0 of 73 legacy recs carry it; this seat
  populates it in every run record and pushes others to.
- [CTO note, 2026-08-21]: three claims verified line-exact before acting;
  the desk_load fix landed same-hour with the incident in the test
  docstring (live 73 -> 16, due False). Batches A/C/D/E/F/G await the CEO.
  Memo filed verbatim as docs/coo/TRIAGE2_2026-08-20.md (run-coo-2).

## 2026-08-21 — the operator's bar (CEO instruction, appended by the CTO)

The CEO raised this seat's bar, verbatim: "we dont want our COO to be just
doing secretary work; it needs to be really sharp and good at decisioning
and try to think from multiple facets... it has to build trust with CEO and
CTO. If it misses things then me and you cant trust it to do its job."
The full bar is now in the charter (coo.md, "The operator's bar"): miss
nothing and prove completeness; examine every batch from the money/foregone-
money/risk/constitution/load/sequencing/second-order/blind-spot facets and
NAME the deciding facet; keep a hit/miss ledger in this file; anticipate the
next desk, not just this one.

HIT/MISS LEDGER (the trust record — log misses yourself, first):
- HIT: triage #2 audited its own trigger (desk_load 3.65x miscount) before
  accepting the dispatch was due.
- MISS (self-logged, founding entry): founding r6 deferred sleeve
  falsification D5 expecting 4 fills to reach the TCA bar - all four were
  paper-venue, zero information by construction. Caught by self in triage
  #2 before it cost anything. The standard.
- HIT: objected to spending the rebase control on a five-hour wait
  (second-order facet: what saying yes teaches the desk).
- PENDING VERDICTS to score next run: Batch A's "resume at 00:00Z clears by
  arithmetic" (score against what actually happened); the DEFER on the 3D
  floor; the min_effective_bets due-light watch item.

### 2026-08-21 — triage #3 (desk_load 23, trigger 20), co-CTO chair dispatch

**COUNT AUDIT: the trigger was CORRECT this run** — 20 open recs + 0 pending orders + 3 open requests = 23, re-derived independently. The open-only fix from triage #2 is holding. But 11 of the 20 were already executed and needed only a closing sweep; true judgement surface was 12 desk items + 4 off-desk = 16, in 5 batches.

**THE METHOD DEFECT I FOUND IN MY OWN SEAT — this is the standing rule now.**
The open-status filter is NECESSARY AND NOT SUFFICIENT. Items at status `accepted` whose execution requires the CEO personally are structurally stuck: the status says the human acted, the record says the decision was never taken, and the trigger cannot see them. **Every triage from now on runs a second pass over status==`accepted` asking "has the thing it asks for actually happened?"** Three found today: PM R1 (the largest-money decision in the firm), the read-only autopolicy endpoint from my own batch D (verified 404), and the controls-or-decoration register answer (concentration limit still reads 0.50).

**THE ARITHMETIC I VERIFIED IN CODE — re-check these first next run:**
1. The rebase direction check reads `unrebased_peak_nav`, which never moves (fund.py:3619). This is *why* rebase #2 can raise the peak and *why* rebase #1 cannot. The defect does NOT gate R1's decision. The handoff's gating was one step too tight; recorded as dissent.
2. Headroom arithmetic, exact: peak $2,036.35, halt at $1,832.72, NAV $1,884.79 -> **$52.08**. Rebased to peak-$128.26 = $1,908.09 -> halt $1,717.28 -> **$167.51** (+$115.43).
3. Cash floor is 5% (`min_cash_pct`), NOT the `min_cash_buffer: 0.0` field. Floor $94.24, idle above it $874.45.
4. Throttled target = 61% x 0.7941 = 48.44% vs live 48.61% — the book is AT target; the idle cash is caused by R1, not by under-deployment.
5. **TLT and DBC time exits (2026-09-08, $501.34) PASS every v3 envelope check** — rules set 2026-08-18T02:11:39Z, fills 2026-08-19T18:20Z, ~13% of NAV each against a 20% cap. They will auto-close with no click. The re-establish half needs the CEO and nothing schedules him. All four legs' exits are now inside the envelope (SPY/DBA rules 2026-08-21T00:06-00:07Z, fills 06:51Z).
6. `autopolicy.py` has NO venue check despite the constitution's "on the paper venue". Second consecutive triage finding drift in that paragraph.

**HIT/MISS LEDGER (scored against retrospective reality, never against acceptance):**
- **HIT (scored):** triage #2 batch A — "no halt decision tonight; it clears by arithmetic at 00:00Z." Reality: `halted: false`, alarms empty, loss reference rolled to prior_strike 2026-08-20T23:46:35Z at 0.00%, no re-halt. The control was not spent on a wait.
- **HIT (scored):** the desk_load overcount objection. Counter verified accurate at 23 this run.
- **HIT (scored):** triage #2's watch on the min_effective_bets due-light. The review was COMPLETED 2026-08-20 and the light is STILL on (`due: True`, drawdown 7.44% > 3%). Confirmed: the register has no acknowledged/reviewed-at concept, so a completed review cannot clear its own alarm. A light that never goes out stops being read.
- **PARTIAL / still pending:** the 3D-floor deferral. Batch E was rejected and the floor was built and extended (D5, D7). The flow-test synthesis independently named the gate — not the floor — as the binding constraint, which supports the sequencing call; but D7 also shipped genuine gate prerequisites, so it was not purely discretionary. **Observable that settles it: does gate v5 round 5 ship before the next builder UI dispatch?**
- **NOT a miss, but named so I do not repeat the shape:** R1 post-dates triage #2, so I could not have caught it then. The *method* gap was real and is now closed by the accepted-item second pass above.

**PENDING VERDICTS to score next run:**
1. Is R1 discharged, and if a rebase was taken, did the direction hold?
2. On 2026-09-08 did TLT/DBC auto-close, and was a human queued for the re-establishment?
3. Gate v5 round 5 versus the next builder UI dispatch (scores the floor deferral).
4. Does the min_effective_bets due-light ever go out?
5. Was the API card's EDGAR line quarantined, or did a seat act on the false instruction first?

**METHOD THAT WORKED, REUSE IT:** read `/fund/desk` once into a file and parse it (~200KB); filter `open_recommendations` on `status == "open"` (the field name still lies — 47 rows, 20 open); then a second pass on `status == "accepted"` for undischarged execution; then the live endpoints; then `git log` on all three repos; then GO TO THE CODE for anything that determines whether an item is still live. Four of this run's six best findings came from the code, not an endpoint — same as both prior triages.

**STANDING RULES CARRIED:** never count a paper-venue fill toward any cost bar at any n. Read `/fund/judgement` every dispatch. Re-derive an item's premise before ranking its urgency. Money-at-stake includes money FOREGONE — the gate being shut is a leg-2 and leg-3 cost, and it belongs in the batches.

- [co-CTO note at resolve, 2026-08-21]: three claims verified before filing
  (fund.py:3619 unrebased_peak_nav sourcing; GET /fund/autopolicy 404 live;
  the 20+0+3=23 count audit). **BOTH DISSENTS AGAINST ME ACCEPTED.** The
  API card's refuted EDGAR line is now QUARANTINED with a one-line REFUTED
  banner — the seat was right that quarantine is not overruling a chair,
  and it took seconds; the full correction stays parked for Fable. The R1
  gating dissent is accepted as arithmetic: the handoff's "no rebase until
  the audit lands" is corrected to gate rebase #2 only, and R1 goes to the
  CEO as its own decision. **Pending verdict #5 is answered the same hour
  it was written: quarantined, no seat acted on it.** On the threshold: the
  seat recommended keeping 20 with its interest disclosed; the CEO
  instructed >=50 in the same hour; the amendment is applied per the CEO
  with this objection preserved verbatim beside it in the constitution. The
  blind spot the seat identified is NOT addressed by the threshold change
  and is filed as open work.
