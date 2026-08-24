# ADVERSARY — D36 DIFF + PROD-GATE PACK v2 — 2026-08-24 (run-adversary-d36-prodgate2)

Blind batch: the builder-d36 gate diff (sensitive surface `app/fund/gate.py`)
and prod-gate precondition pack v2 (trace `3eeb42d4`, a labelled re-review of
the pack killed at batch 4). Filed verbatim by the chair; STATE appended to
`.claude/state/adversary.md`; BINDS carried to builder, validator, quant,
mechanism. Chair resolution at foot.

# TL;DR

```
D36 gate diff: the fix is right, the NUMBER is not. Replacing the old "luck" test
was correct — it was secretly a 1.4-Sharpe skill hurdle mislabelled as a luck test.
But the new setting (50%, i.e. "the Sharpe just has to be positive") was picked by a
calibration whose one tuning input is estimated from 4 of the fund's 336 candidates,
all at the low end. Re-run inside the range the fund's own data actually spans and the
same rule picks the STRICTEST setting instead of the loosest. Everything else in the
diff checks out and costs nothing today. Needs a human: re-set that one number.

Prod-gate pack v2: two of three legs are genuinely fixed. The third still cannot be
judged — the "and tested" half names a test that does not exist anywhere in the repo
and never says how the gate would read it. Not approvable as written; one sentence
from being approvable.
```

---

# ITEM 1 — builder-d36 (gate v4.4 / premia v5r4)

## VERDICT: **KILL — narrow, on one constant.** `CRITERIA["min_psr_pct"] = 50.0` (`gate.py:1085`, head). Everything else in the branch is certified below, including the statistic change, the premia leg, the credit-off decision and the scope.

### What is being changed, stated in the units that matter

Base compared `robustness.psr_pct` (LEAN's published figure) against 65.0 (`gate.py:856` base). Head compares our own target-0 PSR against 50.0 (`gate.py:1068,1085` head). At target 0, `PSR ≥ 50%` ⟺ sample Sharpe ≥ 0. So the alpha luck criterion moves from an effective annualised-Sharpe hurdle of ~1.34–1.51 (the artifact's own inversion) to a **sign test**. The diff says so plainly (`gate.py:1076-1077`).

The level was chosen by one rule: the **lowest level at which the full-gauntlet zero-skill pass set stays a subset of today's** (`calibrate.py:448-457`). Today's arm is not run — it is **emulated** at a per-observation target `ENGINE_TARGET_MID = 0.0755` (`calibrate.py:85`), swept over `(0.0700, 0.0792)` (`calibrate.py:86`).

### KILL ground: the chosen level is an artifact of the emulation target, and the swept range is the wrong range

**(a) Run the estimator over the proposer's own sample.** The artifact inverts the engine's target on **four** control candidates and calls `(0.0700, 0.0792)` "the whole measured range". I ran the artifact's own `statistics.implied_target_sharpe` over **every stored belt result carrying a readable engine PSR and a daily series — 336 of 765** (`scratchpad/advd36/clock.py`, live Postgres):

```
n=336  min=0.0613  p10=0.0668  p25=0.0769  median=0.0887  p75=0.0946  p90=0.1002  max=0.1184
share above the swept ceiling 0.0792 : 71.4 %
share above 0.0843                   : 58.3 %
share above 0.0909                   : 40.5 %
```

The four controls sit at roughly the 4th–27th percentile of the fund's own population. **The sweep covers the low tail and calls it the range.**

**(b) The answer flips inside the untested region.** Same script, same seed, same population, same 700d window — only the emulation target moves (`scratchpad/advd36/popE.py`, n=400, seed 20260824):

| emulated target | shipped engine@65 full-gate FP | lowest target-0 level holding the inclusion |
|---|---|---|
| 0.0755 (as shipped) | 2.50% | **50.0** |
| 0.0792 (swept ceiling) | 2.50% | **50.0** |
| 0.0843 | 2.50% | **50.0** |
| 0.0909 (median of the 336) | 1.75% | **99.9** — no level 50–99 holds |
| 0.0953 | 1.50% | **99.9** |

