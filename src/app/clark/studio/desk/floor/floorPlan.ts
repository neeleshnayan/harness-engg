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
import { seatLamps, type SeatLamps } from "../seatActivity.ts";
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

/* ------------------------------------------------------- the camera math --- */

/**
 * The plane's rendered side, in PIXELS. **Must match `.kt-floor-plane`'s
 * width/height in studio-theme.css**, and it is exported so there is exactly
 * one number: the pulse's travel distance and the separation test below both
 * read it, and a second copy is how the dots start overshooting their desks.
 *
 * RAISED 640 -> 760 on 2026-08-22 (CEO: "make the room bigger and better
 * spaced out"). Both halves of that ask are this one number plus the
 * coordinates below — a bigger plane means more pixels per ROOM UNIT, so the
 * same 68px desk card covers 8.9 units instead of 10.6 and the desks stop
 * crowding each other without anybody moving. The ceiling is MEASURED, not
 * chosen: the Studio content column with the Clark rail open came back at
 * 1152px at its widest (CDP, 2026-08-22, viewports 1920 and 1600), a square of
 * side S turned 45 degrees in-plane projects to S·√2 of screen width, and
 * 760·√2 = 1075 fits with 77px to spare. The next sizes up were rejected on
 * the same measurement, not on taste: 780 draws 1103 and 800 draws 1131,
 * against a column that measured 1132 at a 1600px viewport — 0.6px of margin
 * is not a margin, it is a coin toss with `overflow: hidden`.
 */
export const PLANE_PX = 760;

/** The camera's tilt, in degrees. The same 58 that CAMERA_TRANSFORM carries —
 *  stated as a number so the projection below cannot drift from the CSS. */
export const CAMERA_TILT_DEG = 58;

/**
 * Where a room point lands on screen, in pixels, relative to the room's LEFT
 * vertex. Pure geometry of `rotateZ(-45deg)` then `rotateX(58deg)`:
 *
 *   sx = (u + v) / √2                 sy = (v - u) · cos(58°) / √2
 *
 * with u,v the point in plane pixels. Exported because "these two desks do not
 * overlap" is a claim about SCREEN distance, not about room units — the camera
 * squashes the y axis to 53% — and a layout test that measures the wrong space
 * passes while the room reads as a pile. Validated against the live DOM: this
 * predicted the console card 33.4px below the plane's top edge and
 * `DOM.getBoundingClientRect` measured 34.
 */
export function toScreen(p: RoomPoint): RoomPoint {
  const u = (p.x / 100) * PLANE_PX;
  const v = (p.y / 100) * PLANE_PX;
  const cos = Math.cos((CAMERA_TILT_DEG * Math.PI) / 180);
  return { x: (u + v) / Math.SQRT2, y: ((v - u) * cos) / Math.SQRT2 };
}

/** Centre-to-centre distance between two room points, in SCREEN pixels. */
export function screenSeparation(a: RoomPoint, b: RoomPoint): number {
  const p = toScreen(a);
  const q = toScreen(b);
  return Math.hypot(p.x - q.x, p.y - q.y);
}

/**
 * How far a room point is from the NEAREST wall, in screen pixels.
 *
 * Written 2026-08-22 after a defect a screenshot caught and every assertion in
 * floorPlan.test.ts missed: the first pass of the re-space put the machine room
 * at x=94 and the venue door at (96,84), and both cards rendered hanging past
 * the floor's right edge with nothing underneath them. Nothing in room units
 * looked wrong — 94 is inside 0..100 — because the failure is about the CARD's
 * pixel width against the wall's projected distance, and the two live in
 * different spaces.
 *
 * The camera contracts both floor axes identically (it is dimetric, which is
 * the whole reason the org chart is readable off the geometry), so the
 * perpendicular distance to a wall is a constant per room unit:
 *
 *   2·cos(θ) / (√2 · √(1 + cos²θ))  ≈ 0.662 · PLANE_PX/100  ≈ 5.03px at 760
 *
 * A door is EXEMPT by intent — a door is in a wall, so its plaque straddles
 * one. Everything else has to stand on the floor.
 */
