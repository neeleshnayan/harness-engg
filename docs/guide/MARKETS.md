# MARKETS — what the firm knows, measured

Every entry: the claim · the measurement · the date · the receipt · the
falsifier. A claim without a receipt does not enter. CONTESTED entries are
flagged, never silently rewritten.

## US equity ETFs (our home venue: Alpaca, alpaca-paper)

- **Our realized trading cost is 2.35 bps — our backtests assume 5.0, so they
  are conservative by ~2×.** n=22 informative fills, cost model
  `reliable: true` (2026-08-26; receipt: /fund/tca, cfo run-cfo-demo-path).
  Falsifier: the next 20 fills moving the realized figure above assumption.
- **Paper-venue fills carry ZERO cost information by construction** — the
  internal simulator fills at our own quote. Only alpaca-paper fills teach
  costs (2026-08-21 experimental-deployment authorization; venue post-mortem).
- **The overnight gap is most of a metal ETF's variance**: 57.6% of GLD's
  variance [53.4–62.0%] is the overnight gap (analyst golddossier,
  2026-08-25). Sizing intraday rules on close-to-close vol misprices them.
- **A fast rule's fragility to the moving last bar is arithmetic, not vibes**:
  d(fast−slow)/d(close) = 1/F − 1/S. At 2/4 a 3-cent intraday wobble flips
  4.58% of sessions; at 10/50, 0.60% (quant dispatch #7, 2026-08-26).
  Corollary: start daily-bar live sessions only after the close settles.
- **Capacity is bounded by the least capacious leg** — and the leg that binds
  is often not the one you assumed; name it in the proposal (quant, belt
  instrument finding, 2026-08-21).
- **Benchmark populations without delisted names flatter nothing reliably**:
  survivorship measured at −6.90pp ± 2.40 over 20 months on our own universe
  (SURVIVORSHIP_2026-08-17.md). Direction on any given strategy: UNMEASURED
  until measured. Disclose the basis; never net by instinct.

## Credit ETFs (HYG)

- **The fund's HYG feed is TOTAL-RETURN shaped** (closes 64.83 → 79.85 while
  quoted price fell): a price-vs-mean rule on it is structurally biased long
  (~6%/yr distributions). Never read an HYG timing result as a credit-timing
  claim without correcting (quant dispatch #7 file header, 2026-08-26).

## Crypto (chartered 2026-08-27; accumulating)

- **Daily candles settle at 00:00 UTC by convention** — a settled-bar
  discipline exists; which sources serve immutable closed candles is being
  measured (analyst run-analyst-cryptovenue, in flight).
- **The flagship premia leg (perp funding carry) requires a perps venue** —
  spot-only brokers cannot express it. India-based operation is not bound by
  US retail restrictions; venue survey in flight.
- Entries land here as the dossier and menu return. An empty section is a
  fact, not a gap to pad.

## Market structure, cross-venue

- **Two things wear the word "paper"** and only one teaches anything:
  the broker's paper ACCOUNT (real venue mechanics, real quotes) vs an
  internal simulator (our own quote, no information). Name which one every
  time (venue post-mortem, 2026-08-26).
