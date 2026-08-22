/**
 * How big a decision card renders — from how hard the decision is to take back.
 *
 * HIERARCHY FROM TYPE AND SPACE, NEVER COLOUR. That is the studio's design rule
 * and this is the place the CEO's desk obeys it. The defect it fixes, in his
 * words about the old page: every row rendered "at the same 13px in the same
 * tone", so a $750 armed short and a doc-indexing chore were visually
 * identical — and the page reached for the WARN colour to separate them, which
 * is hierarchy from colour, and puts an alarm tone on rows where nothing is
 * wrong. Size and air do the same work and say the right thing: the biggest
 * type on the page is the thing you cannot get back.
 *
 * THE TRAP THIS MODULE EXISTS TO CLOSE, and it caught me on the first render.
 *
 * `KT.card` already contains `p-5`. Writing `${KT.card} p-3` looks like it
 * overrides the padding and DOES NOT: Tailwind utilities of equal specificity
 * are resolved by their order in the generated stylesheet, not by their order
 * in the class attribute, and `p-5` is emitted after `p-3` and `p-4`. So the
 * whole space half of the scale silently did nothing — measured at the browser
 * as `padding: 20px` on all three cards, while the source said 12, 16 and 16.
 * A class that quietly does nothing is a false belief about our own code, and
 * this codebase has `${KT.card} p-3` written in several other places.
 *
 * So the container class is built HERE, from `KT.panel` (documented "add your
 * own padding"), and `cardStyleIsSound()` below is asserted by a test: exactly
 * one padding utility, and never the pre-padded card.
 */

// `.ts` on a value import, matching `deskTelemetry.ts`: the type-stripping
// test runner opens the file named, and this module must be testable — the
// defect it closes is one only a test can see.
import { KT } from "../theme.ts";

export type CardWeight = "irreversible" | "hard" | "reversible";

export interface CardStyle {
  /** The full container class. Contains exactly one `p-*`. */
  container: string;
  /** The headline's type. */
  text: string;
  weight: CardWeight;
}

/**
 * Three steps, not four. `unclassified` sits with `hard` because that is where
 * the RANKING puts it (the fail-closed direction — an unrecognised kind ranks
 * with the urgent half), and a type scale that disagreed with the sort order
 * would be a second opinion about importance rendered in a different language.
 */
export function cardStyle(reversibility: string): CardStyle {
  if (reversibility === "irreversible") {
    return {
      container: `${KT.panel} p-5`,
      text: "text-[16px] leading-relaxed",
      weight: "irreversible",
    };
  }
  if (reversibility === "hard" || reversibility === "unclassified") {
    return {
      container: `${KT.panel} p-4`,
      text: "text-[14px] leading-relaxed",
      weight: "hard",
    };
  }
  return {
    container: `${KT.panel} p-3`,
    text: "text-[13px] leading-snug",
    weight: "reversible",
  };
}

/**
 * Is the scale actually capable of taking effect? Asserted by a test.
 *
 * Returns the reason it is not, or null when it is sound. A boolean would make
 * the failure message useless, and this check exists precisely because the
 * failure it guards is invisible on screen until you measure a computed style.
 */
export function cardStyleIsSound(s: CardStyle): string | null {
  const padding = s.container.match(/(?:^|\s)p-\d+(?=\s|$)/g) ?? [];
  if (padding.length !== 1) {
    return `container has ${padding.length} padding utilities `
      + `(${padding.join(",") || "none"}); Tailwind resolves equal-specificity `
      + "utilities by stylesheet order, so more than one means the rendered "
      + "padding is whichever Tailwind emitted last — not whichever was "
      + "written last. Build on KT.panel, which carries none.";
  }
  /* Deliberately NOT also checking "is this built on KT.card". The first
   * draft did, and it was WRONG: `KT.panel + " p-5"` is textually identical to
   * `KT.card`, so the check failed the one correct style in the table. The
   * count above already subsumes it — `${KT.card} p-4` is two padding
   * utilities and is caught — and a redundant check that produces false
   * positives is worse than no check, because the fix for it is to weaken
   * something. */
  return null;
}
