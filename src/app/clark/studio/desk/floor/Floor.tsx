"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { KT } from "../../theme";
import { SeatFace } from "../SeatFace";
import { faceFor } from "../faces";
import {
  awaitingReviewSeats,
  CORRIDOR,
  FloorSpot,
  PLANE_PX,
  Pulse,
  RoomPoint,
  RoomState,
  allSpots,
  floorPulses,
  litSeats,
  pulsesByWire,
  runsChip,
  spotById,
} from "./floorPlan";
import type { DeskView, SpineEvent } from "@/lib/fund_api";

/**
 * The room, drawn.
 *
 * Everything WHAT-is-true lives in floorPlan.ts and is tested there; this file
 * is only HOW it looks. The division is deliberate — the spec's acceptance
 * criteria are claims about facts, and a fact computed inside JSX can only be
 * checked by squinting at a screenshot.
 *
 * Read the header of studio-theme.css's floor block before changing anything
 * here: the two rules (nothing moves that did not happen; reduced motion loses
 * no information) are enforced across the CSS and this file together.
 */

/** Room units → percentage of the plane. One place, so the SVG layer and the
 *  DOM furniture can never disagree about where a desk is. */
const pct = (p: RoomPoint) => ({ left: `${p.x}%`, top: `${p.y}%` });
/** The pulse's travel distance is the only place this file needs pixels.
 *  `PLANE_PX` is imported rather than restated: it was a second local copy of
 *  `.kt-floor-plane`'s width carrying a "must match" comment, and the plane
 *  grew 640 -> 760 on 2026-08-22 — exactly the edit that would have sent every
 *  dot 16% short of its desk while the comment still read correct. */
const toPx = (units: number) => (units / 100) * PLANE_PX;

export interface FloorProps {
  desk: DeskView | null;
  events: SpineEvent[] | null;
  halted: boolean | null;
  state: RoomState;
  /** The RiskBar's own sentence, passed in verbatim rather than re-typed — the
   *  spec asks the dead floor to say what the strip says, and two copies of one
   *  sentence is two things to drift. */
  deadSentence: string;
  /** How many desk events the room draws. Stated on-surface beside the total. */
  pulseLimit?: number;
  /** Rendered inside the detail panel for the focused seat. Part B (desk
   *  telemetry) supplies it; the floor itself asserts no figures. */
  renderSeatDetail?: (spot: FloorSpot) => React.ReactNode;
  /** Runs today for a desk, for the numeral ON the room view.
   *
   *  CEO, 2026-08-21: "the floor doesnt capture how many runs each agent had
   *  that day." It only rendered in the click-open detail, so a room you had
   *  to click nine times to read was not answering the question the room is
   *  for.
   *
   *  THREE RETURNS, and they are three different facts: a NUMBER (measured,
   *  including a measured zero), `null` (a seat whose count could not be
   *  measured — renders a dashed x?), and `undefined` (not a dispatched seat
   *  at all — humans and fixtures, which render NOTHING). A zero on a human's
   *  desk would be a lie about a colleague. */
  runsToday?: (spot: FloorSpot) => number | null | undefined;
}

