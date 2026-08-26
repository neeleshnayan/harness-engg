/**
 * THE TICKET CARD CONTRACT v2 — an ACCEPTANCE TEST, not a fixture check.
 *
 * Run: `node --experimental-strip-types --test src/app/clark/studio/desk/ticketCardContract.test.ts`
 *
 * HOW THIS DIFFERS FROM `deskCardContract.test.ts`, and why the difference is
 * the point. v1's producing code lives in ClarkHarness, across a repo boundary
 * with no shared build, so this repo's v1 test can only assert the fixture is
 * internally CONSISTENT WITH ITSELF — totals derived rather than retyped, names
 * looked up rather than indexed, a digest pinned. That is the strongest check
 * available across that boundary and it is genuinely useful.
 *
 * **v2's producing code lives HERE.** `ticketCardState` is in this repo, so
 * every case below is DRIVEN through the real function and its output compared.
 * A case that stops holding turns this file red, which a self-consistency check
 * cannot do.
 *
 * THE ONE NUMBER THE FILE EXISTS FOR is `terminal_rows_offering_a_control`,
 * and it must be zero. The CEO's word for a non-zero was *"like WTF"*.
 *
 * WHAT IS OWED: the ClarkHarness copy. v1 is byte-identical in both repos; v2
 * exists only here until the generator gains an entry on that side. Stated in
 * the contract's own `clarkharness_copy` field and asserted below, so the gap
 * cannot be forgotten by being invisible.
 */

import assert from "node:assert/strict";
import test from "node:test";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import type { Ticket } from "@/lib/fund_api";

import {
  STATE_LABEL, awaitingCount, isTerminal, recordCount, ticketCardState,
} from "./ticketCard.ts";

/**
 * THE DIGEST, PINNED IN SOURCE — the same discipline v1 uses.
 *
 * Regenerating (`node scripts/contract/gen_ticket_card_contract.mjs`) changes
 * this value and this file goes red until a human updates the literal, having
 * read what actually changed. A contract that could move under its own test is
 * not a contract.
 */
const V2_DIGEST =
  "91d1ad392d9e9cbd4e641dddfe0b55243869d229a1aba35ff5656a55d40e1509";

const CONTRACT_URL = new URL(
  "../../../../../contract/desk_card_contract.v2.json", import.meta.url);

interface CaseExpect {
  controls: "decide" | "execute" | "none";
  countedAsAwaiting: boolean;
  awaitingActor: string | null;
  terminal: boolean;
  lamp: "working" | "awaiting-review" | "idle" | "record";
  citationOwed: boolean;
  titleLooksUnreadable?: boolean;
  titleAbsent?: boolean;
  ageKnown?: boolean;
  ageInStateHours?: number | null;
}

interface ContractCase { name: string; why: string; row: Ticket; expect: CaseExpect }

interface Contract {
  contract: string;
  version: number;
  covers: string;
  rules_version: string;
  producing_module: string;
  clarkharness_copy: string;
  lifecycle_working: string[];
  lifecycle_terminal: string[];
  controls: string[];
  lamps: string[];
  invariants: string[];
  cases: ContractCase[];
  expect_totals: Record<string, number>;
  digest: string;
}

const raw = readFileSync(CONTRACT_URL, "utf8");
const C: Contract = JSON.parse(raw);

/* ------------------------------------------------------------ the pin ----- */

test("the contract file matches the digest pinned in this source", () => {
  const { digest, ...body } = C;
  const recomputed = createHash("sha256")
    .update(JSON.stringify(body, null, 1)).digest("hex");
  assert.equal(recomputed, digest, "the file's own digest does not match its body");
  assert.equal(digest, V2_DIGEST,
    "the contract moved. Read the diff, then update V2_DIGEST by hand.");
});

test("v2 is ADDITIVE — v1 exists beside it and is a different file", () => {
  // The brief's constraint, made mechanical: v2 must not have been produced by
  // editing v1. Both files exist, both claim the same contract name, and their
  // versions differ.
  const v1 = JSON.parse(readFileSync(
    new URL("../../../../../contract/desk_card_contract.v1.json", import.meta.url),
    "utf8"));
  assert.equal(v1.contract, C.contract);
  assert.equal(v1.version, 1);
  assert.equal(C.version, 2);
  assert.notEqual(v1.digest, C.digest);
});

test("the cross-repo copy is declared OWED rather than silently missing", () => {
  // An absent thing must SAY it is absent. If someone later ships the
  // ClarkHarness copy, this test is what tells them to update the sentence.
  assert.match(C.clarkharness_copy, /^OWED/);
  assert.match(C.clarkharness_copy, /binds ONE repo/);
});

/* ------------------------------------------------- every case, driven ----- */

