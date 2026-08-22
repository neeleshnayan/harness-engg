# Insider extension 2016q1–2020q4 — RESULT: UNSUPPORTIVE, the lead is retired

**Filed 2026-08-22 by the CTO chair (Fable) from the analyst's pre-registered
run. The specification was locked at `INSIDER_EXTENSION_PREREG_2026-08-22.md`
BEFORE the pull; this is the answer, called by the pre-registration's own
definitions. Findings-class: never edited. Full provenance on the 4TB store at
`Krypton/insider_ext_2016_2020/` — the deciding script is
`scripts/e5_main.py`, verbatim log beside it, and the c4 panel plus all eleven
adversary scripts were preserved there BEFORE any download.**

## The call

> **UNSUPPORTIVE.** PRIMARY (symbol join, the pre-reg literal): **+1.307%/yr,
> t_NW 1.69, placebo z 1.19, bootstrap t 1.73** — range t 1.2–1.7 against a
> prior of 1.6–2.1 and a pre-declared supportive bar of "materially above
> ~1.96, near 2.7". ROBUST (CIK join): +1.661%/yr, t_NW 2.05 — above 1.96 by
> 0.09, not "materially", **and its placebo z FELL (1.56 → 1.32) as the sample
> doubled**, failing the supportive test on the placebo leg outright.

Halves: 2016–2020 alone **+1.178%/yr, t 0.91** (and dropping the five most
influential names takes it to +0.318%, t 0.23); 2021–2026Q1 +2.125%, t 2.15.
Difference between halves: **t = 0.58 — not distinguishable**. The honest
claim is *"the extension DILUTES the estimate and cannot distinguish the
regimes"*, not "2021 was a fluke". Same volatility both halves, so this is an
effect-size drop, not a power problem: **the extension had the power to find
the 2021-era effect and did not find it.**

Integrity checks passed before any headline was believed: the adversary's
published +1.987%/t 1.96 reproduces to +1.981%/t 1.96 on the freshly built
10-year panel (panel-swap check — no difference below is plumbing), and one
2016 event was hand-verified end-to-end against EDGAR's own index page.

## What nobody could know before the pull — three findings bigger than the verdict

1. **The 10b5-1 checkbox (`AFF10B5ONE`) does not exist in the SEC bulk files
   before 2023** — schema-verified. Measured drop rates: 2021 0%, 2022 0%,
   2023 31.5%, 2024 49.5%, 2025 53.9%. **"Discretionary S" is a no-op for
   seven of the ten years**, so the extension added five years in which the
   mechanism story cannot be tested. Worse for the story (EXPLORATORY):
   "S all" scores +4.007% t 3.40 in 2021–26 against discretionary's +2.125% —
   **adding back the scheduled, uninformed plan sales makes the screen
   BETTER**, which is evidence against the informed-selling mechanism.
2. **The biggest number in the study is not the headline: excluding names in
   the 20 sessions BEFORE a filing yields −7.734%/yr at t_NW −8.93.**
   Insiders sell into strength; the pre-filing run-up is 4.7× the post-filing
   effect with the opposite sign. Consequence for every future event study
   here: **a "non-overlapping" date-shift placebo is not thereby NULL** —
   negative shifts averaged −2.63%, positive +0.67%, and one shift dominated
   the pooled sd. And **the placebo sd is 2.47× the Newey-West SE on a
   doubled window** — NW understates this statistic's uncertainty ~2.5×;
   anchor on the placebo z, which reads the effect nearer t 1.2–1.3.
3. **A live data defect in the shipped pipeline: `insider_parse.py` joins the
   universe on `ISSUERTRADINGSYMBOL`, and must join on CIK.** On 2016–2020
   the symbol join misses 4,106 rows of genuine universe companies filing
   under prior tickers (LUMN as CTL, CPAY as FLT through 2024, AZTA as BRKS,
   UPBD as RCII, OBDC as ORCC) and admits 1,048 rows of DIFFERENT companies
   holding recycled symbols (DYN was Dynegy, not Dyne Therapeutics). **The
   2021–2026 panel in current use inherits this unquantified.**

## Survivorship, now measured over ten years — the extension magnifies it

64 of 201 names were not trading at 2016-01-05, and **zero of 201 has a last
bar before 2026-08-20** — a small/mid-cap set with no delistings in ten and a
half years is today's reference data, not the market. EWU 2016–2026Q1
+20.23%/yr vs IWM +12.38%. Direction runs AGAINST the screen (stated in the
pre-reg), and the prohibition stands: no deployment claim without a
point-in-time universe.

## Deployability (exploratory; the pre-reg authorizes no proposal)

Mean 126.1 names held, 297%/yr one-way turnover, **$14.95 per position at
$1,885 NAV**, all gross. The adversary's book-size objection is confirmed over
the full window: even at t = 2.7 this shape is unfundable here. A fundable
version of this idea would have to be a concentrated short list.

## What would revive the line (and nothing less)

1. Parse `FOOTNOTES.tsv` (already on disk in all 41 ZIPs) to recover 10b5-1
   status pre-2023 — the only route to testing the discretionary story on the
   full window.
2. A point-in-time universe.
3. A concentrated construction (top-k by sale size / officer rank).

NOT on the list: a new benchmark, a new period, or a different N.

## Chair note

This is what the pre-registration was for. The firm's best-evidenced lead was
tested at double the sample against a bar it could not move after seeing the
data, and it did not clear it. **An honest negative at a cost of zero market
sessions and one overnight dispatch — leg 1 of the team metric, in service of
the money: the alpha sleeve does not deploy into a diluting effect.** The
resource discipline also held: one sequential worker, checkpointed, RAM
6.17 → 4.28 GB, zero failures — the morning's collapse was parallel streams,
not this workload.
