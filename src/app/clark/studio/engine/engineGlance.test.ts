/**
 * Tests for the engine glance — the trade-ready bar, the fate bar, the signal
 * timeline and the prose demotion.
 *
 * EVERY TEST HERE NAMES THE DEFECT IT PREVENTS, and the defects are the ones
 * this codebase has actually shipped: an absence rendered as a zero, a count
 * whose buckets do not sum, a row dropped because it could not be placed, and
 * a paragraph that describes a control being down disappearing behind a click.
 *
 * The clock is a PARAMETER everywhere. A test that reads `Date.now()` passes
 * at 23:59 and fails at 00:00.
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  ageLabel,
  engineCaveats,
  fateBar,
  firstSentence,
  foldedCaveats,
  glanceTiles,
  instant,
  MIN_POINTS_FOR_DENSITY,
  signalDensity,
  signalLabel,
  signalTimeline,
  sortedSignals,
  surfacedCaveats,
} from "./engineGlance.ts";
import { fateTone, fenceBlindSpots, type EngineView, type SignalLedger, type SignalRow } from "./engineView.ts";

const NOW = Date.parse("2026-08-27T12:00:00Z");

// --------------------------------------------------------------- fixtures

function sig(over: Partial<SignalRow> = {}): SignalRow {
  return {
    order_id: "o1",
    raised_at: "2026-08-27T11:00:00Z",
    source: "lean",
    algo_id: "probe",
    symbol: "HYG",
    side: "buy",
    qty: 1,
    venue: "alpaca",
    status: "filled",
    outcome: "filled",
    terminal: true,
    reached_venue: true,
    ...over,
  };
}

function ledger(over: Partial<SignalLedger> = {}): SignalLedger {
  const signals = over.signals ?? [sig()];
  return {
    signals,
    counts: { filled: 1, in_flight: 0, awaiting: 0, refused: 0, failed: 0, unclassified: 0 },
    fenced: 0,
    live: 1,
    fence: null,
    total: signals.length,
    returned: signals.length,
    sources: ["lean"],
    last_signal_at: signals[0]?.raised_at ?? null,
    domain: { events_scanned: 100, seq_first: 1, seq_last: 100, scan_limit: 100000, window_bound: false },
    ...over,
  };
}

/**
 * ONE CONSTRUCTOR FOR THE WHOLE VIEW, deliberately.
 *
 * ENG2's measured lesson: a fixture that patches one field of a multi-field
 * state is the production defect in test clothes. Every arm below overrides a
 * WHOLE sub-payload, so no test can assert a view that the endpoint could
 * never produce.
 */
function view(over: Partial<EngineView> = {}): EngineView {
  return {
    status: {
      state: "running",
      note: "1 session running. Liveness cannot be proven from here.",
      sessions: [{
        session_id: "s1", algorithm: "hyg_fast_flip_probe", state: "running",
        started_at: "2026-08-26T20:00:00Z", stopped_at: null, log_tail: [],
      }],
      sessions_readable: true,
      last_signal_at: "2026-08-27T11:00:00Z",
      last_signal_scope: "any engine, ever",
      last_bar_seen: null,
      last_bar_seen_note: "UNKNOWN — the session record carries no bar clock.",
      liveness_provable: false,
      liveness_note: "A running session's health is not observable from the spine.",
    },
    ledger: ledger(),
    reconcile: {
      direct: { readable: false, qty_basis: "UNKNOWN", sessions: 1, sessions_running: 1, reason: "a live LEAN session publishes no holdings.", would_need: "the algorithm posting its holdings" },
      implied: {
        basis: "signals", is_model: true, model: "every signal the engine RAISED moves the engine's own paper book. A LEAN container starts FLAT.",
        per_symbol: [], symbols_out_of_sync: 0, symbols_undetermined: 0, symbols_in_sync: 1,
        symbols_fenced: 0, book_readable: true, book_unreadable_reason: null,
      },
      verdict: { state: "in_sync", sentence: "The engine and the fund agree on every symbol. Nothing to do." },
    },
    ...over,
  };
}

// ------------------------------------------------------------------ clocks

test("instant refuses an unparseable stamp instead of returning 1970", () => {
  // KILLS M-CLOCK-1. `new Date(x).getTime()` on rubbish is NaN, and a `|| 0`
  // there would place every unreadable stamp at the epoch — the far left of
  // every axis, looking like the oldest real signal on the record.
  assert.equal(instant(null), null);
  assert.equal(instant(""), null);
  assert.equal(instant("not a date"), null);
  assert.equal(instant("2026-08-27T00:00:00Z"), Date.parse("2026-08-27T00:00:00Z"));
});

