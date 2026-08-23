import test from "node:test";
import assert from "node:assert/strict";

import {
  brakeSummary, clampText, instructionCoverage, lineageFor, recRef, reqRef,
  servesRequests, supersessionCheckIsAlarm, supersessionCheckOf,
  supersessionCheckSentence, unreadableStages, worstSupersessionCheck,
} from "./lineage.ts";
import type {
  DeskSupersessionEdge, DeskView, SpineEvent,
} from "@/lib/fund_api";

/**
 * LINEAGE — the chain behind one row.
 *
 * THE INCIDENT THIS FILE'S CENTRAL TEST GUARDS (D22 review, 2026-08-23). The
 * spine writes `supersession_readable` onto the decision and approval events
 * so that an approval taken while the edge store was down is distinguishable
 * in the record from a verified one. The review found the field appeared in
 * the repo exactly ONCE — inside the sentence promising it. Nothing read it.
 * This module is its first reader, and the four-valued test below is what
 * stops the reader collapsing back into a boolean, which is the same defect
 * with a consumer attached.
 *
 * Measured on the live event log 2026-08-23, and the reason the four values
 * are not academic: of 551 `DeskRecommendationDecided` events, 80 carried
 * `true`, 1 carried `null` (a non-advancing status — no check was due), and
 * 470 carried the key not at all (they predate the disclosure). Re-measured
 * ninety minutes later: 88 / 1 / 470. The disclosed count grows with the
 * day, the pre-disclosure tail is frozen at 470, and — the invariant that
 * matters — **ZERO carry `false`, in both readings.** The alarm has never fired, which is exactly when a reader is
 * cheapest to get wrong, so every branch below is driven by a fixture.
 */

const T = "2026-08-23T12:00:00+00:00";

function ev(type: string, payload: Record<string, unknown>,
            over: Partial<SpineEvent> = {}): SpineEvent {
  return {
    event_id: `e-${type}-${JSON.stringify(payload).length}`, seq: 1,
    aggregate_id: "a", aggregate_type: "desk_run", type,
    payload, actor: "cto", ts: T, ...over,
  };
}

function desk(over: Partial<DeskView> = {}): DeskView {
  return {
    roster: [], protocol: [], artifacts: [], requests: [], runs: [],
    open_recommendations: [], open_requests: 0, kills: 0,
    execution_note: "", note: "", ...over,
  } as unknown as DeskView;
}

const edge = (over: Partial<DeskSupersessionEdge> = {}): DeskSupersessionEdge => ({
  edge_id: "edge-1", target_ref: "rec:run-a#1", superseder_ref: "rec:run-b#2",
  mode: "superseded", reason: "replaced by R39", dies_at_event: null,
  revives_if: null, applied_by: "cto", applied_at: T, ...over,
});

/* ------------------------------------------------- the D22 disclosure ---- */

test("supersession_readable is FOUR-valued and none of the four is another", () => {
  assert.equal(supersessionCheckOf({ supersession_readable: true }), "checked");
  assert.equal(supersessionCheckOf({ supersession_readable: false }),
               "not_consulted");
  assert.equal(supersessionCheckOf({ supersession_readable: null }),
               "not_applicable");
  assert.equal(supersessionCheckOf({}), "undisclosed",
    "a key that is absent is an event predating the disclosure — writing "
    + "`false` there would claim an outage that never happened");
  assert.equal(supersessionCheckOf(null), "undisclosed");
  assert.equal(supersessionCheckOf("nope"), "undisclosed");
  assert.equal(supersessionCheckOf({ supersession_readable: "yes" }),
               "undisclosed",
    "a truthy value the disclosure does not define must NOT read as checked");
  assert.equal(supersessionCheckOf({ supersession_readable: 0 }), "undisclosed",
    "and a falsy one must not read as an outage either");
});

