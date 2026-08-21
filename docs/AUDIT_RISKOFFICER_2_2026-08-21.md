# Riskofficer dispatch 2 — four-item batch (filed verbatim)

**2026-08-21, run-riskofficer-2, serving desk requests dc7b068c and
4a1207c1. Dispatched by the co-CTO chair. co-CTO verification note at the
end. The seat's report follows verbatim; its STATE is in
`.claude/state/riskofficer.md` and its run_record in the flight recorder.**

---

# TL;DR

1. **The DBA "Alpaca" trade never went to Alpaca.** The spine has one broker connector and it is the paper one; "alpaca" was a label the order carried, contradicted by its own submission record two events later. The CEO-approved experiment to finally measure real trading costs produced zero information and is marked done.
2. **The known drawdown-rebase defect is now live and one click from doing harm** — a second rebase would silently raise the risk reference back and undo today's repair, and would record a false "previous peak" while doing it.
3. **The approval guard has no force where the CEO actually clicks.** The Studio order queue fills in both the name and the confirmation code for him; the risk-control panels do this correctly and the order panel does not.
4. **Two live doors have no approval control at all**: changing risk limits, and resuming trading after a halt. Neither has ever been misused; both are open.
5. The auto-approval envelope is genuinely reachable — it will close $501.34 unattended on 8 September, and up to $916 (the whole book) if stops co-fire in one tick. That is correct behaviour, but the code comment claiming it is capped at one position is wrong.

## Scope and method

Whole log audited: 696 events, seq 1–696. 23 OrderApproved, 3 ApprovalRefused, 8 DeskRequestApproved, 1 DrawdownReferenceRebased, 8 TradingResumed. Live reads: `/fund/risk/monitor`, `/fund/liveness`, `/fund/venue/account`. Three demonstrations were run offline against a read-only replay of the live log; nothing was written to the store.

## F1 — CRITICAL: the DBA leg is labelled `alpaca` and filled on the PAPER venue. R15 is falsely marked done.

`venue` is **not a route in this system**. There is exactly one connector, chosen once at import from env (`app/api/v1/fund.py:151-163`), and `pipeline.submit` calls `self._connector.execute(order, …)` unconditionally (`app/fund/pipeline.py:223`). `PaperConnector.validate` never inspects `order.venue` (`app/fund/connectors/paper.py:99-105`). The venue string on a proposal is a self-declared label; the fill copies it verbatim (`pipeline.py:311-318`).

Three independent proofs that DBA filled on paper:

1. `GET /api/v1/fund/venue/account` → `{"venue":"paper","configured":false,"mode":"paper_mock"}`. No Alpaca is configured on the running spine.
2. **seq 593 `OrderSubmitted` for the DBA order says `"venue": "paper"`** with a UUID `venue_ref` — that field is written from what the *connector returned* (`pipeline.py:229`, `ref.venue`), and `PaperConnector.execute` returns `VenueRef(venue=self.name)` = `"paper"`. Only seq 594 `OrderFilled` says `"alpaca"`, and that is the label.
3. Fill price = arrival price = proposal quote to the last binary digit: `28.3799991607666` at seq 588 / 593 / 594. That is the paper venue's signature — it fills at its own quote (`paper.py:116`), so slippage is identically zero. Same pattern on SPY (`762.5999755859375`).

**Why this costs money.** R15 was CEO-accepted (seq 501) with one stated learning goal: *"the fund's first informative cost observations — the paper venue yields zero at any n."* It was marked **done** at seq 612, note: *"DBA routed to alpaca and filled (seq 594)"* — citing the label, not the submission record. The fund therefore believes it has begun measuring execution cost and has not. The live cost model is one global 5 bps/side constant and it is the divisor on every gate verdict. If more "alpaca"-labelled paper fills accumulate, a future TCA pass will measure realised slippage ≈ 0 and conclude 5 bps is conservative — a false belief that mis-sizes every subsequent strategy. Direct loss today: **$0**. Cost: **$150.82 of capital committed to a measurement that returned nothing**, plus a false completion on the record.

