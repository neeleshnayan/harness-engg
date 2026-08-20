# PM Staging Memo (filed at resolve by the CTO, 2026-08-20)

**Author: pm agent, second dispatch (1eef5264 / trace-pm-review-1). Survived a usage-limit death; resumed from transcript. CTO verification notes at the bottom.**

Memory read: `C:\Users\user\Documents\Krypton Fund\.claude\state\pm.md`. Endpoints pulled once, in one batch.

---

# PM Decision Memo — Staging Tickets, Exit Proposals, Sleeve Invalidation
**Dispatch 1eef5264 / trace-pm-review-1 (second dispatch). Read timestamp: all endpoints pulled 2026-08-20T03:16:42Z; `/risk/monitor.ts` = `2026-08-20T03:16:04.896396+00:00`. Gate `v4.1` (`app/fund/gate.py:157`).**

Spine state at read: `/health` `status:"ok"`, 6/6 checks green, chain 227/227, NAV folds from the log ($2,011.81, 9 positions). `/liveness`: settlement, risk_monitor, exit_check, auto_policy, snapshot all beating at ~18s; **`nav_strike` UNOBSERVED in this process** — unknown, not fine. `/risk/alerts` `{"active":[]}`. `/orders/pending` `{"pending":[]}`. `halted: false`.

**The book has not moved since my first review's marks were re-struck.** Every mark in `/risk/monitor.positions` is byte-identical to the 23:47Z pull I made before the restart, and `/orders/history` shows no fill after `2026-08-19T18:20:54` (the TLT sleeve fill). So there are **no fresh fills**, TCA is unchanged, and the arithmetic below is against a static book — not a stale one, a static one. If marks move before staging, quantities are the commitment; notionals are estimates.

---

## 0. The book in one table

Source: `/risk/monitor.positions` + `/strategies[].positions` (which strategy owns which shares) + `/exits`.

| Position | Qty | Mark | Value | Wt | Unreal % | Unreal $ | Owner strategy | Exit coverage | Claim |
|---|---|---|---|---|---|---|---|---|---|
| TLT | 3.019871 | 83.02 | $250.71 | 12.46% | +0.28% | +$0.71 | sleeve_beta_500 | **Full**: loss 4.0%, time 2026-09-08, thesis | premia (declared beta) |
| DBC | 8.122157 | 30.76 | $249.84 | 12.42% | −0.07% | −$0.16 | sleeve_beta_500 | **Full**: loss 8.7%, time 2026-09-08, thesis | premia (declared beta) |
| GLD | 0.424471 | 413.84 | $175.66 | 8.73% | +2.90% | +$4.95 | Trend `e54f40af` | **Nominal**: loss 25% under `strategy_id:"machinery-test"`, note "far away" | legacy — fails gate |
| XLE | 2.749912 | 63.58 | $174.84 | 8.69% | +3.10% | +$5.25 | Trend `e54f40af` | **NONE** | legacy — fails gate |
| SOFI | 9.18819 | 18.42 | $169.25 | 8.41% | +1.40% | +$2.34 | MeanRev `ca78408f` | **NONE** | legacy — fails gate |
| SPY | 0.16554 | 769.06 | $127.31 | 6.33% | −1.22% | −$1.57 | Trend `e54f40af` | **NONE** | legacy — fails gate |
| SPY | 0.052217 | 769.06 | $40.16 | 2.00% | −1.22% | −$0.50 | TEST `3c593166` (**paused**) | **NONE** | none — no backtest on record |
| MSFT | 0.340051 | 484.31 | $164.69 | 8.19% | −2.70% | −$4.58 | Momentum `6cca6a31` | **NONE** | legacy — fails gate |
| NVDA | 0.749886 | 217.56 | $163.15 | 8.11% | −4.18% | −$7.12 | Momentum `6cca6a31` | **NONE** | legacy — fails gate |
| INTC | 1.608762 | 92.80 | $149.29 | 7.42% | −8.08% | −$13.12 | MeanRev `ca78408f` | **NONE effective** — 2 gain rules, one `overridden_at`, one `superseded:true`; **no loss rule** | legacy — fails gate |
| Cash | — | — | $346.92 | 17.24% | — | — | — | — | — |

Unrealised checks against `/strategies`: Momentum −$11.70, MeanRev −$10.77, Trend +$8.63, TEST −$0.50 — my per-position split reconciles to each to the cent.

**Mandate check (measured vs limit; limits from `/risk/monitor.limits`):**

| Control | Measured | Limit | Util | Source |
|---|---|---|---|---|
| Drawdown from peak | 1.21% | 10% | 12% | `/risk/monitor.drawdown` |
| Gross | 82.76% | throttle asks 0.7206× | **ignored** | `/risk/throttle.gross_multiplier` |
| Cash | 17.24% | ≥5% | comfortable | `/risk/monitor.cash_pct` |
| Effective bets | 3.88 | ≥2.0 | comfortable | `/risk/advanced.correlation.effective_bets` |
| Avg pairwise corr | 0.1232 (max NVDA/SPY 0.6819) | ≤0.75 | comfortable | `.correlation` |
| ES 97.5% 1-day | 2.504% / $50.37 | ≤5% | 50% | `.tail.levels.0.975` |
| **Risk concentration** | **INTC 31.96% of book risk on 8.97% of capital** | ≤50% | **64% — closest to binding** | `.risk_contribution.largest_risk_contributor` |
| Largest position | TLT 12.46% | 20% | 62% | `/risk/monitor.utilization` |
| Largest strategy | sleeve 24.88% | 40% | 62% | `.utilization.max_strategy_pct` |

