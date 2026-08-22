# PM decision memo — the measurement trading programme

**Filed verbatim by the CTO chair (Fable) 2026-08-22, from the pm seat's
dispatch on desk request `5b6b37bd`. Run `run-pm-programme` on the desk
carries the twelve recommendations; the seat's STATE is appended to
`.claude/state/pm.md`. Chair verification notes at the end, marked.**

**Read stamp**: endpoints pulled 2026-08-22T04:51–05:06Z. Spine healthy (964
events chained). Venue CLOSED — weekend; next open 2026-08-24T09:30 ET, so the
earliest programme fill is Monday.

## TL;DR

1. The programme is worth running, but the number it is meant to produce is
   currently unreachable for the part of the market where our cost assumption
   is most likely wrong — because the fund measures fills against the *last
   trade*, not the mid, and that alone inflates the sample size needed by
   roughly the square of the cost.
2. Fix one thing first and the whole programme gets about ten times cheaper:
   record the bid and the ask at the moment we submit. Without it, the cheap
   end of the market needs about twelve trades; the expensive end needs about
   four hundred, which we will never do.
3. The design: one small $150 position passed through the book like a baton,
   two measured fills every session, no same-day round trips, a written
   tuition cap of $40, and a stop rule that ends the programme when the number
   is precise enough rather than when someone forgets it.
4. Two things must land before the first trade, both already on the desk: the
   cost reader must stop trusting an order's self-declared venue label (R23),
   and stop silently hiding the newest fills (R24). Also the broker and the
   book disagree on ten of eleven symbols — that blocks the automatic exits
   dated 2026-09-08 and needs the CEO's click either way.
5. New exception nobody flagged: all three live sleeves — 48.6% of the fund —
   are registered "draft", invisible to three of the fund's own monitoring
   readers.

## The finding that decides the whole design

`pipeline.py:218` captures `arrival` from `AlpacaConnector.quote()`, which is
`get_stock_latest_trade` (`alpaca.py:136-140`), cached up to 5 seconds
(`alpaca.py:84`). `execution_bps = fill − arrival` (`tca.py:190`). **So
`execution_bps` is fill-minus-last-print, not fill-minus-mid.** Under
symmetric flow the last print sits at bid or ask with roughly equal
probability; for a marketable order against half-spread `h`, the recorded
observation is ≈0 or ≈2h — an estimator whose sd ≈ the very half-spread it
estimates. Required n ≈ (1.96·h)²:

| True half-spread `h` | ≈ price at a 1-tick spread | Fills for ±1.0 bp @95% |
|---|---|---|
| 0.5 bps | $100 | 2 |
| 1.5 | $33 | 11 |
| 3.0 | $17 | 36 |
| 5.0 | $10 | 97 |
| 10.0 | $5 | **385** |

With bid/ask captured at submit (R32), the estimand becomes the dimensionless
*fraction of the quoted half-spread paid* (residual ~0.2 bps), and the
half-spread itself becomes readable for free, on every name, with no trading.

## The honest sample today

Of 10 "informative" fills, 5 rested 4,466–4,707s (premarket submit → opening
auction) and measure overnight drift. The honest pool is **n=3** (NVDA −1.32,
XLE +1.62, SPY −0.57): mean −0.088, sd 1.528, CI [−3.88, +3.71] — containing
both 0 and 5. All three from ONE session, its first 12 minutes, on
high-priced names: open-biased, single-session, top-of-price-distribution.
The upper 95% bound on σ at n=3 is 9.61 bps. **The circulating 1.96 bps (n=6)
figure is a post-hoc trim and must never be quoted as a fund estimate.**

## Tiers: price, not ADV

At $150 notional we are 0.00006–0.00009% of ADV (impact unmeasurable; ADV
spans 1.5× across the 200-name hunting ground) while the mechanical tick
floor — $0.005/price — spans **1,400×** (0.008–11.26 bps). The median name's
floor is 0.57 bps against a 5.0 assumption; **9 of 200 names have a floor
above 5.0 on their own** (OPEN 11.3, KEEL 10.8, SNAP 10.3, ACHR 9.5, RIG 9.4,
AUR 7.9, SOUN 7.4, BB 5.6, OWL 5.2). Pre-registered tiers: **T1 ≥$100, T2
$25–100, T3 <$25**, balanced on side and session slot (OPEN/MID/CLOSE),
because every honest observation we own sits in the widest-spread window of
the day. Stated in advance: **T3 is expected to end UNRESOLVED unless R32
lands.**

## Structure: the baton, because PDT binds

`/fund/compliance`: PDT applies, **3 day-trades remaining per 7 sessions**
(`compliance.py:59/64/69`; broker equity $2,012 vs the $25k threshold). A
pair-each-entry-with-exit design caps at 6 observations/week and burns the
whole budget. **The baton: each session, sell the position bought last
session, then buy today's sample — two informative fills per session, exactly
one open programme position, zero day trades ever.** Notional $150 (matches
the book's own trade size; all risk limits cleared; the binding constraint is
gross — already 0.55pp OVER the throttle target, so every programme deploy is
a written throttle excursion, flagged as such). Inclusion rule:
`submit_to_fill_s ≤ 60`; slower fills are labelled RESTED and excluded.

