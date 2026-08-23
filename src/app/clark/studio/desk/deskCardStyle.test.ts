/**
 * The decision card's type scale — and the invisible-class trap it closes.
 *
 * THE DEFECT, found by MEASURING a rendered page rather than reading the source
 * (2026-08-22). The card container was written as `${KT.card} p-4`, which reads
 * as "a card with 16px padding" and is not: `KT.card` already contains `p-5`,
 * and Tailwind resolves equal-specificity utilities by their order in the
 * generated stylesheet, not by their order in the class attribute. `p-5` is
 * emitted after `p-3` and `p-4`, so it wins every time.
 *
 * Chrome reported `padding: 20px` on all three cards while the source said 12,
 * 16 and 16. **The space half of "hierarchy from type and space" was doing
 * nothing, and nothing on screen said so.** `${KT.card} p-3` is written in
 * several other places in this codebase and is silently inert in all of them.
 *
 * There is no DOM test runner here, so this cannot assert a computed style. It
 * asserts the property that makes the computed style knowable instead: the
 * container carries exactly one padding utility and is never built on the
 * pre-padded card.
 *
 * Run: `node --experimental-strip-types --test src/app/clark/studio/desk/deskCardStyle.test.ts`
 */

import { strict as assert } from "node:assert";
import { test } from "node:test";
import { readFileSync } from "node:fs";

import { cardStyle, cardStyleIsSound } from "./deskCardStyle.ts";
import { KT } from "../theme.ts";

const ALL = ["irreversible", "hard", "unclassified", "reversible",
             "something-nobody-defined"];

test("every card style can actually take effect", () => {
  for (const r of ALL) {
    const s = cardStyle(r);
    const bad = cardStyleIsSound(s);
    assert.equal(bad, null, `${r}: ${bad}`);
  }
});

test("the guard itself detects the trap it was written for", () => {
  /* A checker that cannot fail is not a checker. The first string below is
   * character-for-character what the page had — `${KT.card} p-4`, which the
   * browser rendered as 20px. */
  assert.ok(cardStyleIsSound({
    container: `${KT.card} p-4`, text: "", weight: "hard",
  }), "`${KT.card} p-4` is the exact defect and must be caught");
  assert.ok(cardStyleIsSound({
    container: "no padding at all", text: "", weight: "hard",
  }), "zero padding utilities must be caught");
  /* And it must NOT fire on the correct composition, which happens to be
   * textually identical to KT.card. The first version of the guard checked
   * `container.includes(KT.card)` and failed exactly here — a redundant check
   * whose only effect was a false positive on the one style that was right. */
  assert.equal(cardStyleIsSound({
    container: `${KT.panel} p-5`, text: "", weight: "irreversible",
  }), null, "KT.panel + one padding utility is the correct composition");
});

test("the scale is monotone: harder to undo renders larger", () => {
  /* The claim the whole module makes. If it ever inverted, the page would be
   * putting the biggest type on the cheapest decision while the docstring
   * said the opposite — and nobody reads a docstring to check a font size. */
  const px = (r: string) =>
    Number(/text-\[(\d+)px\]/.exec(cardStyle(r).text)![1]);
  const pad = (r: string) => Number(/p-(\d+)/.exec(cardStyle(r).container)![1]);

  assert.ok(px("irreversible") > px("hard"),
    "a fill cannot be un-filled; it must be the largest thing on the page");
  assert.ok(px("hard") > px("reversible"),
    "a change to what the machine does without asking again outranks a "
    + "revertible commit");
  assert.ok(pad("irreversible") > pad("hard"));
  assert.ok(pad("hard") > pad("reversible"));
});

test("an unclassified kind renders with the URGENT half, as it SORTS", () => {
  /* `REVERSIBILITY_RANK` puts `unclassified` between `hard` and `reversible`
   * and the ranking comment calls that "the fail-closed direction". A type
   * scale that disagreed with the sort order would be a second opinion about
   * importance, rendered in a different language from the first. */
  assert.deepEqual(cardStyle("unclassified"), cardStyle("hard"));
});

test("an unknown reversibility renders as the SMALLEST, and that is deliberate", () => {
  /* Note the asymmetry with the ranking, which fails an unknown kind CLOSED
   * (it sorts with the urgent half). Here an unrecognised *reversibility*
   * string can only come from a client bug, not from the data — `DeskItem`'s
   * type has four members and `reversibilityOf` returns one of them. Rendering
   * a bug as the largest thing on the page would put visual weight on noise. */
  assert.deepEqual(cardStyle("something-nobody-defined"),
                   cardStyle("reversible"));
});

test("the page uses the tested scale and does not roll its own", () => {
  /* LANDMARK RETARGETED (D31), PROPERTY UNCHANGED. The scoped region used to
   * end at the "2 · EVERYTHING ELSE" heading; the desk is lanes now and that
   * heading is gone. The bug this guards against is unchanged and so is the
   * region it guards: everything above the reading section, which is where
   * the decision cards live.
   *
   * THE LANDMARK IS ASSERTED TO EXIST FIRST, and that is the whole repair.
   * `indexOf` on a missing string returns −1, `slice(0, −1)` is the WHOLE
   * FILE, and the test then failed on a pre-existing `p-3` two hundred lines
   * below the region it meant to check. A test whose scope silently becomes
   * "everything" when a landmark is renamed is a test that reports the wrong
   * defect at the worst moment. */
  const src = readFileSync(new URL("./ceo/page.tsx", import.meta.url), "utf8");
  assert.ok(src.includes("cardStyle(item.reversibility)"),
    "the decision cards must take their size from the tested table");
  const end = src.indexOf("READING — NOT A QUEUE");
  assert.ok(end > 0,
    "the reading section's landmark must exist — without it this test's "
    + "scope silently widens to the whole file");
  assert.ok(!/\$\{KT\.card\}\s+p-\d/.test(src.slice(0, end)),
    "a `${KT.card} p-N` on the decision list is the invisible-class trap: "
    + "KT.card already carries p-5 and Tailwind resolves by stylesheet order, "
    + "so the padding written here would not be the padding rendered");
});
