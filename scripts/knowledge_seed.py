"""Seed the knowledge graph — the first entries, receipts and all.

Run once (idempotent by claim_id): entities, the sharpest claims from the
record, and the edges that make them a graph. The docs/guide/ books render
FROM these rows from here on.
"""
import sys
sys.path.insert(0, r"C:\Users\user\Documents\Krypton Fund\ClarkHarness")

from app.fund.knowledge import KnowledgeStore, KnowledgeError

ks = KnowledgeStore()
A = "cto"

def claim(cid, kind, title, receipt, body="", tags=None, falsifier=None):
    try:
        ks.add_claim(claim_id=cid, kind=kind, title=title, receipt=receipt,
                     body=body, tags=tags or [], falsifier=falsifier, actor=A)
        print("  +", cid, title[:60])
    except KnowledgeError as e:
        print("  =", cid, "(exists)" if "exists" in str(e) else str(e)[:60])

def edge(f, t, rel, note=""):
    r = ks.add_edge(from_id=f, to_id=t, rel=rel, note=note, actor=A)
    print("  ->" if not r["already"] else "  ==", f, rel, t)

# ---- entities ----
claim("mkt-us-etf", "entity", "US equity ETFs (Alpaca venue)",
      "the fund's home market since inception", tags=["market"])
claim("mkt-hyg", "entity", "HYG / credit ETFs",
      "second instrument family; the LEAN probe's market", tags=["market"])
claim("mkt-crypto", "entity", "Crypto",
      "chartered 2026-08-27 by the CEO as the second asset class", tags=["market"])
claim("inst-gate", "entity", "The gate (belt verdict instrument)",
      "app/fund/gate.py; versioned criteria", tags=["instrument"])
claim("inst-lean", "entity", "LEAN live engine",
      "leanrunner.py; sessions, signals, the probe", tags=["instrument"])

# ---- market facts ----
claim("cost-etf-235", "market_fact",
      "Our realized US-ETF trading cost is 2.35 bps - backtests assume 5.0, conservative ~2x",
      "cost model reliable:true at n=22 fills, /fund/tca, 2026-08-26; cited run-cfo-demo-path",
      tags=["costs", "us-etf"],
      falsifier="the next 20 informative fills moving realized above assumption")
claim("crypto-funding-dead", "market_fact",
      "Funding carry is NOT a premium: 94.3% of BTC's 7yr funding is Binance's hardcoded 0.01%/8h constant",
      "run-analyst-cryptovenue 2026-08-27: n=7,628 settlements 2019-2026; excess +0.66%/yr at monthly t=0.39 vs MDE 3.34%/yr; -5.83%/yr last 24m; full-year carry nets +3.02% vs T-bill 3.86%",
      body="35.4% of settlements print EXACTLY the 0.01% default. When funding equals the default, nobody chose to pay it. Fifth mechanically-generated flow-premium killed by the analyst.",
      tags=["crypto", "premia", "funding"],
      falsifier="twelve consecutive months of positive funding EXCESS over the constant (one keyless call/month)")
claim("crypto-costs", "market_fact",
      "Crypto round-trip costs by venue: Alpaca 0.542% / Binance spot 0.200% / Binance perp 0.100% / Delta India 0.119%",
      "run-analyst-cryptovenue 2026-08-27, fee schedules + measured spreads/depth",
      body="Alpaca is 2.7x Binance spot and 4.6x Delta India. A weekly rebalance pays ~28%/yr commission at Alpaca. The venue is a sizing input, not a plumbing detail.",
      tags=["crypto", "costs"])
claim("crypto-survivorship", "market_fact",
      "Crypto survivorship is GOOD: 63.1% of Binance's 3,685 symbols are delisted-and-retained with clean terminal history",
      "run-analyst-cryptovenue 2026-08-27: 5/5 sampled dead symbols end cleanly, zero null-padding",
      body="Reopens for crypto the delisting-edge families fenced for equities (no free PIT there). Caveat: 5 sampled, pre-2018 delistings untested.",
      tags=["crypto", "data", "survivorship"])
claim("crypto-settled-bar", "market_fact",
      "Every free crypto source serves a mutable RUNNING last bar; settled bars need endTime = last-UTC-midnight minus 1ms",
      "run-analyst-cryptovenue 2026-08-27: Binance/Kraken/CoinGecko/Alpaca all served running bars at measurement; recipe verified end-to-end",
      tags=["crypto", "data"],
      falsifier="a source documented to serve only closed candles by default")