Nothing is in breach. **INTC remains the closest-to-binding control, and rec 6 closes it.**

---

## 1. STAGING TICKETS

### 1a. Reconciling "gross → ~58%" against the live book — it does not hold as written

My first memo's parenthetical "(gross → ~58%)" was inherited from `docs/SLEEVE_500_FRAMEWORK.md:250-254`, which said retiring the three failed strategies keeps "gross flat near 58%". **That sentence describes selling ~$500 of the failed strategies to fund the sleeve — not closing them.** Check: 82.76% − $500/$2,011.81 = 82.76 − 24.85 = **57.91%**. That is where 58% comes from, and it is a $500 partial trim, not a retirement.

**Full closure of all three strategies is $1,164.35 of sells and takes gross to 24.88%, not 58%.** My memo's number was correct for the framework's funding scenario and wrong as a description of accepting recs 2–4. Corrected arithmetic is the cumulative table in §1c.

### 1b. Throttle (rec 1) — the number depends on a reading nothing in code fixes

`/risk/throttle` returns `gross_multiplier: 0.7206`, `driver:"turbulence"`, `turbulence_20d_percentile: 89.5`. The multiplier is a **scalar applied to target weights** (`app/fund/throttle.py:135-150`), and `apply_to()` has **zero callers outside its own module** (`grep apply_to app/ --include=*.py`) — so "normal gross" is defined nowhere in code. Two defensible readings:

- **Reading A** (multiplier × the book's own gross, the `apply_to` semantics, and what I used last time): target **59.63% / $1,199.72** → **$465.17 of sells**.
- **Reading B** (multiplier × 100% notional): target **72.06% / $1,449.71** → **$215.18 of sells**.

I keep Reading A and say so explicitly. Under either, **accepting tickets T1–T4 satisfies the throttle** (cumulative sells $523.39 > $465.17; post-gross 56.74%). No separate throttle override is needed, consistent with the CTO's framing. **If the CEO accepts fewer than T1–T4, the throttle is being ignored again and needs a written override.**

### 1c. The tickets

Every ticket is a SELL of an existing long. All pass the pre-trade gate by construction: `app/fund/risk.py:132-136` exempts the position-closing part of a sell from `max_order_notional_pct`, and `min_cash_pct` is only checked on buys (`risk.py:154`). PDT is clear — `/compliance.pdt` shows `used: 2, remaining: 1`, and none of these symbols was bought in the current session (last non-sleeve fill: `2026-08-14T13:42:40`, `/executions`), so **no ticket creates a day trade**.

Post-trade columns are computed by replicating the engine's own method — `effective_bets = (Σwᵢσᵢ / σ_p)²`, `app/fund/correlation.py:241-244` — on `/risk/advanced.correlation.matrix` and `.annualised_vol_pct`. My replication reproduces the live book exactly (eff bets 3.88, vol 16.39%, avg corr 0.1232). Risk-share figures are my equal-weighted-vol version of `.risk_contribution` (engine uses EWMA: its INTC 31.96 vs my 30.28 on the same book) — treat them as ±2pp.

| # | Rec | Order | Qty | Est. notional @ live mark | Realises | Post-trade gross | Cum. sells | Eff bets | Largest risk share |
|---|---|---|---|---|---|---|---|---|---|
| **T1** | 5 | SELL SPY | 0.052217 | $40.16 | −$0.50 | 80.76% | $40.16 | 3.91 | INTC 30.7% |
| **T2** | 6 | SELL INTC | 1.608762 | $149.29 | **−$13.12** | 73.34% | $189.45 | 3.79 | SOFI 32.7% |
| **T3** | 2 | SELL SOFI | 9.18819 | $169.25 | +$2.34 | 64.93% | $358.70 | 4.28 | NVDA 24.9% |
| **T4** | 3 | SELL MSFT | 0.340051 | $164.69 | −$4.58 | **56.74%** ← throttle met | $523.39 | 3.66 | GLD 29.4% |
| **T5** | 3 | SELL NVDA | 0.749886 | $163.15 | −$7.12 | 48.63% | $686.54 | 3.21 | DBC 40.0% |
| **T6** | 4 | SELL GLD | 0.424471 | $175.66 | +$4.95 | 39.90% | $862.20 | 3.12 | **DBC 62.3% — over the 50% limit** |
| **T7** | 4 | SELL XLE | 2.749912 | $174.84 | +$5.25 | 31.21% | $1,037.04 | 3.57 | DBC 89.3% |
| **T8** | 4 | SELL SPY | 0.16554 | $127.31 | −$1.57 | 24.88% | $1,164.35 | 2.49 | DBC 101.0% |

Full acceptance: **$1,164.35 of sells, −$14.35 realised, gross 82.76% → 24.88%, cash 17.24% → 75.12%.** The residual book is exactly the sleeve.

**Two warnings the CEO should have before clicking, not after:**

1. **T6 onward trips `max_risk_concentration_pct` (0.50).** With TLT/DBC at pair correlation −0.4379 (`/risk/advanced.correlation.matrix`), TLT is a *negative* risk contributor, so DBC's share exceeds 100% in a sleeve-only book. `app/fund/riskengine.py:571-584` raises a `severity:"warn"` alarm above 50%. This is arithmetic, not danger — a two-name hedged book concentrates measured risk by construction. **It is not a reason to skip T6–T8; it is a reason not to be surprised at the alarm.** If it fires and reads as a new problem, that is the control being misread.
2. **Effective bets fall 3.88 → 2.49** at full liquidation — still above the 2.0 floor, but the margin goes from 94% to 25%. `SLEEVE_500_FRAMEWORK.md:217-227` recorded that this limit "will pass without having been exercised"; after T8 it is genuinely close to live.

### 1d. Per-position disposition of each retired strategy — closes now, or survives to rec 7

"Retire" has no state in the spine: `StrategyState` is `{draft, backtested, deployed, paused}` and `DEPLOYED → PAUSED` is the only legal exit (`app/fund/strategies.py:24-37`). **Pausing does not close positions** — proved on the live book: TEST is `state:"paused"` and still holds `{"SPY": 0.052217}` = $40.16 (`/strategies`). So each retirement is a state change *plus* an explicit disposition per position, and inertia is a decision.

**Mean Reversion — Cyclicals (`ca78408f`), $318.54:**
- **INTC → CLOSE NOW (T2).** Rec 6's operative branch, per the CTO. My own measurement supports it: 1.5σ of its 21-day vol is **36.33%** (ann vol 83.90%, `/risk/advanced.correlation.annualised_vol_pct.INTC`; σ₂₁ = σ_ann×√(21/252)) — a $54 loss rule on a $149 position, which is not a stop, it is a hope. State on the ticket: *no loss rule was recorded, so CLOSE is the operative branch; the CEO sees the order before it fills.*
- **SOFI → CLOSE NOW (T3).** Orphaned by the retirement; 53.69% ann vol; 1.5σ = 23.25%, also too wide to be a stop at this book size. Same argument as INTC, smaller in degree.

**Momentum — Large Cap Tech (`6cca6a31`), $327.84:**
- **MSFT → CLOSE NOW (T4). NVDA → CLOSE NOW (T5).** Both orphaned; neither is a broad exposure; both ~37% ann vol.

**Trend — Sector & Commodity (`e54f40af`), $477.81:**
- **GLD → CLOSE NOW (T6). XLE → CLOSE NOW (T7). SPY 0.16554 → CLOSE NOW (T8).** These are the ones where I expect pushback, so the reasoning is stated plainly: the gate's verdict on Trend is that the *overlay* is "an expensive way to hold the underlying" — that condemns the timing, not the instruments. GLD/XLE/SPY are exactly the broad exposures `SLEEVE_500_FRAMEWORK.md:235-244` endorses. **But an instrument that survives because its strategy died is an orphan, not a position.** If the CEO wants this exposure, the honest route is re-adoption as a *new* pre-registered declared-beta holding with claim, size and exits written before the decision — not inheritance by inertia. That is a mandate decision (security selection is the CEO's lane), and I am not proposing it as an order.