test("ageLabel's unit boundaries, as a table", () => {
  // KILLS M-CLOCK-2/3/4 — every one of the three `<` comparisons. A boundary
  // table, not three spot checks: this file's whole subject is inequalities
  // and the seat has shipped two strict-vs-non-strict survivors before.
  const at = (msAgo: number) => ageLabel(new Date(NOW - msAgo).toISOString(), NOW)?.text;
  assert.equal(at(0), "just now");
  assert.equal(at(59_999), "just now");
  assert.equal(at(60_000), "1m ago");
  assert.equal(at(59 * 60_000), "59m ago");
  assert.equal(at(60 * 60_000), "1h ago");
  assert.equal(at(47 * 3_600_000), "47h ago");
  assert.equal(at(48 * 3_600_000), "2d ago");
  assert.equal(at(11 * 86_400_000), "11d ago");
});

test("a stamp AHEAD of the reader's clock says so, and is not a negative age", () => {
  // KILLS M-CLOCK-5. Two clocks disagreeing is a fact about the fund's
  // instruments. "-3m ago" or a cheerful "just now" both hide it.
  const ahead = ageLabel(new Date(NOW + 10 * 60_000).toISOString(), NOW);
  assert.equal(ahead?.text, "ahead of this clock");
  assert.ok((ahead?.ms ?? 0) < 0);
  // Inside a minute of skew is not worth a sentence — that is clock jitter.
  assert.equal(ageLabel(new Date(NOW + 5_000).toISOString(), NOW)?.text, "just now");
});

test("ageLabel returns null for an absent stamp, never a zero age", () => {
  assert.equal(ageLabel(null, NOW), null);
  assert.equal(ageLabel(undefined, NOW), null);
});

// ------------------------------------------------------------- the glance

test("the bar always has five tiles, in order, whatever the payload says", () => {
  // A tile that disappears when it has nothing to say makes "nothing is
  // waiting on you" and "this reading cannot say what is waiting on you" the
  // same rendering — the bucket-that-vanishes defect at tile scale.
  const keys = (v: EngineView | null) => glanceTiles(v, NOW).map((t) => t.key);
  assert.deepEqual(keys(view()), ["engine", "spoke", "signals", "books", "needs"]);
  assert.deepEqual(
    keys(view({ ledger: ledger({ signals: [], counts: {}, total: 0, returned: 0, fenced: null, live: null }) })),
    ["engine", "spoke", "signals", "books", "needs"],
  );
});

test("an unread view yields five tiles that all say UNKNOWN, never zero", () => {
  // KILLS M-TILE-1 (`?? 0` anywhere in the tile fold). The old page rendered
  // `{ledger?.total ?? 0} signals`, which prints a measured zero for a ledger
  // nobody could read.
  const tiles = glanceTiles(null, NOW);
  assert.equal(tiles.length, 5);
  for (const t of tiles) {
    assert.notEqual(t.value, "0", `${t.key} printed a zero for an absence`);
    assert.ok(t.sub.length > 0, `${t.key} shipped a blank sub-line`);
  }
  assert.equal(tiles.find((t) => t.key === "signals")?.value, "UNKNOWN");
  assert.equal(tiles.find((t) => t.key === "signals")?.unknown, true);
  assert.equal(tiles.find((t) => t.key === "needs")?.value, "UNKNOWN");
});

test("a BOUND read window says UNKNOWN, not NEVER", () => {
  // KILLS M-TILE-2, and it is the sharpest absence rule on this page. "No
  // engine has ever raised a signal" is a claim about the whole record. A read
  // that stopped at its scan limit has not established it — it has established
  // that it did not look far enough back.
  const bound = view({
    status: { ...view().status, last_signal_at: null },
    ledger: ledger({
      signals: [], counts: {}, total: 0, returned: 0, last_signal_at: null,
      domain: { events_scanned: 100000, seq_first: 1, seq_last: 100000, scan_limit: 100000, window_bound: true },
    }),
  });
  const spoke = glanceTiles(bound, NOW).find((t) => t.key === "spoke");
  assert.equal(spoke?.value, "UNKNOWN");
  assert.equal(spoke?.unknown, true);
  assert.match(spoke?.sub ?? "", /unread, not absent/);

  const unbounded = view({
    status: { ...view().status, last_signal_at: null },
    ledger: ledger({ signals: [], counts: {}, total: 0, returned: 0, last_signal_at: null }),
  });
  const never = glanceTiles(unbounded, NOW).find((t) => t.key === "spoke");
  assert.equal(never?.value, "NEVER");
  assert.equal(never?.unknown, false);
});