At 0.0909 the calibration's own exit path fires: `calibrate.py:569-575` returns **1** with "NO LEVEL HOLDS ON EVERY WINDOW — the ruling's falsifier FIRES: ship engine_reported with the corrected sentence."

**(c) Corroborated on a second seed and a second construction.** Paired common-random-numbers, engine@65 vs sign-test@50, 700d (`scratchpad/advd36/popD.py`, n=600, seed 4242):

```
population    emu target   FP engine@65   FP sign-test     delta      SE  head-only  base-only
shipped           0.0755          1.83%          1.83%    +0.00pp  0.00pp          0          0
shipped           0.0909          0.83%          1.83%    +1.00pp  0.41pp          6          0
probe8            0.0909          5.17%          6.67%    +1.50pp  0.50pp          9          0
invested          0.0755         15.50%         16.17%    +0.67pp  0.33pp          4          0
invested          0.0909          5.50%         16.17%   +10.67pp  1.33pp         64          0
```

Every discordant draw runs one way (0 base-only in all six cells). On a fully-invested basket at the corrected target the loosening is **+10.67pp ± 1.33pp (8σ)**.

**(d) Independent arithmetic reaching the same place.** The 0.0755 target is a *per-observation* number inverted from series LEAN emits **one point per calendar day** (`statistics.py:306`; confirmed empirically — the 336 candidates carry n=365 for a one-year run). It is applied unchanged to synthetic series the script itself describes as session-dated (`calibrate.py:488`). Because the PSR penalty enters as `t·√n`, the same per-obs target on a 252/yr series is weaker by `√(365.25/252) = 1.2039`; `0.0755 × 1.2039 = 0.0909` — the same value the empirical distribution puts at its median. Two independent routes, one number, and the conclusion changes there.

**(e) Population fragility, secondary.** Even at the as-shipped target the inclusion already fails outside the drawn population: fully-invested Dirichlet 13.0% → 13.5% (+1 of 200), and probe8's own shape (cash as a 9th simplex slot, mean cash 0.112) fails at the full window 0.0% → 1.0% (`scratchpad/advd36/popA.py`). The rows that carry Table 1 are drawn with a cash weight uniform on [0.05, 1.0] (`calibrate.py:151`) — a choice made and justified for **Table 2**'s credit question and inherited by Table 1 without re-testing.

**(f) The fund's own register agrees the number is unsupported.** `judgement.py` is byte-identical in this diff; its `min_psr_pct` entry still reads `expected=65.0`. Merging makes `/fund/judgement` report its **first drifted entry**: base `drifted: []` → head `drifted: [{key: min_psr_pct, from: 65.0, to: 50.0, reason: "…either the reason or the number is stale"}]` (`scratchpad/advd36/fuzz.py`). Verified live: the register today is `count 19, drifted 0`.

**Money.** $0 today — 0 of 765 stored results flip either way, and no candidate has ever passed under this leg. A merge-time decision about every future alpha verdict, not a fire.

### Attacks that FAILED — said loudly, they are real

