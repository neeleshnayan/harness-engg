/**
 * THE FENCE, AND THE STRATEGY CARDS — the reading side.
 *
 * The spine decides WHETHER a signal is fenced; this file is about whether the
 * page then says the right thing. Two failures are specifically guarded:
 *
 *   1. A fenced row rendering as agreement, or as an alarm. It is neither —
 *      nothing was compared, so nothing agreed, and there is no live engine to
 *      disagree with.
 *   2. The fence removing rows from a verdict SILENTLY. It takes rows out of a
 *      number the CEO reads, so the count and its anchor go on the panel.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  syncLabel,
  sortedSymbolRows,
  driftExplanation,
  reconcileHeadline,
  fenceNote,
  fenceBlindSpots,
  venueNote,
  unknownsList,
  datasourceLine,
  assetsLine,
  sessionLabel,
  classLine,
  sortedCards,
  strategiesAbsence,
  unmatchedSessionNote,
  cardBuckets,
  type EngineLeg,
  type EngineSymbolRow,
  type EngineStrategyCard,
  type EngineStrategies,
  type SignalLedger,
  type SignalRow,
  type EngineView,
} from "./engineView.ts";

const DOMAIN = { events_scanned: 1591, seq_first: 1, seq_last: 1591, scan_limit: 100000, window_bound: false };

const FENCE = {
  version: "v1",
  sessions_readable: true,
  sessions: 0,
  sessions_running: 0,
  sessions_known_since: "2026-08-26T19:09:25.484641+00:00",
  archived_readable: true,
  archived_strategies: 4,
};

function row(over: Partial<EngineSymbolRow> = {}): EngineSymbolRow {
  return {
    strategy_id: "s1", symbol: "GLD", book_qty: 0, engine_qty: null,
    engine_implied_qty: 0.1, drift: 0.1, in_sync: false,
    sync_state: "diverged", fenced: false, signals: { raised: 1, filled: 0 },
    other_fills: 0, ...over,
  };
}

/** The live record's own fenced row: GLD, dead session, archived strategy. */
const FENCED_ROW = row({
  sync_state: "fenced_history", fenced: true, in_sync: null,
  engine_implied_qty: null, drift: null, fenced_implied_qty: 0.1,
  signals_live: 0, signals_fenced: 1,
  fence_reason: "the strategy is ARCHIVED and no session on this record has survived to now",
});

function leg(over: Partial<EngineLeg> = {}): EngineLeg {
  return {
    direct: {
      readable: false, qty_basis: "UNKNOWN", sessions: 0, sessions_running: 0,
      reason: "a live LEAN session publishes no holdings",
      would_need: "the algorithm posting its own holdings",
    },
    implied: {
      basis: "signals", is_model: true, model: "m",
      per_symbol: [FENCED_ROW], symbols_out_of_sync: 0, symbols_undetermined: 0,
      symbols_in_sync: 0, symbols_fenced: 1, book_readable: true,
    },
    signals_raised: 1, signals_not_filled: 1, signals_fenced: 1, signals_live: 0,
    fence: { ...FENCE },
    verdict: { state: "fenced_history", sentence: "Nothing live to reconcile.", symbols: ["GLD"] },
    domain: { ...DOMAIN },
    ...over,
  };
}

// ------------------------------------------------------------------- the fence

test("HISTORY ONLY is quiet — an uncompared thing is never coloured as a pass", () => {
  const h = reconcileHeadline(leg());
  assert.equal(h.word, "HISTORY ONLY");
  assert.equal(h.tone, "quiet");
  assert.notEqual(h.tone, reconcileHeadline(leg({
    verdict: { state: "in_sync", sentence: "x" },
  })).tone);
});

test("a fenced row sorts LAST, below every symbol that actually agrees", () => {
  const rows = sortedSymbolRows(leg({
    implied: {
      ...leg().implied!,
      per_symbol: [
        FENCED_ROW,
        row({ symbol: "AAA", sync_state: "in_sync", in_sync: true, drift: 0 }),
        row({ symbol: "BBB", sync_state: "diverged" }),
        row({ symbol: "CCC", sync_state: "undetermined", in_sync: null }),
      ],
    },
  }));
  assert.deepEqual(rows.map((r) => r.symbol), ["BBB", "CCC", "AAA", "GLD"]);
});

