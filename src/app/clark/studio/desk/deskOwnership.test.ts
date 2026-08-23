/**
 * "Whose move is it" on the CEO's desk — the third stage, and the number.
 *
 * THE INCIDENT, the CEO in his own words (2026-08-22): *"they sustain on my
 * queue even if that work has been done"*, and *"since morning my desk has
 * stale; out of order and poorly designed stuff. Making my flow messy"*.
 *
 * The page had its own status-label rule and the spine's counter had another.
 * On one live payload they rendered 11 and 6 for the same question, eight
 * pixels apart on the same line. This file pins the repair: ONE definition, in
 * the spine, read off the row — and the rows it routes away stay on the page.
 *
 * Run: `node --experimental-strip-types --test src/app/clark/studio/desk/deskOwnership.test.ts`
 */

import { strict as assert } from "node:assert";
import { test } from "node:test";
import { readFileSync } from "node:fs";

import {
  type DeskItem, recItems, splitDeskItems, stageOfItem,
} from "./execDesk.ts";
import { hasContent, officerDesk } from "./officerQueues.ts";

const rec = (o: Record<string, unknown>) =>
  ({ run_id: "r1", rec_id: 1, seat: "pm", kind: "process", status: "open",
     text: "t", task: "task", artifact_path: null, trace_id: null,
     ...o }) as never;

const run = (o: Record<string, unknown> = {}) =>
  ({ run_id: "r1", seat: "pm", task: "t",
     resolved_at: "2026-08-21T10:00:00+00:00", ...o }) as never;

const item = (o: Partial<DeskItem>): DeskItem => ({
  key: "k", kind: "recommendation", moneyUsd: null,
  reversibility: "reversible", waitingSince: null, dueDate: null, ...o,
});

/* ----------------------------------------------------------- the stage --- */

test("an open row the CEO must decide awaits his decision", () => {
  assert.equal(
    stageOfItem(item({ nextActor: "ceo", rec: rec({ status: "open" }) })),
    "awaiting_decision");
});

test("a DECIDED row is awaiting execution — the CEO's complaint, pinned", () => {
  for (const status of ["accepted", "staged"]) {
    assert.equal(
      stageOfItem(item({ nextActor: "chair", rec: rec({ status }) })),
      "awaiting_execution", status);
  }
});

test("a DECIDED row the CEO must still act on stays HIS — the kill, pinned", () => {
  /* THE INCIDENT (adversary kill, 2026-08-22, on this file's own first cut).
   *
   * The test above pinned "decided => awaiting execution" using ONLY
   * `nextActor: "chair"` — the one case where the spine and the page agree —
   * and so it went green over a function that returned before it ever read the
   * field. The case it never tested is the case the field exists FOR: the
   * constitution's preserved COO objection, verbatim, "items at status
   * `accepted` whose execution requires the CEO personally (three live today,
   * including PM R1, the largest-money decision in the firm)".
   *
   * `desk.py::next_actor` ranks the explicit field ABOVE the lifecycle, so the
   * spine counts such a row as CEO load. The page filed it under "shown, never
   * counted". Server 1, page 0, eight pixels apart — the 11-vs-6 divergence
   * this whole module was written to eliminate, reintroduced by the field that
   * eliminates it.
   *
   * A test that cannot bless the bug: it fails if the accepted/staged shortcut
   * is ever restored above the actor read, in either status. */
  for (const status of ["accepted", "staged"]) {
    assert.equal(
      stageOfItem(item({ nextActor: "ceo", rec: rec({ status }) })),
      "awaiting_decision", `${status} + next_actor ceo`);
    // And the other half of the same defect: an explicit value the SPINE could
    // not parse resolves to `unknown`, which also counts toward the CEO
    // (`desk_load` sums ceo + unknown). A decided row must not swallow it.
    assert.equal(
      stageOfItem(item({ nextActor: "unknown", rec: rec({ status }) })),
      "awaiting_decision", `${status} + next_actor unknown`);
  }
});

