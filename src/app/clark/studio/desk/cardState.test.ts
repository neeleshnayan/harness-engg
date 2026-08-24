/**
 * The CEO's window — the client half.
 *
 * Run: `node --experimental-strip-types --test src/app/clark/studio/desk/cardState.test.ts`
 *
 * THE INCIDENT (2026-08-24). He accepted R39 (spine event seq 1281). The POST
 * returned 200, the page refetched, and the row came back WITH AN ACCEPT
 * BUTTON ON IT — because `accepted` with the next move still his renders
 * inside `awaiting_decision`, which had exactly one appearance. A successful
 * click and a dead click were the same picture, and he said so: *"Why is this
 * issue persisting; shakes my confidence that information is flowing
 * seemlessly in the org."*
 *
 * Live counts that morning (`GET /api/v1/fund/desk`, 227 open
 * recommendations; `/fund/desk/ceo`, 34 decisions): **14 of 34** rows are the
 * stuck-lamp shape, **52 of 227** were closed by the chair and labelled as
 * his, **2** rendered as a Python dict repr.
 */

import assert from "node:assert/strict";
import test from "node:test";

import type { DeskItem } from "./execDesk.ts";
import {
  adjudicationOf, cardText, cascadeChip, cascadeOf, closedByTheChair,
  executionYours, looksUnreadable, rowLamp,
} from "./cardState.ts";

/* ------------------------------------------------------------- fixtures --- */

const rec = (over: Record<string, unknown> = {}) => ({
  run_id: "r", rec_id: 1, seat: "pm", text: "a line", task: "t",
  status: "open", kind: "awaits-ceo", ...over,
}) as unknown as NonNullable<DeskItem["rec"]>;

const item = (over: Record<string, unknown> = {},
              recOver: Record<string, unknown> = {}): DeskItem => ({
  key: "rec:r:1", kind: "recommendation", moneyUsd: null,
  reversibility: "unclassified", waitingSince: null, dueDate: null,
  nextActor: "ceo", rec: rec(recOver), ...over,
}) as DeskItem;

/* ------------------------------------------------------ the stuck lamp ---- */

test("an accepted row whose execution is his is execution_yours", () => {
  assert.equal(
    executionYours(item({}, { status: "accepted", execution_yours: true })),
    true);
});

test("an undecided row is not — the two must never render alike", () => {
  assert.equal(executionYours(item({}, { execution_yours: false })), false);
});

test("the SPINE's answer wins over the local fallback", () => {
  /* Two implementations of one predicate is how this page and the counter
     came to read 11 and 6 for the same payload. The local computation exists
     ONLY for a spine that sends nothing, and must never override one that
     does — even when it disagrees. */
  const i = item({ nextActor: "chair" },
                 { status: "accepted", execution_yours: true });
  assert.equal(executionYours(i), true,
               "the spine said yes; the local rule would have said no");
  const j = item({ nextActor: "ceo" },
                 { status: "accepted", execution_yours: false });
  assert.equal(executionYours(j), false,
               "the spine said no; the local rule would have said yes");
});

test("an older spine with no field degrades to the OLD rule, not a guess", () => {
  assert.equal(executionYours(item({ nextActor: "ceo" },
                                   { status: "accepted" })), true);
  assert.equal(executionYours(item({ nextActor: "chair" },
                                   { status: "accepted" })), false);
  assert.equal(executionYours(item({ nextActor: "ceo" },
                                   { status: "open" })), false);
  // `unknown` stays with him: a row whose owner could not be read is work he
  // may still owe, and routing it away answers an unmeasurable with a zero.
  assert.equal(executionYours(item({ nextActor: "unknown" },
                                   { status: "staged" })), true);
});

test("an order is never execution_yours", () => {
  const order: DeskItem = { ...item(), kind: "order", rec: undefined };
  assert.equal(executionYours(order), false);
});

/* -------------------------------------------------------------- the lamp -- */

test("a decided row shows no Accept button at all", () => {
  /* THE FIX, IN ONE ASSERTION. Offering Accept on a row already accepted is
     what made a landed click indistinguishable from a dead one — and a second
     click writes a second decision event over a decision that happened. */
  const lamp = rowLamp(item({}, { status: "accepted", execution_yours: true,
                                  adjudication: {
                                    channel: "ceo", actor: "ceo",
                                    at: "2026-08-24T09:12:00+00:00",
                                    label: "approved by the CEO",
                                    citation: null, instruction: null } }),
                       { state: "idle" });
  assert.equal(lamp.showButtons, false);
  assert.equal(lamp.tone, "decided");
  assert.match(lamp.label ?? "", /execution yours/);
});

