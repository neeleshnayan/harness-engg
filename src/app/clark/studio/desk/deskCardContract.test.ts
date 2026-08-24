/**
 * The desk-CARD contract: THE COMPANION to `deskStageContract.test.ts`, one
 * layer up the same boundary.
 *
 * The stage contract pins WHICH BUCKET a desk row falls into and how many
 * rows land on the CEO's count. This contract pins something the stage
 * contract deliberately leaves alone: WHAT A ROW RENDERS AS — the nine
 * states the CEO's window either got wrong or could not express on
 * 2026-08-24 (the file's own `covers` field says so: "It binds no count;
 * the stage contract binds the count."). A stuck-lamp Accept button on an
 * already-accepted row, a raw Python dict repr where a title belongs, a
 * "superseded" sentence that names nothing, a cascade block with no
 * arithmetic behind it, a request chip that implied the CEO's move when it
 * was the chair's — none of those are counting defects, so the stage
 * contract's green suite never had a chance to catch them.
 *
 * HOW IT CROSSES A BOUNDARY WITH NO SHARED BUILD (same mechanism as the
 * stage contract, restated because it is the whole point):
 *
 *   `contract/desk_card_contract.v1.json` is generated in ClarkHarness by
 *   `scripts/gen_desk_contract.py` (never typed by hand, so it cannot encode
 *   a wish) and checked in to both repos, byte-identical. This file reads
 *   the SAME JSON this repo carries and asserts the fixture is internally
 *   consistent with itself: totals derived from the case rows rather than
 *   retyped, names looked up rather than indexed, a digest pinned so the
 *   file cannot drift under either suite without a human touching a test.
 *
 * Run: `node --experimental-strip-types --test src/app/clark/studio/desk/deskCardContract.test.ts`
 */

import { strict as assert } from "node:assert";
import { test } from "node:test";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

/**
 * THE DIGEST, PINNED IN SOURCE.
 *
 * Regenerating the contract in ClarkHarness (`python scripts/gen_desk_contract.py`)
 * changes this value. Both suites fail until this literal is updated by
 * hand: this file's digest-pin test (the JSON no longer matches this
 * constant) and ClarkHarness's own generator test (its output no longer
 * matches the copy checked in here) — because neither side may move without
 * a human reading what actually changed.
 */
const CARD_CONTRACT_DIGEST =
  "5407f30702436ac2d83ccde4baa01d5e893719a84d4171d7025876a44509a8c2";

const CONTRACT_URL = new URL(
  "../../../../../contract/desk_card_contract.v1.json", import.meta.url);

interface AdjudicationExpect {
  channel: string;
  actor: string;
  at: string;
  label: string;
  citation: string | null;
  instruction: string | null;
}

interface CascadeMemberExpect {
  ref: string;
  status: string | null;
  state: string;
}

interface CascadeExpect {
  total: number;
  done: number;
  pending: number;
  not_open: number;
  members: CascadeMemberExpect[];
  note: string;
}

interface SupersededByExpect {
  ref: string;
  phrase: string;
  quote: string;
}

interface CardCaseExpect {
  status: string;
  next_actor_resolved: string;
  execution_yours: boolean;
  title: string;
  title_display: string;
  detail: string | null;
  adjudication: AdjudicationExpect | null;
  superseded_by: SupersededByExpect | null;
  cascade: CascadeExpect | null;
  decided_by: string | null;
  decided_at: string | null;
}

interface CardCase {
  name: string;
  why: string;
  row: Record<string, unknown>;
  expect: CardCaseExpect;
}

interface WantedItemExpect {
  text: string;
  state: string;
  note?: string;
}

interface NextMoveExpect {
  actor: string;
  act: string;
}

interface LifecycleStageExpect {
  stage: string;
  at: string | null;
  reached: boolean;
  current: boolean;
}

interface RequestLifecycleExpect {
  stages: LifecycleStageExpect[];
  current: string;
  age_hours: string;
  declined: boolean;
}

interface RequestCaseExpect {
  status: string;
  next_actor_resolved: string;
  title_display: string;
  summary: string | null;
  detail: string | null;
  wanted: WantedItemExpect[];
  next_move: NextMoveExpect | null;
  structured: boolean;
  lifecycle: RequestLifecycleExpect;
  adjudication: AdjudicationExpect | null;
}

