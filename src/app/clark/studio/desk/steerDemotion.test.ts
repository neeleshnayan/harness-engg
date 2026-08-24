import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

/**
 * THE STEERING SENTENCE IS A FOOTNOTE, NOT A HEADLINE (2026-08-24).
 *
 * MEASURED ON THE LIVE DESK BEFORE THE CHANGE (CDP, 1440×2400, the geometry
 * probe kept at `scratchpad/kpp_probe_header.js`): the steering sentence
 * rendered **73px tall at 15px in the warn amber, 282 characters, three
 * lines** — the TALLEST block in a 244px header, taller than the hero line
 * (41px), sitting directly under a page whose own docstring says *"the number
 * is the only hero-scale thing"* and whose design brief says *hierarchy from
 * type and space, never colour*. Three amber lines arguing with the spec above
 * them, on the surface the CEO opens first.
 *
 * AFTER: **59px at 12px, muted**, below the shelves and below the caveat about
 * the number, in the same metadata register the spend-demotion rule put token
 * counts in (`docs/design/RUN_PAGE_2026-08-24.md` — *"the work is the face;
 * the spend is a footnote"*). Header 244px → 209px.
 *
 * THE HONEST RESIDUAL, stated because a test that only reports the win is an
 * advertisement: it is STILL the tallest block in the header, because its
 * length is CONTENT — a clamped 120-char pointer plus the spine's truncation
 * caveat plus the ranking key. What changed is scale, tone and position, not
 * the number of characters, and no character was removed.
 *
 * WHY A SOURCE-LEVEL TEST. This repo's runner is node's own type stripper,
 * which REFUSES `.tsx`, so nothing here can mount a component. That leaves
 * checking the source or checking nothing (`spendDemotion.test.ts`, same
 * reasoning, same file family). EVERY POSITIONAL ASSERTION BELOW IS PAIRED
 * WITH A NULL TEST: a landmark that cannot be found makes a position check
 * pass vacuously, and this file's first job is to prove its landmarks exist.
 */

const RAW = readFileSync(new URL("./ceo/page.tsx", import.meta.url), "utf8");
/** Comment-stripped. A rule that lives in a comment is not a rule — this repo
 *  has already shipped a source test that passed on its own prose (D20/D28). */
const SRC = RAW.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^[ \t]*\/\/.*$/gm, "");
const HEADER = (() => {
  const a = SRC.indexOf("<header");
  const b = SRC.indexOf("</header>");
  return a > 0 && b > a ? SRC.slice(a, b) : "";
})();

test("THE LANDMARKS EXIST (the null test for every position asserted below)",
  () => {
    assert.ok(HEADER.length > 200, "the header element must parse out");
    assert.ok(HEADER.includes("{heroFigure(headline)}"), "the hero figure");
    assert.ok(HEADER.includes("shelves.decideToday"), "the shelf line");
    assert.ok(HEADER.includes("{steer.text}"), "the steering sentence");
    assert.ok(HEADER.includes("headline.note"), "the caveat about the number");
  });

test("THE SENTENCE IS NOT DELETED. A demotion is a MOVE — the content is real "
  + "and it is the one line that says what to do next", () => {
  assert.ok(HEADER.includes("{steer.text}"),
    "the steer must still render; removing it would be a different change "
    + "wearing this one's name");
  assert.ok(SRC.includes("steeringSentence({"),
    "and it must still be computed from the spine's own ranking");
});

test("IT RENDERS BELOW THE SHELVES AND BELOW THE CAVEAT — the header now reads "
  + "greeting, number, shelves, caveat, footnote", () => {
  const hero = HEADER.indexOf("{heroFigure(headline)}");
  const shelf = HEADER.indexOf("shelves.decideToday");
  const caveat = HEADER.indexOf("headline.note");
  const steer = HEADER.indexOf("{steer.text}");
  for (const [name, i] of [["hero", hero], ["shelf", shelf],
    ["caveat", caveat], ["steer", steer]] as const) {
    assert.ok(i > 0, `${name} not found — this test has gone stale`);
  }
  assert.ok(hero < shelf, "the number comes first");
  assert.ok(shelf < steer, "the steer sits below the shelves");
  assert.ok(caveat < steer,
    "and below the caveat, which must stay next to the figure it qualifies");
});

test("IT RENDERS AT THE METADATA SCALE, not at reading scale. `text-[15px]` "
  + "was 73px of amber above the caveat; the register for a footnote on this "
  + "desk is `text-xs`", () => {
  const line = HEADER.split(/\r?\n/)
    .find((l) => l.includes("steer.text"));
  assert.ok(line, "the steer's render line must be findable");
  // The class sits on the enclosing <p>, which is the line before the text on
  // this page. Search the small window around it rather than the whole header,
  // so a `text-xs` belonging to some other element cannot satisfy this.
  const at = HEADER.indexOf("{steer.text}");
  const window = HEADER.slice(Math.max(0, at - 240), at);
  assert.match(window, /text-xs/,
    "the steering sentence must render in the metadata register");
  assert.ok(!/text-\[15px\]/.test(window),
    "15px is reading scale — that is the size this change came from");
});

test("THE COLOUR IS SPENT ON THE COUNT, NOT ON THE PROSE. `steer.overdue` "
  + "still drives a hue, and it drives it on the shelf line's figure — one "
  + "condition, one alarm", () => {
  /* Demoting the size and keeping the amber was tried first and looked at:
   * three amber lines at 12px are still three amber lines. The words "due
   * TODAY" and "N days OVERDUE" remain in the sentence either way, so nothing
   * is silenced — what goes is a second alarm about the same fact, thirty
   * times the area of the first. */
  const at = HEADER.indexOf("{steer.text}");
  const window = HEADER.slice(Math.max(0, at - 240), at);
  assert.ok(!/sev\.warn/.test(window),
    "the steering paragraph must not carry the warn tone");
  const shelfAt = HEADER.indexOf("shelves.decideToday");
  const shelfWindow = HEADER.slice(Math.max(0, shelfAt - 200), shelfAt);
  assert.match(shelfWindow, /steer\.overdue \? KT\.sev\.warn/,
    "the overdue condition must still colour the count — dropping it here "
    + "would turn this demotion into a removal");
});

test("THE RANKING KEY RIDES WITH IT. The steer and the key it is arguing from "
  + "are one thought and were two paragraphs only because the steer used to "
  + "be a headline", () => {
  const at = HEADER.indexOf("{steer.text}");
  const after = HEADER.slice(at, at + 400);
  assert.match(after, /ranked by \$\{engine\.decisions\.ranked_by\}/,
    "the ranking key must render in the same paragraph, after the sentence");
  assert.match(after, /the spine stated no ranking key/,
    "and an ABSENT key must still say so — a missing ranking key is a fact "
    + "about the spine, not an empty string");
});
