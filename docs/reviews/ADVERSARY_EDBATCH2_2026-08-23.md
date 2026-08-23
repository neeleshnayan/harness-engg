# Adversary — Ed batch #2 blind review (P1 + P2), 2026-08-23

**VERDICTS: KILL / KILL — both on grounds the proposals' OWN falsifiers
specified. All headline arithmetic reproduced exactly (said loudly: the
kills are identification failures, not competence failures). Zero
containers spent; total cost one dispatch. Chair spot-check at resolve:
`adv22/p1c.py` re-run — the zero-information rule passes P1's own tercile
test, confirming the mechanism test could not discriminate.**

## P1 (month-turn rebalancing reversal, SPY/TLT) — KILL

**The observable contributes 2.3% of the headline.** Replace the signal
with a constant — always hold SPY over the same T→T+3 window, identical
turnover, identical trade dates: +25.75 bps/mo (t=+2.90) vs the
conditional's +26.36 (t=+2.97). **Marginal value of the signal: +0.61
bps/mo, t=+0.05.** The control is ex-ante legitimate: the SPY
turn-of-month excess was +36.68 bps out of sample over 1993–2002
(published by 1988). The stated falsifier (magnitude terciles) was run on
the 168 s>0 months only — where the signal rule and the zero-information
rule are provably the SAME portfolio (max difference 0.0 bps) — so the
test could not have failed; over all 282 months the monotonicity
vanishes, and the zero-information rule passes it too. The discriminating
leg (s≤0) never reaches |t|>1.2 in any era. Measured vol-ratio 1.0219 vs
predicted 0.90. Prior art (NBER w33554) verified EXACT — and its timing
is against the trade: impact troughs Day 2, reverts by Day 6–15; P1's
hold sits inside the impact window. Failed attacks named: the
EW-rebalance attack came back NEGATIVE (−1.12 pp/yr, second consecutive
empty); the turn-of-month concentration is real (5.1× all-window
average); the mid-month placebo is honest (it just doesn't discriminate).

## P2 (month-end duration extension, last-3, TLT/BIL) — KILL

**The payer has detached from the dates that pay.** The mechanism pins
the payer to the Bloomberg Agg's last-business-day rebalance (factsheet
verbatim, verified). Split at that date, modern era: pinned rtdom −2..−1
= +14.32 (t=1.76, not significant); unpinned rtdom −5..−3 = +32.23
(t=2.68) — exactly inverted from 2003–13. The proposal's own falsifier:
"the effect detaching from the rebalance date." It has. **The claimed
pre-declaration does not exist**: "last three"/"three days"/"final three"
appear nowhere in the 41-page Hartley–Schwarz paper — its flagship window
is LAST-2, which was refused at BE 7.16 this same run. **The second
falsifier has already fired**: trailing-window ladder 96/72/48/36/24
months = BE 13.92 / 8.28 / 8.15 / 9.45 / 3.51 against the 10.0 floor —
modern capture has halved (+50.57 first half → +16.08 second). The NY Fed
"−28% price impact" citation measures execution cost, not crowding
(liquidity is IMPROVING at month-end — favourable to costs, useless as
the falsifier's instrument; label defect, not deception). Failed attacks
named loudly: BIL-carry nearly empty (+0.36 of +4.11 pp/yr — the r4
pattern does NOT apply); the 2014 breakpoint is not mined (2008→2019
sweep flat); the edge survives dropping its top 5 months (BE 12.05); the
window is genuinely special (+30.72 excess over all 3-session windows).

## Cross-proposal: the shared premise SURVIVES both kills

Calendar-mandated month-end flows are real — both primary-source
citations verified exact. P1 died on identification; P2 on payer
detachment + a fired falsifier. Independent grounds. **The family is not
retired**; a future proposal inherits two specific, measured
identification failures, not a dead premise.

## Proposal standards recommended (tightening; applied to Ed's card at resolve)

1. **The constant-observable control**: every conditional rule reports
   the paired marginal (signal vs frozen-signal, identical trades) with
   its t-stat in the header — and runs its mechanism test only on
   observations where the two versions DIFFER.
2. **The trailing-window ladder** (24/36/48/72/96 months) replaces the
   author-chosen era table — the E21 era check passed on both of these
   while the ladder failed one.
3. **Citation discipline**: a cited window counts as pre-declaration only
   with the paper's own defining sentence quoted; a sweep table is not a
   pre-declaration.

**What would change the verdicts**: P1 — the s≤0 leg or the paired
marginal reaching |t|>2 on a pre-declared window. P2 — the pinned
subwindow (rtdom −2..−1) coming back at t>2 with BE ≥10 on modern data,
or flow evidence that benchmarked buying now executes 3–5 sessions ahead
(which would re-pin the payer).

**Primary record (verbatim): run `run-adversary-edbatch2`; STATE in
`.claude/state/adversary.md`. Probes: `scratchpad/adv22/` — `p1c.py`
(constant-observable harness) and `p2c.py` (pinned/unpinned splitter) are
standing instruments for any calendar candidate.**
