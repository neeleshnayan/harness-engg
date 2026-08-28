# P1 — the ETH staking-wrapper premium

**Strategy dossier (pilot of the lifecycle design,
docs/design/STRATEGY_LIFECYCLE_2026-08-28.md). Assembled from the record;
every quote verbatim from the filed artifact it cites. Stages append; nothing
is rewritten.**

```
PROPOSED ✓ → REVIEWED ✓ → IMPLEMENTED ✓ → BELTED ✓ → DECIDED ✓ → SIZED ✓ → DEPLOYED … → LIVE ·
```

---

## PROPOSED — 2026-08-27 (Ed, mechanism batch 7)

**The claim**: holding Grayscale's Ethereum Mini Trust (NYSE "ETH", 0.15%
fee, stakes its holdings) delivers ~+1.9%/yr of total return over ETHA
(0.25%, does not stake) for identical ETH exposure. **The counterparty**:
holders of the unstaked wrapper, who donate the staking yield. **Claim
type**: premia (a better wrapper for the same exposure, judged on excess over
ETHA). Evidence at proposal: +1.86%/yr, 10 of 11 months positive.
Artifact: `docs/mechanism/ED_BATCH7_2026-08-27.md` (the batch's sole
survivor of five).

## REVIEWED — 2026-08-27 (adversary, blind)

**SURVIVED.** The attack went to the issuer's own books: coin-per-share from
SEC filings shows +1.51/+1.83/+1.98 %/yr accrual post-staking against a
+0.03% control — the premium is on the issuer's balance sheet, not in a
price artifact. Residual left open: F1 (the coin-per-share falsifier) was
orphaned by Grayscale's 2026-08-06 amendment paying rewards as cash
distributions; Ed replaces it with a declared-distributions falsifier, due
2026-09-05. Artifact: filed in `docs/reviews/` (batch review).

## IMPLEMENTED — 2026-08-28 (quant, dispatch #9)

`lean_workspace/algorithms/eth_wrapper_premium/main.py` (committed 8fe7eea1).
Hold the mini trust at 0.99 weight, benchmark ETHA — the excess IS the
measured claim. Declared interpretation choices in the file header; four
independent reproductions of the premium off the fund's own feed before any
code (pre-staking −0.107%/yr, post-staking +1.815%/yr, DiD +1.92%/yr).
Pre-registered container prediction: 10 of 11 quantities exact.
Artifact: `docs/quant/QUANT_P1_CRYPTOPROBE_2026-08-28.md`.

## BELTED — 2026-08-28 (candidate a39f301168fa, gate v5r4-premia)

**VERDICT: FAILED — 3 failures, verbatim** (luck 61.245% < 65 on the full
window; holdout retention −152%; 2 of 12 folds measurable vs 8 required).
**And the premia leg itself returned ZERO failures** (advantage +0.00654,
drawdown better than bar, gross under ceiling). On the post-staking window —
the only window where the mechanism exists (staking began 2025-10-06) —
**both substantive premia criteria pass: advantage +0.0202, luck 76.768% ≥
65** (container 9c13e2542206). The chair's and the seat's shared reading:
the failure is the WINDOW (301 of 526 sessions predate staking; the
consistency legs judge ether's falling price, not the wrapper spread). The
instrument cannot be walk-forwarded until ~3 years of history exist (~2027).

## DECIDED — 2026-08-28 (the CEO)

**PURSUED**, verbatim "yes on 1" (chat, morning), on the post-staking
evidence — an eyes-open judgement call on strong-but-short evidence, not a
gate certification; recorded on the desk (run-quant-p1-0828 rec 1, actor
ceo). Honest framing preserved from the belt stage: the gate said the window
is too young, and the decision consciously overrides on the mechanism
evidence.

## SIZED — 2026-08-28 (Stan, run-pm-review-0828)

**$75 (3.73% of NAV), funded from cash** — measured, not defaulted: funding
from a TLT trim gives identical book vol because TLT contributes no risk to
free. ETH measured on the fund's own feed (528 sessions): vol 71.03%
full-window (the 20-day reading is a two-year LOW — stops fitted on the full
window), maxDD −67.52%, worst session −22.05%. At $75 the book's vol goes
3.26%→4.57%, effective bets FALL 4.13→3.78 (low correlation does not
diversify at a 5:1 vol ratio), and ETH carries **37.5% of book risk on 7.5%
of invested capital**. **The expectancy stated plainly: the wrapper edge is
$1.43/yr against $50.64 of measured downside — the premium is the right
instrument, not the reason; the reason is crypto operational experience (the
2026-08-27 crypto-first amendment).** Exits specified: 30% stop (with the
overnight-gap limitation written in as an accepted risk), 2026-11-26
mandatory re-decision, and the wrapper's own falsifier (trailing 3-month
TOTAL-RETURN spread vs ETHA turns negative → re-underwrite as a naked ETH
bet).

## DEPLOYED — staged 2026-08-28, awaiting the CEO's click

Chair staging complete the same hour: venue tradability VERIFIED (ETH
tradable + fractionable at Alpaca, ARCA, active); live strategy registered
(`707b79d0-a2a8-4147-9b62-3823dc5daa81`); **all three exits committed BEFORE
any proposal exists** (event log, actor neelesh-via-cto). The $75 BUY
(3.171247 shares at the $23.65 mark) is ready to propose on the CEO's word —
the proposal passes the pre-trade risk gate and lands on his desk as one
click. Monitoring commitment carried: TOTAL RETURN vs ETHA; Ed's replacement
falsifier due 2026-09-05.

## LIVE — not yet

*(This dossier was assembled by the chair from the record on 2026-08-28 as
the lifecycle pilot; the builder's renderer takes over its maintenance when
built. Any disagreement between this document and the underlying record is a
defect in THIS document.)*
