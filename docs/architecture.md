# Krypton Fund — Harness Architecture (Phase 1)

> **Status:** design spec, phase 1.
> **Companion diagram:** the command-lifecycle + repo-topology figure produced alongside this doc.
> **One-line thesis:** audit, reconciliation, risk, idempotency, approval, and orchestration are not
> six subsystems — they are gates and projections on a single event-sourced command lifecycle.

---

## 1. Goals & non-goals

**Goal.** A "Claude Code for the fund": an agentic interface where the operator (Rushi) sources and
makes decisions with the harness as a complement, and LPs get a read-only view to understand their
portfolio. Rushi keeps ownership of the fund; the AI orchestrates, it does not custody.

**Phase 1 scope (locked).**

| In | Out (later) |
|----|-------------|
| IBKR execution (equities/ETFs) via LEAN | Uniswap / any on-chain trading → **Phase 2** |
| USDC as the cash & deposit rail (Circle) | Vault-token / on-chain unitization → **Phase 3, if ever** |
| Pooled custody + **off-chain** unit ledger | Management/performance fees (leave the hook) |
| Human approval on every financial action | Multi-strategy / multi-PM |

**Non-goals for phase 1.** No Kafka / dedicated event-store DB (Firestore append-only collection is
enough at this scale). No autonomous execution. No client-side financial math.

**Testing posture.** We test with our own money at F&F scale first. Legal structure is a parallel,
later workstream and deliberately does **not** block the build — the technical design (pooled unit
ledger) is identical regardless of the eventual legal wrapper.

---

## 2. Technical principles

1. **Modular connectors** — every venue implements one interface; adding a venue is a new connector,
   zero upstream change.
2. **Venue-agnostic execution** — the pipeline and agent speak only to the connector interface, never
   to a venue SDK directly.
3. **Event-driven state** — execution is asynchronous (fills and confirmations arrive later); state is
   derived by folding an append-only event log, never mutated in place.
4. **Idempotent execution** — every command carries an idempotency key; retries never double-execute.
5. **Human approval for financial actions** — the `Proposed → Approved` transition is a hard gate.
6. **AI as orchestration, not custody** — the agent emits commands and reads projections; keys and
   custody live only inside connectors, behind the approval gate.

---

## 3. The command lifecycle (the spine)

Every financial action is a **Command** — an *intent*, not a fact. It flows through a fixed pipeline:

```
Command  ──▶  Risk Gate  ──▶  Human Approval  ──▶  Connector  ──▶  Event Log  ──▶  Projections
(intent)      (limits,        (approve_interrupt)  (venue-        (append-only,     (NAV, ledger,
              dup-guard)                             agnostic,      source of         audit,
                                                     async)         truth)            positions, risk)
```

- The **event log is the single source of truth.** Everything readable is a fold over it.
- **Rejections are events too.** A blocked trade is recorded and auditable — it is not a silent no-op.
- The **risk gate reads live state from the projections**; it is stateful but never keeps its own copy
  of the truth.
- The **approval gate reuses `krypton_approve_interrupt`**, which already exists in `clark_mcp`.

### 3.1 Commands (phase 1)

| Command | Emitted by | Effect on approval |
|---------|-----------|--------------------|
| `PlaceOrder` | operator, LEAN signal | submit an IBKR order via connector |
| `Rebalance` | operator | expand into a set of `PlaceOrder`s toward a target allocation |
| `Subscribe` | operator (on LP deposit) | record subscription; mint units at next struck NAV |
| `Redeem` | operator (on LP request) | burn units at next struck NAV; queue payout |
| `StrikeNav` | scheduler / operator | snapshot NAV across venues + cash → new `nav_per_unit` |

Every command envelope carries: `command_id`, `idempotency_key`, `actor` (user **or** agent),
`ts`, `payload`.

---

## 4. Event catalog

Events are immutable, append-only, and ordered per aggregate (per order, per LP, per fund).

**Order lifecycle**
- `OrderProposed` — passed risk, awaiting approval (payload: venue, symbol, side, qty, est. impact)
- `OrderRejected` — failed the risk gate (payload: rule, breach detail) *(terminal)*
- `OrderApproved` — human approved (payload: approver, ts)
- `OrderDeclined` — human rejected *(terminal)*
- `OrderSubmitted` — connector accepted it (payload: `venue_ref`, idempotency_key)
- `OrderFilled` — fill confirmed (payload: fill qty, avg price, fees) *(terminal)*
- `OrderPartiallyFilled` — partial fill (payload: cumulative qty)
- `OrderFailed` — venue/broadcast failure (payload: reason) *(terminal)*

