/**
 * Tests for the engine inclusion rule on Allocate.
 *
 * THE FIXTURE IS THE LIVE FUND OF 2026-08-27, because the defect is not
 * hypothetical: `LEAN - HYG fast flip probe` was draft / 0% / $0 exposure with
 * a LEAN session RUNNING, so the old fold put the strategy the engine was
 * trading on a bench headed "not carrying capital"; and `LEAN - GLD 100d SMA
 * filter`, the only strategy on this fund's record ever to raise a signal, was
 * ARCHIVED and therefore on no list at all.
 *
 * Every test names what it prevents.
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import { engineBook, engineBookHeadline, engineBookMismatch } from "./engineBook.ts";
import type { StrategyView } from "@/lib/fund_api";
import type { EngineStrategies } from "../engine/engineView.ts";

const HYG = "95520a8a-b527-4813-b0a5-bd466206912b";
const GLD = "a356b00a-d6c9-45f0-96ff-0a3a67f2af06";

function strat(over: Partial<StrategyView> & { strategy_id: string }): StrategyView {
  return {
    name: "unnamed",
    state: "draft",
    allocation_pct: 0,
    ...over,
  } as StrategyView;
}

/** The live fund, 2026-08-27, reduced to the rows that matter. */
const LIVE: StrategyView[] = [
  strat({ strategy_id: HYG, name: "LEAN - HYG fast flip probe", state: "draft",
          allocation_pct: 0, actual_pct: 0, exposure_usd: 0, archived: false,
          definition: { engine: "lean", algorithm: "hyg_fast_flip_probe" } }),
  strat({ strategy_id: GLD, name: "LEAN - GLD 100d SMA filter", state: "draft",
          allocation_pct: 0, actual_pct: 0, exposure_usd: 0, archived: true,
          definition: { engine: "lean", algorithm: "gld_sma_filter" } }),
  strat({ strategy_id: "sleeve_premia_spy", name: "Sleeve - equity risk premium (SPY)",
          state: "deployed", allocation_pct: 0, actual_pct: 13.25, exposure_usd: 265.27,
          archived: false }),
  strat({ strategy_id: "3c593166", name: "TEST - Fast Intraday (5m SMA)",
          state: "paused", allocation_pct: 0, actual_pct: 0, exposure_usd: 0,
          archived: false }),
];

/**
 * ONE CONSTRUCTOR FOR THE ENGINE PAYLOAD. A fixture that patches one field of
 * a multi-field state is the production defect in test clothes (ENG2, measured).
 */
function enginePayload(over: Partial<EngineStrategies> = {}): EngineStrategies {
  return {
    readable: true,
    reason: null,
    total: 2,
    archived: 1,
    strategies: [
      {
        strategy_id: HYG, name: "LEAN - HYG fast flip probe", engine: "lean",
        state: "draft", archived: false, allocation_pct: 0, assets: ["HYG"],
        datasource: { readable: true }, session_state: "running",
        sessions: [{ session_id: "s1", algorithm: "hyg_fast_flip_probe", state: "running" }],
      },
      {
        strategy_id: GLD, name: "LEAN - GLD 100d SMA filter", engine: "lean",
        state: "draft", archived: true, allocation_pct: 0, assets: ["GLD"],
        datasource: { readable: true }, session_state: "none", sessions: [],
      },
    ],
    ...over,
  };
}

// ------------------------------------------------------------- the inclusion

test("EVERY engine strategy gets a row — draft, unallocated, archived, all of them", () => {
  // KILLS THE WHOLE DEFECT. The old page rendered engine strategies only where
  // the book/bench fold happened to put them, which for the live fund meant a
  // running probe on the bench and an archived one nowhere at all.
  const b = engineBook(LIVE, enginePayload());
  assert.deepEqual(b.rows.map((r) => r.strategy.strategy_id), [HYG, GLD]);
  assert.equal(b.readable, true);
  assert.equal(b.absence, null);
});

test("membership is decided by definition.engine, never by the name", () => {
  // "TEST - Fast Intraday (5m SMA)" is HAND-MANAGED and its name looks like a
  // machine's. A prefix match would badge it and would miss any engine
  // strategy somebody names plainly.
  const b = engineBook(LIVE, enginePayload());
  const ids = b.rows.map((r) => r.strategy.strategy_id);
  assert.ok(!ids.includes("3c593166"), "a manual strategy with a machine-ish name is not an engine row");
  assert.ok(!ids.includes("sleeve_premia_spy"));
  // An engine named plainly IS included.
  const plain = engineBook(
    [strat({ strategy_id: "x", name: "Quiet little thing", definition: { engine: "lean" } })],
    enginePayload({ strategies: [] }),
  );
  assert.equal(plain.rows.length, 1);
});

