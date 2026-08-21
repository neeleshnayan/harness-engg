# Analyst funnel cycle 3 — item 5.02 measured dead, and a ~44%/yr phantom factor in our own price history

**Filed VERBATIM by the co-CTO chair, 2026-08-22, from the analyst dispatch
output. Not edited. STATUS: the phantom-factor finding is VERIFIED by the
chair independently (see the verification note below); the 5.02 verdict and
the entry-14 groundwork are recorded as MEASUREMENTS and are never citable
as proposals.**

## Chair verification, performed before any action was taken

- **TENX**: `GET /fund/marketdata/bars?symbol=TENX&start_date=2020-06-01&end_date=2020-12-31`
  returns 149 bars, `closes[0] = 2320.0` for 2020-06-01, and a 2020 high of
  3168.0 — for a sub-$2 biotech. Confirms cause (a), today-anchored split
  adjustment. The response also carries `adjusted: None` and
  `adjustment: None`: the payload does not name its own anchor.
- **Attrition**: re-counted from the cached 5-year bar set — **203 of 203
  symbols have a last bar of 2026-08-20 or 2026-08-21.** This is STARKER
  than the analyst reported ("0 of 200 before 2026-08-18"): every single
  name in the universe is alive today. Confirms cause (b), survivorship.
- Both causes stand. The finding is real.

## What the chair did with it

1. The no-price-level-sorting rule is IN FORCE and written into
   `.claude/state/mechanism.md`, `quant.md` and `validator.md`.
2. Builder ticket `7032a0fd` — split events, nominal-price view, name the
   anchor in the bar payload.
3. Builder ticket `6aadd330` — expose `accepted_at` / `period` / `items` on
   `GET /fund/research/observations`, and correct the API card.
4. **The gate-blindness half was deliberately NOT injected into gate v5
   round 5, which is in flight.** Adding a fifth ground mid-round is exactly
   how round 4 produced four grounds instead of one. Recorded as a round-6
   input instead.
5. The universe fence is RECOMMENDED to the CEO, not adopted silently — it
   invokes the Clean Field Rule's fence clause and moves the reference frame
   that future work is judged against, which guard rail 5 puts on the
   approval channel.

---

## PROVENANCE NOTE (chair)

The dispatch's task output file (`tasks/afc6a5c24f95cc77a.output`) was written
**0 bytes**. The report below is transcribed by the co-CTO chair from the run
notification, which carried the full text inline. Every number in the two
sections the chair independently verified (TENX, attrition) is confirmed
against the live endpoint and the cached bar set; the remaining numbers are
the analyst's own and are recorded as reported. A scan of the tasks directory
shows many 0-byte output files, so this is a harness defect, not a one-off —
filed separately.

---

# 1. 8-K ITEM 5.02 OFFICER-DEPARTURE DRIFT — MEASURED, DEAD

**Recorded as a MEASUREMENT. Never citable as a proposal.** Ask 909c316c, CEO-approved.

## 1.1 Point-in-time and timestamp discipline

Raw `acceptanceDateTime` hour histogram, n=12,164 8-K filings, 201 tickers:

```
 00: 102  01:  93  02:  32  03:   0  04:   0  05:   0
 06:   0  07:   0  08:   0  09:   0  10: 480  11: 986
 12:1308  13: 831  14: 260  15:  97  16:  99  17: 117
 18: 107  19: 108  20:4025  21:2830  22: 547  23: 142
```