test("a fenced row's explanation is the fence's reason, never a disagreement", () => {
  const e = driftExplanation(FENCED_ROW) ?? "";
  assert.match(e, /ARCHIVED/);
  assert.match(e, /had asked for 0\.1/);
  assert.match(e, /not counted as a disagreement/);
  // THE SHARED-WORD GUARD: "disagree" is the drift branch's word, and the
  // fenced branch must not reach it. Asserting only that the string is
  // non-empty would pass on the wrong branch.
  assert.doesNotMatch(e, /The two books disagree/);
});

test("the fenced count and its anchor go ON THE PANEL, not only in the payload", () => {
  const n = fenceNote(leg()) ?? "";
  assert.match(n, /1 symbol is FENCED HISTORY/);
  assert.match(n, /not counted in the verdict above/);
  // The anchor: without it the reader is told rows were excluded and not what
  // the exclusion was judged against.
  assert.match(n, /2026-08-26T19:09:25/);
});

test("nothing fenced means no fence sentence — a mechanism that has not fired is noise", () => {
  assert.equal(fenceNote(leg({
    implied: { ...leg().implied!, symbols_fenced: 0, per_symbol: [row()] },
  })), null);
  assert.equal(fenceNote(null), null);
});

test("the fence names what it could NOT read, in the safe direction", () => {
  const unread = fenceBlindSpots(leg({
    fence: { ...FENCE, sessions_readable: false },
  }));
  assert.equal(unread.length, 1);
  assert.match(unread[0], /nothing was fenced/);
  assert.match(unread[0], /as if its engine might still be running/);

  const noAnchor = fenceBlindSpots(leg({
    fence: { ...FENCE, sessions_known_since: null },
  }));
  assert.match(noAnchor[0], /could not say when its session memory began/);

  const noRegistry = fenceBlindSpots(leg({
    fence: { ...FENCE, archived_readable: false },
  }));
  assert.match(noRegistry[0], /strategy registry could not be read/);

  // All three readable: nothing to say.
  assert.deepEqual(fenceBlindSpots(leg()), []);
});

test("which session raised a fenced signal is listed as an unknown, only when one is fenced", () => {
  const view = (over: Partial<EngineView> = {}): EngineView => ({
    status: {
      state: "no_session", note: "n", sessions: [], sessions_readable: true,
      last_signal_at: null, last_signal_scope: "s", last_bar_seen: null,
      last_bar_seen_note: "b", liveness_provable: null, liveness_note: "l",
    },
    ledger: {
      signals: [], counts: {}, fenced: null, live: null, fence: null,
      total: 0, returned: 0, sources: [], domain: { ...DOMAIN },
    },
    reconcile: leg(),
    ...over,
  });
  assert.ok(unknownsList(view()).some((u) => /carries no session id/.test(u)));
  const none = view({
    reconcile: leg({ implied: { ...leg().implied!, symbols_fenced: 0 } }),
  });
  assert.ok(!unknownsList(none).some((u) => /carries no session id/.test(u)));
});

// ------------------------------------------------------------------- the venue

function ledgerWith(venues: (string | null)[]): SignalLedger {
  const signals = venues.map((v, i) => ({
    order_id: `o${i}`, status: "declined", outcome: "refused", terminal: true,
    reached_venue: false, venue: v,
  })) as SignalRow[];
  return {
    signals, counts: {}, fenced: null, live: null, fence: null,
    total: signals.length, returned: signals.length, sources: ["lean"],
    domain: { ...DOMAIN },
  };
}

test("a paper-only history says a fill here is a simulator fill", () => {
  const n = venueNote(ledgerWith(["paper"])) ?? "";
  assert.match(n, /PAPER/);
  assert.match(n, /carries no cost information/);
});