test("a blank or non-string engine key is not an engine", () => {
  // `engineOf` trims; a definition carrying `engine: "  "` or `engine: true`
  // would otherwise create a row with an empty badge.
  for (const engine of ["", "   ", true, 0, null, undefined, {}]) {
    const b = engineBook(
      [strat({ strategy_id: "x", definition: { engine } as Record<string, unknown> })],
      enginePayload({ strategies: [] }),
    );
    assert.equal(b.rows.length, 0, `engine=${JSON.stringify(engine)} must not make a row`);
  }
});

// ---------------------------------------------------------------- the label

test("a RUNNING session with no allocation is the warn row, and it is not called a position", () => {
  // The money sentence. LEAN's live-paper brokerage fills the algorithm's
  // order internally whatever the fund decides; the fund's book moves only on
  // an approved fill. Calling this a holding would be a fabricated position.
  const b = engineBook(LIVE, enginePayload());
  const hyg = b.rows.find((r) => r.strategy.strategy_id === HYG)!;
  assert.equal(hyg.headline, "trading via engine · unallocated");
  assert.equal(hyg.tone, "warn");
  assert.equal(hyg.session, "running");
  assert.equal(hyg.sessionAlgorithm, "hyg_fast_flip_probe");
  assert.match(hyg.note, /PROPOSES/);
  assert.match(hyg.note, /Nothing here is a position/);
  assert.equal(b.tradingUnallocated, 1);
});

test("an allocated running engine is NOT counted as unallocated", () => {
  // KILLS M-EB-1 (`allocation_pct > 0` dropped, or `>= 0`). The warn row is an
  // attention request; firing it on a strategy that IS funded teaches the
  // reader to ignore it.
  const funded = LIVE.map((s) =>
    s.strategy_id === HYG ? { ...s, allocation_pct: 12 } : s);
  const b = engineBook(funded, enginePayload());
  const hyg = b.rows.find((r) => r.strategy.strategy_id === HYG)!;
  assert.equal(hyg.headline, "trading via engine · in the book");
  assert.equal(b.tradingUnallocated, 0);
});

test("HOLDING counts as allocated even at a zero target", () => {
  // The C1 lesson, carried: capital at work is a property of the POSITIONS,
  // never of the target weight. A strategy holding $400 at a 0% target is not
  // "unallocated" in the sense this warn row means.
  const holding = LIVE.map((s) =>
    s.strategy_id === HYG ? { ...s, exposure_usd: 400, actual_pct: 20 } : s);
  const b = engineBook(holding, enginePayload());
  assert.equal(b.rows.find((r) => r.strategy.strategy_id === HYG)!.headline,
    "trading via engine · in the book");
  assert.equal(b.tradingUnallocated, 0);
});

test("an archived engine strategy renders, quietly, with its reason", () => {
  const b = engineBook(LIVE, enginePayload());
  const gld = b.rows.find((r) => r.strategy.strategy_id === GLD)!;
  assert.equal(gld.headline, "archived · no session");
  assert.equal(gld.tone, "quiet");
  assert.equal(gld.archived, true);
  assert.match(gld.note, /still on the record/);
});

test("running rows sort first, then live, then by name", () => {
  const b = engineBook(LIVE, enginePayload());
  assert.equal(b.rows[0].session, "running");
  assert.equal(b.rows[b.rows.length - 1].archived, true);
});

// ------------------------------------------------------------- the absences

test("an UNREADABLE engine endpoint is not 'nothing running'", () => {
  // KILLS M-EB-2, and it is the sharpest rule here. A failed engine call must
  // never render a live LEAN container as idle — the container outlives the
  // spine process that started it.
  for (const payload of [null, undefined, enginePayload({ readable: false, reason: "boom" })]) {
    const b = engineBook(LIVE, payload);
    assert.equal(b.sessionsReadable, false);
    assert.equal(b.readable, true, "the rows still come from the strategy list");
    assert.equal(b.rows.length, 2, "the rows do not vanish with the session state");
    for (const r of b.rows) {
      assert.equal(r.session, null);
      assert.equal(r.headline, "session UNKNOWN");
      assert.equal(r.tone, "warn");
      assert.match(r.note, /not the same as no session/);
    }
    assert.equal(b.tradingUnallocated, 0, "an unknown session cannot be counted as running");
  }
});

