# P1 — the ETH staking-wrapper premium

**Strategy dossier (pilot of the lifecycle design,
docs/design/STRATEGY_LIFECYCLE_2026-08-28.md). Assembled from the record;
every quote verbatim from the filed artifact it cites. Stages append; nothing
is rewritten.**

```
PROPOSED ✓ → REVIEWED ✓ → IMPLEMENTED ✓ → BELTED ✓ → DECIDED ✓ → SIZED … → DEPLOYED · → LIVE ·
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

## SIZED — pending (Stan, in flight 2026-08-28)

Conditional sizing memo dispatched the same morning. Basis bound in advance:
size on the **+1.9%/yr post-staking figure**, not the belt's +1.72pp headline
(0.66pp of which is a cash-buffer rebalancing artifact that reverses sign in
a rising market). A NEW ~70%-vol ETH position — the fund holds no ETHA, so
the wrapper is a free improvement on a position being chosen, not a swap.

## DEPLOYED — not yet

Requires: Stan's sizing → chair stages through the ordinary propose path
with exits committed BEFORE entry → the CEO's click. Monitoring commitment
carried from review: judged on TOTAL RETURN vs ETHA; Ed's replacement
falsifier (declared distributions) due 2026-09-05.

## LIVE — not yet

*(This dossier was assembled by the chair from the record on 2026-08-28 as
the lifecycle pilot; the builder's renderer takes over its maintenance when
built. Any disagreement between this document and the underlying record is a
defect in THIS document.)*
