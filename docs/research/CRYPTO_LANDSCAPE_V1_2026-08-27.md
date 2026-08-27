# The Crypto Strategy Landscape — v1

**Dr. Mike Darwin (analyst) · run-analyst-cryptoland · 2026-08-27.** All
prices/measurements taken 2026-08-26 (last complete UTC session) and
2026-08-27 09:34–09:45Z (live reads). Every number is either measured from
a named free endpoint or carries a URL. Companion (do not re-derive):
run-analyst-cryptovenue STATE — venue costs, testnet fidelity, ticker
recycling, the funding-constant decomposition.

**CTO NOTE AT RESOLVE (Fable chair, same day)**: the dossier's single
highest-value open question — whether Alpaca crypto perpetuals are secretly
live behind the 401-gated routes — was SETTLED at resolve with one
authenticated read-only call on our own paper keys: **404 "endpoint not
found" on both routes. Alpaca crypto perps are NOT live**; the SDK doc was
right and the 401 was the auth gate answering before routing. No shorting
or leverage at Alpaca; the "closed" column below stands as written. The
starter-universe recommendation (BTC/ETH/SOL) is on the CEO's desk.

```
TL;DR
Crypto is in a quiet bear: bitcoin is 37% below its October-2025 high, trading volumes are
roughly half of last year's, and price swings are calmer than three-quarters of bitcoin's
own history. The professional money-making trades — market making, the cash-and-carry
basis trade, funding harvesting — are all paying less than a US Treasury bill right now,
which is why the biggest public vehicle for that trade has shrunk 73% since October and
why hedge funds' short position at the CME has not actually unwound (a widely-reported
"flip to long" turns out to be true only for a contract 1/50th the size).
For us that closes most of the professional playbook and leaves one honest lane: slow,
daily-bar, systematic positions in a handful of genuinely liquid coins. Our current
broker, Alpaca, can execute that but costs 2.7x Binance and cannot short or use leverage
at all, which sets the minimum sensible holding period at about two weeks.
The uncomfortable finding for our research pipeline: crypto has no equivalent of company
filings, so the free, dated events we can study are either daily (ETF flows — killed
three separate times) or so rare they can never reach statistical significance.
Event-driven research that worked in equities will not transfer.
```

## 0. The contrary fact, written first

Every institutional crypto strategy priced today earns **less than a
3-month Treasury bill**, with infrastructure, leverage and shorting we do
not have. Hyperliquid's HLP — the most transparent professional
market-making book in crypto — reports **7.00% APR** and is LOSING capital
($224.1M → $185.5M in a month while P&L was positive = redemptions). The
Dec-26 Binance term basis is +4.64%/yr gross. BTC perp funding trailing
365d is +3.32%/yr. Against DGS3MO at 3.86% (2026-08-26). If professionals
with 100× our capability are paid ~0–3% over cash, the honest prior is our
edge is NOT in the carry family, and any proposal claiming otherwise is
claiming to beat Wintermute at Wintermute's own game.

## 1. What is deployed today

- **Market making**: Wintermute (~$15bn/day self-reported), GSR,
  Cumberland, B2C2, DWF. HLP is the one audited public return series: 7.00%
  APR, +$137.7M all-time since 2023-05, shrinking. Binance BTC/USDT spread
  measured 0.00 bp with $6.56M depth — no spread left to capture.
- **Basis / cash-and-carry**: the dominant post-ETF institutional trade.
  Measured 2026-08-27 (Binance delivery futures, spot $80,259.99):
  Sep-26 +4.34%/yr, Dec-26 +4.64%/yr (ETH +4.10/+3.65). CoinDesk reports
  CME 3-month ~2.08% (2026-08-08). **A widely-reported "CME hedge funds
  flipped net long" headline is REFUTED at the CFTC's own file**
  (gpe5-46if, report 2026-08-18): BITCOIN (5 BTC) leveraged funds NET
  −7,439 (≈−$2.94bn), net long 0 of 60 weeks since 2025-07-01; the "flip"
  is MICRO BITCOIN only (+1,098 ≈ +$8.7M ≈ 0.3% of the notional). The
  carry short is compressed, not unwound.
- **Funding harvest**: Ethena USDe $4.05bn vs $14.82bn peak (2025-10-04) —
  **−72.7% in ten months**, the market's own verdict. Funding trailing:
  BTC 365d +3.32%, ETH +2.39%, SOL −1.56%; 13/21 of last week's BTC
  settlements printed exactly the 0.01% hardcoded constant. The prior kill
  (94.3% constant, excess +0.66%/yr t=0.39) stands.
- **Stat arb / momentum / CTA**: VisionTrack 2024: composite +40%, quant
  directional +53.7%, market neutral +18.5% (2025-26 levels NOT public —
  do not carry a bull-market number into a bear). **The only class whose
  infrastructure we already meet.**
- **MEV**: top-3 builders = 90.08% of blocks (Titan 53.86/Quasar
  19.52/BuilderNet 16.70, relayscan 7d). An access game, not a capital game.