test("a decided row the chair owes says so, and differently", () => {
  const lamp = rowLamp(item({ nextActor: "chair" },
                            { status: "accepted", execution_yours: false }),
                       { state: "idle" });
  assert.equal(lamp.showButtons, false);
  assert.match(lamp.label ?? "", /the chair owes the execution/);
  assert.doesNotMatch(lamp.label ?? "", /execution yours/,
                      "146 of 227 live rows are accepted; only 14 are his");
});

test("an undecided row keeps its buttons and says nothing", () => {
  const lamp = rowLamp(item(), { state: "idle" });
  assert.equal(lamp.showButtons, true);
  assert.equal(lamp.label, null);
  assert.equal(lamp.tone, "actionable");
});

test("the click is answered before the refetch lands", () => {
  /* THE ONE-SECOND CRITERION. The refetch pulls seven endpoints and does not
     reliably finish inside a second; the lamp changes on the POST's response,
     which is the moment the spine actually recorded it. */
  const lamp = rowLamp(item(), { state: "landed", status: "accepted",
                                 at: "2026-08-24T09:12:00+00:00" });
  assert.equal(lamp.tone, "decided");
  assert.equal(lamp.showButtons, false);
  assert.match(lamp.label ?? "", /Recorded accepted/);
});

test("a failed click looks like a failure and keeps the buttons", () => {
  /* A decision that failed must not look like a decision that landed — and
     the row must still be clickable, because it is still open. */
  const lamp = rowLamp(item(), { state: "failed", message: "503" });
  assert.equal(lamp.tone, "failed");
  assert.equal(lamp.showButtons, true);
  assert.match(lamp.label ?? "", /Not recorded/);
});

test("a click in flight disables the buttons rather than hiding the row", () => {
  const lamp = rowLamp(item(), { state: "sending" });
  assert.equal(lamp.showButtons, false);
  assert.equal(lamp.tone, "sending");
});

/* --------------------------------------------------------- the dict repr -- */

const REPR = "{'id': 'O4', 'title': 'Validate the ids', 'detail': 'the rest'}";

test("the repaired line is used and the stored one is not shown", () => {
  const out = cardText(rec({ text: REPR, text_display: "Validate the ids",
                             text_detail: "the rest" }));
  assert.equal(out.headline, "Validate the ids");
  assert.equal(out.detail, "the rest");
  assert.equal(out.repaired, true);
});

test("an ordinary sentence is untouched and not marked repaired", () => {
  const out = cardText(rec({ text: "Trim TLT to 12% of NAV." }));
  assert.equal(out.headline, "Trim TLT to 12% of NAV.");
  assert.equal(out.repaired, false);
  assert.equal(out.detail, null);
});

test("a repr with NO spine annotation is flagged, never silently printed", () => {
  /* The third layer: an older spine, a cached response, a fixture. The row IS
     broken and the CEO should see that it is — a tidy blank would hide a
     defect behind good manners. */
  assert.equal(looksUnreadable(rec({ text: REPR })), true);
  assert.equal(cardText(rec({ text: REPR })).headline, REPR,
               "the record is still shown verbatim; nothing is invented");
});

test("a repaired row is no longer flagged unreadable", () => {
  assert.equal(looksUnreadable(rec({ text: REPR, text_display: "Validate" })),
               false);
});

test("prose that merely opens with a brace is not a payload", () => {
  assert.equal(looksUnreadable(rec({ text: "{this} and then a sentence." })),
               false);
});

test("an empty text is not a payload and not a crash", () => {
  assert.equal(looksUnreadable(rec({ text: "" })), false);
  assert.equal(cardText(undefined).headline, "");
  assert.equal(cardText(null).headline, "");
});

/* ------------------------------------------------------- who adjudicated -- */

const adj = (channel: string, over: Record<string, unknown> = {}) => ({
  channel, actor: channel, at: null, label: "l", citation: null,
  instruction: null, ...over,
});

test("a chair disposition is its own category", () => {
  /* CEO, verbatim: "I cant form a view of whats closed and adjudicated by
     you." 52 live rows, rendered as though he had approved them. */
  assert.equal(closedByTheChair(rec({ adjudication: adj("chair") })), true);
  assert.equal(closedByTheChair(rec({ adjudication: adj("ceo") })), false);
});

