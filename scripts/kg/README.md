# `scripts/kg/` — the knowledge graph's ingestion and its only consumer

Two scripts over `app/fund/knowledge.py`. Design:
`docs/research/KNOWLEDGE_GRAPH_V1_2026-08-23.md`.

```
./venv/Scripts/python.exe -X utf8 scripts/kg/backfill.py --run-id <run> [--dry-run] [--json]
./venv/Scripts/python.exe -X utf8 scripts/kg/report.py ledger <family>
./venv/Scripts/python.exe -X utf8 scripts/kg/report.py calibration [seat]
./venv/Scripts/python.exe -X utf8 scripts/kg/report.py taxonomy
./venv/Scripts/python.exe -X utf8 scripts/kg/report.py cheap
./venv/Scripts/python.exe -X utf8 scripts/kg/report.py families
```

`--run-id` is REQUIRED and has no default: a default would manufacture the one
thing the graph refuses to store a row without.

## What the graph is and is not

It is an **index over the record**, never a second record. **It never gates** —
`tests/test_knowledge_isolation.py` walks the AST of every module under `app/`
and fails if one imports it, in both directions. It is WORK LAYER: one commit
to revert.

`report.py` exists so no reader ships unwired. Four query functions with no
caller are the unwired-kill-switch pattern in a reporting costume.

## What the backfill can and cannot recover (measured 2026-08-23)

| source | rows | yields | why |
|---|---|---|---|
| `fund_candidates` | 41 | 41 hypotheses, 37 outcomes | the gate's stored verdicts — the only source that yields rows |
| `fund_agent_runs` | 92 (and rising — the chair records runs continuously; it read 90 two hours earlier in the same dispatch) | **0 outcomes** | **no column links a run to a hypothesis or a candidate.** Used only to resolve citations |
| `fund_lean_jobs` | 584 | **0 outcomes** | no candidate key on a job; joined by `(algorithm, window)` to PRICE an outcome, never to create one |

Three numbers that shape every reader, and the command that reproduces them
(`backfill.py --run-id <id> --dry-run`):

* **6 of 41** candidates are named verbatim by any stored run. The other 35
  cite the ingestion run, and the split is printed. Anyone building on the
  graph should read that as the size of the provenance gap, not as noise.
* **20 of 41** candidates share their container window with a concurrently
  running sibling of the same algorithm, so their cost reports **ABSENT** with
  basis `ambiguous`. Dividing a shared window would invent an allocation — the
  worst case is candidate `14c0af2073d5`, whose window holds 205 containers
  and 25,043 seconds and OVERLAPS EIGHT SIBLINGS of the same algorithm. A
  further **5** predate `fund_lean_jobs` and report `no_jobs`. Absence is never
  zero and it is never free either.
* **0 of 105** stored kill sentences failed to classify against
  `KILL_REASON_RULES`. The unclassified count is printed on every run so gate
  rewording is visible the day it happens.

## The fence

The three 2026-08-20 and three 2026-08-21 `monthend_rebalance_flow` rows are
the cohort the constitution's clean-field amendment names — *"six independent
measurements, not three before/after pairs"*. They are ingested and then
VOIDED with the amendment quoted, so they stay visible, stay counted as "ever
tested", and leave every comparison query automatically.

The set is **derived** from `started_at` and the script **REFUSES** unless the
derivation yields exactly six. Fencing the wrong rows is worse than fencing
none.

**NO EDGES ARE WRITTEN.** `same_family` is already a column (as edges it would
be **253** rows in `null_random_smallcap` alone -- 23 candidates;
reproduce with `SELECT algorithm, count(*)*(count(*)-1)/2 FROM
fund_candidates GROUP BY 1 ORDER BY 2 DESC`); `descendant_of_kill`, `prior_art` and
`supersedes` are grammar-era facts nobody recorded before the grammar existed.
In particular there is **no `supersedes` edge** between the 08-20 and 08-21
monthend rows: the amendment is that a re-run creates a NEW candidate and
never recovers the old one, and an edge saying otherwise would encode the
misreading the amendment forbids.

## Re-running

Both scripts are idempotent. `backfill.py` upserts hypotheses on their id and
outcomes on a `dedupe_key`, so a second run after a merge writes nothing and
says so.