test("an alpaca-only history says a fill here is a REAL fill", () => {
  const n = venueNote(ledgerWith(["alpaca", "alpaca"])) ?? "";
  assert.match(n, /real fill at the broker/);
  assert.doesNotMatch(n, /simulator/);
});

test("a MIXED history names the change and counts the simulated side", () => {
  // The shape the record will actually have: the intake proposed `paper` from
  // birth and `alpaca` from 2026-08-26/27, and both rows are on the log
  // forever. A sentence naming one venue would be correct the day it shipped
  // and quietly wrong the next.
  const n = venueNote(ledgerWith(["paper", "alpaca", "alpaca"])) ?? "";
  assert.match(n, /spans a venue change/);
  assert.match(n, /1 signal was proposed against paper/);
  assert.match(n, /the rest against alpaca/);
  assert.match(n, /only evidence of a real fill on the second kind/);
});

test("venue casing and blanks do not create phantom venues", () => {
  const n = venueNote(ledgerWith(["Alpaca", "ALPACA", "  ", null])) ?? "";
  assert.match(n, /real fill at the broker/);
  assert.doesNotMatch(n, /,/);          // one venue, not three
  assert.equal(venueNote(ledgerWith([null, "  "])), null);
});

// ------------------------------------------------------------- the strategy cards

function card(over: Partial<EngineStrategyCard> = {}): EngineStrategyCard {
  return {
    strategy_id: "s1", name: "LEAN - HYG fast flip probe", engine: "lean",
    state: "draft", archived: false, allocation_pct: 0,
    algorithm: "hyg_fast_flip_probe", class_name: "HygFastFlipProbe",
    class_in_definition: "HygFastFlipProbe",
    rule: "hold HYG while fast > slow", assets: ["HYG"],
    assets_basis: "strategy.assets",
    datasource: {
      readable: true, class_name: "SpineBars", base: "PythonData",
      resolution: "daily", transport: "REMOTE_FILE",
      feed_path: "/marketdata/bars",
      feed_origin: "http://host.docker.internal:8090/api/v1/fund",
      lookback_days: 2000, format: "csv", symbols: ["HYG"],
    },
    session_state: "none",
    signals: { raised: 0, filled: 0, in_flight: 0, awaiting: 0, refused: 0, failed: 0 },
    signals_fenced: 0, last_signal: null,
    ...over,
  };
}

test("the datasource line carries the window, because that is what differs", () => {
  const l = datasourceLine(card().datasource);
  assert.match(l, /SpineBars/);
  assert.match(l, /daily bars/);
  assert.match(l, /marketdata\/bars/);
  assert.match(l, /CSV/);
  // The two live algorithms ask for 700 and 2000 days. A panel that dropped
  // this would be right about the class and wrong about the window, in a way
  // no reader could catch because the wrong number is plausible.
  assert.match(l, /2000-day window/);
});

test("an undeclared window is NAMED, never left as a gap a reader fills in", () => {
  const l = datasourceLine(card({
    datasource: { ...card().datasource, lookback_days: null },
  }).datasource);
  assert.match(l, /window NOT DECLARED/);
  assert.doesNotMatch(l, /-day window/);
});

test("an unreadable datasource shows its reason, never a plausible default", () => {
  const l = datasourceLine({
    readable: false,
    reason: "the algorithm file could not be read (LeanError: unknown algorithm 'x')",
  });
  assert.match(l, /could not be read/);
  assert.doesNotMatch(l, /SpineBars/);
  assert.doesNotMatch(l, /daily/);
  // And with no payload at all — UNKNOWN, not none.
  assert.match(datasourceLine(null), /UNKNOWN, not none/);
});

test("the assets line names WHICH field answered", () => {
  assert.match(assetsLine(card()), /HYG \(from strategy\.assets\)/);
  assert.match(
    assetsLine(card({ assets: ["GLD"], assets_basis: "definition.symbol" })),
    /GLD \(from definition\.symbol\)/);
  // No field answered: a sentence, not an empty cell that reads as "none".
  assert.match(assetsLine(card({ assets: [], assets_basis: null })),
               /No field on this strategy names a symbol/);
});

