# Demo runbook — 2026-08-17

## The one idea to land

Most early quant demos show a pretty equity curve. **This one shows a system that
refuses to believe its own results.** Today it built a strategy, watched it beat
the benchmark in-sample, and then killed it on the holdout — while surfacing four
bugs that had been flattering candidates. That is a far stronger claim than any
backtest, and it is the reason a $2k fund can be taken seriously.

Say the size out loud early. It removes the "so what" and reframes everything as
architecture rather than performance.

---

## Before he arrives (2 min)

```bash
curl -s http://127.0.0.1:8090/api/v1/fund/health | head -c 200
```

- Spine :8090, Clark :8000, frontend :3000, Postgres, Ollama all up.
- **A restart is now survivable.** Jobs, sweeps and candidate verdicts are
  mirrored to Postgres, so a fresh process reads them back — verified by actually
  restarting and re-reading a completed sweep with both grid points intact. A
  sweep interrupted mid-flight comes back as `interrupted` with the points it
  finished, not as a phantom "running".
- **Do not start a fresh LEAN sweep during the demo.** This box threw
  `WinError 1455` (paging file too small) today when containers piled up. A
  finished sweep is already loaded — use that.

## The click path

**1. The map** (`/clark/studio/lab`) — the default view, and the best opening.

> "84 of 5,196 names read — 1.6%."

The point is not the number, it's that **the system volunteers it**.

Then the terrain: regions are plots, not rows — sized by how much has been read.
`8 explored · 2 untouched`, and `GOING CONCERN` / `INSIDER` are drawn as
**unexplored land** rather than omitted. A ranked list would not have mentioned
them at all. Click a plot to see its names; click a name to carry it to the Lab.
That is the loop: explore, decide, then deploy. Then the **legend**: every filter we
chose, plus one marked `UNCHOSEN` — an extraction bias nobody picked, disclosed
on the face of the map rather than buried in a settings panel.

**2. The hunting ground** — the structural argument.

> "Names a multi-billion fund cannot build a position in."

Real businesses now: Core Natural Resources, Kilroy Realty, Erie Indemnity, Texas
Capital Bancshares. Point at the **identity line**: 2,387 names excluded for not
being operating companies — ETFs and warrants issue units on demand, so "closed
to a big fund" is meaningless for them. *This was wrong until an hour ago; the
screen listed leveraged ETFs.* Worth saying — it shows the standard being applied.

Then the distinction that took two attempts to get right: **capacity is a property
of a strategy at a turnover; closed-to-big-funds is a property of the name.** Only
the second is the edge.

**3. The Lab → sweep → gate** — the punchline.

The persisted candidate is `e8490efdf35a` (`GET /api/v1/fund/factory/candidates`).
It went down the belt — sweep, holdout, verify, judge — and its verdict is in
Postgres, not in a process's memory.

Open the loaded sweep. The heatmap shows the grid: best cell, and its **losing
neighbours**. An island, not a plateau — the shape of a fit to history.

Then the gate verdict. **It reads as sentences, not scores:**

> *"probabilistic Sharpe 18.2% is below 50% — the edge is not distinguishable
> from luck on this much history"*
> *"returns 35.7% against 60.9% for simply owning it: an expensive way to hold
> the underlying"*
> *"kept only −21% of its edge out of sample; 50% is the floor"*

Negative retention is the strongest version of this: out of sample it did not
merely fade, it went the other way.

**4. The audit trail** — event-sourced NAV, hash chain 160/160, folds from the
event log and never from broker equity. NAV $2,026.89. If he asks how you know
the number is right: the chain verifies, and the broker is a *comparison*, never
the source of truth.

## The story to tell over it (60 seconds)

1. Every earlier candidate was a long-only timing rule on one name, and each
   failed the same criterion — *an expensive way to hold the underlying*. That's
   structural: a rule that sits in cash can't beat an asset that drifts up.
2. So we tried the shape that can win: **selection** among names. 20 operating
   companies picked **by rule** from the capacity band — because I could see how
   they traded, and hand-picking would be look-ahead bias no holdout would catch.
3. In-sample it worked: **+21.7% vs +10.9%** for holding all 20.
4. Out of sample it kept **−21% of that edge** — it inverted — and trailed the
   no-opinion bar by ~30 points. Gate: **FAILED**, on three counts.
5. Along the way: a benchmark of all-zeros that was being believed (every
   profitable strategy "beat the market"), a multi-name strategy judged against
   one constituent, a holdout that scored 0% for strategies that never traded,
   and a gate verdict that depended on who polled first.

Full write-up: `docs/RESEARCH_XS_MOMENTUM_2026-08-17.md`.

## If he asks

**"Why should a $2k fund exist?"** — capacity. A $5bn fund needs 50 days to build
in these names at 15% of volume. We need minutes. That band is the only water
where size is an advantage, and it has to be searched deliberately.

**"How do you avoid fooling yourselves?"** — the gate is data, not code
(`app/fund/gate.py`), versioned `v1`, and **missing evidence fails**. Today it
failed our own best candidate.

**"Is this live?"** — the ledger is real and event-sourced. Clark can *propose*;
a human clicks approve. LEAN proposes and never executes — no brokerage attached.

## Known rough edges — name them before he finds them

- Monitor shows **"Loading quotes…"** briefly on a cold load.
- Console shows some 500s **only if a component was edited with the page open** —
  Next.js hot-update requests, not real failures. Every fund endpoint returns 200.
- The venue is the **paper connector**, so the header reads "Simulated venue".
  Switching to Alpaca is a config flag, deliberately not flipped mid-demo because
  it would route live orders.
- The three deployed strategies show `backtested=NEVER` and would fail the gate.
  Frame it honestly: *the gate is telling the truth about strategies that predate
  it* — that's the system working.
- Survivorship: the band is measured today, so it contains only survivors. Now
  fixable — the reference API serves delisted tickers and point-in-time
  membership, which is the next piece of work.
