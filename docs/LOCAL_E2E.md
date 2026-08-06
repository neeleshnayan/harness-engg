# Run it locally — end-to-end

All the work is on branch **`claude/krypton-fund-agentic-j8r2mu`** in each repo.
"Updating your local repos" = fetch + checkout that branch.

## Two tiers of testing

- **Tier 1 — spine + frontend (no LLM).** Tests the whole fund loop *except* chat.
  Needs Firebase; Alpaca optional (falls back to the in-Firestore paper venue).
- **Tier 2 — full agentic.** Adds the orchestrator (Krypton_Clark) + optionally
  Clark_MCP for the conversational + approval loop. Also needs AWS Bedrock.

Start with Tier 1 — it exercises everything the fund does; Tier 2 adds the chat.

## Update each local repo

```bash
cd <repo>
git fetch origin claude/krypton-fund-agentic-j8r2mu
git checkout claude/krypton-fund-agentic-j8r2mu
git pull
```

Repos: **ClarkHarness** (spine), **KryptonPay** (frontend), **Krypton_Clark**
(orchestrator, Tier 2), **Clark_MCP** (optional). KryptonPay_Backend is the
payments product — not needed for the fund.

## Ports (avoid clashes)

| Service | Port |
|---|---|
| Krypton_Clark orchestrator | 8000 |
| Krypton Web3 backend | 8001 |
| **ClarkHarness spine** | **8090** |
| KryptonPay frontend | 3000 |

---

## Tier 1 — spine + frontend

**1. ClarkHarness (spine) on :8090**
```bash
cd ClarkHarness
python3 -m venv venv && source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
# put firebase_service_account.json in the repo root (git-ignored)
export FIREBASE_SERVICE_ACCOUNT_JSON=firebase_service_account.json
# optional live venue (else paper): export ALPACA_API_KEY=... ALPACA_SECRET_KEY=... ALPACA_PAPER=true
python3 scripts/preflight.py                          # verify Firebase/Alpaca reachable
uvicorn app.main:app --port 8090
```

**2. KryptonPay (frontend) on :3000**
```bash
cd KryptonPay
npm install
echo "NEXT_PUBLIC_HARNESS_API_URL=http://127.0.0.1:8090" >> .env.local
npm run dev
```
Open **http://localhost:3000/clark/studio** — create → backtest → deploy →
allocate strategies against the live spine.

**3. Drive the fund loop directly (no UI) — curl against :8090**
```bash
H=http://127.0.0.1:8090/api/v1/fund

# Seed an LP deposit (off-platform money, recorded)
curl -s -XPOST $H/lp/subscriptions -H 'content-type: application/json' \
  -d '{"lp_id":"aisha","usd_amount":1000,"lp_name":"Aisha"}'      # -> {subscription_id}
curl -s -XPOST $H/lp/subscriptions/<subscription_id>/confirm -H 'content-type: application/json' \
  -d '{"actor":"rushi"}'                                          # mints units at NAV

# Create + deploy + allocate a strategy
curl -s -XPOST $H/strategies -H 'content-type: application/json' -d '{"name":"Momentum"}'   # -> {strategy_id}
curl -s -XPOST $H/strategies/<strategy_id>/state -H 'content-type: application/json' -d '{"state":"deployed"}'
curl -s -XPOST $H/strategies/<strategy_id>/allocation -H 'content-type: application/json' -d '{"target_pct":40}'

# Propose -> approve -> settle an order
curl -s -XPOST $H/orders/propose -H 'content-type: application/json' \
  -d '{"symbol":"AAPL","side":"buy","qty":2,"strategy_id":"<strategy_id>"}'   # -> {order_id, impact_preview}
curl -s -XPOST $H/orders/<order_id>/approve -H 'content-type: application/json' -d '{"approver":"rushi"}'
curl -s -XPOST $H/orders/settle                                               # async fill tick

# Read state
curl -s $H/nav ; curl -s $H/positions ; curl -s $H/strategies ; curl -s $H/lps
curl -s -XPOST $H/reconcile                                                   # book vs venue
```
(The lifespan scheduler also settles + strikes NAV + reconciles on a timer.)

---

## Tier 2 — full agentic (chat + interrupts)

**4. Krypton_Clark (orchestrator) on :8000** — see its own README. Needs AWS
Bedrock + Firebase. Point it at the spine:
```bash
export CLARK_HARNESS_URL=http://127.0.0.1:8090
uvicorn app.main:app --port 8000
```
The frontend's dev proxy already sends `/api/v1/agents/*` to :8000.

**5. Test the conversation:** open **/clark**, ask *"what's the fund at?"* →
status; *"buy 10 AAPL for the momentum strategy"* → the `fund` skill proposes and
raises `krypton-fund-order-approval`.

> Note: the chat approval **card** for fund orders needs the `InterruptModal`
> generalization (next UI task). Until then, approve fund orders from the Studio /
> REST / the cockpit pending queue. Reads and strategy management via chat work now.

**6. Clark_MCP (optional)** — point `STRANDS_BASE_URL` at the orchestrator to use
Clark from any MCP client.

---

## What's already verified (in CI-less form)
- Spine + ledger + strategy + settlement + backtest: `pytest` (ClarkHarness) — all green.
- Fund skill dispatch + approval flow: `pytest tests/test_fund_skill.py` (Krypton_Clark) — green.
- Frontend (Studio) compiles against the app's conventions; verify with `npm run build`.
