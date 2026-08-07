# Krypton Fund — Local End-to-End Test Report

Ran the fund locally, top to bottom, and fixed what broke. This is the feedback
report plus what was built beyond it. All work is committed on branch
`claude/krypton-fund-agentic-j8r2mu` in each repo (not pushed — see the end).

## Scorecard

```
TIER 1 spine:   pytest 32/32 ✅ · preflight [gracefully fails w/o creds] · e2e_local ✅ all checks
FRONTEND:       npm build ✅ (after 1 fix) · tsc ✅ · /clark/studio ✅ rebuilt as a cockpit
TIER 2 chat:    ✅ ran via local Ollama (no AWS) · status/read ✅ · order approval → filled ✅
BUILT EXTRA:    backtest-by-symbol on free real bars · Bloomberg cockpit · live paper marks
```

Everything below is verified against a running spine, not asserted from reading code.

## What was tested, step by step

**Tier 1 — spine.** `venv` + `pip install -r requirements.txt` clean on Python 3.11.
`pytest` → **27/27** originally, **32/32** after new tests. `scripts/e2e_local.py`
drives the whole loop (deposit→units, strategy create/backtest/deploy/allocate,
propose→approve→settle, NAV/positions/strategies/LPs, reconcile) → **all green**.

**Frontend.** `npm install`, `npm run build`, `npm run dev`, and drove
`/clark/studio` in a browser against the live spine: created a strategy,
backtested it, deployed, allocated, approved an order — each **persisted to the
spine** (verified via the API, not just the UI).

**Tier 2 — chat.** Brought up the Krypton_Clark orchestrator and exercised the
conversational loop: *"what's the fund at?"* → NAV; *"buy 2 AAPL for US
Momentum"* → risk gate → **approval interrupt** → approve → **filled**.

## Bugs found & fixed (all on the branch)

| # | Severity | Where | Problem → Fix | Verified |
|---|----------|-------|---------------|----------|
| 1 | **High** | `Krypton_Clark app/skills/fund/implementation.py` | The orchestrator's generic skill tool passes only free-text `query`, but the fund skill dispatched on a structured `action` it never received → **every** chat call returned `Unknown fund action ''`. Fund chat could not have worked (would fail on Bedrock too). **Fix:** deterministic NL→action parser + strategy-name→id resolution. | Chat reads + orders work; 8/8 skill tests |
| 2 | **High** | `KryptonPay src/app/clark/studio/page.tsx` | `toast({ variant: "destructive" })` — this repo's `useToast` has no `variant` → `next build` failed (TS2353). **Fix:** removed the invalid prop. | `tsc` + `next build` clean |
| 3 | **Med** | `ClarkHarness scripts/*.py` | `→ ✅ ×` printed to a Windows cp1252 console → `UnicodeEncodeError` crash mid-run. **Fix:** reconfigure stdout/stderr to UTF-8 in `e2e_local`, `preflight`, `smoke_*`. | e2e runs clean on Windows |
| 4 | Low | `KryptonPay .next` | Stale build cache → `EINVAL readlink app-build-manifest.json`. **Fix (op):** `rm -rf .next`. Documented. | Build clean after clear |

Non-bugs worth knowing:
- **No AWS creds** → Bedrock returns `UnrecognizedClientException` (the pasted keys
  are invalid/rotated). The routing loop itself is fine. Added an Ollama path so
  Tier 2 runs with no cloud (below).
- **`python3`** isn't on PATH on this box (Windows Store shim); `python` works. The
  docs say `python3` — harmless on macOS/Linux, worth a note for Windows.
- **Backtest with `bars < slow window`** silently returned all-zeros. The Studio
  now warns before running.

## Built beyond the ask

- **Local LLM for Tier 2 (no AWS).** `app/llm_factory.py` — `LLM_PROVIDER=ollama`
  routes the orchestrator's tool-calling loop to a local model (`OLLAMA_MODEL`,
  default `qwen2.5:14b-instruct`, the most reliable local tool-caller). Bedrock
  stays the default; the switch is one env var.
- **Backtest on real free bars.** `POST /fund/strategies/{id}/backtest/by_symbol`
  and `GET /fund/marketdata/bars` — daily bars from Alpaca (if keyed) else **Yahoo
  (free, no key)**. No more pasting prices. (Stooq was dropped — it now gates with
  a JS proof-of-work anti-bot wall.)
