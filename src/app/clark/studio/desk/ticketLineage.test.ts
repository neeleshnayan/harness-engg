/**
 * TICKET LINEAGE — the tests that guard the five ways a parent link can be
 * missing, and the boundary between the two that must never collapse into
 * one (`fenced` vs `absent`).
 *
 * Run: `node --experimental-strip-types --test src/app/clark/studio/desk/ticketLineage.test.ts`
 *
 * `linkFor` is internal (not exported) and is exercised only through
 * `lineageFor` and `lineageCoverage`, per the module's own public surface.
 */

import assert from "node:assert/strict";
import test from "node:test";
import type { Ticket, TicketState, TicketType } from "@/lib/fund_api";

import {
  LINK_SENTENCE, MAX_LINEAGE_DEPTH, ROOT_TYPES,
  lineageCoverage, lineageFor, ticketIndex,
  type LinkState,
} from "./ticketLineage.ts";

/* ------------------------------------------------------------ the maker --- */

let seq = 0;

/** A ticket with inert defaults, overridable field by field.
 *
 *  DEFAULTS ARE THE INERT CASE ON PURPOSE: `type: "recommendation"` is not a
 *  ROOT_TYPE, `parent_id` and `trace_id` are null, `parent_basis` is null
 *  (not the fence value) and `canonical_ticket_id` is null — so with no
 *  overrides, `linkFor` lands on `absent` and nothing else fires by
 *  accident. A test opts into a rule field by field, exactly like the
 *  ticketExceptions house style. */
function tk(over: Partial<Ticket> = {}): Ticket {
  seq += 1;
  const state = (over.state ?? "filed") as TicketState;
  return {
    ticket_id: over.ticket_id ?? `t-${seq}`,
    type: (over.type ?? "recommendation") as TicketType,
    state,
    subject: over.subject ?? `subject ${seq}`,
    filed_for: over.filed_for ?? "builder",
    filed_by: over.filed_by ?? "cto",
    filed_at: over.filed_at ?? "2026-08-21T00:00:00+00:00",
    trace_id: over.trace_id ?? null,
    parent_id: over.parent_id ?? null,
    source: over.source ?? "deskstore.recommendations",
    transitions: over.transitions ?? [],
    refused_transitions: over.refused_transitions ?? [],
    parent_basis: over.parent_basis ?? null,
    terminal: over.terminal ?? false,
    next_actor: over.next_actor ?? "chair",
    next_actor_basis: over.next_actor_basis ?? "kind",
    next_actor_why: over.next_actor_why ?? "the chair's move",
    age_hours: over.age_hours ?? 1,
    age_basis: over.age_basis ?? "event_timestamps",
    age_in_state_hours: over.age_in_state_hours ?? 1,
    age_in_state_basis: over.age_in_state_basis ?? "event_timestamps",
    decided: over.decided ?? false,
    decision_count: over.decision_count ?? 0,
    decided_state: over.decided_state ?? null,
    decided_at: over.decided_at ?? null,
    decided_by: over.decided_by ?? null,
    canonical_ticket_id: over.canonical_ticket_id ?? null,
    decision_basis: over.decision_basis ?? "transitions",
    ...over,
  } as Ticket;
}

const FENCE = "unlinkable_pre_highway";

/* ------------------------------------------------ the five link states --- */

test("found — parent_id set and resolves in the population", () => {
  const parent = tk({ ticket_id: "p1" });
  const child = tk({ ticket_id: "c1", parent_id: "p1" });
  const lin = lineageFor("c1", [parent, child])!;
  assert.equal(lin.parent.state, "found");
  assert.equal(lin.parent.ticket, parent);
  assert.equal(lin.parent.namedId, "p1");
  assert.equal(lin.parent.sentence, LINK_SENTENCE.found);
});

test("dangling — parent_id set but does not resolve; namedId still carries it", () => {
  const orphan = tk({ ticket_id: "c1", parent_id: "ghost-99" });
  const lin = lineageFor("c1", [orphan])!;
  assert.equal(lin.parent.state, "dangling");
  assert.equal(lin.parent.ticket, null);
  assert.equal(lin.parent.namedId, "ghost-99",
    "a dangling link must still show which id it named, or the reader cannot chase it");
  assert.equal(lin.parent.sentence, LINK_SENTENCE.dangling);
});