test("exactly ONE of the four states is an alarm", () => {
  assert.equal(supersessionCheckIsAlarm("not_consulted"), true);
  for (const c of ["checked", "not_applicable", "undisclosed"] as const) {
    assert.equal(supersessionCheckIsAlarm(c), false,
      `${c} must not shout — a warning that fires on every row stops being read`);
  }
});

test("the NOT-CONSULTED sentence says what happened and what it costs", () => {
  const s = supersessionCheckSentence("not_consulted");
  assert.match(s, /NOT CONSULTED/);
  assert.match(s, /unreadable/);
  assert.match(s, /recorded anyway/);
  // The other three must not be alarming prose.
  assert.match(supersessionCheckSentence("checked"), /was consulted/);
  assert.match(supersessionCheckSentence("not_applicable"), /no brake check was due/);
  assert.match(supersessionCheckSentence("undisclosed"), /UNKNOWN rather than no/);
});

test("the worst finding in a chain is the one the drawer reports", () => {
  const base = lineageFor({ kind: "request", requestId: "r" },
                          { desk: null, events: null, edges: null });
  assert.equal(worstSupersessionCheck(base), null,
    "a chain disclosing nothing must return null, not a reassuring value");

  const mk = (vals: (boolean | null | undefined)[]) => {
    const events = vals.map((v, i) => ev("DeskRecommendationDecided", {
      run_id: "run-a", rec_id: 1, status: "accepted", at: `2026-08-2${i}`,
      ...(v === undefined ? {} : { supersession_readable: v }),
    }));
    return worstSupersessionCheck(lineageFor(
      { kind: "rec", runId: "run-a", recId: 1 },
      { desk: desk(), events, edges: [] }));
  };
  assert.equal(mk([true, false]), "not_consulted",
    "one skipped brake outranks any number of clean ones");
  assert.equal(mk([true, null, undefined]), "checked");
  assert.equal(mk([null, undefined]), "not_applicable");
  assert.equal(mk([undefined]), "undisclosed");
});

/* ------------------------------------------------------ serves_requests -- */

test("servesRequests reads a declaration and refuses everything else", () => {
  assert.deepEqual(servesRequests({ meta: { serves_requests: ["a", "b"] } }),
                   ["a", "b"]);
  assert.deepEqual(servesRequests({ meta: { serves_requests: [] } }), [],
    "a run that carries the key and declares nothing declares nothing");
  assert.deepEqual(servesRequests({ meta: { serves_requests: ["", "  ", "x"] } }),
                   ["x"]);
  assert.deepEqual(servesRequests({ meta: { serves_requests: "a" } }), [],
    "a string is not a list; coercing it would invent an edge");
  assert.deepEqual(servesRequests({ meta: {} }), []);
  assert.deepEqual(servesRequests({ meta: null }), []);
  assert.deepEqual(servesRequests({}), []);
  assert.deepEqual(servesRequests(null), []);
});

test("the canonical refs match the spine's own spelling", () => {
  assert.equal(recRef("run-a", 3), "rec:run-a#3");
  assert.equal(reqRef("abc"), "req:abc");
});

/* --------------------------------------------------------- the full chain */

function fullChain() {
  const runs = [{
    run_id: "run-builder-d31", seat: "builder", task: "redesign the desk",
    resolved_at: T, artifact_path: "docs/x.md", verdict: "shipped",
    trace_id: "trace-1",
    meta: { serves_requests: ["req-1"] },
    recommendations: [
      { rec_id: 1, seat: "builder", status: "accepted", text: "do the thing" },
    ],
  }];
  const requests = [{
    request_id: "req-1", kind: "build", serves: "builder", seat: "builder",
    subject: "redesign the desk", task: "redesign the desk",
    status: "resolved", at: "2026-08-22T09:00:00+00:00",
    approved_by: "ceo", approved_at: "2026-08-22T10:00:00+00:00",
    resolved_at: T, resolution: "EXECUTED: merged", trace_id: "trace-1",
  }];
  const events: SpineEvent[] = [
    ev("DeskRequestApproved",
       { request_id: "req-1", supersession_readable: true }),
    ev("DeskDispatched",
       { request_id: "req-1", task_id: "task-1", seat: "builder", at: T }),
    ev("DeskRecommendationDecided", {
      run_id: "run-builder-d31", rec_id: 1, status: "accepted", at: T,
      note: "CEO decision, verbatim: ship it", supersession_readable: true,
    }, { actor: "ceo" }),
    ev("DeskRequestResolved",
       { request_id: "req-1", resolution: "EXECUTED: merged", at: T }),
  ];
  return {
    desk: desk({ runs, requests } as Partial<DeskView>),
    events,
    edges: [edge({ target_ref: "rec:run-builder-d31#1" })],
    runsDeclaringService: 2, runsRead: 117,
  };
}

