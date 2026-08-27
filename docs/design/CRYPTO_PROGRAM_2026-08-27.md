# THE CRYPTO PROGRAM — first asset class, laser focus

**Chartered 2026-08-27 by the CEO, verbatim:** *"we gotta focus on crypto;
understand what strategies are deployed today, how can we create our own
strategy that works given current market conditions, what are our blockers
and how can we start in crypto as our first asset and run our team e2e.
this is the fastest space to improve our harness, battle-test it and
demonstrate something substantial in next 2-3 weeks"* — ratified same
session as the core business objective (*"laser focus... then once we have
operational experience with this we move to say equities"*), with two
riders: **coin selection is first-class** and **venue is open** (connectors
buildable; Alpaca is where we started, not where we are fenced).

Constitution amendment: recorded in `.claude/CLAUDE.md` Identity, dated
2026-08-27, with the chair's scope reading (equity paper book keeps running
as the live measurement; research refocuses) flagged for the CEO's second
look.

## THE OBJECTIVE, dated

**Demonstrate something substantial by 2026-09-10/17 (2-3 weeks):** at
least ONE crypto strategy through the ENTIRE chain — proposed → adversary
→ implemented → belt → gate → PM sizing → CEO click → deployed on paper
with committed exit rules → measured live — with the loop's spot-to-live
latency recorded per the moat-is-the-loop thesis. The harness improvements
the run forces out are first-class deliverables, not overhead: "the
fastest space to improve our harness" is the CEO's stated reason for the
focus.

Intermediate target: **first crypto candidate submitted to the belt by
~2026-09-03** (needs W3's engine fixes merged).

## THE WORKSTREAMS

**W1 — THE LANDSCAPE (in flight, analyst).** What is deployed today by
class and scale; current market conditions measured; where a $2k
latency-slow fund can and cannot play; **THE INVESTABLE UNIVERSE** (the
CEO's coin-selection rider — Alpaca's actual tradable list, liquidity
tiers, per-coin data quality against the survivorship corpus, class→coin
mapping, a recommended starter universe); venue-by-class assessment with
connector build costs (the CEO's venue rider). Evidence-grounded, URLs,
invalidation conditions.

**W2 — GENERATION (in flight, Ed batch #7, crypto-only).** The
exogenous-trigger screen pointed at holder-triggered crypto flows: vesting
unlocks, miner treasury selling, ETF creation/redemption flows,
court-scheduled distributions; 24/7 structural premia admissible with a
named counterparty. Universe named per proposal; venue named per proposal
with connector cost; engine-blocker status stated per proposal.

**W3 — THE BLOCKERS (engineering, enumerated honestly).**
1. `leanrunner.py` annualizes with √252 — an equity constant that
   mis-scores a 7-day market. **Pulled into builder batch B1** (was B3).
2. `marketdata.py:109-114` hardcodes 16 coins. **B1.**
3. **The belt E2E probe** (quant, next heavy slot): one trivial crypto
   algorithm down the whole belt to enumerate every OTHER breakage —
   calendar/session assumptions, benchmark plumbing (what is "excess
   return" against for a crypto premia claim; BTC buy-and-hold for alpha),
   gate criteria written against equity conventions. The probe's output IS
   the W3 backlog's second half; we will not discover it by reading.
4. Venue connectors: as demanded by W1/W2 findings — each a named build
   with a paper/testnet mode required before any real-money question.
5. Data: OI recorder live (day ~21, compounding); unlock-calendar and
   ETF-flow sources to be sourced per Ed's proposals; funding history
   remains dead until a real series is accumulated or bought.

**W4 — THE E2E TEAM RUN (the point of it all).** The full chain on the
first surviving candidate, every seat in its lane, the CEO's click where
it always is. Loop latency measured at every stage — the number that
becomes the moat. Grace re-cuts the critical path with dates the moment
W1 + W2 land (her clock, her falsifiers).

## WHAT DOES NOT CHANGE

The control layer, the click, the gate's discipline, blind review, the
excess-returns rule — the entire constitution. The equity paper book keeps
running as the live measurement until the CEO says otherwise; Friday's
exits and the Sep 1 process demo proceed. Crypto gets the research and
harness focus, not an exemption from the machinery.

## FALSIFIERS, written at charter time

- No crypto candidate reaches the belt by 2026-09-05 → the program's
  sequencing (blockers-first) was wrong; re-plan with the CEO.
- The 2-3 week demonstration produces nothing through the full chain →
  the identity amendment's own falsifier fires; the CEO re-decides.
- Any control loosened "because crypto moves fast" → the one forbidden
  move, program or no program.


## ADOPTED 2026-08-27 (same day): the starter universe

**CEO approval, verbatim: "Hurrah! yes lets go!! great going!"** — given in
direct response to the chair's close naming the universe as awaiting his
word. **BTC/USD, ETH/USD, SOL/USD on Alpaca paper, daily bars, hold >= 2
weeks, slow systematic rules only** is the adopted starter universe
(dossier §4.5, with its four change-triggers standing). Recorded actor:
neelesh. The ETH leg's WRAPPER question (staking ETP vs spot — P1, which
SURVIVED the adversary the same day) goes to Stan's 2026-08-28 batch: if
the book takes ETH exposure, the wrapper choice is ~1.9%/yr of free
improvement, and that decision carries the CEO's click on any order as
always. B1 (the engine-blocker batch: √252, the 16-coin hardcode, the
GETH collision) FIRED the same hour.
