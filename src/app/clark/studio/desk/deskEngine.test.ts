/**
 * The desk engine's client half — and the one thing it must never start doing.
 *
 * The sharpest test in this file is `test the client never classifies a row`:
 * every category on screen must come from the spine's fold. This desk shipped
 * a counter reading 11 beside a page reading 6 because the page carried its
 * own status rule, and the matrix would reproduce that defect at four times
 * the surface area.
 */

import { strict as assert } from "node:assert";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import {
  CATEGORY_LABELS, actionable, badgeView, blockedRecs,
  cellKey, expandable, matrixRows, supersessionChip, truncationNote,
} from "./deskEngine.ts";
import type {
  CeoDeskView, DeskBriefing, DeskMatrix, DeskMatrixCell,
  DeskSupersessionEdge,
} from "@/lib/fund_api";

const HERE = dirname(fileURLToPath(import.meta.url));

function cell(count: number, shown = count): DeskMatrixCell {
  return { count, shown, truncated: count > shown, items: [] };
}

function matrix(over: Partial<DeskMatrix> = {}): DeskMatrix {
  return {
    categories: ["open", "ticking", "blocking", "closed"],
    definitions: { open: "o", ticking: "t", blocking: "b", closed: "c" },
    seats: ["pm", "builder"],
    cells: {
      pm: { open: cell(3), ticking: cell(1), blocking: cell(0), closed: cell(9) },
      builder: { open: cell(0), ticking: cell(2), blocking: cell(1), closed: cell(4) },
    },
    totals: { open: 3, ticking: 3, blocking: 1, closed: 13 },
    items_classified: 20,
    cell_limit: 25,
    note: "",
    ...over,
  };
}

function edge(over: Partial<DeskSupersessionEdge> = {}): DeskSupersessionEdge {
  return {
    edge_id: "e1", target_ref: "rec:run-pm-0908#1",
    superseder_ref: "rec:run-pm-r39#1",
    mode: "superseded", reason: "R39 buys the exits back",
    dies_at_event: null, revives_if: null,
    applied_by: "cto", applied_at: "2026-08-23T00:00:00+00:00",
    retracted_at: null,
    ...over,
  };
}

/* ------------------------------------------------------------- the rule -- */

test("the client never classifies a row — the spine's fold is the only classifier", () => {
  // A source-level assertion, deliberately. A behavioural one cannot see a
  // SECOND classifier added beside the first: the page would keep rendering
  // the spine's answer while a new local rule quietly disagreed somewhere
  // else. Grep the words that would have to appear.
  const src = readFileSync(join(HERE, "deskEngine.ts"), "utf8");
  for (const forbidden of [
    'category = "', "category: 'open'", 'category: "open"',
    'next_actor_resolved ===', 'status === "staged"', "status === 'staged'",
  ]) {
    assert.equal(src.includes(forbidden), false,
      `deskEngine.ts must not decide categories itself (found ${forbidden})`);
  }
});

/* ---------------------------------------------------------- matrixRows --- */

test("matrixRows keeps the spine's seat order and totals every column", () => {
  const rows = matrixRows(matrix());
  assert.deepEqual(rows.map((r) => r.seat), ["pm", "builder"]);
  assert.equal(rows[0].total, 13);
  assert.equal(rows[0].live, 4, "live excludes CLOSED — it is the seat's load");
  assert.equal(rows[1].total, 7);
  assert.equal(rows[1].live, 3);
});

test("a missing cell renders as an explicit zero rather than a ragged row", () => {
  const m = matrix({
    cells: { pm: { open: cell(2) } as unknown as Record<string, DeskMatrixCell> },
    seats: ["pm"],
  });
  const rows = matrixRows(m);
  assert.equal(rows[0].cells.blocking.count, 0);
  assert.equal(rows[0].total, 2);
});

test("an absent matrix yields no rows rather than throwing on a dead spine", () => {
  assert.deepEqual(matrixRows(null), []);
  assert.deepEqual(matrixRows(undefined), []);
  assert.deepEqual(matrixRows({ seats: undefined } as unknown as DeskMatrix), []);
});

test("only a non-empty cell is expandable", () => {
  assert.equal(expandable(cell(1)), true);
  assert.equal(expandable(cell(0)), false);
  assert.equal(expandable(undefined), false);
});

test("a capped cell says how much it is NOT showing, with both numbers", () => {
  const note = truncationNote(cell(40, 25));
  assert.ok(note && note.includes("25") && note.includes("40"),
    "a cap read as a count truncated this firm's first spend meter");
  assert.equal(truncationNote(cell(3)), null);
});

