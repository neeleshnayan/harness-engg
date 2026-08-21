# Adversary blind — builder-d8 code diff — KILL (filed verbatim)

**2026-08-21, run-adversary-d8. BLIND review of branch `builder-d8` vs base
`28a6c28` (ClarkHarness), routed here because the merge gate classified the
diff SENSITIVE: `app/fund/riskmonitor.py`, six changed lines in the
approval-guard region. The reviewer received the artifact and the base only —
no author, no rationale, no dispatch brief. co-CTO verification note at the
end. THE DIFF WAS NOT MERGED.**

---

# TL;DR

The diff's six flagged approval-guard lines are clean — the new `/fund/autopolicy` endpoint is genuinely read-only, pure, and complete. But the diff widens a *different* write path the classifier's regex never looked at: on this repo's actual `.env`, an endpoint that permanently appends fills to the fund's real ledger goes from always-refused to reachable. Separately, the new drift alarm is silent in five of eight failure modes and is actively **erased** by the post-fill risk monitor, which writes "Cleared breach" into the append-only log without ever looking at the broker. The heartbeat's advertised three states collapse to one at the surface — a skipped reconciler is indistinguishable from a clean run. **KILL**: three demonstrated defects, all fixable; the routing and fence work is sound and should survive the repair.

## Blindness note

I was given the branch and the base only. I encountered
`kp/docs/briefs/BUILDER_D8_2026-08-21.md` inside the exported tree (a
materialised symlink; not part of the diff) and did **not** open it. No author
reasoning was consulted. The live spine on 127.0.0.1:8090 was **DOWN** for the
whole dispatch (`curl` → `000`), so every claim is from code and from `.env`,
never from live state.

## VERDICT: **KILL** — three independent grounds, each demonstrated

### GROUND 1 — the new alarm is deleted by a monitor that cannot see the broker

`_drift_alarms` opens with `if self._reconciler is None: return []`. Three
lines above, the constructor comment states the opposite invariant verbatim
(`riskmonitor.py:788-791`): *"OPTIONAL, and its absence is reported rather
than read as agreement... a silent skip would let 'we never looked' render as
'they agree'."*

There is exactly one production caller that constructs a `RiskMonitor`
without a reconciler, and it is the safety-critical one —
**`app/fund/pipeline.py:332`** (unchanged by this diff), the post-fill
re-evaluation. `run()` computes `cleared_keys = active_keys -
set(current_map.keys())` and appends `RISK_ALARM_CLEARED` for each. So the
tick that fires **on every fill** — the most likely moment for a new
divergence — silently erases every `broker_drift:*` alarm the wired monitor
raised.

```
WIRED  raised : ['broker_drift:AAPL', 'cash_floor', 'daily_loss_unevaluable']
BLIND  cleared: ['broker_drift:AAPL']
 EVENT RiskAlarmRaised  monitor      broker_drift:AAPL  AAPL: the broker and the book disagree by -4.0 share(s)
 EVENT RiskAlarmCleared fill_re-eval broker_drift:AAPL  Cleared breach for broker_drift:AAPL
```

That last line is a fabricated fact written by an actor that never read the
broker — *absence is never zero*, broken on the append-only log itself.

**It reaches the halt machinery.** `evaluate_autoresume` condition 3
(`riskmonitor.py:299-307`) reads *this tick's* alarm set. A `critical`
broker-drift alarm — raised when an exit rule is armed on the divergent
symbol, the case whose own message reads "a fired exit would try to sell what
the venue may not hold" — is invisible on the post-fill tick:

```
WIRED: no_other_critical_alarm ok=False  detail=other critical alarms are active: broker_drift:AAPL
BLIND: no_other_critical_alarm ok=True   detail=no other critical alarm is active
```

A loss halt can auto-resume with a real, critical, unrecovered divergence
standing. The docstring's claim that "every unknown fails closed" is true of
the function; the absence is manufactured upstream.

**Failure-mode matrix — five of eight silent:**

```
A no reconciler at all (pipeline.py:332)      -> SILENT
B reconciler raises                           -> [('broker_drift_unreadable', 'warn')]
C drift() returns None                        -> SILENT
D configured=False (paper venue)              -> SILENT
E configured=True, per_symbol EMPTY           -> SILENT
F configured=True, broker_equity missing      -> SILENT
G real structural drift                       -> [('broker_drift:AAPL', 'warn')]
H broker_qty unparseable                      -> [('broker_drift:nav', 'info')]
```

