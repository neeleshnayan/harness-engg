# Krypton Fund — Harness Architecture

> **Status:** living design spec. For current build state, the decisions log, gaps and priorities see
> [`STATUS.md`](./STATUS.md).
> **One-line thesis:** audit, reconciliation, risk, idempotency, approval, and orchestration are not
> six subsystems — they are gates and projections on a single event-sourced command lifecycle.

---

## 1. Goals & non-goals

**Goal.** A "Claude Code for the fund": an agentic interface where the operator (Rushi) creates and
deploys strategies, sources and makes decisions with the harness as a complement, and LPs get a
read-only view to understand their portfolio. Rushi keeps ownership of the fund; the AI orchestrates,
it does not custody.

**v0 scope.** 20 friends & family; one pooled, multi-strategy managed-fund experience.

| In | Out (later) |
|----|-------------|
| IBKR execution (equities/ETFs), **connector-owned** | Uniswap / any on-chain trading |
| Deposits wired to the manager, recorded **off-platform** | Wallets / self-custody / add-cash |
| Pooled custody + off-platform unit ledger | KryptonPay payments rail (regulatory surface) |
| Human approval on every financial action | Management/performance fees (leave the hook) |
| Multi-strategy: create → backtest → deploy → allocate (§13) | Multi-PM |

**Non-goals.** No Kafka / dedicated event-store DB (Firestore append-only collection is enough at this
scale). No autonomous execution. No client-side financial math. **No payments / money-transmission
surface** — money moves off-platform, person to person.

**Testing posture.** Test with our own money at F&F scale first. Legal structure is a parallel, later
workstream and deliberately does **not** block the build — the technical design (pooled unit ledger)
is identical regardless of the eventual legal wrapper.

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

- **NAV** = Σ(position qty × price) across IBKR positions + idle cash, in USD.
- **NAV per unit** = NAV ÷ units outstanding.
- **Subscribe** ($100 in): `units_issued = deposit ÷ current nav_per_unit`. First LP sets
  `nav_per_unit = 1.00` (base). LPs buy in at *current* price, not par.
- **Redeem:** burn units, pay `units × nav_per_unit`.
- P&L accrues to NAV; every LP's units revalue pro-rata automatically. **No per-LP attribution** is
  needed. (Per-*strategy* attribution is a separate projection — §13 — and does not touch unit
  accounting.)

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

**Pricing sources:** IBKR marks the equities; idle cash = face value. (An on-chain oracle enters only
if/when on-chain trading is added.)

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

**Implementations**

- `PaperConnector` — in-repo simulation with real idempotency. **Built** — the current venue.
- `IBKRConnector` — equities/ETFs. **Decision resolved (§11):** connector-owned execution, LEAN only
  *signals*. *(Not yet built — needs an IBKR paper account.)*

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

## 10. Repo topology

| Repo | Layer | Role |
|------|-------|------|
| `ClarkHarness` (this repo) | **the fund** | Standalone service: the spine (event store, connectors, projections, risk, pipeline, unit ledger), the LP view, and the operator cockpit. Home for everything fund. |
| `quantconnect` (LEAN) → v2 | signal source | Rebuilt as a thin adapter: deployed strategies emit *proposed* orders via `POST /fund/orders/propose` (tagged with `strategy_id`). No tunnel, no Circle, no custody. |
| `krypton_clark` (strands) | reasoning | Existing orchestrator (skills + memory + interrupt approval + LEAN/backtest/data engine). Add fund skills that call the spine; its backtest engine powers the Strategy Studio (§13). |
| `clark_mcp` | tool surface | Thin proxy to `krypton_clark`; fund skills surface via `krypton_query`. |
| `kryptonpay_backend` | — | **Out of scope for the fund.** The payments product; the spine was moved *out* of it into ClarkHarness to keep the fund clear of its regulatory surface. |

### The frontend cut line

The **LP view** and the **operator cockpit** (in `ClarkHarness/web`) are the only "frontend", and they
keep exactly two jobs — **render projections** and **capture intent** (submit commands / approve
interrupts). No financial math lives client-side:

| Client must never compute | Reads instead |
|-----------------|---------|
| NAV / P&L | `/fund/nav`, `nav_snapshots` |
| trade history | `/fund/events` (audit) / `positions` |
| "what's my share" | `/fund/lp/{id}` (holdings) |
| order construction / routing | the command pipeline + connectors |

---

## 11. Decisions (resolved)

1. **IBKR execution** — connector-owned; LEAN only *signals*. Human approval has no clean seam inside
   LEAN's autonomous order loop, so LEAN cannot own execution.
2. **Event store** — Firestore append-only collection.
3. **Home** — ClarkHarness, standalone, separate from KryptonPay.
4. **Custody / deposits** — pooled; deposits wired to the manager and recorded off-platform; no
   payments rail in v0.
5. **Framework** — Strands stays for the *episodic* brain; the 24×7 layer is deterministic workers,
   not a running agent. The spine has no agent-framework dependency.
6. **Multi-strategy** — part of the platform before launch: one pooled account, strategies as tags
   (`strategy_id`), per-strategy attribution as a projection (§13).

---

## 12. Build order & status

Done — verified with in-repo smoke tests against an in-memory Firestore fake:

1. ✅ Event store (`fund_events`, global `seq`).
2. ✅ Connector interface + `PaperConnector`.
3. ✅ Projections — positions, NAV (`strike`/`history`), holdings.
4. ✅ Risk gate (hard tier).
5. ✅ Command pipeline — propose → risk → approve → idempotent execute.
6. ✅ Unit ledger — subscribe/redeem, fairness-verified.
7. ✅ LP view (`GET /lp`).

Next — see `STATUS.md` for the prioritized backlog and gap analysis:

8. Strategy layer — `strategy_id` tagging + per-strategy attribution + registry (create/backtest/deploy/allocate).
9. Operator cockpit (`GET /ops`), strategy-aware.
10. `IBKRConnector` (paper → live) + async fill poller + reconciliation.
11. Cross-cutting hardening — auth, scheduled NAV strike, money precision (see STATUS gaps).
12. Wire the brain (`krypton_clark`) to the spine.

---

## 13. Multi-strategy platform

The fund is one pooled IBKR account; **strategies are tags, not separate accounts.**

- **Strategy** — `id`, name, definition (LEAN algo / params), lifecycle (`draft → backtested →
  deployed → paused`), backtest results, target allocation %.
- **Tagging** — every order/fill carries `strategy_id` (`None` = discretionary). Allocation is a
  *target weight*; actual exposure = Σ of that strategy's tagged positions.
- **Attribution** — a projection folding tagged fills → per-strategy exposure and P&L. **Forensics** =
  filter the event log by `strategy_id` + time and replay; it's free once the log exists.
- **Studio** — create → backtest (via `krypton_clark`'s LEAN/backtest engine) → promote to deployed →
  allocate. A deployed strategy's signals `POST` proposed (tagged) orders into the approval queue.

---

*v0 · pooled custody · off-platform deposits · IBKR, connector-owned · multi-strategy · human approval
on every financial action.*
