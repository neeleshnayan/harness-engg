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
        <span className={`${KT.barTrack} w-16 shrink-0`}>
          <span className={KT.barFill}
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
export function CardFigure({ geo, showGlyph = true }: {
  geo: CardGeometry;
  /** The chair's ticket board already renders a type column; a glyph beside
   *  it would say the same thing twice. */
  showGlyph?: boolean;
}) {
  return (
    <span className="flex shrink-0 items-center gap-2.5">
      {showGlyph && (
        <span className={geo.glyph.basis === "matched"
          ? "text-[var(--kt-text-dim)]" : KT.muted}
              data-glyph={geo.glyph.family}>
          <KindGlyph family={geo.glyph.family} size={16}
                     title={`${geo.glyph.label} — ${geo.glyph.why}`} />
        </span>
      )}
      <MoneyFigure geo={geo} />
    </span>
  );
}

export { Spine as CardSpine };