## Stopping rule and tuition

**Stop when the 95% t-interval half-width ≤ 1.0 bps per tier** — the fund's
own pre-existing materiality band (`costassumption.py:68`), not a number
invented for the programme. Anti-peeking: test only at n=12/16/20/26/34/44;
floor 12, ceiling 44 per tier; unconverged tiers report UNRESOLVED, never
extrapolated. Replacing `DEFAULT_SLIPPAGE_BPS` additionally keeps the pooled
n≥20 bar (`costassumption.py:41`). **Tuition cap: $40 cumulative realised
loss, hard stop to the CEO** — expected spread cost $2.67 over 16 round
trips; 2σ market-risk drag ≈ $31 (measured tier vols: T1 41.5%, T2 31.7%, T3
67.6% annualised). A breach means the design is wrong, not bad luck.
Programme trades are never scored as investments.

## Gates, in strict order, before any collection

1. **R23** — `tca.py:212` must prefer the SUBMITTED venue leg (verified again:
   DBA order `17d64dcd` reads Proposed=alpaca / Submitted=paper /
   Filled=alpaca, while its SPY sibling says paper on all three legs).
2. **R24** — `/fund/tca`'s limit is an event limit, oldest-first: 20 orders by
   default vs 22 at `limit=5000`, headline 5.56→4.95; the hidden fraction
   grows daily.
3. **R35 (new)** — an immediacy filter in `summarise()`: nothing reads
   `submit_to_fill_s` today, so the programme's inclusion rule is
   unenforceable by the instrument.
4. **R15-reopened** — the venue must route for real: the one CEO-authorised
   experimental deployment filled on the paper connector.

R32 (bid/ask at submit) is NOT a gate on starting — it IS the gate on T3 ever
converging.

## The recommendations (full text on the desk as run-pm-programme)

- **R25** stopping rule (ceo) · **R26** regime split pre-registered as
  `regime.turbulence.percentile ≥ 80` at proposal time, and the same click
  DECLINES any post-hoc trim (ceo) · **R27** price tiers not ADV (ceo) ·
  **R28** $150 notional, one open position; CTO must confirm venue minimums
  against the venue (ceo) · **R29** the baton (ceo) · **R30** optional
  accelerator: ≤3 intraday round trips per 7 sessions, T3 only — consumes the
  entire PDT budget (ceo, separate click) · **R31** $40 tuition cap (ceo) ·
  **R32** bid/ask on OrderSubmitted, estimand through the mid — ranked ABOVE
  the validator's quote-at-fill (chair) · **R33** decide the 2026-09-08
  TLT/DBC exits NOW as a standing instruction, $501.58, envelope v4 will
  refuse them unsynced (ceo, due 2026-09-08, hard) · **R34** promote the
  three live sleeves out of `draft` or write down why 48.63% of NAV is
  invisible to three readers (chair) · **R35** immediacy filter (chair) ·
  **R36** register `DEFAULT_SLIPPAGE_BPS` as a judgement call, sequenced
  behind the evaluability fix (chair).

## The challenge

Against Grace's D4 (n≥27) — direction neutral: replaces a fixed count with a
rule stricter in two tiers and honest about a third being unreachable. New
evidence: 27 derives from a blended sd (35.35) dominated by two auction fills
the immediacy rule removes by construction; required n is a property of the
INSTRUMENT (last-trade benchmark), not the programme. Proposed instead: the
per-tier precision bound, with the existing pooled 20 governing the act that
moves money. Not asking to override D4 — asking that it not be locked before
R32 is decided.

## What the seat did not look at

Anything on the web (venue minimums NOT verified — observed floor in our log
is $40.49; the CTO confirms against the venue); `nav_strike` (UNOBSERVED,
fourth consecutive review); the five unevaluable exit rules beyond confirming
they sit on flat legacy symbols; gate propagation of a slippage change;
per-name spread data (none exists — `Quote` has no bid/ask field, which is
R32); what the $1,166 of orphan broker holdings become on reconciliation.

---

# CHAIR VERIFICATION — added by the CTO, not part of the seat's memo

Spot-verified before filing: `alpaca.py:136-140` (`get_stock_latest_trade` as
the arrival source) and `:84` (TTL cache) — the memo's central mechanism is
line-exact. `compliance.py` PDT constants and `/fund/compliance
pdt.remaining: 3` — confirmed. `tca.py:212` venue preference and the DBA
order's three-legged label contradiction — confirmed earlier today by the
validator independently; two seats now agree line-exact. The n=3 honest pool
matches the validator's independent derivation to three decimals.

**Chair note on convergence**: three seats (validator, CFO, PM) have now
converged on the same instrument from three axes — dispersion, allocation,
design — and the PM's contribution is the only one that changes the SHAPE of
the fix (quote-at-SUBMIT over quote-at-fill, mid as benchmark). The
executive-table pattern produced a real answer here: Grace's D4, the PM's
challenge to it, and the validator's audit reach the CEO together, with the
disagreement named and the evidence attached.