**TEST — Fast Intraday (`3c593166`), $40.16:** SPY residual → **CLOSE NOW (T1)**. No backtest on record (`/strategies/divergence`: *"no backtest on record — deployed on what?"*), paused, no exit rule.

**Three non-order tickets** (state changes, not orders — no pre-trade gate, no fill):

| # | Action | Endpoint | Why |
|---|---|---|---|
| **S1** | MeanRev `ca78408f` → `paused`, `allocation_pct` 25.0 → 0, then archive | `/strategies/{id}` state, `/allocation`, `/archive` | rec 2; without this, a retired strategy still holds a 25% allocation claim |
| **S2** | Momentum `6cca6a31` → same | same | rec 3 |
| **S3** | Trend `e54f40af` → same | same | rec 4 |

**Do S1–S3 even if some sell tickets are rejected**, and **do them before the sells** — a paused strategy cannot re-open a position the sells just closed. Conversely, closing positions without S1–S3 leaves three deployed strategies with 25% allocations and no positions, which will read as under-deployment rather than as retirement.

### 1e. One free measurement the CEO should know these tickets buy

`/tca.summary.vs_assumption`: `sample: 12`, `reliable: false`, verdict *"12 fills is an anecdote, not a measurement; 20 is the bar"*. **Eight sell tickets take the sample from 12 to exactly 20** — the reliability bar — and the fills are in six different names on the venue the sleeve traded. That also discharges sleeve falsification condition #2 (`SLEEVE_500_FRAMEWORK.md:49-52`), which is currently un-dischargeable at n=12. This is a reason to execute the batch together rather than piecemeal, and it is the only argument in this memo for doing more rather than less.

Current TCA, unchanged since my last review (no fresh fills): blended **4.96bps vs 5.0 assumed**; **Trend 21.47bps/side** on 4 fills, worst 81.22bps (`/tca.by_strategy.e54f40af...`); **sleeve 0.00bps on 2 fills** — decision = arrival = fill, the paper venue adding sample count and zero information; sleeve approval latency mean **189.32s** against 3.88s for Trend.

---

## 2. EXIT-RULE PROPOSALS (rec 7)