for (const c of C.cases) {
  test(`CONTRACT: ${c.name}`, () => {
    const got = ticketCardState(c.row);
    const e = c.expect;
    assert.equal(got.controls, e.controls, "controls");
    assert.equal(got.countedAsAwaiting, e.countedAsAwaiting, "countedAsAwaiting");
    assert.equal(got.awaitingActor, e.awaitingActor, "awaitingActor");
    assert.equal(got.terminal, e.terminal, "terminal");
    assert.equal(got.lamp, e.lamp, "lamp");
    assert.equal(got.citationOwed, e.citationOwed, "citationOwed");
    if (e.titleLooksUnreadable !== undefined) {
      assert.equal(got.title.looksUnreadable, e.titleLooksUnreadable);
    }
    if (e.titleAbsent !== undefined) {
      assert.equal(got.title.absent, e.titleAbsent);
    }
    if (e.ageKnown !== undefined) assert.equal(got.ageKnown, e.ageKnown);
    if (e.ageInStateHours !== undefined) {
      assert.equal(got.ageInStateHours, e.ageInStateHours);
    }
    // ALWAYS, for every case: a control slot is never a blank.
    assert.ok(got.controlsWhy.trim().length > 0,
      "controlsWhy must never be empty — a missing control with no sentence "
      + "is indistinguishable from a control that failed to render");
  });
}

/* ------------------------------------------------------ the totals -------- */

test("the totals are DERIVED from the cases, not retyped beside them", () => {
  const t = C.expect_totals;
  assert.equal(t.cases, C.cases.length);
  assert.equal(t.with_a_decision_control,
    C.cases.filter((c) => c.expect.controls === "decide").length);
  assert.equal(t.with_an_execution_control,
    C.cases.filter((c) => c.expect.controls === "execute").length);
  assert.equal(t.with_no_control,
    C.cases.filter((c) => c.expect.controls === "none").length);
  assert.equal(t.terminal, C.cases.filter((c) => c.expect.terminal).length);
  assert.equal(t.counted_as_awaiting,
    C.cases.filter((c) => c.expect.countedAsAwaiting).length);
  assert.equal(
    t.with_a_decision_control + t.with_an_execution_control + t.with_no_control,
    t.cases, "the three control values must partition the cases");
});

test("NO TERMINAL ROW OFFERS A CONTROL — the one number this file exists for", () => {
  assert.equal(C.expect_totals.terminal_rows_offering_a_control, 0);
  // And measured through the real function, not read off the fixture: a
  // contract that only checked its own expectation would be a wish.
  const live = C.cases
    .map((c) => ticketCardState(c.row))
    .filter((s) => s.terminal && s.controls !== "none");
  assert.deepEqual(live, [],
    "a terminal ticket rendered a control — the CEO's word for this was "
    + "\"like WTF\", and it is what the whole highway was built against");
});

test("the terminal cases cover ALL FIVE terminal states, not a sample", () => {
  // A boundary table, so a sixth terminal state cannot be added to the
  // lifecycle without this file noticing.
  const covered = new Set(
    C.cases.filter((c) => c.expect.terminal).map((c) => c.row.state));
  for (const s of C.lifecycle_terminal) {
    assert.ok(covered.has(s as Ticket["state"]),
      `terminal state ${s} has no contract case`);
  }
});

test("the lifecycle in the contract IS the module's, not a copy of it", () => {
  // MOVED, NOT COMPARED. An assertion that the contract's list equals a
  // hardcoded list here cannot tell a read value from a duplicate that happens
  // to agree — so the check runs each name through the module's own label map
  // and its own terminal predicate.
  for (const s of C.lifecycle_terminal) {
    assert.ok(STATE_LABEL[s as Ticket["state"]],
      `${s} has no label in the module`);
    assert.equal(isTerminal({ terminal: undefined as unknown as boolean,
                              state: s as Ticket["state"] }), true);
  }
  for (const s of C.lifecycle_working) {
    assert.ok(STATE_LABEL[s as Ticket["state"]],
      `${s} has no label in the module`);
    assert.equal(isTerminal({ terminal: undefined as unknown as boolean,
                              state: s as Ticket["state"] }), false);
  }
});

test("the population counters agree with the case-by-case verdicts", () => {
  // `awaitingCount` and `recordCount` are what the desk headings print. If
  // they disagreed with the per-row verdicts, a heading would say "N awaiting"
  // over rows that say otherwise — one quantity computed twice, which this
  // desk has shipped twice.
  const rows = C.cases.map((c) => c.row);
  assert.equal(awaitingCount(rows), C.expect_totals.counted_as_awaiting);
  assert.equal(recordCount(rows), C.expect_totals.terminal);
});

test("every invariant the contract states is a sentence, not a placeholder", () => {
  assert.ok(C.invariants.length >= 6);
  for (const i of C.invariants) assert.ok(i.trim().length > 20, i);
});
