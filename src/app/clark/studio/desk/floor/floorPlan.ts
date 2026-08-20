/**
 * The floor plan — the room's geometry and every derivation drawn on it.
 *
 * Implements Deliverable B of docs/design/CDO_AUDIT_2026-08-20.md: a
 * fixed-camera dimetric lobby whose GEOMETRY IS THE ORG CHART. The rule that
 * shapes the whole file: the room may only show things the spine can prove.
 * Three questions and no more — who is in, what is moving between whom, is the
 * room dark — and everything else is a door.
 *
 * Why the plan lives in a pure module rather than inside the JSX: four of the
 * spec's seven acceptance criteria are assertions about DERIVED FACTS (pulse
 * count equals desk-event count; no lamp on a dead spine; tab order is
 * constitution order; the corridor has no shortcut aisle). A fact derived inside
 * a component can only be checked by looking at it, and looking is what let the
 * last three absence defects ship. Everything below is a pure function with a
 * test that fails if the room starts drawing traffic nobody generated.
 *
 * Coordinates are ROOM UNITS: x ∈ [0,100] left→right, y ∈ [0,100] back→front.
 * y=0 is the back wall (the executive row), y=100 the front (where the room is
 * entered). The renderer maps that square onto a dimetric plane with one CSS
 * transform; nothing here knows about pixels, degrees or the camera.
 */

import type { DeskView, SpineEvent } from "@/lib/fund_api";
import { SEATS, type SeatId } from "../seatLib.ts";
import { faceFor } from "../faces.ts";

/* ------------------------------------------------------------------ flag --- */

/**
 * The floor ships behind `NEXT_PUBLIC_STUDIO_FLOOR=1` (spec, Deliverable B).
 *
 * With the flag unset the route renders a stated "not enabled" panel naming the
 * variable, NOT a 404 — a 404 for a page that exists teaches the reader
 * something false, and a CEO validating this feature has to be able to tell
 * "off" from "broken".
 *
 * The split into two functions is not ceremony, it is a MEASURED bug fix. The
 * first version took the environment as a parameter defaulting to `process.env`
 * so tests could inject one. That reads fine and is wrong: Next inlines only
 * LITERAL `process.env.NEXT_PUBLIC_*` member accesses at build time, so passing
 * `process.env` around as an object leaves the browser reading an empty bag —
 * the flag was set, the room said "not enabled", and only a screenshot found it.
 * The literal read now lives in exactly one expression, and the testable half
 * takes a plain string.
 */
export function floorEnabledFrom(value: string | undefined | null): boolean {
  return value === "1";
}

export function floorEnabled(): boolean {
  return floorEnabledFrom(process.env.NEXT_PUBLIC_STUDIO_FLOOR);
}

/* ---------------------------------------------------------------- points --- */

export interface RoomPoint {
  x: number;
  y: number;
}

/** What kind of thing occupies a spot. Drives the silhouette, exactly as
 *  faces.ts drives portraits: a reader must never mistake the caged auto-policy
 *  for a colleague. */
export type SpotKind = "office" | "desk" | "console" | "machine" | "door";

export interface FloorSpot {
  /** Stable id — the actor id where one exists (`pm`, `ceo`), else a fixture
   *  name (`machine-room`, `venue-door`). Used as the DOM id and the test key. */
  id: string;
  kind: SpotKind;
  at: RoomPoint;
  /** What the plaque says. */
  label: string;
  /** One line: what happens here. Becomes the accessible name together with
   *  the label, so a screen reader hears the room, not a grid of divs. */
  says: string;
  /** Where clicking goes, or null for a fixture that is not a door. */
  href: string | null;
  /** Set on the ONE desk that carries the approval queue. The spec is explicit:
   *  the inbox tray lives in the corner office AND ONLY THERE, because the
   *  click lives there and only there. */
  inboxTray?: boolean;
  /** The COO's triage tray, which feeds the corner office. */
  triageTray?: boolean;
  /** True when the spot is a bench seat with a live lamp. Fixtures never light:
   *  a machine is not "working", and drawing it as if it were would invent a
   *  status the spine does not report. */
  lampable?: boolean;
}

