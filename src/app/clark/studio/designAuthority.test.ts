import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, relative } from "node:path";

/**
 * THE DESIGN AUTHORITY, MADE ENFORCEABLE.
 *
 * The CEO's standard for the Studio, verbatim 2026-08-23: *"the beautiful desk
 * ui which is uncluttered and doesnt feel generic ai slop"*. `theme.ts` is the
 * single source of styling truth and its own header already says so — but a
 * rule written in a docstring is a rule nothing enforces, which is the pattern
 * this firm keeps paying for. This file is the enforcement.
 *
 * WHAT IT FORBIDS, and each entry is here because it is a specific way a
 * calm surface turns into a generic one:
 *
 *   - **gradient fills** — a wash on a panel that sits on screen all day is
 *     decoration that never stops asking for attention (theme.ts says this
 *     about `agent.wash` and then nothing checked the rest of the Studio);
 *   - **`shadow-*` beyond what theme.ts blesses** — theme.ts blesses NONE.
 *     Hierarchy comes from type and space; a drop shadow is depth borrowed
 *     from a different design language;
 *   - **new hex colours** — every colour is a `--kt-*` variable in
 *     `studio-theme.css` so light and dark cannot drift apart;
 *   - **a third accent hue** — emerald is the fund, violet is the machine,
 *     and an operator scanning in seconds must never mistake a sentence a
 *     model wrote for a number the fund computed. Tailwind's named palettes
 *     (`text-blue-600`, `bg-purple-500`) are how a third one arrives;
 *   - **emoji** — in a heading, a label, or anywhere else in this subtree.
 *
 * THREE REAL VIOLATIONS WERE LIVE WHEN THIS WAS WRITTEN and are fixed in the
 * same commit: a `bg-gradient-to-r from-blue-600 to-purple-600` submit button
 * in AllocationModal (a gradient AND two foreign hues, on the Studio's primary
 * action), `shadow-lg` on the Clark launcher, and `shadow-2xl` on the
 * simulation dialog. The rule was in the docstring the whole time.
 *
 * SCOPE: `src/app/clark/studio/**`, excluding `studio/thesis/**`, which is
 * Abhishek's surface and is not this seat's to police.
 */

const HERE = dirname(fileURLToPath(import.meta.url));

/** Every source file under the Studio, minus the surfaces we do not own. */
function studioFiles(dir = HERE, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) {
      // Abhishek's thesis surface is out of bounds for this seat, including
      // for a lint rule: policing a colleague's file is still touching it.
      if (name === "thesis") continue;
      studioFiles(p, out);
    } else if (/\.(ts|tsx|css)$/.test(name) && !/\.test\.ts$/.test(name)) {
      out.push(p);
    }
  }
  return out;
}

const FILES = studioFiles();

/** `studio-theme.css` is where colour is DEFINED; the rules below are about
 *  everywhere else. */
const isThemeCss = (p: string) => p.endsWith("studio-theme.css");
const rel = (p: string) => relative(HERE, p).replace(/\\/g, "/");

