# secretary (Donna) — seat memory

**Seated 2026-08-20 by CEO decision. No runs yet — the first EoD dispatch
will establish the memo template; write your STATE so your successor can
produce tomorrow's memo faster than you produced today's.**

Standing facts for the first run:
- Archive location: `ClarkHarness/docs/archives/YYYY-MM-DD.md`, one file
  per day, §1 short memo (half-page hard limit) + §2 detailed record.
- Event types in Postgres are PascalCase (`OrderFilled`, not
  `ORDER_FILLED`) — the validator's lesson, already on the API card.
- Three repos to sweep with `git -C <repo> log --since=...`: ClarkHarness,
  KryptonPay, and the firm repo (workspace root).
- The flight recorder (`GET /fund/desk`) carries runs with verdicts,
  reasoning, and per-recommendation decision status — it is the richest
  single source for "who delivered what and what the CEO decided".

## STATE

**Day one, 2026-08-20 documented on 2026-08-21 (first Donna run, dispatched "lets run her for yesterday"). The template below WORKED — reuse it, do not redesign it.**

**Method that produced this memo in one pass (repeat it):**
1. Read `.claude/state/secretary.md`, then the day-pack if the CTO prepared one — treat the pack as an INDEX, never as the source of a number.
2. `fund_events` schema gotcha: the type column is **`type`**, not `event_type`; `ts` is **text** (filter with `ts like '2026-08-20%'`), `written_at` is a real timestamptz. Connect with `psycopg` via `ClarkHarness/venv/Scripts/python.exe`; there is **no `psql` on PATH**.
3. `fund_agent_runs` columns: `run_id, seat, task, model, tokens, tool_uses, dispatched_at, resolved_at, artifact_path, verdict, output, recommendations, meta, reasoning, trace_id`. It is **`tokens`, not `tokens_used`**. Filter `resolved_at::text like 'YYYY-MM-DD%'`. This table is the single richest source for the runs and floor sections — verdicts come out quotable.
4. Commit counts: `git -C <repo> log --all --date=format-local:'%Y-%m-%d' --pretty=format:'%h|%cd|%s' | awk -F'|' '$2=="YYYY-MM-DD"'`. **`--since/--until` gave 112 where the true count was 99** — it filters on author date and leaks across the boundary. State the method in the infrastructure section.
5. `GET /fund/risk/monitor` returns state as of NOW, not as of the documented day — useful for confirming carried-forward items, dangerous if pasted into the NAV section. NAV bookends come from `NavStruck` events only.

**Numbers established for 2026-08-20 (reuse as the prior day's reference):** open NAV $2,011.81 (seq 228) = prior strike (seq 209); close $1,884.79 (seq 562), -$127.02, -6.31%; close cash $1,383.46 / gross $501.34 (26.60%) / 2 positions; 8 halts, 7 resumes, ended halted; 8 fills, $1,036.54 notional; 16 runs, 3,216,188 tokens, 1,497 tool uses, all Opus; 99 commits (34/35/30); 17 docs; 188 decision events (CEO 103 = 101 accepted + 2 rejected; CTO 85).

**Things I could NOT verify and therefore did not write:** the dispatch brief offered "three usage-limit interruptions hit the CTO session" — **no citation exists** in `cto.md` or any seat STATE; omitted. The brief also said the day ended with the north-star metric adopted; the record dates commit 5521d48 to **2026-08-21T00:45:11Z**, so it went to the carried-forward section with the discrepancy stated. The brief's "quant filed 7 harness items, builder 5" is not stated in either STATE file; I used measured token/run share for the observer's note instead. **Hold this line — the brief is a pointer, the log is the source.**

**Format contract as exercised (do not drift):** TL;DR fence, 5 lines, no citations. THE DAILY = dateline, book-first line, 3-6 bullets, ranked Awaiting-you, one italic tease. THE RECORD = sections I-IX, `##` roman headings, tables for anything with >2 numbers, zero exclamation marks, citation inline on every claim. Three-leg metric numbers live in I (leg 3, capital deployed), III (leg 2, candidates to the belt), VI (leg 1, defects) — put them there every day so the trend is readable across archives.

**Standing observations to carry into tomorrow's observer's note (check whether they repeat — a pattern across days is the strongest thing this seat can say):** (a) CEO decision bursts >20 items and whether the COO trigger fires before or after the desk fills; (b) builder's share of bench tokens; (c) analyst and mechanism run counts as the leg-2 canary; (d) the UTC/local dating drift — two artifacts and one written reason were misdated on day one, and `docs/archives/` did not yet exist when I wrote this.

- [CTO note at resolve, 2026-08-21]: filed verbatim to docs/archives/2026-08-20.md
  (the directory created by this filing — her own finding), PDF rendered, recorded
  as run-secretary-1. Spot-checks all exact. She refused two claims from MY OWN
  brief for lack of citation — the seat's hard line holding against its principal
  on day one is exactly the seat working. Her §IX items and record-keeping
  findings are on the desk via the run record.
