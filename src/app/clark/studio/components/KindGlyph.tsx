"use client";

import React from "react";
import type { GlyphFamily } from "../desk/cardGeometry";

/**
 * The seven kind glyphs — inline stroke SVG, on a 24-unit grid.
 *
 * ANTI-SLOP, and each clause is a rule this studio already carries:
 *
 *   * **No emoji as icons.** An emoji is a font the reader's OS chooses, at a
 *     weight nobody picked, in a palette that ignores the theme. Every mark
 *     here is a path.
 *   * **`currentColor`, always.** The glyph inherits the tone of whatever it
 *     sits in, so it cannot become an eighth colour on a page whose whole
 *     argument is that hierarchy comes from type and space.
 *   * **Stroke, never fill.** A filled shape at 14px is a blob; a 1.5-weight
 *     stroke reads at the size a card actually uses it. `strokeWidth` is in
 *     grid units and scales with `size`, so a 16px and a 24px glyph have the
 *     same visual weight rather than the same pixel weight.
 *   * **No gradient, no rounded-corner accent, no drop shadow.**
 *
 * WHY SEVEN AND NOT TWENTY-THREE. `kind` is free text — 23 distinct values
 * over 39 live rows — so a glyph per kind is a glyph nobody learns. Seven
 * FAMILIES are learnable in one sitting, which is the entire point of a
 * pre-verbal encoding: a mark the reader must decode is slower than the word
 * it replaced.
 *
 * `unclassified` HAS ITS OWN MARK and it is deliberately the plainest one. A
 * fallthrough wearing another family's shape would be a confident wrong
 * answer, which on this desk is worse than an honest blank.
 */

/** The 24-unit path for each family. One `d` each — a glyph that needs three
 *  paths at 14px is a glyph that will not read at 14px. */
const PATHS: Readonly<Record<GlyphFamily, string>> = {
  // A fork in the road: one line in, two out. What a decision IS.
  decision: "M12 21V13 M12 13L5 6 M12 13L19 6",
  // A limit line with a marker sitting under it — a threshold and where we are
  // against it.
  threshold: "M3 9h18 M8 15h8 M12 15v4",
  // A break in a line. Not a warning triangle: the triangle is spoken for by
  // the studio's alarm banners and reusing it would make every defect row look
  // like a fired alarm.
  defect: "M3 12h5 M10 12l2-4 2 8 2-4h5",
  // An aperture over a field — looking at something, not "search".
  research: "M4 18V7l8-3 8 3v11 M4 12h16 M12 9v9",
  // Stacked holdings, which is what a book is.
  position: "M4 19h16 M6 19V9 M11 19V5 M16 19v-7",
  // An arrow turning back on itself: a challenge points AT the thing it came
  // from.
  challenge: "M20 11a8 8 0 1 0-2.3 5.7 M20 5v6h-6",
  // A square outline with nothing in it. The mark for "we do not know", and
  // the only glyph here that is deliberately empty.
  unclassified: "M5 5h14v14H5z",
};

export interface KindGlyphProps {
  family: GlyphFamily;
  /** 16, 20 or 24 — the studio's icon grid. Anything else is allowed and
   *  nothing enforces it, because a hard refusal on a size is chrome that
   *  costs a render. */
  size?: number;
  /** The `why` from `cardGlyph`. Rendered as a `<title>`, which is what makes
   *  the mark answerable rather than decorative — the illumination principle
   *  binds a shape as hard as it binds a number. */
  title?: string;
  className?: string;
}

export function KindGlyph({ family, size = 16, title, className }: KindGlyphProps) {
  return (
    <svg
      width={size} height={size} viewBox="0 0 24 24"
      fill="none" stroke="currentColor"
      strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round"
      className={className}
      /* `img` + a title, not `aria-hidden`: the family is information a
         screen reader needs, because it is information a sighted reader gets
         from the shape. */
      role="img"
      aria-label={title ?? family}
    >
      {title ? <title>{title}</title> : null}
      <path d={PATHS[family] ?? PATHS.unclassified} />
    </svg>
  );
}

/** Exported for the test that asserts every family has a path and every path
 *  is a single `d` string on the 24-grid. */
export const GLYPH_PATHS = PATHS;
