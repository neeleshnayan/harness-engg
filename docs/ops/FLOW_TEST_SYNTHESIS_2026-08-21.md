# Flow-test synthesis — what the stations said about the machine

**CTO memo, 2026-08-21. The CEO's ask (2026-08-21): "sequence a run so we
can test how its flowing and tune it; let each agent report to you on what
they felt was bottlenecks." Four stations have now run hot and reported:
quant (run-quant-entry11), builder (dispatches 1–6), analyst
(run-analyst-cycle2), mechanism (cycles 1–2). Every claim below cites a
run or a doc; the tuning actions each name their owner and status.**

```
TL;DR
The firm's biggest bottleneck is not any seat — it is that the judging instrument
(the gate) has been dead four rounds while the funnel behind it filled up. Second
is a harness defect that made every single builder dispatch start by proving it
was not about to write to the live tree. Third, the shared API card kept being
wrong, and the bench corrected the chair four times. Most of the small stuff is
already fixed; the two structural fixes have owners and dates.
```

## 1. The bottleneck ranking (by measured cost)

**B1 — The gate is the funnel's ceiling. (Structural; the binding one.)**
Gate v5 has been killed four times; the 10-year backfill, entry 4's
judgeability, entry 13, and three other menu entries queue behind it
(MECHANISM_CYCLE2 §2.5: the current instrument's entire out-of-sample
record is a +47.9% SPY rally — a crisis premium is unjudgeable). The
prerequisites for round 5 are now all written: excess returns
(constitution amendment), shipped geometry, the two new battery nulls,
and the data path (builder D7 Part F, in flight). Owner: CTO, round 5
drafted after D7 lands. This is leg 2's true limiter — not idea
generation, which cycle 2 just proved runs fine.

**B2 — The dispatch harness hands seats the wrong tree. (6/6 dispatches.)**
Every builder dispatch began in the wrong worktree — including, on D6,
the LIVE KryptonPay checkout (builder STATE, dispatch 6). The seat's
clone-both recovery costs ~4 minutes and has never failed, but a
code-writing seat proving it is not in the live tree six times running is
a harness defect, not a seat defect. Tuning: the dispatch flow should
hand the seat a fresh clone path in the brief (owner: CTO brief template,
adopted from D7 onward; the deeper fix — the harness creating the clone —
is a builder item when the dispatch tooling is next touched).

**B3 — The shared API card was wrong four times, caught by the bench.**
Mechanism cycle 1 (lookback param), validator (PascalCase types), analyst
cycle 2 (limit param, per_ticker default, acceptanceDateTime ET),
mechanism cycle 2 (bars depth params — the "3650 works" line was simply
false). Each correction cost part of a dispatch. The card is the right
idea (it exists so seats stop re-learning the spine by trial) but it had
no verification discipline. Tuning adopted: every card claim must carry
its verifying command, and a seat that touches an endpoint the card
describes verifies the card's line as part of the touch (written into the
card header; the four corrections all followed this shape organically —
the rule just makes it binding).

**B4 — Usage limits cut long dispatches. (3 builder interruptions.)**
The constitution day lost three CTO-session stretches to limits; builder
D7 was cut mid-flight today (resumed with context intact via the
same-agent channel). Tuning adopted: briefs now carry the standing line
"prefer finishing and bundling DONE parts over starting new ones" — a
clean partial delivery beats a broken complete one, and the same-builder
resume pattern (D6→D7) means context survives interruptions. The pace
directive already pointed here; the limit makes it mechanical.

**B5 — Work was invisible to the human who had to act on it. (Fixed.)**
The CEO's desk read "0 awaiting you" while two asks waited (fold
vocabulary defect, fixed same hour); seat-filed asks rendered only on the
CTO console (D6 ask surface fixed); the Lab showed runs with no evidence
behind them (D6 Part G fixed); three archived strategies posed as live
(D6 fixed). Pattern worth naming: every one of these was found by a
HUMAN hitting the wall or a seat LOOKING at a rendered page — the CDP
probe doctrine (measure the screen, not the source) is now standing
builder practice because of it.

**B6 — The CEO's attention arrives in bursts the org created. (Watched.)**
Donna's §IX: 103 decisions in six sittings, the two heaviest at ~34 items
in ~7 minutes, and the COO trigger fired late and miscalibrated on the
day it mattered. The counter is fixed (open-only); whether the >20
threshold moves is the CEO's call, unforced; Donna's standing observation
(a) tracks whether the pattern repeats. The four-queue desk (D7) is the
structural answer: decisions arrive by officer, not as one pile.

## 2. What the flow test proved WORKS (do not tune these)

- **The resolve pipeline** (verify → file verbatim → record → resolve →
  STATE append) held across five different seats in one day, and the
  run-record envelope made Donna's full-day reconstruction possible.
- **Blind convergence**: the adversary (judge side) and the mechanism
  (proposer side) independently derived the same financing arithmetic
  (r4 ground 1 = defect D4). The blind-review rule is paying exactly the
  dividend it was designed for.
- **The local split, where checkable**: extraction on local qwen (155
  filings, 58 bad quotes caught by the string gate), sub-functions 4/4 on
  hidden tests — and both the analyst and quant correctly REFUSED the
  split where outputs are not checkable. The delegation law (local
  copies, Opus derives) is holding at the seats' own hands.
- **Seat memory**: quant's fold-geometry numbers, the analyst's PIT rule,
  and the mechanism's "run window_for, never assert it" all carried
  between dispatches without re-derivation. The STATE round-trip is
  earning its cost.
- **Honest negatives at every station**: entry 8 (analyst), entries 4/7
  (mechanism), entry 11 (quant), gate r4 (adversary) — all measured
  kills with revival conditions, none re-litigable. Leg 1 in service of
  leg 3, as tuned.

## 3. Open tuning decisions (the CEO's, unforced)

1. COO trigger threshold (stay 20 / lower) — watch Donna's (a) first.
2. The hardcoded "neelesh" approver in four Studio controls — a
   firm-wide convention; riskofficer's queued batch will opine.
3. Belt-candidate `queued` state (scoreboard shape change) — needs a
   decision before the serialisation work exists.
4. Full-universe corpus deepening (~3.4h compute) — a budget call the
   analyst deliberately did not spend.

## 4. The one-line summary for the record

The funnel generates, the kills are honest, the memory compounds, and the
machine's two real constraints are the gate (round 5, prerequisites
complete) and the harness's worktree hand-off (brief template fixed,
tooling fix queued). Tune those two and the flow test says the rest of
the firm is already flowing.
