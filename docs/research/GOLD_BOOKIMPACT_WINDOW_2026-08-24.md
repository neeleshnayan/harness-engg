# The gold book-impact table, re-measured on the current window (PM, 2026-08-24)

Filed beside GOLD_DOSSIER_V1_2026-08-24.md per the never-edit rule — a new
measurement, not a correction. Author: Stan (run-pm-goldsizing). Chair
verified the reproduction anchor (his 11y row matches the dossier's to
0.02pp, log-vs-simple returns).

**The finding: the dossier's one pro-gold sizing number inverts on current
data.** §4.5 computed book-vol impact on the 11-year covariance window; §4.2
of the same dossier measured GLD's current vol at ~2× its decade average and
the sizing table did not consume it.

| configuration | 11y window (dossier) | last 250 sessions |
|---|---|---|
| current book | 4.54% | **3.43%** |
| + GLD 5% from cash | 4.86% | 4.28% |
| + GLD 10% from cash | 5.29% | **5.40%** |
| + GLD 5% from DBC | 4.24% (−0.30pp) | **3.74% (+0.31pp)** |
| + GLD 10% from DBC | 4.20% (−0.34pp) | **4.57% (+1.14pp)** |
| full DBC→GLD swap | 4.31% | **5.33% (+1.90pp)** |

Cause: GLD realised vol 16.30% (11y) → 29.09% (last 250) → 32.42% (2026
YTD); and corr(GLD,SPY) +0.073 (11y) → +0.310 (250d) → +0.486 (60d).

**Rule extracted (bound to the analyst): a book-impact table states its
covariance window in the table and carries a current-window row.** A risk
parameter handed to a sizing seat inherits the window it was computed on,
and the seat cannot see that window unless it is printed.
