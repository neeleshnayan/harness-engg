# Krypton Fund — roadmap

> **Sprint update, 2026-08-17 (evening).** #26 and #33 are done; #31 is done;
> #27 is half done and produced the sprint's headline finding — **gate v1 passed
> random noise 50% of the time**, so the gate is now v2. #28's code is in and its
> sweep has not been run; #29 is untouched. Details in
> `docs/CALIBRATION_2026-08-17.md` and `docs/SURVIVORSHIP_2026-08-17.md`.
>
> One item was found that was not on this list at all: the durability snapshot
> was not merely unscheduled, it was **broken** — it called a method the local
> Firestore shim did not have, so the fund had never had a working second copy of
> its event log. Now scheduled, fixed, and verified (`behind_by: 0`).

*2026-08-17. Supersedes the previous roadmap, most of which either shipped in a
different shape or was reversed by later decisions (notably: LEAN is now the
engine of record — the "Alpaca replaces LEAN" direction is dead). What still
lives from it is carried forward at the bottom rather than silently dropped.*

*Pairs with `docs/DEMO_RUNBOOK.md` (what exists) and the Harness Thesis
(where it goes). Numbering continues the working queue: #26–#36.*

---

## Where we stand

The machine works. In one day it built a strategy, watched it beat its
benchmark in-sample, killed it on the holdout, and surfaced four bugs that had
been flattering every candidate before it. Jobs, sweeps and verdicts survive a
restart. The loop closes: filing sentence → judgement → candidate → verdict →
back to the map.

Which means **the bottleneck has moved**. It is no longer infrastructure — it
is edge discovery. Five candidates have gone down the belt; zero passed. The
book still holds three strategies that predate the gate and would fail it. The
harness can now kill a bad idea in an afternoon; nothing yet generates good
ideas at volume.

**The metric for this phase is truthful verdicts per week — not features
shipped, and not gate passes.** A pass is the outcome we hope emerges from
volume and honest inputs. The moment a pass becomes the *target*, the gate
becomes the thing under optimization, and we will be fooling ourselves with
extra steps.

---

## The critical read — what is weak today

Written the way we would review someone else's fund, because that is the review
that matters. Each weakness names where it lands in the plan; two of them
produced work items the plan would otherwise not have contained.

1. **The gate has never been calibrated.** It has failed everything it judged.
   That is consistent with high standards — and equally consistent with a bar
   nothing could clear on two years of daily data. We do not know its false
   positive rate (a null strategy that passes would expose a leak) or its false
   negative rate (a known injected edge that fails would expose an unclearable
   floor). "The gate works" is currently an assumption. → **#27**

2. **One holdout window is one draw.** All retention numbers come from a single
   test window (2026 YTD) in a single regime — small caps up 37%. A verdict
   from one window is weak evidence in either direction, and every candidate so
   far has been judged on exactly that window. → **#27**

3. **The backtest feed is single-source and unverified.** Every verdict rests
   on Yahoo-derived bars nobody has cross-checked. A quiet adjustment error —
   a missed split, or price-return where total-return is needed — looks exactly
   like alpha or its absence. The universe contains a REIT and other
   dividend-heavy names, so the total-return question is not hypothetical.
   Polygon's adjusted bars now make the cross-check nearly free. → **#27**

4. **The cost assumption is a guess wearing a constant's clothes.** 5bps
   slippage, everywhere, for names with $2–25M ADV — where real spreads can be
   multiples of that. Breakeven sweeps bound the damage but have never
   confronted the number with data. Per-bar vwap now gives an empirical
   proxy for what a session's trading actually paid. → **#27**, then **#35**

5. **The research loop is built, not lived.** 376 observations, exactly one
   review — made today, by the person testing the feature. The map, evidence
   panel and provenance report are only as honest as their daily use; unused,
   they are a museum with good signage. The measure is reviews per week, and it
   currently rounds to zero. → **#31**, and the cadence in **#30**