test("fenced — no parent_id and parent_basis is the pre-highway fence", () => {
  const row = tk({ ticket_id: "f1", parent_id: null, parent_basis: FENCE });
  const lin = lineageFor("f1", [row])!;
  assert.equal(lin.parent.state, "fenced");
  assert.equal(lin.parent.ticket, null);
  assert.equal(lin.parent.namedId, null);
  assert.equal(lin.parent.sentence, LINK_SENTENCE.fenced);
});

test("not_applicable — no parent_id, not fenced, type is a ROOT_TYPE (ask)", () => {
  const row = tk({ ticket_id: "a1", type: "ask", parent_id: null });
  const lin = lineageFor("a1", [row])!;
  assert.equal(lin.parent.state, "not_applicable");
  assert.equal(lin.parent.sentence, LINK_SENTENCE.not_applicable);
});

test("not_applicable — the other ROOT_TYPE, dispatch, is covered too", () => {
  const row = tk({ ticket_id: "d1", type: "dispatch", parent_id: null });
  const lin = lineageFor("d1", [row])!;
  assert.equal(lin.parent.state, "not_applicable");
  assert.deepEqual([...ROOT_TYPES].sort(), ["ask", "dispatch"]);
});

test("absent — no parent_id, not fenced, type is not a ROOT_TYPE", () => {
  const row = tk({ ticket_id: "r1", type: "recommendation", parent_id: null });
  const lin = lineageFor("r1", [row])!;
  assert.equal(lin.parent.state, "absent");
  assert.equal(lin.parent.sentence, LINK_SENTENCE.absent);
});

/* --------------------------------- the critical pair: fenced vs absent --- */

test("fenced and absent never share a sentence, and are never counted together", () => {
  // FAILS IF ANYONE MERGES THEM. Two rows: one genuinely fenced (pre-highway,
  // unreadable), one genuinely absent (readable record, no parent). A
  // regression that folded `absent` into `fenced` (or vice versa) would
  // still pass every single-state test above by accident if it always
  // reported the SAME state for both — so this test puts both in one
  // population and demands they land in different buckets with different
  // words.
  const fenced = tk({ ticket_id: "fenced-1", parent_basis: FENCE });
  const absent = tk({ ticket_id: "absent-1", type: "recommendation" });
  const cov = lineageCoverage([fenced, absent])!;
  assert.equal(cov.fenced, 1);
  assert.equal(cov.absent, 1);
  assert.notEqual(LINK_SENTENCE.fenced, LINK_SENTENCE.absent);

  // SHARED-WORD CHECK: both sentences contain the word "record", so a
  // substring match on "record" alone would pass even if the two branches
  // were swapped. Assert on a phrase unique to each instead.
  assert.match(LINK_SENTENCE.fenced, /record/);
  assert.match(LINK_SENTENCE.absent, /record/);
  assert.match(LINK_SENTENCE.fenced, /predates the highway/,
    "unique to fenced — absent's sentence never mentions the highway");
  assert.doesNotMatch(LINK_SENTENCE.absent, /predates the highway/);
  assert.match(LINK_SENTENCE.absent, /holds no parent/,
    "unique to absent — fenced's sentence never says 'holds no parent'");
  assert.doesNotMatch(LINK_SENTENCE.fenced, /holds no parent/);

  // linkable excludes fenced and includes absent — the numeric proof that
  // the two are not interchangeable in the coverage denominator either.
  assert.equal(cov.linkable, 1, "only the absent row is linkable; fenced is excluded");
});

/* --------------------------------------------------- the boundary table --- */

test("LINK_SENTENCE has a distinct, non-empty sentence for all five LinkStates", () => {
  const states: LinkState[] =
    ["found", "fenced", "not_applicable", "absent", "dangling"];
  for (const s of states) {
    assert.ok(LINK_SENTENCE[s] && LINK_SENTENCE[s].length > 0,
      `${s} must carry a non-empty sentence`);
  }
  const sentences = states.map((s) => LINK_SENTENCE[s]);
  assert.equal(new Set(sentences).size, states.length,
    "no two LinkStates may render the same sentence");
});