**Rule types the spine actually has:** `KINDS = ("loss_pct", "gain_pct", "time", "thesis")` — `app/fund/exitrule.py:41`. There is **no trailing stop, no correlation rule, no NAV-drawdown rule** at position level. `loss_pct`/`gain_pct` take a positive magnitude (direction carried by the kind, `exitrule.py:63-68`); `time` takes `on_date` as YYYY-MM-DD; `thesis` requires a written `note` and **never fires on its own by design** (`exitrule.py:136-143`) — it is surfaced at review for a human to answer.

**Three mechanical facts that constrain what I can responsibly propose:**

1. **A committed rule that is already breached executes without a click.** The exit tick raises a SELL whose rationale carries `"PRE-COMMITTED EXIT FIRED"` (`exitrule.py:307`), and `autopolicy.evaluate` approves on that marker plus side/halt/liveness/freshness — **there is no actor check** (`autopolicy.py:87-118`), despite the module docstring saying "actor + the marker together". So *committing a rule is an executable act*. Every level below is checked against today's unrealised: **none is breached** (worst is NVDA at −4.18% against a 16.23% level).
2. **Exit sizing is symbol-level, not strategy-level.** `enforce()` sizes the closing order from `qty_by_symbol` (`exitrule.py:269-270, 287, 304`). A SPY rule keyed to *any* strategy_id would propose selling the **whole** 0.217757 SPY position, not that strategy's slice. If T1 and T8 are not both accepted, a SPY exit rule will over-sell.
3. **Loss distances are computed the same way the sleeve's were**, and the method self-validates: 1.5σ on TLT's live vol gives **4.10%** against the frozen commitment of **4.0%** — the pre-registration reproduces.

Proposals, one set per position, for **every position that survives its close ticket** (i.e. commit these in the same session the CEO rejects the corresponding sell — "before next review" is what let seven positions go uncovered in the first place):

| Position | Rule | Level | Currently at | One-line reason |
|---|---|---|---|---|
| **GLD** | `loss_pct` | **13.6%** | −(+2.90%) | 1.5σ of its measured 21-day vol (ann 31.43%), the sleeve's own method, frozen as a number so it cannot be relitigated while holding a loser |
| | `time` | **2026-09-08** | holds | Same horizon as the sleeve, so the whole book is re-decided on one date instead of drifting name by name |
| | `thesis` | note | — | "Held because the CEO chose the exposure on its own merits after Trend was retired, not because Trend held it. If no such written adoption exists at review, the reason for holding is gone." |
| | **supersede** | — | — | **The live `machinery-test` 25% loss rule must be superseded or explicitly overridden** — see Exception 1 |
| **XLE** | `loss_pct` | **10.2%** | −(+3.10%) | 1.5σ of 23.51% ann vol |
| | `time` | **2026-09-08** | holds | as above |
| | `thesis` | note | — | as above |
| **SPY (either or both slices)** | `loss_pct` | **5.8%** | −1.22% | 1.5σ of 13.37% ann vol — the one name where a percentage stop is a real stop (`SLEEVE_500_FRAMEWORK.md:197`) |
| | `time` | **2026-09-08** | holds | as above |
| | `thesis` | note | — | "Held as broad market exposure adopted in writing, not as the residue of a paused intraday test." |
| | ⚠ | — | — | **Commit ONE SPY rule set only, and only if both slices are retained** — sizing is symbol-level (fact 2) |
| **MSFT** | `loss_pct` | **16.0%** | −2.70% | 1.5σ of 36.87% ann vol. **State plainly: 16% on a $165 position is $26 — a stop this wide is a formality, and the honest reading is that a single name at this vol does not belong in a $2k book** |
| | `time` | **2026-09-08** | holds | as above |
| | `thesis` | note | — | "Held on an explicit CEO adoption after Momentum was retired (0 of 4 folds). Absent that, the reason for holding is gone." |
| **NVDA** | `loss_pct` | **16.2%** | −4.18% | 1.5σ of 37.49% ann vol; same formality caveat as MSFT |
| | `time` | **2026-09-08** | holds | as above |
| | `thesis` | note | — | as MSFT |
| **SOFI** | `loss_pct` | **23.3%** | +1.40% | 1.5σ of 53.69% ann vol — **$39 of a $169 position. I do not recommend committing this; it is a stop in name only. If SOFI is retained, it needs a size decision, not a stop** |
| | `time` | **2026-09-08** | holds | as above |
| | `thesis` | note | — | as MSFT |
| **INTC** | `loss_pct` | **36.3%** | −8.08% | 1.5σ of 83.90% ann vol = $54 on a $149 position. **This is the arithmetic that says close it.** Recorded here only so the alternative to rec 6's CLOSE branch is stated as a number rather than left vague |
| | `time` | **2026-09-08** | holds | as above |
| | `thesis` | note | — | as MSFT |

**No `gain_pct` rules proposed on any position.** A gain rule caps upside on a beta claim, and the sleeve deliberately carries none. The one gain rule the fund has ever run in anger (INTC take-profit) aged 46 hours waiting for a click and the gain evaporated — cited in `autopolicy.py`'s own preamble as the motivating failure.

---

## 3. SLEEVE INVALIDATION CONDITIONS (rec 9, redesigned)

For the CEO's approval. **This is the single recorded fact that replaces the weekly interrogation.** Once approved it should live as a versioned doc section, and the `thesis` exit notes on TLT and DBC should be superseded to point at it — because today those notes say *"Answered by a human at every review"* (`/exits`, `kind:"thesis"`), which is precisely the weekly question the CEO removed. **Until they are superseded, `/exits/check` will keep returning them under `unevaluable` with `"a human must answer this at review"` — the old design is still live in the machinery.**

