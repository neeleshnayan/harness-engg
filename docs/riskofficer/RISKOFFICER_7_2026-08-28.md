# Riskofficer dispatch #7 — the autopolicy's first live fire, audited

**Filed by the CTO chair (Fable) 2026-08-28. Seat report verbatim in
substance below; verified by the chair before filing: the unguarded
`/fund/risk/limits` body (fund.py:7394-7399, exactly as quoted), the
120-minute proposal expiry (pipeline.py:48), and the live TCA payload
carrying the contaminated figures (0.89 bps headline, XLF −36.10,
submit_to_fill 49,263 s, `reliable` present).**

**CTO note at filing**: The three auto-approvals are CLEAN on independent
re-verification — every recorded check re-derived from the event log and the
live venue, not trusted from the payload. The audit's two largest findings
are exactly where a good auditor looks after a clean fire: one layer past
the safety checks, in the money. **One chair correction to the operational
finding**: the "BUY expires unapproved at 02:05 ET" concern assumes a
US-resident human — the CEO is IST, where the HYG signal hour (just after
00:00 ET) is ~09:35 AM local. The click path is reachable in his ordinary
morning; the risk is real only on travel days, and the disclosure stands.
Chair actions at resolve: TCA session-boundary fix and the F8 guard
ordering queued for the builder's next batch; the three control-layer
guards (risk/limits — FOURTH ask; /fund/exits + override; E1 market-session
disclosure) ride to the CEO as versioned decisions with the riskofficer's
measurements attached; the READINESS_EXIT_PREDATE_MARGIN answer (no time
floor — authorship guard instead, justified by the 81.8/91.9/101.3 s
measured margins) is carried to Stan's matrix.

---

## TL;DR (seat's own, verbatim)

**The machine executed on its own for the first time and it did so
correctly.** Three pre-committed exits closed themselves overnight, the fund
is now flat in those three names, and the book and the broker agree to the
penny. Every safety check on those approvals re-verified true against the
record.

**One real problem, and it points at money rather than safety.** The exits
fired at 8pm and did not actually trade until the next morning's open,
thirteen hours later. Our trading-cost tracker treated that overnight price
drift as if it were the cost of trading, and it has now cut our measured
trading cost from about 2.3 to 0.9 basis points — a number that argues our
backtests are too pessimistic. That conclusion is not earned, and it feeds
every strategy decision we make. It needs fixing before anyone leans on it.

**One control is still open after four requests**: the page that changes our
risk limits can be called by anyone who can reach the server, with no
approval and no recorded reason. Raising one number there would switch off
the halt everything else depends on.

## The three approvals — CLEAN, all fifteen checks re-verified

Population: whole log, seq 1–1950. `auto-policy-v4` ×3 (seq 1936/1938/1940);
code version == event version, no drift. Highlights of the independent
re-verification: exit-rule provenance matched to the exact triggering events
(seq 1931/1933/1935, non-forgeable token present); rules predate positions
by **81.8 / 91.9 / 101.3 seconds** (rules seq 1548/1550/1552 vs positions
1562/1567/1568); marks corroborated against strike seq 1807 at
0.045/0.017/0.216% moves; post-state venue reconcile: **0 of 14 symbols out
of sync**. Real Alpaca-paper fills (avg_price ≠ arrival_price). Round trip:
**+$2.00 on $500.72 entered (+0.40%) over two days, no fees.** Approved
20:00 ET Thursday (market closed); fills observed 09:41 ET Friday —
`submit_to_fill_s` 49,263. Honesty note preserved: two of three liveness
checks are structurally unverifiable after the fact (in-memory heartbeats,
by design) — self-attested, said rather than passed.

## Findings (severity ordered)

- **F1 HIGH, LIVE, LOOSENING — the overnight fills contaminated the realised
  trading-cost number.** `/fund/tca` consumed the three 13.7-hour fills as
  execution cost: informative sample reads **0.89 bps (n=25, reliable:
  true)** with them, **2.35 bps (n=22)** without; XLF alone contributes
  −36.10 bps of pure overnight gap. The verdict "backtests are conservative"
  against the 5.0 bps every backtest charges is NOT EARNED. `tca.py` has no
  session-boundary class. Fix: classify/exclude session-spanning fills and
  re-publish. Measurement fix, not a threshold move. → builder queue.
- **F2 HIGH, LIVE — the envelope has no concept of the market clock** (zero
  references in 872 lines + 59 tests) while the fund wrote that exact rule
  twice elsewhere (NAV strike main.py:483-499; signal runner
  signals.py:216-224). The seat explicitly does NOT recommend blocking
  out-of-hours exits (a fired exit fires once and expires in 120 min —
  deferral destroys it). **E1**: record `market_session {phase, is_open,
  source}` on every evaluation payload — disclosure, blocks nothing. → CEO.