/* ------------------------------------------------------- the exec row ------ */

/**
 * The back wall, left to right: the corner office, the triage desk beside it,
 * the console.
 *
 * Order is the reporting line, not aesthetics — the CEO's corner, the COO who
 * feeds it, the CTO who dispatches. The corner office is in the CORNER (x=15,
 * against the left wall) because that is what makes it one.
 */
export const EXEC_ROW: readonly FloorSpot[] = Object.freeze([
  {
    id: "ceo", kind: "office", at: { x: 15, y: 11 },
    label: "Neelesh", says: "the corner office — every approval click, and the only inbox tray on this floor",
    href: "/clark/studio/desk/ceo", inboxTray: true,
  },
  {
    id: "coo", kind: "desk", at: { x: 40, y: 11 },
    label: "Vishesh", says: "triage — the desk batched into decisions, then handed to the corner office",
    href: "/clark/studio/desk/coo", triageTray: true, lampable: true,
  },
  {
    id: "cto", kind: "console", at: { x: 63, y: 11 },
    label: "Fable", says: "the console — the dispatch board; every seat runs from here",
    href: "/clark/studio/desk/cto",
  },
]);

/* ----------------------------------------------------------- the bench ----- */

/**
 * The bench, two rows of four, IN CONSTITUTION ORDER.
 *
 * The order is `SEATS` from seatLib — the same list the route whitelist uses —
 * and not the order `GET /fund/desk` happens to return its roster in. Those two
 * disagree today (the spine returns builder before riskofficer), and the spec
 * says constitution order, so the plan states which source it obeys rather than
 * inheriting whichever arrived. The COO is not here: it sits in the exec row by
 * the CEO's 2026-08-20 decision.
 */
export const BENCH_ORDER: readonly SeatId[] = Object.freeze(
  SEATS.filter((s) => s !== "coo"),
) as readonly SeatId[];

const BENCH_ROW_Y = [43, 66];
const BENCH_COL_X = [15, 34, 53, 72];

export function benchSpots(): FloorSpot[] {
  return BENCH_ORDER.map((seat, i) => {
    const f = faceFor(seat);
    return {
      id: seat,
      kind: "desk" as const,
      at: { x: BENCH_COL_X[i % 4], y: BENCH_ROW_Y[Math.floor(i / 4)] },
      label: seat,
      // The role sentence comes from faces.ts verbatim (criterion 5: accessible
      // names from faces.ts roles). A second copy of "what the pm does" would be
      // a second thing to drift.
      says: f?.role ?? "no role on file for this seat",
      href: `/clark/studio/desk/${seat}`,
      lampable: true,
    };
  });
}

/* --------------------------------------------------------- the fixtures --- */

/**
 * Everything in the room that is not a colleague.
 *
 * The machine room (the belt and the gate) is drawn as square-faced machines
 * because that is the silhouette rule faces.ts already enforces; the auto-policy
 * is a machine IN A CAGE, and the cage is the envelope — it is the only drawn
 * object in the room whose meaning is a constraint. Abhishek's wing is a DOOR
 * and renders no interior: his surfaces are not ours to draw.
 */
export const FIXTURES: readonly FloorSpot[] = Object.freeze([
  {
    id: "machine-room", kind: "machine", at: { x: 88, y: 22 },
    label: "belt · gate",
    says: "the machine room — the belt runs the candidate, the gate judges it",
    href: "/clark/studio/lab",
  },
  {
    id: "autopolicy-cage", kind: "machine", at: { x: 84, y: 74 },
    label: "auto-policy",
    says: "the deterministic auto-approval envelope, caged — the cage IS the envelope; everything outside it waits for the click",
    href: null,
  },
  {
    id: "venue-door", kind: "door", at: { x: 94, y: 86 },
    label: "the venue",
    says: "the door orders leave by. A halt lights the red strip here: buys blocked, sells still allowed",
    href: null,
  },
  {
    id: "thesis-door", kind: "door", at: { x: 3, y: 34 },
    label: "thesis — observe only",
    says: "Abhishek's wing. The door opens his page; this floor draws no interior",
    href: "/clark/studio/thesis",
  },
]);