interface RequestCase {
  name: string;
  why: string;
  row: Record<string, unknown>;
  expect: RequestCaseExpect;
}

interface IdRuleCase {
  declared: string;
  why: string;
  ids: string[];
  normalised: { declared: string; resolved: string }[];
  ambiguous: { declared: string; matches: string[] }[];
  unresolved: string[];
}

interface Contract {
  contract: string;
  version: number;
  rules_version: string;
  request_routing_version: string;
  covers: string;
  lifecycle: string[];
  wanted_states: string[];
  adjudication_channels: string[];
  cases: CardCase[];
  request_cases: RequestCase[];
  id_rules: {
    min_prefix: number;
    doors_refusing_unknown_ids: string[];
    note: string;
    cases: IdRuleCase[];
  };
  expect_totals: {
    execution_yours: number;
    counted_for_ceo: number;
    superseded_edges: number;
    repaired_reprs: number;
    requests_on_the_ceos_figure: number;
  };
  digest: string;
}

function loadContract(): { body: Contract; raw: string } {
  let raw: string;
  try {
    raw = readFileSync(CONTRACT_URL, "utf8");
  } catch (e) {
    throw new Error(
      `the desk-card contract is missing at ${CONTRACT_URL.pathname}. It is `
      + "generated in ClarkHarness by `python scripts/gen_desk_contract.py` "
      + "and copied here; without it this repo has no shared definition of "
      + `how a desk row renders at all. (${(e as Error).message})`);
  }
  return { body: JSON.parse(raw) as Contract, raw };
}

/**
 * Python's `json.dumps(sort_keys=True, separators=(",", ":"),
 * ensure_ascii=False)`, reimplemented — the same helper the stage contract
 * test carries, duplicated on purpose rather than imported: each contract
 * test must be able to prove its own digest without trusting a shared
 * implementation to have not drifted underneath it.
 */
function canonical(v: unknown): string {
  if (v === null || typeof v !== "object") return JSON.stringify(v);
  if (Array.isArray(v)) return `[${v.map(canonical).join(",")}]`;
  const o = v as Record<string, unknown>;
  const keys = Object.keys(o).sort();
  return `{${keys.map((k) => `${JSON.stringify(k)}:${canonical(o[k])}`).join(",")}}`;
}

function findCase(cases: CardCase[], name: string): CardCase {
  const c = cases.find((x) => x.name === name);
  assert.ok(c, `the contract must carry a case named "${name}"`);
  return c!;
}

function findRequestCase(cases: RequestCase[], name: string): RequestCase {
  const c = cases.find((x) => x.name === name);
  assert.ok(c, `the contract must carry a request case named "${name}"`);
  return c!;
}

function findIdRuleCase(cases: IdRuleCase[], declared: string): IdRuleCase {
  const c = cases.find((x) => x.declared === declared);
  assert.ok(c, `id_rules must carry a case declared "${declared}"`);
  return c!;
}

/* ------------------------------------------------------------- the lock --- */

test("the contract file is the one this repo was written against", () => {
  /* If this fails, the copy here and the copy in ClarkHarness have drifted,
   * or somebody edited the fixture to make a failing assertion pass — which
   * is the only way a shared contract can be defeated from one side. */
  const { body } = loadContract();
  const withoutDigest = { ...body } as Record<string, unknown>;
  delete withoutDigest.digest;
  const computed = createHash("sha256")
    .update(canonical(withoutDigest), "utf8").digest("hex");

  assert.equal(computed, body.digest,
    "the contract's body no longer matches its own digest — the file has "
    + "been edited by hand. Regenerate it in ClarkHarness rather than "
    + "patching it.");
  assert.equal(computed, CARD_CONTRACT_DIGEST,
    "the contract changed and this test was not updated. Regenerate in "
    + "ClarkHarness, copy the file here, and update CARD_CONTRACT_DIGEST — "
    + "then read what actually changed.");
});

test("the canonical form agrees with Python's, or the digest proves nothing", () => {
  /* A cross-language digest is only a lock if both languages produce the
   * same bytes. This asserts the reimplementation above against a value
   * with the awkward parts: sorted keys out of order, nested arrays, null,
   * and non-ASCII (the contract is full of em-dashes and curly quotes, and
   * `ensure_ascii=False` leaves them raw). */
  assert.equal(
    canonical({ b: 1, a: [null, "—", { d: 2, c: "it's" }], A: true }),
    '{"A":true,"a":[null,"—",{"c":"it\'s","d":2}],"b":1}');
});

