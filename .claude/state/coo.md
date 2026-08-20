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