**Subscription / redemption**
- `SubscriptionRequested` → `CashConfirmed` → `UnitsIssued`
- `RedemptionRequested` → `UnitsBurned` → `PayoutSent`

**Valuation & reconciliation**
- `NavStruck` — (payload: total_nav_usd, units_outstanding, nav_per_unit, breakdown{ibkr, cash})
- `ReconciliationMismatch` — internal state diverged from venue truth (payload: field, expected, actual)

> **Audit log = this event stream.** No separate audit system. Each event already carries
> `{ts, actor, venue, order_details, tx_hash|venue_ref, status}` (requirement §7). "Show the audit
> trail" is a query over events.

---

## 5. Projections (read models)

Projections are built by folding events. The frontend and the agent's read tools consume **only**
projections — never raw events, never venue SDKs.

| Projection | Folds | Answers |
|-----------|-------|---------|
| `nav_snapshots` | `NavStruck` | current NAV, NAV/unit, breakdown by venue + cash |
| `unit_ledger` / `holdings` | `UnitsIssued`, `UnitsBurned` | who owns how many units, current $ value each |
| `positions` | `OrderFilled`, venue truth | live position book by venue/asset |
| `audit` | *all events* | the immutable action trail |
| `risk_state` | fills, `NavStruck` | current exposures, today's realized P&L, cash buffer |

**Reconciliation (requirement §6)** is the `positions` projection cross-checked against venue truth
(IBKR portfolio pull, on-chain balances). Divergence → emit `ReconciliationMismatch` → surfaces in the
harness. A run-on-a-schedule reconciler (reuse the existing 30-min scheduler in `kryptonpay_backend`)
keeps the internal ledger honest against the venues.

---

## 6. The unit ledger & NAV

Standard open-ended-fund accounting — solves "20 people, one pool" without ever tracking who owns
which share:

- **NAV** = Σ(position qty × price) across IBKR + idle USDC, in USD.
- **NAV per unit** = NAV ÷ units outstanding.
- **Subscribe** ($100 in): `units_issued = deposit ÷ current nav_per_unit`. First LP sets
  `nav_per_unit = 1.00` (base). LPs buy in at *current* price, not par.
- **Redeem:** burn units, pay `units × nav_per_unit`.
- P&L accrues to NAV; every LP's units revalue pro-rata automatically. **No per-trade attribution.**

**Rules that prevent silent losses:**

1. **Strike the NAV at a defined moment** (daily close is fine at this scale). Subscriptions and
   redemptions execute at the **next** strike, never intraday — otherwise someone deposits right
   before a known-good fill and dilutes everyone.
2. **Never strike over in-flight trades.** A strike folds only `OrderFilled` (confirmed) positions and
   marks anything mid-flight as pending.
3. **Two-phase subscription.** `SubscriptionRequested → CashConfirmed → UnitsIssued`. Never mint units
   before cash is confirmed in the fund wallet.
4. **Fees:** zero for phase 1, but the strike path leaves a hook (NAV deduction or unit dilution) so
   adding a fee later is not a rewrite.

### Data model (Firestore)

```
lps            id, name, contact
subscriptions  lp_id, usd_amount, strike_ts, nav_per_unit, units_issued, status
redemptions    lp_id, units_burned, strike_ts, nav_per_unit, usd_out, status
holdings       lp_id -> units_outstanding            (materialized projection)
nav_snapshots  ts, total_nav_usd, units_outstanding, nav_per_unit, breakdown{ibkr, cash}
positions      venue, asset, qty, price, usd_value, as_of, source
events         seq, aggregate_id, type, ts, actor, payload   (append-only, source of truth)
```

**Pricing sources:** IBKR marks the equities; idle USDC = face value. (Phase 2 adds an on-chain oracle
for tokens — FMP/CoinGecko already available to start, Chainlink/TWAP later.)

---

## 7. Venue-agnostic execution — the connector interface

```python
class Connector(Protocol):
    def quote(self, order: Order) -> Quote: ...            # price, est. slippage, fees
    def validate(self, order: Order) -> ValidationResult: ...
    def execute(self, order: Order, idem_key: str) -> VenueRef: ...   # returns immediately
    def poll(self, ref: VenueRef) -> ExecStatus: ...       # status + fill, for async settle
    def positions(self) -> list[Position]: ...             # venue truth, for reconciliation
    def balances(self) -> list[Balance]: ...
```