test("a decided row owned elsewhere is a PROMISE, not somebody else's ticket", () => {
  /* The distinction the repair must not flatten while fixing the one above.
   * `chair`/`seat`/`nobody` on an OPEN row means nobody decided it and it was
   * never the CEO's (`owned_elsewhere`); the same actor on a DECIDED row means
   * he said yes and the firm owes him the execution (`awaiting_execution`).
   * Both are uncounted, and reporting the second as the first would drop a
   * promise the firm actually made. */
  for (const actor of ["chair", "seat", "nobody"]) {
    assert.equal(
      stageOfItem(item({ nextActor: actor, rec: rec({ status: "accepted" }) })),
      "awaiting_execution", `accepted + ${actor}`);
    assert.equal(
      stageOfItem(item({ nextActor: actor, rec: rec({ status: "open" }) })),
      "owned_elsewhere", `open + ${actor}`);
  }
});

test("an OPEN row owned by the chair is neither his decision nor a promise", () => {
  /* The distinction that earns the third stage. Nobody decided it, so calling
   * it "decided, awaiting execution" would report a promise the firm never
   * made; nobody is waiting on the CEO, so counting it is the complaint. */
  for (const actor of ["chair", "seat", "nobody"]) {
    assert.equal(
      stageOfItem(item({ nextActor: actor, rec: rec({ status: "open" }) })),
      "owned_elsewhere", actor);
  }
});

test("an UNKNOWN owner stays with the CEO", () => {
  /* Absence is never zero, including the absence of an answer about who owns a
   * row. Routing an unreadable row away would make it disappear from the one
   * number that is supposed to tell him what he still owes. */
  assert.equal(
    stageOfItem(item({ nextActor: "unknown", rec: rec({ status: "open" }) })),
    "awaiting_decision");
});

test("a pending ORDER is the CEO's decision whatever else is true", () => {
  assert.equal(stageOfItem(item({ kind: "order", nextActor: "chair" })),
               "awaiting_decision");
});

test("a spine with no routing falls back to the OLD rule, never to a guess", () => {
  /* Degrading to the previous behaviour is the only safe direction: guessing
   * would put the page back to having its own second definition. */
  assert.equal(stageOfItem(item({ rec: rec({ status: "open" }) })),
               "awaiting_decision");
  assert.equal(stageOfItem(item({ rec: rec({ status: "accepted" }) })),
               "awaiting_execution");
});

/**
 * The source-text census of `stageOfItem`, comments stripped.
 *
 * THE INCIDENT this shape is written from (adversary kill, 2026-08-22): the
 * previous version of the test below was TITLED "never re-derives the routing
 * from kind or status" and grepped the body for `KIND_ACTORS` and
 * `"awaits-ceo"` — and **never for `status`**, which was literally in the slice
 * it read, deciding the answer one line above the field it did assert on. A
 * test whose title names a token it never greps for is a green light you built
 * yourself.
 *
 * So this does not grep for a blacklist. It enumerates EVERY string literal and
 * EVERY `i.…` field read in the function and requires each one to be on a
 * reviewed allowlist. A token nobody reviewed fails the test BY NAME, which is
 * the only version of this check that cannot go quietly green over a rule
 * somebody added.
 */