function scan(re: RegExp, opts: { skipThemeCss?: boolean } = {}) {
  const hits: string[] = [];
  for (const p of FILES) {
    if (opts.skipThemeCss && isThemeCss(p)) continue;
    const src = readFileSync(p, "utf8");
    src.split(/\r?\n/).forEach((line, i) => {
      // A rule NAMED in a comment is not a rule BROKEN. Without this the
      // docstrings above — which quote every forbidden token — would fail the
      // very tests they explain.
      const code = line.replace(/\/\/.*$/, "").replace(/\/\*.*?\*\//g, "");
      if (re.test(code)) hits.push(`${rel(p)}:${i + 1}  ${line.trim().slice(0, 110)}`);
    });
  }
  return hits;
}

test("the Studio has at least one file to police", () => {
  /* THE INSTRUMENT'S OWN NULL TEST. Every assertion below is "this scan found
   * nothing", and a scan over an empty file list finds nothing too. Without
   * this, a broken glob would turn the whole file green. */
  assert.ok(FILES.length > 40, `only ${FILES.length} files scanned`);
  assert.ok(FILES.some((p) => p.endsWith("theme.ts")));
  assert.ok(!FILES.some((p) => rel(p).startsWith("thesis/")),
    "Abhishek's surface must not be scanned, let alone policed");
});

test("the scanner can SEE a violation when there is one", () => {
  /* The second half of the null test: prove the regexes match real strings,
   * so a green result means "nothing found" and not "nothing matched, ever". */
  const gradient = /\bbg-gradient-to-|\blinear-gradient\(/;
  assert.ok(gradient.test('className="bg-gradient-to-r from-blue-600"'));
  assert.ok(/\bshadow-(sm|md|lg|xl|2xl)\b/.test('className="p-2 shadow-lg"'));
  assert.ok(/#[0-9a-fA-F]{3,8}\b/.test("color: #1a1a1a"));
  assert.ok(/\b(?:text|bg|border|from|to|via)-(?:blue|purple|indigo|pink|orange|yellow|teal|cyan|fuchsia|rose|lime)-\d{2,3}\b/
    .test('className="text-blue-600"'));
});

test("no gradient fills anywhere in the Studio", () => {
  const hits = scan(/\bbg-gradient-to-|\blinear-gradient\(/, { skipThemeCss: false });
  assert.deepEqual(hits, [],
    "a wash on a panel that sits on screen all day is decoration that never "
    + "stops asking for attention — theme.ts says so about the Clark rail and "
    + "the rule is the Studio's, not one component's");
});

test("no drop shadows — theme.ts blesses none", () => {
  const hits = scan(/\b(?:drop-)?shadow-(?:sm|md|lg|xl|2xl|inner)\b/);
  assert.deepEqual(hits, [],
    "hierarchy comes from TYPE SCALE and SPACE, never from depth borrowed "
    + "from another design language");
});

test("no new hex colours outside studio-theme.css and the ONE named bridge", () => {
  /* THE EXEMPTION IS NAMED, NOT IMPLIED, and it is narrower than it looks.
   * `chartColors.ts` holds literal hexes because charting libraries PARSE
   * colour strings in JavaScript, where `var(--kt-accent)` throws — the module
   * documents that and the exemption rests on it. It is not a licence to
   * choose colours: `chartColors.test.ts` parses `studio-theme.css` and
   * asserts every literal against its token, in both themes, and that test
   * exists because every dark value HAD drifted (accent #34d399 vs #79a98c).
   * So the file is exempt from THIS rule and held to a stricter one. */
  const hits = scan(/#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?\b/, { skipThemeCss: true })
    // An `#rec-id` style anchor or a `#` in prose is not a colour; only a
    // literal that parses as one, in a styling position, counts.
    .filter((h) => /(?:color|background|border|fill|stroke|shadow)[^;]*#[0-9a-fA-F]{3}/i.test(h)
                || /["'`][^"'`]*#[0-9a-fA-F]{6}\b/.test(h))
    .filter((h) => !h.startsWith("chartColors.ts:"));
  assert.deepEqual(hits, [],
    "every colour is a --kt-* variable in studio-theme.css, which is what "
    + "keeps light and dark from drifting apart");
});

test("the hex exemption covers exactly ONE file, and that file is still policed", () => {
  /* A guard whose scope is a literal has a quiet off-switch (D27): if someone
   * adds a second exemption above, this fails. And if the stricter test that
   * justifies the exemption is ever deleted, this fails too. */
  const exempted = scan(/#[0-9a-fA-F]{6}\b/, { skipThemeCss: true })
    .filter((h) => /["'`][^"'`]*#[0-9a-fA-F]{6}\b/.test(h))
    .map((h) => h.split(":")[0]);
  assert.deepEqual([...new Set(exempted)], ["chartColors.ts"],
    "exactly one file may hold literal colours, and it is the charting bridge");
  const guard = readFileSync(join(HERE, "chartColors.test.ts"), "utf8");
  assert.match(guard, /studio-theme\.css/,
    "the exemption is only legitimate while a test pins those literals to the "
    + "stylesheet they claim to mirror");
});

test("no third accent hue — emerald is the fund, violet is the machine", () => {
  const hits = scan(
    /\b(?:text|bg|border|from|to|via|ring|fill|stroke)-(?:blue|purple|indigo|pink|orange|yellow|teal|cyan|fuchsia|rose|lime|sky|violet)-\d{2,3}\b/,
    { skipThemeCss: true });
  assert.deepEqual(hits, [],
    "an operator scanning in seconds must never mistake a sentence a model "
    + "wrote for a number the fund computed; a third hue breaks that split");
});

test("no emoji anywhere in the Studio", () => {
  /* PICTOGRAPHS ONLY, AND THE NARROWING IS DELIBERATE. The first cut swept in
   * U+2600–U+27BF, which is Miscellaneous Symbols and Dingbats — and caught
   * the `✓` / `✗` beside a pass/kill count in MechanicsViews. Those are
   * typographic marks this codebase uses as glyphs, in a monospace run of
   * figures, and they are not what "generic ai slop" means. Banning them
   * would make this rule about taste rather than about the failure mode, and
   * a rule that fires on things nobody objects to gets suppressed.
   *
   * What IS banned is the pictographic planes plus the emoji variation
   * selector — the `🛢️ Geopolitical Oil Spike` scenario labels this test
   * found live, which are exactly the failure mode. */
  const hits = scan(/[\u{1F300}-\u{1FAFF}\u{FE0F}]/u);
  assert.deepEqual(hits, [],
    "the CEO's standard for this surface is that it must not feel generic; "
    + "an emoji in a label is the fastest way there");
});

test("theme.ts is still the single source, and still says so", () => {
  /* A traceability check, deliberately separate from the behavioural scans
   * above: the rules are only legitimate because the theme file claims the
   * authority they enforce. If that claim is ever deleted, these tests become
   * this file's opinion rather than the codebase's rule. */
  const theme = readFileSync(join(HERE, "theme.ts"), "utf8");
  assert.match(theme, /THE single source of truth for Studio styling/);
  assert.match(theme, /emerald accent/);
  assert.match(theme, /NEVER branches on the active theme/);
});