/* --------------------------------------------------------- B: shape sanity */

test("every case and request case carries a non-empty name and why", () => {
  const { body } = loadContract();
  assert.ok(body.cases.length > 0, "the case table must not be empty");
  assert.ok(body.request_cases.length > 0, "the request-case table must not be empty");
  for (const c of [...body.cases, ...body.request_cases]) {
    assert.ok(c.name.length > 0, "every case needs a name to be looked up by");
    assert.ok(c.why.length > 0, `${c.name}: every case needs a "why" it exists`);
  }
});

/* ------------------------------------------- C: cases, looked up by name --- */

test("execution_yours flips on for the CEO's own resolution, off for the open baseline", () => {
  const { body } = loadContract();
  const stuckLamp = findCase(body.cases, "ACCEPTED, EXECUTION YOURS — the stuck lamp");
  assert.equal(stuckLamp.expect.execution_yours, true,
    "the row the CEO himself just accepted must read as his to execute");

  const openBaseline = findCase(body.cases, "open recommendation — nobody has decided it");
  assert.equal(openBaseline.expect.execution_yours, false,
    "an undecided row must never look like a decided one awaiting execution");
});

test("THE COUNT IS UNCHANGED: the totals are derived from the cases, not retyped", () => {
  const { body } = loadContract();
  const executionYoursCount =
    body.cases.filter((c) => c.expect.execution_yours === true).length;
  assert.equal(body.expect_totals.execution_yours, executionYoursCount,
    "expect_totals.execution_yours must equal the number of cases actually "
    + "marked execution_yours — a contract whose header disagrees with its "
    + "own rows is the exact defect this file exists to catch");

  const countedForCeoCount = body.cases.filter((c) =>
    c.expect.next_actor_resolved === "ceo" || c.expect.next_actor_resolved === "unknown"
  ).length;
  assert.equal(body.expect_totals.counted_for_ceo, countedForCeoCount,
    "expect_totals.counted_for_ceo must equal the number of cases resolved "
    + 'to "ceo" or "unknown"');
});

test("DICT PAYLOAD: renders its title, never its repr", () => {
  const { body } = loadContract();
  const c = findCase(body.cases, "DICT PAYLOAD — renders its title, never its repr");
  assert.ok(!c.expect.title_display.startsWith("{"),
    "title_display must never start with a raw dict repr's opening brace");
  assert.notEqual(c.expect.title_display, c.expect.title,
    "title_display must be the repaired line, distinct from the stored (raw) title");
});

test("SUPERSEDED-SOUNDING PROSE THAT NAMES NOTHING — the null case", () => {
  /* Six of the ten live word-level "supersed" hits are one boilerplate
   * sentence stapled to unrelated resolutions — about two stray events, not
   * about the row carrying it. A word-match parser draws a wrong edge here;
   * the contract requires a NAMED target before any superseded_by renders,
   * so this row (prose that sounds like a supersession but names nothing)
   * must resolve to null rather than a guessed link. */
  const { body } = loadContract();
  const c = findCase(body.cases,
    "SUPERSEDED-SOUNDING PROSE THAT NAMES NOTHING — the null case");
  assert.equal(c.expect.superseded_by, null,
    "prose that merely sounds like a supersession, with no named target, "
    + "must never render an edge");
});

test("BUNDLE WITH MEMBERS: the cascade arithmetic partitions its four members", () => {
  const { body } = loadContract();
  const c = findCase(body.cases, "BUNDLE WITH MEMBERS — cascade pending");
  const cascade = c.expect.cascade;
  assert.ok(cascade, "this case must carry a cascade block");
  assert.equal(cascade!.done + cascade!.pending + cascade!.not_open, cascade!.total,
    "done + pending + not_open must exactly partition the bundle's members");
  assert.equal(cascade!.pending, 2,
    "two of the four members are still undecided");
});

test("adjudication_channels covers every channel the cases actually use", () => {
  const { body } = loadContract();
  const usedChannels = new Set(
    body.cases
      .map((c) => c.expect.adjudication?.channel)
      .filter((ch): ch is string => ch != null));
  for (const channel of usedChannels) {
    assert.ok(body.adjudication_channels.includes(channel),
      `case adjudication uses channel "${channel}", which must be declared `
      + "in the top-level adjudication_channels list");
  }
});