Raw hours 03–09 are empty. EDGAR accepts 06:00–22:00 ET. Read as UTC: raw 10 =
06:00 ET (open), raw 02 = 22:00 ET (close), raw 03 = 23:00 ET (shut). Read as ET
it does not fit at all. **Raw is UTC; ET = raw − 4h; store unshifted.** Agrees
with `ClarkHarness/app/fund/edgar.py:79-98` (builder's n=30,732 roll-over test).
The analyst's own cycle-2 memory prose ("acceptanceDateTime IS ET") is **wrong
and has been struck**; its cycle-2 *code* already subtracted 4h and was correct,
so entry 8's numbers do not need re-running.

Entry rule: **reaction date R = first session at/after acceptance (post-16:00 ET
→ next session); entry at the OPEN of R+1.** Hand-verified end to end, SRPT
accession `0001193125-26-316995`, filed 2026-07-27 → R=2026-07-27, E=2026-07-28:
entry open $15.74, exit close 2026-08-03 $15.88, stock +0.89%, excess −1.62%
after SPY.

## 1.2 The population

n=2,241 events (2,254 raw, 13 lost to bar alignment), 198 tickers, **1,105
distinct reaction dates**, 2021-01-04 → 2026-08-19. Even by year
(404/384/397/396/400/260). 69.7% accepted post-close, 21.8% pre-open.
Reaction-day AR mean −35bp, median −27bp.

EDGAR's `items` field carries **no sub-letter codes** — verified: no `5.02a` or
`5.02(` anywhere across all 12,164 8-Ks. "CFO resigns abruptly" and "board
elects a new director" are the same code. Separating them needs the filing text.

## 1.3 The effect, clustered — it survives, unlike item 2.02

| N | naive cross-sectional | clustered by reaction date |
|---|---|---|
| 1 | −11.4bp t=−1.80 | −9.2bp t=−1.19 (c=1105) |
| 3 | −17.7bp t=−1.47 | −15.4bp t=−1.14 |
| **5** | **−31.7bp t=−1.98** | **−37.6bp t=−1.99** (c=1101) |
| 10 | −32.2bp t=−1.28 | −36.9bp t=−1.27 |
| 20 | −49.1bp t=−1.59 | −52.1bp t=−1.47 |
| 40 | +89.9bp t=+0.96 | +52.6bp t=+0.67 |

Genuinely different from entry 8, where clustering collapsed t from 2.92 to 0.64.
Here the clustered t is *marginally larger*. 1,105 clusters over 2,241 events.

**Sub-period:** 2021-2023 N5 −42.8bp t=−1.89; 2024-2026 N5 −31.8bp t=−1.02. Same
sign, same order of magnitude, neither half individually significant. Not a
one-year artifact (2023 strongest, N20 −199bp t=−2.81; 2022 and 2025 also
negative at N5).

## 1.4 The benchmark decides the verdict

| benchmark | N1 | N3 | N5 | N10 | N20 |
|---|---|---|---|---|---|
| vs SPY | −12.6 (t−1.59) | −18.8 (t−1.38) | −41.2 (**t−2.16**) | −40.4 (t−1.38) | −55.2 (t−1.56) |
| vs IWM (small-cap) | −11.6 (t−1.48) | −11.7 (t−0.89) | −26.9 (t−1.47) | −13.4 (t−0.48) | **−3.4 (t−0.10)** |
| vs EW universe | −14.5 (t−1.87) | −21.2 (t−1.62) | −42.1 (**t−2.33**) | −46.4 (t−1.67) | −71.9 (**t−2.14**) |

Against IWM the 20-day effect is **exactly zero**. Companies filing 8-K 5.02 are
small caps; SPY is the wrong benchmark for them. **Any |t|>2 here is a benchmark
choice, not a finding.** Universe context: EW universe +24.77%/yr vs SPY +17.58%
vs IWM +15.97% over 2020-06..2026-08.

## 1.5 The tradeability test kills it

Calendar-time portfolio, PIT, short the 5.02 names / long the EW universe, entry
at open of R+1, 5bps/side:

```
  N   days   avgN   ann.net%   vol%     IR       t   ann.gross%
  3   1397    4.8      4.69   28.63   0.16    0.39      13.09
  5   1412    7.9      5.89   21.60   0.27    0.65      10.93
 10   1413   15.8      1.31   14.55   0.09    0.21       3.83
 20   1413   31.5      4.69   10.23   0.46    1.09       5.95
```

N=5 by year: 2021 −8.70%, 2022 +9.26%, 2023 +7.74%, 2024 +2.14%, 2025 +28.84%,
2026 −9.58%. Cumulative +22.0% with a **−22.9% max drawdown** — one year (2025)
carries the whole result and both recent partial years are negative.

Beta decomposition of the raw short-leg basket (n=1,412 days): **beta_SPY 0.09,
beta_IWM 0.96, alpha −3.99%/yr, t(alpha)=−0.42.** The basket *is* the small-cap
index. There is no alpha to short.

Event t=−2.33, calendar-time t=+0.65. The portfolio holds 7.9 names at a time, so
idiosyncratic variance eats the signal. At the $500 alpha sleeve that is **~$63
per position across eight simultaneous short positions in small caps**, with
borrow cost entirely unmeasured on this desk and no short capability in the
harness.

## 1.6 Conditioning — one apparent survivor, killed by its own placebo

All clustered vs EW universe. `5.02` alone (n=1,299) N5 −32.7bp t=−1.56;
`5.02+2.02` (n=137) +11bp t=0.13; `5.02` bundled with something other than
earnings (n=805) N3 −57.3bp t=−2.82, N5 −72.5bp t=−2.51.

The sharpest cut was **`5.02+5.07`** (officer change filed with annual-meeting
vote results, n=211): N5 −122.7bp t=−2.51, N10 −215.8bp **t=−3.10**; 2024-2026
subset N10 −350.8bp t=−3.27. Killed three ways:

- **Placebo R−120** (same tickers, event-independent dates): N3 −86.3bp t=−2.37,
  N20 −222.6bp t=−2.52. The control shows the same thing.
- **`5.07` without `5.02`** (n=906): same sign throughout — it is the annual
  meeting, not the officer.
- **Calendar-time**: N5 +24.27% ann but **44.70% vol, IR 0.54, t=0.72, 2.4 names
  held**. N20 −0.85%, t=−0.03.

Multiple-testing honesty: ~30 condition×horizon cells across three benchmarks.
Two or three |t|>2 are expected by chance. Nothing clears that bar after its
placebo.

## 1.7 VERDICT: DEAD. Revival conditions

**8-K item 5.02 officer-departure drift is not a tradeable edge in this
universe.** Not because the cross-sectional effect is absent — it is present,
clustered, and stable in sign across both halves — but because (a) it vanishes
against the correct small-cap benchmark at N20, (b) it is 96% IWM beta with
negative alpha, and (c) an 8-name portfolio cannot harvest 40bp.

Revive only on **new data**:

1. **Text-conditioned departures.** The item code cannot separate a forced CFO
   exit from a routine director election. `5.02` substance sits in the 8-K
   **body** (`primaryDocument`), so unlike item 2.02 it is **already reachable**
   and the EX-99.1 fix is not the blocker. If a text classifier isolates
   involuntary CEO/CFO departures (plausibly ~10-15% of 2,241), re-run.
2. **A universe wide enough to hold ≥30 names at once.** The 201-name corpus caps
   the portfolio at ~8 names. A breadth constraint, not a signal constraint.
3. Do NOT revive on a benchmark change or a new sub-period. Both were tried.

---

# 2. THE FINDING THAT MATTERS MORE — OUR PRICE HISTORY CARRIES A ~44%/yr PHANTOM FACTOR

Came out of the 5.02 control tests. A **confirmed defect in the fund's own
measurement instrument**, weight-bearing for every future study.

## 2.1 What was seen

Sorting 5.02 events on prior-close price level produced the best t-stats of the
dispatch: highest-price quintile N5 −94.5bp t=−3.60, N20 −208.2bp t=−3.75 vs
SPY; lowest-price quintile +294.6bp t=+2.80 at N20. A "short expensive stocks
after an officer leaves" strategy.

**It is not about officers, or about events at all.** Placebo, same tickers, R
shifted by an event-independent −120 sessions:

```
                        N5                N10               N20
REAL 5.02   HIGHpx   -86.3(t-3.26)    -96.5(t-2.03)   -197.7(t-3.60)
PLACEBO-120 HIGHpx   -54.7(t-2.14)   -110.5(t-3.07)   -186.6(t-3.46)
PLACEBO+120 HIGHpx   -61.7(t-2.29)    -43.3(t-1.07)   -105.0(t-1.79)
CTRL 8-K non-5.02    -29.2(t-1.49)    -45.1(t-1.27)   -109.2(t-2.37)
```

## 2.2 Sized as a factor

Monthly-rebalanced, equal-weight price quintiles over the 200-name universe,
1,528 sessions:

| sort variable | LOW ann | HIGH ann | LOW−HIGH | vol | t |
|---|---|---|---|---|---|
| **adjusted close (our feed)** | 57.07% | 7.39% | **+49.68%** | 21.51% | **5.69** |
| **nominal close (splits undone)** | 52.34% | 8.50% | **+43.84%** | 23.39% | **4.62** |

Positive every single year: adjusted 2020 +67%, 2021 +40%, 2022 +33%, 2023 +24%,
2024 +54%, 2025 +86%, 2026 +55%.

## 2.3 Two distinct causes, both verified

**(a) Split back-adjustment is a look-ahead in any price-LEVEL sort.** Our feed's
"close" is anchored to today, not to the date. `marketdata.py:240-242` selects
Yahoo's `adjclose`; `:269` computes `factor = adjclose / raw_close` and applies
it to OHLC — the adjustment is real and applied backward from today.

- Our feed reports **TENX closing at $2,320.00 on 2020-06-01**. Yahoo split
  events for TENX: **1:20 on 2023-01-05 and 1:80 on 2024-01-03** — a 1,600×
  reverse-split factor. Actual 2020 price ≈ $1.45.
- Requesting `end_date=2020-12-31` returns the *same* $2,320.00 — the anchor does
  not move with the window. There is no point-in-time price view:
  `as_of=2020-12-31` returns "nothing archived for TENX on or before 2020-12-31".
- Yahoo's `quote.close` is **also** split-adjusted (factor 1.000000 measured on
  TENX/LOAR/CYTK/DYN), so exposing the raw field is *not* the fix — the split
  **events** are (`&events=div,split`, `numerator`/`denominator`).