/** Every spot in the room, in TAB ORDER: exec row, then the bench in
 *  constitution order, then the fixtures. Criterion 5's falsifier reads this
 *  list directly — a room whose tab order is DOM order by accident would pass
 *  by luck and fail the day a card moves. */
export function allSpots(): FloorSpot[] {
  return [...EXEC_ROW, ...benchSpots(), ...FIXTURES];
}

export function spotById(id: string): FloorSpot | null {
  return allSpots().find((s) => s.id === id) ?? null;
}

/* ---------------------------------------------------------- the corridor --- */

/**
 * The chain, as the room walks it. Constitution order, no stage skippable.
 *
 * These five stations are the constitution's candidate chain — mechanism
 * proposes → adversary attacks → the CTO verifies and implements → the belt
 * tests and the gate judges → the operator clicks. The corridor visits them in
 * that order and in no other, and there is no shortcut aisle BECAUSE THERE IS
 * NO SHORTCUT IN THE CONSTITUTION. That is the one thing this drawing exists to
 * say, and `corridorHasNoShortcut()` is what stops it being said falsely.
 */
export const CHAIN: readonly string[] = Object.freeze([
  "mechanism", "adversary", "cto", "machine-room", "ceo",
]);

/**
 * The aisle itself: ONE polyline, no branches, threaded through the stations in
 * chain order. The long return leg from the machine room back to the corner
 * office is deliberate and is the truest segment on the floor — a candidate
 * that clears the gate walks BACK across the room for a human's click.
 */
export const CORRIDOR: readonly RoomPoint[] = Object.freeze([
  { x: 15, y: 43 },   // mechanism
  { x: 15, y: 66 },   // adversary
  { x: 26, y: 66 },
  { x: 26, y: 29 },
  { x: 63, y: 29 },
  { x: 63, y: 11 },   // the console
  { x: 80, y: 11 },
  { x: 88, y: 22 },   // the machine room
  { x: 88, y: 36 },
  { x: 36, y: 36 },
  { x: 36, y: 18 },
  { x: 15, y: 11 },   // the corner office
]);

/** The corridor index each station sits at, or -1. */
export function stationIndex(id: string): number {
  const s = spotById(id);
  if (!s) return -1;
  return CORRIDOR.findIndex((p) => p.x === s.at.x && p.y === s.at.y);
}

/**
 * Does the aisle connect any two stations that the constitution does not put
 * next to each other?
 *
 * The falsifier for "no shortcut aisle exists". Walking the polyline, the
 * stations must be encountered in exactly CHAIN order with nothing skipped: if
 * a future edit ever routes the corridor from mechanism straight to the corner
 * office, the stations come out of order or short, and this returns false.
 */
export function corridorHasNoShortcut(): boolean {
  const hits: string[] = [];
  for (const p of CORRIDOR) {
    const station = CHAIN.find((id) => {
      const s = spotById(id);
      return !!s && s.at.x === p.x && s.at.y === p.y;
    });
    if (station) hits.push(station);
  }
  return hits.length === CHAIN.length && hits.every((h, i) => h === CHAIN[i]);
}

/* -------------------------------------------------------------- the room --- */

/**
 * Is the room lit, dimmed, or dark? The floor's third question, and the only
 * one with a wrong answer that costs money.
 *
 * `dead` is NOT `lit-and-quiet`. A spine we cannot reach tells us nothing about
 * the fund, so the room goes unlit and says the RiskBar's own sentence — every
 * lamp, pulse and chip goes with it (criterion 3). Unknown is not idle, and a
 * calm-looking floor over an unreachable spine is the same lie as a zero over an
 * absent number.
 */
export type RoomState = "lit" | "halted" | "dead";

export function roomState(opts: {
  deskReadable: boolean;
  monitorReadable: boolean;
  halted: boolean | null | undefined;
}): RoomState {
  // Either read failing darkens the room. The desk supplies who is in; the
  // monitor supplies whether the venue door is barred. Missing one of them
  // means the room cannot answer one of its three questions, and a floor that
  // answers two of three while looking complete is worse than an unlit one.
  if (!opts.deskReadable || !opts.monitorReadable) return "dead";
  return opts.halted === true ? "halted" : "lit";
}

