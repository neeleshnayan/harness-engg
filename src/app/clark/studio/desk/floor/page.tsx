"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Users } from "lucide-react";
import {
  fundApiClient, CeoDeskView, DeskView, RiskMonitorResponse, SpineEvent,
} from "@/lib/fund_api";
import { KT } from "../../theme";
import { StudioHeader } from "../../components/StudioHeader";
import { RISK_UNREACHABLE_SENTENCE } from "../../components/RiskBar";
import { SeatTelemetryChips, SectionHead } from "../components";
import { seatTelemetry } from "../deskTelemetry";
import { DeskMatrix } from "../DeskMatrix";
import { routingFootprint } from "../routingFootprint";
import type { SeatFanout } from "../fanout";
import { seatFanout } from "../fanout";
import { Floor } from "./Floor";
import { floorEnabled, roomState } from "./floorPlan";

/**
 * `/clark/studio/desk/floor` — the 2.5D lobby.
 *
 * CDO spec, Deliverable B (docs/design/CDO_AUDIT_2026-08-20.md). The 2D pages
 * remain the working truth; this is PRESENCE, TRAFFIC, STATE and nothing else.
 * Three questions: who is in, what is moving between whom, is the room dark.
 * Everything else on this floor is a door.
 *
 * Behind `NEXT_PUBLIC_STUDIO_FLOOR=1`. With the flag unset the route renders a
 * stated "not enabled" panel naming the variable rather than a 404 — a 404 for a
 * page that exists teaches the reader something false, and the CEO validating
 * this feature needs to be able to tell "off" from "broken".
 *
 * The reads are the same three the Studio already makes: `GET /fund/desk` (who
 * is in), `GET /fund/events` (what moved), `GET /fund/risk/monitor` (is the
 * venue door barred). No new endpoint, no new storage, no new dependency.
 */

/** How many desk interactions the room draws at once.
 *
 * A rendering decision, not a measurement: the log carries 174
 * DeskRecommendationDecided events today and a room drawing all of them would
 * be a fog, not a floor. The page states the drawn count AND the total beside
 * it, so a clipped view can never read as a complete one. */
const PULSE_LIMIT = 14;

