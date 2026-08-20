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
