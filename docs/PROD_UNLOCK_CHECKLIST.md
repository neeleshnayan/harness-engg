# The PROD unlock checklist

**Created 2026-08-28 on the CEO's decision, verbatim: "Since only I hqave
access to our system we might not need the safety lock just yet but park it
for PROD."** The reasoning recorded with the decision: today exactly one
human can reach the spine, so endpoint guards protect against an actor who
does not exist; the day the fund funds a real account or a second person
gains access, that premise dies. **This file is the durable park** — each
item below BLOCKS the prod/live-money unlock and is re-decided (build or
waive, in writing) before `PROD_UNLOCKED` ever flips.

Append-only; items leave only by being built (commit cited) or by a written
CEO waiver. The riskofficer audits this list against the live code at every
G1/live-account milestone.

| # | item | source | status |
|---|---|---|---|
| 1 | Guard `POST /fund/risk/limits` (approval guard: allowlist, echo, mandatory reason; refuse unknown keys) — the endpoint that can disarm the halt | riskofficer #7 F3 (fourth ask); fund.py:7394-7399 | PARKED 2026-08-28 |
| 2 | Guard `POST /fund/exits` and `POST /fund/exits/override` (the second disarms a committed stop); register `READINESS_EXIT_PREDATE_MARGIN = no time floor, authorship guard instead` (measured basis: 81.8/91.9/101.3 s margins on the first three auto-approvals) | riskofficer #7 F4 | PARKED 2026-08-28 |
| 3 | Flip `no_shorting = true` on the trading account (long-only mandate; venue default ships shorting enabled at 4× margin) | adversary v5r2 #4 → chair verification 2026-08-28 | PARKED 2026-08-28 |
| 4 | confirmEcho: full-id echo (today `target.slice(0,8)`, KryptonPay fundMode.ts:218) — the alpaca-p collision ruling | adversary d11-v2 #2, builder d14 #2 | PARKED (pre-existing pre-prod blocker, now recorded here) |
| 5 | Re-verify the F9 latent pair before any second approver exists: chair-identity allowlist re-spelled inline (fund.py:5601, :5614); `deskcard._VIA_RE` admits identities the guard refuses | riskofficer #7 F9 | PARKED 2026-08-28 |

**What would change this decision's mind** (clause 4, recorded at decision
time): a second person gaining any access to the spine, a real-money account
being funded, or any unexplained write on a guarded-class endpoint —
whichever comes first re-opens every parked item immediately, before the
event that triggered it proceeds.
