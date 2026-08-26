"use client";

/**
 * THE TICKET SURFACES' SHARED RENDERING — one card, one lineage block, one
 * read-state banner, so three pages cannot phrase the same absence three ways.
 *
 * Every judgement here is imported, never re-derived: `ticketCardState` decides
 * whether a control exists, `ticketExceptions` decides which rule surfaced a
 * row, `ticketLineage` decides why a link is missing. This file only draws.
 * That separation is not tidiness — it is the reason the contract file can pin
 * the rendering at all, and it is why three of the four surfaces that once
 * answered "is this row finished" got different answers.
 */

import React from "react";
import Link from "next/link";
import { fundApiClient, type Ticket, type TicketPage } from "@/lib/fund_api";
import { KT } from "../theme";
import { money } from "../format";
import {
  RULE_LABEL, type ExceptionRow, type RuleReport,
} from "./ticketExceptions.ts";
import {
  STATE_LABEL, TERMINAL_STATES, WORKING_STATES, type TicketCardState,
  ticketCardState,
} from "./ticketCard.ts";
import {
  LINK_SENTENCE, type TicketLineage, lineageFor, ticketIndex,
} from "./ticketLineage.ts";
import { readState, type DeskRead } from "./deskRead.ts";
import {
  ticketFailureKind, ticketReadNote, ticketsCountable,
  type TicketReadFailure,
} from "./ticketRead.ts";

/* --------------------------------------------------------------- the read -- */

/** How often a ticket surface re-asks. Named because two pages used to spell
 *  it, and a poll interval written twice drifts silently. */
export const TICKET_POLL_MS = 20000;

export interface TicketFold {
  page: TicketPage | null;
  tickets: Ticket[] | null;
  read: DeskRead;
  /** Whether this surface may print a number at all. */
  countable: boolean;
  /** The sentence to show instead of numbers, or null when the read is good. */
  note: string | null;
  failure: TicketReadFailure;
  /** The spine capped the fold. No count over it can be trusted. */
  truncated: boolean;
}

/**
 * Read the ticket fold, with all four read states, once for every surface.
 *
 * EXTRACTED AT THE LATE READ-THROUGH. Both ticket pages carried a
 * byte-for-byte copy of this block — four pieces of state, the fetch, the
 * interval, and the three derivations. Two copies of a read discipline is two
 * places for it to diverge, and the discipline is the whole point of the
 * module it calls.
 *
 * THE PAYLOAD IS CLEARED ON FAILURE, deliberately: a decision list is exactly
 * the thing a reader acts on without noticing a banner, so a surface must
 * never show a stale fold beside a failure sentence.
 */
export function useTicketFold(): TicketFold {
  const [page, setPage] = React.useState<TicketPage | null>(null);
  const [failed, setFailed] = React.useState(false);
  const [failure, setFailure] =
    React.useState<TicketReadFailure>("unreadable");
  const [reason, setReason] = React.useState<unknown>(null);

  const load = React.useCallback(async () => {
    try {
      setPage(await fundApiClient.getTickets({ limit: 5000 }));
      setFailed(false);
    } catch (e) {
      setPage(null);
      setFailed(true);
      setFailure(ticketFailureKind(e));
      setReason(e);
    }
  }, []);

  React.useEffect(() => {
    load();
    const t = setInterval(load, TICKET_POLL_MS);
    return () => clearInterval(t);
  }, [load]);

  const read = readState(page !== null, failed);
  return {
    page,
    tickets: page?.tickets ?? null,
    read,
    countable: ticketsCountable(read),
    note: ticketReadNote(read, failure, reason),
    failure,
    truncated: page?.truncated === true,
  };
}

/* ------------------------------------------------------------- the lamps --- */

const LAMP_TONE: Record<TicketCardState["lamp"], string> = {
  working: "bg-[var(--kt-accent)]",
  "awaiting-review": "bg-[var(--kt-warn)]",
  idle: "bg-[var(--kt-border-strong)]",
  record: "bg-transparent border border-[var(--kt-border)]",
};

const LAMP_TITLE: Record<TicketCardState["lamp"], string> = {
  working: "in flight — a seat is running",
  "awaiting-review": "returned — the chair owes a review",
  idle: "not running",
  record: "closed — nothing is owed",
};

export function TicketLamp({ lamp }: { lamp: TicketCardState["lamp"] }) {
  return (
    <span
      title={LAMP_TITLE[lamp]}
      className={`inline-block h-2 w-2 shrink-0 rounded-full ${LAMP_TONE[lamp]}`}
    />
  );
}