Two worth naming beyond A. **E**: `reconcile_epoch.evaluate_drift` computes
`measurable: False` and the note *"whether the broker agrees is UNKNOWN, not
confirmed"* — and `_drift_alarms` discards both, returning only
`out["alarms"]`. The honest answer is computed and thrown away, and the
branch's own test asserts the discarded field, so the suite is green over the
silence. **H**: an unparseable broker quantity is `continue`d out of the
structural leg, leaving the NAV leg free to fire — so a real *quantity*
divergence renders as `severity: "info"` with the message *"this is a
valuation or timing difference **rather than a missing order**"*.

**Overturned by**: `pipeline.py:332` passing a reconciler, or `_drift_alarms`
raising `broker_drift_unmeasurable` on the None / `{}` / empty-`per_symbol`
paths so no tick can clear what it could not evaluate.

### GROUND 2 — a ledger-write endpoint is widened, on this repo's actual `.env`

The six flagged lines are the new read-only endpoint and are clean. The
widening is in a function whose name matches none of the classifier's
patterns: `_real_broker()` → `_broker_is_real()` at both venue-backfill
guards, changing an env-var test into `getattr(_connector, "name", "") ==
"alpaca"`.

`apply_venue_backfill` calls `BrokerBackfill.apply` (`backfill.py:222-235`),
which appends **`EventType.ORDER_FILLED`** — the event type NAV, positions and
attribution all fold from. This is the phantom-fill surface, and it sits
outside the approval channel entirely: no approver identity, no confirm echo,
just `confirm: true` and a free-text `actor`.

```
BACKFILL GUARD (/fund/venue/backfill/plan and /apply):
  FUND_OFFLINE=0 FUND_REAL_BROKER=0 ALPACA_API_KEY=1: base_allows=False branch_allows=True  <-- WIDENED
  ... (7 other cells identical)
this repo's .env -> base_allows = False   branch_allows = True
```

The one widened cell **is** the live configuration. The diff's own note claims
*"the apply path stays guarded by the production refusal and an explicit
confirm, neither of which moved."* Neither moved — but that refusal reads
`env == "production"` sourced from `FUND_ENV`, which is **staging** in `.env`
while `FIREBASE_SERVICE_ACCOUNT_JSON` points at `hedgefund-ae96c`, **the real
book**. The sentence relies on a label that does not describe the ledger.

**Overturned by**: proof that `/fund/venue/backfill/apply` is unreachable on
every configuration the fund actually runs (an auth dependency — I found none
— or a `FUND_ENV=production` invariant on every launch path).

### GROUND 3 — the heartbeat's three states are one at the surface

The dead-reconciler half is **real and good**: `main.py` beats `reconcile`
separately and deliberately does not beat on exception, so a throwing
reconciler ages past budget and goes `ok: False`. Verified.

The three-state note does not survive. `heartbeat.status()` (unchanged, so
absent from the diff) builds `{..., **hit, "note": ...}` — the later literal
key overwrites the beat's own note. `reconcile_note()`'s output never reaches
`report()`, which is what `GET /fund/liveness` returns. **Zero** consumers of
`heartbeat.last()` exist in `app/` or `web/`.

```
reconcile_note() -> ran (10 symbol(s) checked, 0 structural)   status: ok=True note="reconcile ran 0s ago"
reconcile_note() -> skipped: venue does not persist positions   status: ok=True note="reconcile ran 0s ago"
reconcile_note() -> ran, but reported no symbol count           status: ok=True note="reconcile ran 0s ago"
```

Not hypothetical: on the paper venue `Reconciler.run()` returns `skipped`
every tick, so liveness reads **`ok=True, "reconcile ran 12s ago"` forever
while zero reconciliation has ever occurred** — and rule 7 is simultaneously
silent on that venue (matrix case D). The whole leg is inoperative and green
together. All eight note tests call `reconcile_note()` directly; none asserts
through `status()` or `report()`.

## Per-question verdicts

| # | Question | Verdict |
|---|---|---|
| 1 | The six approval-guard lines | **SURVIVES** — but the diff widens a write path elsewhere: **KILL** (Ground 2) |
| 2 | Alarm failure modes | **KILL** (Ground 1) |
| 3 | The fence | **SURVIVES** |
| 4 | `NAV_BAND_PCT` / `NAV_BAND_FLOOR_USD` | **SURVIVES**, with a labelled caveat |
| 5 | The flag deletion | Routing **SURVIVES** (0/8 truth-table differences); backfill guard **KILL**; one broken-but-fail-closed tool |
| 6 | The heartbeat | **KILL** (Ground 3), though its stated purpose is genuinely achieved |

## Honest negatives — attacks that did NOT land. Spend no further rounds here.

**The six flagged lines are clean.** `view()` wrote **0 events**,
`approves_empty_order: False`, version `v3`, twelve checks enumerated from
the live policy. `autopolicy_view.GOVERNED` matches the module's uppercase
constants **exactly**. `autopolicy.py` is untouched by the diff. The endpoint
is `@router.get`, no write path. One caveat, not a ground: it publishes
`EXIT_MARKER` on an endpoint with no auth dependency — mitigated by design,
since v3 already requires the trigger event to name the exact order precisely
because the marker alone is forgeable. Worth a line to the riskofficer.