### TLT — recorded thesis

`sleeve_beta_500` holds 3.019871 TLT ($250.71, 12.46% of NAV) as one of two legs of a **declared-beta** sleeve whose purpose is to complete one full decide→size→enter→mark→cost→monitor→exit→review cycle with every step measured. **No edge is claimed and none will be reported**; any profit is long-duration Treasury exposure and will be described that way. TLT was chosen from a 12-name measured shortlist by category, not by view, because the TLT+DBC pair scored 4.03 book effective bets at −0.41 pair correlation (`SLEEVE_500_FRAMEWORK.md:269`) — a selection made on measured properties. Its loss exit was frozen at **4.0%** = 1.5× its then-measured 21-day sigma, and the method reproduces on live data (1.5σ today = 4.10%). **The sleeve succeeds if the loop completes and every step was measured; it does not succeed by making money and does not fail by losing it.**

### DBC — recorded thesis

`sleeve_beta_500` holds 8.122157 DBC ($249.84, 12.42% of NAV) as the second leg, on the identical declared-beta claim, chosen for the same measured reason (its −0.41 correlation to TLT is what makes the pair two bets rather than one). Its loss exit was frozen at **8.7%**. Recorded precisely: on today's measured vol (22.71% ann → 6.56% σ₂₁) **8.7% is 1.33σ, not 1.5σ** (1.5σ today would be 9.83%). The frozen number stands — freezing it is the whole point of `SLEEVE_500_FRAMEWORK.md:204-210` — but the drift is recorded so nobody later claims the stop is 1.5σ when it is 1.33σ. Combined dollar risk at both stops: **$31.77** ($10.03 TLT + $21.74 DBC), 1.58% of NAV against a 10% drawdown limit — matching the pre-registered "~$32" to within 23 cents.

### (a) DETERMINISTIC invalidation conditions — a number the spine can watch