test("a complete chain finds all seven stages, and names the join", () => {
  const l = lineageFor({ kind: "request", requestId: "req-1" }, fullChain());
  for (const [name, st] of Object.entries({
    request: l.request, dispatches: l.dispatches, runs: l.runs,
    recommendations: l.recommendations, decisions: l.decisions,
    execution: l.execution, supersessions: l.supersessions,
  })) {
    assert.equal(st.state, "found", `${name} should be found`);
    assert.ok(st.rows.length > 0, `${name} should carry rows`);
  }
  assert.equal(l.runs.rows[0].joinedBy, "serves_requests",
    "a DECLARED join must be labelled as one — a shared trace id is a weaker "
    + "claim and must not borrow the declaration's credibility");
  assert.match(l.joinNote, /serves_requests/);
  assert.equal(l.request.rows[0].approvalSupersessionReadable, "checked");
  assert.equal(l.decisions.rows[0].verbatim, "CEO decision, verbatim: ship it");
  assert.equal(l.execution.rows[0].text, "EXECUTED: merged");
});

test("a rec anchor walks BACK to the ask through the declaration", () => {
  const l = lineageFor({ kind: "rec", runId: "run-builder-d31", recId: 1 },
                       fullChain());
  assert.equal(l.request.state, "found");
  assert.equal(l.request.rows[0].requestId, "req-1");
});

test("a trace-id join is labelled as the weaker claim it is", () => {
  const src = fullChain();
  // Strip the declaration; only the shared trace remains.
  (src.desk.runs[0] as { meta?: unknown }).meta = {};
  const l = lineageFor({ kind: "request", requestId: "req-1" }, src);
  assert.equal(l.runs.rows[0].joinedBy, "trace_id");
  assert.match(l.joinNote, /weaker claim/);
});

/* ------------------------------------------------------- the absences ---- */

test("the three stores fail INDEPENDENTLY, and each says UNKNOWN alone", () => {
  /* A page that rendered "no lineage" because only the edge table was down
   * would make an outage look like a clean record — which is precisely the
   * failure the D22 disclosure was written against. */
  const src = fullChain();

  const noDesk = lineageFor({ kind: "request", requestId: "req-1" },
                            { ...src, desk: null });
  assert.equal(noDesk.request.state, "unreadable");
  assert.equal(noDesk.runs.state, "unreadable");
  /* THE JOIN'S INPUT FAILED, NOT THE LOG — and this must not render as "no
   * decision". A request owns no rec of its own; which rows belong to it is
   * enumerated from the desk's run list, so an unreadable desk leaves the log
   * with nothing to be asked about. Reporting `absent` here would have been an
   * outage wearing an empty record's clothes, and the first cut did exactly
   * that. */
  assert.equal(noDesk.decisions.state, "unreadable");
  assert.match(noDesk.decisions.note, /The event log was read, but the desk was not/);
  /* A REC anchor is different and must stay different: it names its own row,
   * so the log alone can answer for it. */
  const noDeskRec = lineageFor({ kind: "rec", runId: "run-builder-d31", recId: 1 },
                               { ...src, desk: null });
  assert.equal(noDeskRec.decisions.state, "found",
    "a rec anchor names its own row, so the log alone can answer for it");
  /* THE WARNING NAMES THE STORE THAT FAILED, NOT THE STAGE THAT WENT QUIET.
   * Only the desk was unreadable here; naming the event log — which answered
   * perfectly — would send a reader to investigate a healthy store. The first
   * cut of `unreadableStages` inferred the store from the stage and did
   * exactly that. */
  assert.deepEqual(unreadableStages(noDesk), ["the desk"]);

  const noLog = lineageFor({ kind: "request", requestId: "req-1" },
                           { ...src, events: null });
  assert.equal(noLog.dispatches.state, "unreadable");
  assert.equal(noLog.decisions.state, "unreadable");
  assert.equal(noLog.execution.state, "unreadable");
  assert.equal(noLog.request.state, "found");
  assert.equal(noLog.request.rows[0].approvalSupersessionReadable, "undisclosed",
    "an unreadable log cannot vouch that the brake ran");
  assert.deepEqual(unreadableStages(noLog), ["the event log"]);

  const noEdges = lineageFor({ kind: "request", requestId: "req-1" },
                             { ...src, edges: null });
  assert.equal(noEdges.supersessions.state, "unreadable");
  assert.match(noEdges.supersessions.note, /UNKNOWN — not no/);
  assert.equal(noEdges.request.state, "found");
  assert.deepEqual(unreadableStages(noEdges), ["the supersession store"]);
});

