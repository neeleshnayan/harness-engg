# Dr. Mike Darwin — THE LEADS SHELF v2 (run-analyst-shelf2), 2026-08-23

**Filed by the chair at resolve; operative summary — the full report is
verbatim in run `run-analyst-shelf2`. Datasets RESCUED into the repo at
`data/research/` (they were session-scratchpad artifacts): the CPI/NFP
calendar + sourcing, the SEC dissemination lookup (118,294 rows), the E21
pre-registration. Zero containers, zero bulk extraction, host intact.**

## 1. E21 IS CLOSED — on its own pre-registered path, plus a defect in the bar itself

The 2020 20-year reintroduction is a genuine natural experiment (76
monthly auctions at a tdom slot empty since 2009) and it is NULL: PRE
coefficient −1.65 bp/day (t=−0.25) with day-of-month FE; DiD vs 2014–20
control −4.99 bp/day (t=−0.74), rank 6/18 in its own placebo ladder; null
across five control eras; the 30-year leg goes the WRONG way. Pipeline
validated first by reproducing Ed's own headline to three decimals.
**The bigger finding: the revival bar was UNREACHABLE** — the design's SE
is 6.63 bp/day, so |t|>2.5 needs 16.6 bp/day against a claimed effect of
8.83 (implied t=−1.33); the same machinery returns only t=−1.57 in the
era nobody disputes. **|t|>2.5 with tdom FE has never been achieved by
this family in any era.** CHALLENGE filed (TIGHTENS, on the CEO's desk):
every pre-registered revival/kill condition must state the MINIMUM
DETECTABLE EFFECT its own design delivers, beside the t-bar — a bar
nobody has powered is a trigger that can only return one answer.

## 2. THE CPI/NFP RELEASE CALENDAR — delivered, 1994-01 → 2026-11

`data/research/macro_release_dates_cpi_nfp.csv` (788 rows) + SOURCING doc.
Every past-dated row double-sourced (BLS schedule pages 1997–2026; BLS
archived-release indexes to 1994-02; all 68 pre-1997 releases opened and
their embargo lines read — 68/68 agree). **Four caveats that will bite:**
the BLS archive filename is a slug, not a release date (4 confirmed
disagreements; one 1:30 PM release in 788); **reference period 2025-10
does not exist for either series** (a 12-per-year loop fabricates an
event); duplicate reference-period labels exist in BLS's own index;
EMPSIT is Friday 379/394 while CPI spreads across four weekdays — pooling
without a day-of-week control mixes two calendar objects.

## 3. THE COMMENT-LETTER PILE — the headline is a LOOK-AHEAD DEFECT

**An SEC UPLOAD's EDGAR `filingDate` is the letter's authoring date,
back-dated — NOT the publication date.** Proven three ways (document
headers 143/181; acceptanceDateTime==filingDate 600/606; EDGAR's daily
dissemination index — the truth). Measured over 49,626 UPLOAD records
2020–26: **lag median 57 days, mean 103, p90 221, max 6,152; only 0.13%
within one day.** Cause: SEC policy releases correspondence "no earlier
than 20 business days following the completion of a filing review."
**Every one of the fund's 3,185 stored UPLOAD dates is the wrong date for
a price study.** Recovery instrument: the daily index, ~1.6 s/day,
checkpointed; the 2020–26 lookup is filed at
`data/research/sec_correspondence_dissemination_2020_2026.csv`.

**The corrected pilot is a measured null on our universe** (n=331, N20
−0.774% t=−0.80 vs the matched-date EW panel; severity splits
directionally right, none significant; the +60 placebo at N=20 is NOT
clean — carried). **Not tradeable as a basket at our size** (~100
events/yr ≈ 8 concurrent positions ≈ $235 each; the full population
needs ~700 names + a short leg). **The defensible form: a RISK FLAG on
names already held** — bundle size ≥2 and bundle span >180d are
computable on the dissemination day (the conversation-dump structure:
whole threads drop at once) and the worst pilot cell ran −3.56%/20d
(n=23, t=−1.61, directional not established). Four event-study designs
scoped with identification requirements and no-null controls (D1
conversation-dump severity; D2 topic-conditioned; D3 CORRESP-first
asymmetry; D4 the look-ahead itself as a calibration instrument — the
cheapest, both date sets exist).

What the pile contains (181 read): 36% closing letters with zero
comments; median 1 numbered comment; topics led by segment reporting /
revenue recognition / exec comp; going-concern 0, restatement 1. Method
lesson: a topic flag that hits 100% is a bug, never a finding (`VIE`
matched "review").

**Primary record: run `run-analyst-shelf2`; STATE + EVOLVE in
`.claude/state/analyst.md` and the seat file. Ed consumes this shelf in
batch #3 and reports consumed/rejected per lead.**