6. **The book contradicts the harness.** Three pre-gate strategies at 25%
   each, plus open TEST positions. Every day this stands, the fund's actual
   money is governed by exactly the standards the rest of the system exists to
   replace. Deciding is a human click; producing the evidence for the decision
   is ours to do. → **#29**

7. **The claimed edge and the actual reading were disjoint.** The filings
   corpus covers 84 names of which **one** is in the tested universe. We read
   breadth-first across the whole market while claiming the edge lives in a
   specific capacity band. → **#28**

8. **Known fragilities we have already hit once.** The memory ceiling killed a
   holdout run mid-demo-day; the Firestore durability snapshot exists and has
   never run on a schedule; everything lives on one machine whose loss is an
   untested event. → **#33**, **#36**

---

Three horizons, ordered by one principle: **truth before volume, volume before
autonomy.** Calibrating the instruments comes first, because every verdict
produced before that inherits their bias.

## Horizon 1 — pay down the truth debt (this week)

### #26 Price the survivorship bias
The capacity band is measured today, so it contains only survivors. Every
backtest over it is flattered by an amount nobody can state — and it flatters
hold-everything *more* than selection, so it distorts the exact comparison the
gate depends on. The reference API now serves both cures: point-in-time
membership (`date=` on `/v3/reference/tickers`) and delisted names with
`delisted_utc`.
**Do:** build as-of universe membership; re-run `xs_universe_control` against
as-of-2025 membership; publish the haircut in the research note.
**Done when:** the control's +37% carries an honest error bar and any backtest
can request as-of membership instead of today's.

### #27 Calibrate the instruments (new — from the critical read)
Three audits of the measuring equipment itself, none of the strategies:
- **Null audit:** run a batch of random-entry strategies down the belt. Any
  that pass expose a leak (look-ahead, cost hole, survivorship). The pass rate
  IS the gate's false-positive measurement.
- **Injected-edge audit:** run strategies with a synthetic, known-size edge.
  If realistic edges cannot clear the PSR floor on this sample length, the
  floor is measuring history-length, not skill — and we should know that
  before concluding anything from failures.
- **Feed audit:** cross-check the spine's bars against Polygon adjusted bars
  for the 20-name universe — splits, dividends, total-vs-price return. Any
  disagreement is a restatement, handled by the barstore's existing rules.
Plus one structural fix: **walk-forward holdouts** (multiple folds) instead of
the single 2026 window, so retention stops being a one-draw statistic.
**Done when:** we can state the gate's operating characteristics instead of
assuming them, and the feed has survived an independent check.

### #28 Aim the filings reader at the hunting ground
**Do:** sweep the 2,363 band names by ADV descending, nightly, resumable; make
*band coverage* the map's headline number, not whole-market coverage.
**Done when:** the majority of new observations are band names and the
going-concern / insider regions stop being empty for lack of looking.

### #29 Re-judge everything the bugs invalidated
The holdout-starvation bug means the Mean-Reversion/INTC verdict ("2 fills,
kept 0% OOS") was probably never a real test. The three deployed strategies
show `backtested=NEVER` and predate the gate entirely.
**Do:** re-run INTC through the belt with warm-up; run all three legacy
strategies through it; produce a one-page flatten/keep memo per strategy with
evidence attached. The click stays human, sequenced around the PDT constraint.
**Done when:** no position in the book rests on an unexamined verdict.

## Horizon 2 — volume, then hands off (next 2–3 weeks)

### #30 Candidate families through the belt, at volume
Families, in order of prior: **reversal** (the sweep's worst cells were the
shortest lookbacks — weak evidence momentum is the wrong sign at this size),
**filing-event** strategies once #28 feeds the corpus (dilution, customer
concentration, going concern), **breadth variants** (more names, smaller
weights — 5 of 20 concentrates idiosyncratic risk the drawdowns already show).
Every submission through the factory with provenance links, so the map learns
which regions pay.
**Done when:** verdicts/week is a tracked number and the provenance yield
report has enough acted-on observations to say something.