test("an unreadable session list is not 'nothing running'", () => {
  // KILLS M-TILE-3. `sessions_readable: false` with an empty list must never
  // read as an idle engine: an engine we cannot ask about may be doing
  // anything, and the fund has a live LEAN container that outlives its spine.
  const v = view({
    status: {
      ...view().status, state: "unknown", sessions: [], sessions_readable: false,
      note: "the live-session list could not be read",
    },
  });
  const t = glanceTiles(v, NOW).find((x) => x.key === "engine");
  assert.equal(t?.unknown, true);
  assert.match(t?.sub ?? "", /not the same as nothing running/);
  assert.notEqual(t?.value, "NOT RUNNING");
});

test("a fenced count of null is UNKNOWN, and a fenced count of zero is a fact", () => {
  // KILLS M-TILE-4 (`ledger.fenced ?? 0`). Three-valued in, three-valued out:
  // "nothing could ask what is running" and "nothing is fenced" are opposite
  // readings of the same page.
  const cannotAsk = view({ ledger: ledger({ fenced: null, live: null }) });
  assert.match(
    glanceTiles(cannotAsk, NOW).find((t) => t.key === "signals")?.sub ?? "",
    /fenced is UNKNOWN/,
  );
  assert.match(
    glanceTiles(view(), NOW).find((t) => t.key === "signals")?.sub ?? "",
    /still on record/,
  );
});

test("'needs you' counts only what is awaiting a click, and warns only then", () => {
  // KILLS M-TILE-5 (`> 0` → `>= 0`) and M-TILE-6 (counting refusals as
  // pending). A refusal is a decision somebody took; putting it in the queue
  // that asks for the CEO's attention is how a surface cries wolf.
  const quiet = glanceTiles(view(), NOW).find((t) => t.key === "needs");
  assert.equal(quiet?.value, "NOTHING");
  assert.equal(quiet?.tone, "quiet");

  const refusedOnly = view({
    ledger: ledger({ counts: { filled: 0, in_flight: 0, awaiting: 0, refused: 3, failed: 0, unclassified: 0 } }),
  });
  assert.equal(glanceTiles(refusedOnly, NOW).find((t) => t.key === "needs")?.value, "NOTHING");

  const waiting = view({
    ledger: ledger({ counts: { filled: 0, in_flight: 0, awaiting: 2, refused: 0, failed: 0, unclassified: 0 } }),
  });
  const t = glanceTiles(waiting, NOW).find((x) => x.key === "needs");
  assert.equal(t?.value, "2");
  assert.equal(t?.tone, "warn");
});

test("a signal in a state we have no word for reaches the 'needs you' line", () => {
  // The unclassified bucket exists so `sum(counts) == total` holds. If the
  // glance ignored it, a signal would be in the fund's total and on nobody's
  // attention list — the vanishing row, one layer up.
  const v = view({
    ledger: ledger({ counts: { filled: 0, in_flight: 0, awaiting: 0, refused: 0, failed: 0, unclassified: 1 } }),
  });
  assert.match(
    glanceTiles(v, NOW).find((t) => t.key === "needs")?.sub ?? "",
    /no word for/,
  );
});

test("an unreadable fund book is not 'the books agree'", () => {
  const v = view({
    reconcile: {
      ...view().reconcile,
      implied: { ...view().reconcile.implied!, book_readable: false, book_unreadable_reason: "the attribution fold could not be read" },
      verdict: { state: "undetermined", sentence: "The fund's own book could not be read." },
    },
  });
  const t = glanceTiles(v, NOW).find((x) => x.key === "books");
  assert.equal(t?.unknown, true);
  assert.match(t?.sub ?? "", /could not be read/);
});

// ----------------------------------------------------------- the fate bar

test("the fate bar sums to its own domain and says so when the total disagrees", () => {
  // KILLS M-BAR-1. A bar that silently renormalises hides exactly the defect
  // the spine's `sum(counts) == total` assertion exists to surface: a row in
  // the total and in no bucket.
  const ok = fateBar(ledger());
  assert.equal(ok.note, null);
  assert.equal(ok.covered, 1);
  assert.equal(Math.round(ok.segments.reduce((a, s) => a + s.pct, 0)), 100);

  const mismatched = fateBar(ledger({ total: 3 }));
  assert.ok(mismatched.note, "a bar whose domain differs from the total must say so");
  assert.match(mismatched.note ?? "", /sum to 1 and the ledger reports 3 signals/);
});