- Universe-wide: 21/202 names split 2020-2026 — 12 reverse (BKKT, BKSY, COGT,
  GSAT, IVR, KNTK, SBET, SLG, SVC, TENX, VOR, VRDN), 10 forward. **17 of 182
  names sit in a different price quintile** under nominal vs adjusted on a single
  sample date (2022-06-30).

**(b) Survivorship in the universe itself — the larger half.** Undoing splits
removes only ~6 of the 49.7 points. The residual 43.84% (t=4.62) is universe
construction:

- **0 of 200 names have a last bar before 2026-08-18.** Zero delistings, zero
  bankruptcies, zero going-private, across six years of small/mid caps.
- 162/200 have bars from 2020-06-05; the other 38 were added as they listed. The
  universe was assembled forward from a today-snapshot.
- `GET /fund/universe/hunting-ground` confirms the construction:
  `"operating_only": true`, `"identity_source": "polygon reference data"`,
  `"excluded": {"not_operating": 0, "unclassified": 2402, ...}` — membership is
  conditioned on *currently* being an operating company.

No clean external delisting base rate could be sourced (the one candidate
returned HTTP 429; an unverified number will not be cited). **Reported absent.**
The internal measurement — zero attrition in 200 names over six years — is
sufficient on its own.

## 2.4 Why this is worth more than the 5.02 kill