### #31 The morning digest
The Level 2 surface, and the answer to weakness #5: what was read overnight,
what was judged, what died and why (in the gate's own sentences), what needs a
human click today. A queue of *verdicts*, not ideas — and the surface that
makes reviewing observations a two-minute daily habit instead of a feature
nobody visits.
**Done when:** the morning read takes five minutes, ends in at most a handful
of decisions, and reviews/week stops rounding to zero.

### #32 One full trading day with nobody babysitting (#19)
The scheduler owns the day: universe refresh, filings sweep, factory batch,
Firestore snapshot, digest. Kill switch documented and tested.
**Done when:** one clean market day passes with zero human touches and a
coherent morning report — the Level 2 precondition, met rather than claimed.

### #33 Ops honesty — the machine's own limits
Raise the paging file and cap LEAN container memory so a stacked sweep degrades
instead of dying (`WinError 1455` already cost us a holdout run), and put the
Firestore snapshot on a clock.
**Done when:** a stacked sweep survives, and the snapshot has a schedule and a
last-ran timestamp someone can check.

## Horizon 3 — earn trust (the month after)

### #34 Statements an outside investor could audit (#20)
Monthly statement folded from the event log: NAV series, flows, positions,
per-strategy attribution, the chain-verification stamp. The Level 3
precondition, and what makes the fund legible to anyone outside it.

### #35 Divergence watch (Level 3 seed)
vwap-based TCA — the empirical answer to weakness #4 — compared against each
deployed strategy's recorded promise. When live behaviour diverges past a
stated bound, the system *proposes* retirement. Strategies age; the system
should notice before the P&L does.

### #36 The restore drill (#17 — parked, kept visible)
Prove the fund survives losing this laptop: restore from Postgres + the
Firestore snapshot on a second machine, measure the gap. Deferred by explicit
decision — it stays on the map because Level 3 names it as a precondition, and
a deferred item that vanishes from view becomes a surprise later.

---

## Standing constraints

- **15.2 GB RAM** is the binding compute ceiling until #33 lands.
- **Polygon/Massive free tier: 5 requests/minute, ~2 years of history.** The
  throttle blocks rather than fails; bulk endpoints (1,000 rows/call) are the
  only way to use it at universe scale. The MCP needs re-auth after restarts;
  the keyed REST client does not.
- **PDT:** one day trade remains before the 90-day flag — #29's flatten/keep
  decisions must be sequenced around it.
- **The paper connector stays** until an unattended day (#32) passes clean.
  Flipping to the live venue is a deliberate decision, never a side effect.
- **Abhishek owns everything thesis-side** (`thesis_generator`,
  `/studio/thesis`). Interface point when he's ready: his generator submits
  candidates to the factory like any other source, with provenance carried the
  same way.
- **The gate only moves by versioned change, in either direction.** Criteria
  are data; a change is a new version with a written reason. If #27 shows the
  PSR floor is unclearable on our history length, *lowering it with evidence
  and a version bump is honest* — quietly loosening it to manufacture a pass is
  the thing that is forbidden.

## Non-goals for this phase

No new data vendors. No IBKR, no on-chain venues, no tokenization (parked,
legal-gated). No multi-tenant anything — Level 4 is a direction, not a work
item. No new UI surfaces beyond the digest (#31) — the map, hunting ground and
Lab are the product; deepen, don't multiply.

## Carried forward from the previous roadmap

Still right, absorbed into the numbered items: the **24/7 R&D department**
(became #30/#32 — agents running the belt continuously, every proposal landing
as a draft for human review); **adversarial review** before deployment (fold
into gate evolution when something first passes); **agent scorecards / P&L
attribution** (post-Level-2; the post-mortem dataset is the substrate); and the
three **non-negotiables**, unchanged: a hard human seam with a global kill
switch, per-strategy risk budgets, everything through the event log.

Superseded, recorded so nobody re-litigates them: "Alpaca replaces LEAN"
(reversed — LEAN is the engine of record and the harness drives it directly);
the studio information-architecture plan (built, differently); the
web-of-agents topology (the factory belt *is* the topology, with the spine as
shared truth).
