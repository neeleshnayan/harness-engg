/**
 * SOURCE-LEVEL PINS for the engine page.
 *
 * WHY THIS FILE IS ODD, stated so nobody mistakes it for a real render test:
 * KryptonPay has NO DOM test runner, so every `.tsx` call site in this repo is
 * unverifiable by execution. Mutation proved the cost — T20 (`<Qty v={r.book_qty} />`
 * replaced by `{r.book_qty ?? 0}`, which renders UNKNOWN as a zero on the fund's
 * reconciliation screen) SURVIVED the whole suite.
 *
 * So this reads the SOURCE and pins the small number of expressions where the
 * page could quietly re-introduce the exact defect the module below it exists
 * to prevent. It is weaker than a render test and stronger than nothing, and
 * every assertion here names the mutant it kills.
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const PAGE = readFileSync(join(HERE, "page.tsx"), "utf8");

/**
 * The page with its COMMENTS REMOVED — the surface every NEGATIVE assertion
 * below should read.
 *
 * MEASURED, 2026-08-27, on this file's own new pin: `doesNotMatch(PAGE, /\?\? 0/)`
 * went red on the comment that explains why the `?? 0` was removed. A source
 * scan that reads prose is the shared-word defect pointed at itself — the same
 * class as the `/approve|decline/` pin that failed on the page's own English,
 * and as ENG2's `"are gone"` mutant that walked past a negative assertion by
 * rephrasing.
 *
 * Block comments only (`/* … *​/`), which is the form this page's comments take
 * — including the JSX `{/* … *​/}` ones. A trailing `// …` would survive, and
 * that limitation is stated rather than papered: a stripper that also ate
 * `//` would eat `https://` out of a string literal and quietly weaken every
 * negative pin in this file.
 */
const CODE = PAGE.replace(/\/\*[\s\S]*?\*\//g, "");

test("every quantity cell goes through Qty, which never prints 0 for UNKNOWN", () => {
  // KILLS T20. The four numeric columns of the reconciliation table are the
  // one place on this page where an absence would be indistinguishable from a
  // measured zero, and Qty is the only thing standing between them.
  for (const field of ["r.engine_qty", "r.engine_implied_qty", "r.book_qty", "r.drift"]) {
    assert.ok(
      PAGE.includes(`<Qty v={${field}}`),
      `${field} must be rendered by <Qty>, not interpolated directly`,
    );
  }
  // A positive control: a field this test does NOT know about would not be
  // caught, so assert the set it checks is the set the table renders.
  const cells = [...PAGE.matchAll(/<Qty v=\{([^}]+)\}/g)].map((m) => m[1].trim());
  assert.deepEqual(new Set(cells),
    new Set(["r.engine_qty", "r.engine_implied_qty", "r.book_qty", "r.drift"]));
});

test("Qty renders a word, not a number, when the value is absent", () => {
  assert.match(PAGE, /if \(v == null\) \{[\s\S]{0,200}unknown/);
  assert.match(PAGE, /unknown = "UNKNOWN"/);
});

test("the page reads its verdict words from the module, never inline", () => {
  // A second copy of "in sync" in JSX is how the page and its tested module
  // start disagreeing. The page must call syncWord/reconcileHeadline.
  // Switched from `syncWord(r.in_sync)` to `syncLabel(r.sync_state)` when the
  // fence made `in_sync`'s null mean two things. A page still reading
  // `in_sync` would render a fenced history row in the amber "cannot tell"
  // alarm reserved for a book the spine could not read.
  assert.ok(PAGE.includes("syncLabel(r.sync_state)"));
  assert.doesNotMatch(PAGE, /syncWord|syncTone/);
  assert.ok(PAGE.includes("reconcileHeadline(leg)"));
  assert.ok(PAGE.includes("engineHeadline(status)"));
  assert.doesNotMatch(PAGE, /"in sync"/);
});

test("the figure on the fate strip is toned by countTone, not by bucket", () => {
  // KILLS the page-side half of T1: the module's countTone is useless if the
  // page reaches past it for b.tone.
  assert.ok(PAGE.includes("TONE_TEXT[b.countTone]"));
  assert.ok(!PAGE.includes("TONE_TEXT[b.tone]"));
});

/**
 * Every onClick on this page, and the ONLY two shapes either of them may take.
 *
 * WIDENED 2026-08-27, and the widening is stated rather than done quietly. The
 * old assertion was `deepEqual(handlers, ["() => void load()"])` — a literal
 * list, which the redesign broke the moment a signal row became clickable for
 * its own detail. A literal list is not the property; the property is that no
 * handler REACHES THE SPINE. So this now allows exactly two shapes — the
 * loader, and a local `setOpenSignal` toggle that touches nothing but this
 * component's own state — and fails on anything else, including a third
 * plausible-looking local setter nobody reviewed.
 */
const ALLOWED_HANDLERS = [
  /^\(\) => void load\(\)$/,
  /^\(\) => setOpenSignal\([^)]*\)$/,
];