test("via-chair is NOT the chair's own — merging them answers 63 for 52", () => {
  /* `neelesh-via-cto` is HIS decision with the chair's hand on it. Eleven live
     rows. Different fact, different category. */
  assert.equal(closedByTheChair(rec({ adjudication: adj("via_chair") })),
               false);
  assert.equal(adjudicationOf(rec({ adjudication: adj("via_chair") }))?.channel,
               "via_chair");
});

test("an undecided row has no adjudication", () => {
  assert.equal(adjudicationOf(rec()), null);
  assert.equal(closedByTheChair(rec()), false);
});

test("a malformed adjudication is treated as absent, never as a channel", () => {
  assert.equal(adjudicationOf(rec({ adjudication: {} as never })), null);
  assert.equal(adjudicationOf(rec({ adjudication: "chair" as never })), null);
});

/* ------------------------------------------------------------- cascade ---- */

const cascade = (over: Record<string, unknown> = {}) => ({
  total: 3, done: 0, pending: 2, not_open: 1, members: [], note: "n", ...over,
});

test("a pending cascade names how many of how many", () => {
  assert.equal(cascadeChip(cascadeOf(rec({ cascade: cascade() }))),
               "Cascade pending · 2 of 3 undecided · 1 no longer on the open "
               + "desk, not counted as done");
});

test("a fully closed cascade shows NO chip", () => {
  /* A chip that fired on a finished bundle would be noise on every decided
     row, and noise on every row is how a warning stops being read. */
  assert.equal(
    cascadeChip(cascadeOf(rec({ cascade: cascade({ done: 3, pending: 0,
                                                   not_open: 0 }) }))),
    null);
});

test("members that left the open desk are reported, never counted as done", () => {
  const chip = cascadeChip(cascadeOf(rec({
    cascade: cascade({ done: 1, pending: 0, not_open: 2 }) })));
  assert.match(chip ?? "", /^Cascade · 1 of 3 confirmed closed/);
  assert.match(chip ?? "", /2 no longer on the open desk/);
  assert.doesNotMatch(chip ?? "", /3 of 3/,
                      "absent is not finished; only 1 is confirmed");
});

test("a row with no cascade renders nothing", () => {
  assert.equal(cascadeOf(rec()), null);
  assert.equal(cascadeChip(null), null);
});

test("a malformed cascade is absent, not a zeroed block", () => {
  assert.equal(cascadeOf(rec({ cascade: { note: "x" } as never })), null);
});

/* ------------------------------------------------------- the record row --- */

/* D42. THE INCIDENT (CEO, 2026-08-24): *"like WTF"* — an already-executed
   chair action rendered with Accept and Reject. The row is `open` and its
   `next_actor_resolved` is `nobody`. These four fail if it is ever offered a
   decision on this desk again. */

test("D42: a record row shows NO buttons and says why", () => {
  const lamp = rowLamp(
    item({ nextActor: "nobody" },
         { status: "open", next_actor_resolved: "nobody",
           next_actor_why: "the row states its next actor is the nobody" }),
    { state: "idle" });
  assert.equal(lamp.showButtons, false);
  assert.equal(lamp.tone, "record");
  assert.match(lamp.label ?? "", /Filed for the record/);
});

test("D42: an ordinary open row KEEPS its buttons — the guard must not close "
  + "the desk it was written to correct", () => {
  const lamp = rowLamp(item({ nextActor: "ceo" }, { status: "open" }),
                       { state: "idle" });
  assert.equal(lamp.showButtons, true);
  assert.equal(lamp.tone, "actionable");
  assert.equal(lamp.label, null);
});

test("D42: an open row that states NO actor keeps its buttons — absence is "
  + "not the spine saying nobody", () => {
  const lamp = rowLamp(item({ nextActor: null }, { status: "open" }),
                       { state: "idle" });
  assert.equal(lamp.showButtons, true);
});

test("D42: a DECIDED row routed to nobody still says who decided it — the "
  + "record branch must not swallow the acceptance sentence", () => {
  const lamp = rowLamp(
    item({ nextActor: "nobody" },
         { status: "accepted", next_actor_resolved: "nobody" }),
    { state: "idle" });
  assert.equal(lamp.tone, "decided");
  assert.match(lamp.label ?? "", /You accepted this/);
  assert.equal(lamp.showButtons, false);
});
