import test from "node:test";
import assert from "node:assert/strict";

import { deskLanes, lanesAccountedFor, laneCount, decidedCount, utcDay } from "./deskLanes.ts";
import type {
  DeskSupersessionEdge, DeskView,
} from "@/lib/fund_api";

/**
 * THE LANES.
 *
 * The property under test everywhere below is the same one: **a lane's number
 * is the FUND'S number and its rows are this page's fold, and where they
 * differ the lane says so.** Measured live 2026-08-23: `desk_load` reported
 * 162 decided-awaiting-execution (167 ninety minutes later) while the
 * recommendation feed the page can render carried a different subset. The
 * totals move with the day; the DISAGREEMENT is what holds, which is why no
 * figure below is hardcoded into the module.
 *
 * A lane printing its own row count as the fund's figure is the
 * quantity-computed-twice defect for the fourth time on this desk; a lane
 * printing the fund's figure over fewer rows in silence is worse, because the
 * reader believes they have seen everything.
 */

const NOW = "2026-08-23T16:49:27+00:00";

type Rec = DeskView["open_recommendations"][number];
type Req = DeskView["requests"][number];

function rec(over: Partial<Rec> = {}): Rec {
  return {
    rec_id: 1, seat: "pm", status: "open", text: "a row",
    run_id: "run-a", task: "t",
    ...over,
  } as Rec;
}

function req(over: Partial<Req> = {}): Req {
  return {
    request_id: "req-1", kind: "build", serves: "builder",
    subject: "do the thing", status: "approved",
    ...over,
  } as Req;
}

function desk(over: Partial<DeskView> = {}): DeskView {
  return {
    roster: [], protocol: [], artifacts: [], requests: [], runs: [],
    open_recommendations: [], open_requests: 0, kills: 0,
    execution_note: "", note: "",
    ...over,
  } as unknown as DeskView;
}

function lanes(over: Partial<DeskView> = {}, extra: Record<string, unknown> = {}) {
  return deskLanes({
    desk: desk(over),
    read: "readable",
    awaitingShown: 0,
    awaitingServed: 0,
    blocked: new Map<string, DeskSupersessionEdge>(),
    now: NOW,
    ...extra,
  });
}

const laneById = (ls: ReturnType<typeof deskLanes>, id: string) =>
  ls.find((l) => l.id === id)!;

/* ------------------------------------------------------------ laneCount -- */

test("a served figure equal to the rows renders as ONE number", () => {
  const c = laneCount(5, 5, "x");
  assert.equal(c.value, 5);
  assert.equal(c.source, "spine");
  assert.equal(c.note, null, "there is nothing for a reader to reconcile");
});

test("a served figure LARGER than the rows says both, and why", () => {
  const c = laneCount(162, 40, "decided work");
  assert.equal(c.value, 162, "the FUND's figure is the lane's number");
  assert.equal(c.shown, 40);
  assert.match(c.note!, /162/);
  assert.match(c.note!, /40/);
  assert.match(c.note!, /not resolved/,
    "a reader must not read 'outside the payload' as 'already done'");
});

test("MORE rows than the fund counts is a disagreement, not a rounding", () => {
  /* The loud case. Two folds disagreeing about which rows EXIST is a finding,
   * and clamping to either would throw it away. */
  const c = laneCount(3, 9, "decided work");
  assert.equal(c.value, 3);
  assert.equal(c.shown, 9);
  assert.match(c.note!, /disagreement about which rows exist/);
  assert.match(c.note!, /neither figure is safe alone/);
});