export function wallClearance(p: RoomPoint): number {
  const cos = Math.cos((CAMERA_TILT_DEG * Math.PI) / 180);
  const perUnit =
    ((PLANE_PX / 100) * 2 * cos) / (Math.SQRT2 * Math.sqrt(1 + cos * cos));
  return Math.min(p.x, 100 - p.x, p.y, 100 - p.y) * perUnit;
}

/* ------------------------------------------------------- the exec row ------ */

/**
 * The back wall, left to right: the corner office, the triage desk beside it,
 * the CFO beside her, the secretary, the console.
 *
 * Order is the reporting line, not aesthetics — the CEO's corner, the COO who
 * feeds it, the CFO who argues with the COO, the secretary who records it, the
 * CTO who dispatches. The corner office is in the CORNER (against the left
 * wall) because that is what makes it one.
 *
 * GRACE JOINED 2026-08-22 (CEO: "CFO desk needs to be visible in the room
 * too"). She is on the BACK WALL and not on the bench because the constitution
 * puts her there twice over: the COO "sits in the floor's executive row", and
 * THE EXECUTIVE TABLE seats the two of them as peers who advise the same person
 * on the same decisions from different axes and are expected to argue. So they
 * are ADJACENT — Vishesh at 27, Grace at 46 — because on this floor the
 * geometry is the org chart, and two seats that argue with each other sitting
 * at opposite ends of the row would be drawing something false.
 *
 * THE ROW WAS RE-SPACED FROM FOUR TO FIVE, not squeezed. Donna's arrival
 * (2026-08-21) recorded the reason and it still binds: exec spacing was 23-25
 * units and the bench's is 19, so an inserted desk at ~11 units would have
 * overlapped its neighbours. Five desks at 8/27/46/65/84 is a flat 19 units,
 * which at PLANE_PX=760 is 116px between centres against a 68-75px card.
 *
 * TWO THINGS MOVED WITH THE ROW AND BOTH ARE LOAD-BEARING:
 *   1. **The corridor.** The console is a chain station; the aisle threads
 *      through it. It moved 75 -> 84 and the waypoint moved with it, or the
 *      drawing would show the candidate chain passing through empty floor.
 *   2. **The machine room.** It moved (88,22) -> (91,26) because the console's
 *      new x=84 leaves the OLD machine-room spot 77.2px from it on screen —
 *      measured with `screenSeparation`, and under the 85px floor the layout
 *      test now enforces. It is a chain station too, so its waypoints moved.
 */