1. **The off-switch attack came back empty.** `premia_require_luck_filter=False` sets `checks["luck"]["applied"]=False` with a reason and returns no failures (`gate.py:1368-1372`); the criterion cannot read as passed. No production caller passes `premia_criteria`. The level guard is checked **after** the off-switch by design and is correct. Unknown `psr_basis` fails closed (verified, `scratchpad/advd36/offswitch.py`).
2. **The emulation-divergence attack failed on its own terms at n=200** (`popC.py`, all six targets held). It only bites once measured at n≥400/600 — I nearly filed the negative.
3. **The pin holds and is structural.** `premia_inputs` is the single producer; the credit `smap[d] - wmap[d]*rfmap[d]` and the benchmark subtraction `bmap[d] - rfmap[d]` use the *same* `rfmap` object in the same loop (`leanrunner.py:2338-2352`, `:2313`). No second rate series exists. My D23 constant-rf channel cannot re-enter here.
4. **Alpha identity is true and understated.** The claim is "11 of 11". Re-judging **765 stored results under base and head, both claim types** (`scratchpad/advd36/judge.py`): 0 flips, 0 crashes, 0 passes either side. Head only ADDS failures. **Strictly refusing on every stored input.**
5. **Scope is tight.** AST+constant diff: `autopolicy, walkforward, exitrule, risk, orders, pipeline, events, pgstore, judgement, factory, api/v1/fund.py, marketdata` all **byte-identical**. Nothing removed anywhere.
6. **The premia luck filter is a real discriminator, not decoration** (`scratchpad/advd36/premia.py`, n=400): premia-leg zero-skill false passes 11.75% (v5r3, no filter) → 7.50% at the shipped 65 → 1.25% at 95 (700d); 7.25% → 4.25% → 0.00% (full).
7. **The credit-off decision is corroborated by my own instrument.** With the new luck filter ON at 65, turning the credit on takes the premia leg 7.50% → **28.25%** (700d) and 4.25% → 16.25% (full). My batch-4 kill is honoured and the filter does not substitute for it.
8. **Tests are honest.** 285 passed across the six new/changed test files. No test asserts a loosening.

### Residuals (named, not grounds)

- `evaluate()` can raise on hostile stored payloads: 512-combination fuzz → **128 raises, 0 unexpected passes**; both paths need magnitudes no producer emits. Fails loud, not open.
- `leanrunner.py:2053` docstring contradicts `:2318` (self-penalising direction).
- `gate.py:1049-1051` claims the off-switch is recorded in the stored verdict's `criteria`; zero premia keys appear in it (`"criteria": c`, `gate.py:2345`).
- `premia_min_luck_pct = 0` DOES pass a measurable advantage (`0.0 >= 0.0`), contra `gate.py:1043-1049`; the gate does not range-check the level while `calibrate.py:338-342` does. Unreachable from production.
- Operational: 426 of 765 stored results have no undownsampled series, so the alpha luck leg reads UNMEASURABLE on 56% of the fund's history. Direction is refusing.

### What would change my mind