/* --------------------------------------------- D: request cases, by name --- */

test("STRUCTURED REQUEST — the four questions", () => {
  const { body } = loadContract();
  const c = findRequestCase(body.request_cases, "STRUCTURED REQUEST — the four questions");
  assert.equal(c.expect.structured, true);
  assert.equal(c.expect.wanted.length, 3,
    "the structured card carries three wanted entries");
});

test("PROSE-ONLY REQUEST — the permanent fallback", () => {
  const { body } = loadContract();
  const c = findRequestCase(body.request_cases, "PROSE-ONLY REQUEST — the permanent fallback");
  assert.equal(c.expect.structured, false);
  assert.ok(!c.expect.title_display.includes("\n"),
    "title_display must be the subject's first line only, never the whole "
    + "multi-line subject");
});

test('next_move with an actor and no act — REFUSED', () => {
  const { body } = loadContract();
  const c = findRequestCase(body.request_cases, "next_move with an actor and no act — REFUSED");
  assert.equal(c.expect.next_move, null,
    "a next_move naming an actor but no act must be refused, not rendered half-formed");
});

/* --------------------------------------------- E: requests never own the CEO's figure */

test("no request case ever resolves to the CEO, and none counts on his figure", () => {
  const { body } = loadContract();
  for (const c of body.request_cases) {
    assert.notEqual(c.expect.next_actor_resolved, "ceo",
      `${c.name}: a request must never resolve straight to "ceo" — the `
      + "stage contract's desk_load count owns his figure, not the request rail");
  }
  assert.equal(body.expect_totals.requests_on_the_ceos_figure, 0);
});

/* ---------------------------------------- F: request lifecycle rail shape --- */

test("every request's age is wall-clock, never pinned, and its stages mirror the top-level rail", () => {
  const { body } = loadContract();
  for (const c of body.request_cases) {
    assert.equal(c.expect.lifecycle.age_hours, "<wall-clock>",
      `${c.name}: a contract that embedded a real age would be stale one `
      + "second later — age_hours must always read as the sentinel, never a number");

    const stageNames = c.expect.lifecycle.stages.map((s) => s.stage);
    assert.deepEqual(stageNames, body.lifecycle,
      `${c.name}: the request's stage rail must be exactly the file's `
      + "top-level lifecycle array, in the same order");

    const currentCount = c.expect.lifecycle.stages.filter((s) => s.current === true).length;
    assert.equal(currentCount, 1,
      `${c.name}: exactly one stage must be marked current`);
  }
});

/* ---------------------------------------------------------- G: id_rules --- */

test("id_rules: an ambiguous shorthand is refused, never guessed", () => {
  const { body } = loadContract();
  const c = findIdRuleCase(body.id_rules.cases, "abcd1234");
  assert.equal(c.ambiguous.length, 1,
    "a shorthand matching two ids must be reported ambiguous, not resolved");
  assert.equal(c.normalised.length, 0,
    "an ambiguous shorthand must never also appear normalised");
});

test("id_rules: a seven-character declaration is a typo, not a shorthand", () => {
  const { body } = loadContract();
  const c = findIdRuleCase(body.id_rules.cases, "3eeb42d");
  assert.equal(c.unresolved.length, 1,
    "a declaration shorter than the minimum prefix must be reported unresolved");
  assert.equal(c.normalised.length, 0,
    "a too-short declaration must never be normalised to a real id");
});

test("id_rules: an eight-character shorthand normalises to exactly one id", () => {
  const { body } = loadContract();
  const c = findIdRuleCase(body.id_rules.cases, "3eeb42d4");
  assert.equal(c.normalised.length, 1,
    "a shorthand at the minimum prefix, matching exactly one id, must normalise");
});

test("id_rules.min_prefix is pinned on both sides so neither side can move it alone", () => {
  /* min_prefix decides where "typo" ends and "shorthand" begins for every
   * declared id on the desk. It is asserted here, literally, so that a
   * change to the minimum on either side of the boundary shows up as a
   * failing test rather than a quiet, one-sided drift. */
  const { body } = loadContract();
  assert.equal(body.id_rules.min_prefix, 8);
});