export default function FloorPage() {
  const enabled = floorEnabled();
  const [desk, setDesk] = useState<DeskView | null>(null);
  const [events, setEvents] = useState<SpineEvent[] | null>(null);
  const [monitor, setMonitor] = useState<RiskMonitorResponse | null>(null);
  const [deskErr, setDeskErr] = useState<string | null>(null);
  const [monErr, setMonErr] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  /* The ticket board's own fold, a SEPARATE failure from the room's: the board
     can be unreadable while the room is fine, and rendering an empty board for
     an unreachable endpoint would say "no tickets". */
  const [ceo, setCeo] = useState<CeoDeskView | null>(null);
  const [ceoErr, setCeoErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [d, ev, m, b] = await Promise.allSettled([
      fundApiClient.getDesk(),
      fundApiClient.getEvents(1000, 0),
      fundApiClient.getRiskMonitor(),
      // `git=false`: hygiene's commit-citation rule shells out to git, which
      // does not belong in a 10-second poll. The payload reports H3 as NOT
      // EVALUATED rather than as finding nothing.
      fundApiClient.getCeoDesk(null, false),
    ]);
    if (b.status === "fulfilled") { setCeo(b.value); setCeoErr(null); }
    else setCeoErr(b.reason instanceof Error ? b.reason.message : "unreachable");
    if (d.status === "fulfilled") { setDesk(d.value); setDeskErr(null); }
    else { setDesk(null); setDeskErr(d.reason instanceof Error ? d.reason.message : "unreachable"); }
    // The events read is allowed to fail on its own: the room can still say who
    // is in and whether the door is barred. It simply draws no traffic, and the
    // note under the room says which of the two it is.
    setEvents(ev.status === "fulfilled" ? ev.value.events || [] : null);
    if (m.status === "fulfilled") { setMonitor(m.value); setMonErr(null); }
    else { setMonitor(null); setMonErr(m.reason instanceof Error ? m.reason.message : "unreachable"); }
    setLoaded(true);
  }, []);

  useEffect(() => {
    // NO LONGER GATED ON THE FLAG. The 2.5D room is behind
    // `NEXT_PUBLIC_STUDIO_FLOOR`; the ticket board that now lives on this
    // route is NOT, and gating its reads on the room's flag would make the
    // board render empty rather than absent in exactly the build where nobody
    // would think to look. A control that quietly does nothing when a flag is
    // off is the unwired-kill-switch pattern in a new costume.
    load();
    // Same 10s cadence as the office page: the floor is watched, and the reads
    // are cheap folds the spine already computes.
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [load]);

  /**
   * THE FIRM'S TICKET BOARD — moved here from the office page.
   *
   * CEO instruction, verbatim 2026-08-23: *"And put the matrix in the room not
   * the desk page."* The desk pages are PERSONAL — what awaits you, in lanes,
   * with lineage — and an org-wide seats × states board on one of them was the
   * one block that answered nobody's own question. The room is where the firm
   * is looked at as a firm, so the board is here, under the seats it counts.
   *
   * IT IS OUTSIDE THE ROOM'S FLAG, deliberately: see the effect above. The
   * 2.5D room ships behind `NEXT_PUBLIC_STUDIO_FLOOR`; the board must not.
   */
  const footprint = routingFootprint(
    desk?.open_recommendations ?? null, ceo?.matrix?.seats ?? []);

  const board = (
    <section className="mb-8">
      <SectionHead
        title="The ticket board"
        lede="Every open thing at the firm, one row per seat. Click any number to read the rows behind it. Counts come from the spine's own fold, so a cell and its list can never disagree."
      />
      {ceoErr ? (
        <div className={`${KT.panel} p-4`}>
          <p className={`text-sm ${KT.sev.warn}`}>
            The ticket board could not be read ({ceoErr}) — showing nothing
            rather than a clear board.
          </p>
        </div>
      ) : (
        <>
          <DeskMatrix matrix={ceo?.matrix ?? null} />
          <RoutingFootprintNote footprint={footprint} readable={desk !== null} />
        </>
      )}
    </section>
  );

  if (!enabled) {
    return (
      <div className="min-h-screen bg-[var(--kt-bg)] text-[var(--kt-text)]">
        <StudioHeader subtitle="The floor" />
        <div className={KT.container}>
          {board}
          <div className={`${KT.card}`}>
            <p className={KT.label}>The 2.5D room is not enabled</p>
            <p className={`mt-2 text-sm ${KT.body}`}>
              This build was made without <code className="font-mono">NEXT_PUBLIC_STUDIO_FLOOR=1</code>.
              The room is off, not broken — the board above is unaffected, and
              the 2D office at{" "}
              <Link href="/clark/studio/desk" className={`${KT.accent} underline underline-offset-2`}>
                /clark/studio/desk
              </Link>{" "}
              is the working truth either way.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const state = roomState({
    deskReadable: !!desk && !deskErr,
    monitorReadable: !!monitor && !monErr,
    halted: monitor?.halted,
  });

  return (
    <div className="min-h-screen bg-[var(--kt-bg)] text-[var(--kt-text)]">
      <StudioHeader subtitle="The floor — presence, traffic, and whether the room is dark" />
      <div className={KT.container}>
        <header className="mb-6">
          <p className={KT.label}>Krypton Fund · The floor</p>
          <h1 className="mt-1 flex items-center gap-2 text-2xl font-medium tracking-tight">
            <Users size={22} className={KT.accent} />
            The room
          </h1>
          <p className={`mt-2 max-w-2xl text-sm ${KT.muted}`}>
            Who is in, what is moving between whom, and whether the room is dark.
            No numbers and no decisions live here — every desk is a door into the
            page that carries them.{" "}
            <Link href="/clark/studio/desk" className={`${KT.accent} underline underline-offset-2`}>
              the 2D office
            </Link>{" "}
            remains the working truth.
          </p>
        </header>

        {board}

        {!loaded ? (
          <p className={`text-sm ${KT.muted}`}>Reading the room…</p>
        ) : (
          <>
            <Floor
              desk={desk}
              events={events}
              halted={monitor?.halted ?? null}
              state={state}
              deadSentence={
                // Verbatim from the RiskBar (the spec asks the dead floor to say
                // what the strip says), with the actual failure appended so the
                // reader can tell an unreachable spine from a 500.
                monErr || deskErr
                  ? `${RISK_UNREACHABLE_SENTENCE} (${monErr || deskErr})`
                  : RISK_UNREACHABLE_SENTENCE
              }
              pulseLimit={PULSE_LIMIT}
              // The SAME three figures the 2D bench cards show, from the same
              // module — the CEO will compare the two surfaces, and two
              // renderings of one number is how a reader learns to trust
              // whichever is prettier. Only DESKS get them: a machine has no
              // runs, and a zero beside the caged auto-policy would read as a
              // measurement of something nobody measures.
              /* Runs today, ON the room (CEO, 2026-08-21: "the floor doesnt
                 capture how many runs each agent had that day"). The three
                 returns are three facts: undefined for anything that is not a
                 dispatched seat — humans and fixtures keep their no-count
                 honesty lines and get NO numeral, because a zero on Neelesh's
                 or Fable's desk would be a lie about a colleague; null when
                 the count could not be measured; a number otherwise. */
              runsToday={(spot) => {
                if (spot.kind === "machine" || spot.kind === "door") return undefined;
                if (spot.id === "ceo" || spot.id === "cto") return undefined;
                const t = seatTelemetry(desk, spot.id);
                return typeof t.runsToday === "number" ? t.runsToday : null;
              }}
              renderSeatDetail={(spot) =>
                spot.kind === "machine" || spot.kind === "door" ? (
                  <p className={`mt-2 text-xs ${KT.muted}`}>
                    A fixture, not a seat — nothing dispatches it and nothing
                    counts its runs.
                  </p>
                ) : spot.id === "ceo" || spot.id === "cto" ? (
                  <p className={`mt-2 text-xs ${KT.muted}`}>
                    A human, not a dispatched seat — the spine cannot count a
                    person&apos;s runs, and a zero here would be a lie about a
                    colleague.
                  </p>
                ) : (
                  <>
                    <SeatTelemetryChips t={seatTelemetry(desk, spot.id)} />
                    {/* THE FAN-OUT, from the record. CEO 2026-08-23: "would be
                        good to see agents w sub-agents fanned out in the rooms
                        UI too!". It mounts on the DETAIL prop, not inside the
                        room's geometry — the floor plan is coupled four ways
                        and this needed none of it. */}
                    <FanoutTree f={seatFanout({ kind: "record", desk }, spot.id)} />
                  </>
                )
              }
            />

            {/* The "what this room does not show" disclaimer was REMOVED
                2026-08-22 on the CEO's instruction. The constraints it listed
                are still true and still enforced in floorPlan.ts — this floor
                renders no decidable control, no ambient motion, and no
                interior for Abhishek's thesis wing. They are properties of the
                code, not a caption, and the caption was costing a screenful. */}
          </>
        )}
      </div>
    </div>
  );
}

/**
 * THE FAN-OUT TREE — the workers a seat fired, FROM THE RECORD.
 *
 * IT SAYS "LAST RECORDED RUN" ON EVERY CARD, and that sentence is the feature
 * as much as the tree is. The CEO asked for the floor to change shape in
 * real time; the spine has no dispatch-state store, agents run inside the
 * chair's session, and nothing streams their shape. A tree drawn from the
 * flight recorder that let itself read as live would be a floor that looks
 * like it is breathing while showing yesterday — strictly worse than no tree.
 *
 * THE D33 SEAM IS `f.basis`, and it is one word. `seatFanout` takes a SOURCE,
 * not a desk; when a live endpoint exists, D33 adds a `live` source, this
 * component renders "live" instead of "last recorded run", and neither the
 * card nor the room moves.
 *
 * Four shapes, four different facts, and the tree is only ever drawn for the
 * first — see `fanout.ts` for why prose is never parsed into workers.
 */
function FanoutTree({ f }: { f: SeatFanout }) {
  if (f.shape === "no_run" || f.shape === "none") {
    return (
      <p className={`mt-2 text-[10px] leading-relaxed ${KT.muted}`}>{f.note}</p>
    );
  }
  return (
    <div className="mt-2">
      <p className={`${KT.label} flex flex-wrap items-baseline gap-x-2`}>
        <span>fan-out</span>
        <span className="font-mono tabular-nums text-[var(--kt-text-strong)]">
          {f.count === null ? "unstated" : f.count}
        </span>
        {/* The honesty word, always on screen, never inferred by the reader. */}
        <span className="normal-case tracking-normal">{f.basis}</span>
      </p>
      {f.shape === "structured" && (
        <ul className="mt-1 space-y-0.5 border-l border-[var(--kt-border)] pl-2.5">
          {f.workers.map((w) => (
            <li key={w.worker} className="text-[11px] leading-snug">
              <span className="flex flex-wrap items-baseline gap-x-1.5">
                {/* A MID-RUN CATCH IS THE ONE THING THAT EARNS THE ACCENT.
                    It is the only outcome that changed what the run did while
                    it was running; used and discarded are bookkeeping. */}
                {w.outcome === "catch" && <span className={KT.dot} />}
                <span className="font-mono text-[var(--kt-text-strong)]">
                  {w.worker}
                </span>
                <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${
                  w.outcome === "catch" ? KT.accent : KT.muted}`}>
                  {w.outcome === "unstated" ? "outcome unstated" : w.outcome}
                </span>
                {w.kind && (
                  <span className={`font-mono text-[10px] ${KT.muted}`}>{w.kind}</span>
                )}
                {w.tokens !== null && (
                  <span className={`font-mono text-[10px] tabular-nums ${KT.muted}`}>
                    {w.tokens.toLocaleString("en-US")} tok
                  </span>
                )}
              </span>
              {w.brief && (
                <span className={`block text-[11px] leading-snug ${KT.muted}`}>
                  {w.brief}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {f.shape === "prose" && (
        <p className={`mt-1 border-l border-[var(--kt-border)] pl-2.5 text-[11px] leading-snug ${KT.body}`}>
          {f.prose}
        </p>
      )}
      <p className={`mt-1 text-[10px] leading-relaxed ${KT.muted}`}>{f.note}</p>
      {f.runId && (
        <p className={`font-mono text-[10px] ${KT.muted}`}>
          {f.runId}{f.at ? ` · ${f.at.slice(0, 10)}` : ""}
        </p>
      )}
    </div>
  );
}

/**
 * THE ROUTING FOOTPRINT, against the seat that filed.
 *
 * The brief asked for the desk's `routing_advisory` to render against the
 * filing seat. Measured against the running spine first: that advisory is
 * built on the 200 body of `POST /fund/desk/runs` and no GET returns it, so a
 * browser cannot read it — see `routingFootprint`'s own docstring for why
 * re-implementing `routing_errors()` here was refused. What is rendered is the
 * spine's STORED footprint of the same machinery, and the sentence says which
 * of the two it is.
 *
 * Quiet and factual, per the brief: no alarm styling. A seat filing under an
 * older rule set is not misbehaving.
 */
function RoutingFootprintNote({ footprint, readable }: {
  footprint: ReturnType<typeof routingFootprint>;
  readable: boolean;
}) {
  if (!footprint) {
    return (
      <p className={`mt-3 text-[11px] leading-relaxed ${KT.sev.warn}`}>
        {readable
          ? "The recommendation feed could not be folded, so routing coverage is UNKNOWN."
          : "The desk could not be read, so routing coverage is UNKNOWN — not zero."}
      </p>
    );
  }
  // Only seats that actually filed something. A row of zeroes per idle seat
  // would be six lines of nothing under a board that is already dense.
  const rows = footprint.seats.filter((s) => s.filed > 0);
  return (
    <div className="mt-4">
      <p className={KT.label}>Routing, as filed</p>
      <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1">
        {rows.length === 0 ? (
          <p className={`text-[11px] ${KT.muted}`}>
            No seat has a recommendation in the feed this page reads.
          </p>
        ) : rows.map((s) => (
          <p key={s.seat} className={`font-mono text-[10px] ${KT.muted}`}>
            {s.seat}{" "}
            <span className="tabular-nums text-[var(--kt-text-strong)]">
              {s.declared}
            </span>
            <span className="tabular-nums">/{s.filed}</span>
            {s.unrouted > 0 && (
              <span className="tabular-nums"> · {s.unrouted} unrouted</span>
            )}
          </p>
        ))}
      </div>
      <p className={`mt-2 max-w-3xl text-[11px] leading-relaxed ${KT.muted}`}>
        {footprint.note}
      </p>
    </div>
  );
}