test("an UNREADABLE strategy list is UNKNOWN, not an empty engine panel", () => {
  const b = engineBook(null, enginePayload());
  assert.equal(b.readable, false);
  assert.deepEqual(b.rows, []);
  assert.match(b.absence ?? "", /UNKNOWN — not none/);
  assert.match(b.absence ?? "", /may be trading right now/);
});

test("a readable list with no engine strategies is a FACT, and says so", () => {
  const b = engineBook(
    LIVE.filter((s) => !s.definition),
    enginePayload({ strategies: [], total: 0 }),
  );
  assert.equal(b.readable, true);
  assert.deepEqual(b.rows, []);
  assert.match(b.absence ?? "", /No strategy on this fund declares an engine/);
});

test("every row carries a note; none is ever blank", () => {
  // A blank region gets filled in optimistically.
  for (const payload of [enginePayload(), null]) {
    for (const r of engineBook(LIVE, payload).rows) {
      assert.ok(r.note.length > 0, `${r.headline} shipped a blank note`);
      assert.ok(r.headline.length > 0);
    }
  }
});

// ------------------------------------------------------- the two sources

test("a strategy the ENGINE knows and the list does not is named, not swallowed", () => {
  // Illumination clause 3. This is exactly the class of defect the whole
  // dispatch is fixing — a strategy visible on one surface and absent from the
  // other — so the page says so rather than picking the prettier count.
  const b = engineBook(
    LIVE.filter((s) => s.strategy_id !== GLD),
    enginePayload(),
  );
  assert.deepEqual(b.unmatched, [GLD]);
  assert.match(engineBookMismatch(b) ?? "", /does not contain/);
  assert.ok(engineBookMismatch(b)!.includes(GLD));
});

test("the normal case says nothing about a mismatch", () => {
  assert.equal(engineBookMismatch(engineBook(LIVE, enginePayload())), null);
});

// -------------------------------------------------------------- the headline

test("the headline names the number that matters, or says there is none", () => {
  const warn = engineBookHeadline(engineBook(LIVE, enginePayload()))!;
  assert.equal(warn.tone, "warn");
  assert.match(warn.text, /1 engine strategy is running with no allocation/);
  assert.match(warn.text, /the book moves on your approval/);

  const funded = LIVE.map((s) => s.strategy_id === HYG ? { ...s, allocation_pct: 9 } : s);
  const quiet = engineBookHeadline(engineBook(funded, enginePayload()))!;
  assert.equal(quiet.tone, "quiet");
  assert.match(quiet.text, /none running unallocated/);
});

test("an unreadable STRATEGY list gets no headline — the panel says it once", () => {
  // FOUND ON THE DEAD-SPINE PASS. The headline used to return `b.absence` and
  // the panel rendered `b.absence` beneath it, so a dead spine printed the same
  // paragraph twice on the Allocate page. Two copies of one fact is how a
  // reader learns a surface is generated rather than written — and it is the
  // third instance of this class this seat shipped in one dispatch.
  const dead = engineBook(null, enginePayload());
  assert.equal(engineBookHeadline(dead), null);
  assert.ok(dead.absence, "the panel still says it, exactly once");
});

test("an unreadable ENGINE endpoint DOES get a headline, because the rows render", () => {
  // The other absence, and it is the opposite case: the rows come from the
  // strategy list, so there ARE rows and nothing else on the panel would say
  // that their session state is unknown.
  const h = engineBookHeadline(engineBook(LIVE, null))!;
  assert.equal(h.tone, "warn");
  assert.match(h.text, /not the same as no session/);
});

test("an empty panel gets no headline at all", () => {
  // A sentence about a state the panel is not in is padding, and padding is
  // how a real entry gets hidden.
  const b = engineBook([], enginePayload({ strategies: [] }));
  assert.equal(engineBookHeadline(b), null);
});

test("plurals are written, not machine-formatted", () => {
  // "1 engine strategy(ies)" is the tell of a number formatted by something
  // that did not look at it, and it shipped once on the engine page.
  const two = LIVE.map((s) => s.strategy_id === GLD ? { ...s, archived: false } : s);
  const payload = enginePayload({
    strategies: enginePayload().strategies.map((c) => ({ ...c, session_state: "running", archived: false })),
  });
  const h = engineBookHeadline(engineBook(two, payload))!;
  assert.match(h.text, /2 engine strategies are running/);
  assert.doesNotMatch(h.text, /\(s\)|\(ies\)/);
});