test("an empty edge store is ABSENT, and says it was READ", () => {
  const l = lineageFor({ kind: "request", requestId: "req-1" },
                       { ...fullChain(), edges: [] });
  assert.equal(l.supersessions.state, "absent");
  assert.match(l.supersessions.note, /was read and holds no edge/,
    "'read and empty' and 'could not be read' are different facts and only "
    + "one of them is reassuring");
});

test("a rec with no request says the CHAIN STARTS AT THE RUN, not that nobody asked", () => {
  const src = fullChain();
  (src.desk.runs[0] as { meta?: unknown }).meta = {};
  (src.desk.runs[0] as { trace_id?: string | null }).trace_id = null;
  const l = lineageFor({ kind: "rec", runId: "run-builder-d31", recId: 1 }, src);
  assert.equal(l.request.state, "absent");
  assert.match(l.request.note, /bookkeeping gap/);
  assert.match(l.request.note, /not evidence that nobody asked for it/);
  // The run itself is still reachable: a chain missing its head is not a
  // chain missing everything.
  assert.equal(l.runs.state, "found");
  assert.equal(l.runs.rows[0].joinedBy, "direct");
});

test("an unjoined row quotes the FIRM-WIDE coverage, not just its own emptiness", () => {
  /* Measured 2026-08-23: 2 of 117 runs declared service, 2 of 119 ninety
   * minutes later — a frozen numerator over a growing denominator. The
   * FIXTURE pins 2/117 because the sentence must reproduce whatever figures
   * it is given; the live pair is the reason the sentence exists. Without it
   * a reader would conclude this ROW is undocumented, when the truth is that
   * the join is 2% populated firm-wide. */
  const l = lineageFor({ kind: "request", requestId: "nope" },
                       { desk: desk(), events: [], edges: [],
                         runsDeclaringService: 2, runsRead: 117 });
  assert.equal(l.runs.state, "absent");
  assert.match(l.runs.note, /2 of 117 runs firm-wide/);
  assert.match(l.runs.note, /the norm and not a fact about this row/);
});

test("no coverage figure is stated as UNKNOWN coverage, never as good coverage", () => {
  const l = lineageFor({ kind: "request", requestId: "nope" },
                       { desk: desk(), events: [], edges: [] });
  assert.match(l.runs.note, /reported no coverage figure/);
  assert.ok(!/\d+ of \d+ runs/.test(l.runs.note));
});