function stageOfItemCensus(): {
  literals: Set<string>; fields: Set<string>; body: string;
} {
  const src = readFileSync(new URL("./execDesk.ts", import.meta.url), "utf8");
  /* The slice ends at the NEXT top-level `export`, not at a named landmark.
   * A named end-marker is a landmark that moves: adding an unrelated export
   * between `stageOfItem` and the old marker (`export interface DeskSplit`)
   * silently widened this census to cover code it was never meant to judge,
   * which it caught on itself within the hour of being written. A slice that
   * can drift is a source assertion that can quietly stop being about its
   * subject. */
  const start = src.indexOf("export function stageOfItem");
  const after = src.slice(start + 1);
  const rel = after.indexOf("\nexport ");
  const raw = rel >= 0 ? src.slice(start, start + 1 + rel) : src.slice(start);
  /* Guards, because a census over nothing passes every assertion it makes. */
  if (start < 0 || !raw.includes("DeskStage") || raw.length > 4000) {
    throw new Error(
      `the stageOfItem slice looks wrong (${raw.length} chars). A census over `
      + "the wrong text is worse than no census.");
  }
  // Comments carry the why and are prose; a sentence about `accepted` is not a
  // re-derivation of it. Strip them before tokenising, or the census measures
  // the documentation instead of the code.
  const body = raw.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/\/\/[^\n]*/g, " ");
  const literals = new Set<string>();
  for (const m of body.matchAll(/"([^"\\]*(?:\\.[^"\\]*)*)"|'([^'\\]*(?:\\.[^'\\]*)*)'/g)) {
    literals.add(m[1] ?? m[2] ?? "");
  }
  const fields = new Set<string>();
  for (const m of body.matchAll(/\bi\s*(?:\?\.|\.)\s*(\w+)(?:\s*(?:\?\.|\.)\s*(\w+))?/g)) {
    fields.add(m[2] ? `${m[1]}.${m[2]}` : m[1]);
  }
  return { literals, fields, body };
}

test("the page NEVER re-derives the routing — every token is on the allowlist", () => {
  const { literals, fields, body } = stageOfItemCensus();

  /* What the function is ALLOWED to say, and why each entry is here. Adding a
   * token means editing this list, which means somebody read it. */
  const ALLOWED_LITERALS = new Set([
    // The item discriminant — an order, not a recommendation's `kind`.
    "order",
    // The two lifecycle statuses, and ONLY these two. `desk.py` treats
    // accepted/staged as "the CEO already decided"; the client reads the same
    // pair for the same reason and reads no other status at all.
    "accepted", "staged",
    // The spine's five actors, verbatim from `desk.py::NEXT_ACTORS`. A sixth
    // one appearing here would be the client inventing routing.
    "ceo", "unknown", "chair", "seat", "nobody",
    // Its own three return values.
    "awaiting_decision", "awaiting_execution", "owned_elsewhere",
  ]);
  const ALLOWED_FIELDS = new Set([
    "kind",        // DeskItem.kind — "order" | "recommendation"
    "rec.status",  // the lifecycle, for the decided/open split ONLY
    "nextActor",   // the spine's answer
  ]);

  const uncheckedLiterals = [...literals].filter((x) => !ALLOWED_LITERALS.has(x));
  const uncheckedFields = [...fields].filter((x) => !ALLOWED_FIELDS.has(x));

  /* Print the census every run, per the brief: run the assertion against your
   * own source and say what it did NOT check. An empty remainder is a claim
   * this test earns rather than implies. */
  console.log(
    "  [census] stageOfItem literals:", [...literals].sort().join(" ")
    + "\n  [census] stageOfItem i.<field> reads:", [...fields].sort().join(" ")
    + `\n  [census] unchecked: literals=[${uncheckedLiterals.join(",")}] `
    + `fields=[${uncheckedFields.join(",")}]`);

  assert.deepEqual(uncheckedLiterals, [],
    "a string literal in stageOfItem that nobody put on the allowlist — either "
    + "it is a re-derivation of the spine's routing, or the allowlist above "
    + "needs a line saying why it is not");
  assert.deepEqual(uncheckedFields, [],
    "stageOfItem reads a field the allowlist does not cover; every input to "
    + "this predicate must be a reviewed one");

  // The positives, stated so the census cannot pass by the function being empty.
  assert.ok(fields.has("nextActor"), "the stage must read the spine's field");
  assert.ok(!body.includes("KIND_ACTORS"),
    "no kind table may be re-implemented on the client");
  assert.ok(!fields.has("rec.kind"),
    "the recommendation's KIND must not reach this predicate: `kind` is free "
    + "text (84 distinct values over 219 rows) and routing on it is the spine's "
    + "job, done once, in `desk.py::KIND_ACTORS`");
});

test("the ACTOR is read BEFORE the status shortcut can return — the kill, in source", () => {
  /* The behavioural pin is above; this pins the SHAPE, because the defect was
   * an ORDERING and an ordering is what a future edit will get wrong again.
   * The first `awaiting_execution` return must not sit above the first read of
   * the spine's actor — that single line of precedence is the whole kill. */
  const { body } = stageOfItemCensus();
  const firstActorRead = body.indexOf("nextActor");
  const firstDecidedReturn = body.indexOf('"awaiting_execution"');
  /* The guard is not ceremony: a source assertion whose landmark has moved
   * finds nothing and passes, which is the same green-light-you-built-yourself
   * failure this whole file is being repaired from. It has already fired once
   * — the first draft looked for the string `return "awaiting_execution"` and
   * the repaired function returns it from a ternary. */
  assert.ok(firstActorRead >= 0 && firstDecidedReturn >= 0,
    `both landmarks must exist for this assertion to mean anything `
    + `(nextActor@${firstActorRead}, "awaiting_execution"@${firstDecidedReturn})`);
  assert.ok(firstActorRead < firstDecidedReturn,
    "stageOfItem returned `awaiting_execution` before it had read "
    + "`nextActor` — that is the accepted-row-owned-by-the-CEO defect the "
    + "adversary killed on 2026-08-22, exactly as it was written the first time");
});

/* ------------------------------------------------------------ the split -- */

test("the split loses nothing across all three queues", () => {
  const items = recItems([
    rec({ rec_id: 1, status: "open", next_actor_resolved: "ceo" }),
    rec({ rec_id: 2, status: "accepted", next_actor_resolved: "chair" }),
    rec({ rec_id: 3, status: "open", kind: "build",
          next_actor_resolved: "chair" }),
    rec({ rec_id: 4, status: "open", kind: "handoff_to_quant",
          next_actor_resolved: "seat" }),
  ], [run()]);
  const s = splitDeskItems(items);
  assert.equal(s.awaitingDecision.length, 1);
  assert.equal(s.awaitingExecution.length, 1);
  assert.equal(s.ownedElsewhere.length, 2);
  assert.equal(
    s.awaitingDecision.length + s.awaitingExecution.length
      + s.ownedElsewhere.length,
    items.length, "every item must land in exactly one queue");
});

/* --------------------------------------------------------- the queues ---- */

test("chair-owned rows are SHOWN and NOT COUNTED", () => {
  /* Both halves matter and they pull in opposite directions. Counting them was
   * the complaint; hiding them would be a worse answer to it — "do not solve a
   * counting problem by hiding work". */
  const mine = recItems([rec({ rec_id: 1, status: "open",
                               next_actor_resolved: "ceo" })], [run()]);
  const theirs = recItems([rec({ rec_id: 2, status: "open", kind: "build",
                                 next_actor_resolved: "chair" })], [run()]);
  const d = officerDesk({
    awaitingDecision: mine, awaitingExecution: [], ownedElsewhere: theirs,
    memos: [], asks: [],
  });
  assert.equal(d.awaitingTotal, 1, "only the CEO's row counts");
  assert.equal(d.others.elsewhere.length, 1, "and the chair's row is still here");
  assert.ok(hasContent(d.others));
});

test("a queue holding ONLY somebody else's work is not empty", () => {
  /* `hasContent` decides whether a queue renders at all. If it ignored the new
   * bucket, an officer whose entire output was engineering tickets would
   * vanish from the page — hiding by omission rather than by filtering. */
  const theirs = recItems([rec({ rec_id: 2, seat: "validator", status: "open",
                                 kind: "harness",
                                 next_actor_resolved: "chair" })], [run()]);
  const d = officerDesk({
    awaitingDecision: [], awaitingExecution: [], ownedElsewhere: theirs,
    memos: [], asks: [],
  });
  assert.equal(d.awaitingTotal, 0);
  assert.ok(hasContent(d.others), "a queue of others' work must still render");
});

test("a caller that predates the third stage still works", () => {
  const d = officerDesk({
    awaitingDecision: [], awaitingExecution: [], memos: [], asks: [],
  });
  assert.equal(d.others.elsewhere.length, 0);
  assert.equal(d.awaitingTotal, 0);
});

test("the CEO page renders the routed-away rows and says why", () => {
  const src = readFileSync(new URL("./ceo/page.tsx", import.meta.url), "utf8");
  assert.ok(src.includes("ownedElsewhere: split.ownedElsewhere"),
    "the page must pass the third queue through to the officer routing");
  assert.ok(src.includes("Open, and not yours"),
    "the routed-away rows need a door of their own");
  assert.ok(src.includes("next_actor_why"),
    "each routed row must carry the spine's reason, so a reader can disagree");
  assert.ok(src.includes("more on file, at the foot"),
    "the headline must say that the rows which left the count are still on "
    + "the page — taking work off the number must not take it off the screen");
});

test("the decision list comes FIRST and the folded doors come after", () => {
  /* THE RESTRUCTURE, pinned in source (2026-08-22). Measured on the page this
   * replaces: the first Accept button sat 11,608px — 14.7 screenfuls — below
   * the CEO's name, behind 49,549 characters, and the largest block on the
   * page was a section headed "0 awaiting you".
   *
   * A source-order assertion is a weak proxy for a layout and it is stated as
   * one; the strong check is the DOM measurement in the dispatch report. What
   * this catches is the cheap regression: somebody adding a section above the
   * list because it seemed important, which is exactly how the old page grew.
   */
  const src = readFileSync(new URL("./ceo/page.tsx", import.meta.url), "utf8");
  const list = src.indexOf("1 · THE DECISION LIST");
  const doors = src.indexOf("2 · EVERYTHING ELSE, BEHIND NAMED DOORS");
  assert.ok(list > 0 && doors > 0, "both landmarks must exist");
  assert.ok(list < doors, "the decision list must precede the folded doors");

  /* The only things allowed above the list are the ones that change what a
   * click on it DOES, or say the page cannot be trusted. */
  const above = src.slice(0, list);
  for (const allowed of ["THE HALT", "CONTRACT DRIFT"]) {
    assert.ok(above.includes(allowed),
      `${allowed} is one of the two blocks that may sit above the list`);
  }
  for (const banned of ["MemoCard key=", "DailyMemoCard memo", "AskRow key"]) {
    assert.ok(!above.includes(banned),
      `${banned} renders above the decision list — memos, the daily and the `
      + "ask queue are the three blocks that were measured at 708, 951 and "
      + "9,596 pixels of already-read text above the first Accept button");
  }
});

test("the header count and the card count are ONE number in the source", () => {
  /* INTENT UNCHANGED, LETTER REWRITTEN (2026-08-23, D28) — and the rewrite is
   * itself a finding. This test used to require the header to render
   * `officers.awaitingTotal`, the PAGE's own fold. That is precisely the
   * behaviour D28 was dispatched to remove: the header now renders the
   * SERVED counter through `awaitingHeadline`, because rendering the page's
   * fold beside the spine's chip put 96 and 97 on consecutive lines.
   *
   * Worse, the old assertions had stopped testing code. `officers.awaitingTotal`
   * survived only inside a COMMENT explaining the invariant, and the test
   * passed on prose — the same trap as grepping source text for a name (D20).
   * Everything below reads comment-stripped source.
   *
   * The property is stronger now: exactly ONE call computes the figure,
   * exactly ONE expression renders it, and the cards it is reconciled against
   * are `decisionList`'s own total. That is how 11 and 6, then 1 and 0, then
   * 96 and 97 ended up on one screen. */
  const raw = readFileSync(new URL("./ceo/page.tsx", import.meta.url), "utf8");
  const src = raw.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^[ \t]*\/\/.*$/gm, "");
  assert.ok(src.includes("decisionList(officers,"),
    "the list must be built FROM the officer desk");
  const folds = [...src.matchAll(/awaitingHeadline\(\{/g)];
  assert.equal(folds.length, 1,
    `the figure is computed ${folds.length} times; it must have exactly one `
    + "source, because computing one quantity twice is how this page rendered "
    + "11 and 6 for the same question");
  assert.ok(src.includes("cardCount: list.total"),
    "the served figure must be reconciled against decisionList's own total, "
    + "not against a third count");
  // Every rendered figure reads the SAME fold. A second `officers.awaitingTotal`
  // anywhere in the code is the old defect returning under a new name.
  assert.ok(!/officers\.awaitingTotal/.test(src),
    "the page must not read the officer desk's total directly any more — the "
    + "served counter is the figure and headline.value is the only reader");
  // Both rendered figures read the SAME fold, named site by site rather than
  // tallied — a count of occurrences would move with an added `?:` and pin
  // nothing.
  assert.ok(src.includes(`{headline.value === null ? "unknown" : headline.value}`),
    "the header figure must be headline.value, and UNKNOWN when it is null");
  assert.ok(src.includes("needsYou={headline.value}"),
    "the greeting must read the same fold, which is what makes the two agree "
    + "by construction rather than by care");
});