claim("crypto-luna-splice", "market_fact",
      "Crypto tickers get RECYCLED inside one series: LUNAUSDT splices Terra Classic to Terra 2.0 - a 177,400x fake one-day return at HTTP 200",
      "run-analyst-cryptovenue 2026-08-27; guard built and tested: futures onboardDate check + >20x single-day jump screen (flags 1 of 10 majors, next highest DOGE 4.9x, a real day)",
      tags=["crypto", "data", "identity"])
claim("hyg-total-return", "market_fact",
      "The fund's HYG feed is total-return shaped - price-vs-mean rules on it are structurally biased long (~6%/yr distributions)",
      "quant dispatch #7 file header, 2026-08-26 (closes 64.83->79.85 while quoted price fell)",
      tags=["hyg", "data"])
claim("fastbar-fragility", "market_fact",
      "A fast rule's exposure to the moving last bar is arithmetic: d(fast-slow)/d(close) = 1/F - 1/S",
      "quant dispatch #7: at 2/4 a 3-cent wobble flips 4.58% of sessions; at 10/50, 0.60% - 7.6x",
      tags=["microstructure", "design"],
      falsifier="a measured counterexample where the ratio mispredicts flip frequency")

# ---- failure classes / doctrine ----
claim("fail-absence-as-value", "failure_class",
      "Absence rendered as a value - the firm's most recurrent defect class",
      "instances: due_for_review [] over unevaluable triggers; len(None or [])==0; 422-as-None; P2 unchecked-while-satisfied (Grace 2026-08-27)",
      tags=["absence"],
      falsifier="a quarter with zero new instances of the class")
claim("doc-integrity-not-completeness", "doctrine",
      "A hash chain proves the record unedited, NOT complete - the two are separate controls, costed separately",
      "Grace's retraction, run-cfo-demo-path 2026-08-27: 1,611/1,611 chained AND a 42.6h hole covering all of Tue 2026-08-25",
      body="Completeness must be adversarial to silence: the null and healthy readings are byte-identical, and mutual agreement between stale folds reads as corroboration.",
      tags=["record", "controls"])
claim("run-spine-cycle", "runbook",
      "Cycle the spine: stop LEAN sessions FIRST, verify container death, then restart, then relaunch once",
      "ENG2 orphan finding + the TOCTOU race dc12903f, 2026-08-26/27; full steps in docs/guide/OPERATIONS.md",
      tags=["operations", "lean"])
claim("inst-sqrt252", "market_fact",
      "leanrunner annualises with sqrt(252): every 365-day crypto series gets vol understated 1.2039x, flattering Sharpe",
      "run-analyst-cryptovenue 2026-08-27; verified leanrunner.py:1733 sd * sqrt(252)",
      tags=["crypto", "instrument-defect"],
      falsifier="the annualisation made calendar-aware or explicitly compensated per run")

# ---- edges ----
edge("crypto-funding-dead", "mkt-crypto", "applies_to")
edge("crypto-costs", "mkt-crypto", "applies_to")
edge("crypto-survivorship", "mkt-crypto", "applies_to")
edge("crypto-settled-bar", "mkt-crypto", "applies_to")
edge("crypto-luna-splice", "mkt-crypto", "applies_to")
edge("cost-etf-235", "mkt-us-etf", "applies_to")
edge("hyg-total-return", "mkt-hyg", "applies_to")
edge("fastbar-fragility", "mkt-hyg", "applies_to")
edge("inst-sqrt252", "inst-gate", "applies_to",
     "the gate consumes the flattered Sharpe")
edge("inst-sqrt252", "mkt-crypto", "applies_to")
edge("crypto-luna-splice", "crypto-survivorship", "contradicts",
     "good survivorship AND identity splices coexist: retention is clean, identity is not")
edge("crypto-settled-bar", "fastbar-fragility", "derived_from",
     "both are the moving-last-bar family; crypto has no closing bell at all")
edge("run-spine-cycle", "inst-lean", "applies_to")
edge("doc-integrity-not-completeness", "fail-absence-as-value", "derived_from",
     "a missing day IS absence rendered as health")
edge("crypto-funding-dead", "crypto-costs", "grounds",
     "the carry arithmetic dies on the round-trip cost table")

print("\n--- search smoke: 'crypto costs' ---")
r = ks.search("round-trip")
print("matched:", r["matched"], "of corpus", r["corpus_total"])
print("\n--- neighborhood smoke: mkt-crypto depth 1 ---")
n = ks.neighborhood("mkt-crypto", depth=1)
print("nodes:", len(n["nodes"]), "edges:", len(n["edges"]))