/* --------------------------------------------------- the unread anchor --- */

test("lineageFor returns null when the population does not contain the id", () => {
  // Null is NOT an empty lineage — an anchor the fold has never seen is a
  // different fact from a ticket with no parent.
  const result = lineageFor("nowhere", [tk({ ticket_id: "other" })]);
  assert.equal(result, null);
});

/* ------------------------------------------------------------ ancestors --- */

test("ancestors is empty when the parent link is not `found`", () => {
  const dangling = tk({ ticket_id: "c1", parent_id: "ghost" });
  const lin = lineageFor("c1", [dangling])!;
  assert.deepEqual(lin.ancestors, []);
  assert.equal(lin.depth, 0);
});

test("ancestors is nearest-parent-first and walks transitively (grandparent chain)", () => {
  const grandparent = tk({ ticket_id: "gp" });
  const parent = tk({ ticket_id: "p", parent_id: "gp" });
  const child = tk({ ticket_id: "c", parent_id: "p" });
  const lin = lineageFor("c", [grandparent, parent, child])!;
  assert.deepEqual(lin.ancestors.map((t) => t.ticket_id), ["p", "gp"],
    "nearest parent first, then its parent");
  assert.equal(lin.depth, 2);
  assert.equal(lin.truncated, false);
});

/* -------------------------------------------------------- cycle safety --- */

test("a cyclic parent chain terminates with truncated: true and does not hang", () => {
  const a = tk({ ticket_id: "cyc-a", parent_id: "cyc-b" });
  const b = tk({ ticket_id: "cyc-b", parent_id: "cyc-a" });
  const lin = lineageFor("cyc-a", [a, b])!;
  assert.equal(lin.truncated, true);
  assert.deepEqual(lin.ancestors.map((t) => t.ticket_id), ["cyc-b"],
    "walks to b, then detects a repeats and stops before re-adding it");
});

test("a chain longer than MAX_LINEAGE_DEPTH sets truncated: true", () => {
  // A linear (acyclic) chain of anchor -> t1 -> t2 -> ... -> t14, well past
  // MAX_LINEAGE_DEPTH (10). No cycle here — this isolates the depth cap from
  // the cycle-detection path tested above.
  const N = 14;
  const tickets: Ticket[] = [tk({ ticket_id: "anchor", parent_id: "n1" })];
  for (let i = 1; i <= N; i++) {
    tickets.push(tk({
      ticket_id: `n${i}`,
      parent_id: i < N ? `n${i + 1}` : null,
    }));
  }
  const lin = lineageFor("anchor", tickets)!;
  assert.equal(lin.truncated, true);
  assert.equal(lin.ancestors.length, MAX_LINEAGE_DEPTH);
});

test("a chain at or under MAX_LINEAGE_DEPTH is NOT truncated", () => {
  const tickets: Ticket[] = [tk({ ticket_id: "anchor", parent_id: "n1" })];
  for (let i = 1; i <= 3; i++) {
    tickets.push(tk({ ticket_id: `n${i}`, parent_id: i < 3 ? `n${i + 1}` : null }));
  }
  const lin = lineageFor("anchor", tickets)!;
  assert.equal(lin.truncated, false);
  assert.equal(lin.ancestors.length, 3);
});

/* -------------------------------------------------------------- children -- */

test("children is every ticket naming the anchor as parent_id", () => {
  const anchor = tk({ ticket_id: "anchor" });
  const kid1 = tk({ ticket_id: "kid1", parent_id: "anchor" });
  const kid2 = tk({ ticket_id: "kid2", parent_id: "anchor" });
  const stranger = tk({ ticket_id: "stranger", parent_id: "someone-else" });
  const lin = lineageFor("anchor", [anchor, kid1, kid2, stranger])!;
  assert.deepEqual(
    lin.children.map((t) => t.ticket_id).sort(),
    ["kid1", "kid2"],
  );
});

test("children is empty when nothing names the anchor", () => {
  const anchor = tk({ ticket_id: "anchor" });
  const lin = lineageFor("anchor", [anchor, tk({ ticket_id: "unrelated" })])!;
  assert.deepEqual(lin.children, []);
});