- **Lending/OTC (Galaxy Q2-26, SEC 8-K verbatim)**: $49M adjusted gross
  profit, **net loss $(85)M**, $2.7bn equity, $1.4bn loan book. The whole
  professional stack's profitability in this regime.
- **Staking/DeFi**: requires self-custody — out of scope by construction.
  Alpaca staking not documented either way.

## 2. Current market conditions (measured, settled bars, 2026-08-26 close)

- **Price**: BTC $79,023.75 (−36.6% from ATH close 2025-10-06); ETH
  $2,506.78 (−48.1%); SOL $102.07 (−61.0%). 2026 YTD: −9.8/−15.6/−18.1%.
- **Vol is LOW**: BTC 30d ann vol 41.8% = **24.5th percentile of its own
  history** (n=3,267 windows); ETH 67.7% = 39.8th; **SOL 51.9% = 5.5th
  percentile** — the most extreme reading in the survey. Structural
  decline: 2017 110% → 2025 42% → 2026 47%.
- **Activity halved**: Binance BTC $1,088M/day (30d) vs $2,322M (2024);
  DEX 30d $7.22bn/day vs $16.45bn a year ago (−56%).
- **Composition**: BTC dominance 59.2%; mcap $2.715tn; stablecoins
  $310.8bn with USDC +1.91%/mo — **dry powder is NOT leaving; the one
  two-sided fact**.
- **ETF flows regime-flipped inside a bad year**: BTC 2026 YTD −$1,935m
  but trailing 20d +$3,250m with ten consecutive positive sessions.
  Recorded, not explained.
- **Mining stress confirmed at the primary**: hashrate 950.6 EH/s = −27.2%
  from the 2025-10-24 peak; miner revenue $40.0M/day vs $35.6M/day of
  issuance.
- **Structural changes 2025-26**: in-kind creations/redemptions approved
  2025-07-29 (SEC 2025-101) — weakens the ETF-flow→spot mechanism; US-legal
  perps arrived (Coinbase 2025-07, Kraken/Bitnomial 2026-06); the carry
  trade de-levered without unwinding.

## 3. Where we can and cannot play