test("an unnamed bucket gets its own segment rather than being folded away", () => {
  // A bucket this page has no word for is drawn, in warn, with its count. The
  // alternative — dropping unknown keys — is a row that vanishes between the
  // spine and the screen.
  const bar = fateBar(ledger({
    counts: { filled: 1, in_flight: 0, awaiting: 0, refused: 0, failed: 0, unclassified: 1 },
    total: 2,
  }));
  const extra = bar.segments.find((s) => s.fate === "unclassified");
  assert.equal(extra?.n, 1);
  assert.equal(extra?.tone, "warn");
  assert.equal(bar.covered, 2);
  assert.equal(bar.note, null);
});

test("an empty ledger draws no bar and says empty, rather than a full grey bar", () => {
  const bar = fateBar(ledger({ signals: [], counts: {}, total: 0, returned: 0 }));
  assert.equal(bar.empty, true);
  assert.deepEqual(bar.segments, []);
  assert.equal(bar.total, 0);

  const unread = fateBar(null);
  assert.equal(unread.empty, true);
  assert.equal(unread.total, null, "an unread ledger has an UNKNOWN total, not zero");
});

// ----------------------------------------------------------- the timeline

test("the axis ends at NOW, so silence since the last signal is visible", () => {
  // KILLS M-TL-1 (`tEnd = tLast`). An axis that ends at the last signal always
  // puts a point on its right edge, so an engine that spoke ten days ago and
  // one that spoke a minute ago draw identically. That is the single most
  // important thing this graph has to show.
  const old = sig({ order_id: "a", raised_at: "2026-08-16T18:00:00Z" });
  const tl = signalTimeline(ledger({ signals: [old], last_signal_at: old.raised_at }), NOW);
  assert.equal(tl.endIsNow, true);
  assert.equal(tl.points.length, 1);
  assert.equal(tl.points[0].x, 0, "the only signal anchors the left edge");
  assert.equal(tl.degenerate, false);
  assert.equal(tl.endIso, new Date(NOW).toISOString());
});

test("one signal raised at this instant is degenerate, and says so", () => {
  // KILLS M-TL-2 (`span <= 0` → `span < 0`). A zero span cannot be divided;
  // 0/0 is NaN and every point would render off-canvas with no word about it.
  const s = sig({ raised_at: new Date(NOW).toISOString() });
  const tl = signalTimeline(ledger({ signals: [s], last_signal_at: s.raised_at }), NOW);
  assert.equal(tl.degenerate, true);
  assert.equal(tl.points[0].x, 1);
  assert.ok(Number.isFinite(tl.points[0].x));
});

test("points are ordered and spread across the axis by their real times", () => {
  const rows = [
    sig({ order_id: "c", raised_at: "2026-08-27T11:00:00Z", outcome: "refused", status: "declined" }),
    sig({ order_id: "a", raised_at: "2026-08-27T10:00:00Z" }),
    sig({ order_id: "b", raised_at: "2026-08-27T11:30:00Z" }),
  ];
  const tl = signalTimeline(ledger({ signals: rows, total: 3, returned: 3 }), NOW);
  assert.deepEqual(tl.points.map((p) => p.order_id), ["a", "c", "b"]);
  assert.equal(tl.points[0].x, 0);
  assert.equal(tl.points[1].x, 0.5);
  assert.equal(tl.points[2].x, 0.75);
  // NOT "bad". A refusal is a DECISION somebody took, and `fateTone` returns
  // `neutral` for it by a measured decision from the ENG1 look-pass — the
  // refused bucket was the only non-zero count on the live reading and it
  // rendered as the dimmest thing on the strip. The timeline reads its tone
  // from the same function, so a second opinion about what a refusal LOOKS
  // like cannot enter the codebase here.
  assert.equal(tl.points[1].tone, fateTone("refused"));
  assert.equal(tl.points[1].tone, "neutral");
  assert.equal(tl.points[0].tone, fateTone("filled"));
});