/* ----------------------------------------------------------- traceCohort -- */

test("traceCohort excludes the anchor, its ancestors and its children", () => {
  const parent = tk({ ticket_id: "parent", trace_id: "tr-1" });
  const anchor = tk({ ticket_id: "anchor", parent_id: "parent", trace_id: "tr-1" });
  const kid = tk({ ticket_id: "kid", parent_id: "anchor", trace_id: "tr-1" });
  const cohortMate = tk({ ticket_id: "cohort-mate", trace_id: "tr-1" });
  const otherTrace = tk({ ticket_id: "other-trace", trace_id: "tr-2" });
  const lin = lineageFor("anchor", [parent, anchor, kid, cohortMate, otherTrace])!;
  assert.deepEqual(lin.traceCohort.map((t) => t.ticket_id), ["cohort-mate"]);
  assert.equal(lin.traceId, "tr-1");
});

test("a blank or whitespace-only trace_id gives an empty cohort and traceId: null", () => {
  const anchor = tk({ ticket_id: "anchor", trace_id: "   " });
  const other = tk({ ticket_id: "other", trace_id: "   " });
  const lin = lineageFor("anchor", [anchor, other])!;
  assert.deepEqual(lin.traceCohort, []);
  assert.equal(lin.traceId, null);
});

test("a null trace_id also gives an empty cohort and traceId: null", () => {
  const anchor = tk({ ticket_id: "anchor", trace_id: null });
  const lin = lineageFor("anchor", [anchor])!;
  assert.deepEqual(lin.traceCohort, []);
  assert.equal(lin.traceId, null);
});

/* -------------------------------------------------------------- canonical -- */

test("canonical is null when canonical_ticket_id is absent", () => {
  const anchor = tk({ ticket_id: "anchor", canonical_ticket_id: null });
  const lin = lineageFor("anchor", [anchor])!;
  assert.equal(lin.canonical, null);
});

test("canonical is null when canonical_ticket_id equals the anchor's own id", () => {
  const anchor = tk({ ticket_id: "anchor", canonical_ticket_id: "anchor" });
  const lin = lineageFor("anchor", [anchor])!;
  assert.equal(lin.canonical, null);
});

test("canonical is a `found` link when canonical_ticket_id resolves", () => {
  const anchor = tk({ ticket_id: "anchor", canonical_ticket_id: "winner" });
  const winner = tk({ ticket_id: "winner" });
  const lin = lineageFor("anchor", [anchor, winner])!;
  assert.equal(lin.canonical!.state, "found");
  assert.equal(lin.canonical!.ticket, winner);
  assert.equal(lin.canonical!.namedId, "winner");
});

test("canonical is a `dangling` link when canonical_ticket_id does not resolve", () => {
  const anchor = tk({ ticket_id: "anchor", canonical_ticket_id: "ghost-canonical" });
  const lin = lineageFor("anchor", [anchor])!;
  assert.equal(lin.canonical!.state, "dangling");
  assert.equal(lin.canonical!.ticket, null);
  assert.equal(lin.canonical!.namedId, "ghost-canonical");
});

/* ---------------------------------------------------------- ticketIndex --- */

test("ticketIndex maps FULL ids only — a prefix of a real id does not resolve", () => {
  // The 8-char-prefix habit is what rotted 54 of 56 linkages at this firm.
  const full = tk({ ticket_id: "abcdef12-3456-7890-full-id" });
  const idx = ticketIndex([full]);
  assert.equal(idx.get("abcdef12-3456-7890-full-id"), full);
  assert.equal(idx.get("abcdef12"), undefined,
    "an 8-char prefix of a real id must never resolve");
});

test("a parent_id that is only a prefix of a real id is dangling, not found", () => {
  const full = tk({ ticket_id: "abcdef12-3456-7890-full-id" });
  const child = tk({ ticket_id: "child", parent_id: "abcdef12" });
  const lin = lineageFor("child", [full, child])!;
  assert.equal(lin.parent.state, "dangling");
});

/* ------------------------------------------------------------- coverage --- */

