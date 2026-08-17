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
| **Sleeve name** | `sleeve_beta_500` — one strategy id, so attribution and divergence can see it |
| **Claim** | **Declared beta.** No edge is claimed and none will be reported. Any profit is market exposure, and will be described that way |
| **Instruments** | **2 broad exposures**, chosen from the measured shortlist in §7. Not single names — see §6 |
| **Entry rule** | Market order at the open on the session following approval. Deliberately trivial: the entry is not what is under test |
| **Size per name** | **$250 equal weight** (12.3% of NAV each, inside the 20% cap; 2 orders, inside the 15% order cap) |
| **Exit rule — loss** | **1.5σ of the instrument's own measured 21-day volatility, frozen as a percent** at commitment. Per-instrument values in §7 |
| **Exit rule — time** | **21 calendar days from fill**, at which point it is closed or explicitly re-decided in writing |
| **Exit rule — thesis** | "This sleeve exists to test machinery, not to express a view. If the loop has been measured end to end, the reason for holding is gone." Answered at every review |
| **Review cadence** | Daily mark from the event log; one **written** review per week, kept whatever the outcome |
| **Cost of information (worst case)** | **~$32** across both stops (§7), = 1.6% of NAV against a 10% drawdown limit |
| **What would falsify it** | Four conditions, none of them P&L — see below |

**Falsification.** The sleeve has failed if any of these occur, and *only* if:

1. An exit rule fires and **no closing proposal appears in the approval queue** —
   machinery failure. This is the primary thing under test.
2. **TCA cannot compare the fills against the 5bps slippage assumption** —
   measurement failure. We would then be assuming our costs, which is the habit
   this fund exists to break.
3. **NAV folded from the event log diverges from broker equity** beyond a stated
   tolerance — accounting failure. The log is the truth; a gap means the truth and
   the world disagree and we do not know which is wrong.
4. **A week passes with no written review** — discipline failure, and the most
   likely of the four.

Losing $32 is not on that list. Neither is making $32. Read the success criterion
at the top of this document again if either feels wrong.

The falsification row matters most and is the easiest to skip. A position with no
falsification condition cannot be wrong, only unlucky — and a fund that can never
be wrong learns nothing.

## 2. What the harness enforces today, with the arithmetic

These are not recommendations. They are constraints already in code, and they
**shape the deployment before any preference does**. Against NAV **$2,026.89** and
cash **$846.92** (41.8%), measured 2026-08-18:

| limit | value | what it means for $500 |
|---|---|---|
| `max_order_notional_pct` 15% | $304.03 per order | **$500 needs at least 2 orders** |
| `max_position_pct` 20% | $405.38 per name | **$500 needs at least 2 names** |
| `max_strategy_pct` 40% | $810.76 | a $500 sleeve fits as one strategy |
| `min_cash_pct` 5% | $101.34 floor | cash is $846.92, so **no trim is needed to fund this** — see §6a |
| `min_effective_bets` 2.0 | correlation-adjusted | two names that move together count as one bet |
| `max_avg_correlation` 0.75 | | a pair above this trips the monitor |

**A single-name $500 position is rejected before it reaches you** — 24.7% of NAV
against a 20% cap. That is the pre-trade gate doing its job, the machine already
forbids the simplest version of this, and §5b turns it into a free test.

**On gross exposure.** An earlier draft of this document warned that gross would go
from 58.2% to 82.9% and flagged it as the largest single change. That is true only
if the sleeve is funded purely from cash. Funded alongside retiring the failed
strategies — which is the plan — **gross stays flat near 58%**, and the concern
dissolves. Check `/risk/throttle` before committing regardless: it was last seen
asking for 77% of normal gross at a turbulence reading in the 87.9th percentile,
and it is display-only, so nothing enforces it but us.

Kill switches that will act without asking:

- NAV **−10% from peak** → trading halts
- NAV **−4% in a day** → trading halts
- a position **15% underwater** → **alarm only, not an exit**