/* -------------------------------------------------------------- the card --- */

/**
 * One ticket, drawn.
 *
 * THE CONTROL SLOT IS ALWAYS RENDERED, and when there is no control it holds
 * the SENTENCE saying why. A row that simply lost its buttons is
 * indistinguishable from a row whose buttons failed to render, and the CEO has
 * already seen the second wearing the first's clothes.
 *
 * NO SURFACE HERE POSTS ANYTHING. Every decision still lands through the
 * existing approval path on the CEO's own desk; this view names the control
 * that is owed and links to where it lives. The highway's transition door is
 * on the approval channel and a read-only board is not the place to open it.
 */
export function TicketCard({ ticket, rule, why, overdue, onOpenLineage }: {
  ticket: Ticket;
  rule?: ExceptionRow["primary"];
  why?: string;
  overdue?: boolean;
  onOpenLineage?: (id: string) => void;
}) {
  const c = ticketCardState(ticket);
  return (
    <article className={`${KT.card} ${KT.cardHover}`}>
      <div className="flex items-start gap-3">
        <span className="mt-1.5"><TicketLamp lamp={c.lamp} /></span>
        <div className="min-w-0 flex-1">
          <p className="text-[15px] leading-snug text-[var(--kt-text-strong)]">
            {c.title.absent
              ? <span className={KT.sev.warn}>this ticket stores no subject</span>
              : c.title.line}
          </p>
          {c.title.looksUnreadable && (
            /* The row IS broken and the reader should see that it is. Seven of
               the 713 live tickets store a serialised payload here. */
            <p className={`mt-1 text-xs ${KT.sev.warn}`}>
              the stored subject is a serialised payload, not a sentence
            </p>
          )}
          <p className={`mt-1.5 text-xs ${KT.muted}`}>
            <span className="font-mono">{ticket.type}</span>
            {" · "}{c.stateLabel}
            {" · "}
            {c.ageKnown
              ? `${(c.ageInStateHours ?? 0).toFixed(0)}h in state`
              : <span className={KT.sev.warn}>age UNKNOWN — the fold could
                  not read the instants</span>}
            {typeof ticket.money_at_stake === "number"
              && Number.isFinite(ticket.money_at_stake)
              && ticket.money_at_stake > 0
              ? ` · ${money(ticket.money_at_stake)} at stake` : ""}
            {ticket.due_date
              ? (overdue
                /* THE ONE CONDITION THAT IS TRUE WHETHER OR NOT ANYBODY
                   CLICKS, and the only thing on this card that spends a
                   colour. The look-pass caught its absence: the first three
                   rendered rows were all due 2026-08-24, read on 2026-08-26,
                   and the card said "due 2026-08-24" in the same muted tone as
                   everything else. */
                ? <span className={KT.sev.warn}> · OVERDUE — due {ticket.due_date}</span>
                : ` · due ${ticket.due_date}`)
              : ""}
          </p>

          {rule && (
            <p className={`mt-2 text-xs ${KT.muted}`}>
              <span className="rounded-full border border-[var(--kt-border)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider">
                {RULE_LABEL[rule]}
              </span>
              {why ? <span className="ml-2">{why}</span> : null}
            </p>
          )}

          {/* THE CONTROL SLOT. Never empty. */}
          <div className="mt-3 border-t border-[var(--kt-border)] pt-3">
            {c.controls === "none" ? (
              <p className={`text-xs ${KT.muted}`}>{c.controlsWhy}</p>
            ) : (
              <p className="text-xs">
                <span className="font-medium text-[var(--kt-text-strong)]">
                  {c.controls === "decide"
                    ? "A decision is owed" : "An execution is owed"}
                </span>
                {/* THE SAME SENTENCE, ONCE. The rule chip above already prints
                    the row's reason, and on a `your_move` row the two are the
                    SAME STRING — the rendered page carried "the row states its
                    next actor is the ceo" twice on every one of 57 cards.
                    Found by looking; no test could see it, because both halves
                    were individually correct. */}
                {c.controlsWhy !== why && (
                  <span className={`ml-1 ${KT.muted}`}>— {c.controlsWhy}</span>
                )}
                {" "}
                <Link href="/clark/studio/desk/ceo" className="underline">
                  open it on your desk
                </Link>
              </p>
            )}
            {c.citationOwed && (
              <p className={`mt-1 text-xs ${KT.sev.warn}`}>
                closed with NO citation — the design makes one mandatory for a
                close, so this row is a bookkeeping gap, not a completed one
              </p>
            )}
          </div>

          <p className={`mt-2 font-mono text-[10px] ${KT.muted}`}>
            {ticket.ticket_id}
            {onOpenLineage && (
              <button
                type="button"
                onClick={() => onOpenLineage(ticket.ticket_id)}
                className="ml-2 underline"
              >
                lineage
              </button>
            )}
          </p>
        </div>
      </div>
    </article>
  );
}

