# GEMINI.md — ClarkHarness (Krypton Fund spine)

You are the implementer. This is the **spine** — the single source of deterministic
truth for the whole fund (event-sourced: NAV, unit ledger, positions, risk). The
frontend and the agent orchestrator only *read* it. Work in small commits; keep the
test suite green.

## Non-negotiable ground rules
1. **Everything auditable is an event.** State is folded from the append-only event
   log (`app/fund/events.py` + projections). Never mutate state in place; never keep a
   second copy of the truth.
2. **Deterministic. No fabricated numbers, no randomness in logic.** (`Math.random`'s
   Python cousins are banned in the core.)
3. **Tests are the contract.** Run `./venv/Scripts/python.exe -m pytest -q` — it must
   stay green (68 tests today). New capability ships WITH tests.

## Current priority — implement the Risk Engine
Full spec: **`docs/RISK_ENGINE_SPEC.md`**. This is the fund's most important safety
system (a real Friends-&-Family fund; capital preservation first). Implement Tasks 1–6:
1. `RiskControl` — fold limits + kill-switch state from events.
2. `RiskMonitor.assess()` — the full risk picture (the observability pane).
3. `evaluate_alarms()` + `run()` — persist alarm events (dedup) + **auto-halt** on a
   drawdown/daily-loss breach.
4. Pipeline halt-check: block BUYs when halted, **always allow SELLs** (must be able to
   de-risk while halted).
5. Endpoints in `app/api/v1/fund.py` + schemas (contracts are in the spec).
6. `tests/test_riskmonitor.py` — the "can't screw this up" gate (drawdown kill-switch,
   halt-blocks-buys, alarm dedup, each alarm type, `assess()` shape, human-only resume).

**Already scaffolded — build on it, don't recreate:**
- `app/fund/events.py` — the 5 new risk event types.
- `app/fund/risk.py` — `RiskLimits` with mandate controls + `to_dict`/`from_dict`.
- `app/fund/riskmonitor.py` — the SKELETON with the full contract (the `assess()`
  docstring is canonical). Implement every `NotImplementedError`.

## Verify before every commit
```bash
./venv/Scripts/python.exe -m pytest -q     # all green, incl. new test_riskmonitor
```

## Guardrails on the risk logic (get these exactly right)
- Kill-switch auto-engages on a **critical** drawdown or daily-loss alarm; it **never**
  auto-resumes (human only).
- Alarms dedup by a stable `key` — a standing breach raises once, clears once.
- `GET /fund/risk/monitor` is a **pure read** (no event writes). Only `run()` writes.
