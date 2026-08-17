# Deploying $500, end to end

**Mandate: make money without risking more than we can chew.**

The point of starting at $500 is not the money. It is to complete **one full cycle
— decide, size, enter, mark, monitor, review, exit — with every step measured**,
before anything larger depends on machinery nobody has driven all the way round.

Read the success criterion carefully, because it is the thing most likely to be
misremembered later:

> **This exercise succeeds if the loop completes and every step was measured. It
> does not succeed by making money, and it does not fail by losing it.**

$500 held for a few weeks carries no statistical information about edge. Anyone
who concludes "it worked" from a profit here has learned nothing and will size up
on noise. What the exercise *can* establish is that the machinery is trustworthy:
that a position can be entered under a pre-committed rule, marked from the event
log, monitored against limits that actually fire, reviewed on a schedule, and
exited for a reason written down in advance.

---

## 1. Pre-registration — written before the click, not after

Everything in this section must be filled in and committed to the repo **before**
the first order. That ordering is the whole discipline: once a position exists,
every subsequent judgement about it is contaminated by owning it. Writing the exit
down beforehand is the only defence, and it is cheap now and impossible later.

| field | commitment |
|---|---|
| **Sleeve name** | *(to fill)* — one strategy id, so attribution and divergence can see it |
| **Claim** | Alpha or **beta**? If beta: no edge is being claimed and none will be reported |
| **Instruments** | ≥2 names (forced by the position cap — see §2) |
| **Entry rule** | The condition that justifies buying, stated so someone else could apply it |
| **Size per name** | And the method: equal weight, inverse-vol, or explicit |
| **Exit rule — loss** | The price/drawdown at which this is closed, **no discretion** |
| **Exit rule — time** | The date at which it is closed or explicitly re-decided |
| **Exit rule — thesis** | What observation would mean the reason for holding is gone |
| **Review cadence** | Daily mark, weekly written review |
| **What would falsify it** | The result that would make us say this was a mistake |

The last row matters most and is the easiest to skip. A position with no
falsification condition cannot be wrong, only unlucky — and a fund that can never
be wrong learns nothing.

## 2. What the harness enforces today, with the arithmetic

These are not recommendations. They are constraints already in code, and they
**shape the deployment before any preference does**. Against NAV $2,030.14:

| limit | value | what it means for $500 |
|---|---|---|
| `max_order_notional_pct` 15% | $304.52 per order | **$500 needs at least 2 orders** |
| `max_position_pct` 20% | $406.03 per name | **$500 needs at least 2 names** |
| `max_strategy_pct` 40% | $812.06 | a $500 sleeve fits as one strategy |
| `min_cash_pct` 5% | $101.51 floor | after $500, cash is $346.92 = 17.1% — OK |
| `min_effective_bets` 2.0 | correlation-adjusted | two names that move together count as one bet |
| `max_avg_correlation` 0.75 | | a pair above this trips the monitor |

**A single-name $500 position is rejected before it reaches you.** That is the
pre-trade gate doing its job, and it is worth knowing the machine already forbids
the simplest version of this.

**One number to weigh deliberately:** gross exposure goes from **58.3% to 82.9%**
of NAV. That is the largest single change this makes, it is squarely the "how much
are we chewing" question, and the regime throttle was last seen asking for
*reduced* gross. Check `/risk/throttle` before committing.

Kill switches that will act without asking:

- NAV **−10% from peak** → trading halts
- NAV **−4% in a day** → trading halts
- a position **15% underwater** → **alarm only, not an exit**

That last one is the gap.

## 3. What the harness cannot enforce — and must, for this to be honest

**There is no exit machinery.** No stop, no take-profit, no time-exit, nothing
that holds us to a pre-registered exit rule. `underwater_pct` raises an alarm and
then waits for a human who is, by then, a human with a position.

This is the one piece that has to be built before "managed end to end" is a true
description rather than an aspiration. Concretely:

1. **Record the exit rule as an event** at deployment, so it is auditable and
   cannot be quietly revised. A rule stored in a doc is a rule; a rule in the
   event log is a commitment.
2. **Evaluate it on every mark** and, when it triggers, put a closing order in the
   approval queue with the rule that fired quoted in the proposal. The human still
   clicks — the machine's job is to make the pre-committed exit *unmissable*, not
   to trade.
3. **Log any override.** If the rule fires and the position is kept, that decision
   gets recorded with a reason. Overrides are allowed; silent overrides are how a
   stop-loss becomes a story about why this time is different.

Two smaller gaps, worth naming:

- **Divergence watch requires a backtest on record.** A declared-beta sleeve has
  none, so it would be invisible to `divergence.compare`. Either give the sleeve an
  explicit expected-return statement to diverge *from*, or accept it is unmonitored
  on that axis and say so.
- **TCA exists and should be used.** Compare the fills against the 5bps slippage
  assumption; at $250 per order in liquid names the real cost may be materially
  different, and this is the first chance to measure it with real fills rather than
  assume it.

## 4. The cycle, and what gets measured at each step

| step | action | measured by | already works? |
|---|---|---|---|
| Decide | Entry rule, pre-registered | this document, committed | yes |
| Size | ≥2 names, within caps | pre-trade gate | yes |
| Enter | Orders to the approval queue, human clicks | event log | yes |
| Mark | NAV folds from the event log | `/nav`, chain verify | yes |
| Cost | Fills vs the 5bps assumption | TCA | yes |
| Monitor | Limits, correlation, ES, drawdown | risk monitor | yes |
| Exit | Pre-registered rule fires → proposal | **nothing** | **no — build it** |
| Review | Weekly written note, kept whatever the outcome | this repo | yes, by habit |

Seven of eight steps are instrumented. The missing one is the exit, which is also
the step where discipline is hardest and most valuable.

## 5. Decisions that are yours

I have deliberately not chosen these, because they are mandate decisions rather
than analysis:

1. **Alpha or beta?** Nothing has passed a trustworthy gate, so an alpha claim has
   no support today. A declared-beta sleeve is defensible and honest; an
   undeclared one is how a fund starts lying to itself.
2. **What to hold**, subject to ≥2 names and the correlation limit.
3. **Whether to fund the $500 from cash** ($346.92 left, comfortably above the
   floor) **or from selling part of the existing book** — which interacts with the
   three failed strategies and the one remaining day trade.
4. **Whether 82.9% gross is more than we want to chew**, given the throttle's last
   reading.

## 6. Recommended order of work

1. Build the exit-rule mechanism (§3). Without it this is not end-to-end.
2. Fill in the pre-registration (§1) and commit it.
3. Deploy in ≥2 orders across ≥2 names.
4. Run one full week: daily marks, one written review, TCA on the fills.
5. Then, and only then, decide whether the loop earned the right to a larger sleeve.

Step 1 before step 3 is not fussiness. Deploying first and building the exit
afterwards means the first exit decision gets made by a human holding a position,
which is precisely the failure mode the pre-registration exists to prevent.