/** The seats whose lamp is lit, from the spine's own activity fold.
 *
 *  Null roster → EMPTY, never "all idle": a floor with no lamps and a floor we
 *  could not read must not look alike, and the caller renders the dead room
 *  differently on the strength of this returning nothing. */
export function litSeats(roster: DeskView["roster"] | null | undefined): string[] {
  if (!roster) return [];
  return roster
    .filter((r) => r.activity?.status === "working")
    .map((r) => r.agent);
}

/* -------------------------------------------------------------- pulses ----- */

export const DESK_EVENT_TYPES = [
  "DeskRequested",
  "DeskDispatched",
  "DeskRequestResolved",
  "DeskRecommendationDecided",
] as const;

export type DeskEventType = (typeof DESK_EVENT_TYPES)[number];

export interface Pulse {
  /** The spine's own event id. Rendered as `data-event-id` on the drawn pulse
   *  — criterion 4's falsifier reads it straight off the DOM. There is no code
   *  path in this module that mints one. */
  eventId: string;
  type: DeskEventType;
  at: string | null;
  /** The verb the wire is carrying, in the office's own words. */
  verb: string;
  /** Spot ids. `null` means the endpoint is not on this floor — an actor with
   *  no desk (`cdo-trial` is live in the log today) or a resolution whose
   *  dispatch fell outside the window. The pulse still EXISTS and still counts;
   *  it renders as a stated off-floor chip rather than a wire from nowhere. */
  fromId: string | null;
  toId: string | null;
  /** Why an endpoint is missing, in the reader's terms. Null when both landed. */
  offFloor: string | null;
  label: string;
}

const str = (p: Record<string, unknown>, k: string): string | null => {
  const v = p[k];
  return typeof v === "string" && v ? v : null;
};

/** Does this actor or seat name have a spot in this room? */
function spotFor(name: string | null): string | null {
  if (!name) return null;
  return spotById(name) ? name : null;
}

/**
 * Real desk traffic, turned into wires. NOTHING ELSE EVER MOVES ON THIS FLOOR.
 *
 * One pulse per desk event, in and out. The spec's criterion 4 is a count
 * identity, so this function is deliberately incapable of the two failures that
 * would break it: it never merges two events into one wire (each pulse keys on
 * its own `event_id`), and it never emits a pulse without an event to hang it
 * on (there is no default, no ambient, no "idle animation" branch anywhere in
 * this file — the room is still when the log is still, and that stillness is
 * information).
 *
 * `DeskRequestResolved` carries no seat: its payload is `{request_id,
 * resolution, actor, trace_id}` (verified on the live log, 2026-08-21). The
 * delivering seat is recovered from the DeskDispatched whose `task_id` matches;
 * when that dispatch is outside the events read, the pulse says so instead of
 * guessing a seat.
 *
 * @param events  spine events, any types, any order
 * @param limit   how many of the MOST RECENT desk events to draw. Clipping is a
 *                rendering decision and the caller states it on-surface; this
 *                function reports `total` so the page can never imply it drew
 *                everything.
 */
