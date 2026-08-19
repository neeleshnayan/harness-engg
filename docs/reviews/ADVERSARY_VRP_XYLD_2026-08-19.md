# ADVERSARY VERDICT: KILL — VRP/XYLD proposal

**Artifact attacked:** docs/proposals/VRP_XYLD_2026-08-19.md
**Reviewer: adversary agent (blind), 2026-08-19. Attacked with live data from the
fund's own feed, not with argument.**

Two independent grounds, each sufficient. The mechanism (VRP exists in index
options) is not what died — the artifact's specific, checkable claims did.

## Ground 1 — the success criterion fails on our own data

The proposal pre-registers the honest test itself: higher Sharpe than SPY at
60–70% of its vol, paired over the same folds. Run on the fund's feed (Alpaca,
split+dividend adjusted — XYLD's yield is included):

| window | XYLD Sharpe | SPY Sharpe | diff | Memmel/JK z | vol ratio | daily-OLS alpha |
|---|---|---|---|---|---|---|
| 630d (fund judgment window) | +1.230 | +1.266 | **−0.036** | −0.12 | 0.68 | +1.0%/yr |
| 504d | +1.207 | +1.197 | +0.010 | +0.03 | 0.69 | +1.4%/yr |
| 252d | +2.484 | +1.544 | +0.940 | +1.97 | 0.55 | +7.8%/yr |
| **10y common (n=2514)** | +0.634 | +0.891 | **−0.257** | −1.55 | **0.81** | **−1.92%/yr** |

On the judgment window: a dead tie with a negative point estimate. On the deepest
window our feed serves: XYLD is WORSE (z −1.55), and the vol ratio is 0.81 —
outside the claimed band. The only supporting window is the trailing 12 months,
precisely the recency the gate architecture exists to discount.

**The proposal's own falsification #2 is already true historically:** daily OLS
alpha of XYLD on SPY is −1.92%/yr at beta 0.70 over 10 years. The wrapper leaks —
fees, roll timing, upside-cap drag eat the premium. The proposal named its own
failure mode and did not run the check.

## Ground 2 — the falsification monitor cannot be computed here

Falsification #1 and the "well-powered" mechanism test require VIX. Measured:

- `fetch_daily_bars('^VIX')` → `BarsError: Invalid symbol` (validator rejects the
  caret; Alpaca serves no indices; bare "VIX" returns 0 bars)
- No VIX ingestion path exists anywhere in the codebase
- VIXY/VXX exist but are rolled-futures ETPs — substituting them changes what the
  number measures

The claim "~30 independent monthly observations on our history" is asserted
against data the fund does not have and cannot fetch. The kill switch that
distinguishes this from unfalsifiable buy-and-hold is fiction on this
infrastructure.

## What survived, for the record

- XYLD exists with 10 years of usable history (~$30.7M avg dollar volume); PUTW is
  dead on our feed (last bar 2025-04-03) — the proposal's hedge was correct
- Correlation limits: no breach (book avg 0.19 → 0.25 with XYLD; XYLD–SPY pair
  0.89–0.91, one hundredth under the 0.90 strategy-correlation limit)
- Cited standalone Sharpe range matches measurement
- Friction: 20% sizing sits exactly on the position cap with zero headroom

## What would change the verdict

1. A real IV-surface ingestion path producing the claimed monthly IV−RV series,
   with the trailing 12-month mean measurably positive — the monitor made real
   BEFORE the position exists
2. A paired Sharpe on the judgment window positive with meaningful z — or an
   amended, pre-registered criterion stating that a Sharpe TIE at ~0.68× vol is
   itself the success (a defensible vol-reduction claim, but a different claim)
3. Evidence the −1.9%/yr 10-year wrapper leak is regime-specific and the
   compressed post-2023 premium still clears the wrapper's drag net
