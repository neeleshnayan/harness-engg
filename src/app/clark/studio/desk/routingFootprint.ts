/**
 * THE ROUTING FOOTPRINT — what a seat's filings look like at the desk's door.
 *
 * THE BRIEF ASKED FOR SOMETHING THE SPINE DOES NOT SERVE, AND THIS IS THE
 * HONEST NEIGHBOUR OF IT. The ask was: *"a filing whose response carried
 * `routing_advisory` renders the advisory against the filing seat"*. Measured
 * against the running spine before a line of this was written:
 *
 *   `routing_advisory` is built in `app/api/v1/fund.py:2006` and returned ONLY
 *   on the 200 body of `POST /fund/desk/runs`. It is not stored, and no GET
 *   returns it. `ROUTING_REQUIRED_FIELDS` has no GET either.
 *
 * So a browser cannot read the advisory: the POST that produces it is made by
 * the chair's tooling, and its response is gone by the time any page loads.
 * The two ways to put something on screen anyway were:
 *
 *   (a) re-implement `desk.routing_errors()` in TypeScript over the served
 *       rows — a SECOND COPY OF A LAW in production code, which this codebase
 *       forbids for the reason it keeps re-learning: two definitions of one
 *       rule are two rules, and only one of them gets updated; or
 *   (b) render the STORED footprint of the same machinery.
 *
 * (b) is what this does. `route_at_birth()` stamps `routing_rules_version` onto
 * every recommendation whose `next_actor` it could route, so the field's
 * presence on a stored row is the spine's own record that the row went through
 * routing. Its ABSENCE is reported as exactly what it is — no routing version
 * recorded — and NOT as "this row would have been advised", because a row filed
 * before routing v1 existed is grandfathered and looks identical.
 *
 * Measured live 2026-08-23, twice and ninety minutes apart: 16 of 232
 * recommendations in the feed carried `routing_rules_version`, then 22 of
 * 238. BOTH numbers move, which is the useful fact — new filings are
 * adopting routing v1 while the grandfathered tail stays put, so roughly
 * nine in ten rows carry no version and that share is falling slowly. The
 * gap against the ~123 rows carrying any `next_actor` at all is the
 * grandfathered population, and it is why this reports a footprint rather
 * than a verdict.
 */

import type { DeskRecommendation } from "@/lib/fund_api";

export interface SeatRouting {
  seat: string;
  /** Rows in the feed filed by this seat. */
  filed: number;
  /** Rows carrying `routing_rules_version` — routed at the door. */
  declared: number;
  /** Rows carrying none. NOT the same as rows that would be refused. */
  undeclared: number;
  /** Of the undeclared rows, how many state no `next_actor` either. These are
   *  the ones routing v1 exists for: the desk's default sends an unrouted row
   *  to the chair, and a reader is entitled to see how much of the chair's
   *  queue is the default doing its job. */
  unrouted: number;
}

export interface RoutingFootprint {
  seats: SeatRouting[];
  filed: number;
  declared: number;
  /** The sentence that must travel with the numbers. */
  note: string;
}

type Rec = Pick<DeskRecommendation, "seat" | "next_actor">
  & { routing_rules_version?: string | null };

/**
 * Per seat, in the order the caller supplies (the matrix's own seat order — a
 * second sort here would put the board's rows and this block out of step).
 *
 * A seat with no rows in the feed still gets a row, with zeroes. That zero is
 * honest for once: the feed was read, and this seat filed nothing in it.
 */
export function routingFootprint(
  recs: Rec[] | null | undefined, seats: string[],
): RoutingFootprint | null {
  // NULL IS NOT AN EMPTY FOOTPRINT. A caller that could not read the feed must
  // render an outage, and returning zeroes here would hand it a clean board.
  if (!recs) return null;

  const blank = (): SeatRouting => ({
    seat: "", filed: 0, declared: 0, undeclared: 0, unrouted: 0,
  });
  const by = new Map<string, SeatRouting>();
  for (const s of seats) by.set(s, { ...blank(), seat: s });

  let filed = 0;
  let declared = 0;
  for (const r of recs) {
    const seat = (r.seat ?? "").trim() || "unattributed";
    let row = by.get(seat);
    if (!row) {
      row = { ...blank(), seat };
      by.set(seat, row);
    }
    const hasVersion = typeof r.routing_rules_version === "string"
      && r.routing_rules_version.trim().length > 0;
    const hasActor = typeof r.next_actor === "string"
      && r.next_actor.trim().length > 0;
    row.filed += 1;
    filed += 1;
    if (hasVersion) { row.declared += 1; declared += 1; }
    else {
      row.undeclared += 1;
      if (!hasActor) row.unrouted += 1;
    }
  }

  return {
    seats: Array.from(by.values()),
    filed,
    declared,
    note:
      `${declared} of ${filed} recommendation(s) in the feed carry a routing `
      + "version — the spine's record that the row was routed at the door. "
      + "The advisory itself (`routing_advisory`) is returned only on the POST "
      + "that files a run and is served by no GET, so this is the stored "
      + "footprint of that machinery and not the advisory. A row with no "
      + "routing version was either filed before routing v1 or stated no "
      + "usable next actor; those look identical here and are not "
      + "distinguished.",
  };
}
