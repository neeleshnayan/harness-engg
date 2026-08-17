# Architecture review — 2026-08-17

*Requested alongside the roadmap: what works, what is drifting, and where to
steer. Written the way we would review someone else's system. Numbers are
measured, not remembered.*

---

## What is genuinely right — protect these

**The event-sourced spine with a hash chain.** The single best decision in the
codebase. NAV folds from the log; the broker is a comparison; the chain
verifies 160/160. Everything auditable about this fund descends from it. Never
let convenience put a second source of truth next to it.

**Honesty as an engineering pattern, not a value statement.** The same move
appears everywhere and it is the house style: *absence is never zero.* A
holdout with no trades is "never examined", not 0% retention. A benchmark
missing most of its legs is refused, not reported thin. An unclassified ticker
is unknown, not non-operating. A category nobody reviewed is "no evidence
either way". This is rare, it compounds, and it is the actual moat — a
competitor can copy the features but not the discipline.

**The gate as versioned data.** Criteria live in a dict, verdicts are
sentences, missing evidence fails. "Should we deploy" is a checklist, not an
argument.

**The design system as a single file.** `theme.ts` is why the UI stayed
coherent through a week of fast iteration. Components never branch on theme.

**LEAN as engine of record, driven directly.** Algorithms as files in a
workspace, results parsed back into the fund's own vocabulary. Pragmatic and
versionable.

---

## Backend — what is drifting

### 1. `fund.py` is becoming a god module
**2,677 lines, 131 endpoints**, plus connector selection, module singletons
and some request models. Every new capability lands as another endpoint pair
in the same file. It has not caused a bug yet; it has caused every bug to take
longer to find (the connector-selection surprise this week lived here).
**Steer:** split into routers by domain — `research`, `lean`, `universe`,
`risk`, `ledger` — and move singleton construction into an explicit
composition root. Do it incrementally, one router per touch, not as a big
bang.

### 2. Durable state has three different owners
The ledger's truth is Postgres. Jobs and sweeps are memory-first with a
write-through mirror (this week's fix). Live LEAN sessions are **memory only**
— a restart still orphans them. The scheduler lease is Postgres. Four
subsystems, three answers to "who owns the state".
**Steer:** one rule, applied as each subsystem is next touched: *durable state
lives in Postgres; memory is a cache.* The mirror pattern was the right bridge;
it should not become the destination. Live sessions are the next candidate —
they are precisely the state you want after a crash.

### 3. Import-time singletons
`_connector = (...)` resolves at import, before anyone can reason about env
order — which is exactly how the paper-vs-Alpaca surprise stayed hidden. The
`EventStore.__new__` dispatch is clever, and clever is what magic looks like
before it bites.
**Steer:** FastAPI lifespan/app-state wiring for connector, stores, runner.
Boring, explicit, testable.

### 4. No backpressure on engine containers
Jobs and sweeps spawn daemon threads freely. A sweep plus a factory batch plus
a filings run can stack LEAN containers until the machine dies — not a
hypothetical, it killed a holdout run this week (`WinError 1455`).
**Steer:** a single semaphore capping concurrent containers at 1–2. Smallest
possible change; directly prevents the known crash. Pairs with roadmap #33.

### 5. Network I/O in read paths
Mostly fixed (the 57-second NAV, `enrich=False` for sweeps), but the pattern
needs to be a stated rule rather than a lesson re-learned: **read endpoints
never touch the network; anything network-backed is precomputed with its
staleness stamped on it.** The universe freshness pattern is the model —
extend it.

---

## Frontend — what is drifting

### 1. Twenty-four components fetch for themselves
Each owns its axios calls, error unwrapping (the same snippet copy-pasted),
and polling loop. The network log shows the cost: one page load hits
`/session` and `/nav` four to five times. It works at one user; it is
already noisy and will get worse with the digest.
**Steer:** a small shared fetch hook with cache + dedupe + interval (SWR or ~40
lines by hand). Not a state framework — just one place where "how we fetch"
lives. This alone removes the duplicate requests and the copy-pasted error
handling.

### 2. API types are splitting
`fund_api.ts` holds 87 interfaces, but new components (Evidence, HuntingGround
extensions) declare their own local copies of spine shapes. Two definitions of
one JSON payload is a drift waiting for a runtime surprise.
**Steer:** types live in `fund_api.ts` only; components import.

### 3. No error boundary
A throwing component takes the whole page down. We were lucky this week.
**Steer:** one boundary around each major panel; cheap insurance before the
demo becomes a daily surface.

### 4. The Lab route is becoming the everything-page
Map + hunting ground + editor + results on one scroll. Right for the demo;
watch it. When the digest lands, the natural shape is: map/digest as the
landing, the editor one level deeper. Flagged, not urgent.

---

## The flow — what works and what is missing

The loop's shape is right, and it is the product: map → evidence → judgement →
candidate → verdict → provenance, each arrow one click, mirroring how an
analyst actually works. The demo proved it lands.

Three gaps:

**The loop has no pull.** Nothing brings the operator back tomorrow. Reviews
per week currently round to zero because the loop runs only when someone
remembers it exists. The morning digest (roadmap #31) is not a feature among
features — it is the loop's heartbeat, and until it exists the rest is a
museum after hours.

**Clark is peripheral to the flow he was meant to drive.** The orchestrator
runs with 27 tools, and the loop we built uses him for one button. Either he
gets a real job or he is an appendix. The real job is obvious and bounded:
**the night shift** — draft candidates from the day's new observations, submit
them through the factory with provenance links, and narrate the morning digest.
Proposing only, as always; the human wakes up to verdicts. That is also the
honest version of the qwen co-pilot ambition.

**Deployment has no approval card.** The trade seam is human-gated; promoting
a gate-passing candidate to deployed is still just an API call. Before
anything ever passes, promotion needs the same card the trades have —
otherwise the first pass becomes the first ungated action in the system.

---

## The one-sentence steer

Stop widening: no new surfaces, no new vendors, no new subsystems. The
architecture's risks are all of one kind — *duplication of ownership* (state,
types, fetching, endpoints) — and the cure is consolidation applied
incrementally, while the roadmap's Horizon 1 fixes what the numbers are
measured against.