**The gate cannot catch it.** Walk-forward slices time; every fold reads the same
today-anchored, survivor-only series. A candidate that sorts on price level,
market cap, or dollar volume would present ~+44%/yr, IR ~1.9, positive in every
fold, and pass. At the $500 alpha sleeve that is a phantom +$220/yr of "edge" and
a real sleeve at risk.

**What is safe and what is not, on this feed:**

- SAFE: anything built from **returns** (momentum, event AR, reversal,
  volatility). Returns are adjustment-invariant — that is what adjustment is
  *for*. The 5.02 study used only returns; its conclusions stand.
- UNSAFE without a fix: any cross-sectional sort on **price level, market cap,
  dollar volume, or share count**, and any comparison of a **filing's nominal
  dollar figure** to our closes.
- Long-horizon absolute-return studies on this universe are inflated by
  survivorship regardless of the sort variable.

---

# 3. ENTRY 14 — SECONDARY-OFFERING PLACEMENT DISCOUNTS: EVIDENCE GROUNDWORK

Groundwork only. **No proposal is made and none is implied** — the mechanism owns
that stage.

## (a) The population, counted

Full EDGAR pull, 201 tickers, all forms since 2021-01-01: **91,795 filings
cached** (forms: 4→49,409, 8-K→12,166, 144→6,178, 10-Q→3,198 …). Equity-takedown
prospectus supplements:

**537 filings — 424B5 (422), 424B7 (75), 424B4 (38), 424B1 (2) — across 108 of
201 tickers, 2021-2026.** By year: 140/46/68/106/119/58. 63 tickers have ≥3.
**517/537 have usable price history.**

Acceptance timing is textbook overnight-marketed: **368/537 (69%) accepted at or
after 16:00 ET**, 93 (17%) pre-open.

Classified by regex on cover text (classification accuracy not hand-validated at
scale — stated as a caveat):

| class | n | tickers | offer price extracted by regex |
|---|---|---|---|
| DEBT | 208 | 50 | 25 (12%) |
| **EQUITY** | **130** | **51** | **51 (39%)** |
| PREFERRED | 114 | 26 | 23 (20%) |
| ATM | 62 | 27 | 13 (21%) |
| UNIT/WARRANT | 20 | 8 | 7 (35%) |
| fetch error | 3 | 3 | — |

**Only 24% of the raw 537 are equity placements.** Of the 130 EQUITY rows, **31
are 424B4 — IPO prospectuses**, which have no pre-deal market price and must be
excluded (they generated the three most extreme "discounts": LOAR −43.7%, ABSI
−30.1%, and the +21.6%/+31.8% "premiums" on OSCR and DYN). **Clean follow-on
population ≈ 99 events over 5.6 years across ~45 tickers ≈ 18/year.**

**8-K item 8.01 is a poor primary trigger**: 2,596 filings, 194 tickers — but
only **212 (8.2%) fall within ±2 calendar days of a 424B* by the same issuer.**
Use the 424B* as the trigger and 8.01 only as corroboration.

## (b) Is the discount OBSERVABLE? — YES, with two named blockers

The offer price is on the cover in standard form (`public offering price of
$X.XX per share`, or a `Price to public … $X.XX` table). Regex hit 51/130.

1. **The denominator was broken.** Comparing a filing's *nominal* offer price to
   our *back-adjusted* close is invalid — the same defect as §2. Fixed inside
   this study by reconstructing nominal closes from Yahoo split events.
2. **Naive regex is not accurate enough for a 3-4% effect.** It returned $0.0001
   on BRUN and RDNT (par value) and $19.23 on CYTK 2021-07-19 where the actual
   deal two days later priced at $27.50. Extraction error and effect size are the
   same order.

**Does the EX-99.1 fix help here? No — and that is a useful negative.** A 424B5
*is* the primary document; there is no exhibit indirection. That defect remains
relevant to item 2.02 and, by the same argument, is *not* a blocker for item
5.02 either.

**The local-model split paid here, measured.** On the 74 EQUITY 424B5/B7 rows
where regex found no price, `qwen3.5:9b` (temperature 0, think=false, 9k-char
cover text) on a sample of 20 recovered **8 prices, every one verified verbatim
against the source text**, at **1.4 s/doc**. The nulls were correct, not lazy:
ANIP 2023-05-11 null → 05-12 $39.50; AXGN 01-21 null → 01-23 $31.00; BFLY 01-29
null → 01-30 $3.15 — preliminary supplement, then priced supplement.
Extrapolated, the full 74 would take the clean sample from 24 to ~54. **No local
model produced any number in this report** — all t-statistics, portfolios and
betas are deterministic Python.

## (c) First-look magnitude

Method: EQUITY-classified **424B5/424B7 only** (IPO prospectuses removed),
regex-extracted offer price, point-in-time nominal reference close — D's close if
accepted ≥16:00 ET, else D−1's close — deduplicated on (ticker, date, price).

**n = 24 events, 14 tickers, 2021-2026.**

- **median discount −3.18%, mean −5.48%, sd 7.80%, t = −3.44 vs zero**
- **19 of 24 (79%) priced below the prior close**
- distribution: <−15%: 3 | −15..−8: 3 | −8..−4: 5 | −4..−1: 7 | −1..0: 1 | ≥0: 5