/* ----------------------------------------------------------- the lineage --- */

function LineageRow({ t }: { t: Ticket }) {
  const c = ticketCardState(t);
  return (
    <li className="flex items-start gap-2 py-1">
      <span className="mt-1.5"><TicketLamp lamp={c.lamp} /></span>
      <span className="min-w-0">
        <span className="text-[13px]">{c.title.line || "(no subject)"}</span>
        <span className={`ml-2 font-mono text-[10px] ${KT.muted}`}>
          {t.type} · {t.state} · {t.ticket_id}
        </span>
      </span>
    </li>
  );
}

/**
 * The chain behind one ticket, with the absence stated rather than drawn as a
 * gap.
 *
 * THE FENCE GETS ITS OWN SENTENCE AND ITS OWN TONE. 443 of 713 rows are
 * pre-highway; a chain that drew them as "no lineage" would tell the reader the
 * bookkeeping is clean where in truth it is unreadable.
 */
/** Internal: `LineageForId` is the only caller and the only export. An
 *  exported component with no external consumer reads, from outside, like a
 *  second entry point that must be kept working. */
function TicketLineageView({ lineage }: { lineage: TicketLineage }) {
  const l = lineage;
  const fenced = l.parent.state === "fenced";
  return (
    <div className={`${KT.card} mt-3`}>
      <p className={KT.label}>Lineage</p>

      <div className="mt-3">
        <p className={`text-xs ${fenced || l.parent.state === "dangling"
          ? KT.sev.warn : KT.muted}`}>
          Parent: {l.parent.sentence}
          {l.parent.namedId
            ? <span className="ml-1 font-mono">{l.parent.namedId}</span> : null}
          {l.parent.basis
            ? <span className="ml-1">(basis: {l.parent.basis})</span> : null}
        </p>
      </div>

      {l.ancestors.length > 0 && (
        <div className="mt-3">
          <p className={KT.label}>Up the chain ({l.ancestors.length})</p>
          <ol className="mt-1">
            {l.ancestors.map((t) => <LineageRow key={t.ticket_id} t={t} />)}
          </ol>
          {l.truncated && (
            <p className={`mt-1 text-xs ${KT.sev.warn}`}>
              the walk stopped early — the chain either loops or is deeper than
              the walk allows; what is shown is a PREFIX, not the whole chain
            </p>
          )}
        </div>
      )}

      <div className="mt-3">
        <p className={KT.label}>Children ({l.children.length})</p>
        {l.children.length
          ? <ol className="mt-1">
              {l.children.map((t) => <LineageRow key={t.ticket_id} t={t} />)}
            </ol>
          : <p className={`mt-1 text-xs ${KT.muted}`}>
              no ticket names this one as its parent
              {fenced ? " — and this row is inside the pre-highway fence, so "
                + "that is not evidence of anything" : ""}
            </p>}
      </div>

      <div className="mt-3">
        <p className={KT.label}>
          Same trace ({l.traceCohort.length})
        </p>
        {l.traceId
          ? (l.traceCohort.length
            ? <ol className="mt-1">
                {l.traceCohort.map((t) => <LineageRow key={t.ticket_id} t={t} />)}
              </ol>
            : <p className={`mt-1 text-xs ${KT.muted}`}>
                nothing else rides trace <span className="font-mono">{l.traceId}</span>
              </p>)
          : <p className={`mt-1 text-xs ${KT.muted}`}>
              this ticket carries no trace id, so the cohort is UNKNOWN rather
              than empty
            </p>}
      </div>

      {l.canonical && (
        <p className={`mt-3 text-xs ${KT.sev.warn}`}>
          The canonical decision lives on another ticket:{" "}
          <span className="font-mono">{l.canonical.namedId}</span> —{" "}
          {l.canonical.sentence}
        </p>
      )}

      <div className="mt-3">
        <p className={KT.label}>History ({l.transitions.length})</p>
        <ol className={`mt-1 space-y-0.5 text-xs ${KT.muted}`}>
          {l.transitions.map((tr, i) => (
            <li key={i} className="font-mono">
              {tr.from ?? "—"} → {tr.to} · {tr.at ?? "instant UNKNOWN"} ·{" "}
              {tr.actor ?? "actor unknown"} · {tr.basis ?? "basis unknown"}
            </li>
          ))}
        </ol>
        {l.refused.length > 0 && (
          /* KEPT, NEVER DROPPED. "This never happened" and "this was attempted
             and correctly refused" are different facts, and the second is the
             one that says a guard did its job. */
          <>
            <p className={`${KT.label} mt-3`}>
              Refused by terminal precedence ({l.refused.length})
            </p>
            <ol className={`mt-1 space-y-0.5 text-xs ${KT.sev.warn}`}>
              {l.refused.map((tr, i) => (
                <li key={i} className="font-mono">
                  {tr.from ?? "—"} → {tr.to} · {tr.actor ?? "actor unknown"}
                  {tr.why ? ` · ${tr.why}` : ""}
                </li>
              ))}
            </ol>
          </>
        )}
      </div>
    </div>
  );
}

