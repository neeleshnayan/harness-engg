# Risk Engine & Observability — Implementation Spec (for Gemini)

**Audience:** the AI coding agent implementing this. **Owner of the design:** the
architect (do not change contracts without flagging).

## Why this exists (the bar)
This runs a real Friends-&-Family fund. The mandate is **capital preservation
first**. Two outcomes must be true when this is done:
1. **We cannot silently blow up.** Continuous monitoring of every asset and the
   whole portfolio, with a **hard drawdown kill-switch** that halts trading
   automatically, and **auditable alarms** the moment anything breaches.
2. **Rushi can see exactly what's happening across the portfolio at any instant** —
   one observability pane. The **Risk tab** and **Strategies tab** must *close*
   (be fully real, no placeholders) against this.

Everything is deterministic and lives in the **spine** (`ClarkHarness`). The
frontend only *reads* it. **Never fabricate or hardcode a risk number.**

## What is already scaffolded (do not re-create — build on it)
- `app/fund/events.py` — new event types: `RISK_LIMITS_SET`, `RISK_ALARM_RAISED`,
  `RISK_ALARM_CLEARED`, `TRADING_HALTED`, `TRADING_RESUMED`.
- `app/fund/risk.py` — `RiskLimits` extended with mandate controls + `to_dict` /
  `from_dict` (capital-preservation defaults). This is the ONE limits config.
- `app/fund/riskmonitor.py` — **SKELETON with the full contract**: `RiskControl`,
  `RiskMonitor`, `Alarm`. The `assess()` docstring is the canonical response shape.
  **Your job is to implement every `NotImplementedError`.**

---

## Task 1 — Implement `RiskControl` (`app/fund/riskmonitor.py`)
Fold events into state (mirror how `ThesisRegistry` / `OrdersProjection` fold):
- `limits()` → latest `RISK_LIMITS_SET` payload merged onto `RiskLimits()` via
  `RiskLimits.from_dict`. Default when none set.
- `set_limits(patch, actor)` → merge patch onto current, emit `RISK_LIMITS_SET`
  with the full resulting dict, return `RiskLimits`.
- `is_halted()` → fold `TRADING_HALTED`/`TRADING_RESUMED` on aggregate `"fund"`;
  True if the last one is a halt.
- `halt(reason, actor)` → emit `TRADING_HALTED {reason}` (idempotent: if already
  halted, no-op and say so). `resume(actor)` → emit `TRADING_RESUMED`.
- `active_alarms()` → fold `RISK_ALARM_RAISED`/`RISK_ALARM_CLEARED` keyed by
  `payload.key`; return the raised-not-cleared set, newest first, as dicts.
- `alarm_history(limit)` → recent raised+cleared events, newest first.

## Task 2 — Implement `RiskMonitor.assess()`
Build the exact dict in the skeleton's docstring from live truth:
- NAV / cash / gross from `NavService.compute()`.
- **Drawdown:** `peak_nav = max(all struck NAV in NavService.history(365), current)`;
  `drawdown_pct = (peak - current)/peak * 100`; `max_drawdown_pct` = worst point in
  history. `utilization = drawdown_pct / (max_drawdown_pct_limit*100)`.
- **Per-asset:** for each position — weight %, `unrealized_pnl_pct` = (mark − avg
  cost)/avg cost × 100 (the "going down" signal), `shock_20_usd` = value × −0.20.
- **Per-strategy:** from `StrategyAttribution.with_values(pricer)` — exposure,
  weight %, pnl; `breach = weight_pct > max_strategy_pct*100`.
- `limits` = `control.limits().to_dict()`; `utilization` map per limit.
- `alarms` = `evaluate_alarms(assessment)` as dicts; `worst_position` = most
  underwater. `halted` = `control.is_halted()`.

## Task 3 — Implement `evaluate_alarms()` and `run()`
- `evaluate_alarms()` is **pure** — apply the six rules in the skeleton docstring;
  return `Alarm` list with stable `key`s (`"drawdown"`, `"concentration:AAPL"`,
  `"cash_floor"`, `"underwater:NVDA"`, `"strategy_cap:<id>"`, `"daily_loss"`).
- `run(actor)` — the tick:
  1. `a = assess()`; `current = evaluate_alarms(a)` keyed by `key`.
  2. Diff vs `control.active_alarms()`: emit `RISK_ALARM_RAISED` for new keys,
     `RISK_ALARM_CLEARED` for keys no longer breaching. **Never duplicate a
     standing alarm.**
  3. **Auto-halt:** if any *critical* alarm of type `drawdown` or `daily_loss` is
     active and not already halted → `control.halt(reason, actor="monitor")`.
     Never auto-resume (human only).
  4. Return `{"raised": [...], "cleared": [...], "halted": bool, "active": [...]}`.

## Task 4 — Pipeline integration (`app/fund/pipeline.py`)
- In `propose_order`, **before** the risk gate: if `RiskControl(store).is_halted()`
  and `order.side == BUY` → reject with breach `"trading halted (risk kill-switch)"`.
  **Allow SELLs** (must always be able to de-risk/exit while halted).
- Pass the **configured limits** into the `RiskGate` (construct
  `RiskGate(control.limits())` where the pipeline builds the gate) so gate + monitor
  share one config. Add per-strategy cap to the gate check if feasible; otherwise
  leave gate as-is and rely on the monitor for the strategy cap.