Venue is a build decision (CEO correction): `connectors/base.py` is a
119-line venue-agnostic Protocol ("adding a venue is a new connector with
zero upstream change"); alpaca.py is 386 lines; a Binance connector ≈ 400
lines (`ccxt` not in venv; adding it is a dependency decision that would
collapse this under 100).

**The cost table sets the tradeable frequency band — the most actionable
arithmetic here** (round-trip: Alpaca 0.542% / Binance spot 0.200% / perp
0.100% / Delta India 0.119%):

| rebalance | Alpaca drag/yr | Binance spot | Binance perp |
|---|---|---|---|
| daily | **136.6%** | 50.4% | 36.5% |
| weekly | **28.2%** | 10.4% | 5.2% |
| bi-weekly | 14.1% | 5.2% | 2.6% |
| monthly | **6.5%** | 2.4% | 1.2% |

**At Alpaca, any rule holding under ~2 weeks is dead on costs before the
first backtest.**

**CLOSED by arithmetic**: market making (our 15bp maker fee vs 1.5bp
half-spread — we'd pay 10× what we capture; 0-bp tier needs $100M+/mo =
53,000× NAV); latency/cross-venue arb (0.542% RT vs a 0.0842% median
dislocation that is the USDT/USD basis, not a mispricing); MEV (90.08%
builder concentration); basis carry (Dec-26 nets +3.68%/yr vs T-bill
3.86% — loses to cash before tax; Alpaca can't short or margin AT ALL,
verbatim from its docs); funding harvest (the constant); staking (custody).

**OPEN**: slow systematic directional/cross-sectional on liquid majors,
daily bars, hold ≥2 weeks. Capacity measured, not assumed: a $471 position
is 0.14% of Alpaca BTC daily volume; slippage 0.017% at $2,000. The
counterparty is "nobody in particular" — judge it as PREMIA, not alpha.

### 3.1 The exogenous-trigger screen applied — and the structural finding

| family | free? | dated? | verdict |
|---|---|---|---|
| token unlocks | **NO — llama emissions now HTTP 402** | — | CLOSED on data + off-universe (only ARB vests in our set). Published impact: trust −4.85% median vs MATCHED peers (n=236) over the unmatched −16.97% |
| miner selling | partial | **NO — the 8-K production cadence DECAYED** (MARA 25/yr→11; CLSK 31→6; only 23-34% land by the 8th) | CLOSED on calendar reliability |
| ETF creations/redemptions | yes | yes | **PRE-KILLED ×3** (ETH placebo; GLD 21y replication; in-kind approval removes the mechanism) |
| court distributions | yes | slipping | STRUCTURALLY UNMEASURABLE (n≤10) — and FTX pays USD cash at petition valuations: a potential BID, sign undetermined; Mt. Gox slipped again to 2026-10-31 |

**THE MDE, computed before any test**: BTC daily sd 2.188% ⇒ at n=4 a
5-day effect must exceed 4.89% for |t|=2; n=10 → 3.09%; n=50 → 1.38%.
**Crypto has no middle-band event class.** Equities gave us 79,559 dated
8-Ks; tokens do not file. The free dated families are daily-and-dead (ETF
flows, n=674) or rare-and-unmeasurable (n≤10). **Generation in crypto must
come from price/flow structure and calendar mechanics on a small liquid
universe, not from an event corpus.**

### 3.3 Venue map

Slow systematic spot: **Alpaca today** ($0 connector, real paper crypto).
Cost-optimised: Binance spot (spot TESTNET measured unusable: 18.35%
median daily range vs 2.75% mainnet). Short/leverage: Binance perp or
Delta India (no 1% TDS on F&O) — Binance FUTURES testnet fidelity
UNMEASURED, the cheapest open item. **Alpaca crypto perps: SETTLED NOT
LIVE at resolve (authenticated 404).** Beware: "Alpaca Finance" (BNB-chain
DeFi) is a different company — three of the top search results are the
wrong Alpaca.

## 4. The investable universe (CEO: "selecting the right coins are also key")

- Alpaca serves 29 USD pairs — **four are corpses with no warning** (TRX
  quotes stale since 2023-04, NEAR/MATIC 2023-06, MKR 2025-09): the fourth
  "absence wearing values" instance on this seat's record. Filter on quote
  freshness, never on "the endpoint returned a row."
- Tiers (7d avg): T1 BTC $347k/day 3.0bp, ETH $149k 2.2bp; T2 SOL $76k
  3.8bp, XRP $206k but **40bp spread and a 93-bar GAPPED series** (Alpaca
  delisted/relisted it) — the trap of the table; T3 (LINK/AAVE/UNI/DOT/
  DOGE) usable but spread-costly; T4 marginal; **T5 untradeable** (FIL
  $293/day — one position = 1.6× the coin's entire daily volume).
- **Splice screen run on all 27: ZERO flags** (max DOGE 4.92×, a real
  day). Binance base rate re-measured: 3,685 spot symbols, **63.1%
  dead**. Perp naming traps caught: PEPE/SHIB perps exist as
  1000PEPEUSDT/1000SHIBUSDT; MATIC has none (migrated to POLUSDT).
- Backtest-on-Binance / execute-on-Alpaca carries a **~9bp systematic
  USDT/USD offset** — a third of an Alpaca round trip; declare it in every
  such candidate.

> **RECOMMENDED STARTER UNIVERSE: BTC/USD, ETH/USD, SOL/USD on Alpaca
> paper, daily bars, hold ≥ 2 weeks, slow systematic rules only.** The only
> three names clearing every measured filter simultaneously (spread ≤4.1bp,
> volume ≥160× a position, ≥1,600 bars both venues, zero splices, live
> quotes, perp available for a future short leg). What would change it:
> a Binance connector merged (T3 opens, ~10 names); any name failing the
> freshness/splice screen (re-run before every study); SOL's vol leaving
> its 5.5th percentile (re-fit anything vol-scaled); a T4 name sustaining
> $50k/day for 30 days.

## 5. Invalidation conditions (per claim — full table in the run record)

Carry-is-dead: 12 consecutive months of positive funding EXCESS or 60-day
basis >8%/yr above cash. MM-closed: any accessible venue with ≤1bp maker
at our size. ETF-flows-dead: only a pre-registered test on a NEW
instrument. Vol-is-low: BTC 30d crossing 55.5% (its median). Carry-short-
not-unwound: 3 consecutive CFTC weeks net long in the 5-BTC contract.
The-2-week-hold: the first REAL crypto fill re-measures the 0.542%.

## 6. Not checkable today (reported absent, not assumed)

DGS3MO live (FRED timed out; 3.86% is 08-26); Alpaca's liquidity source
(undisclosed); Kaiko report bodies (gated; §1 quotes flagged second-hand);
VisionTrack 2025-26; Binance futures-testnet fidelity; Delta India funding
(two surfaces, opposite signs — do not measure there); real crypto
execution costs (zero real fills exist; the paper venue cannot measure
them by construction).

## 7. The money question, answered plainly

Six of eight professional classes closed by arithmetic; the seventh
(events) closed by a structural absence of measurable events nobody had
articulated; **the eighth — slow systematic BTC/ETH/SOL on daily bars,
held ≥2 weeks — is genuinely open**, and we have the venue, data,
capacity and paper account today. At $1,885.74 NAV a world-class year is
~$283: the value of the next three weeks is not the $283 — it is one
crypto candidate through the entire chain on a 24/7 asset that exercises
the harness harder than equities ever did, with the candidate not built on
a premise the market has already priced to zero.

---

*STATE appended to the seat's memory and BINDS carried (Ed, quant, Stan,
chair, validator) at the chair's resolve, same session. Measurement scripts
and cached datasets: session scratchpad `cryptoland/` (m1–m15).*