/* The COLLAPSED_BY_DEFAULT test was DELETED with the constant (D31,
   cleanup dce47670): DeskMatrix never imported it. The label-order half
   of it survives below, where it still pins something that ships. */

test("the four columns are in the CEO's own order", () => {
  assert.deepEqual(Object.keys(CATEGORY_LABELS),
    ["open", "ticking", "blocking", "closed"]);
});

test("cellKey is stable and distinguishes seats from categories", () => {
  assert.notEqual(cellKey("pm", "open"), cellKey("pm", "closed"));
  assert.notEqual(cellKey("pm", "open"), cellKey("builder", "open"));
});

test("no source file in this module carries a control character", () => {
  /* A LITERAL NUL SHIPPED IN THIS FILE and the suite could not see it.
   * `cellKey` was written with a NUL where a separator was meant; every
   * behavioural assertion above still passed, because a NUL separates two
   * strings perfectly well. What it does NOT do is survive review: git
   * classified the whole module as BINARY (`Bin 0 -> 10787 bytes` in
   * `diff --stat`), so the file would have reached the CTO as an unreadable
   * blob — a diff nobody can review is a diff nobody did.
   *
   * Caught by reading the diff summary at bundling time, eleven dispatches
   * running that the late pass finds what the tests cannot. This is the test
   * that could have. */
  for (const f of ["deskEngine.ts", "DeskMatrix.tsx", "EngineViews.tsx"]) {
    const src = readFileSync(join(HERE, f), "utf8");
    const bad = [...src].filter(
      (ch) => ch.charCodeAt(0) < 32 && ch !== "\n" && ch !== "\r" && ch !== "\t");
    assert.deepEqual(bad.map((c) => c.charCodeAt(0)), [],
      `${f} carries a control character — git will treat it as binary and the `
      + `diff becomes unreviewable`);
  }
});

/* -------------------------------------------------------- supersession --- */

test("a pending chip carries BOTH halves — the named event and the revival branch", () => {
  const chip = supersessionChip(edge({
    mode: "superseded_pending",
    dies_at_event: "R39 step 4 rebuy TLT/DBC",
    revives_if: "R39 stops at the probe",
  }));
  assert.ok(chip);
  assert.equal(chip.diesAt, "R39 step 4 rebuy TLT/DBC");
  assert.equal(chip.revivesIf, "R39 stops at the probe");
  assert.equal(chip.blocksApproval, true);
});

test("the pending wording names the click it exists to prevent", () => {
  const chip = supersessionChip(edge({ mode: "superseded_pending" }));
  assert.ok(chip!.detail.toLowerCase().includes("after the event"),
    "'pending' read as 'not yet decided' would invite the exact click that "
    + "strips $501.58 of dated exit coverage");
});

test("every live mode blocks approval, and a retracted edge blocks nothing", () => {
  for (const mode of ["superseded", "superseded_pending", "killed"] as const) {
    assert.equal(supersessionChip(edge({ mode }))!.blocksApproval, true, mode);
  }
  assert.equal(
    supersessionChip(edge({ retracted_at: "2026-08-24T00:00:00+00:00" })), null);
  assert.equal(supersessionChip(null), null);
  assert.equal(supersessionChip(undefined), null);
});

test("a killed row shows no lineage rather than an invented one", () => {
  const chip = supersessionChip(edge({ mode: "killed", superseder_ref: null }));
  assert.equal(chip!.superseder, null);
  assert.equal(chip!.label, "KILLED");
});

/* ------------------------------------------------------------ briefings -- */

test("an unreadable ledger reads UNKNOWN, never unverified", () => {
  const base: DeskBriefing = {
    path: "docs/coo/TRIAGE7.md", seat: "coo", who: "Vishesh", label: "Triage",
    title: "t", date: "2026-08-23", badge: "unknown",
    verified_by: null, verified_at: null, corrections: [],
  };
  assert.equal(badgeView(base).tone, "unknown");
  assert.equal(badgeView({ ...base, badge: "chair-unverified" }).tone, "unverified");
  assert.equal(badgeView({ ...base, badge: "chair-verified" }).tone, "verified");
  assert.notEqual(badgeView(base).text, badgeView({ ...base, badge: "chair-unverified" }).text);
});

/* --------------------------------------------------------- the headers --- */

