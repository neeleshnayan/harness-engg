# The Krypton Book

Eighteen chapters, five parts, beginner to fund operator. This document is the
authoring brief: what each chapter asks, what already exists that carries into
it, what has to be written from nothing, and what was cut.

## The spine

Read the chapter questions in order and the book's real progression shows
itself. It is **not** finance → statistics → risk → operations, which is how
every other book on this shelf is organised. It is:

**economics → evidence → decision → control → capital → autonomy**

That is the distinctive claim of this book. The chapter titles are questions
precisely so they keep making it.

## The layout rule

Every chapter runs six beats, in order:

1. **The concept, plainly.** No jargon that has not been earned.
2. **The numbers, worked.**
3. **THE CASE** — a worked failure drawn from practice and **de-identified**.
4. **The operator's decisions** — what *you* click or set in this domain.
5. **An exercise** — run against your own book and your own records.
6. **What pro looks like**, closing with the ladder — every chapter, no
   exceptions:

   > **Novice** — what they *look at*.
   > **Operator** — what they *measure*.
   > **Pro** — what *decision* they make from it.

   Backtesting: novice looks at Sharpe · operator checks PIT, leakage and
   multiple testing · pro decides whether it is allowed through the gate.
   Execution: novice looks at fill price · operator measures slippage against
   decision price · pro changes routing, size or timing from the measured
   distribution. Risk: novice looks at volatility · operator measures
   concentration and tail loss · pro defines the conditions under which the
   position must be reduced or killed.

   The ladder is what makes the beginner-to-operator promise visible on every
   page rather than only in the table of contents.

Math at working level, no proofs. **Every chapter ends with a decision, not a
summary**, because the reader's job is clicking approve.

## The confidentiality rule

**No example may reveal how the firm is built or run.** This is a hard
constraint on beats 2, 3 and 5, and it overrides any pedagogical convenience.

Excluded, always:

- NAV, capital, position sizes, or any live book figure
- Turnover, universe size, or sleeve composition of anything running
- File paths, storage locations, service names, endpoints, repo layout
- Internal document filenames, chair or role names, approval-chain structure
- Gate architecture, thresholds, or the specific shape of the control stack

What survives — and it is the actual teaching value:

- The **failure mode**, and the reasoning that caught it
- The **discipline** applied, stated as a general rule
- **Illustrative** numbers, marked as such, chosen to be realistic not actual

A case reads *"a screen that excluded names on recent insider selling"* — never
*"our screen, at our size, on our stack."* If a paragraph would tell a
competitor something about how the firm operates, it comes out, even if it is
the most vivid paragraph in the chapter.

The book is written internal-first, but because no chapter depends on a private
figure or a named internal system, **it can be shown without redaction.** The
cost is real and worth stating: the vivid, specific version of every case is the
one that cannot be told. Write the general version well enough that it does not
need the specifics.

## Where the material comes from

Fifteen chapters of a first-principles hedge fund track already exist in
`neelesh-website`, with fourteen interactive figures that are machine-checked.
That track was built as a public course; this book is an operator's manual. The
concepts carry, the framing does not, and the strategy-taxonomy chapters mostly
do not.

- **CARRY** — the existing chapter is substantially the concept beat already.
- **FOLD** — existing material is split or merged into a new shape.
- **NEW** — nothing exists.

---

# Part I — Know the machine

### 1. Where does a fund's economic life actually come from?
*What a hedge fund is, as a business*

The governing question replaces a list of topics. Follow the money in one
unbroken chain, and the death modes fall out as the conclusion rather than as a
fourth subject:

**capital enters → positions create P&L → costs and fees remove P&L → NAV
determines who owns what → investors can redeem → the fund compounds, stagnates,
or dies.**

**FOLD** — existing ch4 *Fees, and what they actually cost* (figure
`fee-ratchet`; "where a third of the gain went"; what the high-water mark does
and does not do) carries the middle of the chain. Existing ch3 supplies the
opening and the liability picture.

**Keep legal structure short.** The onshore/offshore twin and the empty GP are
useful but must not turn this into a fund-formation chapter. The reader is not
becoming a fund lawyer. One aside, not a section.

**NEW:** the chain end to end, and the three ways funds die — blowup,
redemption, slow decay — arriving as its consequence. Slow decay is the one
nobody plans for, and the fee-ratchet arithmetic already has it.

### 2. What happens when it trades?
*Market structure and execution*