Externally corroborated: the SEO literature puts the average discount at about 3%
relative to the prior day's market price, and notes that most seasoned equity
offerings in 2009-2014 were announced and issued overnight — matching the
measured 69% post-close acceptance. Sources:
[ScienceDirect, SEO overview](https://www.sciencedirect.com/topics/economics-econometrics-and-finance/seasoned-equity-offering),
[Gustafson, "Price Pressure and Overnight Seasoned Equity Offerings", SSRN](https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID2867516_code1629977.pdf?abstractid=1945014).

**The secondary market shows nothing.** Entry at the first open after the 424B*,
vs EW universe: N1 −25.7bp t=−0.38; N3 −87.4bp t=−0.66; N5 −13.9bp t=−0.10; N10
+47.1bp t=+0.31; N20 +125.0bp t=+0.39. Overnight gap prior-close→next-open: mean
**+0.28%**, median +0.18% — the market does **not** gap down to the offer price.
Deepest-discount half vs shallowest half at N5: +167bp vs −195bp (n=12 vs 12) — a
362bp spread, suggestive, nowhere near significant, one cut among many.

**The structural fact the mechanism needs before proposing:** the ~3% discount is
compensation paid to the **allocated placement buyer**. This fund cannot be
allocated. The tradeable residue is the secondary-market drift, measured at
|t| ≤ 0.66 on n=24. Capacity is the second wall: ~4.3 clean events/year (~10/year
if extraction is completed), so at a $500 sleeve the strategy transacts a few
hundred dollars a year and a 3% edge on it is worth low tens of dollars.

**Verdict for the mechanism: the population is MEASURED and the discount is
MEASURABLE — the edge is not ours to collect at this size.** A saved cycle,
delivered before the proposal rather than after.

---

# 4. WHAT COULD NOT BE CHECKED

- **Involuntary vs routine 5.02** — the decisive conditioning variable, requiring
  text classification of 2,241 8-K bodies. Not attempted; ~50 min of local qwen
  at the measured 1.4 s/doc.
- **Borrow cost and short availability** on small caps. Entirely unmeasured on
  this desk. The 5.02 calendar-time result is gross of it.
- **`fund_observations.accepted_at` / `period` / `items`** — the brief says these
  are backfilled across all 1,035 rows, but `GET /fund/research/observations`
  returns **none of the three fields**. EDGAR's submissions API was used directly
  instead. **API-card defect: the response model does not expose the backfilled
  columns.** Reported, not worked around silently.
- **External delisting base rate** — HTTP 429, no verified source. Absent, not
  estimated.
- **Classification accuracy of the 537-row regex classifier** at scale
  (hand-audited on the 39-row discount table only).
- **Whether 424B classification errors are directional.** If DEBT/ATM
  misclassification is asymmetric, the 130 EQUITY count is biased in an unknown
  direction.
- **Point-in-time universe.** No survivor-inclusive historical membership exists
  in the fund. Every §2 magnitude is conditional on that absence.

---

# 5. TWO ENGINEERING TICKETS

1. **Expose split events and a nominal-price view in `marketdata.py`.**
   `&events=div,split` returns `numerator`/`denominator` per split;
   `nominal(t) = split_adjusted(t) × Π_{splits after t}(num/den)`. Verified
   working on 202/202 symbols in ~2 minutes. Until it lands, **no strategy may
   sort on price level, market cap, dollar volume, or compare a filing's dollar
   figure to our closes.** Add a bar-payload flag naming the anchor, the way
   `adjusted`/`adjustment` already do at `marketdata.py:289-290`.
   → **FILED by the chair as `7032a0fd`.**
2. **Return `accepted_at`, `period`, `items` from
   `GET /fund/research/observations`.** Backfilled in the table, invisible at the
   API. → **FILED by the chair as `6aadd330`, with the card correction included.**

A third item is a judgement call for the chair, not a ticket: the ~44%/yr
survivorship inflation in the 200-name universe cannot be re-baselined (no
point-in-time membership exists), so under the CLEAN FIELD RULE's fence clause it
should be **fenced as a pre-instrument reference frame**, not laundered.
→ **The chair has routed this to the CEO rather than adopting it, because guard
rail 5 puts a frame change on the approval channel.**