export const EXEC_ROW: readonly FloorSpot[] = Object.freeze([
  {
    id: "ceo", kind: "office", at: { x: 8, y: 12 },
    label: "Neelesh", says: "the corner office — every approval click, and the only inbox tray on this floor",
    href: "/clark/studio/desk/ceo", inboxTray: true,
  },
  {
    id: "coo", kind: "desk", at: { x: 27, y: 12 },
    label: "Vishesh", says: "triage — the desk batched into decisions, then handed to the corner office",
    href: "/clark/studio/desk/coo", triageTray: true, lampable: true,
  },
  {
    // Grace, for Hopper. The sentence carries the seat's actual point rather
    // than its title: the CFO's scarce resource is the CLOCK, not the money
    // (CEO, 2026-08-22), and every allocation she makes is judged on whether it
    // moves the date this fund can honestly ask for more capital.
    id: "cfo", kind: "desk", at: { x: 46, y: 12 },
    label: "Grace", says: "the meter — what each seat costs and what it bought; the scarce resource is the clock, so every call is judged on whether it moves the date",
    href: "/clark/studio/desk/cfo", lampable: true,
  },
  {
    id: "secretary", kind: "desk", at: { x: 65, y: 12 },
    label: "Donna", says: "the record — each day documented from the log at end of day; documents, never decides",
    href: "/clark/studio/desk/secretary", lampable: true,
  },
  {
    id: "cto", kind: "console", at: { x: 84, y: 12 },
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
 * the CEO's 2026-08-20 decision, and neither is the SECRETARY, who joined that
 * row 2026-08-21. Both are excluded by the same rule — a seat with an exec-row
 * desk drawn on the bench as well would appear twice in one room.
 *
 * THE CFO JOINED THE EXCLUSION 2026-08-22 with her exec-row desk. The bench
 * stayed at eight and still fills 4x2 exactly — CHECKED, not assumed: `SEATS`
 * gained `cfo` in the same change, so eleven seats less three exec desks is
 * eight. The assertion lives in floorPlan.test.ts, and it is the one that
 * caught Donna appearing twice on the day she was added.
 */
const EXEC_SEATS = new Set(["coo", "secretary", "cfo"]);

export const BENCH_ORDER: readonly SeatId[] = Object.freeze(
  SEATS.filter((s) => !EXEC_SEATS.has(s)),
) as readonly SeatId[];

/* The bench spread out with the room (2026-08-22, CEO: "better spaced out").
   Rows moved 43/66 -> 42/68 and columns 15/34/53/72 -> 16/36/56/76: a flat 20
   units between columns and 26 between rows, which at PLANE_PX=760 is 122px and
   152px between centres against a 68-75px card. Column 1 moved RIGHT
   specifically to unstick the thesis door, whose plaque is the widest card in
   the room at 117px and made it the tightest pair on the floor. */
const BENCH_ROW_Y = [42, 68];
const BENCH_COL_X = [16, 36, 56, 76];

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
 *
 * EVERY FIXTURE MOVED 2026-08-22 with the room, and each move has a measured
 * reason rather than a taste. The first three were placed, LOOKED AT, and
 * placed again — the first attempt drew the machine room and the venue door
 * hanging over the floor's right edge, which no unit test in this file could
 * have caught and a screenshot caught immediately:
 *
 *   · machine room (88,22) -> (91,26). It had to move because the console's new
 *     x=84 leaves the old spot 77.2px from it, under the 85px floor. It could
 *     not simply go further out to x=94, which was the first attempt: a
 *     card's distance from the +x wall is about 5.03px per room unit under this
 *     camera, so a 68px card needs its centre ~7 units in, and at 94 it stood 4px
 *     OUTSIDE the floor it is meant to be a room in. At 91 it clears by 11px.
 *     Its corridor waypoints moved with it, and the aisle got SIMPLER: the leg
 *     out of the console is now axis-aligned, so the room draws one diagonal
 *     where it used to draw two.
 *   · auto-policy cage (84,74) -> (78,84) and venue door (94,86) -> (90,90).
 *     They moved for two reasons at once: the bench's fourth column at x=76
 *     leaves the OLD cage spot 75.5px from the builder's desk — two 68-71px
 *     cards with 6px of air, and under the 85px floor — and the whole
 *     lower-right quadrant of the floor — the far corner an order actually
 *     leaves by — was empty. The venue door now sits ten units off the far
 *     corner, which is where a door belongs. The cage stays beside it (13.4
 *     room units; the test's bound is 20).
 *     THE CAGE AND THE THRESHOLD ARE DRAWN TWICE — here as spots and in
 *     Floor.tsx as the bars and the halt strip — so both coordinates move
 *     together or the room draws an UNCAGED auto-policy.
 *   · thesis door: UNMOVED, at (3,34), and that is a correction to an earlier
 *     pass of this same change. It was shifted to (2,32) on the way through and
 *     the diff read fine — but measuring afterwards showed (3,34) already
 *     clears the corner office by 119.4px and the mechanism's desk by 113.7px,
 *     against the 92.5px its 117px plaque needs. The move was solving a problem
 *     created by an intermediate bench position and would have LOWERED the
 *     clearance to 105.6px. A fixture that does not need to move does not move.
 */
export const FIXTURES: readonly FloorSpot[] = Object.freeze([
  {
    id: "machine-room", kind: "machine", at: { x: 91, y: 26 },
    label: "belt · gate",
    says: "the machine room — the belt runs the candidate, the gate judges it",
    href: "/clark/studio/lab",
  },
  {
    id: "autopolicy-cage", kind: "machine", at: { x: 78, y: 84 },
    label: "auto-policy",
    says: "the deterministic auto-approval envelope, caged — the cage IS the envelope; everything outside it waits for the click",
    href: null,
  },
  {
    id: "venue-door", kind: "door", at: { x: 90, y: 90 },
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
  { x: 16, y: 42 },   // mechanism
  { x: 16, y: 68 },   // adversary
  { x: 26, y: 68 },
  { x: 26, y: 28 },
  // Moved 63 -> 75 (2026-08-21, Donna) -> 84 (2026-08-22, Grace) WITH the
  // console. The aisle reaches the CTO because the CTO is a chain station; a
  // waypoint left at an old x would draw the chain through empty floor and
  // `corridorHasNoShortcut` would stop reaching a station it must. This is the
  // second time an exec-row insertion has dragged the corridor with it, which
  // is why the coupling is written at the top of EXEC_ROW as well.
  { x: 84, y: 28 },
  { x: 84, y: 12 },   // the console
  // Axis-aligned into the machine room, where it used to be a dog-leg. That
  // was not tidying: it takes the room from two diagonal segments to one, and
  // `corridorHasNoShortcut`'s sibling test caps diagonals precisely because a
  // free diagonal lets a future edit draw mechanism -> ceo as one straight run
  // and still pass the ordering check.
  { x: 91, y: 12 },
  { x: 91, y: 26 },   // the machine room
  { x: 91, y: 36 },
  { x: 34, y: 36 },
  { x: 34, y: 20 },
  // Moved 15 -> 12 (2026-08-21) -> 8 (2026-08-22) with the corner office. The
  // aisle's last leg is the candidate walking BACK for a human's click; it has
  // to end where the office actually is.
  { x: 8, y: 12 },    // the corner office
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

/**
 * What runs-today numeral a spot should carry, given the room's state.
 *
 * THREE RETURNS AND THEY ARE THREE DIFFERENT FACTS, which is the whole reason
 * this is a function and not an inline ternary:
 *   · a NUMBER — measured, including a measured zero;
 *   · `null` — a dispatched seat whose count could not be read (renders ×?);
 *   · `undefined` — NOT A DISPATCHED SEAT AT ALL, so no numeral is drawn. A
 *     human, a machine, a door. A count on Neelesh's desk would be a lie about
 *     a colleague, and one on the caged auto-policy would invent a measurement
 *     of something nobody measures.
 *
 * THE DEFECT THIS EXISTS TO FIX, found by looking on 2026-08-22 and live until
 * then: the dead-room branch read `state === "dead" ? null : runsToday(spot)`,
 * which correctly refuses to show a stale count — and collapsed `undefined`
 * into `null` on the way, putting a ×? on the CEO, the CTO, the machine room,
 * the auto-policy cage, the venue door and Abhishek's thesis door. Seventeen
 * spots, seventeen chips, on a floor whose own page comment says a numeral
 * there would be a lie.
 *
 * A dead spine still suppresses every COUNT: unknown must not read as measured.
 */
export function runsChip(
  state: RoomState,
  runs: number | null | undefined,
): number | null | undefined {
  if (runs === undefined) return undefined;   // not a dispatched seat, ever
  if (state === "dead") return null;          // a count now would be a stale one
  return runs;
}

/**
 * Every seat's lamps, from the one reader.
 *
 * ADDED 2026-08-27 on the CEO's own observation on this floor, verbatim: *"1
 * builder working but 2 in reality"*. `litSeats` and `awaitingReviewSeats`
 * below now DELEGATE here rather than filtering the roster's headline status
 * themselves — that filter kept only a seat's most recent dispatch, so a seat
 * running two jobs lit one lamp and a seat whose newest job had finished while
 * an older one ran lit none at all.
 *
 * One reader, three consumers. The room, the console and the seat pages must
 * not be able to disagree about who is busy.
 */
export function floorLamps(
  roster: DeskView["roster"] | null | undefined,
): SeatLamps[] {
  if (!roster) return [];
  return roster.map((r) => seatLamps(r.agent, r.activity));
}

/** The seats whose lamp is lit, from the spine's own activity fold.
 *
 *  Null roster → EMPTY, never "all idle": a floor with no lamps and a floor we
 *  could not read must not look alike, and the caller renders the dead room
 *  differently on the strength of this returning nothing. */
export function litSeats(roster: DeskView["roster"] | null | undefined): string[] {
  return floorLamps(roster)
    .filter((l) => l.lamps.some((d) => d.state === "working"))
    .map((l) => l.seat);
}

/** How many jobs each seat is running, where it is more than one.
 *
 *  TWO CONSUMERS, both in `Floor.tsx`: the stacked lamps (capped at three, so
 *  a busy desk reads as busier) and the "N jobs" chip that appears only PAST
 *  that cap, where the lamps stop being countable at a glance.
 *
 *  Only seats with MORE THAN ONE open job are in the map: a marker on every
 *  desk is chrome, and this one exists to say "this is not the one job you
 *  assume". Absent from the map means one job or none — never "unknown", which
 *  is `seatLamps`' `basis` to report and not this map's. */
export function lampCounts(
  roster: DeskView["roster"] | null | undefined,
): Record<string, number> {
  const out: Record<string, number> = {};
  for (const l of floorLamps(roster)) {
    if (l.lamps.length > 1) out[l.seat] = l.lamps.length;
  }
  return out;
}

/**
 * Seats whose dispatch has COME BACK and which nobody has reviewed.
 *
 * The third state (CEO, request 907ecc74). The floor drew two where there are
 * three, so three finished dispatches rendered as WORKING for hours and the
 * chair's review queue was invisible.
 *
 * Deliberately NOT lit like a working seat: a lamp says "someone is at that
 * desk". A returned dispatch is the opposite — the seat is done and the
 * obligation has moved to the chair. Rendering them the same is what made the
 * queue invisible in the first place.
 */
export function awaitingReviewSeats(
  roster: DeskView["roster"] | null | undefined,
): string[] {
  return floorLamps(roster)
    .filter((l) => l.lamps.some((d) => d.state === "awaiting_review"))
    .map((l) => l.seat);
}

/**
 * Whether the spine could TELL a returned dispatch from a running one.
 *
 * False means detection was unavailable, not that every seat is genuinely
 * busy — measured 2026-08-21, only 8 of 23 dispatched task_ids carry a run
 * with a matching trace. A floor that showed a confident WORKING on an
 * undetectable dispatch would be asserting something it cannot see.
 */
export function reviewDetectionBlind(
  roster: DeskView["roster"] | null | undefined,
): string[] {
  // A DELIBERATE BEHAVIOUR CHANGE, named because it is the only one in this
  // delegation and it was silent until the read-through. The old predicate was
  // `review_detectable === false`, so a working seat whose payload OMITS the
  // key was reported as detectable — a confident "we looked and could tell"
  // built on a field nobody sent. It now reads as BLIND, which is the same
  // direction every other absence on this floor takes: absent is not a claim.
  // The arm had no test; it does now.
  return floorLamps(roster)
    .filter((l) => l.lamps.some(
      (d) => d.state === "working" && !d.reviewDetectable))
    .map((l) => l.seat);
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