test("session state is FOUR-valued and unreadable is not 'no session'", () => {
  assert.equal(sessionLabel(card({ session_state: "running" })).word, "SESSION RUNNING");
  assert.equal(sessionLabel(card({ session_state: "stopped" })).word, "session stopped");
  assert.equal(sessionLabel(card({ session_state: "none" })).word, "no session");
  const unknown = sessionLabel(card({ session_state: null }));
  assert.equal(unknown.word, "session UNKNOWN");
  assert.equal(unknown.tone, "warn");
  assert.notEqual(unknown.tone, sessionLabel(card({ session_state: "none" })).tone);
});

test("a definition that has drifted from its file is SHOWN, never merged away", () => {
  assert.equal(classLine(card()), "HygFastFlipProbe");
  const drift = classLine(card({ class_name: "RealClass", class_in_definition: "StaleClass" }));
  assert.match(drift, /RealClass/);
  assert.match(drift, /DEFINITION says StaleClass/);
  assert.match(drift, /the file is what runs/);
  // File unreadable: the definition's word, LABELLED as the definition's.
  assert.match(classLine(card({ class_name: null })), /from the definition/);
  assert.equal(classLine(card({ class_name: null, class_in_definition: null })),
               "class UNKNOWN");
});

test("archived strategies stay visible and sort last", () => {
  const s: EngineStrategies = {
    readable: true, total: 2, archived: 1,
    strategies: [
      card({ strategy_id: "a", name: "AAA archived", archived: true }),
      card({ strategy_id: "b", name: "ZZZ live", archived: false }),
    ],
  };
  assert.deepEqual(sortedCards(s).map((c) => c.strategy_id), ["b", "a"]);
});

test("an unreadable registry is UNKNOWN algorithms, not an empty bench", () => {
  const a = strategiesAbsence({
    readable: false, reason: "the strategy registry could not be read",
    strategies: [], total: null, archived: null,
  });
  assert.match(a ?? "", /could not be read/);
  // An EMPTY readable list is a different sentence: a fact about the fund.
  const empty = strategiesAbsence({ readable: true, strategies: [], total: 0, archived: 0 });
  assert.match(empty ?? "", /No strategy on this fund declares an engine/);
  assert.doesNotMatch(empty ?? "", /could not be read/);
  // And with cards there is no absence sentence at all.
  assert.equal(strategiesAbsence({
    readable: true, strategies: [card()], total: 1, archived: 0,
  }), null);
});

test("a live session no strategy accounts for gets its own sentence", () => {
  const n = unmatchedSessionNote({
    readable: true, strategies: [card()], total: 1, archived: 0,
    sessions_unmatched: [{ session_id: "x", algorithm: "ghost_algo", state: "running" }],
  }) ?? "";
  assert.match(n, /1 live session is running/);
  assert.match(n, /ghost_algo/);
  assert.match(n, /running outside anything this page can describe/);
  // The normal case is silence, so the sentence means something when it appears.
  assert.equal(unmatchedSessionNote({
    readable: true, strategies: [card()], total: 1, archived: 0,
    sessions_unmatched: [],
  }), null);
});

test("a card's fate strip carries all five buckets, zero included", () => {
  const b = cardBuckets(card());
  assert.equal(b.length, 5);
  assert.deepEqual(b.map((x) => x.n), [0, 0, 0, 0, 0]);
  // A zero is quiet whatever bucket it sits in, or the absences out-shout the
  // facts — the defect measured on this page's first live reading.
  assert.ok(b.every((x) => x.countTone === "quiet"));
  const withOne = cardBuckets(card({
    signals: { raised: 1, filled: 0, in_flight: 0, awaiting: 0, refused: 1, failed: 0 },
  }));
  assert.equal(withOne.find((x) => x.fate === "refused")!.n, 1);
  assert.notEqual(withOne.find((x) => x.fate === "refused")!.countTone, "quiet");
});
