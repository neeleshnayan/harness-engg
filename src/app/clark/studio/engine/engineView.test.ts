/**
 * ENGINE VIEW — the readings this page must never get wrong.
 *
 * THE INCIDENT (quant, 2026-08-26): a live LEAN session keeps its own paper
 * book, which agrees with the fund's only while every signal it raises is
 * approved. The first DECLINED signal makes them diverge; from then on the
 * engine reasons about stock the fund does not hold. It already happened —
 * GLD, order e035957c, declined 2026-08-16 — and nothing rendered it.
 *
 * Every test here fails if one of the three absences this page keeps apart
 * collapses back into another: a signal never raised reading as agreement, a
 * signal in the queue reading as a failure, or an engine that cannot be read
 * reading as an engine that holds nothing.
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  fateBuckets,
  fateTone,
  ledgerAbsence,
  ledgerTruncation,
  syncWord,
  syncTone,
  reconcileHeadline,
  impliedCaveat,
  sortedSymbolRows,
  driftExplanation,
  engineHeadline,
  unknownsList,
  venueNote,
  FATE_ORDER,
  FATE_HELP,
  type SignalLedger,
  type SignalRow,
  type EngineLeg,
  type EngineStatus,
  type EngineSymbolRow,
} from "./engineView.ts";

// ------------------------------------------------------------------ fixtures

const DOMAIN = { events_scanned: 1569, seq_first: 1, seq_last: 1569, scan_limit: 100000, window_bound: false };

function ledger(over: Partial<SignalLedger> = {}): SignalLedger {
  return {
    signals: [],
    counts: { filled: 0, in_flight: 0, awaiting: 0, refused: 0, failed: 0 },
    total: 0,
    returned: 0,
    sources: [],
    last_signal_at: null,
    domain: { ...DOMAIN },
    ...over,
  };
}

function signal(over: Partial<SignalRow> = {}): SignalRow {
  return {
    order_id: "e035957c-0715-4c5d-b5d8-62c33fd8578c",
    seq: 157,
    raised_at: "2026-08-16T18:59:52.498555+00:00",
    source: "lean",
    algo_id: "gld_sma_filter",
    reason: "GLD crossed above its 100-day SMA",
    strategy_id: "s1",
    strategy_name: null,
    symbol: "GLD",
    side: "buy",
    qty: 0.1,
    venue: "paper",
    status: "declined",
    outcome: "refused",
    terminal: true,
    reached_venue: false,
    decided_at: "2026-08-16T19:00:50+00:00",
    decided_by: "claude:loop-test",
    filled_qty: null,
    avg_price: null,
    filled_at: null,
    failure_reason: null,
    annotations: [],
    ...over,
  };
}

function symbolRow(over: Partial<EngineSymbolRow> = {}): EngineSymbolRow {
  return {
    strategy_id: "s1",
    strategy_name: null,
    symbol: "GLD",
    book_qty: 0,
    engine_qty: null,
    engine_implied_qty: 0.1,
    drift: 0.1,
    in_sync: false,
    signals: { raised: 1, filled: 0, awaiting: 0, refused: 1, in_flight: 0, failed: 0 },
    other_fills: 0,
    ...over,
  };
}

function leg(over: Partial<EngineLeg> = {}): EngineLeg {
  return {
    direct: {
      readable: false,
      qty_basis: "UNKNOWN",
      sessions: 0,
      sessions_running: 0,
      reason: "a live LEAN session publishes no holdings — its session record carries state, container and a log tail only (leanrunner.py). With no session running there is additionally nothing to ask.",
      would_need: "the algorithm posting its own holdings alongside its signals, or the spine reading the session's LEAN results folder",
    },
    implied: {
      basis: "signals",
      is_model: true,
      model: "every signal the engine RAISED moves the engine's own paper book",
      per_symbol: [symbolRow()],
      symbols_out_of_sync: 1,
      symbols_undetermined: 0,
      book_readable: true,
      book_unreadable_reason: null,
    },
    signals_raised: 1,
    signals_not_filled: 1,
    verdict: {
      state: "diverged",
      sentence: "The engine's signals and the fund's book disagree on 1 symbol(s): GLD engine 0.1 vs book 0.0.",
      symbols: ["GLD"],
    },
    ...over,
  };
}

function status(over: Partial<EngineStatus> = {}): EngineStatus {
  return {
    state: "no_session",
    note: "No LEAN session has ever been started on this fund. This is a fact about the fund, not a fault in the engine.",
    sessions: [],
    sessions_readable: true,
    last_signal_at: "2026-08-16T18:59:52.498555+00:00",
    last_signal_scope: "any engine, ever — signals carry no session id",
    last_bar_seen: null,
    last_bar_seen_note: "UNKNOWN — the session record carries no bar clock. Closing this needs the algorithm to report the bar it last processed, or the spine to read the session's LEAN results folder.",
    liveness_provable: null,
    liveness_note: "Nothing has ever run, so there is no liveness question to answer.",
    ...over,
  };
}

// --------------------------------------------------------------------- fates

test("all five fate buckets render, zero included", () => {
  const buckets = fateBuckets(ledger());
  assert.equal(buckets.length, 5);
  assert.deepEqual(buckets.map((b) => b.fate), FATE_ORDER);
  assert.ok(buckets.every((b) => b.n === 0));
});

test("a bucket does not disappear when it is empty", () => {
  // "no signal was refused" and "this reading does not report refusals" must
  // not be the same rendering.
  const b = fateBuckets(ledger({ counts: { filled: 2, in_flight: 0, awaiting: 0, refused: 0, failed: 0 }, total: 2 }));
  const refused = b.find((x) => x.fate === "refused");
  assert.ok(refused, "the refused bucket must still exist");
  assert.equal(refused!.n, 0);
});

test("an unread ledger still renders five buckets rather than nothing", () => {
  assert.equal(fateBuckets(null).length, 5);
  assert.equal(fateBuckets(undefined).length, 5);
});

test("awaiting is not toned as a failure, and failed is", () => {
  assert.notEqual(fateTone("awaiting"), fateTone("failed"));
  assert.equal(fateTone("failed"), "bad");
  assert.equal(fateTone("filled"), "good");
});

test("every fate carries its own sentence, and awaiting says it is not a failure", () => {
  for (const fate of FATE_ORDER) {
    assert.ok(FATE_HELP[fate].length > 10, `${fate} needs a sentence`);
  }
  assert.match(FATE_HELP.awaiting, /not a failure/);
  assert.match(FATE_HELP.refused, /decision/);
});

// ---------------------------------------------------------------- the domain

test("an empty ledger says nothing was raised AND how much was read", () => {
  const s = ledgerAbsence(ledger());
  assert.ok(s);
  assert.match(s!, /No engine has ever raised a signal/);
  assert.match(s!, /1,569 events/);
  assert.match(s!, /seq 1–1569/);
});

test("a BOUND window says the older signal would be unread, not absent", () => {
  const s = ledgerAbsence(ledger({ domain: { ...DOMAIN, window_bound: true, events_scanned: 100000 } }));
  assert.ok(s);
  assert.match(s!, /window BOUND/);
  assert.doesNotMatch(s!, /never/);
});

test("a ledger with rows has no absence sentence", () => {
  assert.equal(ledgerAbsence(ledger({ total: 1, returned: 1, signals: [signal()] })), null);
});

test("truncation is a sentence, never a silently shorter list", () => {
  assert.equal(ledgerTruncation(ledger({ total: 5, returned: 5 })), null);
  assert.equal(ledgerTruncation(ledger({ total: 5, returned: 2 })), "Showing 2 of 5 signals.");
});

// ------------------------------------------------------------ reconciliation

test("a three-valued sync flag never renders null as agreement", () => {
  assert.equal(syncWord(true), "in sync");
  assert.equal(syncWord(false), "DIVERGED");
  assert.equal(syncWord(null), "cannot tell");
  assert.equal(syncWord(undefined), "cannot tell");
  assert.notEqual(syncTone(null), syncTone(true));
});

test("the live divergence gets the DIVERGED headline and the bad tone", () => {
  const h = reconcileHeadline(leg());
  assert.equal(h.word, "DIVERGED");
  assert.equal(h.tone, "bad");
  assert.match(h.sentence, /GLD engine 0\.1 vs book 0\.0/);
});

test("nothing to compare is NOT coloured as passing", () => {
  const h = reconcileHeadline(leg({
    verdict: { state: "no_signals", sentence: "No engine has raised a signal on this record, so there is nothing to reconcile — which is not the same as agreement." },
  }));
  assert.equal(h.word, "NOTHING TO COMPARE");
  assert.notEqual(h.tone, "good");
});

test("an unreadable leg is warned about, not passed", () => {
  const h = reconcileHeadline(leg({ verdict: { state: "unreadable", sentence: "The engine leg could not be built: RuntimeError: boom" } }));
  assert.equal(h.word, "UNREADABLE");
  assert.equal(h.tone, "warn");
});

test("an absent leg is UNREAD, not in sync", () => {
  const h = reconcileHeadline(null);
  assert.equal(h.word, "UNREAD");
  assert.notEqual(h.tone, "good");
});

test("an in-sync leg reads as good", () => {
  const h = reconcileHeadline(leg({ verdict: { state: "in_sync", sentence: "All 1 symbol(s) agree." } }));
  assert.equal(h.word, "IN SYNC");
  assert.equal(h.tone, "good");
});

test("the implied caveat names UNKNOWN and what would close it", () => {
  const c = impliedCaveat(leg());
  assert.ok(c);
  assert.match(c!, /UNKNOWN/);
  assert.match(c!, /IMPLY, not what it reports/);
  assert.match(c!, /results folder/);
});

test("a readable engine would drop the caveat — the caveat is not decoration", () => {
  const readable = leg();
  readable.direct!.readable = true;
  assert.equal(impliedCaveat(readable), null);
});

test("disagreements sort above undetermined, and both above agreement", () => {
  const rows = sortedSymbolRows(leg({
    implied: {
      ...leg().implied!,
      per_symbol: [
        symbolRow({ symbol: "AAA", in_sync: true }),
        symbolRow({ symbol: "BBB", in_sync: null }),
        symbolRow({ symbol: "CCC", in_sync: false }),
      ],
    },
  }));
  assert.deepEqual(rows.map((r) => r.symbol), ["CCC", "BBB", "AAA"]);
});

test("a drift is explained by the unfilled signals that caused it", () => {
  const e = driftExplanation(symbolRow());
  assert.ok(e);
  assert.match(e!, /1 of 1 signal\(s\) on this symbol never filled/);
});

test("a drift on a strategy with outside fills says so rather than blaming the engine", () => {
  const e = driftExplanation(symbolRow({ other_fills: 2 }));
  assert.ok(e);
  assert.match(e!, /2 fill\(s\) on this strategy came from somewhere other than the engine/);
});

test("an unexplained drift admits it is unexplained", () => {
  const e = driftExplanation(symbolRow({
    signals: { raised: 1, filled: 1, awaiting: 0, refused: 0, in_flight: 0, failed: 0 },
    other_fills: 0,
  }));
  assert.equal(e, "The two books disagree and no signal or outside fill explains it.");
});

test("an agreeing row has no explanation to give", () => {
  assert.equal(driftExplanation(symbolRow({ in_sync: true })), null);
  assert.equal(driftExplanation(symbolRow({ in_sync: null })), null);
});

// -------------------------------------------------------------- engine status

test("no session is quiet, not an alarm", () => {
  const h = engineHeadline(status());
  assert.equal(h.word, "NOT RUNNING");
  assert.equal(h.tone, "quiet");
  assert.notEqual(h.tone, "bad");
  assert.notEqual(h.tone, "warn");
});

test("a running session is neutral — neither a green light nor a red one", () => {
  const h = engineHeadline(status({ state: "running", note: "1 session(s) running. Liveness cannot be proven from here" }));
  assert.equal(h.word, "RUNNING");
  assert.equal(h.tone, "neutral");
});

test("a failed session IS bad, because that state is readable", () => {
  assert.equal(engineHeadline(status({ state: "failed" })).tone, "bad");
});

test("an unreadable session list is warned about, and is not 'not running'", () => {
  const h = engineHeadline(status({ state: "unknown", note: "The live-session list could not be read" }));
  assert.equal(h.word, "UNKNOWN");
  assert.notEqual(h.word, "NOT RUNNING");
  assert.equal(h.tone, "warn");
});

test("an unread status is UNREAD rather than absent", () => {
  assert.equal(engineHeadline(null).word, "UNREAD");
});

// ------------------------------------------------------------ what is unknown

test("the unknowns list names the engine's own holdings", () => {
  const u = unknownsList({ status: status(), ledger: ledger(), reconcile: leg() });
  assert.ok(u.some((s) => /What the engine itself holds/.test(s)));
});

test("with nothing ever running, the bar clock is not listed as a missing answer", () => {
  // A question that does not arise is not an honest entry in an honest list.
  const u = unknownsList({ status: status(), ledger: ledger(), reconcile: leg() });
  assert.ok(!u.some((s) => /bar clock/.test(s)));
});

test("with a session running, the bar clock and the liveness gap ARE listed", () => {
  const u = unknownsList({
    status: status({ state: "running", liveness_provable: false, liveness_note: "A running session's health is not observable from the spine." }),
    ledger: ledger(),
    reconcile: leg(),
  });
  assert.ok(u.some((s) => /bar clock/.test(s)));
  assert.ok(u.some((s) => /not observable from the spine/.test(s)));
});

test("an unreadable session list appears in the unknowns", () => {
  const u = unknownsList({ status: status({ sessions_readable: false }), ledger: ledger(), reconcile: leg() });
  assert.ok(u.some((s) => /Whether any session is running/.test(s)));
});

test("an unreadable fund book appears in the unknowns", () => {
  const l = leg();
  l.implied!.book_readable = false;
  l.implied!.book_unreadable_reason = "RuntimeError: the store is down";
  const u = unknownsList({ status: status(), ledger: ledger(), reconcile: l });
  assert.ok(u.some((s) => /the store is down/.test(s)));
});

test("an unread view has nothing to claim about its unknowns", () => {
  assert.deepEqual(unknownsList(null), []);
});

// ---------------------------------------------------------------- the venue

test("a paper-venue signal is marked as a simulator fill", () => {
  const n = venueNote(ledger({ total: 1, returned: 1, signals: [signal()] }));
  assert.ok(n);
  assert.match(n!, /PAPER venue/);
  assert.match(n!, /carries no cost information/);
});

test("a non-paper venue is reported as itself rather than as paper", () => {
  const n = venueNote(ledger({ total: 1, returned: 1, signals: [signal({ venue: "alpaca" })] }));
  assert.ok(n);
  assert.match(n!, /alpaca/);
  assert.doesNotMatch(n!, /simulator/);
});

test("no signals means no venue claim at all", () => {
  assert.equal(venueNote(ledger()), null);
});