That last one is the gap.

## 3. The exit machinery — built since this document was first written

> **CORRECTION 2026-08-18.** An earlier revision of this section claimed the exit
> rule "is evaluated on every mark" and that a fired rule "puts a closing order in
> the approval queue". ~~Both halves were false.~~ `EXIT_RULE_TRIGGERED` was
> emitted by no code in the repository; `ExitRules.check()` was a pure read
> reachable only from an endpoint nothing called. The mechanism was verified by
> calling it *by hand*, and that was read as the loop being closed.
>
> The consequence was worse than a wrong sentence: §1's primary falsification
> condition — "an exit fires and no closing proposal appears in the queue" — was
> **guaranteed true** before a single order existed. The test could not have been
> passed.
>
> Now genuinely wired (`ExitRules.enforce()`, ticked from `main.py::_scheduler`)
> and verified *unattended*: seq 170 `ExitRuleSet` → 171 `OrderProposed` → 172
> `ExitRuleTriggered`, chain 172/172, with nobody calling an endpoint. The
> struck-through claim is left visible rather than edited away, so the record shows
> what we believed and when. See `docs/FUND_GENESIS.md` stage 02.

The mechanism exists (`app/fund/exitrule.py`) and behaves as follows — three events
verified live, one rule fired with its reason quoted, one holding, one override
recorded:

1. **The rule is an event** (`EXIT_RULE_SET`), recorded at deployment. That single
   choice is what makes it a commitment: a rule in a document can be edited by the
   person it constrains and nobody would know; a rule in the append-only log can
   only be superseded, and the supersession is visible.
2. **It is evaluated on every mark** (`EXIT_RULE_TRIGGERED`), and a fired rule puts
   a closing proposal in the approval queue with the rule quoted. The human still
   clicks — the machine's job is to make the pre-committed exit *unmissable*, never
   to act on it.
3. **Overrides are recorded with a reason** (`EXIT_RULE_OVERRIDDEN`). Overrides are
   allowed; silent ones are not. An exit that can be ignored without a trace is not
   an exit, it is a story about why this time is different.

"Could not check" is reported separately from "not fired", because a missing mark
must never read as a position in good standing.

Two smaller gaps, still open:

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
| Exit | Pre-registered rule fires → proposal | `exitrule.py`, event log | **yes — built since §3** |
| Review | Weekly written note, kept whatever the outcome | this repo | yes, by habit |

> **CORRECTION 2026-08-18.** This table previously read
> ~~"All eight steps are now instrumented"~~ on the strength of the exit mechanism
> existing. Existing and being *wired* are different claims, and only the second one
> licenses that sentence. Two rows were wrong at once: `Exit` was unreachable, and
> `Monitor` depended on `RiskMonitor.run()`, which had **zero callers** — so the
> documented −10% drawdown and −4% daily-loss halts would not have fired either.
> Both are scheduled now, with a heartbeat so a *missing* tick is visible as an
> absence rather than as silence (`GET /fund/liveness`).

**All eight steps are instrumented and, as of 2026-08-18, actually scheduled.** The
exit was the last one, and it is also the step where discipline is hardest and most
valuable — which is why it was built before any order rather than after the first
one. Deploying first and building the exit afterwards would have meant the first
exit decision was made by a human holding a position, which is precisely the
failure mode the pre-registration exists to prevent.

The weakest remaining row is **Review**, marked "yes, by habit" — meaning nothing
enforces it, and a missed week is one of the four falsification conditions in §1.
Of the four, it is the most likely to be the one that trips.

## 5a. Why the stop is in sigma and not in percent

The first draft of this document was going to say "8% loss stop." The arithmetic
says that is not a stop at all, and the way it fails is instructive.

Measured annualised volatility on the current book, 172 sessions to 2026-08-17,
converted to a 21-day sigma (`σ_ann × √(21/252)`):

