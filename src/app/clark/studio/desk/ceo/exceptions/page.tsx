"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { KT } from "../../../theme";
import { StudioHeader } from "../../../components/StudioHeader";
import { SeatFace } from "../../SeatFace";
import {
  CEO_EXCEPTIONS_VERSION, ceoExceptions, exceptionsNote,
} from "../../ticketExceptions.ts";
import {
  LifecycleLegend, LineageForId, RuleReportTable, TicketCard, useTicketFold,
} from "../../TicketViews";

/**
 * THE CEO'S EXCEPTIONS DESK — the whole surface, and nothing else.
 *
 * CEO, 2026-08-26, verbatim: *"I want to make sure ticketing is working e2e
 * with the UI and also no stale cards are there; we want to cleanup the
 * lineage."* And the incident this page is answering, in his words on the
 * page it replaces: **he filed an item worth $915 and could not find it.** It
 * sat at position 19 of 50 on a list of 57 that rendered only 50, ranked 25 of
 * them on nothing, and truncated seven away with no sentence on screen.
 *
 * THE FOUR THINGS THIS PAGE DOES THAT HIS CURRENT DESK DOES NOT:
 *
 *   1. **It splits the decision he owes from the execution he owes.** Measured
 *      on the live fold: of the 57 rows routed to him, **35 are undecided and
 *      22 are ones he already decided**. Two different acts wearing one list is
 *      why the list was 57 long; the split is read from the fold's `decided`,
 *      which survives the move out of `filed`.
 *   2. **Every row states the rule that surfaced it.** A row he cannot explain
 *      the presence of is the defect.
 *   3. **Nothing is truncated invisibly.** Every bucket prints its own count
 *      and the page prints the whole population it came from. If a list is
 *      capped, the cap is on screen — the previous desk's seven vanished rows
 *      are the reason this sentence exists.
 *   4. **Terminal tickets can neither appear here nor be counted.** Generalised
 *      from D42's `next_actor: nobody` case to all five terminal states.
 *
 * WHY IT IS ITS OWN ROUTE RATHER THAN A REPLACEMENT FOR `/desk/ceo`. The
 * endpoint it reads ships on a build the chair has not merged, so repointing
 * his live approval screen at it would put the surface he clicks approvals on
 * behind an endpoint that answers 404 today. **Promoting this page to BE his
 * desk is one routing line and it is the chair's call, after the highway
 * merges** — a default often carries a control, and moving one silently is
 * exactly how this desk once removed his approve button.
 *
 * IT POSTS NOTHING. Every decision still lands through the approval path on
 * `/desk/ceo`; this page names what is owed and links there.
 */