test("a signal with no timestamp is carried OUT, never dropped", () => {
  // KILLS M-TL-3. A timeline showing four points beside a header saying five
  // signals is the vanishing row this whole surface was built to catch. The
  // undated row cannot be placed, so it is listed instead.
  const rows = [sig({ order_id: "a" }), sig({ order_id: "b", raised_at: null })];
  const tl = signalTimeline(ledger({ signals: rows, total: 2, returned: 2 }), NOW);
  assert.equal(tl.points.length, 1);
  assert.equal(tl.undated.length, 1);
  assert.equal(tl.undated[0].order_id, "b");
  assert.equal(tl.points.length + tl.undated.length, 2, "every signal is on exactly one list");
});

test("every signal undated means an absence sentence, not an empty graph", () => {
  const rows = [sig({ order_id: "a", raised_at: null }), sig({ order_id: "b", raised_at: "" })];
  const tl = signalTimeline(ledger({ signals: rows, total: 2, returned: 2 }), NOW);
  assert.deepEqual(tl.points, []);
  assert.equal(tl.undated.length, 2);
  assert.match(tl.absence ?? "", /none carrying a timestamp/);
});

test("no signals at all gives the ledger's own absence sentence, with its domain", () => {
  const tl = signalTimeline(ledger({ signals: [], counts: {}, total: 0, returned: 0 }), NOW);
  assert.ok(tl.absence);
  assert.match(tl.absence ?? "", /No engine has ever raised a signal/);
  // A count without its domain is not a result.
  assert.match(tl.absence ?? "", /100 events/);
});

test("an unread ledger is UNKNOWN on the timeline, not an empty axis", () => {
  const tl = signalTimeline(null, NOW);
  assert.match(tl.absence ?? "", /UNKNOWN, not empty/);
  assert.deepEqual(tl.points, []);
});

test("truncation is a sentence on the axis", () => {
  // A shorter axis with no word for it is a lie about the record's shape.
  const tl = signalTimeline(ledger({ total: 40, returned: 1 }), NOW);
  assert.match(tl.note ?? "", /covers 1 of 40 signals/);
});

test("signalLabel never prints a bare id, and never invents a quantity", () => {
  assert.equal(signalLabel(sig({ side: "buy", qty: 0.1, symbol: "GLD" })), "BUY 0.1 GLD");
  assert.equal(signalLabel(sig({ side: null, qty: null, symbol: null })), "qty UNKNOWN SYMBOL UNKNOWN");
  // A genuine zero quantity is a zero, not an absence — the `x ?? 0` twin.
  assert.equal(signalLabel(sig({ side: "sell", qty: 0, symbol: "HYG" })), "SELL 0 HYG");
});

// -------------------------------------------------------------- the prose

test("firstSentence clips at a sentence boundary and never mid-word", () => {
  assert.equal(firstSentence("One. Two. Three."), "One.");
  assert.equal(firstSentence("No boundary here"), "No boundary here");
  // A decimal is not a sentence end. "0.1 GLD was declined." must survive.
  assert.equal(firstSentence("A 0.1 GLD order was declined. Then nothing."),
    "A 0.1 GLD order was declined.");
  assert.equal(firstSentence("Only one sentence."), "Only one sentence.");
});

test("a control being DOWN stays on the surface; the rest goes behind the fold", () => {
  // KILLS M-CAVEAT-1, and it is the one that would make this redesign a
  // loosening. theme.ts illumination clause 5: a disclosure that a control is
  // down renders where the CEO looks, in the warn tone, the moment it exists.
  // Demoting THAT behind a click is the quiet half of a loosening.
  const blind = view({
    reconcile: {
      ...view().reconcile,
      implied: { ...view().reconcile.implied!, symbols_fenced: 1 },
      fence: {
        version: "v1", sessions_readable: false, sessions: null, sessions_running: null,
        sessions_known_since: "2026-08-26T20:00:00Z", archived_readable: true,
        archived_strategies: 4, orphan_containers_checked: false,
        orphan_note: "Nothing asks Docker what is running.",
      },
    },
  });
  const surfaced = surfacedCaveats(blind);
  // The WORDS come from engineView.fenceBlindSpots — one implementation, two
  // forms — so this asserts the PROPERTY (both blind spots reach the surface)
  // rather than a phrasing this file could quietly fork.
  assert.deepEqual(
    surfaced.map((c) => c.full),
    fenceBlindSpots(blind.reconcile),
    "every blind spot the fence reports must reach the surface, in order, unedited",
  );
  assert.ok(surfaced.some((c) => /session list could not be read/.test(c.full)),
    "an unreadable session list must stay visible");
  assert.ok(surfaced.some((c) => /Docker/.test(c.full)),
    "the orphan blind spot must stay visible");
  for (const c of surfaced) assert.equal(c.tone, "warn");
  // And the two lists partition the caveats: nothing is shown twice and
  // nothing is lost between them.
  const all = engineCaveats(blind);
  assert.equal(surfaced.length + foldedCaveats(blind).length, all.length);
  assert.equal(new Set(all.map((c) => c.key)).size, all.length, "caveat keys are unique");
});