**The order-routing truth table is genuinely unchanged** — both versions
re-implemented verbatim and run over all eight combinations: **0
differences**. The store-target/order-routing conflation is *not*
reintroduced.

**No live code still reads the old flag.** Base has 21 references; the branch
has zero live reads — every remaining occurrence is prose. The `db()` refusal
is preserved and re-keyed, not dropped.

**The fence is tight.** A *point* match at 1e-6, not a band: a fenced symbol
drifting further alarms; drifting back alarms with the opposite sign
(residual deliberately unclamped); unfenced symbols get no suppression. The
`money.f()` `Decimal→float` round-trip does not break it at fund scale. Two
disclosed caveats, neither a ground: the alarm's `metric` reports the
residual rather than the total divergence, and the fence has no expiry.

**Both new numbers check out arithmetically and gate nothing severe.**
$0.92 / 0.0488% ⇒ NAV $1,886.16; 1.0% / 0.0488% = 20.5×, so the "~20×"
basis is sound. But at NAV $1,886 the band is `max(18.86, 150) = $150`, so
**the floor is the only operative leg**, at 7.95% of NAV / 163× the noise
floor — not the 20× its comment describes. The diff discloses this itself, so
it is a mislabel, not a hidden move. The floor's basis is category-confused: a
NAV-vs-equity gap is a *valuation* difference, and the case that creates one
is a position present on one side and missing on the other — exactly what a
$150 floor is sized to miss. Note the live gap is **$128.48**, sitting $21.52
under the floor. Not a kill: the leg is `info`, and info alarms neither
auto-halt nor block auto-resume. **Changes to a ground if** any consumer
treats `broker_drift_nav` as actionable.

**One broken-but-safe tool**: `firebase.py` changes the identity label from
`"mock"` to `"offline"`, but `scripts/mock_seed.py:107` still refuses unless
`env == "mock"`. The seeder can now never run — fail-closed, harmless, but
silently dead.

**Performance, not correctness**: `EVENT_SCAN = 1_000_000` means `/fund/tca`
performs four full-log folds per request. Worth a look against Firestore
before it matters. The `window` block itself is honest.

**Reproduction was clean**: the branch's own suites pass on the exported tree,
**142 passed**. Every ground above is a hole the green suite does not cover,
not a broken test.

## What would change my mind

1. `pipeline.py:332` passes a reconciler — or `_drift_alarms` raises
   `broker_drift_unmeasurable` on every absence path.
2. Proof that `/fund/venue/backfill/apply` is unreachable on every
   configuration the fund runs, or the guard restored to an explicit operator
   opt-in.
3. `heartbeat.status()` stops overwriting the beat's note, and a test asserts
   the three states through `report()`.

Nothing in the fence, the routing split, the autopolicy view, or the two new
constants needs re-attacking. **A repaired version of this diff is worth
merging — the fund currently has no broker-drift alarm at all, and that gap is
worth more than these three defects cost.**

---

## co-CTO verification note (2026-08-21/22, at resolve)

**Ground 2 verified line-exact before acting, because it is the money
ground**: `backfill.py:230` appends `EventType.ORDER_FILLED` — a permanent
write to the ledger NAV and positions fold from. The surviving guard checks
`env == "production"`. `ClarkHarness/.env` carries **`FUND_ENV=staging`**
while `FIREBASE_SERVICE_ACCOUNT_JSON` points at `hedgefund-ae96c`, the real
fund project — so the production refusal does not fire here. The branch's own
comment discloses the change in plain words ("these endpoints are now
reachable where the env-var test refused them"), which is to the builder's
credit and does not make it less of a widening: a money-bearing write path
moved without a versioned envelope change or a written reason.

**THE DIFF IS NOT MERGED.** The KryptonPay half (0 sensitive, 0 forbidden,
230/230) was merged separately at `65e6fdc4` and is unaffected by this
verdict; the builder designed the UI to degrade honestly while these spine
endpoints are absent, so the split is safe.

**The finding that outlives this review** is the adversary's own: the
sensitive-diff classifier is a **regex**, and it flagged the benign lines
while missing the only real widening, because its vocabulary has no term for
`backfill`, for ledger-write endpoints, or for guard-predicate renames. A
keyword filter is standing in for a control-flow question. That is a defect in
the fund's own instrument, found the second time that instrument was used in
anger, and it is filed as harness work rather than left as a note.

Routed back to the builder as dispatch 8 round 2 with the three repairs and
the instruction that the fence, routing split, autopolicy view and NAV
constants are sound and must not be re-litigated.
