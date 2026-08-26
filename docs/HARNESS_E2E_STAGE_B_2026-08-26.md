# STAGE B — THE BRAIN: can a strategy decide for itself?

**CEO, 2026-08-26: *"our lean engine should be running to compute these
strategies buy/sell signal right?"* — and he was right to ask. It is not, and
it never has been.**

Chartered by the co-CTO. Stage A (the carriage) is armed and fills Friday;
this is the half that tests whether the fund can MAKE a decision rather than
merely carry one.

---

## THE CLAIM UNDER TEST

**"An algorithm running in the engine can raise a proposal that reaches the
CEO's desk, correctly attributed, and be managed by the same machinery as a
hand-staged one."**

## WHAT EXISTS ALREADY — read from the code, not assumed

The path is **built and complete on paper**, which is better than I expected:

- `POST /fund/lean/live` (`fund.py:1490`) starts a supervised live session.
  **The container gets a signal token and a strategy id and nothing else** —
  no venue credentials, no broker keys. Its entire reach is one POST back.
- `POST /fund/signals/external` (`fund.py:3746`) is that intake. Token-gated
  (`EXTERNAL_SIGNAL_TOKEN`, **verified present in .env**), constant-time
  compare, **503 when unset — absent config reads as OFF, never as open**.
- It **refuses an unregistered strategy** (404): *"an engine signal nobody can
  attribute is a trade nobody can post-mortem."*
- The signal lands as an ordinary proposal, behind the same risk and
  compliance gates, and the human click stays the only path to the venue.
- **8 of 12 saved algorithms already declare `set_benchmark`**, which live
  mode requires (without it LEAN subscribes to SPY minute bars the live-paper
  queue cannot serve, and the session dies at startup).

**It has run exactly once, ten days ago**: seq 157, 2026-08-16, one GLD buy
from `gld_sma_filter`, actor `external:lean`. One proposal in the fund's
entire history.

## THE GAPS — measured, and G1 is the one that decides the design

- **G1. THE INTAKE HARDCODES `venue="paper"`** (`fund.py:3777`). Every engine
  signal becomes a PAPER order regardless of what the algorithm intends. Two
  consequences: (a) **it never reaches Alpaca**, so Stage B cannot close a
  round trip at a real venue; (b) **paper fills carry ZERO cost information
  by construction** — a standing fact in this firm — so Stage B produces no
  TCA. **This is the single change that would make Stage B a real test, and
  it is an ORDER-PATH change: not the co-CTO's to make.**
- **G2. One live session at a time**, enforced (`leanrunner.py:641`). Fine
  for a test; a constraint to remember before anyone imagines a bench of
  strategies running together.
- **G3. Daily bars are a once-a-day event, not a ticking feed** (the runner's
  own docstring). Live mode buys supervision and surviving state, not
  latency. A test must therefore span **days**, not minutes.
- **G4. The strategy must be REGISTERED first** or the intake 404s — and
  registered strategies are separate from saved algorithms. Nothing today
  links `gld_sma_filter` the algorithm to a strategy record.
- **G5. No exit rules are attached to engine proposals.** Stage A proved
  rules must predate a position for the autopolicy to auto-approve a sell.
  An engine that opens a position the fund has no exit rule for creates the
  exact orphan class R39 spent a day cleaning up.
- **G6. Nothing supervises the session.** No heartbeat, no alarm if it dies
  silently, no record on the desk that a session is running. A dead engine
  and a flat engine look identical.
- **G7. The engine and the book can disagree about holdings** — the defect
  class that cost the fund all of 2026-08-24. LEAN keeps its own portfolio
  state; the fund folds its own from the log. Nothing reconciles them.

## THE PLAN

| phase | what | gate |
|---|---|---|
| **B0** | Register a strategy record for the chosen algorithm and attach exit rules to it BEFORE any session starts (G4, G5). | chair |
| **B1** | **Decide G1 — the CEO's call.** Either (a) leave `venue="paper"` and accept Stage B proves *attribution and plumbing only, with no cost information and no real fill*, or (b) change the intake to carry the venue, which is an ORDER-PATH change: adversary blind first, then his click. **My recommendation: run B2–B4 on paper FIRST** — it is free, it exercises G2/G3/G4/G6/G7, and it tells us whether the engine can raise anything at all before we spend a control review on the venue. | **CEO** |
| **B2** | Start one live session on a dull algorithm with `set_benchmark` already declared. Record it on the desk so a human can see it is running (G6). | chair |
| **B3** | **The test**: does a signal reach the intake, pass the token, attribute to the strategy, and land on the desk as a proposal? Does it carry a sane quantity? Does the engine's view of the position match the fund's fold (G7)? | machine |
| **B4** | Stop the session deliberately. Confirm it stops, confirm nothing orphaned, confirm the record says a human stopped it rather than it dying. | chair |

## WHAT WOULD MAKE STAGE B A FAILURE

Not "the algorithm was wrong" — the edge is irrelevant here as in Stage A. It
fails if a signal is **raised and lost**, if a proposal arrives **unattributable**,
if the session **dies without saying so**, or if the engine and the book hold
**different positions and nothing notices**.

## SEQUENCING AGAINST STAGE A

Stage A's exits fire Friday 2026-08-28. **Do not start a live session before
then.** Stage A is the first test of exit-fires → autopolicy-approves → fills;
an engine raising proposals into the same queue during that window would make
a failure ambiguous between two causes, which is the one thing a test must
never allow.