export function Floor({
  desk, events, halted, state, deadSentence, pulseLimit = 14, renderSeatDetail,
  runsToday,
}: FloorProps) {
  const [focus, setFocus] = useState<string | null>(null);
  const [zooming, setZooming] = useState(false);

  const spots = useMemo(() => allSpots(), []);
  const lit = useMemo(
    // A dead room has no lamps at all, whatever the last roster said.
    () => (state === "dead" ? [] : litSeats(desk?.roster)),
    [desk, state],
  );
  // The third state. NOT a lamp: a lamp says someone is at that desk, and a
  // returned dispatch means the opposite — the seat is done and the
  // obligation has moved to the chair. Drawing them alike is what made the
  // review queue invisible for hours.
  const awaiting = useMemo(
    () => (state === "dead" ? [] : awaitingReviewSeats(desk?.roster)),
    [desk, state],
  );
  const { pulses, total } = useMemo(
    () => (state === "dead"
      ? { pulses: [] as Pulse[], total: 0 }
      : floorPulses(events, pulseLimit)),
    [events, pulseLimit, state],
  );
  const wires = useMemo(() => pulsesByWire(pulses), [pulses]);
  const offFloor = useMemo(() => pulses.filter((p) => !p.fromId || !p.toId), [pulses]);

  const focused = focus ? spotById(focus) : null;

  return (
    // `kt-floor-room` is the QUERY CONTAINER the stage and the room scale
    // against. See studio-theme.css: the old viewport media queries could not
    // see the Clark rail taking ~440px out of the content column, so at a
    // 1181px viewport the corner office and the venue door were cut off the
    // floor and no breakpoint could tell.
    <div className="kt-floor-room">
      <div className="kt-floor-stage" data-room={state}>
        <div className="kt-floor-scale">
          <div className="kt-floor-plane" data-zooming={zooming ? "1" : undefined}>
            <RoomSvg wires={wires} lit={lit} state={state} />
            {/* Furniture, emitted in TAB ORDER (exec row → bench in
                constitution order → fixtures). Visual position comes from the
                inline percentages; the keyboard reads the org chart. */}
            <nav className="kt-floor-layer"
                 aria-label="The floor — every desk in the firm">
              {spots.map((s) => (
                <Spot
                  key={s.id}
                  s={s}
                  lit={lit.includes(s.id)}
                  awaitingReview={awaiting.includes(s.id)}
                  state={state}
                  halted={halted === true}
                  focused={focus === s.id}
                  onFocus={() => setFocus(s.id)}
                  onLeave={() => setFocus((f) => (f === s.id ? null : f))}
                  onNavigate={() => setZooming(true)}
                  runs={runsChip(state, runsToday?.(s))}
                />
              ))}
            </nav>
            {/* The traffic. One wrapper per pulse, carrying the spine's own
                event id, present in BOTH motion modes. */}
            {wires.map((w) => (
              <Wire key={w.key} fromId={w.fromId} toId={w.toId} pulses={w.pulses} />
            ))}
          </div>
        </div>

        {state === "dead" && (
          <div className="absolute inset-x-0 bottom-0 border-t border-[var(--kt-border)] bg-[var(--kt-bg)] px-5 py-3">
            <p className={`text-sm ${KT.sev.warn}`}>{deadSentence}</p>
            <p className={`mt-1 text-xs leading-relaxed ${KT.muted}`}>
              The floor is unlit because the spine could not be read — not
              because the room is empty. No lamp, no pulse and no chip is drawn
              from a stale reading. Every desk below is still a door.
            </p>
          </div>
        )}
      </div>

      {/* --------------------------------------------------- under the room */}
      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2">
        <TrafficNote state={state} drawn={pulses.length} total={total} limit={pulseLimit} />
        {offFloor.length > 0 && (
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border border-[var(--kt-border)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}
            title={offFloor.map((p) => `${p.verb}: ${p.offFloor}`).join("\n")}
          >
            <span className="tabular-nums">{offFloor.length}</span>
            <span>off-floor</span>
          </span>
        )}
        {state === "halted" && (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--kt-down)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--kt-down)]">
            trading halted — buys blocked, the sells exit stays lit
          </span>
        )}
      </div>

      {/* Off-floor pulses still need their event ids in the DOM: the replay
          count must not depend on whether an endpoint happened to have a desk. */}
      <div className="sr-only">
        {offFloor.map((p) => (
          <span key={p.eventId} data-event-id={p.eventId}>
            {p.verb} — {p.offFloor}
          </span>
        ))}
      </div>

      {focused && (
        <Detail spot={focused} lit={lit.includes(focused.id)} state={state}
                renderSeatDetail={renderSeatDetail} />
      )}
    </div>
  );
}

/* ------------------------------------------------------------- the room ---- */

/** The floor grid, the corridor, the corner office's walls, and the wires.
 *
 *  Inline SVG in ROOM UNITS (viewBox 0 0 100 100) so every coordinate in here
 *  is the same number floorPlan.ts states. `non-scaling-stroke` keeps the
 *  hairlines hairlines under the camera's foreshortening, the same rule
 *  SeatFace.tsx already follows.
 *
 *  `preserveAspectRatio="none"` IS KEPT DELIBERATELY, and the reason is the
 *  opposite of the usual one. It normally means "stretch, distortion be
 *  damned" — here it means "cover the plane box exactly", and it must, because
 *  the desk CARDS are positioned as percentages of that same box (see `pct`).
 *  Under the default `xMidYMid meet` a non-square box would letterbox the grid
 *  while the furniture kept using the full width, and the corridor, the lamps
 *  and the office walls would slide off the desks standing on them. It costs
 *  nothing today because `.kt-floor-plane` is square (760×760, and the CSS says
 *  why that is a constraint) — so `none` distorts nothing and guarantees the
 *  two layers agree if it ever stops being square. */
