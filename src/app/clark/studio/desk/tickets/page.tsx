"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import type { Ticket, TicketState } from "@/lib/fund_api";
import { KT } from "../../theme";
import { StudioHeader } from "../../components/StudioHeader";
import { SeatFace } from "../SeatFace";
import {
  STATE_LABEL, WORKING_STATES, isTerminal, listCap,
} from "../ticketCard.ts";
import { allTrays, chairQueue, type SeatTray } from "../ticketTrays.ts";
import { lineageCoverage } from "../ticketLineage.ts";
import {
  LifecycleLegend, LineageForId, TicketCard, TicketLamp, useTicketFold,
} from "../TicketViews";

/**
 * THE BOARD — every ticket, the per-seat trays, and the lineage walk.
 *
 * This is the surface the design's Part 3 calls *"the on-demand board he visits
 * by choice"*, plus the per-desk views: an in-tray per seat (approved and
 * undispatched, plus unconsumed lessons) and an out-tray (returned work the
 * chair owes a review on). Both are QUERIES over one fold — the design's "no
 * per-view state" clause, which is what makes a tray unable to go stale
 * relative to the record it draws.
 *
 * THREE NUMBERS ON THIS PAGE ARE HONEST ZEROES WITH THEIR DOMAINS BESIDE THEM,
 * measured 2026-08-26 on 713 live tickets, and every one of them would be a lie
 * without the sentence next to it:
 *
 *   - **0 returned tickets.** The state was born two days ago and no door has
 *     been used. Every out-tray is empty and none of them is good news.
 *   - **0 lesson tickets.** The type exists; BINDS are still carried by hand.
 *   - **443 of 713 rows are FENCED**, so the lineage coverage percentage is
 *     computed over the 122+0+0 that could carry a link at all, with the fence
 *     reported beside it and never inside it.
 *
 * IT POSTS NOTHING and it opens no door. Every decision still lands on the
 * approval path.
 */