This also settles the COO's venue drift (item 4): adding `venue == "paper"` to `autopolicy.py` would check a **self-declared string** — the exact class of error the EXIT_MARKER lesson already taught. Do not add that check.

## F2 — CRITICAL, now live: the second rebase raises the reference

**Line: `app/api/v1/fund.py:3619`** (the request's `:3511` is stale; Donna's correction is right).

`current_peak = dd.get("unrebased_peak_nav", dd.get("peak_nav"))` — `unrebased_peak_nav` is the trailing-365d max and never falls; `effective_peak` returns the *rebased* value. The direction guard `new >= cur` is compared against a number that stopped being the reference the moment seq 694 landed. The unit is correct; **the caller feeds it the wrong baseline** — and `tests/test_drawdown_rebase.py:213-222` exercises two rebases only by hand-passing `current_peak=1990.0`. No test touches the endpoint.

Demonstration (reproduces the live monitor exactly):

```
after rebase #1 (seq 694)   peak=$1,908.09 dd=1.2211%  halt_line=$1,717.28 headroom=$167.51
endpoint would pass current_peak = $2,036.35 — $128.26 too high
REBASE #2 to $2,000.00: nav-guard=pass  direction-guard=ACCEPTED
   -> reference $1,908.09 -> $2,000.00 (RAISED)  headroom $167.51 -> $84.79
REBASE #2 to $2,036.34: ACCEPTED -> reference $2,036.34, headroom back to $52.08
```

Two harms: **direction** (any second rebase in ($1,908.09, $2,036.35) raises the reference; $2,036.34 fully reverses R1 and with it P(halt) 9.6% → 58.4%), and **the record lies in every case, including legitimate lowerings** — `previous_peak_usd` is written from the same wrong `current_peak`. That defeats Clean-Field guard-rails 2 and 3 inside the one mechanism those rails were written for.

**The fix is TWO lines, and a one-line fix breaks the channel.** `fund.py:3619` must read `dd.get("peak_nav", …)` — *and* `riskmonitor.py:850-851` must publish `rebase_token` off `peak["peak_nav"]`. The endpoint hashes `current_peak` into the token it demands as the confirm echo; change one side only and every future rebase is refused. Tier 3 — recommend, do not execute.

## F3 — HIGH: on the UI path the approval guard cannot refuse

`_guard_approval` binds allowlist membership, a confirm echo equal to `target_id[:8]`, and a non-empty `instruction`. On the order path the client supplies **both** binding conditions automatically: `{ approver, confirm: orderId.slice(0, 8) }` (`fund_api.ts:1821`), with `approver` hardcoded at the call site. For any Studio order click the guard is a no-op — it cannot produce a refusal, ever. It has force only on the scripted/agent path, which is where all three recorded refusals came from.

**The risk-control panels already do this right** and are the model: `approver` has no default and `confirm` is the *server-issued* `rebase_token` / `halt_ack_token` — a digest of live state, so a click on a stale panel is refused. That is what made the R1 rebase's `ad699edb` meaningful.

Recommendation: keep the hardcoded name — identity is not what an echo protects — and make the **order** echo server-issued, derived from the order's id *plus its proposal timestamp and quote price*. That closes a second hole for free: today the CEO can approve a queue row rendered against a mark that has since moved.

## F4 — HIGH, latent: two execution-critical endpoints carry NO approval guard

`POST /fund/risk/limits` (`fund.py:3588-3591`) — no allowlist, no echo, no mandatory written reason, against a constitution clause reading *"A threshold moves only by a versioned change with a written reason… Quiet loosening is the one forbidden move."* Same for `POST /fund/risk/resume` (`fund.py:3687-3690`).

The inconsistency is structural: the **ceremonial** half of halt-reopening is on the approval channel (`halt_acknowledge`, `loss_reference_rebase`), while the **actual reopening** is not. And raising `max_drawdown_pct` from 0.10 to 0.50 through this endpoint disarms the drawdown halt and the envelope's most important precondition, with no record of why.

