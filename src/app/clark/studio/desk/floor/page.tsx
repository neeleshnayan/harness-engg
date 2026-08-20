"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Users } from "lucide-react";
import {
  fundApiClient, DeskView, RiskMonitorResponse, SpineEvent,
} from "@/lib/fund_api";
import { KT } from "../../theme";
import { StudioHeader } from "../../components/StudioHeader";
import { RISK_UNREACHABLE_SENTENCE } from "../../components/RiskBar";
import { SeatTelemetryChips, SectionHead } from "../components";
import { seatTelemetry } from "../deskTelemetry";
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

  const load = useCallback(async () => {
    const [d, ev, m] = await Promise.allSettled([
      fundApiClient.getDesk(),
      fundApiClient.getEvents(1000, 0),
      fundApiClient.getRiskMonitor(),
    ]);
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
    if (!enabled) return;
    load();
    // Same 10s cadence as the office page: the floor is watched, and the reads
    // are cheap folds the spine already computes.
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [enabled, load]);

  if (!enabled) {
    return (
      <div className="min-h-screen bg-[var(--kt-bg)] text-[var(--kt-text)]">
        <StudioHeader subtitle="The floor" />
        <div className={KT.container}>
          <div className={`${KT.card}`}>
            <p className={KT.label}>The floor is not enabled</p>
            <p className={`mt-2 text-sm ${KT.body}`}>
              This build was made without <code className="font-mono">NEXT_PUBLIC_STUDIO_FLOOR=1</code>.
              The room is off, not broken — the 2D office at{" "}
              <Link href="/clark/studio/desk" className={`${KT.accent} underline underline-offset-2`}>
                /clark/studio/desk
              </Link>{" "}
              is the working truth and is unaffected either way.
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
                  <SeatTelemetryChips t={seatTelemetry(desk, spot.id)} />
                )
              }
            />

            <section className="mt-8">
              <SectionHead
                title="What this room deliberately does not show"
                lede="Stated, because a floor plan that looks complete invites the reader to stop looking."
              />
              <ul className={`space-y-1 text-[13px] leading-relaxed ${KT.muted}`}>
                <li>· No numbers and no recommendation text — those live on the desk pages, where they can be decided.</li>
                <li>· No decidable control. Nothing on this floor approves, stages, dispatches or halts anything.</li>
                <li>· No people walking, no ambient motion, no replay. A pulse exists only where a spine event does.</li>
                <li>· No interior for the thesis wing — that is Abhishek&apos;s surface, and this floor draws its door only.</li>
              </ul>
            </section>
          </>
        )}
      </div>
    </div>
  );
}
