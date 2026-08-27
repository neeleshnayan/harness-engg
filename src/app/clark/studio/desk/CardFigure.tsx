"use client";

import React from "react";
import { KT } from "../theme";
import { KindGlyph } from "../components/KindGlyph";
import type { CardGeometry } from "./cardGeometry";

/**
 * The card's picture, rendered. Three pieces, no prose.
 *
 * `cardGeometry` decides WHAT is true; this file decides only how it is drawn,
 * and it takes no facts of its own. That split is the reason the encodings
 * cannot drift: a component that read `item.due_date` to colour a spine would
 * be a second implementation of "is it late", and this desk has been repaired
 * from a duplicated derivation twice.
 *
 * EVERY COLOUR IS A TOKEN. No hex appears in this file. The spine's three
 * tones are `--kt-warn` (the one condition that spends colour), `--kt-agent`
 * (dated, the machine's own tracking), and `--kt-border-strong` (everything
 * else) — which is the studio's stated palette used for exactly what it says:
 * emerald is the fund, violet is the machine, warn is a genuine warning.
 */

/* ------------------------------------------------------------- the spine -- */

/** Tailwind cannot take an opacity modifier on an arbitrary CSS variable —
 *  `bg-[var(--x)]/40` is dropped entirely and the element falls back to
 *  transparent (measured, KP9, where an SVG fell back to BLACK). So the two
 *  spine layers are two full-opacity colours, never one colour at two alphas. */
const SPINE_TONE: Readonly<Record<string, { track: string; fill: string }>> = {
  blocker: { track: "bg-[var(--kt-border)]", fill: "bg-[var(--kt-warn)]" },
  dated: { track: "bg-[var(--kt-border)]", fill: "bg-[var(--kt-agent)]" },
  quiet: { track: "bg-[var(--kt-border)]", fill: "bg-[var(--kt-border-strong)]" },
};

/**
 * The left spine — TONE is priority, FILL is age.
 *
 * Two encodings on one element, and they are separable by construction: the
 * tone is the whole rule's colour and the fill is a fraction of its height
 * measured from the top. A reader learns "is this on fire" from the hue and
 * "how long has it sat" from how far down the darker part runs, without
 * either question interfering with the other.
 *
 * AN UNKNOWN AGE DRAWS NO FILL AT ALL — not a zero-height one. They would be
 * the same pixels, and "we do not know how old this is" is a finding.
 */
function Spine({ geo }: { geo: CardGeometry }) {
  const tone = SPINE_TONE[geo.band.tone] ?? SPINE_TONE.quiet;
  return (
    <div
      className={`relative w-[3px] shrink-0 self-stretch overflow-hidden rounded-full ${tone.track}`}
      title={`${geo.band.label} · ${geo.band.why}\n${geo.age.why}`}
      data-band={geo.band.tone}
      data-age-step={geo.age.step}
    >
      {geo.age.known && (
        <div className={`absolute inset-x-0 top-0 rounded-full ${tone.fill}`}
             style={{ height: `${Math.round(geo.age.fill * 100)}%` }} />
      )}
      {/* A blocker with an UNKNOWN age would otherwise draw an empty track —
          the same picture as a quiet fresh row. The tone is the finding, so
          it is drawn whole rather than as a fill. */}
      {!geo.age.known && geo.band.tone === "blocker" && (
        <div className={`absolute inset-0 ${tone.fill}`} />
      )}
    </div>
  );
}

/* -------------------------------------------------------------- the money - */

/**
 * Money, four renderings, and three of them are not a bar.
 *
 * The rule this exists to keep: a zero-width rectangle and a missing
 * rectangle are the same pixels. So `zero`, `unpriced` and `unscaled` each
 * render a WORD, and only `bar` renders a rectangle.
 *
 * The figure is printed beside the bar in `tabular-nums`, because the bar
 * answers "which of these is the big one" and only the number answers "how
 * big" — a bar with no number is a shape asking to be trusted.
 */