test("the page has no control that acts — it is a reading", () => {
  // The brief's hard boundary. The only client call is the read.
  const calls = [...PAGE.matchAll(/fundApiClient\.(\w+)/g)].map((m) => m[1]);
  assert.deepEqual([...new Set(calls)], ["getEngine"]);
  // CODE tokens, not prose. The first version of this assertion matched
  // /approve|decline/ against the whole file and failed on the page's own
  // English ("Sitting in the approval queue", "declined") — a doesNotMatch
  // defeated by the very sentences the page exists to say. The Gauntlet's
  // shared-word rule applies to negative assertions too.
  const handlers = [...PAGE.matchAll(/onClick=\{([^}]*)\}/g)].map((m) => m[1].trim());
  assert.ok(handlers.length >= 2, "the loader and the signal toggle both exist");
  for (const h of handlers) {
    assert.ok(ALLOWED_HANDLERS.some((re) => re.test(h)), `unreviewed handler: ${h}`);
  }
  assert.ok(handlers.some((h) => h === "() => void load()"), "the refresh survives");
  assert.doesNotMatch(PAGE, /fundApi\.post|\.post\(|method:\s*"POST"/);
});

test("a failed read clears the payload rather than showing a stale one", () => {
  assert.match(PAGE, /catch \(e\) \{[\s\S]{0,400}setView\(null\)/);
});

// ------------------------------------------------- the fence and the cards (2026-08-27)

test("the fenced row's dead quantity is shown BESIDE the live absence, not instead of it", () => {
  // The clean-field rule's guard rail 2 at the pixel level: annotate, never
  // erase. Without this the fenced row renders UNKNOWN in the engine column
  // and the reader loses the only number the history contains.
  assert.match(PAGE, /r\.fenced && r\.fenced_implied_qty != null/);
  assert.match(PAGE, /was \{r\.fenced_implied_qty\} \(dead session\)/);
});

test("the fence explains itself ON THE PANEL, and names what it could not read", () => {
  // KILLS the page-side half of the loosening: the fence removes rows from a
  // verdict the CEO reads, so a page that computed the fence's domain and
  // never rendered it would ship a number without it.
  //
  // RE-POINTED 2026-08-27. The redesign routes both sentences through
  // `engineCaveats`, which CALLS fenceNote and fenceBlindSpots — asserted in
  // engineGlance.test.ts, where `surfacedCaveats(...).map(c => c.full)` is
  // required to equal `fenceBlindSpots(leg)` exactly. What this file pins is
  // the page's half: the surfaced list is rendered WHOLE and unsliced.
  assert.ok(PAGE.includes("surfacedCaveats(view)"));
  assert.match(PAGE, /warn\.map\(\(c\) =>/);
  assert.doesNotMatch(PAGE, /warn\.slice|warn\[0\]/);
});

test("every strategy-card sentence comes from the module, never inline in JSX", () => {
  // The same rule the verdict words follow: a second copy of a sentence in JSX
  // is how the page and its tested module start disagreeing.
  for (const fn of ["datasourceLine(c.datasource)", "assetsLine(c)", "classLine(c)",
                    "sessionLabel(c)", "cardBuckets(c)", "sortedCards(view?.strategies)",
                    "strategiesAbsence(view?.strategies)",
                    "unmatchedSessionNote(view?.strategies)"]) {
    assert.ok(PAGE.includes(fn), `${fn} must be called, not re-implemented in JSX`);
  }
  // The datasource facts must not be spelled into the page: they are read
  // from the algorithm and they differ per algorithm.
  assert.doesNotMatch(PAGE, /SpineBars|lookback_days|2000-day/);
});

test("an unreadable strategy registry does not render as an engine count of zero", () => {
  // Absence discipline on the panel's own header. `readable === false` is
  // UNKNOWN algorithms; `cards.length` would print 0 and read as "none".
  assert.match(PAGE, /view\?\.strategies\?\.readable === false[\s\S]{0,60}"UNKNOWN"/);
});

test("the archived label and the unmatched-session warning both render", () => {
  // Archived stays VISIBLE — it is the record of what ran, and the fenced row
  // on the panel above has nothing to point at without it.
  assert.match(PAGE, /\{c\.archived &&/);
  assert.match(PAGE, /\{unmatched &&/);
});

test("the page still has no control that acts, after gaining two panels", () => {
  // Re-asserted rather than trusted: the strategy panel is the first thing on
  // this page that renders a per-strategy row, which is exactly the shape a
  // start/stop button would arrive in.
  const handlers = [...PAGE.matchAll(/onClick=\{([^}]*)\}/g)].map((m) => m[1].trim());
  for (const h of handlers) {
    assert.ok(ALLOWED_HANDLERS.some((re) => re.test(h)), `unreviewed handler: ${h}`);
  }
  const calls = [...PAGE.matchAll(/fundApiClient\.(\w+)/g)].map((m) => m[1]);
  assert.deepEqual([...new Set(calls)], ["getEngine"]);
  // The signal toggle is LOCAL state and nothing more. A setter that wrote to
  // anything the spine can see would have arrived in exactly this costume.
  assert.match(PAGE, /const \[openSignal, setOpenSignal\] = useState<string \| null>\(null\)/);
});

test("the fence's residual is rendered, not merely computed", () => {
  // FOUND BY THE GAUNTLET, then closed on both sides. `fenceBlindSpots` now
  // carries the orphan residual — a LEAN container outlives the spine, so a
  // container that went quiet before the last restart is fenced and cannot be
  // told from a dead one. A blind spot that rides in the payload and is never
  // rendered has not been published, so the page must map the WHOLE list and
  // must not slice it.
  //
  // RE-POINTED 2026-08-27 with the redesign: the residual now arrives in the
  // `warn` list, which the page maps whole. The tone is what keeps it ON the
  // surface — `foldedCaveats` is everything else, and a warn caveat that
  // drifted into the fold would be the quiet half of a loosening.
  assert.match(PAGE, /const warn = surfacedCaveats\(view\)/);
  assert.match(PAGE, /const folded = foldedCaveats\(view\)/);
  assert.match(PAGE, /warn\.map\(\(c\) =>/);
  assert.doesNotMatch(PAGE, /warn\.slice|warn\[0\]/);
  // And the fold names its own size. A fold whose label does not say how much
  // is behind it is an omission with a chevron on it.
  assert.match(PAGE, /\{folded\.length\} thing/);
});

// ------------------------------------------- the glance redesign (2026-08-27)

test("all five tiles are rendered, whole and unsliced", () => {
  // KILLS T-GLANCE-1. `glanceTiles` guarantees five tiles in a fixed order
  // precisely so that "nothing is waiting on you" and "this reading cannot say
  // what is waiting on you" render differently. A page that sliced the list,
  // or filtered the empty ones out, would undo that in the renderer.
  assert.match(PAGE, /const tiles = glanceTiles\(view, readAt\)/);
  assert.match(PAGE, /\{tiles\.map\(\(t\) => <Tile key=\{t\.key\} t=\{t\} \/>\)\}/);
  assert.doesNotMatch(PAGE, /tiles\.slice|tiles\.filter|tiles\[\d\]/);
});

test("an UNKNOWN tile is styled as an absence, not as a figure", () => {
  // The tile-scale form of the KT.heroDim lesson: a composition of
  // `${KT.hero} ${KT.muted}` loses, because both carry a text colour at equal
  // specificity. So the branch is explicit and it is on `unknown`, not on the
  // tone — a warn tone is also what a real amber number wears.
  assert.match(PAGE, /t\.unknown\s*\?\s*"text-\[var\(--kt-text-muted\)\]"\s*:\s*TONE_TEXT\[t\.tone\]/);
});

test("the ages are measured against the READ, not against the render", () => {
  // KILLS T-GLANCE-2. `Date.now()` inside the render body makes "11d ago"
  // refer to whenever React last re-drew rather than to when the payload
  // landed — and on a page whose entire subject is how stale things are, that
  // is the defect wearing the fix's clothes. The clock is stamped once, in
  // load(), and passed in.
  assert.match(PAGE, /setReadAt\(Date\.now\(\)\)/);
  const clocks = [...PAGE.matchAll(/Date\.now\(\)/g)];
  assert.equal(clocks.length, 1, "exactly one clock read on this page, and it is in load()");
  for (const fn of ["glanceTiles(view, readAt)", "signalTimeline(ledger, readAt)"]) {
    assert.ok(PAGE.includes(fn), `${fn} must take the read's clock`);
  }
});

test("a signal the axis cannot place is rendered, not silently absent", () => {
  // KILLS T-GLANCE-3, and it is the vanishing-row defect at graph scale: a
  // timeline showing four points beside a header saying five signals.
  assert.match(PAGE, /timeline\.undated\.length > 0/);
  assert.match(PAGE, /timeline\.undated\.map\(\(u\) => u\.label\)/);
});

test("a fenced point is drawn HOLLOW, and the ledger's own words decide it", () => {
  // A solid dot claims the signal still testifies about a live engine. The
  // fenced ones describe a paper book that is gone.
  assert.match(PAGE, /p\.fenced[\s\S]{0,200}bg-transparent/);
});

test("the distribution is drawn from the module's rule, never from a page-local threshold", () => {
  // A second opinion about how few points is too few is how this page and
  // NavPanel start disagreeing about what an honest curve is.
  assert.ok(PAGE.includes("signalDensity(timeline)"));
  assert.match(PAGE, /density\.drawn \?/);
  assert.doesNotMatch(PAGE, /points\.length [<>]=? \d/);
  assert.doesNotMatch(PAGE, /MIN_POINTS/);
});

test("no absence on this page is rendered through `?? 0`", () => {
  // KILLS T-GLANCE-4. The page this replaced printed `{ledger?.total ?? 0}
  // signals` in its own header — a measured zero for a ledger nobody read.
  // Every count now comes from the tile fold, which is three-valued.
  assert.doesNotMatch(CODE, /\?\?\s*0\b/);
  // Positive controls on the stripper — a scan whose domain has been eaten
  // returns a clean pass over nothing (the null-test rule: a zero without its
  // domain is not a result).
  assert.ok(CODE.includes("glanceTiles(view, readAt)"));
  assert.ok(CODE.length > PAGE.length / 2, "the comment stripper ate the page");
});

test("the density bars are painted through fill, never a Tailwind opacity class", () => {
  // KILLS T-GLANCE-5, FOUND BY LOOKING at the 42-signal arm. Tailwind cannot
  // apply the `/40` opacity modifier to an arbitrary CSS variable, so
  // `fill-[var(--kt-accent)]/40` is dropped entirely and SVG falls back to its
  // own default fill: BLACK, on a black panel. Every bar of the new graph was
  // invisible and the whole suite was green.
  assert.match(CODE, /fill="var\(--kt-accent\)"/);
  assert.match(CODE, /fillOpacity=\{[\d.]+\}/);
  assert.doesNotMatch(CODE, /fill-\[var\(--kt-[a-z-]+\)\]\/\d/);
});

test("the ledger list is rendered through the sorted fold, not in payload order", () => {
  // The list sits under a time axis; payload order put 19d before 5d before
  // 21d. The sort is a tested pure function, and the page must not re-open it.
  assert.match(CODE, /sortedSignals\(ledger\)\.map/);
  assert.doesNotMatch(CODE, /ledger\?\.signals \?\? \[\]\)\.map/);
});

test("the no-signals absence is said ONCE, by the timeline", () => {
  // KILLS T-GLANCE-6, FOUND BY LOOKING at the empty arm. The page rendered
  // `timeline.absence` AND `ledgerAbsence(ledger)`, which return the same
  // sentence when nothing was ever raised — so the empty arm printed the same
  // paragraph twice, one inset directly above the other. Two copies of one
  // fact is how a reader learns the page is generated rather than written.
  assert.ok(CODE.includes("timeline.absence"));
  assert.doesNotMatch(CODE, /ledgerAbsence/);
});