**Honest scope**: never abused. Exactly one `RiskLimitsSet` in fund history — seq 1, actor `vishesh`, the genesis register. But 8 of 8 `TradingResumed` events carry an empty payload and a free-text actor.

## F5 — MEDIUM: `MAX_AUTO_NOTIONAL_PCT` is a per-order cap, and the comment claims otherwise

`autopolicy.py:110-113` states the 20% ceiling "bounds the blast radius to one position". It does not — the check is per order and `run()` iterates the whole pending list in one tick with no aggregate budget.

Measured (live log, live marks, live heartbeats, v3): TLT $248.66 (13.19%), DBC $252.68 (13.41%), DBA $150.82 (8.00%), SPY $263.95 (14.00%) — **all APPROVE 12/12. $916.11 = 48.61% of NAV auto-approvable in a single tick.**

I am **not** recommending a tightening. These are pre-committed exits; auto-closing the book when stops co-fire is what pre-commitment *means*. Recommend instead: correct the comment, and if a per-tick ceiling is wanted, implement it as a *deferral*, never as a block.

**Item 4's direct answer: the envelope is reachable and will fire.** On 2026-09-08 the TLT and DBC time exits auto-close **$501.34** with no click — the COO's figure independently reproduced. `auto_policy` is ticking, so the control is live, not dormant.

## F6 — MEDIUM: `marksanity.py` is right about the check and wrong about the incident

The module states the phantom "was proposed against a quote of $100.00 … **and a human approved it**". The log says otherwise: **seq 256 `OrderApproved`, approver `auto-policy-v1`** — a machine, in 261 ms. No human ever approved order `2ec1ec3f`. The false premise originated in PM R14, passed through the D5 brief, and is now cemented in the shipped module's docstring — three hops, the EDGAR pattern exactly.

**Coverage is nevertheless complete**: the auto path has carried `mark_corroborated` since v2 with the *same* constant. Right control, wrong story.

**Item 3's direct answer.** Would it have caught the GLD fill? Its logic refuses those exact facts (`refuse=True basis=corroborated move_pct=75.8361`). But **as wired it would not have run**, because the order never reached the endpoint it guards.

**What the `False` flag lets through**: mostly correctly stated, with two corrections — **the code never reads `side`**, so a SELL of a never-held symbol at $0.01 returns `refuse=False`; and "the LAST strike only" is actually *the last strike that carried positions*. Flipping the flag to `True` would freeze all new deployment — a leg-3 defect. **Keep it `False`.**

## F7 — Item 2: the `neelesh-via-co-cto` channel, audited as a real event (seq 694)

**The three guard conditions bound, and I verified each**: allowlist membership (added 06:49Z, before the 13:07:57Z use); echo `ad699edb`, the live `drawdown.rebase_token` — the **strong** echo class, a digest of live state, read from the monitor rather than typed; instruction non-empty.

**Does the recorded instruction authorise what was done? Partly — and the load-bearing part is unattested.**

- The text labelled **verbatim** is a chair-authored desk line with the CEO's two-word assent appended. Calling a paraphrase "verbatim" in the immutable record is a precision defect in the one field the guard exists to preserve.
- **The option selection has no independent record.** Seq 502 records the CEO accepting the *item* with `note: ""`, not choosing an *option*. The choice among repair / dated exception / run-reduced exists solely inside the chair's own approver string and the chair's own note 26 seconds later. Self-corroboration, not corroboration. This is not chair misconduct — the guard offers no field that could do better — it is the channel's honest limit and should be written down as one.

**Attacking the channel as design.** Fails closed: unknown approver, missing/wrong echo, empty instruction, open integrity halt, a target below current NAV. Does **not** fail closed: instruction content is never validated (one character passes); nothing binds an instruction to its target and **reuse is established practice** (one instruction across four orders at seq 375/378/381/384); the endpoints are unauthenticated; and F2 sits inside this channel.