A shipped-arm measurement that is **not an emulation** (one LEAN container over a synthetic series pinning the engine's target on the same clock the draws use); **or** a stated argument, with data, that the four control candidates are the right analogue and the other 332 are not; **or** the level chosen on a power/false-pass trade-off rather than an inclusion test against a criterion the same table shows is dominated.

**One-line verdict:** `KILL (narrow, one constant) — gate v4.4's alpha luck level CRITERIA["min_psr_pct"]=50.0 (gate.py:1085) rests on an emulated hurdle calibrated from 4 of the fund's 336 stored candidates; 71.4% of that population implies a target above the swept ceiling 0.0792, and at the population median 0.0909 the calibration's own rule chooses 99.9 instead of 50.0. Everything else certified: 0 verdict flips on 765 stored results, 12 modules byte-identical, credit ships OFF and is re-measured at 7.50%→28.25%, premia luck filter measured as a real discriminator, 285 tests green.`

---

# ITEM 2 — prod-gate precondition pack v2 (trace 3eeb42d4) — **RE-REVIEW** of the pack killed at batch 4

## VERDICT: **CANNOT TELL** — and the missing thing is named: **how the gate EVALUATES the "tested" half of P4.** P3 SURVIVES as re-specced; P2's ground is mitigated but its specification names the client-supplied shape that the pattern it cites explicitly refuses.

### Live baseline, re-measured today

`GET /fund/mode` → `n_met 1 / n_blocking 4 / reachable false`. `GET /fund/liveness` → `risk_monitor ok:true 0.8s`, `exit_check ok:true 0.3s`. `GET /fund/venue/reconcile` → `delta_usd 128.43 / delta_pct 6.8106 / symbols_out_of_sync 10` — **worse than yesterday's 126.54 / 6.7104**. `GET /fund/judgement` → 19 entries, drifted 0, **17 of 19 empty `trigger_spec`** — the 2-of-19 base rate reproduces on a fresh sample.

**Magnitude of the loosening:** three unevaluable-and-therefore-blocking legs become evaluable; `n_blocking` goes **4 → 1**, and the survivor is a countdown of 12 real fills.

### P4 — half closed, half unevaluable

**Closed, plainly: the reader is the right instrument and it fails closed.** `judgement._wired` reads `heartbeat.status(job)`; `status` returns `ok: None` for an unobserved job, `_wired` raises on that, and `Precondition.evaluate` catches any exception into `status: "unchecked"` (`mode.py:336-341`) — never "met". The beat is recorded **inside** the try, **after** the call (`main.py:210-214`), so a raising tick stops the beat and the budget marks it stale. That is the exact shape my batch-4 AST probe scored FALSE-WIRED; the heartbeat reader is not fooled by it.

**Not closed:** the "tested" half. The named test does not exist — zero files outside `app/` mention `run_risk_monitor_tick` or `run_exit_check_tick` — and the proposal never states how the gate reads it: a static existence check is a repo fact satisfiable in the same commit (my batch-4 ground unmoved); running pytest at gate-read time is precisely what P3's own re-spec forbids for itself. Marginal content priced: the register already publishes `wired: true`; a heartbeat proves the call *returned*, not that the switch *works* — the leg that proves function is `controls_fired`, already separate and already met.

### P3 — SURVIVES as re-specced

`unrealised_pnl_pct` (`riskmonitor.py:411-445`) is fixed. The proposed fixture, executed in-process: `f(-10, 110, 100) = -10.0` → the assertion passes on the fixed code; the pre-fix mutant (ignores qty) returns `+10.0` → caught. A real behavioural pin on the live code path. Two caveats, neither a ground: it is a one-point assertion (three other sign mutants pass it), and `avg_cost <= 0 → 0.0` is a documented open defect the fixture does not reach.

### P2 — mitigated ground, wrong shape

Routing through `_guard_approval` is real (10 guarded channels; `venue_sync` at `fund.py:5061`). But `fund.py:5068-5070`, nine lines after the cited pattern: *"The plan is re-read here rather than trusted from the client, so the numbers written are ones this process just measured."* The proposal says the attestation must **"carry the machine-measured numbers"** — the client-supplied shape the cited model refuses. Nothing in the spec says the server re-reads the reconcile at attestation time, and nothing says the number **decides** anything. Also unresolved: an expiry bounds the clock, never the divergence (the book moved $1.89 and 0.10pp in one day, in the wrong direction); and `_guard_approval` computes `want = (target_id or "")[:8]` — the attestation's token must be provably non-empty.

### What would change my mind

One sentence naming the evaluation method for P4's "tested" half — neither a source read nor a gate-time pytest run — plus P2 re-specced so the server re-reads the reconcile at attestation time and states what the number must satisfy. With those, I would expect to clear the pack on the next pass.

**One-line verdict:** `CANNOT TELL (pack v2) — P3 SURVIVES (in-process fixture catches the pre-fix mutant), P4's WIRED half CLOSED (heartbeat beat inside the try after the call; unobserved raises to "unchecked"), but P4's TESTED half has ZERO referents in the repo and no stated evaluation method, and P2's "carry the machine-measured numbers" is the client-supplied shape the pattern it cites refuses nine lines later (fund.py:5068-5070).`

---

*Chair's resolution (2026-08-24): Item 1's kill triggered the PSR ruling's
own pre-committed falsifier path — the engine statistic stays at 65.0 with
the corrected sentence; D37 dispatched with the certified surface frozen
(level revert + the four residuals only); the register-why rewrite drafted
for the chair at merge; the engine-target pin queued as a v2-lane
experiment (one LEAN container over a synthetic series — no more
emulation). Item 2: pack v3 filed with exactly the two named repairs
(P4-tested as per-switch controls-fired evidence from the append-only log;
P2 as server-side re-read with refuse-unless-bound-or-fence); routes blind
again, iteration 3. Per the non-negotiables this document is never edited.*
