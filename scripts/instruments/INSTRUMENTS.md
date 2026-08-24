# THE INSTRUMENT SHELF — reusable measurement tools, promoted from dispatches

**Created 2026-08-23 under Delegation v2, on the CEO's question: "are all of
our team members logging re-usable skills?" The gap this closes: seats were
naming instruments reusable in their STATEs while the scripts lived in the
session scratchpad — ephemeral by design. From now on, THE PROMOTION IS PART
OF THE RESOLVE PIPELINE: any instrument a seat names reusable in its STATE
is copied here by the chair at resolve, with one index line. An instrument
on the shelf is a skill the whole firm keeps; one in a scratchpad is a
memory one seat had.**

Rules: append-only by convention (new instruments, never silent edits — a
sharpened instrument gets a new file or a dated note beside the old);
paths inside scripts may reference old scratchpad worktrees — repoint the
constants at the top before running; none of these touch money paths.

## Gate & criteria instruments

| instrument | what it measures | born |
|---|---|---|
| `adv23/probe3.py` | **The premia-rule instrument**: shipped rule vs TRUE excess-Sharpe advantage on realised-rf, over zero-skill cash/beta blends × belt windows. Run on ANY future premia criterion. | adversary D23 kill |
| `adv23/probe5.py` | **The gate re-judge identity harness**: re-judges every stored enriched job result under two gate revisions, diffs passed/failures/version/checks. ~4s for 55 results. Run on EVERY gate diff. | adversary D23 |
| `adv23/probe8.py` (+probe2) | Zero-skill Dirichlet false-pass census in the belt's own window geometry; probe8c arm samples the cash-heavy population a kill describes. | adversary D23 / builder D29 |
| `adv23/astdiff_d24.py` | AST-diff with constants between two revs: which symbols changed, added, removed. Repoint the two revs and run. | adversary D22 |
| `identity_dump.py` | 62-case alpha-verdict byte-identity dump (base worktree vs head) — the builder's half of the identity proof. | builder D23 |
| `d41/clocks.py` | **Which clock the belt's stored series actually run on**, and what LEAN's per-observation PSR target is worth on it: obs/year, the hurdle, and what a level demands, over every stored result with readable dates — plus the `n` vs `n-1` convention side by side, because the two have been confused for one population. Null-tests itself (an exact-252 series must read 1.000000) and REFUSES on a missing dump rather than printing bands over zero rows. Cited by the `min_psr_pct` register draft. | builder D41 |
| `mutate_d23.py` / `mutate_d24.py` / `d27mutate.py` | Mutation harnesses (byte-exact restore, CRLF-aware, git-status check). Copy the pattern, swap the mutant table. | builders D23/D24/D27 |

## Desk & store instruments

| instrument | what it measures | born |
|---|---|---|
| `adv23/d24_store.py` | Real-store re-derivation for supersession canonicalisation (CALL the repaired layer, never MODEL it). | adversary D24 re-blind |
| `adv23/d24_routing.py` | The door-predicate-over-live-traffic instrument: would-422 count for routing enforcement on the day's real filings. | adversary D22/D24 |
| `d24probe/probeA2.py` / `probeE2.py` / `probeB5_on.py` | The supplements for layers the original probes model by hand: flood-to-endpoint, real add(), flag-on arm via wrapper. | builder D24 |
| `d27probe_lock2.py` | **The two-armed lock test**: every reader completes under an open blocker (arm 1) AND the schema path raises LockNotAvailable under lock_timeout DSN (arm 2 — without it arm 1 proves nothing). Run on any store's readers. | builder D27 |

## Host & process instruments

| instrument | what it measures | born |
|---|---|---|
| `d29/suite_when_free.sh` | Self-limiting suite runner: polls the belt lock, respects the 1.5 GB RAM floor, takes/releases `.suite_running`, writes a verdict file. THE pattern for heavy runs beside heavy neighbours. | builder D29 |
| `cdp_strict.js` | Occlusion probe that intersects every clipping ancestor's rect before elementFromPoint — the honest click-interception count (its naive predecessor over-counted 30×). | builder D28 |
| `cdp28.js` | CDP viewport/geometry sweep across widths for the Studio shell. | builder D28 |
| `stale_pyc_scan.py` | **Does this tree SERVE bytecode its source denies?** Recompiles every source with the import machinery's own settings and names the first differing node with both values. Separates POISONOUS (invalidation key intact — Python will run it) from stale-not-served. RUN IT AFTER ANY MUTATION PASS: a same-length in-place edit (`1.0`->`1.1`) restored within one second leaves mtime and size unchanged, so the mutant is served to every later test while `git status` reads clean. Twelve red tests, no defect. | builder D41 |

## Data instruments

| instrument | what it measures | born |
|---|---|---|
| `tiingo_probe.py` | The 5-URL vendor probe battery: recycled-ticker decider, dead-name fetch, metadata control, ABSENCE control (a silent empty-200 is UNKNOWN, never "none existed"). Adapt per vendor (fmp_probe2 pattern in the D31-era scratchpad). | analyst pituniverse |
| `tiingo_backfill.py` | Throttled, checkpointed, manifest-writing puller under a free tier's own limits; empty-200 recorded UNKNOWN. Key from env, never on disk. | chair, same night |

Where the skill is a RULE rather than a script, it lives in the seat's own
file via `## EVOLVE` (Ed's 15-item pre-flight card; the quant's container
census; the adversary's CALL-vs-MODEL probe classification; the builder's
null-test-your-instrument and commit-before-checkout-baseline standards) —
the seat files are the skill registry for judgement; this shelf is the
registry for tools.