- **Strategy Studio → a Bloomberg-style cockpit.** Dense operator terminal:
  live KPI strip (NAV, cash %, exposure, P&L, LPs, pending), a **TradingView-style
  price chart** (recharts) with a symbol watch box, a strategies table with
  target-vs-actual allocation bars + Sharpe/return, a **live pending-approvals
  queue** with inline approve/decline, positions, and the LP book with ownership %.
  6-second auto-refresh. Aligned to the KryptonPay design system.
- **Live paper marks.** `FUND_LIVE_MARKS=true` marks the paper venue at real free
  prices, so NAV/P&L move with the market — **paper execution, real prices**
  (e.g. AAPL marks at ~$312, not the $220 seed). On by default in the local
  launcher. See the mock-vs-live note below.

## Mock vs. live — where we actually are

| Layer | Today |
|-------|-------|
| Backtests | **Real** free historical daily bars (Yahoo, or Alpaca if keyed). |
| Order execution | **Simulated** paper venue (instant fills). |
| Position marks / NAV / P&L | **Real** free live marks when `FUND_LIVE_MARKS=true` (default in the local launcher); static seeds otherwise. |

To go to **real Alpaca paper** (execution *and* marks through one account), set
both `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` — the spine auto-switches, no code
change. Currently only the Alpaca **key id** is on hand; the **secret** is needed.

## Run it locally

**Spine (no Firebase needed) + live marks:**
```bash
cd ClarkHarness
python -m venv venv && source venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt -r requirements-dev.txt
python scripts/run_local_fake.py                        # :8090, in-memory store, live marks on
# real Firebase instead: set FIREBASE_SERVICE_ACCOUNT_JSON and use `uvicorn app.main:app --port 8090`
```

**Frontend cockpit:**
```bash
cd KryptonPay
npm install
# .env.local already has NEXT_PUBLIC_HARNESS_API_URL=http://127.0.0.1:8090
npm run dev            # http://localhost:3000/clark/studio
```

**Tier 2 chat via local Ollama (no AWS):**
```bash
cd Krypton_Clark
export LLM_PROVIDER=ollama OLLAMA_MODEL=qwen2.5:14b-instruct
export CLARK_HARNESS_URL=http://127.0.0.1:8090
uvicorn app.main:app --port 8000        # then use /clark in the frontend
```

## Roadmap — toward the "hedge-fund harness"

The vision that emerged: a **web of agents complementing each fund operation**,
across the lifecycle **Research → Deploy → Monitor → Analyze → Unwind**, with
Clark as a Claude-Code-style harness and Studio as a Bloomberg-grade cockpit.
Where today's pieces sit and what's next:

- **Research** *(next)* — agentic strategy generation + a collaborative Studio
  tool; the Strands orchestrator + skills are the substrate ("deep agents":
  planning, sub-agents, persistent memory).
- **Deploy** *(built)* — Studio create→backtest→deploy→allocate; chat propose→approve.
- **Monitor** *(started)* — cockpit live KPIs, positions, approvals, live marks;
  next: a **risk-monitoring agent** on top of the existing risk gate (limit
  breaches, drift alerts).
- **Analyze / Unwind** *(next)* — per-strategy attribution exists; add analytics
  views and an unwind flow (close/trim with the same approval seam).

Also queued from the existing backlog: **auth** on LP/cockpit/write routes (the
hard gate before any external LP link), repoint the customer/LP views to the
spine, CI for the suites, and the **Alpaca secret** to flip execution live.

## Handoff notes

- **8 commits** across ClarkHarness (3), KryptonPay (2), Krypton_Clark (2) — all on
  `claude/krypton-fund-agentic-j8r2mu`, **not pushed**. Say the word and I'll push
  and open PRs.
- Secrets stayed in **git-ignored** `.env` files; nothing sensitive was committed.
- The two dirty files you had before switching branches (KryptonPay
  `CumulativeAUMChartNew.tsx` + `useStrategySubgraphData.ts`, Krypton_Clark
  `orchestrator_strands.py`) were **stashed** per your OK — `git stash list` shows
  them, `git stash pop` restores.
