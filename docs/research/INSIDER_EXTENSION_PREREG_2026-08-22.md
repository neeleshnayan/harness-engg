# PRE-REGISTRATION — insider-exclusion screen, 2016q1–2020q4 extension

**Committed 2026-08-22 by the CTO chair (Fable), BEFORE any extension data is
pulled. CEO-authorized the same day ("yup", on the chair's overnight plan).
This is a findings-class document: never edited. If the specification below
turns out to be wrong, the correction is a new dated section that says so —
the original stands as what was promised.**

## Why a pre-registration exists at all

The adversary's blind review of the insider exclusion screen (2026-08-22)
KILLED the headline (+2.72%/yr, t_NW 2.66 — the screen sold at the close of
the filing day, and 86.8% of the panel's Form 4s were accepted at or after
16:00 ET that day) and found the underlying effect SURVIVES at **+1.99%/yr,
t_NW 1.96, honest range t 1.6–2.1**. Its cheapest decisive test: extend the
SEC bulk pull from 2021q1 back to 2016q1 — roughly doubling the sample — with
one condition it stated explicitly: **pre-register N and the event filter
BEFORE the pull**, because N=20 is currently a local peak on a 72-cell
specification surface whose t values run 0.09 to 3.20 and which is
non-monotone in hold length. An extension whose specification is chosen after
seeing the extended data is a second in-sample fit, not a test.

## The locked specification

Every parameter below is fixed now. The extension run reports THIS cell and
may report others only labelled as exploratory, never as the result.

1. **Event filter: discretionary S** — open-market sales excluding 10b5-1
   plan sales, exactly as the shipped screen defines it. NOT "S all", although
   "S all" scored higher in-sample (+3.88%, t 3.20) — the mechanism story is
   about discretionary information, and switching to the stronger cell now
   would be selection on the outcome.
2. **Hold length: N = 20 sessions.**
3. **Construction: long-only exclusion** — equal-weight the universe, exclude
   names with a qualifying filing within the last N sessions, measured as the
   difference against equal-weight-of-universe.
4. **Point-in-time rule: time-aware PIT, the adversary's corrected version.**
   A filing accepted before 15:45 ET exits at that day's close; a filing
   accepted at or after 15:45 ET exits at the OPEN of the next session (the
   name keeps the overnight leg). Acceptance timestamps from the EDGAR
   `accepted` field, converted to ET with DST handled. Unmatched accessions
   are treated as late (the conservative direction).
5. **Data: SEC bulk insider-transaction quarterly ZIPs, 2016q1–2020q4** — 20
   files through the existing `insider_parse.py` pipeline, joined to the same
   201-ticker universe. Output lands on the 4TB store
   (`//wsl.localhost/Ubuntu/mnt/wsl/PHYSICALDRIVE0p1/Krypton`), never in the
   session scratchpad.
6. **Statistics reported: all three, always together** — Newey-West t on the
   full 2016–2026 difference series; the date-shift placebo z using
   non-overlapping shifts that are multiples of N; a 63-day block bootstrap.
   The result is the RANGE, not the most flattering of the three.

## What the result means, declared in advance

- **Supportive**: the full-sample t lands materially above the current ~1.96
  (the adversary's back-of-envelope: near 2.7 if the effect is real and
  stable) with the placebo z and bootstrap agreeing in direction.
- **Unsupportive**: the extension dilutes the effect — full-sample t at or
  below the current level. That is a real answer and it retires the lead from
  "best lead" to "2021-era artifact until explained."
- **Either way, one caveat is permanent and pre-stated**: the universe is
  TODAY'S universe projected backwards — zero delisted names, 30 names that
  first traded after 2021-01-04 (which are simply absent from the early
  window, thinning it). The equal-weight universe returned +17.16%/yr against
  IWM's +8.67% over 2021–2026: a survivor set. **Differences against that
  benchmark are internally consistent; absolute numbers are not deployable
  claims. No deployment decision may cite this extension without a
  point-in-time universe being priced first.** Survivorship runs AGAINST an
  exclusion screen (the missing delistings are the collapses it would have
  dodged), so the bias direction is stated, not assumed flattering.

## What this pre-registration does NOT authorize

No deployment, no proposal, no gate submission. The extension is a
MEASUREMENT of an effect's stability. If supportive, the next step is a
mechanism proposal that prices the PIT-universe question and the book-size
constraint the adversary flagged (143 names at 578%/yr one-way turnover is
not fundable at $1,885 NAV — book size, not signal strength, is the binding
leg). That proposal goes through the full chain: adversary attack, belt, gate,
CEO click. No stage is skipped because the pre-registration exists.
