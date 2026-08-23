# E21 RESURRECTION CHECK - PRE-REGISTRATION (written before any regression was run)
Author: analyst (Dr. Mike Darwin). Date: 2026-08-23.

## The condition being tested (verbatim from mechanism.md:653)
"a design with real identifying variation - the 2020 20-year reintroduction as a
natural experiment, or non-mid-month sovereign calendars - showing the PRE
coefficient at |t|>2.5 WITH day-of-month FE."

## CONTRARY FACTS, WRITTEN FIRST (Darwin's rule)
C1. The entire treatment period (2020-05 onward) sits INSIDE the era my own memory
    records as dead: "the mid-month window was alive 2003-13 and is dead 2014-26".
    A positive result here contradicts the era split rather than confirming E21.
C2. 2020-05..2026-08 spans COVID QE, the 2022 hiking cycle and March 2023. TLT
    daily vol in the post period is materially higher than pre; any DiD on raw
    returns is heteroskedastic and the post period will dominate any pooled t.
C3. The 20y point is a known persistent curve dislocation (20y yields above 30y
    for much of 2021-2024). A 20y-specific effect may be a level/cheapness story,
    not an auction-cycle story. The DiD does not distinguish them.
C4. Within the post period alone, the 20y auction sits at a near-fixed trading-day
    -of-month, so tdom FE will absorb most of the PRE dummy by construction. The
    within-post spec is therefore LOW POWER by design and a null there is weak
    evidence. The DiD across the reintroduction is the spec that carries the claim.
C5. n=76 auctions. Minimum detectable effect is computed and reported BEFORE the
    coefficient is interpreted.

## DESIGN (fixed now)
y_t = 100 * (TLT_t/TLT_{t-1} - SHY_t/SHY_{t-1})   [pct/day, Ed's own instrument pair]
tdom = trading-day-of-month, 1-indexed.
EVENT20 = 20y-family auctions (security_term in {20-Year, 19-Year 10-Month,
   19-Year 11-Month}) from fiscaldata, auction_date >= 2020-05-01.
   EXCLUDED: 2021-12-02, offering_amt 25,000,000 (3 orders of magnitude off the
   $12-27bn norm; treated as a data anomaly, exclusion declared here).
PRE20 = 1 on the 5 sessions strictly before an EVENT20 date (E21's own window).

SPEC A (the adversary's literal bar): sample 2020-05-01..2026-08-21.
   y ~ PRE20 + tdom FE. SE clustered by calendar month. Bar: |t(PRE20)| > 2.5.

SPEC B (the natural experiment, the one that carries the claim): DiD.
   Control era = 2014-01-01..2020-04-30 (same regime per the 2014 split, no 20y).
   Treatment era = 2020-05-01..2026-08-21.
   Placebo anchor in the control era = the MEDIAN tdom of post-period EVENT20
   auctions, one anchor per month; PRE20p = the 5 sessions before that tdom.
   y ~ PREany + POST + PREany:POST + tdom FE, cluster by month.
   The DiD coefficient is PREany:POST. Bar: |t| > 2.5 AND the correct sign
   (negative = concession, i.e. long duration underperforms into the auction).

PLACEBO LADDER (run before filing, construction stated): re-run SPEC B with the
   anchor moved to every tdom from 3 to 20. If the true-anchor DiD does not sit in
   the tail of that distribution, the effect is a calendar artefact, not an auction.

ROBUSTNESS declared now: EDV-SHY as a second instrument (EDV from 2008-01-29);
   the 30y-only PRE window as a within-post comparison.

## WHAT WOULD MAKE ME CALL IT ALIVE
SPEC B DiD negative, |t| > 2.5, AND outside the 5th percentile of the 18-anchor
placebo ladder, AND same sign on EDV-SHY. Anything less = the resurrection path
is closed.