| name | ann vol | 21d σ | what an 8% stop is | P(fires on noise, path) |
|---|---|---|---|---|
| INTC | 83.7% | 24.2% | **0.33σ** | ~74% |
| SOFI | 53.6% | 15.5% | 0.52σ | ~60% |
| NVDA | 37.6% | 10.8% | 0.74σ | ~46% |
| GLD | 31.2% | 9.0% | 0.89σ | ~37% |
| SPY | 13.4% | 3.9% | **2.0σ** | ~4% |

The same number is a real stop on SPY and a coin flip on INTC. A flat percentage
across instruments of different volatility produces the *feeling* of discipline
plus a stream of meaningless exits — which we would then be tempted to explain,
and the explanations would be stories.

**So the distance is chosen in σ. But the commitment is frozen as a number.**

That second half matters as much as the first. A rule reading "sell at 1.5σ"
requires recomputing σ at the moment of decision, and σ is arguable — which hands
the person holding a losing position exactly the lever this mechanism exists to
remove. "Sell at −6.7%" cannot be relitigated. So σ selects the number at
pre-registration, and then the number is what we are held to.

**1.5σ** is the chosen distance: roughly a 1-in-7 chance of firing over three
weeks. Tight enough that the machinery genuinely gets exercised, loose enough that
firing is not the expected outcome. It is a judgement, and it is registered as one
in `app/fund/judgement.py`.

## 5b. Two limits that will NOT be tested, said plainly

Measured for every candidate pair in §7: the book's effective bets land between
**3.66 and 4.39** against a floor of 2.0, and average pairwise correlation between
0.13 and 0.17 against a 0.75 ceiling. Nothing we would sanely deploy comes close
to threatening either.

That is a good property of the book and a gap in the test. Both limits will pass
without having been exercised, and a limit that has never fired is a limit nobody
has verified. Recorded here so that "the risk controls passed" is never later read
as "the risk controls work."

**One control can be tested for free.** A single $500 order in one name is 24.7%
of NAV against a 20% position cap, so the pre-trade gate is obliged to reject it.
Submitting it deliberately exercises a control we have never watched fire, costs
nothing, and never reaches an approval click because it dies before one. Do this
first, and record the rejection.

## 6. Why broad exposures rather than single names

A declared-beta sleeve holding a single stock is a stock pick wearing a label. The
idiosyncratic component is not beta to anything, so the claim on the tin would be
false in the one place we have promised to be careful — and the whole reason for
declaring beta was to avoid asserting an edge we cannot support.

It also happens to make the vol arithmetic in §5a behave: broad exposures cluster
at 4–26% annualised, so a 1.5σ stop lands at 2–11%, which is a sane distance to
commit to and a bounded dollar risk.

## 6a. The trim is not a funding decision

Worth separating, because these were conflated: cash is **$846.92, 41.8% of NAV**,
and the floor is 5% (~$101). **$500 needs no trim to fund it.**

Retiring the three failed strategies is a separate decision — about not holding
things that fail the gate — which *also* keeps gross flat near 58% instead of
pushing it to 82.9%. Two decisions that happen to be compatible, and the earlier
worry about 83% gross dissolves once they are kept apart.

## 7. The measured shortlist

Candidates are liquid broad exposures chosen by *category* — rates, small cap,
developed international, EM, credit, defensive sectors, commodities, real assets —
not by any view about returns. All 12 have full 249-session history to 2026-08-17.
Ranked by the book's effective bets after adding $250 to each name and trimming
$500 pro rata:

| pair | book effective bets | avg pairwise corr | pair corr | stop A | stop B | $ risk at stop |
|---|---|---|---|---|---|---|
| XLV + DBC | 4.39 | 0.130 | −0.21 | 6.7% | 8.7% | $38.63 |
| DBC + VNQ | 4.19 | 0.138 | −0.21 | 8.7% | 6.0% | $36.82 |
| XLU + DBC | 4.18 | 0.137 | −0.05 | 6.5% | 8.7% | $38.09 |
| TLT + DBC | 4.03 | 0.129 | −0.41 | 4.0% | 8.7% | $31.91 |
| XLV + XLU | 4.03 | 0.137 | 0.27 | 6.7% | 6.5% | $32.98 |
| TLT + XLV | 3.83 | 0.137 | 0.20 | 4.0% | 6.7% | $26.81 |
| IEF + XLV | 3.66 | 0.145 | 0.27 | 2.0% | 6.7% | $21.75 |

Every row clears every limit. **The instrument choice is the operator's** — this
table exists so that the choice is made against measured properties rather than a
feeling, not to make it. Once two are picked, the stop percentages above are
frozen into `POST /fund/exits` before any order is submitted.

## 7a. The second child: an alpha sleeve, constituted now and fed later

The beta sleeve is one organism. An alpha sleeve is its sibling, and having two is
what turns a deployment into a selection mechanism — neither one can be graded in
isolation, but they can be graded against each other.

The blocking fact: **nothing has passed the gate.** All three deployed strategies
fail it, and one (INTC) has not traded at all in 2026 — 226 sessions, zero orders.
So an alpha claim has no support today, and a sleeve asserting one would be the
fund's first lie.

The resolution is that the child is **constituted now and funded at $0**:

| field | commitment |
|---|---|
| **Sleeve name** | `sleeve_alpha_500` |
| **Claim** | Alpha. Explicitly falsifiable, and unfunded until it earns funding |
| **Initial capital** | **$0** |
| **Admission criterion** | One strategy passes **gate v3** with a written verdict on record. That is its birth condition, and it is the only one |
| **Capital on admission** | $250, matched against the beta sibling |
| **Retirement criterion** | See below — and it is deliberately *not* the admission criterion run backwards |

**Admission is the gate; retirement is the sibling comparison.** Keeping these
separate is the whole design, and collapsing them is the trap.

If we admitted a strategy because it beat the beta sleeve in live trading, we would
be selecting on three weeks of noise — and if we kept spawning children and
retaining whichever beat beta, that is data mining with extra steps. It is the same
multiple-testing error the gate's PSR floor exists to prevent, smuggled back in
through the live book. Three weeks of $250 carries no information about edge.
Admission therefore stays with the gate, which is pre-registered and statistically
aware.

Retirement is where the sibling comparison belongs, because it operates over
horizons long enough to mean something and it asks the right question. The bar is
not "did the alpha sleeve make money" — a rising market makes both children money.
It is:

> **Did the alpha sleeve beat its beta sibling, net of costs, over enough
> independent reviews to be distinguishable from luck?**

That is a real fitness test. It has a control group, it is net of the costs TCA
measures, and it cannot be passed by simply being long during an up month. A
strategy that clears the gate and then fails to beat plain market exposure has
earned nothing, and its capital returns to the beta sleeve.

**What this does not do yet is evolve.** Two siblings with a comparison rule is
selection with a population of two — the minimum that can be called selection at
all, and honestly labelled as such. Variation, inheritance and specialisation
across a real population are the layer after this, and they are gated on the
compute constraint (~1,000 candidates ≈ 230 hours on one container slot), not on
the design. The pre-screen that would fix that is the next build.

## 8. Decisions that are yours

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

## 9. Recommended order of work

1. Build the exit-rule mechanism (§3). Without it this is not end-to-end.
2. Fill in the pre-registration (§1) and commit it.
3. Deploy in ≥2 orders across ≥2 names.
4. Run one full week: daily marks, one written review, TCA on the fills.
5. Then, and only then, decide whether the loop earned the right to a larger sleeve.

Step 1 before step 3 is not fussiness. Deploying first and building the exit
afterwards means the first exit decision gets made by a human holding a position,
which is precisely the failure mode the pre-registration exists to prevent.