- After a fill is booked in `approve_order`, call `RiskMonitor(...).run()` so a bad
  fill re-evaluates immediately. Keep it best-effort (wrap in try/except; a monitor
  error must never break execution).

## Task 5 — Wiring in `app/api/v1/fund.py`
Construct once near the other services:
```python
_control = RiskControl(store=_store)
_monitor = RiskMonitor(nav_service=_nav, store=_store, pricer=_connector.price,
                       attribution=_attribution, strategies=_strategies, control=_control)
```
Endpoints (schemas in `app/schemas/fund.py`):
| Method / path | Body | Returns |
|---|---|---|
| `GET /fund/risk/monitor` | — | `_monitor.assess()` (pure read; poll this for the live pane) |
| `GET /fund/risk/alerts` | — | `{"active": _control.active_alarms()}` |
| `GET /fund/risk/alerts/history?limit=100` | — | `{"history": _control.alarm_history(limit)}` |
| `POST /fund/risk/monitor/run` | `{actor}` | `_monitor.run(actor)` (worker + manual) |
| `GET /fund/risk/limits` | — | `_control.limits().to_dict()` |
| `POST /fund/risk/limits` | `{patch:{}, actor}` | updated limits dict |
| `POST /fund/risk/halt` | `{reason, actor}` | halt result |
| `POST /fund/risk/resume` | `{actor}` | resume result |

Also add a worker hook `run_risk_monitor()` next to `run_settlement()` and, if there
is a scheduled worker loop, call it every ~30–60s. `GET /fund/risk/monitor` MUST stay
a pure read (no event writes) — only `run()` writes.

## Task 6 — Tests (`tests/test_riskmonitor.py`) — REQUIRED, this is the "can't screw up" gate
Use the `wire` fixture pattern (fake Firestore). Cover at minimum:
1. **Drawdown kill-switch:** seed capital, buy, strike NAV, drop the pricer so NAV
   falls past `max_drawdown_pct` → `run()` emits a `drawdown` `RISK_ALARM_RAISED`
   **and** `TRADING_HALTED`; `is_halted()` is True.
2. **Halt blocks buys, allows sells:** while halted, `propose_order(BUY)` is
   rejected; `propose_order(SELL)` passes the gate.
3. **Alarm dedup:** two consecutive `run()`s on the same standing breach raise the
   alarm **once**; when the breach resolves, exactly one `RISK_ALARM_CLEARED`.
4. **Concentration + underwater + cash-floor + strategy-cap** each raise the right
   alarm type at the right threshold and clear when back in bounds.
5. **`assess()` shape:** returns every key in the contract; numbers reconcile with
   NAV/positions.
6. **Resume is human-only:** `run()` never emits `TRADING_RESUMED`.

Run `./venv/Scripts/python.exe -m pytest -q` — all green (existing 68 + new).

---

## Task 7 — Frontend: close the RISK tab (`KryptonPay/src/app/clark/studio/risk/page.tsx`)
Add client methods to `src/lib/fund_api.ts`: `getRiskMonitor()`, `getRiskAlerts()`,
`getRiskAlertHistory()`, `runRiskMonitor()`, `getRiskLimits()`, `setRiskLimits(patch)`,
`haltTrading(reason)`, `resumeTrading()` — each hitting the endpoints above with the
response types from the `assess()` contract.

The Risk page must be **100% real** (the fabricated audit logs were already removed
— do not reintroduce). It should show, all polling `GET /fund/risk/monitor` every
3–5s:
- A **kill-switch banner**: if `halted` → red "TRADING HALTED — {reason}" with a
  **Resume** button (calls `resumeTrading`); else green "Live" with a **Halt** button.
- **Drawdown gauge** (current vs peak vs limit) + **limit-utilization gauges**
  (position / strategy / cash / drawdown) driven by `utilization`.
- **Live alarm feed** from `GET /fund/risk/alerts` (active) + `.../history` — this
  REPLACES the deleted fake audit log. Color by severity; show metric vs threshold
  and timestamp. Empty state when none.
- **Per-asset risk table** from `assess().positions` (weight, unrealized P&L %,
  20% shock) — red rows for underwater/over-weight names.
- A **limits editor** (form → `setRiskLimits`) so the mandate is tunable + audited.

## Task 8 — Close the STRATEGIES tab risk view (`.../strategies/page.tsx`)
Use `assess().strategies[]` (or the existing `GET /fund/strategies/{id}/risk`) to show
**per-strategy** exposure, weight, P&L, limit utilization, and a `breach` flag — so
each strategy's risk sits next to its assets. No hardcoded ids or numbers.

---

## Acceptance / verification
```bash
cd ClarkHarness && ./venv/Scripts/python.exe -m pytest -q          # all green incl. test_riskmonitor
curl -s localhost:8090/api/v1/fund/risk/monitor | jq '.drawdown, .halted, (.alarms|length)'
cd ../KryptonPay && npx tsc --noEmit && npm run build              # 0 errors
grep -rnE "Math\.random|hardcoded|102978" src/app/clark/studio/risk src/app/clark/studio/strategies || echo clean
```
Done = kill-switch works and auto-halts on drawdown; alarms raise/clear once and are
auditable; the Risk tab shows only real data with a working halt/resume; the
Strategies tab shows real per-strategy risk.
