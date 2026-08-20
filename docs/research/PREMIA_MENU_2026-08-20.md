# The premia menu — the standing top of the funnel

**v1, drafted by the CTO 2026-08-20 under the CEO's direction ("a strong top of
funnel that consistently generates good strategies"). Versioned: entries are
added/retired with written reasons; statuses move as the chain moves them.
This register turns generation from creativity into COVERAGE: the mechanism
seat works through the menu systematically, three entries per dispatch, each
becoming a full falsifiable proposal or an honest "not proposable, because…".**

**Column correction, 2026-08-20 (cycle 1, mechanism defect D3): "Testable
today?" conflated "folds exist" with "a plausible effect is resolvable" — how
entry 5 got marked YES while being unresolvable through 16.9%/yr of tracking
vol. The column now answers BOTH, and a dispatch is never aimed at an entry
the instrument cannot judge.**

Ground rules inherited from the identity decision (2026-08-19): premia claims
are judged on risk-adjusted return vs holding the asset, never on beating
buy-and-hold. Every entry names its economic reason and counterparty BEFORE
any backtest exists — an entry without a reason someone pays does not get on
the menu. Testability column is against the CURRENT archive (~621 sessions,
2024-02-26 →); the planned 10y backfill (see FUNNEL doc §4) re-opens the
NOT-TESTABLE rows — the belt's fold table, not this doc, is the authority.

| # | Premium | Economic reason / who pays | Canonical instruments (our band) | Hold | Testable today? | Status |
|---|---|---|---|---|---|---|
| 1 | Equity variance risk premium | Insurance against drawdowns; pensions/structured desks buy puts by mandate | put-write / covered-call ETFs (XYLD family) | weeks | partly | **KILLED 2026-08-19 as XYLD implementation** — 3 revival conditions in docs/reviews/ADVERSARY_VRP_XYLD_2026-08-19.md; re-proposable only through them |
| 2 | Term premium | Duration risk compensation; liability hedgers pay | TLT / IEF ladder | months | NO (42d+) | in the sleeve as declared beta; proposable as premia post-backfill |
| 3 | Commodity carry / roll yield | Hedging pressure from producers; index rollers pay | DBC, per-commodity ETFs | months | NO | sleeve leg (declared beta); proposable post-backfill |
| 4 | Time-series trend (as premia) | Slow-moving capital, behavioral underreaction; rebalancers pay | broad ETF set, 3–12m lookbacks | months | NO (long lookbacks) | UNPROPOSED — the retired "Trend" strategy was NOT this (it failed as alpha at 21-day scale) |
| 5 | Cross-sectional momentum (band) | ~~Underreaction in neglected small-caps~~ | 20-name capacity band | ~21d | folds exist; effect NOT resolvable | **RETIRED 2026-08-20 (cycle 1)**: required alpha for IR 1.0 is 16.9%/yr at top-5 (measured: median name vol 48.2%, pairwise corr 0.182) vs single-digit documented style premia; and the ADV band is a capacity filter used as a counterparty story, which the charter forbids. Revivable ONLY with a non-price signal (entry 8). |
| 6 | Index mean reversion (short horizon) | ~~Levered-ETF daily rebalance flow~~ | SPY/QQQ daily reversion | days | folds exist; regime coverage poor (D1) | **DECLINED-WITH-CONDITIONS 2026-08-20 (cycle 1)**: the mechanism's own symmetry test fails on our feed (up-tail 3d excess +0.286%, wrong sign). Conditions in REVIVAL_REGISTER. |
| 7 | Defensive / low-vol premium | Leverage-constrained investors overpay for lottery names | low-vol screen within band + ETFs | months | NO | UNPROPOSED |
| 8 | Post-filing drift in neglected names | Attention is scarce below coverage thresholds; slow diffusion | filings-corpus event windows, band names | 5–20d | YES | UNPROPOSED — the corpus is the input asset; analyst/mechanism joint |
| 9 | FX / rates carry via ETFs | Interest differentials; hedgers pay | currency-hedged ETF pairs | months | NO | UNPROPOSED; data coverage unverified |
| 10 | Closed-end fund discount reversion | Forced/retail flows misprice wrappers | CEF universe | weeks–months | data absent | UNPROPOSED; needs discount data source — absence stated, not assumed |
| 11 | Month-end rebalancing flow (the one calendar entry with a named payer) | $20trn of pension/TDF fixed-target mandates sell the winner into month-end — 17bp next-day impact, ~$16bn/yr transfer, NBER w33554 | SPY/TLT always-invested sign switch | 21d (monthly re-decide) | 4 folds; effect (IR ~0.2–0.4) NOT resolvable at 22.8% power | **SPEC-FILED / DEFERRED 2026-08-20 (cycle 1)** — implementation-ready (claim type ALPHA; mid-month placebo passes cleanly; magnitude test fails; post-publication half is a coin flip). Unblocked by P1 (per-instrument cost measurement — the global 5bps kills it 1.2%/yr vs 1.0–1.8%/yr gross) and P2 (history backfill, itself gated on gate v5). Full spec in docs/research/MECHANISM_CYCLE1_2026-08-20.md. |
| 12 | Dated-catalyst events | Information with a timestamp (PDUFA, lockups, reconstitution) | band names + revival register | event | YES | the REVIVAL_REGISTER's SRPT Q3 condition is the live example |

## How an entry leaves this menu

proposed → attacked → implemented → belt-judged → gate verdict, per the chain.
An entry may also be retired with a written reason (e.g. "no instrument in our
band", "counterparty story failed adversary twice"). A killed implementation
does NOT retire the entry — it moves to killed-with-conditions and the
conditions go to the revival register.

## What the menu deliberately excludes

Anything requiring speed (HFT, intraday microstructure), breadth we lack
(thousand-name stat-arb), leverage or shorting beyond the paper venue's
reality, or data we do not have and have not priced. The menu grows by
demonstrated feasibility, never by textbook completeness.
