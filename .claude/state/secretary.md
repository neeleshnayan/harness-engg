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