test("no caveat is dropped: every demoted paragraph keeps its full text", () => {
  // The redesign's promise is DEMOTION, not deletion. Each caveat carries the
  // paragraph the old page rendered at the front, and `short` is only a
  // clipped view of it.
  const cs = engineCaveats(view());
  assert.ok(cs.length > 0);
  for (const c of cs) {
    assert.ok(c.full.length > 0);
    assert.ok(c.full.startsWith(c.short) || c.full === c.short,
      `${c.key}: the short line must be a prefix of the full text, not a rewrite`);
  }
});

test("an unread view produces no caveats at all, rather than invented ones", () => {
  assert.deepEqual(engineCaveats(null), []);
  assert.deepEqual(surfacedCaveats(undefined), []);
});

// ------------------------------------------------------------- the density

test("no distribution is drawn from fewer than three points", () => {
  // KILLS M-DENS-1. NavPanel has refused to draw a curve from two points
  // since 2026-08-20 for exactly this reason, and the engine will spend its
  // first weeks at n = 1. A one-bar histogram is a claim about a shape.
  const one = signalTimeline(ledger(), NOW);
  const d = signalDensity(one);
  assert.equal(d.drawn, false);
  assert.deepEqual(d.bins, []);
  assert.match(d.note ?? "", /1 signal on the axis/);
  assert.equal(MIN_POINTS_FOR_DENSITY, 3);
});

test("every point lands in exactly one bin, including the one at the right edge", () => {
  // KILLS M-DENS-2 (`Math.floor(x * binCount)` with no clamp). x = 1 floors to
  // binCount, which is off the end of the array — the most recent signal, the
  // one a reader cares about most, would vanish from its own graph.
  const rows = [
    sig({ order_id: "a", raised_at: "2026-08-27T00:00:00Z" }),
    sig({ order_id: "b", raised_at: "2026-08-27T06:00:00Z" }),
    sig({ order_id: "c", raised_at: "2026-08-27T12:00:00Z" }),  // == NOW, so x = 1
  ];
  const tl = signalTimeline(ledger({ signals: rows, total: 3, returned: 3 }), NOW);
  assert.equal(tl.points[2].x, 1);
  const d = signalDensity(tl, 4);
  assert.equal(d.drawn, true);
  assert.equal(d.bins.length, 4);
  assert.equal(d.bins.reduce((a, b) => a + b.n, 0), 3, "no point may be lost between bins");
  assert.equal(d.bins[3].n, 1, "the right-edge point belongs to the LAST bin");
  assert.equal(d.max, 1);
});

test("a degenerate axis draws no distribution, because x carries no information", () => {
  const at = new Date(NOW).toISOString();
  const rows = [sig({ order_id: "a", raised_at: at }), sig({ order_id: "b", raised_at: at }), sig({ order_id: "c", raised_at: at })];
  const tl = signalTimeline(ledger({ signals: rows, total: 3, returned: 3 }), NOW);
  assert.equal(tl.degenerate, true);
  assert.equal(signalDensity(tl).drawn, false);
});

// ---------------------------------------------------------------- the list

test("the ledger list is newest first, and the undated rows are kept at the end", () => {
  // KILLS M-SORT-1 (dropping undated rows) and M-SORT-2 (oldest first). FOUND
  // BY LOOKING at the 42-signal arm: the list under a TIME AXIS read
  // 19d · 5d · 21d · 8d · 13d, so the most recent signal — the row that
  // matters on a page about when the engine last spoke — was unfindable.
  const rows = [
    sig({ order_id: "old", raised_at: "2026-08-01T00:00:00Z" }),
    sig({ order_id: "none", raised_at: null }),
    sig({ order_id: "new", raised_at: "2026-08-27T00:00:00Z" }),
    sig({ order_id: "mid", raised_at: "2026-08-14T00:00:00Z" }),
  ];
  const out = sortedSignals(ledger({ signals: rows, total: 4, returned: 4 }));
  assert.deepEqual(out.map((s) => s.order_id), ["new", "mid", "old", "none"]);
  assert.equal(out.length, rows.length, "no row may be lost to the sort");
});

