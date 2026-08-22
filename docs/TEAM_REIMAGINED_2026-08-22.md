# THE REIMAGINED TEAM — design and implementation record

**2026-08-22. CEO instruction, verbatim: *"What I need to discuss with you is
how we restructure and rebuild our team to truly represent an agentic hedge
fund of the future; thats is not clogged by the thought of how human teams
have traditionally operated... our team needs to become a self evolving
harness that cordially works as one team and one goal"* — and, after the
design conversation: *"Perfect and I need you to go ahead and implement a new
reimagined team over the night."***

**Implemented by the CTO chair (Fable) overnight 2026-08-22, with the CEO's
pre-authorization given awake. The executive table (Grace on the date axis,
Vishesh on the reversibility axis) reviews this implementation in their next
dispatches — review AFTER implementation was the CEO's sequencing call, made
deliberately. Anything here is one revert away; that is why it was safe to
build overnight.**

---

## 1. The organizing insight

We have been unbundling the human hedge fund since the firm was founded,
without naming it. The redesign names it: **for each inherited structure, ask
whether it was load-bearing for JUDGMENT or merely an accommodation to human
limits.** Discard the accommodations. Keep — and sharpen — the judgment
structures, because they were never really about humans.

| inherited structure | verdict | why |
|---|---|---|
| Role as skill-container | **DISCARD** | Every seat runs the same model. A seat that exists to divide labor is furniture. |
| Role as judgment-separator | **KEEP, and name it as the ONLY reason a standing seat exists** | The adversary's value is not knowing the author's reasoning. The validator's value is distrusting our instruments. Nearly every real finding this firm has made came from these boundaries. |
| Hierarchy as coordination bandwidth | **DISCARD** | Measured cost: 115 items naming the chair, the firm serializing through one message bus. Replaced by THE WIRE — a routed graph with human ignition keys. |
| Serialization as safety | **DISCARD** | We serialize only where the five-part dependency check demands it. |
| Separation of duties (author ≠ reviewer ≠ approver), pre-registration, audit trail, the human click on money | **KEEP UNCHANGED** | Not human tradition — error-correction design. Mistakes and incentive problems exist regardless of substrate. |
| Social cohesion managed as a resource | **DISCARD — and this is the deepest one** | Agents can hold total goal-alignment WITH total judgment-independence. Human teams cannot separate the two, so their disagreement is friction. Ours is the product. "Cordially one team" costs us nothing; what needs active defense is the OPPOSITE failure: absorption. |

## 2. The two layers — the rule that makes self-evolution safe to want

**THE WORK LAYER evolves; THE CONTROL LAYER versions.**

- **WORK**: seat definitions, briefs, propagation protocols (STATE/BINDS/
  EVOLVE), allocation, memory files, the wire's routing table contents.
  Changes here are proposals reviewed by the chair, applied same-day,
  reversible by one commit.
- **CONTROL**: the approval guard, the autopolicy envelope, the gate and its
  thresholds, risk limits, exit-rule mechanics, the event store, the CEO's
  click, the ignition keys. Changes here happen ONLY by versioned,
  human-decided change with a written reason — exactly as the non-negotiables
  already require. **The self-evolving machinery may not touch this layer,
  may not propose to touch it quietly, and a proposal that would touch it
  routes like any loosening: adversary first, CEO always.**

A self-evolving system's native failure mode is quiet self-loosening. The
firm's oldest rule already forbids quiet loosening; this extends it to the
evolution mechanism itself, at birth rather than after an incident.

## 3. The seat model, restated

1. **A STANDING seat exists to hold one of three things: an independent
   judgment boundary, an accountability surface (memory + auditability), or a
   write permission.** Not a workload. Current roster maps cleanly:
   adversary/validator/riskofficer hold judgment boundaries; every seat holds
   an accountability surface; builder and quant hold the two pens.
2. **TRANSIENT FAN-OUT under a standing seat's name.** When a seat's task
   needs breadth — thirty parallel readers, a sweep, a census — the chair may
   fan out transient workers UNDER that seat's identity and accountability.
   The standing seat's memory receives the consolidated STATE; the transient
   workers have none. Human firms cannot hire thirty analysts for one
   afternoon; we can, and the accountability surface stays singular.
3. **Labor moves freely; boundaries do not.** Work may be re-lanes between
   seats by the chair without ceremony. The blind-review boundary, the
   never-downgrade rule on the adversary and the approval chain, and the
   author ≠ reviewer ≠ approver separation move never.

## 4. The nervous system: STATE → BINDS → EVOLVE

The seat protocol gains its third section, completing the loop:

- **`## STATE`** — what the seat learned, for its own future self. (Existing.)
- **`## BINDS`** — lessons carried to OTHER seats, written as instructions to
  them, chair-reviewed at resolve. (Existing.)
- **`## EVOLVE`** (NEW) — a seat may propose amendments **to its own seat
  file**, as concrete before/after text, grounded in a measured outcome from
  its own runs. The chair reviews at resolve exactly like BINDS: strike what
  it does not accept, apply the rest, commit with the seat's reasoning named.
  A seat may also propose an amendment to ANOTHER seat's file — that routes
  through the chair with one extra requirement: the receiving seat sees the
  proposal in its next brief and may answer before it is applied.

**The bar for an EVOLVE is the challenge bar: a measured outcome or a
demonstrated consequence, never taste.** "My brief keeps asking me for X and
X has been dead three dispatches" qualifies. "I would phrase my mandate
differently" does not.

## 5. The selection loop — the retrospective organ

**The firm's genome is its artifacts** — seat files, briefs, protocols, the
constitution. Sessions are ephemeral; the artifacts are the organism. What was
missing is selection: nothing ever read the record and asked what worked.

The organ, specified:

- **Input**: the decision log — runs (49 lifetime and counting),
  recommendations with dispositions, desk requests with response ages,
  BINDS-carried-vs-dropped, the friction ledger once Donna runs it, and the
  D5 fields (dispatched_at, failure runs) once they land.
- **The questions, per cycle**: which briefs produced verdicts that SURVIVED
  downstream review; which seat-file amendments changed measured outcomes;
  which lessons were carried and then paid; where did two seats re-derive the
  same finding (a propagation failure); which recommendations aged without an
  answer; what got built and never consulted.
- **Output**: proposed amendments to WORK-layer artifacts, as reviewable
  diffs, filed through the ordinary desk path. **Machine-generated proposals,
  human-gated selection. Nothing auto-applies. Ever.**
- **Cadence**: weekly, or on the chair's trigger. It is a dispatch like any
  other — no self-starting.
- **Who runs it**: seeded as a joint Grace-question (she declared "test
  whether the decision log is a usable dataset" as her next dispatch) with
  Donna's friction ledger as an input. If the organ proves out, whether it
  earns its own seat is decided by demonstrated need, like every seat before
  it.

**THE IMMUNE-SYSTEM EXCLUSION (default pending the CEO's explicit
ratification): the selection loop may not propose amendments to the ADVERSARY
seat.** The immune system does not get to edit itself, and nothing that
reviews the firm's work may be reshaped by the thing it reviews. The CEO was
asked to sleep on whose seat is beyond the loop's reach; the adversary is the
chair's conservative default, applied tonight, reversible by one word from
him.

## 6. What did NOT change, listed so nobody has to wonder

- **No seat gained a trigger.** Ignition keys stay human. A posting fills an
  in-tray; it never fires a seat (the wire's pinned boundary, CEO-confirmed).
- **Every non-negotiable stands.** NAV folds from the event log; absence is
  never zero; thresholds move only by versioned change; findings docs are
  never edited; the clean-field rule; quiet loosening remains the one
  forbidden move.
- **The chain of a candidate is untouched**: mechanism proposes → adversary
  attacks → CTO verifies → belt → gate → the CEO clicks.
- **The CEO's click count can only go down, never his authority** — Grace's
  bar, now everyone's.
- **The executive table's discipline** (own ranking first, then differ) is
  unchanged and is the antibody this design leans on hardest.

## 7. Implementation manifest (what the night actually ships)

1. This document.
2. A dated constitution section: THE REIMAGINED TEAM — the two layers, the
   seat model, EVOLVE, the selection loop's charter, the immune-system
   exclusion.
3. Every seat file gains a uniform **ONE TEAM, ONE GOAL** section: the north
   star restated, the EVOLVE protocol, and that seat's **fitness question** —
   the one measured thing that says whether the seat is earning its tokens
   (e.g. adversary: kills that were RIGHT, and survives that were RIGHT —
   both directions score; mechanism: candidates reaching the belt; pm:
   decisions the CEO could take in one read).
4. The retrospective organ's first run, as a Grace dispatch input — her v0.2.
5. The wire (already filed: `572261e6`, `384a4bfd`) proceeds as the transport
   this design assumes.
6. Vishesh's triage #5 reviews the whole implementation on the reversibility
   axis, with standing to object to any of it.

**Review clause**: this design is provisional like every decision here. Its
falsifier, written at birth: if after two weeks the selection loop has
produced no amendment that survived chair review AND seat review, the loop is
theatre and gets dismantled — the seats and the two-layer rule stand on their
own.