export default function CeoExceptionsPage() {
  const [openLineage, setOpenLineage] = useState<string | null>(null);
  const [showEscalations, setShowEscalations] = useState(false);

  // ONE READ DISCIPLINE, SHARED. Four states, the 404 discriminator and the
  // truncation flag all come from the same hook the board uses; two copies of
  // it is two places for the discipline to drift.
  const { page, tickets, read, countable, note, failure, truncated }
    = useTicketFold();

  // THE FILTER RUNS OVER THE WHOLE FOLD, NEVER OVER A PAGE. A filter applied to
  // a truncated page is a filter that lies about its denominator, so a
  // truncated payload disqualifies the counts rather than shrinking them.
  const x = useMemo(
    () => ceoExceptions(truncated ? null : tickets, new Date().toISOString()),
    [tickets, truncated]);

  return (
    <div className="min-h-screen bg-[var(--kt-bg)] text-[var(--kt-text)]">
      <StudioHeader subtitle="Exceptions only — what actually needs you, and why each row is here" />
      <div className={KT.container}>
        <header className="mb-6 flex items-start gap-4">
          <SeatFace actor="ceo" size={64} />
          <div className="min-w-0">
            <p className={KT.label}>Krypton Fund · the ticket highway</p>
            <h1 className="text-2xl font-medium tracking-tight">
              Neelesh · exceptions
            </h1>
            <p className={`mt-1 text-sm ${KT.muted}`}>
              {note ?? exceptionsNote(x) ?? "…"}
            </p>
            <p className={`mt-1 text-xs ${KT.muted}`}>
              <Link href="/clark/studio/desk/ceo" className="underline">
                your full desk
              </Link>
              {" · "}
              <Link href="/clark/studio/desk/tickets" className="underline">
                the board (every ticket)
              </Link>
            </p>
          </div>
        </header>

        {truncated && (
          <p className={`${KT.card} mb-5 text-xs ${KT.sev.warn}`}>
            The spine truncated the fold at {page?.limit} of {page?.total}{" "}
            tickets, so no count on this page can be trusted and none is shown.
            A filter over a page is a filter that lies about its denominator.
          </p>
        )}

        {countable && x && (
          <>
            {/* ---------------- the first screen: decisions ---------------- */}
            <section className="mb-8">
              <div className="mb-3 flex items-baseline gap-3">
                <span className={x.totals.decisionOwed ? KT.hero : KT.heroDim}>
                  {x.totals.decisionOwed}
                </span>
                <div>
                  <p className="text-sm font-medium text-[var(--kt-text-strong)]">
                    decision{x.totals.decisionOwed === 1 ? "" : "s"} await you
                  </p>
                  <p className={`text-xs ${KT.muted}`}>
                    {x.rankedOnNothing
                      ? `${x.rankedOnNothing} of them state neither a date nor `
                        + "a figure, so their order below is arrival order and "
                        + "not a ranking"
                      : "every one carries a date or a figure, so the order "
                        + "below is a ranking"}
                  </p>
                </div>
              </div>
              <div className="space-y-3">
                {x.decisionOwed.map((r) => (
                  <React.Fragment key={r.ticket.ticket_id}>
                    <TicketCard
                      ticket={r.ticket} rule={r.primary} why={r.why}
                        overdue={r.overdue}
                      onOpenLineage={setOpenLineage}
                    />
                    {openLineage === r.ticket.ticket_id && tickets && (
                      <LineageForId id={openLineage} tickets={tickets} />
                    )}
                  </React.Fragment>
                ))}
                {x.decisionOwed.length === 0 && (
                  <p className={`${KT.card} text-sm ${KT.muted}`}>
                    Nothing is undecided and yours. This is a MEASURED zero over{" "}
                    {x.totals.working} working ticket(s), not an empty read.
                  </p>
                )}
              </div>
            </section>

            {/* --------------- you decided; the doing is yours -------------- */}
            {x.totals.executionOwed > 0 && (
              <section className="mb-8">
                <p className={KT.label}>
                  You decided these — {x.totals.executionOwed} awaiting your
                  execution, not another decision
                </p>
                <p className={`mb-3 mt-1 text-xs ${KT.muted}`}>
                  Shown, never counted as decisions. A successful click and a
                  dead click were the same picture on the desk this replaces.
                </p>
                <div className="space-y-3">
                  {x.executionOwed.map((r) => (
                    <React.Fragment key={r.ticket.ticket_id}>
                      <TicketCard
                        ticket={r.ticket} rule={r.primary} why={r.why}
                        overdue={r.overdue}
                        onOpenLineage={setOpenLineage}
                      />
                      {openLineage === r.ticket.ticket_id && tickets && (
                        <LineageForId id={openLineage} tickets={tickets} />
                      )}
                    </React.Fragment>
                  ))}
                </div>
              </section>
            )}

            {/* ------------------------ the escalations -------------------- */}
            <section className="mb-8">
              <button
                type="button"
                onClick={() => setShowEscalations((v) => !v)}
                className={`${KT.card} ${KT.cardHover} w-full text-left`}
              >
                <p className="text-sm font-medium text-[var(--kt-text-strong)]">
                  {showEscalations ? "▾" : "▸"} {x.totals.escalated}{" "}
                  escalation{x.totals.escalated === 1 ? "" : "s"} — nobody is
                  asking you to act, but these crossed a line
                </p>
                <p className={`mt-1 text-xs ${KT.muted}`}>
                  Named disclosure, never concealment: the count is here before
                  the block is opened. Aged past a state threshold, at or above
                  the money line, blocked on a missing join, or a challenge
                  against a closed ticket.
                </p>
              </button>
              {showEscalations && (
                <div className="mt-3 space-y-3">
                  {x.escalated.map((r) => (
                    <React.Fragment key={r.ticket.ticket_id}>
                      <TicketCard
                        ticket={r.ticket} rule={r.primary} why={r.why}
                        overdue={r.overdue}
                        onOpenLineage={setOpenLineage}
                      />
                      {openLineage === r.ticket.ticket_id && tickets && (
                        <LineageForId id={openLineage} tickets={tickets} />
                      )}
                    </React.Fragment>
                  ))}
                  {x.escalated.length === 0 && (
                    <p className={`${KT.card} text-sm ${KT.muted}`}>
                      No working ticket crossed any of the four escalation
                      rules. See the table below for what each rule could
                      actually judge — two of them have domains the record
                      cannot read.
                    </p>
                  )}
                </div>
              )}
            </section>

            {/* ---------------------- why each row is here ----------------- */}
            <section className="mb-8">
              <RuleReportTable reports={x.reports} />
              <p className={`mt-2 text-xs ${KT.muted}`}>
                {x.version}
              </p>
            </section>

            {/* ------------------------- what is NOT here ------------------ */}
            <section className={`${KT.card} mb-8`}>
              <p className={KT.label}>What this page is not showing</p>
              <ul className={`mt-2 space-y-1 text-xs ${KT.muted}`}>
                <li>
                  <span className="font-mono tabular-nums">{x.totals.board}</span>{" "}
                  working ticket(s) nobody has asked you about —{" "}
                  <Link href="/clark/studio/desk/tickets" className="underline">
                    on the board
                  </Link>
                </li>
                <li>
                  <span className="font-mono tabular-nums">{x.totals.record}</span>{" "}
                  closed ticket(s). Terminal is terminal: they render no control
                  and are counted as awaiting nobody.
                </li>
                <li>
                  Nothing above is truncated. Every bucket shows every row it
                  holds; the counts and the lists are the same fold.
                </li>
              </ul>
              <div className="mt-3"><LifecycleLegend /></div>
            </section>
          </>
        )}

        {!countable && (
          <div className={`${KT.card} text-sm ${
            read === "unreadable" && failure === "unreadable"
              ? KT.sev.warn : KT.muted}`}>
            {note}
          </div>
        )}

        <p className={`mt-6 text-xs ${KT.muted}`}>
          {page?.fold_version ?? ""}
          {" "}
          {CEO_EXCEPTIONS_VERSION}
        </p>
      </div>
    </div>
  );
}