test("sorting the ledger does not mutate the payload", () => {
  // A sort in place would re-order the array the timeline also reads, so the
  // graph and the list would silently depend on which rendered first.
  const rows = [sig({ order_id: "a", raised_at: "2026-08-01T00:00:00Z" }),
                sig({ order_id: "b", raised_at: "2026-08-27T00:00:00Z" })];
  const led = ledger({ signals: rows, total: 2, returned: 2 });
  sortedSignals(led);
  assert.deepEqual(led.signals.map((s) => s.order_id), ["a", "b"]);
});

test("an unread ledger sorts to an empty list, not a crash", () => {
  assert.deepEqual(sortedSignals(null), []);
  assert.deepEqual(sortedSignals(undefined), []);
});

// ------------------------------------------- closing the mutation survivors
//
// Every test below was written because a MUTANT SURVIVED the suite above.
// Each names its mutant. The one survivor NOT closed here is G16 (the
// divide-by-zero guard in `fateBar`'s pct), which is RETIRED WITH PROOF: when
// `covered === 0` every count is zero, and every NaN pct it would produce
// belongs to a segment the `s.n > 0` filter removes before it can be rendered.
// The guard is kept anyway — it absorbs a second fault if that filter ever
// changes — and it is recorded as not a behaviour fix rather than as a gap.

test("a zero unclassified count adds NOTHING to the 'needs you' line", () => {
  // KILLS G10 (`unclassified > 0` -> `>= 0`). A standing clause reading
  // "· 0 signals in a state this page has no word for" is furniture, and
  // furniture is how a real entry stops being read.
  const clean = glanceTiles(view(), NOW).find((t) => t.key === "needs")!;
  assert.doesNotMatch(clean.sub, /no word for/);
  assert.equal(clean.sub, "no engine signal is waiting on a decision");
});

test("an unreadable session list is UNKNOWN even when the state word is not", () => {
  // KILLS G11. `unknown` was true in the fixtures only because the spine also
  // set `state: "unknown"` — so the sessions_readable clause was doing nothing
  // that the state word was not already doing. A payload that says RUNNING and
  // could not read its session list is exactly the case where the two diverge,
  // and it is the dangerous direction: a confident word over an unread list.
  const v = view({
    status: { ...view().status, state: "running", sessions: [], sessions_readable: false },
  });
  const t = glanceTiles(v, NOW).find((x) => x.key === "engine")!;
  assert.equal(t.value, "RUNNING");
  assert.equal(t.unknown, true, "an unread session list makes the tile an absence");
});

test("an ABSENT sessions_readable is not 'unreadable'", () => {
  // KILLS G12 (`=== false` -> `!x`). The field is optional; an older spine
  // omitting it has said nothing, and "the field is missing" must not render
  // as "the list could not be read". Absence of a disclosure is not a
  // disclosure of absence.
  const v = view({ status: { ...view().status, sessions_readable: undefined } });
  const t = glanceTiles(v, NOW).find((x) => x.key === "engine")!;
  assert.doesNotMatch(t.sub, /could not be read/);
  assert.match(t.sub, /hyg_fast_flip_probe/);
});

test("a degenerate axis does not claim to end NOW", () => {
  // KILLS G20 (`tEnd === nowMs && nowMs > tLast` -> `tEnd === nowMs`). When
  // the only signal is at this instant the axis has no extent, so "now" is
  // not a right edge the reader can measure a silence against.
  const at = new Date(NOW).toISOString();
  const tl = signalTimeline(ledger({ signals: [sig({ raised_at: at })], last_signal_at: at }), NOW);
  assert.equal(tl.degenerate, true);
  assert.equal(tl.endIsNow, false);
  // ...and a real gap DOES claim it.
  const old = signalTimeline(ledger({ signals: [sig({ raised_at: "2026-08-01T00:00:00Z" })] }), NOW);
  assert.equal(old.endIsNow, true);
});