**Verdict on seq 694 as an act: correct, conservative, and I would not reverse it.** $2,036.35 − $128.26 = $1,908.09 exact, and $128.26 = 0.424471 × ($402.18 − $100.00) to the cent. Two points of precision: the reason mixes two comparators (the $415.04 method yields $133.73, the struck-mark method $133.22 — both would justify a *lower* peak, so **the executed rebase was conservative by ~$5**); and the reason says it *"repairs the trailing-365-day peak corrupted by the phantom"* when **the peak was not corrupted** — it was struck at seq 99 on genuine marks six days *before* the phantom. What the rebase actually did is lower a *genuine* high by the amount a defect destroyed. Defensible with a written reason on the approval channel; just not what it says.

## CLEAN — what I checked and found sound

- **Every approver on all 23 OrderApproved events was on the allowlist as it stood at that moment.** Guard v1.1 landed **mid-day 2026-08-20** (~14:08Z) — so the `rushi` approvals that morning are legitimate. **Brief correction:** the retirement boundary is mid-day 2026-08-20, not "before 2026-08-20". Nineteen of 23 approvals predate the guard entirely.
- **The three ApprovalRefused events, classified**: seq 373+374 54 ms apart followed by a clean approval is a deliberate **smoke test** of a guard shipped minutes earlier; seq 395 is a **stale-identity script** that failed closed. **No probe pattern. No agent has ever successfully approved anything.**
- The one auto-approval in fund history remains as audited. No version drift.
- My last dispatch's F1 is **closed** (`_SEED_PRICES` no longer serves equities).
- **Mark sanity ran and passed on today's two approvals.**
- **Heartbeats are honest**; `nav_strike` correctly reports "unobserved", which the policy treats as a fail.

**Two absences worth a line**: no `reconciliation` job appears in the liveness set at all, and the last `ReconciliationMismatch` is seq 141 (2026-08-15) — six days and one new position ago. And `nav_strike` has never been observed in this process.

---

## co-CTO verification note (2026-08-21, at resolve)

**F1 verified independently, all three proofs, before any action**:
`GET /fund/venue/account` returns `{"venue":"paper","configured":false,
"mode":"paper_mock"}`; the DBA order's own lifecycle reads OrderProposed
`venue: alpaca` (seq 588) → **OrderSubmitted `venue: paper` with a real
`venue_ref` UUID (seq 593)** → OrderFilled `venue: alpaca` (seq 594),
price `28.3799991607666` identical across submission and fill; and
line-exact, `_connector` is a module-level singleton chosen once at import
(`fund.py:151-163`) while `pipeline.submit` calls
`self._connector.execute(...)` unconditionally (`pipeline.py:223`) and
writes `venue: ref.venue` from what the connector returned
(`pipeline.py:229`). **Venue is a label on the proposal and the fill; the
submission record carries the truth.**

**Action taken at resolve**: PM R15 **REOPENED** — the prior `done` mark
cited the fill label against that order's own submission record, and a
false completion on a CEO-authorised measurement is the one thing the
record must not carry. It stays open until venue either routes for real
or is deleted from proposals; no TCA or cost-model work may consume
`alpaca`-labelled fills meanwhile.

**Three seats converged on this independently in one day**, which is why
it surfaced: Donna reported the venue disagreement across the order's own
three lifecycle events and the `avg_price == arrival_price` signature
(run-secretary-2 §VI item 2); the COO found the constitution's
"paper venue" clause with no venue check in code, for the second
consecutive triage; the riskofficer proved the mechanism and named the
consequence.

**On F7 — the audit of my own approval channel, and I am recording its
criticisms rather than softening them.** The seat is right that I labelled
as "verbatim" a string that was my own desk line with the CEO's assent
appended, in the one field the guard exists to preserve. It is right that
the option selection has no record I did not author. And it is right that
the reason text mixes two comparators and calls a peak "corrupted" that
was struck six days before the phantom on genuine marks — what the rebase
actually did is lower a genuine high by a defect's realised destruction,
which is defensible and is not what I wrote. The correction the seat
proposes costs nothing and I am adopting it: **where the CEO selects among
options, the selection must be captured in a record the chair does not
author** — a `note` on the `DeskRecommendationDecided` event would have
done it for R1.