function RoomSvg({ wires, lit, state }: {
  wires: ReturnType<typeof pulsesByWire>;
  lit: string[];
  state: RoomState;
}) {
  const corridor = CORRIDOR.map((p) => `${p.x},${p.y}`).join(" ");
  return (
    <svg className="kt-floor-svg" viewBox="0 0 100 100" preserveAspectRatio="none"
         aria-hidden="true" fill="none" strokeLinecap="round" strokeLinejoin="round">
      {/* The ground. --kt-surface, not --kt-inset: at inset the floor sat within
          two units of the page background and the room did not read as a room at
          all — the plane's edge was the only thing separating them. */}
      <rect x="0" y="0" width="100" height="100" fill="var(--kt-surface)" />
      {/* Faint on purpose: the grid is the room's floorboards, and the desks
          must be the brightest thing in it. At the audit's first opacity the
          eye read the grid before it read the org chart. */}
      <g stroke="var(--kt-border)" strokeWidth="0.6" vectorEffect="non-scaling-stroke"
         opacity="0.32">
        {Array.from({ length: 9 }, (_, i) => (
          <React.Fragment key={i}>
            <line x1={(i + 1) * 10} y1="0" x2={(i + 1) * 10} y2="100" />
            <line x1="0" y1={(i + 1) * 10} x2="100" y2={(i + 1) * 10} />
          </React.Fragment>
        ))}
      </g>

      {/* the corner office: two walls, in plan. A corner office is a corner and
          two walls, and drawing them is what makes the only inbox tray on the
          floor sit somewhere a reader recognises.

          Drawn in 2026-08-22 from (28,22) to (22,18) because the exec row now
          starts at x=8 and the COO sits at x=27: at the old size the office
          wall would have been drawn one unit to the COO's left, i.e. with
          Vishesh inside the CEO's office. The office shrank; the CEO did not
          move out of the corner. */}
      <path d="M0 18 L22 18 L22 0" stroke="var(--kt-border-strong)" strokeWidth="1.4"
            vectorEffect="non-scaling-stroke" />

      {/* THE CORRIDOR — the constitution's chain, walked. One polyline, no
          branch, no shortcut: mechanism → adversary → the console → the machine
          room → the corner office. The wide pale stroke is the aisle; the thin
          one on top is its centre line. */}
      <polyline points={corridor} stroke="var(--kt-inset)" strokeWidth="7.5"
                strokeLinejoin="round" strokeLinecap="round" opacity="0.9" />
      <polyline points={corridor} stroke="var(--kt-border-strong)" strokeWidth="1"
                vectorEffect="non-scaling-stroke" strokeDasharray="1.6 1.8" />

      {/* The venue door's threshold, and the cage around the auto-policy. BOTH
          ARE DRAWN TWICE — once as a FloorSpot in floorPlan.FIXTURES and once
          as these bars and this line — so both coordinates move together or the
          room draws an UNCAGED auto-policy and a threshold across empty floor.
          The rect is centred on the cage spot (78,84); the line runs through the
          venue spot (90,90). Re-spaced 2026-08-22 with the room, into the
          lower-right quadrant that was standing empty — the far corner is where
          an order actually leaves by. */}
      <line x1="86" y1="84" x2="95" y2="96"
            stroke={state === "halted" ? "var(--kt-down)" : "var(--kt-border-strong)"}
            strokeWidth={state === "halted" ? 3 : 1.6} vectorEffect="non-scaling-stroke" />
      <rect x="72" y="78" width="12" height="12" rx="1"
            stroke="var(--kt-border-strong)" strokeWidth="1"
            vectorEffect="non-scaling-stroke" strokeDasharray="1.2 1.2" />

      {/* the wires that carried traffic. `data-traffic` is what the
          reduced-motion rule dashes — a wire with no traffic is not drawn at
          all, so an empty log leaves an empty room. */}
      <g>
        {wires.map((w) => {
          const a = spotById(w.fromId)?.at;
          const b = spotById(w.toId)?.at;
          if (!a || !b) return null;
          return (
            <line key={w.key} className="kt-floor-wire" data-traffic="1"
                  x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                  strokeWidth="0.8" vectorEffect="non-scaling-stroke"
                  opacity={0.7} />
          );
        })}
      </g>

      {/* a lamp is drawn over a working seat as a soft pool on the floor; the
          DOM lamp above it carries the breathe. Zero lamps on a dead room. */}
      <g>
        {lit.map((id) => {
          const s = spotById(id);
          if (!s) return null;
          return (
            <circle key={id} cx={s.at.x} cy={s.at.y} r="7"
                    fill="var(--kt-warn)" opacity="0.10" />
          );
        })}
      </g>
    </svg>
  );
}

