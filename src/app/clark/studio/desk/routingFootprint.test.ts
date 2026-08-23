import test from "node:test";
import assert from "node:assert/strict";

import { routingFootprint } from "./routingFootprint.ts";

/**
 * THE ROUTING FOOTPRINT.
 *
 * What this module is NOT is the point of it, so the tests pin that first:
 * it is not `routing_errors()`. That function lives in the spine and its
 * output reaches only the 200 body of `POST /fund/desk/runs`; no GET returns
 * it and `ROUTING_REQUIRED_FIELDS` has no GET either. A TypeScript
 * re-implementation would be a SECOND COPY OF A LAW in production code, free
 * to drift from the first, and only one of two copies ever gets updated.
 *
 * So what is measured here is the presence of the spine's own stamp,
 * `routing_rules_version`, which `desk.route_at_birth()` writes onto every row
 * whose next actor it could route. Its absence is reported as an absence and
 * never as a verdict — a row filed before routing v1 existed and a row that
 * stated no usable next actor look identical, and the note says so.
 */

const rec = (seat: string, over: Record<string, unknown> = {}) =>
  ({ seat, status: "open", text: "", rec_id: 1, ...over }) as Parameters<
    typeof routingFootprint>[0] extends (infer T)[] | null | undefined ? T : never;

test("an unreadable feed is NULL, never an empty footprint", () => {
  /* A caller handed zeroes would render a clean board over an outage. */
  assert.equal(routingFootprint(null, ["pm"]), null);
  assert.equal(routingFootprint(undefined, ["pm"]), null);
});

test("a readable but EMPTY feed is a footprint of zeroes", () => {
  const f = routingFootprint([], ["pm", "builder"])!;
  assert.equal(f.filed, 0);
  assert.equal(f.declared, 0);
  assert.deepEqual(f.seats.map((s) => s.seat), ["pm", "builder"]);
  assert.match(f.note, /0 of 0/);
});

test("seat order follows the caller, so the board and this block stay in step", () => {
  const f = routingFootprint([rec("builder"), rec("pm")],
                             ["coo", "pm", "builder"])!;
  assert.deepEqual(f.seats.map((s) => s.seat), ["coo", "pm", "builder"],
    "a second sort here would put the matrix's rows and this block out of "
    + "order, and a reader would compare row 1 with row 3");
});

test("declared, undeclared and unrouted are three different counts", () => {
  const f = routingFootprint([
    rec("pm", { routing_rules_version: "routing v1 (2026-08-23)",
                next_actor: "ceo" }),
    rec("pm", { next_actor: "chair" }),   // routed, but no version stamped
    rec("pm", {}),                        // no actor at all
    rec("pm", { routing_rules_version: "   ", next_actor: "ceo" }),
  ], ["pm"])!;
  const pm = f.seats[0];
  assert.equal(pm.filed, 4);
  assert.equal(pm.declared, 1, "a blank version string is not a declaration");
  assert.equal(pm.undeclared, 3);
  assert.equal(pm.unrouted, 1,
    "UNDECLARED AND UNROUTED ARE NOT THE SAME COUNT. Three rows carry no "
    + "usable routing version; only ONE of them also states no next actor. "
    + "The row with a blank version string and `next_actor: ceo` is "
    + "undeclared and routed, and the row with `next_actor: chair` is the "
    + "grandfathered case this footprint exists to keep visible without "
    + "calling it a fault.");
  assert.equal(pm.undeclared - pm.unrouted, 2,
    "two of the three undeclared rows told the desk whose move it is");
  assert.equal(f.filed, 4);
  assert.equal(f.declared, 1);
});

test("a whitespace next_actor is not an actor", () => {
  const f = routingFootprint([rec("pm", { next_actor: "  " })], ["pm"])!;
  assert.equal(f.seats[0].unrouted, 1);
});

test("a seat the board does not list still gets a row", () => {
  /* The board's seat list comes from the matrix; the feed can carry a seat the
   * matrix has not got to. Dropping it would hide filings. */
  const f = routingFootprint([rec("cfo")], ["pm"])!;
  assert.deepEqual(f.seats.map((s) => s.seat), ["pm", "cfo"]);
  assert.equal(f.seats[1].filed, 1);
});

test("a row with no seat is attributed to 'unattributed', not to the first seat", () => {
  const f = routingFootprint(
    [rec(""), rec("   ")] as unknown as Parameters<typeof routingFootprint>[0],
    ["pm"])!;
  const un = f.seats.find((s) => s.seat === "unattributed")!;
  assert.equal(un.filed, 2);
  assert.equal(f.seats.find((s) => s.seat === "pm")!.filed, 0);
});

test("the note carries BOTH numbers and refuses to be read as the advisory", () => {
  const f = routingFootprint([
    rec("pm", { routing_rules_version: "v1" }), rec("pm"), rec("pm"),
  ], ["pm"])!;
  assert.match(f.note, /1 of 3/);
  assert.match(f.note, /served by no GET/,
    "a reader must not take this for the advisory the spine builds at the POST");
  assert.match(f.note, /filed before routing v1|stated no usable next actor/);
  assert.match(f.note, /are not\s+distinguished/,
    "the two reasons a row carries no version look identical here and the "
    + "note must say so rather than implying a verdict");
});