function view(over: Partial<CeoDeskView> = {}): CeoDeskView {
  return {
    at: "2026-08-23T12:00:00+00:00", rules_version: "routing v1",
    greeting: { at: null, since: null, changed: "", needs_you: "", on_fire: "",
                hygiene: null, text: "" },
    decisions: { shown: 2, total: 2, truncated: false, ranked_by: "",
                 ranked_on_nothing: 0, items: [], note: "" },
    on_fire: { shown: 0, total: 0, items: [], risk_halted: null, definition: "" },
    briefings: null,
    matrix: matrix(),
    hygiene: null,
    blocked: { shown: 0, total: 0, items: [], note: "" },
    kill_shelf: { shown: 0, total: 1, items: [], note: "" },
    elsewhere: { by_actor: {}, by_source: {} },
    readable: { recommendations: true, supersessions: true, intray: true, risk: true },
    ...over,
  };
}

/* The `sectionCounts` and `hygieneLine` tests were DELETED with the
   functions they pinned (D31, cleanup dce47670). Neither had a
   production consumer: the desk header carries ONE number and a count
   per lane, and the hygiene sentence is served by the spine on
   `greeting.hygiene` and rendered verbatim. A test that keeps dead code
   alive is the accretion this ticket exists to reverse. */

/* ----------------------------------------------------------- actionable -- */

test("blockedRecs reads the UNCAPPED list, not the capped matrix cells", () => {
  // The hazard, stated: the matrix caps each cell at 25. A page that gathered
  // its blocked rows from there would silently miss the 26th — and the one row
  // a page must never miss is the one whose approve button has to be off. So
  // the fixture puts the blocked row ONLY in `blocked`, with the matrix cell
  // deliberately empty, and the map must still find it.
  const item = {
    source: "recommendation", ref: "rec:run-pm-0908#1", seat: "pm",
    title: "R37", kind: "policy", status: "staged", due_date: null,
    money_at_stake: null, reversibility: null, next_actor_resolved: "ceo",
    next_actor_basis: "kind", at: null, run_id: "run-pm-0908", rec_id: 1,
    supersession: edge({ mode: "superseded_pending" }),
  } as CeoDeskView["blocked"]["items"][number];
  const v = view({ blocked: { shown: 1, total: 1, items: [item], note: "" } });
  const map = blockedRecs(v);
  assert.equal(map.size, 1);
  assert.ok(map.has("run-pm-0908#1"));
  assert.equal(map.get("run-pm-0908#1")!.mode, "superseded_pending");
});

test("blockedRecs is empty rather than throwing when the engine is unreadable", () => {
  assert.equal(blockedRecs(null).size, 0);
  assert.equal(blockedRecs(view()).size, 0);
});

test("blockedRecs ignores rows with no run/rec identity", () => {
  const item = {
    source: "request", ref: "req:q1", seat: "adversary", title: "x",
    kind: "attack", status: "open", due_date: null, money_at_stake: null,
    reversibility: null, next_actor_resolved: "ceo", next_actor_basis: "l",
    at: null, supersession: edge(),
  } as CeoDeskView["blocked"]["items"][number];
  assert.equal(
    blockedRecs(view({ blocked: { shown: 1, total: 1, items: [item], note: "" } })).size,
    0, "a request is not a recommendation and has no run#rec key");
});

test("actionable never offers a button the server would refuse", () => {
  const blocked = {
    source: "recommendation", ref: "rec:a#1", seat: "pm", title: "R37",
    kind: "policy", status: "staged", due_date: null, money_at_stake: null,
    reversibility: null, next_actor_resolved: "ceo", next_actor_basis: "kind",
    at: null, supersession: edge({ mode: "superseded_pending" }),
  } as CeoDeskView["decisions"]["items"][number];
  const clean = { ...blocked, ref: "rec:b#1", supersession: null };
  const v = view({
    decisions: { shown: 2, total: 2, truncated: false, ranked_by: "",
                 ranked_on_nothing: 0, items: [blocked, clean], note: "" },
  });
  assert.deepEqual(actionable(v).map((i) => i.ref), ["rec:b#1"]);
  assert.deepEqual(actionable(null), []);
});

test("actionable does not RE-RANK the spine's order", () => {
  const mk = (ref: string) => ({
    source: "recommendation", ref, seat: "pm", title: ref, kind: "k",
    status: "open", due_date: null, money_at_stake: null, reversibility: null,
    next_actor_resolved: "ceo", next_actor_basis: "kind", at: null,
    supersession: null,
  } as CeoDeskView["decisions"]["items"][number]);
  const items = [mk("c"), mk("a"), mk("b")];
  const v = view({
    decisions: { shown: 3, total: 3, truncated: false, ranked_by: "",
                 ranked_on_nothing: 3, items, note: "" },
  });
  assert.deepEqual(actionable(v).map((i) => i.ref), ["c", "a", "b"],
    "the spine ranked these; re-sorting here is the second definition again");
});