test("a zero denominator does not produce a divide-by-nothing sentence", () => {
  const l = lineageFor({ kind: "request", requestId: "nope" },
                       { desk: desk(), events: [], edges: [],
                         runsDeclaringService: 0, runsRead: 0 });
  assert.match(l.runs.note, /reported no coverage figure/,
    "0 of 0 says nothing and must not be printed as though it did");
});

/* -------------------------------------------------- execution evidence --- */

test("an ACCEPTED recommendation is NOT evidence that anything was done", () => {
  /* THE DISCIPLINE OF THIS STAGE. The desk records that a decision was MADE
   * in several places and that it was CARRIED OUT in exactly one: the
   * resolution on the request. Treating `status: accepted` as execution is
   * the "EXECUTED" text-grep this desk was repaired from. */
  const src = fullChain();
  src.events = src.events.filter((e) => e.type !== "DeskRequestResolved");
  const l = lineageFor({ kind: "rec", runId: "run-builder-d31", recId: 1 }, src);
  assert.equal(l.decisions.state, "found");
  assert.equal(l.decisions.rows[0].status, "accepted");
  assert.equal(l.execution.state, "absent",
    "an accepted row with no resolved request is a decision made and not yet "
    + "evidenced");
  assert.match(l.execution.note, /decision made and\s+not yet evidenced/);
  assert.match(l.execution.note, /different from one that failed/);
});

test("a resolution with no text is a closure the record cannot describe", () => {
  const src = fullChain();
  src.events = src.events.map((e) => e.type === "DeskRequestResolved"
    ? ev("DeskRequestResolved", { request_id: "req-1", resolution: "  " })
    : e);
  const l = lineageFor({ kind: "request", requestId: "req-1" }, src);
  assert.equal(l.execution.rows[0].text,
    "resolved with no resolution text recorded");
});

/* ---------------------------------------------------------- the words ---- */

test("an EMPTY instruction is no instruction, never empty quotation marks", () => {
  /* Measured 2026-08-23: 300 of 551 decision events carried a note, 308 of
   * 559 ninety minutes later — the ratio holds near 55%. The spine
   * writes "" when the decider typed nothing. */
  for (const note of ["", "   ", null, undefined, 7]) {
    const l = lineageFor({ kind: "rec", runId: "run-a", recId: 1 }, {
      desk: desk(), edges: [],
      events: [ev("DeskRecommendationDecided",
                  { run_id: "run-a", rec_id: 1, status: "accepted",
                    ...(note === undefined ? {} : { note }) })],
    });
    assert.equal(l.decisions.rows[0].verbatim, null,
      `a note of ${JSON.stringify(note)} must not render as a quotation`);
  }
});

test("decisions are ordered oldest first, so a chain reads forwards", () => {
  const events = [
    ev("DeskRecommendationDecided",
       { run_id: "run-a", rec_id: 1, status: "accepted", at: "2026-08-23" }),
    ev("DeskRecommendationDecided",
       { run_id: "run-a", rec_id: 1, status: "open", at: "2026-08-21" }),
  ];
  const l = lineageFor({ kind: "rec", runId: "run-a", recId: 1 },
                       { desk: desk(), events, edges: [] });
  assert.deepEqual(l.decisions.rows.map((d) => d.status), ["open", "accepted"],
    "the event feed is newest-first; a lineage that inherited that order "
    + "would show the outcome above the cause");
});

test("a decision event for ANOTHER row is not part of this chain", () => {
  const events = [
    ev("DeskRecommendationDecided", { run_id: "run-a", rec_id: 2, status: "x" }),
    ev("DeskRecommendationDecided", { run_id: "run-b", rec_id: 1, status: "y" }),
    ev("DeskRecommendationDecided", { run_id: "run-a", rec_id: 1, status: "mine" }),
  ];
  const l = lineageFor({ kind: "rec", runId: "run-a", recId: 1 },
                       { desk: desk(), events, edges: [] });
  assert.deepEqual(l.decisions.rows.map((d) => d.status), ["mine"]);
});