export function floorPulses(
  events: SpineEvent[] | null | undefined,
  limit = 14,
): { pulses: Pulse[]; total: number } {
  const all = (events ?? []).filter(
    (e) => (DESK_EVENT_TYPES as readonly string[]).includes(e.type),
  );

  // request_id -> the seat it was dispatched to, so a resolution can name its
  // sender. Built over EVERY desk event read, not just the drawn window.
  const seatOfRequest = new Map<string, string>();
  for (const e of all) {
    if (e.type !== "DeskDispatched") continue;
    const p = (e.payload || {}) as Record<string, unknown>;
    const tid = str(p, "task_id") || str(p, "request_id");
    const seat = str(p, "seat");
    if (tid && seat) seatOfRequest.set(tid, seat);
  }

  const sorted = [...all].sort((a, b) => (b.ts || "").localeCompare(a.ts || ""));
  const drawn = limit >= 0 ? sorted.slice(0, limit) : sorted;

  const pulses: Pulse[] = [];
  for (const e of drawn) {
    const p = (e.payload || {}) as Record<string, unknown>;
    const actor = (e.actor || "").trim().toLowerCase() || null;
    let fromName: string | null = actor;
    let toName: string | null = null;
    let verb = "moved";
    let label = "";
    let missing: string | null = null;

    if (e.type === "DeskRequested") {
      toName = str(p, "serves");
      verb = "asked";
      label = str(p, "subject") || "(request)";
    } else if (e.type === "DeskDispatched") {
      toName = str(p, "seat");
      verb = "dispatched";
      label = str(p, "task") || "(dispatch)";
    } else if (e.type === "DeskRequestResolved") {
      // Delivery travels the other way: the seat hands its artifact back.
      const rid = str(p, "request_id");
      const seat = rid ? seatOfRequest.get(rid) ?? null : null;
      fromName = seat;
      toName = actor;
      verb = "delivered";
      label = str(p, "resolution") || "(delivery)";
      if (!seat) {
        missing = rid
          ? `the dispatch for request ${rid.slice(0, 8)} is outside the events read, so the delivering seat is unknown`
          : "this resolution names no request, so the delivering seat is unknown";
      }
    } else {
      toName = str(p, "seat");
      verb = str(p, "status") || "decided";
      label = str(p, "text") || "(recommendation)";
    }

    const fromId = spotFor(fromName);
    const toId = spotFor(toName);
    if (!missing) {
      const off: string[] = [];
      if (fromName && !fromId) off.push(`"${fromName}" has no desk on this floor`);
      if (!fromName) off.push("no actor was recorded on this event");
      if (toName && !toId) off.push(`"${toName}" has no desk on this floor`);
      if (!toName) off.push("this event names no seat");
      missing = off.length ? off.join("; ") : null;
    }

    pulses.push({
      eventId: e.event_id,
      type: e.type as DeskEventType,
      at: e.ts ?? null,
      verb,
      fromId,
      toId,
      offFloor: missing,
      label,
    });
  }
  return { pulses, total: all.length };
}

/** Pulses grouped by the wire they travel, so the reduced-motion rendering can
 *  put ONE dashed aisle and ONE count chip per wire and lose no information.
 *
 *  Keyed `from>to`; pulses missing an endpoint are not on a wire and are
 *  returned separately by the caller reading `offFloor`. */
export function pulsesByWire(pulses: Pulse[]): {
  key: string; fromId: string; toId: string; pulses: Pulse[];
}[] {
  const wires = new Map<string, { key: string; fromId: string; toId: string; pulses: Pulse[] }>();
  for (const p of pulses) {
    if (!p.fromId || !p.toId || p.fromId === p.toId) continue;
    const key = `${p.fromId}>${p.toId}`;
    let w = wires.get(key);
    if (!w) {
      w = { key, fromId: p.fromId, toId: p.toId, pulses: [] };
      wires.set(key, w);
    }
    w.pulses.push(p);
  }
  return Array.from(wires.values());
}

/* --------------------------------------------------------------- camera --- */

/**
 * The fixed camera, as CSS. Dimetric: the two horizontal axes take the same
 * foreshortening, so a desk one unit further back is the same size as one a
 * unit to the side — which is what lets the eye read the org chart off the
 * geometry rather than off perspective.
 *
 * `perspective` is deliberately absent. A perspective camera makes the front of
 * the room bigger than the back, and the back of this room is where the
 * approvals are. Exported as a string so the ONE place the camera is defined is
 * here and the test can assert it never grows a `perspective(` or a second
 * rotate axis.
 */
export const CAMERA_TRANSFORM = "rotateX(58deg) rotateZ(-45deg)";

/** The counter-transform that stands a card back up to face the camera. Applied
 *  to every desk so the room is 2.5D — a 3D floor with flat, readable furniture
 *  — rather than 3D text nobody can read at 58 degrees. */
export const BILLBOARD_TRANSFORM = "rotateZ(45deg) rotateX(-58deg)";