/* -------------------------------------------------------------- furniture -- */

function Spot({ s, lit, state, halted, focused, onFocus, onLeave, onNavigate,
               runs, awaitingReview }: {
  s: FloorSpot; lit: boolean; state: RoomState; halted: boolean;
  focused: boolean; onFocus: () => void; onLeave: () => void; onNavigate: () => void;
  runs?: number | null;
  awaitingReview?: boolean;
}) {
  const machine = s.kind === "machine" || s.kind === "door";
  const body = (
    <span
      className={`flex min-w-[4.25rem] flex-col items-center gap-0.5 rounded-xl border px-2 py-1.5 ${
        focused
          ? "border-[var(--kt-text-dim)] bg-[var(--kt-surface)]"
          : "border-[var(--kt-border-strong)] bg-[var(--kt-surface)]"
      }`}
    >
      <span className="flex items-center gap-1.5">
        {/* A lamp, not a badge: the room tells you someone is at the desk the
            way a room does. `kt-breathe` keeps the marker drawn under reduced
            motion and drops only the motion. */}
        {lit && <span className={`kt-breathe kt-floor-lamp h-1.5 w-1.5`} aria-hidden="true" />}
        <span className={lit ? "text-[var(--kt-text-strong)]" : "text-[var(--kt-text-muted)]"}>
          {machine ? <MachineGlyph kind={s.kind} /> : <SeatFace actor={s.id} size={26} decorative />}
        </span>
      </span>
      <span className={`text-center font-mono text-[10px] leading-tight ${
        lit ? "text-[var(--kt-text)]" : KT.muted}`}>
        {s.label}
      </span>
      {/* The third state (CEO, request 907ecc74). NOT a lamp and not a lit
          label: the seat is finished and the obligation has moved to the
          chair, so it reads as a standing item rather than as activity.
          Three dispatches rendered as WORKING for hours before this. */}
      {awaitingReview && (
        <span
          title="returned — the chair has not reviewed it yet; a dispatch closes on a resolution, never on a run coming back"
          className="inline-flex items-center rounded-full border border-[var(--kt-text-dim)] px-1.5 font-mono text-[9px] uppercase tracking-[0.08em] text-[var(--kt-text)]"
        >
          review
        </span>
      )}
      {/* Runs today, ON the room view (CEO, 2026-08-21). Matches the x-N chip
          style the CTO's compact seat cards use, so one glyph means one thing
          in both places. `undefined` renders NOTHING — a human or a fixture
          has no run count and a zero there would be a lie about a colleague;
          `null` renders a dashed x? because unmeasured must never read as
          zero; a number renders, including a measured zero. */}
      {runs !== undefined && (
        <span
          title={typeof runs === "number"
            ? `${runs} run${runs === 1 ? "" : "s"} today`
            : "runs today could not be measured — unmeasured, not zero"}
          className={`inline-flex items-center rounded-full border px-1.5 font-mono text-[9px] uppercase tracking-[0.08em] ${
            typeof runs === "number"
              ? `border-[var(--kt-border)] ${KT.muted}`
              : "border-dashed border-[var(--kt-border-strong)] " + KT.muted}`}
        >
          ×<span className={typeof runs === "number"
            ? "tabular-nums text-[var(--kt-text)]" : ""}>
            {typeof runs === "number" ? runs : "?"}
          </span>
        </span>
      )}
      {s.inboxTray && <Tray label="inbox" hot={!halted} />}
      {s.triageTray && <Tray label="triage" hot={false} />}
      {s.id === "venue-door" && halted && (
        <span className="h-1 w-full rounded-full bg-[var(--kt-down)]" aria-hidden="true" />
      )}
      {s.id === "venue-door" && halted && (
        <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-[var(--kt-down)]">
          sells only
        </span>
      )}
    </span>
  );

  // The screen-reader name carries the third state too — a chip nobody can
  // hear is half a control.
  const label = `${s.label} — ${s.says}`
    + (awaitingReview ? " — awaiting review" : "");
  const common = {
    className: "kt-floor-spot",
    style: pct(s.at),
    onMouseEnter: onFocus,
    onMouseLeave: onLeave,
    onFocus,
    onBlur: onLeave,
  };

  // A dead spine changes nothing about clickability (criterion 3): every desk
  // is still a door, because the door does not depend on the reading.
  if (!s.href) {
    // NOT focusable, deliberately. The cage and the venue door are things you
    // read, not doors you open — and a tab stop that does nothing when you
    // press Enter is exactly what axe's focus-order-semantics rule exists to
    // catch. They keep their accessible name and their hover detail; the
    // keyboard walks the org chart, which is what criterion 5 asks for.
    return (
      <div {...common} aria-label={label} title={label} role="img">
        {body}
      </div>
    );
  }
  return (
    <Link {...common} href={s.href} aria-label={label} title={label}
          onClick={onNavigate} data-room-state={state}>
      {body}
    </Link>
  );
}

