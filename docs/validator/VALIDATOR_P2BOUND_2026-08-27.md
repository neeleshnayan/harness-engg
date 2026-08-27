# VALIDATOR — P2 (`book_venue_reconciled`): the bound, measured

**Run**: `run-validator-p2bound`, dispatched 2026-08-27 ~06:04Z under
Delegation v2 (Grace's D2 accepted by the CEO — "agree w Grace"), resolved
by the CTO chair the same morning.

**CTO VERIFICATION NOTE (chair, at resolve)**: the four sharpest claims
were checked against the code before filing — all four hold. (1)
`reconcile.py:95-98` names seq 119-141 verbatim as the mock-mode artifact
("a spine accidentally started in mock mode ran this hourly… seq 119-141
of the local book are exactly that") — cohort A is fenced by the producing
code itself. (2) The mismatch payload at `reconcile.py:121-124` is
`{"symbol", "expected", "actual"}` — quantity only, no mark/notional/NAV,
so no dollar quantile is computable from this event type at any n. (3)
`riskmonitor.py:519` renders `f" ({float(delta_pct):.2f}% of NAV)"` into
the only historical series of the quantity, directly beneath the comment
(":508-512") saying the dollar figure is context, never the trigger. (4)
`mode.py:473`: `"reachable": bool(PROD_UNLOCKED) and not unmet` — the
independent lock the direction note relies on is real. The anti-correlation
headline (H1/M1/M2 ordering) is accepted on the seat's event-log citations
(seq 1414, 1459, 1525), spot-checked for existence, not re-derived.

**Chair disposition**: Leg A adopted as the P2 evaluator spec (builds with
the P3 evaluator — no new constant, tightening-shaped, but routed as a
loosening per the direction note since it makes an unchecked precondition
passable). Leg B held PROVISIONAL until the regular-hours re-measurement
(due 2026-08-28 after 13:30Z), then adversary blind (it is a loosening),
then the CEO. Samplers promoted to the instrument shelf. The CHALLENGE to
D2's method is accepted by the chair and carried to Grace as a BIND.

---

## The seat's report, verbatim

```
TL;DR
The 71 historical reconciliation events cannot calibrate anything: they are two
known incidents logged over and over — 17 distinct rows, not 71 — and both are
already fenced as bad data. Worse, the dollar figure the bound was to be set on
does not measure what its name says: today the book and the broker agree on all
14 positions and it reads $2.10, while on the two occasions the books genuinely
disagreed — once about a third of the fund — it read 5 cents and 18 cents. The
single reading Grace cited (−$0.02) is a hundred times smaller than today's on
an equally clean book, so a bound set there would fail the fund every day.
Recommendation: pass the precondition on the position check the fund's two live
controls already use, taken twice two minutes apart, and carry the dollar figure
as a separately-named marking check at half a percent of NAV. Human needed only
to route this the way any change that makes a locked precondition passable gets
routed; the second code lock still holds regardless.
```

# P2 (`book_venue_reconciled`) — the bound, measured

**Verdict: the bound Grace scoped cannot be built from the population she named, and the statistic it would have been built on is anti-correlated with the property P2 names.** A different specification is recommended, with arithmetic.

## 1. The historical population: 71 events, 17 distinct rows, 0 usable

```
docker exec krypton-pg psql -U krypton -d krypton_fund -c "select case when seq<200
 then 'A_2026-08-15' else 'B_2026-08-21' end as cohort, count(*) as events,
 count(distinct (payload->>'symbol')||'|'||(payload->>'expected')||'|'||(payload->>'actual'))
 as distinct_rows, count(distinct (payload->>'symbol')) as symbols,
 count(distinct left(ts,16)) as runs from fund_events
 where type='ReconciliationMismatch' group by 1;"
```

| cohort | events | distinct rows | symbols | reconciler runs |
|---|---|---|---|---|
| A · 2026-08-15, seq 119–141 | 21 | 7 | 7 | 3 |
| B · 2026-08-21, seq 715–854 | 50 | 10 | 10 | 5 |

**71, not ~50** (the brief's figure and `docs/cfo/GRACE1_2026-08-22.md:165` both say 71 in one place and 50 in another; the 50 is cohort B alone). **A quantile over 71 rows is a quantile over 2 incidents** — pseudo-replication of 3.4×. Both are FENCED, and neither fencing is my judgement call:

- **Cohort A is fenced by the producing code itself.** `reconcile.py:96-99` names these exact sequence numbers: *"a spine accidentally started in mock mode ran this hourly and appended a ReconciliationMismatch for every real holding to the permanent ledger (seq 119-141 of the local book are exactly that)."* The in-memory paper connector reports zero holdings; `actual: "0"` on all 21.
- **Cohort B is the 2026-08-21 venue/ledger divergence** (`docs/pm/PM_DIVERGENCE_2026-08-21.md` §E2 names seq 715–724 as its first ten; `docs/archives/2026-08-21.md:113` records the same 50 with divergence $129.59 / 6.87% at seq 725). PM verdict at the time: *"FENCE THE COHORT… zero trading."*

**Fenced rows: 71 of 71. Calibration points from this population: 0.**

And the payload cannot answer the question anyway: `reconcile.py:124` writes `{"symbol", "expected", "actual"}` — **quantity only, no mark, no notional, no NAV.** "Split by |delta_usd| and |delta_pct|" is not computable from this event type at all. `Reconciler.drift()`, which produces `delta_usd`/`delta_pct`, **writes no events** (`reconcile.py:32-33`, docstring: *"Read-only … Writes NO events"*). Two things named "reconciliation delta"; the historical one is shares, the live one is dollars.

## 2. The only historical readings of the live quantity — n=5, and the ordering is inverted

`drift()` is unrecorded, but `riskmonitor._drift_alarm` embeds its dollar reading in the alarm message. Four raises exist, plus the cleanest calibration instant in the record — the R39 phase-1 sync (`BookReconciledToVenue`, seq 1414), where positions and cash were **SET TO** the venue's own reading, so the residual is *purely* marking (the payload says so: `"marks_from": "the fund's own pricer, not the venue's"`):

| # | when | symbols out of sync | mismatched notional | delta_usd | delta_pct |
|---|---|---|---|---|---|
| H1 | 08-24 12:36:46Z, post-sync (seq 1414) | 0 by construction | $0 | **−2.14** | **−0.1064%** |
| M1 | 08-24 13:46:48Z (seq 1459) | 1 of 8 — XLE | **$174.72** | **−0.18** | −0.01% |
| M2 | 08-24 15:51:37Z (seq 1525) | 3 of 11 — DBA/DBC/TLT | **$650.86 = 32.5% of NAV** | **−0.05** | −0.00% |
| I1 | 08-21 ~15:22Z (seq 725, archive) | 10 of 11 | whole book | +129.59 | +6.87% |
| I2 | 08-22 22:04:18Z (seq 1025) | 10 of 11 | whole book | +126.54 | +6.71% |

**H1 (a perfectly reconciled book) reads 21× the dollar delta of M2 (a book that disagreed with the broker about a third of the fund).** That is the finding.

**The mechanism, verified against the log rather than inferred.** M1: XLE SELL 2.749912 @ 63.536363 filled at `13:46:45.580` (seq 1457); the alarm raised at `13:46:48.576` — **3.00 s later** — and cleared at `13:47:13.599`, 28.02 s after the fill. M2: DBC/TLT/DBA BUYs filled `15:51:33.290`–`15:51:36.031` (seq 1522-1524); alarm raised `15:51:37.965` (**1.93 s** later), cleared `15:51:59.895` (23.86 s after the fill). Both are the **post-fill settlement race**: the book has recorded the fill, the broker's `positions()` snapshot has not. A fill moves book cash and book position **together**, so book NAV is unchanged, and the broker's equity nets the same way — **each ledger is internally consistent and the disagreement is about where the value sits.** NAV delta is blind to it by construction. $650.86 of position disagreement produced $0.05 = 0.0077% of the mismatched notional.

## 3. The live reading is not what the brief says, and it is not stable

Two independent live measurements taken this dispatch, both with **0 of 14 symbols out of sync**:

**(a) Aggregate, `GET /fund/venue/reconcile`, n=58 over 28.5 min (06:06:43Z–06:35:13Z):**

| | min | p50 | p90 | max | sd |
|---|---|---|---|---|---|
| `delta_usd` | 1.68 | **2.10** | 2.23 | **2.25** | 0.181 |
| `delta_pct` | 0.0839 | **0.1049** | 0.1114 | **0.1124** | 0.00904 |

`symbols_out_of_sync` = 0 in 58 of 58. **`book_nav` was 2002.44 in all 58 samples** — the fund's marks are entirely frozen overnight; `broker_equity` moved 2004.12→2004.69.

**The brief's stated live reading (`delta_usd −0.02`, `delta_pct −0.001`) is 100× smaller than today's, three days later, on an equally clean book.** A bound set at −0.001% would report P2 unmet on every one of today's 58 readings. Grace's number is also within 4 quanta of the instrument's own resolution floor (§4).

**(b) Paired per-symbol decomposition, n=20 samples × 7 names = 140 observations (06:08:46Z–06:23:00Z).** Fund mark = `AlpacaConnector._fetch_price` (`alpaca.py:156-161`, `get_stock_latest_trade`); broker mark = the position's own `current_price`, read in the same loop.

| sym | qty | notional | wt %NAV | rel bps (min/med/max) | USD med |
|---|---|---|---|---|---|
| **DBA** | 5.314306 | 153.69 | 7.67 | **110.12 / 110.12 / 110.12** | **+1.674** |
| DBC | 8.122157 | 247.73 | 12.36 | −8.19 / −8.19 / −8.19 | −0.203 |
| IWM | 0.558 | 166.60 | 8.31 | −15.39 / −12.04 / −11.71 | −0.201 |
| QQQ | 0.235 | 167.98 | 8.38 | 18.80 / 30.17 / 33.40 | +0.505 |
| SPY | 0.346119 | 265.80 | 13.26 | 15.40 / 19.70 / 22.18 | +0.523 |
| TLT | 3.019871 | 251.56 | 12.55 | −9.60 / −8.40 / −8.40 | −0.211 |
| **XLF** | 2.862 | 166.71 | 8.32 | **0.00 / 0.00 / 0.00** | 0.000 |

Σ qty×(broker−fund) = **1.732 / 2.087 / 2.186 USD** (min/med/max) = **0.0864% / 0.1041% / 0.1090%** of equity — it reconstructs the observed `delta_usd` to within the $0.06 standing cash difference (broker 584.41 vs book 584.47). **The delta is entirely mark dispersion.** Per-symbol |rel bps|: median 12.04, max 110.12 (n=140); **ex-DBA** median 10.66, p90 26.66, max 33.40 (n=120). **One thin name at 7.67% weight supplies 80% of the delta.**

**Null test on the instrument** (the D28 standing rule): XLF returned exactly **0.00 bps in 20 of 20** samples against a domain of 140 paired observations — the dispersion instrument is not manufacturing a gap.

## 4. The tolerance chain — nothing clips the delta, and the two `_TOL`s are on a different axis

| constant | value | where it acts | clips `delta_usd`/`delta_pct`? |
|---|---|---|---|
| `reconcile._TOL` (`reconcile.py:20`) | 1e-6 | `:63` divide-by-zero guard on `book_nav`; `:77` per-symbol qty `in_sync`; `:120` the emit test | **No** |
| `engineledger._TOL` (`engineledger.py:63`) | 1e-9 | `:798`, the **ENGINE** leg (fund book vs LEAN session implied book), composed as a sibling key at `fund.py:5448` | **No — different fold entirely** |
| `positions._QTY_EPS` (`positions.py:37`) | 1e-9 | positions projection | No |
| `nav._EPS` (`nav.py:37`) | 1e-9 | `:160`, skips sub-epsilon positions from valuation | No |
| `autopolicy.MAX_POSITION_DRIFT_QTY` (`:213`) | 1e-6 | v4 check 14, pinned `== float(reconcile._TOL)` by `tests/test_autopolicy.py:517-518` | No |
| **`money.money()` → CENTS** | **0.01** | **`nav.py:216` quantizes `total_nav_usd`; `reconcile.py:58` reads that rounded value** | **YES — ±$0.005** |
| `round(delta_pct, 4)` (`reconcile.py:85`) | 1e-4 pp | display | ±0.0001 pp |

**No layer clips a delta before a bound at any sane level sees it — but the two `_TOL`s the brief names are both QUANTITY tolerances on two different comparisons, and neither is on the dollar axis at all.** The only real clip is cent-rounding of book NAV: at NAV $2,002.44 that is a floor of **0.00025% of NAV** on `delta_pct`. Grace's −0.001% sits 4 quanta above zero.

**Reporting-path defect, small and real:** `riskmonitor.py:519` renders `f" ({float(delta_pct):.2f}% of NAV)"`. The alarm messages are the *only* historical series of this quantity the fund owns, and it prints M1 as `-0.01%` and **M2 as `-0.00%`** — which is −0.0025%, not zero. Anyone calibrating from the record would read a healthy value as zero. Same family as the census's absence-as-value sites.

## 5. Recommended specification

### Leg A — integrity (this is P2; it needs NO calibrated bound)

```
configured is True
AND len(per_symbol) >= 1
AND symbols_out_of_sync == 0
on TWO readings taken >= 120 s apart
```

- **No new constant.** `symbols_out_of_sync` is computed at `reconcile._TOL = 1e-6` and is **already the statistic both live controls use**: `autopolicy.py:517-522` (`book_venue_in_sync`, money path) and `riskmonitor.py:504-506` (`book_venue_drift`, critical alarm, whose own comment at `:508-512` says the dollar figure is *"CONTEXT on the message, never the trigger … this rule owns no threshold of its own"*). Importing it reuses the discipline `mode.py:388` already applied to `PROD_MIN_INFORMATIVE_FILLS` — two copies of one belief is how the cost model drifted.
- **`len(per_symbol) >= 1` is not pedantry.** `symbols_out_of_sync == 0` is trivially true on an empty list; `_drift_alarm` has the same property (`out = []` → `return None`). An unpopulated book would read "reconciled". Absence rendered as agreement, in the precondition that gates real money.
- **The 120 s is the settlement-race window, and its basis is n=2.** Both observed races cleared 28.02 s and 23.86 s after their fill; 120 s is 4.3×. **Honest confidence: 2 of 2 races clearing inside 28.1 s bounds P(a race exceeds 28.1 s) only under 77.6% at 95% (1 − 0.05^(1/2)).** That is nearly no bound; the two-reading form is recommended precisely *because* it does not depend on the number being right. **Falsifier: any observed race clearing later than 120 s reopens it.**
- **Measured basis for "clean" today: 58 of 58 readings at 0 of 14 over 28.5 minutes.** As an independent sample that is **one instant, not 58** — `book_nav` was constant throughout.

### Leg B — valuation (the number Grace asked for), REPORTED beside P2 under a different name

```
|delta_pct| <= 0.50   (% of folded NAV)
```

**Arithmetic — a mandate derivation, not a quantile:**

- Measured healthy ceiling on the record: **0.1124%** (today's max of 58) and **0.1064%** (H1, the post-sync instant three days earlier and independent). Two independent clean instants.
- **What n=2 supports:** 95% upper bound on P(a clean reading exceeds 0.1124%) is **77.6%**. A quantile bound is therefore not available and none is offered.
- **Mechanical headroom instead.** `max_position_pct = 0.20` (`risk.py:53`, live at `/fund/risk/limits`). A single mandate-maximal position at the worst dispersion measured today (DBA, 110.12 bps) contributes **0.2202% of NAV** on its own. Today's whole book, at 70.8% invested, contributes 0.105%. 0.50% therefore survives one mandate-maximal stale name plus today's baseline (≈0.37%) and **fails at two** (≈0.59%) — which is the right place for it to fail, because two 20% positions both 110 bps off a stale feed is a marking problem worth a human.
- **Incident side:** I1 6.87% and I2 6.71% fail 0.50% by **13.4×**. Healthy history passes by **4.4×**. That is the "passes healthy, fails incident" separation the brief asked for — on n_healthy = 2 independent instants and n_incident = 2.
- **Name it for what it measures.** `marking_agreement` / `valuation_delta`, not `reconciled`. On this record the label and the number point opposite ways, and P2's *text* ("Book and venue reconcile clean, or the divergence is explained and fenced") is satisfied by Leg A.

### What the bound does NOT cover

1. **It does not measure position integrity.** Measured: 0.0077%–0.1030% of the mismatched notional on the two real mismatches. Both M1 and M2 would **pass** a 0.50% bound; M2 disagreed about 32.5% of the fund.
2. **Time of day is entirely uncovered.** All 78 live samples were taken 06:06–06:35 UTC = **02:06–02:35 ET, market closed**. The fund's mark is IEX last trade, frozen overnight; the broker's is not. `delta_pct` drifted *up* across the 28.5-minute window (0.0954 → 0.1124). The regular-hours distribution is **UNMEASURED**. H1 (12:36Z) was also pre-open.
3. **Composition.** 80% of today's delta is one name. The 4.4× headroom is a property of today's holdings, not a constant.
4. **Fees.** `FeeLedger.outstanding()` is subtracted from book NAV (`nav.py:198-204`) and has no broker counterpart. It is $0.00 today by an explicit `FeeTermsSet` zero whose own note reads *"Revisit before any outside capital"* — i.e. the $10k path P2 sits on. Non-zero fees inject a monotonically growing delta into exactly this statistic.
5. **An unexplained $0.06 standing cash difference** (broker 584.41 vs book 584.47). 3% of today's delta. Not diagnosed; not claimed as noise.
6. **Single venue, USD, long-only, no margin.** No financing accrual, no FX, no short rebate.
7. **Sample.** 2 independent clean instants, 2 real mismatches, 2 incidents, 71 fenced events. Everything above is a **run of the instrument**, not a model of it.

### Direction note

**Shipping any P2 evaluator that can return `met` converts a precondition currently reporting `unchecked` — which `mode.py:473` counts as unmet — into a passable one. That is directionally a loosening of the prod gate and should be routed as one**, notwithstanding that the CEO's word already covers the evaluator shipping. Two mitigations, both verified: `PROD_UNLOCKED = False` is an independent lock and `reachable = bool(PROD_UNLOCKED) and not unmet` (`mode.py:473`), so this alone cannot open prod; and Leg A introduces **no new constant**. The residual is presentational: when P2 flips, the report will read closer to "5 of 5", and the code lock becomes the only thing standing.

## CHALLENGE (tightens — no adversary pass required)

**Decision challenged:** the CEO's "agree w Grace" on her D2, insofar as it accepts D2's *method* — *"a quantile over the ~50 `ReconciliationMismatch` events already in the log, plus the live reading."* The decision to ship P2's evaluator is untouched and supported.

**New evidence the decider did not have:** (a) the population is **71 events / 17 distinct rows / 2 incidents / 8 reconciler runs**, and **71 of 71 are fenced**; (b) the events carry **quantity only** so no dollar quantile is computable from them at any sample size; (c) "the live reading" moved **from −0.001% to +0.1049% (median of 58) in three days** with 0 of 14 out of sync on both occasions.

**What to do instead:** exactly §5 — Leg A on the existing quantity statistic with no new constant, Leg B derived from `max_position_pct × measured feed dispersion` and named for what it measures.

## GAPS (for strategy generation)

1. **No stored book-vs-venue delta series anywhere.** `fund_metrics_daily` has **0 rows**; `drift()` writes no events; the only history is 4 alarm messages with the percent clipped to 2dp. The fund's realised marking error is the noise floor on any live-vs-backtest attribution — a strategy whose live edge is under ~10 bps of NAV per rebalance cannot be told apart from the mark gap. One `fund_venue_drift` row per reconciler run turns "is this strategy actually working live?" from an argument into a query.
2. **The fund's mark and the broker's mark are different numbers and no field names the difference.** Measured: 12.04 bps median, 110.12 bps worst, per name. A `mark_source` on `NavStruck.positions[]` and the fill's `arrival_price` lets a proposal's cost claim be checked against the mark the book actually uses.
3. **`ReconciliationMismatch` carries no money.** Adding `mark`, `notional_usd`, `book_nav_usd` makes "is this live book trustworthy" a read instead of a reconstruction.
4. **Fenced cohorts are fenced only in prose.** A `fenced` / `fence_reason` annotation would make the Clean Field Rule *queryable* instead of oral, so the next seat proposing a study over live-book history does not re-excavate known-bad data.

---

*The seat's `## STATE`, `## BINDS` and tickets were appended/carried through
the chair's resolve pass, same session. Samplers promoted to
`scripts/instruments/` (p2_reconcile_sampler.py, p2_persym_dispersion.py).*