function MoneyFigure({ geo }: { geo: CardGeometry }) {
  const m = geo.money;

  if (m.render === "bar") {
    return (
      <span className="flex min-w-0 items-center gap-1.5" title={m.why}>
        {/* `block`, and it is a BUG FIX rather than a tidy-up. `KT.barTrack`
            carries `h-1.5` and `KT.barFill` carries `h-full`; both were on
            inline `<span>`s, where a height utility does nothing. MEASURED at
            the browser: every money bar on the CEO desk came back 0x0 inside
            a 64px track — a proportional encoding drawing nothing at all,
            invisible on the screenshot and invisible to 1,266 green tests.
            The same class as the `${KT.card} p-3` trap `deskCardStyle`'s
            docstring records: a class that quietly does nothing. */}
        <span className={`${KT.barTrack} block w-10 shrink-0`}>
          <span className={`${KT.barFill} block`}
                style={{ width: `${Math.max(2, Math.round(m.fraction * 100))}%` }}
                data-money-pct={Math.round(m.fraction * 100)} />
        </span>
        <span className="font-mono text-[11px] tabular-nums text-[var(--kt-text)]">
          {m.label}
        </span>
      </span>
    );
  }
  if (m.render === "unscaled") {
    return (
      <span className="font-mono text-[11px] tabular-nums text-[var(--kt-text)]"
            title={m.why}>
        {m.label}
      </span>
    );
  }
  /* ZERO AND UNPRICED BOTH DRAW NOTHING, AND THEY DRAW DIFFERENT NOTHINGS.
     Zero is quiet — one muted word, no track, no furniture. Unpriced is a
     FINDING and says so in words, because a row nobody put a number on is a
     row whose importance nobody assessed. */
  return (
    <span className={`font-mono text-[10px] ${KT.muted}`} title={m.why}
          data-money={m.render}>
      {m.label}
    </span>
  );
}

/* ------------------------------------------------------------- the whole -- */

/**
 * The glyph + the money, as the row's right-hand figure block.
 *
 * The spine is exported separately because it must be a SIBLING of the card's
 * padding box, not a child of it: a spine inside `p-4` is a stripe floating
 * in a margin, and the whole read of a spine is that it is the card's edge.
 */
/**
 * THE WIDTH IS FIXED, AND THAT IS THE WHOLE POINT OF A COLUMN.
 *
 * MEASURED, before this was fixed: 39 cards produced SEVEN distinct
 * right-hand edges for this block, spanning 56px, because a row with a bar
 * (`▭ $630`) is wider than a row with two muted words (`not priced`). Every
 * headline on the page therefore started at a different x.
 *
 * A ragged column defeats the entire encoding. The reason the glyph and the
 * bar exist is that a reader SCANS them — and scanning is comparing things
 * that sit on top of one another. A picture the eye has to hunt for, one row
 * at a time, is slower than the word it replaced.
 *
 * 7.5rem holds the widest case (a 64px track, a gap, and `-$1.8M`) with the
 * money RIGHT-ALIGNED into the column, which is what `tabular-nums` is for:
 * digits that line up are digits a reader can compare without reading them.
 */
const FIGURE_COLUMN = "w-[7.5rem]";

export function CardFigure({ geo, showGlyph = true }: {
  geo: CardGeometry;
  /** The chair's ticket board already renders a type column; a glyph beside
   *  it would say the same thing twice. */
  showGlyph?: boolean;
}) {
  return (
    <span className={`flex shrink-0 flex-col gap-1 ${FIGURE_COLUMN}`}
          data-figure-column="">
      <span className="flex w-full items-center justify-between gap-2">
        {showGlyph ? (
          <span className={geo.glyph.basis === "matched"
            ? "text-[var(--kt-text-dim)]" : KT.muted}
                data-glyph={geo.glyph.family}>
            <KindGlyph family={geo.glyph.family} size={16}
                       title={`${geo.glyph.label} — ${geo.glyph.why}`} />
          </span>
        ) : <span />}
        <MoneyFigure geo={geo} />
      </span>
      {/* THE DATE MOVED HERE FROM AN INLINE CHIP BEFORE THE HEADLINE, and it
          is a measurement that moved it. With the chip inline, 39 cards
          produced FOUR distinct headline start positions spanning 119px —
          dated rows were indented by the width of their own chip, so the one
          thing on the card a reader is scanning did not sit in a column.

          It also says more than the chip did. `band.short` is "3d late" for
          an overdue row where the chip said "due 2026-08-24" and left the
          reader to do the arithmetic against today; the full ISO date is in
          the title and on `band.due`, so nothing was lost.

          THE WARN TONE IS SPENT ONCE, HERE AND ON THE SPINE, on the same
          rows: a dated commitment already past is the one condition on this
          desk that is true whether or not anybody clicks. */}
      {geo.band.short && (
        <span className={`text-right font-mono text-[10px] tabular-nums ${
          geo.band.tone === "blocker" ? KT.sev.warn : KT.muted}`}
              title={`${geo.band.label} · ${geo.band.why}`}
              data-due={geo.band.due ?? ""}>
          {geo.band.short}
        </span>
      )}
    </span>
  );
}

export { Spine as CardSpine };
