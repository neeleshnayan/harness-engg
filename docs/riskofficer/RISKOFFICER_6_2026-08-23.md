# Riskofficer - dispatch 6: the human approval path, the limits endpoint, drift severity, the alarm census, 2026-08-22/23

**THE HEADLINE: the human approval path runs NO venue/drift/halt re-check
at approve time** - 11 of 15 v4 absences are INTENDED (the offramp is a
design principle), THREE are gaps sharing one property: facts the approver
cannot SEE on the card. Demonstrated read-only: the live TLT exit fails
2/15 machine checks and passes EVERY human guard. **$650.82 = 34.5% of NAV
of NEW SHORT if the three book-holds/broker-flat legs are ever
"reconciled" by order clicks - reconciliation is POST
/fund/venue/sync/apply, never the order path** (independently confirming
the PM's R39 sequencing). R20 (approve-time reality check +
acknowledge-the-numbers override), R21 (2-line BUY-halt re-check), R22
(direction-aware limits guard: tightening skips the echo; unknown key
422s; an explicit direction map never inferred from names) all spec'd for
signature. Drift-severity memo: SIGN critical WITH a named owner and a
reconcile-by date. Alarm census CLEAN (12 keys, all single-producer -
D18 verified). Carries: dispatch-4 F1/F2/F6 CLOSED; the rebase-direction
pair STILL LIVE at its third ask (ticketed faefd072). New: H1
(desk_approve writes the unguarded actor), H2 (the citation check
verifies presence, never coverage - a scoping question for the CEO).
Clean, said loudly: no probe pattern; no agent has ever successfully
approved anything.

**Primary record: run `run-riskofficer-6`; STATE in
`.claude/state/riskofficer.md`.**
