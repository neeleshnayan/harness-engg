# THE END-TO-END HARNESS TEST — charter

**CEO instruction, 2026-08-26, verbatim:** *"what I am thinking is that we
first test our harness for a simple strategy. see how we deploy and manage it
end to end"* and *"charter an execution plan and tell me the gaps"*.

**Chartered by the co-CTO (Fable OOO). Awaiting the CEO's go and his click at
each order, as always.**

---

## THE CLAIM UNDER TEST

**"This firm can take one idea from proposal to a CLOSED round trip, and
manage it while it is open."** Not *"can we find an edge"* — the edge is
deliberately irrelevant here. The subject is the machinery.

**This has never happened.** Not once, in any form.

## WHAT IS PROVEN AND WHAT IS NOT — measured 2026-08-26, not asserted

| # | stage | status | evidence |
|---|---|---|---|
| 1 | mechanism proposes a falsifiable edge | **PROVEN** | many; Ed's batches |
| 2 | adversary attacks it blind | **PROVEN** | kills on record incl. today's |
| 3 | quant implements to a LEAN algorithm | **PROVEN** | lean_workspace |
| 4 | the belt runs it, the gate judges | **PROVEN** | 767 stored results |
| 5 | a candidate PASSES the gate | **PROVEN ONCE** | Entry 20, premia, 2026-08-24 |
| 6 | a gate-cleared candidate is DEPLOYED | **NEVER** | no path exists (see G1) |
| 7 | a position is managed while open | **PARTIAL** | exit rules armed; PM reviews |
| 8 | an exit rule FIRES and EXECUTES | **NEVER** | 2 triggered, **0 filled** |
| 9 | the autopolicy auto-approves anything | **NEVER** | **0 approvals, 15 declines** |
| 10 | a round trip is measured (TCA/post-mortem) | **NEVER** | entry fills only |

**40 fills exist and 19 are sells — but not one sell was raised by an exit
rule.** Every close this fund has ever made was a human decision or a
reconciliation, never its own machinery firing.

## THE PLAN — one position, short-dated, chosen so the loop CLOSES in days

Under the **experimental-deployment authorization** (CEO, 2026-08-21): a small
position deployed as a MEASUREMENT, learning goal written down, alpaca venue,
exit rules committed BEFORE entry, notional capped, the CEO's click per order.
**Its learning goal is the machinery, not the return** — which is why the gate
is not the arbiter here and the strategy is deliberately dull.

| phase | what | who |
|---|---|---|
| **P0** | Pick the instrument and write the learning goal. One liquid ETF already in the universe; size **$40–60** (~2–3% of NAV, below every cap). Nothing about the choice should be interesting. | chair proposes, CEO agrees |
| **P1** | **Commit the exit rules BEFORE entry**: a `time` rule **3–5 trading days out** (so the loop closes this week, not on 2026-09-08) and a `loss_pct` rule. Verify both live in `/exits` with `superseded:false`, `triggered_at:null`. | chair |
| **P2** | Propose the BUY through the ordinary path. CEO clicks. Capture NBBO at submit. | chair → **CEO click** |
| **P3** | **Manage it, visibly**: it appears in the sleeve, on the desk, in risk, in the ticket lineage. A PM read while open. | chair |
| **P4** | **THE STAGE THAT HAS NEVER RUN — the exit fires.** On the dated day the rule triggers, the autopolicy evaluates it, and either auto-approves inside the v4 envelope or refuses with a reason. **Either outcome is a pass for this test**; a silent nothing is the failure. | machine |
| **P5** | The sell fills. Reconcile reads in_sync, residual inside bound. | machine → **CEO click if outside the envelope** |
| **P6** | **Measure the round trip**: realised P&L, TCA on both legs against the pre-registered prediction, and a post-mortem on the machinery — every stage that needed a human who should not have been needed. | chair + validator |

**Total CEO clicks: 2 (entry, and the exit if the envelope declines it).**
**Total capital at risk: ~$50.** **Wall-clock to a closed loop: ~1 week.**

## THE GAPS — what will bite, named in advance

- **G1. There is no gate→deploy path at all.** A candidate that clears the gate
  becomes a row on a desk; nothing turns it into a position. This test routes
  around G1 by using the experimental-deployment authorization instead. **The
  gap remains, and stage 6 stays unproven even if this test passes.**
- **G2. The autopolicy has never auto-approved anything — 0 approvals, 15
  declines.** P4 is the first time the envelope is asked to say yes. It may
  decline for a reason we have never seen; that is information, not failure,
  but it means **the exit may need a human click**, which is stage 8 only
  half-proven.
- **G3. An exit that fires may not reach an order.** Two rules have triggered
  in this fund's history and **zero produced a fill**. The 2026-08-24 entry
  freeze existed because triggered rules self-disarm on a drift check. That
  path has been repaired but **never exercised end to end**.
- **G4. Cost realism is unmeasured on a round trip.** We have entry-side fills
  only. The TCA pre-registration exists; the closing leg has never tested it.
- **G5. Nothing renders the position's own history.** Ticket-highway lineage is
  built but unmerged (blocked on today's adversary kill and its repair), and
  slices 7–8 — producer templates and the historical backfill — are unbuilt.
  **The test will be legible in the event log and not much else.**
- **G6. Weekend/market-closed handling is untested** for a dated exit.
- **G7. No post-mortem instrument exists for a closed round trip.** P6's
  method has to be written; it does not exist today.

## WHAT WOULD MAKE THIS TEST A FAILURE (written before it runs)

Not a loss — a $50 loss teaches nothing about machinery. It fails if **any
stage needs a human the design says it should not**, or if a stage produces
**silence rather than a refusal**. Both outcomes get written down; the second
is the one this firm treats as a defect.

## WHAT THIS IS NOT

It is not a bet, not an edge, and not evidence about any strategy. It is a
test of the fund's own plumbing, sized so that being wrong costs a rounding
error and being right proves the thing nobody has yet proved.