**Phase 1 implementations**

- `IBKRConnector` — equities/ETFs. **Open decision (see §11):** LEAN owns execution natively *or* the
  connector calls the IBKR API and LEAN only signals.
- `CircleConnector` — USDC custody, deposits/redemptions, balances. (No swaps in phase 1.)

`execute()` is **not** request/response. IBKR fills settle asynchronously; the connector returns a
`VenueRef` immediately and a poller/webhook emits `OrderFilled` / `OrderFailed` later. This
asynchronicity is exactly why the event log (not synchronous CRUD) is the state model.

---

## 8. Risk engine — a gate before approval

Two tiers, both reading `risk_state`:

**Hard reject (human never sees it) → `OrderRejected`:**
- position limit (per asset), max allocation (per asset class / venue)
- daily loss limit (halt new risk once breached)
- minimum cash buffer
- transaction validation (sane amount, known venue + asset)
- **duplicate-execution guard** — idempotency key already seen or in-flight

**Escalate (requires approval, possibly extra confirmation):**
- approval thresholds — e.g. a trade > 25% of NAV needs a second confirm / cooling-off.
  (F&F: everything routes to Rushi, but the tier exists.)

The risk engine is stateful but derives every limit from projections, so it never duplicates the
source of truth.

---

## 9. Idempotency & the async boundary

The money-losing case: a timeout where you don't know if the order landed.

- Persist the `idempotency_key` **before** submit.
- Before **any** retry, *query the venue* — IBKR by client-order-id; (phase 2) chain by pending-tx /
  nonce — never blind-resubmit.
- The connector maps `(idempotency_key → venue_ref)` so a replay returns the existing ref instead of
  placing a second order.

---

## 10. Repo topology (no new spine repo needed for phase 1)

| Repo | Layer | Role |
|------|-------|------|
| `quantconnect` (LEAN) | signal source | strategy engine; emits *proposed* commands; owns IBKR exec (pending §11) |
| `strands_agents` | reasoning | turns operator intent into commands; composes read tools; explains decisions |
| `clark_mcp` | tool surface | **repurposed** from 2-tool proxy → the fund's tool contract (reads + gated writes) |
| `kryptonpay_backend` | spine (brain-body) | **extended** with event store, projections, connectors, risk, command handlers; holds custody |
| frontend | interface | **thinned** to render projections + capture intent; all NAV/P&L/history math moves back to the spine |
| `ClarkHarness` (this repo) | design + interface | architecture spec now; home for the operator REPL + LP view as they take shape |

### The frontend cut line

Frontend keeps exactly two jobs — **render projections** and **capture intent** (submit commands /
approve interrupts), ideally over a websocket/SSE feed off the event stream. Everything else moves
back to the spine:

| Move to backend | Becomes |
|-----------------|---------|
| NAV / P&L math | `nav_snapshots` projection |
| trade history assembled client-side | `audit` / `positions` projection API |
| "what's my share" | `holdings` projection |
| order construction / routing | command pipeline + connectors |

---

## 11. Open decisions

1. **IBKR execution ownership** — LEAN as native brokerage (truth for the TradFi sleeve lives in
   LEAN; reconciler pulls from there) **vs.** connector-owned execution via IBKR API (LEAN signals
   only). The diagram currently assumes LEAN-native.
2. Nothing else blocking — event store = Firestore append-only collection for phase 1 (agreed).

---

## 12. Build order

Dependency-ordered; read-only tools and the LP view parallelize once projections exist.

1. **Event store** — append-only `events` collection + a small append/read API in `kryptonpay_backend`.
2. **NAV service + projections** — `StrikeNav` handler → `nav_snapshots`; `positions`, `risk_state`,
   `holdings` folds. (Reuse the existing scheduler for periodic strike + reconciliation.)
3. **Connector interface + `IBKRConnector` + `CircleConnector`** — with the async poll → event path.
4. **Risk gate** — hard tier first, thresholds second.
5. **Command pipeline + approval** — wire `PlaceOrder` / `Subscribe` / `Redeem` through
   risk → `krypton_approve_interrupt` → connector → events.
6. **Clark tool surface** — read tools (`portfolio_status`, `nav`, `lp_book`, `risk`) then gated write
   tools, each write returning a pre-trade impact preview.
7. **Thin the frontend** — swap client-side math for projection reads; subscribe to the event feed.

---

*Phase 1 · pooled custody · IBKR + USDC · human approval on every financial action.*
