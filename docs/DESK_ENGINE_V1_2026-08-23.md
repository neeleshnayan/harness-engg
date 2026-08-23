# THE DESK ENGINE v1 — the CEO's desk as a self-maintaining instrument
**Consolidated spec, 2026-08-23, from six CEO instructions given in one
sitting. Supersedes-and-absorbs tickets 26533b0f (three-tier desk),
762d28c9 (supersession lineage), cec27460 (greetings). Companion to the
DELEGATION REGISTER proposal (4c9317ad, adversary-blind first). The CEO's
verbatim instructions are the requirements:**

1. *"my desk is more cluttered than before... Why is everything hitting my desk?"*
2. *"the agents dont get access to me directly, it makes me a bottleneck
   for a team running 24x7; I want a better routing and approval mechanism"*
3. *"COO reaches to me directly with you in CC"* (kills triple-processing)
4. *"team members should be able to directly add tasks to other desks
   which gets bundled in their next run; blessed by you"*
5. *"where supersed happens; this r37 withdraw and r39 acceptance fills
   the same pattern"*
6. *"we need a mechanism so the desk is structured and maintained
   automatically without you handholding every clean and message pass"*

## The architecture, one paragraph

Every seat gets an IN-TRAY; the CEO gets a DESK that shows only his
decision surface plus a BRIEFINGS shelf; everything else lives on the
FLOOR. Routing is mandatory at filing and defaults to the chair. Hygiene
runs as a deterministic, versioned policy in the spine — the autopolicy
pattern applied to bookkeeping — so the desk maintains itself and the
chair stops being the janitor.

## The components

### 1. ROUTING AT BIRTH (kills the default-to-CEO flood)
- Every filed recommendation/request REQUIRES `next_actor`, `due_date`
  (nullable), `reversibility`, `money_at_stake` — 422 without them (the
  Stan R39 standard, enforced by schema, not chair diligence).
- **The default flips**: `next_actor` unset is INVALID; "undecided"
  routes to `chair`, never to `ceo`. Measured basis: 54 of 91 CEO-routed
  rows arrived by default (triage #7).
- The CEO's desk view = rows where `next_actor == ceo` AND status open,
  ranked by due_date then money. Target steady state: single digits.

### 2. THE BRIEFINGS SHELF (seat memos reach the CEO directly)
- Donna's archives, COO triages, Grace's ledgers auto-publish to the
  shelf at filing, stamped `chair-unverified` until the chair's parallel
  verification flips the badge. The chair is CC, never relay. A
  discrepancy found post-publication gets a visible correction chip —
  never a silent edit (findings-doc rules apply).

### 3. SEAT IN-TRAYS + THE BLESSING (instruction 4)
- Any seat may post a task to any seat's in-tray (`POST
  /fund/desk/intray/{seat}`); it is an ASK, never a trigger (ignition
  stays human, unchanged).
- At the target seat's next dispatch the chair DRAINS the in-tray into
  the brief — the blessing: strike-with-reason anything the chair
  disagrees with, exactly the BINDS pattern applied to tasks. Struck
  items return to the sender's next brief with the reason.
- The CEO's desk never sees seat-to-seat traffic.

### 4. SUPERSESSION AS CODE (instruction 5; R37/R39 is the type specimen)
- `supersedes` edge on desk rows; a superseding row auto-applies a chip
  to its target: SUPERSEDED-PENDING (premise dies at a named future
  event, revival branch preserved) or SUPERSEDED (dead now, lineage
  shown). A superseded row CANNOT be approved — the button is disabled
  with the lineage rendered. KILLED rows leave the desk for the floor's
  kill shelf.
- Seats retire their own superseded rows in the same memo (the Stan
  BIND); the engine enforces what the discipline requests.

### 5. AUTO-HYGIENE — deterministic, versioned, audited (instruction 6)
The autopolicy pattern for bookkeeping. Rules v1, ALL evidence-joins,
zero judgment:
- A blind-review request whose verdict run has resolved → auto-close
  with the verdict citation. (Measured leak: two delivered verdicts sat
  open; the queue "does not close on a verdict.")
- An approved request whose dispatch resolved → auto-mark done with the
  run id. (Measured: ≥4 of 37 "backlog" rows were merged work.)
- A rec citing a commit that is an ancestor of HEAD → auto-flag
  PROBABLY-DISCHARGED for one-click chair confirm (flag, not close —
  prose matching is not an evidence join).
- Fuzzy/judgment closes remain chair acts, logged. The hygiene policy is
  VERSIONED with a written reason per rule change; the riskofficer
  audits its closes exactly as it audits auto-approvals.
- The counter reads post-hygiene state, so Donna's friction trend and
  the COO trigger measure decisions, not bookkeeping.

### 6. GREETINGS (cec27460, absorbed)
Each desk view opens with an executive greeting: what changed since your
last visit, what needs you, what is on fire — generated from the same
folds, not hand-written.

## What this does NOT change (stated so nobody wonders)
The CEO's authority (click count falls, authority never); ignition keys
(a posted task fills an in-tray and never fires a seat); the guarded
approval path (auto-hygiene closes bookkeeping, never approves anything);
blind review; every non-negotiable. The DELEGATION REGISTER (which lets
categories of decisions execute without the CEO's per-item click) is
SEPARATE, a loosening, and goes adversary-blind before ratification.

## Sequencing
Next builder slot (CEO priority, this sitting). Write scope:
`app/fund/desk.py` + new intray/hygiene modules + `app/api/v1/fund.py`
desk routes + KryptonPay desk views. The hygiene rules and routing
schema are work-layer; the delegation register is governance and ships
separately after its blind.

## Falsifier at birth
If after one week the CEO's desk still exceeds ~15 rows at steady state,
or the chair is still running manual sweep passes, the engine has failed
its one job and gets redesigned rather than patched.