/** The lineage block for one id, resolved against a population. Renders the
 *  unknown-anchor case rather than an empty chain. */
export function LineageForId({ id, tickets }: {
  id: string; tickets: readonly Ticket[];
}) {
  const idx = React.useMemo(() => ticketIndex(tickets), [tickets]);
  const l = React.useMemo(() => lineageFor(id, tickets, idx), [id, tickets, idx]);
  if (!l) {
    return (
      <div className={`${KT.card} mt-3`}>
        <p className={`text-xs ${KT.sev.warn}`}>
          No ticket with id <span className="font-mono">{id}</span> is in this
          fold. That is an UNKNOWN ticket, not an empty lineage — the fold may
          be filtered, or the id may name nothing.
        </p>
      </div>
    );
  }
  return <TicketLineageView lineage={l} />;
}

/* ------------------------------------------------------- the rule reports -- */

/** Each rule's own three numbers. A "0 caught" with no domain beside it is a
 *  vacuous result and this table is what stops one being printed. */
export function RuleReportTable({ reports }: { reports: RuleReport[] }) {
  return (
    <div className={KT.card}>
      <p className={KT.label}>Why each row is here — the five rules</p>
      <table className="mt-3 w-full text-xs">
        <thead>
          <tr className={KT.muted}>
            <th className="pb-1 text-left font-normal">rule</th>
            <th className="pb-1 text-right font-normal">caught</th>
            <th className="pb-1 text-right font-normal">could judge</th>
            <th className="pb-1 text-right font-normal">unknown</th>
            <th className="pb-1 text-right font-normal">domain</th>
          </tr>
        </thead>
        <tbody>
          {reports.map((r) => (
            <tr key={r.rule} className="border-t border-[var(--kt-border)]">
              <td className="py-1.5 pr-2 align-top">
                <span className="font-medium text-[var(--kt-text-strong)]">
                  {RULE_LABEL[r.rule]}
                </span>
                <span className={`block ${KT.muted}`}>{r.note}</span>
              </td>
              <td className="py-1.5 text-right align-top font-mono tabular-nums">
                {r.caught}
              </td>
              <td className="py-1.5 text-right align-top font-mono tabular-nums">
                {r.evaluable}
              </td>
              <td className={`py-1.5 text-right align-top font-mono tabular-nums ${
                r.unknown ? KT.sev.warn : KT.muted}`}>
                {r.unknown}
              </td>
              <td className="py-1.5 text-right align-top font-mono tabular-nums">
                {r.domain}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* --------------------------------------------------------- the state map --- */

/** The lifecycle, rendered as a legend, so a reader can see the five terminal
 *  states are terminal rather than infer it from rows that happen to be quiet. */
export function LifecycleLegend() {
  return (
    <p className={`text-xs ${KT.muted}`}>
      <span className="font-medium">Working:</span>{" "}
      {/* THE VOCABULARY IS READ, NOT RETYPED. The read-through found this
          list written out THREE times — here, in the board's census grid, and
          in `ticketCard.ts` where the named constant already lived with zero
          production consumers. A copy that happens to agree today is exactly
          what a MOVE test cannot distinguish from a read, so the copies are
          gone and the constant is what renders. */}
      {WORKING_STATES.map((s) => STATE_LABEL[s]).join(" · ")}
      {" — "}
      <span className="font-medium">Terminal:</span>{" "}
      {TERMINAL_STATES.map((s) => STATE_LABEL[s]).join(" · ")}
      {". "}
      Terminal is terminal: there is no reopen transition, and a dispute with a
      closed ticket is a new challenge ticket.
    </p>
  );
}