| # | Condition | Threshold | Measurement source | Machinery status |
|---|---|---|---|---|
| **D1** | TLT unrealised loss | **≥ 4.0%** | `/exits/check` on `EXIT_RULE_SET` (`kind:"loss_pct"`, `strategy_id:"sleeve_beta_500"`) | **ARMED and TICKING** — `exit_check` heartbeat 18s (`/liveness`); today "down 0.28% of 4.00%" |
| **D2** | DBC unrealised loss | **≥ 8.7%** | same | **ARMED**; today "down −0.07% of 8.70%" |
| **D3** | Time | **on 2026-09-08** | same, `kind:"time"` | **ARMED**; "holds until 2026-09-08" |
| **D4** | Fired exit produces no closing proposal (falsification #1) | any fire with `order_id: null` on the `EXIT_RULE_TRIGGERED` event | `/events`, `exitrule.py:293-299, 323-331` | **wired but UNTESTED on the sleeve** — no sleeve exit has ever fired |
| **D5** | TCA cannot compare fills to the 5bps assumption (falsification #2) | `/tca.summary.vs_assumption.reliable` stays `false` at the 21-day close | `/tca` | **CURRENTLY TRIPPED**: `sample: 12`, `reliable: false`. Discharged if the §1 sell batch executes (12 → 20) |
| **D6** | NAV folded from the log diverges from broker equity (falsification #3) | any stated tolerance | `/reconcile`, `/health.checks.venue` | **UNTESTABLE TODAY**: `/compliance.account` = `"simulated venue — no brokerage account"`. There is no broker equity to diverge from. **Record this as untestable, not as passing** |
| **D7** | Pair correlation regime break | TLT/DBC 250d correlation rises above **0.0** from −0.4379 | `/risk/advanced.correlation.pairs` | **NO MACHINERY** — the spine has no correlation exit kind (`exitrule.py:41`). Monitored only when a PM dispatch runs. See J3 |
| **D8** | Book effective bets | falls below **2.0** | `/risk/advanced.correlation.effective_bets`; alarm at `riskengine.py:541-548` | ARMED as a warn alarm. Post-T8 the sleeve-only book sits at **2.49** — 25% margin |
| **D9** | Book risk concentration | one name **> 50%** of book risk | `.risk_contribution`; alarm at `riskengine.py:571-584` | ARMED. **Will trip by construction at T6+; expected, not a surprise** |

**D1–D3 are the only conditions that both watch a number and act on it.** D4–D9 are watched; only D8/D9 raise an alarm, and an alarm is not an exit. Stated so "the risk controls passed" is never read as "the risk controls work" — the framework's own words at line 227.

**One precision fact for the record, not an action:** the pre-registration says "21 calendar days **from fill**" (`SLEEVE_500_FRAMEWORK.md:39`). The rules were set 2026-08-18T02:11:39Z with `on_date: 2026-09-08` = 21 days from the *set* date; the fills landed 2026-08-19T18:20Z, so **the committed date is 20 calendar days from fill, not 21**. The frozen date stands — relitigating it is exactly what freezing forbids — and it is recorded here so no later reading claims 21-from-fill.

### (b) JUDGMENTAL invalidation conditions — checked on PM dispatches

| # | Condition | Evidence that trips it |
|---|---|---|
| **J1** | **The loop has completed.** The sleeve's stated reason for existing is gone once every step has been measured end to end. | All eight rows of `SLEEVE_500_FRAMEWORK.md:152-160` have a live measurement on the sleeve's own fills: entry ✓, mark ✓, **cost — currently NOT measured (D5, n=12 of 20)**, monitor ✓, **exit — NOT measured (D4, never fired)**, review ✓. **Trips when Cost and Exit both have real sleeve measurements.** Today it does not trip: two rows are absent, and absence is not completion. This is the condition that replaces "is the thesis still good?" |
| **J2** | **The claim stopped being declared beta.** Any report, memo or dashboard describing sleeve P&L as skill, edge, or validation of anything. | A written artifact attributing sleeve profit to anything but market exposure. Zero instances to date. |
| **J3** | **The pair stopped being two bets.** D7's number with no machinery behind it — so it becomes my judgement on dispatch. | TLT/DBC correlation above 0.0 (from −0.4379) **and** book effective bets under 3.0, together, on two consecutive dispatches. One reading is noise. |
| **J4** | **The sleeve is being sized by its P&L rather than its purpose.** | Any proposal to add to TLT/DBC, or to extend past 2026-09-08, whose stated reason references the sleeve's return. $500 held for three weeks carries no statistical information about edge (`SLEEVE_500_FRAMEWORK.md:15`). |
| **J5** | **The machinery under test stopped being trustworthy.** | Any of: `/health` red on a sleeve-relevant check; `exit_check` heartbeat stale; an `EXIT_RULE_TRIGGERED` with `order_id: null`; an auto-approval the risk officer flags. Today: none — but `nav_strike` is UNOBSERVED in this process, which is neither broken nor fine. |
| **J6** | **Discipline failure (falsification #4).** The framework rates this the most likely to trip. | The CEO redesigned "a week passes with no written review" into machine monitoring plus PM dispatches. **This condition is now: 7+ days pass with neither a PM dispatch nor a written sleeve note. Clock runs from the 2026-08-19 fills → first trip date 2026-08-26.** Recording the replacement is what keeps the original falsifiable rather than quietly dropped. |

**What is deliberately absent: any P&L condition.** Losing $32 is not on the list. Neither is making $32.

---

## 4. Exceptions

1. **A machinery-test exit rule is armed on a real position, with auto-execution downstream.** `/exits` carries `{kind:"loss_pct", symbol:"GLD", strategy_id:"machinery-test", threshold_pct:25.0, note:"far away", superseded:false}` with **no `overridden_at`**. `/exits/check` evaluates it live ("down 2.90% of 25.00%"). If GLD fell 25%, `enforce()` would raise a SELL for the **entire** GLD position carrying the `"PRE-COMMITTED EXIT FIRED"` marker, and `autopolicy.evaluate` would auto-approve it — the marker is the only provenance check (`autopolicy.py:87-91`), there is no actor test, and `strategy_id:"machinery-test"` is not excluded anywhere. **A rule created to prove the wiring is now portfolio policy that can execute unattended.** Recommendation R4 below.
2. **Three strategies deployed against the fund's own belt, re-verified on live fold data (not the v2 doc I cited last time).** `/lean/sweeps` now serves per-fold `holdout_result`. Against gate v4.1's `min_psr_pct: 65.0` and `min_walkforward_folds: 4` with a strict majority (`app/fund/gate.py:165, 183-184`):
   - `mean_reversion_cyclicals` — **all 5 sweeps place ZERO orders in the holdout** (`total_orders: 0`, `psr_pct: 0.0`, every window). It does not trade out of sample at all. **0 of 4 folds.**
   - `momentum_large_cap_tech` — fold PSRs 41.489 / 18.290 / **64.578** / 9.530. **0 of 4** clear 65.0, the best missing by 0.42. Orders per fold 1–3, against `min_orders: 20`.
   - `trend_sector_commodity` — fold PSRs 2.748 / 0.0 / 85.307 / 15.753. **1 of 4.** Orders per fold 3–11.
   
   $1,124.19 of exposure, 55.9% of NAV, on claims the fund's own belt rejects at fold level. Recs 2–4 are correct and the live evidence is stronger than the evidence that produced them.
3. **The sleeve is invisible to the divergence watch — now measured, not predicted.** `/strategies/divergence` returns 4 rows; `sleeve_beta_500` is **not among them**, and it does not appear in `/strategies` at all (it exists only as an attribution key in `/risk/monitor.strategies`). `SLEEVE_500_FRAMEWORK.md:141-144` predicted this and offered two options; neither was taken. **The sleeve is unmonitored on that axis and this memo says so** — which is the option the framework allowed, now formally exercised.
4. **The sleeve's `thesis` exit still encodes the design the CEO replaced.** Both TLT and DBC carry `"Answered by a human at every review"`, and `/exits/check` returns them under `unevaluable` on every tick. Until superseded to point at §3, the machinery still asks the weekly question.
5. **`nav_strike` has never run in this process** (`/liveness.unobserved`). Unknown, which is neither broken nor fine. NAV `live` and `last_struck` currently agree to the cent ($1,664.89 positions / $346.92 cash), so nothing is visibly wrong — but that is a coincidence of a static book, not evidence the striker works.
6. **TCA is unreliable and unchanged**: n=12 against a bar of 20, `reliable: false`. Trend at 21.47bps/side is 4.3× the 5bps every backtest charges — and Trend is the strategy being retired, so that measurement will not be repeated. **No fresh fills since the last review, so there is no new TCA verdict to give.**

---

## 5. Recommendations — one decision each

Tickets T1–T8 and S1–S3 in §1 are themselves the clickable recommendations for recs 1–6; these are the new ones this dispatch produced.

- **R1.** Approve the §3 invalidation conditions as the recorded sleeve fact (rec 9 redesign). One decision: accept, amend, or reject the record.
- **R2.** Supersede the TLT `thesis` exit note to point at the approved §3 record instead of "answered by a human at every review".
- **R3.** Same for DBC. (Separate from R2 so one can be accepted without the other.)
- **R4.** Retire the `machinery-test` GLD `loss_pct` 25% rule — either supersede it with the R7-proposed 13.6% rule (if GLD survives) or record an explicit override with the reason "test artifact, not portfolio policy". **Do not leave it armed.** It is the only live exit rule on the book that nobody chose as policy.
- **R5.** Record D5 and D6 as **explicitly untestable-today** rather than passing: TCA is at n=12 of 20, and there is no brokerage account for NAV to diverge from (`/compliance.account.error`). Two of the sleeve's four falsification conditions currently cannot be evaluated, and that should be on the record before the 2026-09-08 time exit, not discovered at it.
- **R6.** Review `min_effective_bets: 2.0` and `max_risk_concentration_pct: 0.50` **with the evidence in §1c** — a two-name hedged book concentrates measured risk above 50% by construction, so the limit will alarm on a book that is objectively less risky than today's. I recommend a review, not a change; the threshold moves only by a versioned change with a written reason, and that is the humans' call.
- **R7.** Commit the §2 exit rules on any position whose close ticket is rejected, **in the same session as the rejection** — not "before next review".

---

## 6. What I did not look at

Fees and accruals (`/fees`, `/fees/terms`); `/ledger/verify`; `/reconcile`; `/custody/*`; the raw event stream (`/events`) beyond what `/health.chain` reports; `/nav/history` and `/nav/intraday`; `/risk/history` and `/risk/alerts/history` (only the current `active: []`); `/risk/simulate`, `/risk/shock`, `/risk/whatif` — **`whatif` is a POST and I do not call POST endpoints, so every post-trade figure in §1c is my own replication of `correlation.py`, not the engine's answer**; `/signals`; `/memos`; `/factory/*`; `/research/*`; the 57 `null_random_smallcap` and 10 `oracle_calibration_only` sweeps; the gate's per-sweep verdict text (`/lean/gate/{sweep_id}` is POST-only, so the §4.2 verdicts are read from `holdout_result` fields, not from gate output); `/desk/requests`; the LEAN algorithm sources. Marks are as of 2026-08-20T03:16Z and have not moved since 2026-08-19T23:47Z, which I treat as a static book, not a verified-fresh one — `/health.checks.market_data` reports `stale: false` for SPY only.

I did **not** verify that the CEO's acceptance statuses in Postgres match what the CTO relayed beyond reading `/desk/runs/run-pm-review-1`, which shows recs 1–7 `accepted`, 8 `done`, 9 `rejected`, all `decided_by: "ceo"`.

**One self-correction, recorded because the bench's failure mode is confident imprecision:** mid-analysis I believed `/strategies` was reporting `realized_pnl_usd: 0.0` for a strategy whose true realised P&L is +$25.63, and was about to file it as a defect. It was my own misreading of a field-ordered print — the endpoint returns 25.63, and `/strategies/{id}` agrees. No defect. The check cost one call.

---

## STATE

```
## 2026-08-20 — second dispatch (1eef5264 / trace-pm-review-1): staging tickets, rec-7 exits, rec-9 redesign

- Book UNCHANGED from first review's marks: NAV 2011.81, cash 346.92 (17.24%),
  gross 1664.89 (82.76%), 9 positions, no fill since 2026-08-19T18:20 (sleeve
  TLT). Marks identical across the v4.1 restart. Treat as static, not fresh.
- CORRECTED my own memo: "gross → ~58%" was the FRAMEWORK's $500-partial-trim
  number (82.76 − 500/NAV = 57.91%), NOT full retirement. Full close of the
  three strategies = $1,164.35 of sells → gross 24.88%, cash 75.12%, realised
  −$14.35. Say this if anyone re-cites 58%.
- Throttle 0.7206. "Normal gross" is defined NOWHERE in code — throttle.apply_to
  has zero callers. Reading A (× book gross) = 59.63%/$465 of sells; Reading B
  (× 100%) = 72.06%/$215. I use A. Tickets T1–T4 ($523) satisfy it; fewer than
  T1–T4 = throttle ignored again, needs written override.
- 8 sell tickets issued (T1 SPY-TEST .052217 / T2 INTC 1.608762 / T3 SOFI
  9.18819 / T4 MSFT .340051 / T5 NVDA .749886 / T6 GLD .424471 / T7 XLE 2.749912
  / T8 SPY-Trend .16554) + 3 state tickets S1–S3 (pause+alloc 0+archive; do
  BEFORE the sells). Recommended disposition: CLOSE ALL — no legacy position
  survives on its own merits; survival-by-inertia makes orphans. If CEO wants
  GLD/XLE/SPY, it must be NEW pre-registered declared beta, not inheritance.
- KEY WARNING carried forward: risk concentration crosses the 50% limit at T6
  (DBC 62.3%) and reaches ~101% sleeve-only, because TLT/DBC corr is −0.4379 so
  TLT is a NEGATIVE risk contributor. Arithmetic, not danger. Effective bets
  3.88 → 2.49 (floor 2.0). riskengine.py:571-584 will warn. Expected.
- MECHANICAL FACTS I re-derived and must not re-derive: exit KINDS are only
  (loss_pct, gain_pct, time, thesis) — exitrule.py:41. No trailing/correlation/
  NAV-drawdown kind. Exit sizing is SYMBOL-level (exitrule.py:269,287) so a SPY
  rule sells all 0.217757. autopolicy has NO actor check — the "PRE-COMMITTED
  EXIT FIRED" marker alone (autopolicy.py:87-91) triggers auto-approval, so
  COMMITTING AN ALREADY-BREACHED RULE = EXECUTING. Always check the level
  against live unrealised before proposing. StrategyState has no "retired" —
  DEPLOYED→PAUSED only (strategies.py:24-37), and PAUSED does NOT close
  positions (proof: TEST paused, still holds $40.16 SPY).
- 1.5σ 21d levels (σ_ann×√(21/252), from /risk/advanced.correlation.
  annualised_vol_pct): TLT 4.10 (validates the frozen 4.0), DBC 9.83 (frozen 8.7
  = 1.33σ today), GLD 13.61, XLE 10.18, SPY 5.79, MSFT 15.97, NVDA 16.23,
  SOFI 23.25, INTC 36.33. None breached today.
- LIVE GATE EVIDENCE (better than docs/book_rejudged.json v2): /lean/sweeps now
  serves 84 sweeps with holdout_result. mean_reversion_cyclicals = ZERO orders
  in ALL 5 holdouts, psr 0.0 everywhere. momentum fold PSRs 41.5/18.3/64.6/9.5
  → 0 of 4 clear 65.0 (best misses by 0.42). trend 2.7/0.0/85.3/15.8 → 1 of 4.
  Gate v4.1: min_psr 65, min_orders 20, 4 folds strict majority (gate.py:165,183).
- TCA UNCHANGED (no fresh fills): n=12 of 20, reliable:false, 4.96 vs 5.0 bps;
  Trend 21.47bps/side (worst 81.22); sleeve 0.00bps on 2 fills, latency 189.3s.
  The 8 sell tickets take n 12→20 = exactly the bar, and discharge sleeve
  falsification #2. Only argument in the memo for doing more rather than less.
- OPEN EXCEPTIONS: (1) machinery-test GLD loss_pct 25% is LIVE, not overridden,
  and would auto-execute a full-GLD sell — R4. (2) sleeve thesis exit notes still
  say "answered by a human at every review", the design the CEO replaced — R2/R3.
  (3) sleeve is absent from /strategies AND /strategies/divergence entirely —
  framework §3 gap now MEASURED true. (4) nav_strike UNOBSERVED in this process.
- Rec 9 redesign delivered: TLT + DBC recorded theses, D1–D9 deterministic
  (only D1–D3 both watch AND act; D5 currently TRIPPED at n=12; D6 UNTESTABLE —
  simulated venue, no broker equity; D7 has NO machinery), J1–J6 judgemental.
  J6 replaces "a week with no written review": 7+ days with neither a PM dispatch
  nor a written note. CLOCK FROM 2026-08-19 FILLS → FIRST TRIP 2026-08-26.
- Time exit on_date 2026-09-08 is 21d from the rule-SET date (08-18) = 20d from
  FILL (08-19). Frozen date stands; recorded so nobody claims 21-from-fill.
- Self-correction logged: I nearly filed a realized_pnl_usd=0.0 "defect" that was
  my own field-ordered print misreading. /strategies returns 25.63 correctly.
- NEXT REVIEW: check which tickets executed and re-run the §1c arithmetic on what
  actually filled; expect a risk_concentration warn alarm if T6+ executed and do
  NOT read it as new; check TCA n (should be 20 if the batch went) and give the
  first RELIABLE cost verdict; check whether R2/R3 superseded the thesis notes;
  check J6 clock (2026-08-26) and D5/D6 status before the 2026-09-08 time exit.
```
---

## CTO verification notes (2026-08-20, at resolve)

Spot-checked before acting; both CONFIRMED:

1. **Exception 1 (machinery-test GLD rule)**: `/fund/exits` shows the GLD
   `loss_pct` 25% rule live with `overridden_at: None` while its INTC sibling
   was overridden — exactly as the memo states. Filed as recommendation R4.
2. **Strategy lifecycle**: `/fund/strategies/{id}/state` and `/allocation`
   exist as described; the three retirements were executed at resolve
   (paused + allocation 0, actor cto). Archive deferred until positions are
   flat — an archived strategy holding open positions distorts attribution.

Actions taken at resolve: S1–S3 executed minus archive. T1–T8 NOT staged
overnight — `PROPOSAL_STALE_AFTER_MINUTES = 120` (pipeline.py:40) would have
auto-declined every ticket before the CEO woke; they stage fresh when the CEO
is live, quantities as committed in §1c, notionals re-marked. R1–R7 recorded
as decidable recommendations on run-pm-staging (trace-pm-review-1).
