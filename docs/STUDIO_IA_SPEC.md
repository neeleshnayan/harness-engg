# Studio Information Architecture — workflow-first

## The problem this fixes
The Studio was organised by **system component** (Overview / Strategies / Composer /
Approvals / Theses / Risk). That mirrors how the code is built, not how the fund is
run, and it creates a recurring "where does this live?" ambiguity — a strategy's
drawdown is risk data *about a strategy*, so Strategies and Risk each have an equal
claim on it, and today it is served well by neither. Every new feature re-opens the
same argument.

## The paradigm
The fund does four things, in a loop:

> **DECIDE** what to own → **ALLOCATE** how much → **MONITOR** what's happening →
> **REVIEW** how it went → back to DECIDE

Four surfaces, one per job. A thing lives where the user is when they need it, not
where its code lives.

Risk is **not** one of the four. Risk applies to all of them, so it is a persistent
bar, not a destination (below).

---

## Routes

| Route | Job | Absorbs |
|---|---|---|
| `/clark/studio` | **DECIDE** — the case for a trade | Theses, Memos, Approvals (pending orders + the thesis behind each) |
| `/clark/studio/allocate` | **ALLOCATE** — sizing and composition | Strategies list + detail, Composer, weights, backtests, deploy |
| `/clark/studio/monitor` | **MONITOR** — what is happening right now | Live NAV, positions, order blotter, limit breaches, per-asset risk, kill-switch controls |
| `/clark/studio/review` | **REVIEW** — how it went | Attribution (realized vs unrealized), post-mortems, closed positions, NAV history |

Old routes (`/strategies`, `/compose`, `/risk`, `/theses`, `/approvals`) redirect to
their new home so links and muscle memory survive.

### DECIDE (`/clark/studio`)
The default landing page: the fund's open questions.
- **Pending approvals** — each rendered as *the case*, not the ticket: thesis claim,
  memo recommendation, invalidation criteria, risk-gate result, then approve/decline.
- **Theses** — active investment theses with state, the assets they scope, and their
  invalidation conditions. A thesis nearing invalidation is surfaced here, not buried.
- **Drafting** — start a thesis / request a memo.
Nothing on this page is a number the user must monitor; it is all decisions awaiting
a human.

### ALLOCATE (`/clark/studio/allocate`)
Everything about *how much* of the fund goes where.
- **Strategy list** — state, target vs actual weight, exposure, Sharpe, breach flag.
- **Strategy detail** (drawer/route) — assets, backtest, positions, per-strategy risk,
  realized/unrealized P&L, orders. This is where per-strategy risk lives, ending the
  Strategies-vs-Risk overlap.
- **Composer** — build a composite from child sleeves, weight them (manual, equal,
  risk-parity, HRP, max-Sharpe), see the blended curve, deploy.
- **Rebalance** — target vs actual drift and the orders to close it.

### MONITOR (`/clark/studio/monitor`)
The live cockpit. Answers "what is happening?" in one screen.
- **Live NAV** + today's move, and the **broker-vs-book drift** signal
  (`GET /fund/venue/reconcile`) — a book that disagrees with the venue is a
  first-class alert, not a hidden endpoint.
- **Positions** with marks, weights, and per-asset risk contribution.
- **Order blotter** — live and recent fills.
- **Active limit breaches** with severity, and the **kill-switch** (halt / resume).
- **Stress test** — scenario shocks against live holdings. Must render
  `proxied_symbols` and `sensitivities_are_assumptions` so a soft estimate reads as soft.

### REVIEW (`/clark/studio/review`)
Accountability, and the input to the next DECIDE.
- **Attribution** per strategy: **realized vs unrealized** P&L (now that the spine
  distinguishes them), cost basis, contribution to fund return.
- **Post-mortems** — closed positions against their original thesis: what was claimed,
  what happened, what invalidated.
- **NAV history** and drawdown record.
- **Audit trail** — the event log, the fund's memory.

---

## The persistent risk bar
A thin strip directly under the header, on **every** page.

- Normal: halt state, current drawdown vs limit, count of active breaches. Calm, quiet.
- Breached: the bar turns severity-coloured, names the breach, and offers the action
  (review / halt). It is never dismissible.
- Halted: unmistakable — trading is stopped, BUYs are blocked, and it says so, with
  resume gated to a human.

**Why persistent:** capital preservation is the fund's first priority, and a breach
you have to navigate to is a breach you find late. The user must never have to be on
the right tab to learn the fund is in trouble.

Data: `GET /fund/risk/monitor` (a pure read — it writes no events), polled 3–5s.

---

## Rules that keep it coherent
1. **A number appears where the user acts on it**, not everywhere it is available.
   Cross-links, not duplicated panels.
2. **Per-strategy risk lives in ALLOCATE** (with the strategy); **fund-level risk lives
   in the bar and MONITOR**. This is the line that was missing.
3. **No fabricated numbers.** Real spine data or an honest empty state — unchanged.
4. **Desk terminology** (Live NAV, Limit Breaches, Realized/Unrealized P&L,
   Annualized Volatility, Trading Halt). No internal architecture words — never
   "spine", "event-sourced", "projection" in user-facing copy.
5. **Style only from `KT` tokens** in `theme.ts`; never branch on theme — light/dark
   differ only in the CSS variables. Charts take literal colors from `useChartColors()`
   because the charting libraries parse colors in JS.