- **F3 HIGH, FOURTH ASK — `POST /fund/risk/limits` unguarded**
  (fund.py:7394-7399): no allowlist, no echo, no reason; unknown keys
  silently swallowed; raising `max_drawdown_pct` disarms the halt
  `not_halted` rests on. Meanwhile resume/halt-acknowledge/both rebases are
  NOW guarded (dispatch-2 F4 half and Grace's blocker 1 CLOSED, verified).
  → CEO, due 09-01.
- **F4 MED-HIGH — `/fund/exits` and `/fund/exits/override` unguarded**
  (free-text actor; the second disarms a committed stop). Bounded: a rule
  against an existing position fails `rule_predates_position`. **And the
  READINESS_EXIT_PREDATE_MARGIN question is ANSWERED: not a time value** —
  any principled margin (5 or 15 min) would have refused all three of the
  fund's first successful auto-approvals (measured margins 81.8/91.9/101.3
  s). The threat is AUTHORSHIP; the fix is the existing approval guard on
  the exit endpoints. → CEO, due 09-04; answer carried to Stan.
- **F5 MED — TCA cannot tell alpaca-paper from alpaca-live** (`informative`
  keys on connector name; both modes share `("alpaca",)`). 100% of the
  "reliable" cost sample is paper. The v5 draft is CLEAN on this (reads
  venue_kind + real_money, citing eng3).
- **F6 MED — `mark_corroborated` bounds the move, never the age**: the
  corroborating strike was 4h59m old; `nav_strike` is not a required
  heartbeat; liveness reports 11 NAV holes, worst 36.7h. **E3**: the check's
  detail should name the strike's timestamp and age.
- **F7 MED — first live demonstration that the notional cap has no
  aggregate**: 25.0% of NAV auto-approved in 3.59 s against a 20% per-order
  ceiling. Still no hard block recommended (pre-committed exits; blocking
  strands the position) — a ceiling, if wanted, must DEFER.
- **F8 LOW — mark-sanity runs before the terminal-state check**: a re-click
  on an already-filled order writes an `ApprovalRefused` with a false reason
  (seq 1472 vs fill 1470). → builder queue.
- **F9 LOW, LATENT (0 occurrences)** — chair-identity allowlist re-spelled
  inline twice (fund.py:5601, :5614); `deskcard._VIA_RE` admits identities
  the guard refuses. jan1's BIND confirmed live.

## Clean, said loudly

119/119 sweep rows citation-backed, six spot-checks verified (incl. the
test count: exactly 59). The 14 `supersession_readable: null` rows are the
documented not-applicable case — CLOSED, not a fail-open. All 18
`AutopolicyDeclined` correct. The 19 `ApprovalRefused` in 17 minutes were
**one control firing correctly 19 times at a human whose remedy needed a
different button** — an operability defect, not an attack; fix is a
strike-then-approve affordance. Fee-term exposure measured ZERO
(`charges_anything: false`) and no v4 check can be loosened by a fee accrual
(accrual tightens the only NAV-relative check). **No `OrderApproved` has
ever carried `neelesh-via-cto` — the chair has never approved an order.**

## N2 dollar-floor — argument MADE, one clause rejected

v5 gathers `nav` once and five caps divide by it — one field, one failure.
Why v4 never needed it (the load-bearing half): v4's four position checks
bind every order to a broker-confirmed holding, so a corrupt NAV makes the
cap vacuous but cannot manufacture size; v5's engine ENTRIES have no such
backstop. Sharpenings: MIN(pct, dollars) recorded as TWO checks; the floor
must be a versioned constant, never derived from NAV. REJECTED: "not a
better ceiling" — keep both (ceiling catches absurd, floor catches
wrong-but-plausible, and the second is the likely fault). Values are the
CEO's; the operating envelope they must clear: largest auto-approved order
$169.16, largest day $502.16, engine probe $50/signal.

## HYG v2 bridge

Exits confirmed live, set 2026-08-27T18:48:44/45Z (the seat corrected the
brief's 08-28 date — accepted), predating any entry by construction. **Every
BUY will be DECLINED on `side_is_sell` and left pending — a working control
with three worked examples.** Proposals expire at 120 minutes; with the CEO
in IST the signal hour lands at ~09:35 AM his time (chair's correction), so
the click path is reachable on ordinary days; disclosure stands for travel
days.

*Seat STATE, BINDS (quant, pm, cfo, adversary, builder, chair) and EVOLVE
(hunt-list 4b: the gap between certification and execution) carried at
resolve; run record run-riskofficer-7.*