test("an edge that REPLACES this row is in the chain as well as one that kills it", () => {
  /* Both directions: the row I am looking at may be the target OR the
   * superseder. A chain that only followed one would leave a reader unable to
   * see what a row replaced. */
  const l = lineageFor({ kind: "rec", runId: "run-b", recId: 2 }, {
    desk: desk(), events: [],
    edges: [edge({ target_ref: "rec:run-a#1", superseder_ref: "rec:run-b#2" })],
  });
  assert.equal(l.supersessions.state, "found");
  assert.equal(l.supersessions.rows[0].target_ref, "rec:run-a#1");
});

/* ------------------------------------------------------- the roll-ups ---- */

test("the ALARM is never rolled away, and is named in the summary too", () => {
  /* FOUND BY LOOKING AT THE RENDERED DRAWER, not by this suite: a 17-decision
   * chain printed the same reassuring brake sentence seventeen times, in a
   * panel whose whole job is to be read. The roll-up is the repair — and its
   * one hard rule is that summarising must not be able to hide the row that
   * matters. */
  const s = brakeSummary(["checked", "checked", "not_consulted", "undisclosed"]);
  assert.equal(s.alarms, 1);
  assert.equal(s.checked, 2);
  assert.equal(s.undisclosed, 1);
  assert.match(s.line!, /^supersession brake: 1 recorded WITHOUT/,
    "the alarm must come FIRST in the line — a reader scanning only the "
    + "summary must not have to read past two reassurances to find it");
  assert.match(s.line!, /2 checked/);
  assert.match(s.line!, /1 predating the disclosure \(UNKNOWN, not no\)/);
});

test("a clean chain's summary states what it checked, never 'all clear'", () => {
  const s = brakeSummary(["checked", "checked"]);
  assert.equal(s.alarms, 0);
  assert.equal(s.line, "supersession brake: 2 checked");
  assert.ok(!/clear|fine|ok/i.test(s.line!));
});

test("a chain that discloses nothing says UNKNOWN, and an empty one says nothing", () => {
  assert.equal(brakeSummary(["undisclosed", "undisclosed"]).line,
    "supersession brake: 2 predating the disclosure (UNKNOWN, not no)");
  assert.equal(brakeSummary([]).line, null,
    "a stage with no rows has nothing to summarise, and an empty summary line "
    + "would be a claim about a population that does not exist");
});

test("the summary's four counters partition the input", () => {
  const input = ["checked", "not_consulted", "not_applicable", "undisclosed",
                 "checked"] as const;
  const s = brakeSummary([...input]);
  assert.equal(s.alarms + s.checked + s.notApplicable + s.undisclosed,
               input.length, "every row lands in exactly one counter");
});

test("instruction coverage is a RATIO, and says nothing when nothing is missing", () => {
  assert.equal(instructionCoverage([{ verbatim: "x" }, { verbatim: "y" }]), null,
    "a sentence that fires when there is nothing to report is noise");
  assert.equal(instructionCoverage([]), null);
  assert.match(instructionCoverage([{ verbatim: "x" }, { verbatim: null }])!,
               /1 of 2 carry/);
  assert.match(instructionCoverage([{ verbatim: null }])!, /0 of 1 carries/,
    "one row is singular; the desk has shipped 'row of that are' before");
});

test("clampText makes its clamp visible and leaves short text alone", () => {
  assert.equal(clampText("short", 40), "short");
  assert.equal(clampText("  a   b  ", 40), "a b", "whitespace is normalised");
  const long = "x".repeat(300);
  const out = clampText(long, 50);
  assert.equal(out.length, 50);
  assert.ok(out.endsWith("…"), "a silent truncation is a lie about the record");
  assert.equal(clampText(null, 10), "");
  assert.equal(clampText(undefined, 10), "");
  // A string EXACTLY at the limit is not clamped — an off-by-one here would
  // put an ellipsis on text that fits.
  assert.equal(clampText("y".repeat(50), 50), "y".repeat(50));
  assert.ok(clampText("y".repeat(51), 50).endsWith("…"));
});