export default function TicketBoardPage() {
  const [stateFilter, setStateFilter] = useState<TicketState | "all">("all");
  const [openLineage, setOpenLineage] = useState<string | null>(null);
  const [openSeat, setOpenSeat] = useState<string | null>(null);

  // The same read discipline the exceptions desk uses — one hook, four states.
  const { page, tickets, read, countable, note, failure } = useTicketFold();

  const trays = useMemo(() => allTrays(tickets), [tickets]);
  const queue = useMemo(() => chairQueue(tickets), [tickets]);
  const coverage = useMemo(() => lineageCoverage(tickets), [tickets]);

  // THE CAP IS COMPUTED ONCE AND THE LIST IS SLICED WITH IT, so the sentence
  // and the rows cannot disagree. The rendered page said "showing 369 of 713"
  // over a list of 200 before this existed.
  const shownList = useMemo(() => {
    if (!tickets) return null;
    if (stateFilter === "all") return tickets.filter((t) => !isTerminal(t));
    return tickets.filter((t) => t.state === stateFilter);
  }, [tickets, stateFilter]);
  const shown = shownList;
  const cap = listCap(shown?.length ?? 0, page?.counts.total ?? 0);

  return (
    <div className="min-h-screen bg-[var(--kt-bg)] text-[var(--kt-text)]">
      <StudioHeader subtitle="The ticket board — every desk's in-tray and out-tray, over one fold" />
      <div className={KT.container}>
        <header className="mb-6">
          <p className={KT.label}>Krypton Fund · the ticket highway</p>
          <h1 className="text-2xl font-medium tracking-tight">The board</h1>
          {/* THE FAILURE SENTENCE IS SAID ONCE PER SURFACE. The
              absent-endpoint arm rendered it VERBATIM TWICE — here and in
              the block below — and it was visible only on the rendered
              page, because both halves were individually correct. The
              block owns the failure; this line owns the count. */}
          <p className={`mt-1 text-sm ${KT.muted}`}>
            {countable ? (page?.note ?? "…") : "…"}
          </p>
          <p className={`mt-1 text-xs ${KT.muted}`}>
            <Link href="/clark/studio/desk/ceo/exceptions" className="underline">
              the CEO&apos;s exceptions desk
            </Link>
            {" · "}
            <Link href="/clark/studio/desk/ceo" className="underline">
              his full desk
            </Link>
          </p>
        </header>

        {!countable && (
          <div className={`${KT.card} text-sm ${
            read === "unreadable" && failure === "unreadable"
              ? KT.sev.warn : KT.muted}`}>
            {note}
          </div>
        )}

        {countable && page && tickets && (
          <>
            {/* ------------------------- the census ------------------------ */}
            <section className={`${KT.card} mb-6`}>
              <p className={KT.label}>The population</p>
              <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-5">
                {WORKING_STATES.map((s) => (
                    <div key={s}>
                      <p className={`font-mono tabular-nums text-2xl ${
                        page.counts.by_state[s] ? "" : KT.muted}`}>
                        {page.counts.by_state[s] ?? 0}
                      </p>
                      <p className={`text-xs ${KT.muted}`}>{STATE_LABEL[s]}</p>
                    </div>
                  ))}
              </div>
              <p className={`mt-3 text-xs ${KT.muted}`}>
                {page.counts.terminal} closed ·{" "}
                {page.counts.recommendations_read
                  ? `${page.counts.runs_seen ?? "?"} run(s) read`
                  : <span className={KT.sev.warn}>
                      the recommendation store was NOT read — that leg is
                      UNKNOWN, not zero
                    </span>}
                {page.counts.desk_load_runs_cap != null && (
                  <>
                    {" · "}the other instrument caps at{" "}
                    {page.counts.desk_load_runs_cap} runs and this fold read{" "}
                    {page.counts.runs_seen ?? "?"}, so the two are still
                    comparable — and they{" "}
                    {page.counts.reconciles_with_desk_load
                      ? "reconcile"
                      : <span className={KT.sev.warn}>do NOT reconcile</span>}
                  </>
                )}
              </p>
              <div className="mt-3"><LifecycleLegend /></div>
            </section>

            {/* ---------------------- lineage coverage --------------------- */}
            {coverage && (
              <section className={`${KT.card} mb-6`}>
                <p className={KT.label}>Lineage coverage</p>
                {/* TWO HERO FIGURES, NOT ONE, AND THE FENCE IS THE SECOND.
                    `linkablePct` alone renders 100% on today's record — true,
                    and the most misleading true thing on this page, because
                    62% of the same population is fenced and unreadable. The
                    eye must meet both or it meets neither. */}
                <div className="mt-2 flex flex-wrap items-baseline gap-x-8 gap-y-2">
                  <p>
                    <span className={coverage.linkablePct === null
                      ? KT.heroDim : KT.hero}>
                      {coverage.linkablePct === null
                        ? "—"
                        : `${coverage.linkablePct.toFixed(0)}%`}
                    </span>
                    <span className={`ml-3 text-xs ${KT.muted}`}>
                      of the {coverage.linkable} ticket(s) that could carry a
                      parent are linked
                    </span>
                  </p>
                  <p>
                    <span className={coverage.fenced
                      ? `${KT.hero} ${KT.sev.warn}` : KT.heroDim}>
                      {coverage.fencedPct === null
                        ? "—"
                        : `${coverage.fencedPct.toFixed(0)}%`}
                    </span>
                    <span className={`ml-3 text-xs ${KT.muted}`}>
                      of all {coverage.total} are FENCED — their lineage is
                      UNKNOWN, not absent
                    </span>
                  </p>
                </div>
                {coverage.leads === "fenced" && (
                  <p className={`mt-2 text-xs ${KT.sev.warn}`}>
                    The fenced cohort is LARGER than the linked one, so the
                    first figure describes a minority of the record. Read them
                    together or not at all.
                  </p>
                )}
                <p className={`mt-2 text-xs ${KT.muted}`}>{coverage.note}</p>
                <div className={`mt-3 grid grid-cols-2 gap-3 text-xs sm:grid-cols-5`}>
                  <Fig n={coverage.found} label="linked" />
                  <Fig n={coverage.fenced} label="FENCED — unknown, not absent"
                       warn={coverage.fenced > 0} />
                  <Fig n={coverage.notApplicable} label="head of its own chain" />
                  <Fig n={coverage.absent} label="read, and holds no parent" />
                  <Fig n={coverage.dangling} label="names a ticket nobody has seen"
                       warn={coverage.dangling > 0} />
                </div>
              </section>
            )}

            {/* --------------------- the chair's queue --------------------- */}
            <section className={`${KT.card} mb-6`}>
              <p className={KT.label}>
                Awaiting the chair&apos;s review ({queue?.length ?? 0})
              </p>
              {queue && queue.length > 0 ? (
                <ul className="mt-2 space-y-2">
                  {queue.map((t) => (
                    <li key={t.ticket_id} className="flex items-start gap-2">
                      <span className="mt-1.5"><TicketLamp lamp="awaiting-review" /></span>
                      <span className="text-sm">{String(t.subject).slice(0, 120)}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className={`mt-2 text-xs ${KT.muted}`}>
                  No ticket is in <span className="font-mono">returned</span>.
                  The state exists and no door has been used yet, so this empty
                  queue is an UNUSED DOOR and not a cleared backlog — the
                  constitution&apos;s missing middle state has a rendering now
                  and nothing to render.
                </p>
              )}
            </section>

            {/* ------------------------ the seat trays --------------------- */}
            <section className="mb-6">
              <p className={`${KT.label} mb-3`}>
                Per-desk trays ({trays?.length ?? 0} seat(s) in the record)
              </p>
              <div className="space-y-3">
                {(trays ?? []).map((tr) => (
                  <TrayCard
                    key={tr.seat} tray={tr}
                    open={openSeat === tr.seat}
                    onToggle={() => setOpenSeat(
                      openSeat === tr.seat ? null : tr.seat)}
                    onOpenLineage={setOpenLineage}
                    tickets={tickets}
                    openLineage={openLineage}
                  />
                ))}
              </div>
            </section>

            {/* --------------------------- the rows ------------------------ */}
            <section className="mb-6">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <span className={KT.label}>Every ticket</span>
                <select
                  value={stateFilter}
                  onChange={(e) => setStateFilter(e.target.value as TicketState | "all")}
                  className="rounded-lg border border-[var(--kt-border)] bg-[var(--kt-surface)] px-2 py-1 text-xs"
                >
                  <option value="all">all working</option>
                  {page.states.map((s) => (
                    <option key={s} value={s}>
                      {s} ({page.counts.by_state[s] ?? 0})
                    </option>
                  ))}
                </select>
                <span className={`text-xs ${cap.capped ? KT.sev.warn : KT.muted}`}>
                  {cap.note}
                  {stateFilter === "all"
                    ? " Terminal rows are excluded from this view and reachable "
                      + "by picking their state above."
                    : ""}
                </span>
              </div>
              <div className="space-y-3">
                {(shown ?? []).slice(0, cap.shown).map((t) => (
                  <React.Fragment key={t.ticket_id}>
                    <TicketCard ticket={t} onOpenLineage={setOpenLineage} />
                    {openLineage === t.ticket_id && (
                      <LineageForId id={openLineage} tickets={tickets} />
                    )}
                  </React.Fragment>
                ))}
              </div>
              {cap.capped && (
                /* THE CAP IS ON SCREEN TWICE — above the list and below it —
                   because a reader who scrolls to the bottom of a capped list
                   is exactly the reader who will otherwise conclude it ended.
                   The desk this replaces truncated seven rows away with no
                   sentence at all and the CEO lost a $915 item to it. */
                <p className={`mt-3 text-xs ${KT.sev.warn}`}>
                  {cap.note} Narrow the state filter to reach the rest.
                </p>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}

function Fig({ n, label, warn }: { n: number; label: string; warn?: boolean }) {
  return (
    <div>
      <p className={`font-mono tabular-nums text-lg ${
        warn ? KT.sev.warn : n ? "" : KT.muted}`}>{n}</p>
      <p className={`${KT.muted}`}>{label}</p>
    </div>
  );
}

function TrayCard({ tray, open, onToggle, onOpenLineage, tickets, openLineage }: {
  tray: SeatTray;
  open: boolean;
  onToggle: () => void;
  onOpenLineage: (id: string) => void;
  tickets: readonly Ticket[];
  openLineage: string | null;
}) {
  const waiting = tray.awaitingDispatch.length + tray.unconsumedLessons.length;
  return (
    <div className={KT.card}>
      <button type="button" onClick={onToggle} className="w-full text-left">
        <div className="flex items-center gap-3">
          <SeatFace actor={tray.seat} size={32} />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-[var(--kt-text-strong)]">
              {open ? "▾" : "▸"} {tray.seat}
            </p>
            <p className={`text-xs ${KT.muted}`}>
              in-tray {waiting} ({tray.awaitingDispatch.length} approved,{" "}
              {tray.unconsumedLessons.length} lesson(s)) · in flight{" "}
              {tray.inFlight.length} · out-tray {tray.outTray.length}
              {" · "}
              {tray.oldestWaitingHours === null
                ? (waiting
                  ? "oldest wait UNKNOWN — the fold could not read the instants"
                  : "nothing waiting")
                : `oldest wait ${tray.oldestWaitingHours.toFixed(0)}h`}
            </p>
            <p className={`mt-0.5 text-xs ${KT.muted}`}>{tray.note}</p>
          </div>
        </div>
      </button>
      {open && (
        <div className="mt-3 space-y-3 border-t border-[var(--kt-border)] pt-3">
          {[...tray.awaitingDispatch, ...tray.unconsumedLessons,
            ...tray.inFlight, ...tray.outTray].map((t) => (
            <React.Fragment key={t.ticket_id}>
              <TicketCard ticket={t} onOpenLineage={onOpenLineage} />
              {openLineage === t.ticket_id && (
                <LineageForId id={openLineage} tickets={tickets} />
              )}
            </React.Fragment>
          ))}
          {waiting + tray.inFlight.length + tray.outTray.length === 0 && (
            <p className={`text-xs ${KT.muted}`}>
              Nothing in either tray. {tray.note}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