test("lineageCoverage(null) returns null", () => {
  assert.equal(lineageCoverage(null), null);
  assert.equal(lineageCoverage(undefined), null);
});

test("lineageCoverage: the five counts sum to total (exhaustiveness over a mixed population)", () => {
  // BEING SOMEBODY'S PARENT DOES NOT MAKE YOUR OWN PARENT LINK `found`. The
  // coverage census classifies EVERY row by ITS OWN upward link, so the `ask`
  // at the head of this chain is `not_applicable` even though a recommendation
  // points at it. A first draft of this test asserted `found: 2` on exactly
  // that misreading and it is worth pinning: a census that counted a row once
  // for its own link and once for being referenced would double-count, and the
  // partition assertion below is what makes that impossible.
  const rows = [
    tk({ ticket_id: "found-1", parent_id: "found-parent" }),
    tk({ ticket_id: "found-parent", type: "ask" }),
    tk({ ticket_id: "fenced-1", parent_basis: FENCE }),
    tk({ ticket_id: "fenced-2", parent_basis: FENCE }),
    tk({ ticket_id: "na-1", type: "ask" }),
    tk({ ticket_id: "na-2", type: "dispatch" }),
    tk({ ticket_id: "na-3", type: "ask" }),
    tk({ ticket_id: "absent-1", type: "recommendation" }),
    tk({ ticket_id: "dangling-1", parent_id: "ghost" }),
  ];
  const cov = lineageCoverage(rows)!;
  assert.equal(cov.total, rows.length);
  assert.equal(
    cov.found + cov.fenced + cov.notApplicable + cov.absent + cov.dangling,
    cov.total,
    "the five link-state counts must partition the population",
  );
  assert.equal(cov.found, 1, "only `found-1` carries a resolving parent_id");
  assert.equal(cov.fenced, 2);
  assert.equal(cov.notApplicable, 4, "three roots plus the ask at the head");
  assert.equal(cov.absent, 1);
  assert.equal(cov.dangling, 1);
});

test("linkable = found + absent + dangling, and excludes fenced and not_applicable", () => {
  const rows = [
    tk({ ticket_id: "found-1", parent_id: "found-parent" }),
    tk({ ticket_id: "found-parent" }),
    tk({ ticket_id: "fenced-1", parent_basis: FENCE }),
    tk({ ticket_id: "na-1", type: "ask" }),
    tk({ ticket_id: "absent-1", type: "recommendation" }),
    tk({ ticket_id: "dangling-1", parent_id: "ghost" }),
  ];
  const cov = lineageCoverage(rows)!;
  assert.equal(cov.linkable, cov.found + cov.absent + cov.dangling);
  assert.equal(cov.linkable, rows.length - cov.fenced - cov.notApplicable,
    "fenced and not_applicable are excluded from the linkable denominator");
});

test("linkablePct is null when linkable === 0 — never 0, never NaN", () => {
  const rows = [
    tk({ ticket_id: "fenced-only", parent_basis: FENCE }),
    tk({ ticket_id: "na-only", type: "ask" }),
  ];
  const cov = lineageCoverage(rows)!;
  assert.equal(cov.linkable, 0);
  assert.equal(cov.linkablePct, null);
  assert.notEqual(cov.linkablePct, 0);
});

test("linkablePct is a real percentage when linkable > 0", () => {
  // The chain head is an `ask`, so it is `not_applicable` and sits OUTSIDE the
  // denominator — which is the whole design of this number: a percentage that
  // counted chain heads would improve every time somebody filed an ask.
  const rows = [
    tk({ ticket_id: "found-1", parent_id: "found-parent" }),
    tk({ ticket_id: "found-parent", type: "ask" }),
    tk({ ticket_id: "absent-1", type: "recommendation" }),
  ];
  const cov = lineageCoverage(rows)!;
  assert.equal(cov.linkable, 2, "one found + one absent; the ask is excluded");
  assert.equal(cov.linkablePct, 50);
});

test("lineageCoverage([]) is a real answer, not null — total 0, linkablePct null", () => {
  const cov = lineageCoverage([])!;
  assert.equal(cov.total, 0);
  assert.equal(cov.linkable, 0);
  assert.equal(cov.linkablePct, null);
});