// ----------------------------------------------- archived AND still running

test("an ARCHIVED strategy with a RUNNING session is its own row, and it is loud", () => {
  // KILLS M-EB-3, and the branch did not exist until the look-pass. A strategy
  // the fund has declared dead, with a live engine session still running it,
  // is strictly worse than "running and unfunded" — and under the old ordering
  // it would have been labelled the milder of the two, because the unallocated
  // branch was tested first.
  const zombie = enginePayload({
    strategies: enginePayload().strategies.map((c) =>
      c.strategy_id === GLD ? { ...c, session_state: "running",
        sessions: [{ session_id: "z", algorithm: "gld_sma_filter", state: "running" }] } : c),
  });
  const b = engineBook(LIVE, zombie);
  const gld = b.rows.find((r) => r.strategy.strategy_id === GLD)!;
  assert.equal(gld.kind, "archived_running");
  assert.equal(gld.tone, "warn");
  assert.match(gld.headline, /archived/);
  assert.match(gld.headline, /RUNNING/);
  // It is NOT counted as unallocated — a different fact needs a different count.
  assert.equal(b.tradingUnallocated, 1, "only the HYG row is 'running and unfunded'");
  assert.equal(b.rows.filter((r) => r.kind === "archived_running").length, 1);
});

test("the unallocated count reads the KIND, not the headline's English", () => {
  // KILLS M-EB-4. Counting rows by comparing `headline` to a string literal
  // makes every re-wording of a sentence a silent change to a number the CEO
  // reads off the panel header.
  const b = engineBook(LIVE, enginePayload());
  assert.equal(b.tradingUnallocated, b.rows.filter((r) => r.kind === "unallocated").length);
  // Every row carries a kind, and the kinds are the closed set.
  const kinds = new Set(["session_unknown", "archived_running", "unallocated",
                         "in_book", "archived", "idle"]);
  for (const r of b.rows) assert.ok(kinds.has(r.kind), `unknown kind ${r.kind}`);
});

test("the headline word appears once per row, not twice", () => {
  // The look-pass found "ARCHIVED  ARCHIVED · NO SESSION" on the rendered row,
  // because the page drew its own archived chip beside a headline that already
  // said it. The module's contract is that the headline is COMPLETE — a
  // renderer needs to add nothing to it.
  for (const r of engineBook(LIVE, enginePayload()).rows) {
    if (r.archived) assert.match(r.headline, /archived/i,
      "an archived row's headline must say so, so the page need not");
  }
});

// ------------------------------------------- closing the mutation survivors

test("a RUNNING engine sorts above a quiet one that would win on name", () => {
  // KILLS B8. The original ordering assertion passed under a mutant that
  // removed the running-first rule, because the only running row also happened
  // to win the name tie-break. The fixture now makes the two rules DISAGREE:
  // "AAA quiet engine" beats "LEAN - HYG…" alphabetically and must still lose.
  const withQuiet = [
    strat({ strategy_id: "aaa", name: "AAA quiet engine", archived: false,
            definition: { engine: "lean" } }),
    ...LIVE,
  ];
  const payload = enginePayload({
    strategies: [
      { strategy_id: "aaa", name: "AAA quiet engine", engine: "lean", state: "draft",
        archived: false, allocation_pct: 0, assets: [], datasource: { readable: true },
        session_state: "none", sessions: [] },
      ...enginePayload().strategies,
    ],
  });
  const b = engineBook(withQuiet, payload);
  assert.deepEqual(b.rows.map((r) => r.strategy.strategy_id), [HYG, "aaa", GLD]);
});

test("a deployed engine strategy is marked as ALSO in the book", () => {
  // KILLS B12 (`inBook` emptied). The field is what stops the panel from
  // reading as a second, contradictory book: without it a deployed engine
  // strategy appears in two lists with nothing saying they are one row.
  const deployed = LIVE.map((s) =>
    s.strategy_id === HYG
      ? { ...s, state: "deployed" as const, actual_pct: 11, exposure_usd: 220 }
      : s);
  const b = engineBook(deployed, enginePayload());
  assert.equal(b.rows.find((r) => r.strategy.strategy_id === HYG)!.inBook, true);
  // ...and an unfunded draft is not.
  assert.equal(b.rows.find((r) => r.strategy.strategy_id === GLD)!.inBook, false);
  assert.equal(engineBook(LIVE, enginePayload()).rows.find((r) => r.strategy.strategy_id === HYG)!.inBook,
    false, "a draft with no exposure is not in the book");
});