test("no served figure falls back to the page's count AND says so", () => {
  for (const absent of [null, undefined, Number.NaN]) {
    const c = laneCount(absent as number | null, 4, "today's resolutions");
    assert.equal(c.value, 4);
    assert.equal(c.source, "page",
      "a figure this build computed is a different claim from the fund's");
    assert.match(c.note!, /Counted by this page, not by the fund/);
    assert.match(c.note!, /today's resolutions/);
  }
});

test("a served ZERO is the fund's zero, not a missing figure", () => {
  const c = laneCount(0, 0, "x");
  assert.equal(c.source, "spine");
  assert.equal(c.note, null);
});

/* -------------------------------------------------------------- utcDay --- */

test("utcDay is UTC and refuses what it cannot parse", () => {
  assert.equal(utcDay("2026-08-23T23:59:59+00:00"), "2026-08-23");
  assert.equal(utcDay("2026-08-24T00:00:01+00:00"), "2026-08-24");
  // The fund's day is UTC: an instant late in the UTC day must not roll back
  // to the previous day because the browser sits west of Greenwich.
  assert.equal(utcDay("2026-08-23T20:00:00-05:00"), "2026-08-24");
  assert.equal(utcDay(null), null);
  assert.equal(utcDay(undefined), null);
  assert.equal(utcDay("never"), null);
});

/* ------------------------------------------------- b. decided, awaiting -- */

test("the decided lane names WHO HAS IT NOW, per row", () => {
  const ls = lanes({
    open_recommendations: [
      rec({ status: "accepted", next_actor_resolved: "chair",
            next_actor_why: "the chair stages accepted rows",
            decided_by: "ceo", decided_at: "2026-08-23T08:00:00+00:00" }),
      rec({ rec_id: 2, status: "staged", next_actor: "seat" }),
    ],
    desk_load: { decided_awaiting_execution: 162 } as DeskView["desk_load"],
  });
  const d = laneById(ls, "decided");
  assert.equal(d.count.value, 162, "the lane's number is the fund's");
  assert.equal(d.rows.length, 2);
  assert.equal(d.rows[0].actor, "chair");
  assert.equal(d.rows[0].detail, "decided by ceo");
  assert.equal(d.rows[1].actor, "seat",
    "`next_actor` is read when the spine resolved none — a row is not "
    + "unowned because it predates the resolution field");
  assert.equal(d.openByDefault, false);
});

test("a decided row whose event named no actor SAYS so", () => {
  const ls = lanes({ open_recommendations: [rec({ status: "accepted" })] });
  const d = laneById(ls, "decided");
  assert.equal(d.rows[0].detail,
    "decided — the decision event recorded no actor");
  assert.equal(d.rows[0].actor, null,
    "a row with no routing is a finding; the view renders it as one");
});

test("`unknown` is not an actor", () => {
  const ls = lanes({
    open_recommendations: [rec({ status: "accepted",
                                 next_actor_resolved: "unknown" })] });
  assert.equal(laneById(ls, "decided").rows[0].actor, null,
    "the spine's own word for 'I could not tell' must not render as a person");
});

test("an OPEN row is not decided, and a rejected one is not either", () => {
  const ls = lanes({
    open_recommendations: [
      rec({ status: "open" }), rec({ rec_id: 2, status: "rejected" }),
      rec({ rec_id: 3, status: "done" }), rec({ rec_id: 4, status: "noted" }),
    ] });
  assert.equal(laneById(ls, "decided").rows.length, 0,
    "only accepted and staged are decided-and-not-yet-executed");
});

/* ----------------------------------------- c. approved, awaiting dispatch */

test("the dispatch lane is the chair's, and every row says so", () => {
  const ls = lanes({
    requests: [
      req({ approved_by: "ceo", approved_at: "2026-08-22T09:00:00+00:00" }),
      req({ request_id: "req-2", status: "open" }),
      req({ request_id: "req-3", status: "resolved" }),
    ],
    desk_load: { requests_approved_undispatched: 65 } as DeskView["desk_load"],
  });
  const d = laneById(ls, "dispatch");
  assert.equal(d.count.value, 65);
  assert.equal(d.rows.length, 1, "only APPROVED asks are awaiting dispatch");
  assert.equal(d.rows[0].actor, "chair");
  assert.equal(d.rows[0].detail, "approved by ceo");
  assert.match(d.rows[0].actorWhy!, /the approval is not itself a trigger/,
    "the constitution's chain must be on the row: a seat files, the CEO "
    + "approves, the CHAIR triggers");
});

test("an approved ask with no approver named says so rather than blank", () => {
  const ls = lanes({ requests: [req()] });
  assert.equal(laneById(ls, "dispatch").rows[0].detail,
    "approved — the approval event recorded no actor");
});

test("an ask with no subject renders a sentence, not an empty row", () => {
  const ls = lanes({
    requests: [req({ subject: undefined, task: undefined } as Partial<Req>)] });
  assert.equal(laneById(ls, "dispatch").rows[0].text,
    "this ask recorded no subject");
});

/* ------------------------------------------------------ d. open elsewhere */

test("open-elsewhere excludes the CEO's own rows and the unrouted ones", () => {
  const ls = lanes({
    open_recommendations: [
      rec({ rec_id: 1, status: "open", next_actor_resolved: "chair" }),
      rec({ rec_id: 2, status: "open", next_actor_resolved: "ceo" }),
      rec({ rec_id: 3, status: "open" }),
      rec({ rec_id: 4, status: "accepted", next_actor_resolved: "chair" }),
    ],
    desk_load: { open_elsewhere: 46 } as DeskView["desk_load"],
  });
  const e = laneById(ls, "elsewhere");
  assert.equal(e.count.value, 46);
  assert.deepEqual(e.rows.map((r) => r.key), ["run-a#1"],
    "the CEO's own row belongs to lane (a); an unrouted row counts toward HIS "
    + "figure by the spine's own rule, so it is not somebody else's; and a "
    + "decided row is lane (b)");
  assert.match(e.rows[0].actorWhy!, /the spine stated no reason/);
});

/* --------------------------------------------------------- e. resolved --- */

test("resolved-today is the FUND's UTC day, not the browser's", () => {
  /* THE `now` HERE IS DELIBERATELY NOT THE WALL CLOCK, and that is the whole
   * test. A mutation swapping `utcDay(now)` for `utcDay(new Date()...)`
   * SURVIVED the first version of this test, because the fixture's day
   * happened to be the day the suite ran: the assertion could not tell the
   * fund's clock from the machine's. The spine's `at` is the fund's day, a
   * desk read at 23:50Z is a different day from the same desk read ten
   * minutes later, and a browser west of Greenwich is a day behind for
   * several hours of every day. */
  const FIXED = "2020-02-29T12:00:00+00:00";
  assert.notEqual(utcDay(FIXED), utcDay(new Date().toISOString()),
    "this fixture's day must differ from the day the suite runs, or the "
    + "assertion below cannot distinguish the two clocks");
  const ls = lanes({
    requests: [
      req({ request_id: "y", status: "resolved",
            resolved_at: "2020-02-29T00:00:01+00:00", resolution: "did it" }),
      req({ request_id: "n", status: "resolved",
            resolved_at: "2020-02-28T23:59:59+00:00", resolution: "yesterday" }),
      req({ request_id: "t", status: "resolved",
            resolved_at: new Date().toISOString(),
            resolution: "closed on the machine's today, not the fund's" }),
    ] }, { now: FIXED });
  const r = laneById(ls, "resolved");
  assert.deepEqual(r.rows.map((x) => x.key), ["req:y"],
    "only the row closed on the FUND's day belongs in this lane");
  assert.equal(r.rows[0].detail, "did it");
  assert.equal(r.count.source, "page",
    "`desk_load` counts what is OPEN; there is no served figure for what "
    + "closed today, and the lane must say the number is its own");
});

test("a resolution with no text is a CLOSURE WITH NO RECORD, said plainly", () => {
  const ls = lanes({
    requests: [req({ status: "resolved", resolved_at: NOW, resolution: "   " })] });
  assert.match(laneById(ls, "resolved").rows[0].detail!,
    /the record does not say what was done/);
});

test("resolved rows are newest first", () => {
  const ls = lanes({
    requests: [
      req({ request_id: "old", status: "resolved",
            resolved_at: "2026-08-23T01:00:00+00:00", resolution: "a" }),
      req({ request_id: "new", status: "resolved",
            resolved_at: "2026-08-23T15:00:00+00:00", resolution: "b" }),
    ] });
  assert.deepEqual(laneById(ls, "resolved").rows.map((r) => r.key),
                   ["req:new", "req:old"]);
});

/* --------------------------------------------------- the withdrawn rule -- */

test("a superseded row NEVER appears in an active lane, and is counted out", () => {
  /* The server refuses their approval, so a lane listing one would be
   * offering a control that fails. Removing them silently would be worse: a
   * row that vanishes is a row nobody can revive. */
  const blocked = new Map<string, DeskSupersessionEdge>([
    ["run-a#1", { edge_id: "e", target_ref: "rec:run-a#1",
                  superseder_ref: "rec:run-b#3", mode: "superseded",
                  reason: "replaced", dies_at_event: null, revives_if: null,
                  applied_by: "cto", applied_at: null }],
    ["run-a#3", { edge_id: "e2", target_ref: "rec:run-a#3",
                  superseder_ref: null, mode: "killed",
                  reason: "killed", dies_at_event: null, revives_if: null,
                  applied_by: "cto", applied_at: null }],
  ]);
  const ls = deskLanes({
    read: "readable",
    desk: desk({ open_recommendations: [
      rec({ rec_id: 1, status: "accepted" }),
      rec({ rec_id: 2, status: "accepted" }),
      rec({ rec_id: 3, status: "open", next_actor_resolved: "chair" }),
      rec({ rec_id: 4, status: "open", next_actor_resolved: "chair" }),
    ] }),
    awaitingShown: 0, awaitingServed: 0, blocked, now: NOW,
  });
  const d = laneById(ls, "decided");
  const e = laneById(ls, "elsewhere");
  assert.deepEqual(d.rows.map((r) => r.key), ["run-a#2"]);
  assert.equal(d.withdrawn, 1, "the row removed must be COUNTED, not dropped");
  assert.deepEqual(e.rows.map((r) => r.key), ["run-a#4"]);
  assert.equal(e.withdrawn, 1);
});

/* ------------------------------------------------------- lane (a) & set -- */

test("lane (a) takes its two numbers from the caller, never from rows", () => {
  const ls = lanes({}, { awaitingShown: 27, awaitingServed: 28 });
  const a = laneById(ls, "awaiting");
  assert.equal(a.count.value, 28);
  assert.equal(a.count.shown, 27);
  assert.match(a.count.note!, /28/);
  assert.equal(a.rows.length, 0,
    "lane (a) renders the page's own decision CARDS, which carry approval "
    + "controls this module must not re-implement");
  assert.equal(a.openByDefault, true, "it is the only lane open by default");
});

test("exactly one lane opens by default, and the five ids are stable", () => {
  const ls = lanes();
  assert.deepEqual(ls.map((l) => l.id),
    ["awaiting", "decided", "dispatch", "elsewhere", "resolved"]);
  assert.equal(ls.filter((l) => l.openByDefault).length, 1);
  assert.equal(ls[0].openByDefault, true);
});

test("an unreadable desk yields five lanes of UNKNOWN, never five zeroes", () => {
  /* THIS TEST FOUND A REAL DEFECT IN THE MODULE ON ITS FIRST RUN, and the
   * defect was the absence-as-zero error inside the desk whose whole
   * discipline is that absence is never zero: with no served figure,
   * `laneCount` fell back to the page's row count, and on an unreadable desk
   * that count is 0 — so all five lanes rendered a confident zero over a
   * queue nobody had looked at. `read` is the repair. */
  const ls = deskLanes({
    desk: null, read: "unreadable", awaitingShown: 0, awaitingServed: null,
    blocked: new Map(), now: NOW,
  });
  assert.equal(ls.length, 5);
  for (const l of ls) {
    assert.equal(l.count.value, null, `${l.id} must be UNKNOWN, not 0`);
    assert.equal(l.count.source, "unknown");
    assert.match(l.count.note!, /Neither the fund nor this page could count/);
    assert.match(l.count.note!, /Anything waiting is still waiting/);
  }
  assert.equal(lanesAccountedFor(ls), 0);
});

test("a readable desk with an empty lane renders the fund's or the page's ZERO", () => {
  /* The other side of the same boundary, and it must NOT be swept up by the
   * repair above: a desk that WAS read and holds nothing for a lane is a
   * measurement, and rendering "unknown" there would be an outage wearing an
   * empty queue's clothes. */
  const ls = lanes();
  const r = laneById(ls, "resolved");
  assert.equal(r.count.value, 0);
  assert.equal(r.count.source, "page");
  assert.match(r.count.note!, /Counted by this page/);
});

test("a served figure survives an unreadable page, and says the rows are missing", () => {
  /* `read: "unreadable"` must only govern the FALLBACK. A spine that counted
   * 162 still counted 162; what the page cannot do is show the rows. */
  const c = laneCount(162, 0, "decided work", "unreadable");
  assert.equal(c.value, 162);
  assert.equal(c.source, "spine");
  assert.match(c.note!, /this page can render 0 of them/);
});

test("lanesAccountedFor sums the rendered rows and excludes lane (a)'s cards", () => {
  const ls = lanes({
    open_recommendations: [rec({ status: "accepted" })],
    requests: [req()],
  }, { awaitingShown: 9, awaitingServed: 9 });
  assert.equal(lanesAccountedFor(ls), 2,
    "lane (a)'s nine cards are rendered by the page, not held here");
});


/* ------------------------------------------------ decidedCount (lane b) --- */

test("decidedCount: same partition agrees -> total shown, remainder NAMED not alarmed", () => {
  /* The live 169-vs-187 of 2026-08-24: 18 decided rows whose next act is also
   * the CEO's. Both folds right; the old guard called it an existence
   * disagreement. */
  const c = decidedCount(169, 169, 187);
  assert.equal(c.value, 187);
  assert.equal(c.shown, 187);
  assert.equal(c.source, "page");
  assert.match(c.note!, /187 decided in all/);
  assert.match(c.note!, /169 awaiting\s+someone else/);
  assert.match(c.note!, /18 are decided rows/);
  assert.match(c.note!, /Awaiting you as well/);
  assert.doesNotMatch(c.note!, /disagreement about which rows exist/);
});

test("decidedCount: no remainder -> clean count, no note", () => {
  const c = decidedCount(12, 12, 12);
  assert.equal(c.value, 12);
  assert.equal(c.note, null);
});

test("decidedCount: singular remainder reads as one row", () => {
  const c = decidedCount(5, 5, 6);
  assert.match(c.note!, /1 is a decided\s+row/);
});

test("decidedCount: a GENUINE partition disagreement still alarms, shown = total", () => {
  /* served 10 vs sameBasis 14 is a real existence dispute; the alarm and the
   * spine-sourced value survive, and shown reports what the lane renders. */
  const c = decidedCount(10, 14, 20);
  assert.equal(c.value, 10);
  assert.equal(c.shown, 20);
  assert.equal(c.source, "spine");
  assert.match(c.note!, /disagreement about which rows exist/);
});

test("decidedCount: unreadable desk stays UNKNOWN, never a confident total", () => {
  const c = decidedCount(null, 0, 0, "unreadable");
  assert.equal(c.value, null);
  assert.equal(c.source, "unknown");
  assert.match(c.note!, /UNKNOWN/);
});