**The chapter's whole distinction:** *"what did that fill cost?"* is a research
question. Do not teach microstructure as an academic subject; teach the operator
to interrogate a fill:

- What was the **decision price**?
- What liquidity was available?
- Which venue did we choose?
- What did we actually pay?
- What would an alternative execution have cost?
- Was the slippage **predictable**?
- Was it our execution, or the market?

**Recurring concept introduced here:** every trade has a **forecasted cost** and
an **observed cost**. Chapter 7 turns that pair into portfolio economics.

**CARRY** — existing ch1 (figure `order-book`; "why the price on the screen is
not your price") **+** the mechanics half of ch15 ("three things that are all
called market impact"; "how large is impact really? two honest answers that
disagree").

### 3. How does it know what happened?
*The accounting spine*

NAV, event-sourcing vs broker equity, reconciliation, custody; why the ledger is
the truth and the broker is a comparison.

**NEW** — essentially all of it. Zero coverage of reconciliation, event sourcing
or NAV construction in the existing track. Teach the *pattern*, not this firm's
implementation of it.

**CASE:** a ledger that silently drifted from the broker's own record.

### 4. What can it trade?
*Instruments and their mechanics*

**Organise by what can go wrong, not by textbook definition.** For every
instrument, four questions in order:

> What is it? → How does it make money? → How can it lose money? → **How can the
> plumbing fail?**

That framing is what makes the shorting section land. Borrow, buy-in, and the
**backwards stop** — a stop on a short that fires *into* the loss — teach
something far deeper than short mechanics:

> **A risk control can itself become a source of risk.**

That sentence is the bridge into chapter 13, and it should be planted here.

**FOLD** — the instrument half of ch1 **+** the shorting mechanics in ch5.

---

# Part II — Know where returns come from

### 5. Is this alpha?
*Risk premia vs alpha* — **be ruthless here**

The question is not "what is alpha?" but: **what evidence would convince us that
this return deserves to be called alpha?** Establish the ladder the reader
climbs every time they meet a return:

**raw → benchmark-relative → factor-adjusted → risk-adjusted → residual claim of
skill**

**FOLD** — ch2 *Money, rates, and the price of time* (figure `price-of-time`;
real vs nominal) **+** ch5 *What hedged originally meant* ("beta measured
how?") **+** ch10's "removing the part you cannot control removes its rewards
too".

**Bring in from the cut list:** the trend/straddle result. A trend rule
reproduces a long straddle on a market with *zero edge* — mean return +0.13%,
beta −0.002. The lesson, and a superb setup for Part III:

> **A strategy can have an interesting payoff shape without having an edge.**

> **HOLD before carrying the secondary result.** Review found "curvature falls
> as real edge appears" to be a units artifact: the quadratic coefficient scales
> as 1/σ of the move, so at zero edge throughout, raising monthly vol from 3% to
> 12% moves it 3.54 → 0.89 while the slope of the V's arms is constant to four
> decimals. The *primary* result (zero mean, zero beta, a V payoff) is solid and
> reproduces exactly. Carry that; leave the trade-off sentence and the
> `trend-smile` figure until the source is fixed.

### 6. How many bets are there?
*Portfolio math that actually binds*

**Danger: this is the chapter most likely to become a quant textbook.** Vol,
correlation, covariance, eigenvalues, effective bets, IC, breadth, IR — together
they turn into "here is portfolio theory". Hold the operator's chain instead,
four links and nothing else:

> How many **independent** bets do I actually have? → How good is each bet? →
> How much **evidence** do I have? → What aggregate risk does that imply?

`IR = IC × √breadth` is an **operator constraint**, not a formula to admire.

**Book-wide rule, introduced here:**

> **If you cannot state your effective number of bets, you do not yet know what
> evidence threshold you should demand.** Declare k.

**CARRY, three chapters' worth** — ch6 (figure `vol-drag`; log returns) **+**
ch7 (figure `diversify`; the floor at σ√ρ) **+** ch9 (figure `spectrum`; **"how
many independent bets the market is offering"**, already the effective-bet count,
arriving from the eigenvalue side).

**NEW:** `IR = IC × √breadth` stated explicitly and joined to the spectrum, so
"declare k" gets a *measured* answer rather than an asserted one.

**Demoted, not deleted:** ch8 *The efficient frontier, and why it lies* becomes
an aside — *why we do not run an optimiser*.

### 7. What does it cost?
*Costs as first-class citizens*

**Make the relationship to chapter 2 explicit, or the two will repeat each
other:**

| | |
|---|---|
| **Chapter 2** | *measurement* of transaction cost — what did this trade cost? |
| **Chapter 7** | *economics* of transaction cost — what does it do to the strategy? |

**CARRY, nearly intact** — ch15 (figures `capacity`, `capacity-point`,
`turnover-cube`; "alpha squared over turnover cubed"; "the cost comes out of the
Sharpe at exactly the same rate"). The closest fit in the whole merge.

### 8. What are we actually exposed to?
*Factor exposure and regimes*

**Central idea:** a portfolio can be market-neutral and still be **extremely
exposed**. Introduce **hidden beta** by name, then walk the layers:

market beta → factor beta → sector/country/style → crowding → regime dependence
→ hedge cost → residual exposure

**CARRY** — ch10 (figures `crowding`, `hedge-breakeven`, `hedge-cost`; **"August
2007, in the numbers its own authors published"**). The 2007 material is perfect
here because it shows that *hedged does not mean safe*.

---

# Part III — Deciding whether it's real

*The book's climax, not its middle. The reader is not learning statistics for
its own sake — they are deciding whether to allocate capital. Hence "deciding".*

Chapters 9–11 are mechanically progressive.

### 9. Can I trust the data and the experiment?
*How backtests lie* — **WRITTEN** → `book/ch09-how-backtests-lie.md`

Overfitting, survivorship, point-in-time discipline, look-ahead;
pre-registration as the antidote.

**CARRY** — ch14 *Data, and the lies inside it* (figure `backtest`;
survivorship 5.9% → 8.0%; PIT correlation 0.83 costing Sharpe 1.25 → 1.04; the
look-ahead demonstration returning **Sharpe 202 on data containing nothing**).
All simulation results from the public track, so they carry freely.

**CASE:** an insider-exclusion screen whose headline was killed by a timing
defect, and the pre-registration written to test what survived.

### 10. Can I trust the statistical evidence?
*Statistics for verdicts*

**Scope control is the whole risk here.** Do not write "statistics you should
know". Write:

> **What can make apparently strong evidence disappear?**

Then every tool answers one named failure mode:

| failure mode | tool |
|---|---|
| autocorrelation → inflated precision | Newey–West |
| non-normality → misleading Sharpe | higher moments |
| apparent effect without economic content | placebo / date-shift |
| winner's curse across many tries | multiple testing |
| is the Sharpe above a meaningful threshold? | PSR |
| uncertainty around the estimate | sample size — **a count is not a confidence interval** |

**Deflated Sharpe: teach it properly or cut it.** A half-mentioned methodology
is worse than an omitted one, and it currently sits in the old track's reading
list without ever being taught — the worst of both.

**CARRY** — ch16 (figure `noise-sharpe`; **"the Sharpe ratio and the
t-statistic are the same number"**; "how many tries to fake a Sharpe of 2").

**CASE:** an attribution audit in which a reported count was mistaken for a
confidence interval.

### 11. Can I trust the decision process?
*The gate as an institution* — **give this more room than the outline implies**

Where the reader crosses from *"I know statistics"* to *"I know how a
professional fund makes decisions."* The central distinction:

> **A test does not prove a strategy is true. It determines whether the strategy
> is permitted to advance.**

That is an institutional concept, not a statistical one. Teach **certification
boundaries** as a five-question form applied to every gate:

- What does this test **establish**?
- What does it **not** establish?
- What decision does **passing unlock**?
- What decision does **failing block**?
- What evidence can **overturn** the decision?

**NEW** — one passing mention of walk-forward exists and nothing else. Teach the
form; keep any particular firm's gate shape out of it.

---

# Part IV — Know how it can hurt you

*The progression is **understand → constrain → survive**.*

### 12. What can happen?
*Measuring risk*

Drawdown, expected shortfall, concentration, correlation stress — measured,
never assumed.

**FOLD** — the drawdown half of the trend chapter carries directly: the table
for a fund at 12% annual vol, the result that Sharpe 0.4 → 1.0 moves the median
five-year drawdown only 20.9% → 15.6%, and the runnable underwater simulation.
Also fold ch11's `convergence` figure and "being right about the destination
says nothing about the journey".

> **Note from review:** state the **marking frequency**. The 91%-underwater
> figure is on daily marks; the same fund is underwater 65% of the time on
> monthly marks, and investors redeem on monthly statements. Use the monthly
> number for any business claim.

**NEW:** expected shortfall and concentration.

### 13. What prevents it?
*Controlling risk* — **a signature chapter**

Do not just teach kill switches. Teach **control architecture** as a pipeline:

> trigger → state → action → authority → logging → verification → recovery

Then **fail-open vs fail-closed**, and the sentence that belongs somewhere
prominent:

> **A control isn't real until you've observed it fire under the condition it
> was designed to handle.**

This is one of the places the book teaches something a conventional hedge fund
textbook simply cannot.

**CASE:** a risk-envelope revision that introduced a hazard on the short side —
the control becoming the risk. Pair with chapter 4's backwards stop.

**NEW** — all of it.

### 14. What if the prevention fails?
*Operational risk*

**This is not an IT-risk chapter.** It is:

> **The risk of believing your controls are working when they aren't.**

That framing is what makes the phantom-price case powerful rather than
anecdotal. The unwired kill switch, reconciliation drift, silent failure modes;
why a control that reports nothing is worse than no control.

**CASE:** a phantom price that propagated because the control watching for it
reported nothing. *(Note for the author: the original brief called this a
phantom-*fill* incident; the record is a phantom *price*. Confirm whether these
are one event or two.)*

**NEW** — all of it.

---

# Part V — Know how to run it

*An arc, not four independent management chapters.*

### 15. Who is allowed to decide?
*Governance*

Separation of duties, approval chains, versioned thresholds, provisional
decisions, the challenge discipline. **NEW** — all of it.

### 16. What deserves capital?
*The allocator's craft — the synthesis chapter*

**Capital as a scarce resource.** The CIO is not primarily picking strategies;
the CIO is deciding:

> **Which marginal dollar produces the best risk-adjusted future outcome?**

Then the inputs to that one decision: expected return · marginal risk ·
correlation · capacity · liquidity · confidence and evidence · operational
complexity · strategic optionality · kill/scale.

This chapter should feel like the reader has finally been handed **the CIO's
screen** — it is where Parts II, III and IV are cashed in at once.

**NEW** — all of it.

### 17. How far can we scale?
*Scaling capital — the permission ladder*

Do not write "at $2k, X; at $10k, Y". **Make each rung require new evidence:**

| capital | what must be proven |
|---|---|
| $2k | technical validity |
| $10k | execution validity |
| $100k | portfolio validity |
| $1M+ | capacity validity |
| $10M | institutional / market-impact validity |

Thresholds are firm-specific; the ladder is the idea.

> **Scaling is not multiplying position size. Scaling is acquiring permission to
> take on a new class of risk.**

**FOLD** — chapter 7's capacity machinery is the engine; the ladder and its
preconditions are new.

### 18. What happens when decisions become agentic?
*The agentic fund*

Not "AI in hedge funds" — **the logical endpoint of the entire book.** What
changes in principle when the decision-makers themselves become scalable
software: adversarial review at industrial scale, the decision log as a dataset,
the two-layer rule.

**NEW** — and the chapter where the confidentiality rule bites hardest: teach
what changes in principle, never how any particular firm wired it. The honest
closer from the public track's planned finale belongs here as the last beat.

---

## What was cut, and why

| Cut | Why |
|---|---|
| ch8 *The efficient frontier, and why it lies* | An optimiser chapter for an operator who does not run one. Survives as an aside in chapter 6. |
| ch11 *Relative value, and the arbitrage that isn't* | Strategy taxonomy. Its LTCM material is about leverage and forced exit, so the useful half moves to chapter 12. |
| ch12 *Trend* as a strategy chapter | Same reason. The straddle result moves to chapter 5, the drawdown table to chapter 12. |
| ch13 *Event-driven and merger arbitrage* (planned) | Not in this book. The `dealspread` model — an implied probability read out of a market price — is a good device for chapter 10 if a home is wanted. |
| The `spread` blocks throughout | "The same idea in six other fields" is public-course texture. Beats 3 and 5 replace it. |
| The `ground` blocks | Keep only where they earn it. An operator does not need to be told they have met an order book buying concert tickets. |

## Writing order

Not numerical. Evidence first — that is where the operator's role concentrates,
and those chapters have the most existing material:

**9 → 10 → 11 → 3 → 13 → 14 → 12 → 16 → 17 → 15 → 18**

Part I and II chapters (1, 2, 4, 5, 6, 7, 8) slot in wherever wanted, since
existing material does most of their work.
