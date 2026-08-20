# The premia menu — the standing top of the funnel

**v1, drafted by the CTO 2026-08-20 under the CEO's direction ("a strong top of
funnel that consistently generates good strategies"). Versioned: entries are
added/retired with written reasons; statuses move as the chain moves them.
This register turns generation from creativity into COVERAGE: the mechanism
seat works through the menu systematically, three entries per dispatch, each
becoming a full falsifiable proposal or an honest "not proposable, because…".**

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
| 5 | Cross-sectional momentum (band) | Underreaction in neglected small-caps; the research write-up exists | 20-name capacity band | ~21d | YES (4 folds) | write-up filed (RESEARCH_XS_MOMENTUM_2026-08-17.md); never proposed through the chain |
| 6 | Index mean reversion (short horizon) | Liquidity provision to overshooters; impatient flow pays | SPY/QQQ daily reversion | days | YES | UNPROPOSED |
| 7 | Defensive / low-vol premium | Leverage-constrained investors overpay for lottery names | low-vol screen within band + ETFs | months | NO | UNPROPOSED |
| 8 | Post-filing drift in neglected names | Attention is scarce below coverage thresholds; slow diffusion | filings-corpus event windows, band names | 5–20d | YES | UNPROPOSED — the corpus is the input asset; analyst/mechanism joint |
| 9 | FX / rates carry via ETFs | Interest differentials; hedgers pay | currency-hedged ETF pairs | months | NO | UNPROPOSED; data coverage unverified |
| 10 | Closed-end fund discount reversion | Forced/retail flows misprice wrappers | CEF universe | weeks–months | data absent | UNPROPOSED; needs discount data source — absence stated, not assumed |
| 11 | Seasonal/calendar effects (audited skeptically) | Flow calendars (rebalancing, tax) | ETFs | days | YES | UNPROPOSED; adversary prior: mostly data-mined — proposals must carry a named flow |
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