/** The square-faced machines, drawn to the same rule faces.ts states: humans
 *  round or oval, machines square. A reader must never mistake the auto-policy
 *  for a person. */
function MachineGlyph({ kind }: { kind: FloorSpot["kind"] }) {
  return (
    <svg viewBox="0 0 26 26" width={26} height={26} fill="none" stroke="currentColor"
         strokeWidth={1.25} strokeLinecap="round" strokeLinejoin="round"
         vectorEffect="non-scaling-stroke" aria-hidden="true">
      {kind === "door" ? (
        <>
          <rect x="6.5" y="3.5" width="13" height="19" rx="1.5" />
          <circle cx="16" cy="13" r="1" />
        </>
      ) : (
        <>
          <rect x="4.5" y="6.5" width="17" height="13" rx="2" />
          <path d="M8.5 11 h4 M8.5 15 h9" />
        </>
      )}
    </svg>
  );
}

/** A tray. The corner office's is the ONLY inbox on this floor — the spec's
 *  sharpest sentence, and floorPlan's test enforces it. */
function Tray({ label, hot }: { label: string; hot: boolean }) {
  return (
    <span className={`flex items-center gap-1 font-mono text-[9px] uppercase tracking-[0.08em] ${
      hot ? "text-[var(--kt-text-dim)]" : KT.muted}`}>
      <svg viewBox="0 0 16 10" width={16} height={10} fill="none" stroke="currentColor"
           strokeWidth={1} vectorEffect="non-scaling-stroke" aria-hidden="true">
        <path d="M1 6 L3 2 h10 l2 4 v2 a1 1 0 0 1 -1 1 H2 a1 1 0 0 1 -1 -1 z" />
        <path d="M1 6 h4 l1 1.5 h4 L11 6 h4" />
      </svg>
      {label}
    </span>
  );
}

/* ---------------------------------------------------------------- traffic -- */

/** One wire's worth of traffic: the moving dots (animated mode) and the count
 *  chip (reduced-motion mode). Both are always in the DOM; the media query
 *  decides which is displayed, and the `data-event-id` wrappers never move. */
