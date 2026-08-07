# Rushi — testing the Krypton Fund locally

Three services + a browser. Everything is on branch
`claude/krypton-fund-agentic-j8r2mu` in each repo.

## Start (3 terminals)

**1. Spine (fund engine)** — Alpaca paper if keys are in `ClarkHarness/.env`, else the free paper venue:
```bash
cd ClarkHarness && source venv/Scripts/activate
USE_FAKE_FIRESTORE=1 FUND_LIVE_MARKS=true uvicorn app.main:app --port 8090
```

**2. Clark (the brain)** — local LLM, no AWS needed:
```bash
cd Krypton_Clark && source venv/Scripts/activate
LLM_PROVIDER=ollama OLLAMA_MODEL=qwen2.5:14b-instruct CLARK_HARNESS_URL=http://127.0.0.1:8090 \
  uvicorn app.main:app --port 8000
```

**3. Frontend:**
```bash
cd KryptonPay && npm run dev      # http://localhost:3000
```

**Seed a demo fund (one command, optional but recommended):**
```bash
cd ClarkHarness && HARNESS_URL=http://127.0.0.1:8090 python scripts/seed_demo.py
```

## What to try

| Where | Do this |
|-------|---------|
| **Cockpit** — http://localhost:3000/clark/studio (or /admin) | See NAV, LPs, positions, live chart. Create a strategy → **Backtest → "By symbol"** (type AAPL) → Deploy → Allocate. Approve/decline the pending order in the right rail. |
| **Chat** — http://localhost:3000/clark | Ask *"what's the fund at?"*, *"show me the strategies"*. Try *"buy 2 AAPL for US Momentum"* → an **approval card** appears → approve → it routes to the venue. |

## Good to know

- **Alpaca paper:** approved orders are real paper orders. Outside market hours they sit **Accepted** and **fill at the open (9:30am ET)** — the position shows once it settles.
- **Ephemeral store:** `USE_FAKE_FIRESTORE` keeps state in memory — restarting the spine resets the fund. Re-run `seed_demo.py`. (For persistence, set `FIREBASE_SERVICE_ACCOUNT_JSON` and drop `USE_FAKE_FIRESTORE`.)
- **Backtest data** is real & free (Yahoo). SMA needs enough bars (fast<slow<lookback).
- Full detail + what was fixed: `ClarkHarness/docs/LOCAL_TEST_REPORT.md`.