test("an undated row already FIRST in the payload still sorts last", () => {
  // KILLS G30 (`return 1` -> `return 0`). The original assertion passed under
  // the mutant because the undated row happened to sit in the middle of the
  // input and V8's stable sort left it near where it started. A comparator
  // returning 0 for one direction and -1 for the other is INCONSISTENT, and an
  // inconsistent comparator's output is implementation-defined — so the test
  // has to put the undated row where the mutant would visibly keep it.
  const rows = [
    sig({ order_id: "none", raised_at: null }),
    sig({ order_id: "old", raised_at: "2026-08-01T00:00:00Z" }),
    sig({ order_id: "new", raised_at: "2026-08-27T00:00:00Z" }),
  ];
  const out = sortedSignals(ledger({ signals: rows, total: 3, returned: 3 }));
  assert.deepEqual(out.map((s) => s.order_id), ["new", "old", "none"]);
});

// -------------------------------------------- found at the late read-through

test("a MISSING awaiting count is UNKNOWN on the tile that asks for the CEO", () => {
  // `counts` is a loose record by design, so a bucket the spine renames or
  // drops is a real shape — and reading its absence as zero prints "NOTHING"
  // on the one tile whose whole job is "does anything need you". This is the
  // absence-as-zero defect on the most consequential four words on the page.
  const v = view({
    ledger: ledger({ counts: { filled: 1, refused: 0 } }),   // no `awaiting` key
  });
  const t = glanceTiles(v, NOW).find((x) => x.key === "needs")!;
  assert.equal(t.value, "UNKNOWN");
  assert.equal(t.unknown, true);
  assert.equal(t.tone, "warn");
  assert.match(t.sub, /not the same as nothing waiting/);
  // A genuine zero still reads as a fact — without this the fix is a new defect.
  const zero = glanceTiles(view(), NOW).find((x) => x.key === "needs")!;
  assert.equal(zero.value, "NOTHING");
  assert.equal(zero.unknown, false);
});

test("the books tile clips the verdict at a SENTENCE, not at any full stop", () => {
  // The reconciliation verdicts carry quantities — "GLD 0.1 vs 0.0" — and the
  // first version of this read `sentence.split(".")[0]`, which clips one
  // mid-number. `firstSentence` exists three functions away and was not being
  // used here: the fix applied to one member of a family and not its sibling.
  const v = view({
    reconcile: {
      ...view().reconcile,
      verdict: { state: "diverged", sentence: "1 symbol disagrees: GLD 0.1 vs 0.0. Open the ledger." },
    },
  });
  const t = glanceTiles(v, NOW).find((x) => x.key === "books")!;
  assert.equal(t.sub, "1 symbol disagrees: GLD 0.1 vs 0.0.");
});

// ---------------------------------------------- gaps the Gauntlet found

test("the books tile names a DIVERGENCE, and a divergence outranks an undetermined row", () => {
  // FOUND BY THE GAUNTLET: every fixture above carried
  // `symbols_out_of_sync: 0, symbols_undetermined: 0`, so the two branches
  // that describe an ACTUAL disagreement were never exercised — on the tile
  // that answers "do the books agree". A green-path-only fixture set is the
  // fixture-classification defect: the model arm was tested and the call arm
  // was not.
  const diverged = view({
    reconcile: {
      ...view().reconcile,
      implied: { ...view().reconcile.implied!, symbols_out_of_sync: 2, symbols_undetermined: 1 },
      verdict: { state: "diverged", sentence: "2 symbols disagree. Open the ledger." },
    },
  });
  const t = glanceTiles(diverged, NOW).find((x) => x.key === "books")!;
  assert.equal(t.value, "DIVERGED");
  assert.equal(t.tone, "bad");
  assert.equal(t.unknown, false);
  assert.equal(t.sub, "2 symbols where the engine and the fund disagree");
});

test("an undetermined symbol is named when nothing has diverged", () => {
  const undetermined = view({
    reconcile: {
      ...view().reconcile,
      implied: { ...view().reconcile.implied!, symbols_out_of_sync: 0, symbols_undetermined: 1 },
      verdict: { state: "undetermined", sentence: "1 symbol could not be determined." },
    },
  });
  const t = glanceTiles(undetermined, NOW).find((x) => x.key === "books")!;
  assert.equal(t.sub, "1 symbol could not be determined either way");
  // Singular, written. "1 symbol(s)" is the tell of a number nobody looked at.
  assert.doesNotMatch(t.sub, /\(s\)|symbols/);
});

test("foldedCaveats survives an absent view, exactly like its siblings", () => {
  // FOUND BY THE GAUNTLET: `foldedCaveats` is called in production and only
  // its siblings were probed at absence. A null test on two of three
  // functions is a null test on two of three functions.
  assert.deepEqual(foldedCaveats(null), []);
  assert.deepEqual(foldedCaveats(undefined), []);
});