function Wire({ fromId, toId, pulses }: { fromId: string; toId: string; pulses: Pulse[] }) {
  const a = spotById(fromId)?.at;
  const b = spotById(toId)?.at;
  if (!a || !b) return null;
  const dx = toPx(b.x - a.x);
  const dy = toPx(b.y - a.y);
  const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
  const summary = pulses
    .map((p) => `${(p.at || "").slice(0, 16).replace("T", " ")}Z · ${fromId} ${p.verb} ${toId}: ${p.label}`)
    .join("\n");

  return (
    <>
      {pulses.map((p, i) => (
        <span
          key={p.eventId}
          className="kt-floor-pulse-wrap"
          style={pct(a)}
          data-event-id={p.eventId}
          title={`${fromId} ${p.verb} ${toId} — ${p.label}`}
        >
          <span
            className="kt-floor-pulse"
            style={{
              // Per-pulse geometry as CSS variables so ONE keyframe serves every
              // wire; a keyframe per wire is how a room's CSS ends up unbounded.
              ["--kt-wire-dx" as string]: `${dx}px`,
              ["--kt-wire-dy" as string]: `${dy}px`,
              // Stagger so two events on one wire read as two, not as one dot.
              animationDelay: `${i * 380}ms`,
            }}
            aria-hidden="true"
          />
        </span>
      ))}
      {/* Reduced motion's half of the information parity: the aisle is dashed
          (CSS, above) and this chip carries the count the dots were carrying. */}
      <span className="kt-floor-spot" style={pct(mid)}>
        <span
          className="kt-floor-wire-chip items-center gap-1 rounded-full border border-[var(--kt-text-muted)] bg-[var(--kt-inset)] px-1.5 py-0.5 font-mono text-[10px] tabular-nums text-[var(--kt-text-dim)]"
          title={summary}
          aria-label={`${pulses.length} interaction${pulses.length === 1 ? "" : "s"} from ${fromId} to ${toId}`}
        >
          {pulses.length}
        </span>
      </span>
    </>
  );
}

function TrafficNote({ state, drawn, total, limit }: {
  state: RoomState; drawn: number; total: number; limit: number;
}) {
  if (state === "dead") {
    return (
      <p className={`text-xs ${KT.sev.warn}`}>
        No traffic is drawn — the event log could not be read. This is an
        absence, not a quiet room.
      </p>
    );
  }
  if (total === 0) {
    return (
      <p className={`text-xs ${KT.muted}`}>
        The room is still because the log is still — no desk interaction in the
        events read. Nothing on this floor moves without an event behind it.
      </p>
    );
  }
  return (
    <p className={`text-xs ${KT.muted}`}>
      Drawing the {drawn} most recent desk interaction{drawn === 1 ? "" : "s"}
      {total > drawn && <> of {total} read (the newest {limit} are shown)</>}
      . Every pulse carries its spine event id.
    </p>
  );
}

/* ----------------------------------------------------------------- detail -- */

function Detail({ spot, lit, state, renderSeatDetail }: {
  spot: FloorSpot; lit: boolean; state: RoomState;
  renderSeatDetail?: (spot: FloorSpot) => React.ReactNode;
  /** Runs today for a desk, for the numeral ON the room view.
   *
   *  CEO, 2026-08-21: "the floor doesnt capture how many runs each agent had
   *  that day." It only rendered in the click-open detail, so a room you had
   *  to click nine times to read was not answering the question the room is
   *  for.
   *
   *  THREE RETURNS, and they are three different facts: a NUMBER (measured,
   *  including a measured zero), `null` (a seat whose count could not be
   *  measured — renders a dashed x?), and `undefined` (not a dispatched seat
   *  at all — humans and fixtures, which render NOTHING). A zero on a human's
   *  desk would be a lie about a colleague. */
  runsToday?: (spot: FloorSpot) => number | null | undefined;
}) {
  const f = faceFor(spot.id);
  return (
    <div className={`${KT.card} mt-4 p-4`}>
      <div className="flex items-start gap-3">
        <span className={lit ? "text-[var(--kt-text-strong)]" : "text-[var(--kt-text-muted)]"}>
          <SeatFace actor={spot.id} size={34} decorative />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-mono text-sm text-[var(--kt-text-strong)]">
            {spot.label}
            {f && f.label !== spot.id && (
              <span className={`ml-1.5 text-[11px] font-normal ${KT.muted}`}>{spot.id}</span>
            )}
          </p>
          <p className={`mt-1 text-[13px] leading-relaxed ${KT.body}`}>{spot.says}</p>
          {state === "dead" ? (
            <p className={`mt-2 text-xs ${KT.sev.warn}`}>
              Nothing is known about this desk right now — the spine could not be
              read. That is not the same as an idle desk.
            </p>
          ) : (
            renderSeatDetail?.(spot)
          )}
          {spot.href && (
            <Link href={spot.href} className={`mt-2 inline-block text-xs ${KT.accent} underline underline-offset-2`}>
              open {spot.label}&apos;s page
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
