"use client";

import React from "react";
import { KT } from "../theme";
import { type BookStrip, bookHeadline } from "./bookStrip";
import { type Spark, SPARK_H, SPARK_W, sparkChange } from "./sparkline";

/**
 * The header's three pictures: the strip, the line, and the big figure.
 *
 * All three take a COMPUTED object and render it. No fetching, no arithmetic,
 * no absence handling — `bookStrip` and `sparkline` own every one of those,
 * and a component that re-derived any of it would be a second opinion nothing
 * could test.
 *
 * NO CHART LIBRARY ON THIS PAGE. Both graphics are inline SVG or plain divs.
 * The CEO desk is the page he opens first and its header should cost what a
 * header costs.
 */

/* ------------------------------------------------------- the book strip --- */

/**
 * Each holding's WIDTH is its share of NAV. Cash is a visible void.
 *
 * WHAT A READER LEARNS BEFORE READING A WORD: how many things the fund holds,
 * whether one of them dominates, and how much of the fund is sitting in cash
 * doing nothing. Three facts that previously required opening a different
 * page and reading a table.
 *
 * THE VOID IS THE DESIGN. A strip of positions alone always fills its track,
 * so a fund 71% in cash and a fund 0% in cash draw the same picture. Cash is
 * rendered as an unfilled, bordered region — present, measured, and visibly
 * not working.
 */
export function BookStripView({ strip, height = 10 }: {
  strip: BookStrip;
  height?: number;
}) {
  if (strip.state === "unreadable") {
    return (
      <p className={`text-xs ${KT.sev.warn}`} data-book="unreadable">
        {strip.note}
      </p>
    );
  }
  return (
    <div className="min-w-0">
      <div
        className="flex w-full overflow-hidden rounded-full border border-[var(--kt-border)]"
        style={{ height }}
        data-book={strip.state}
        data-segments={strip.segments.length}
      >
        {strip.segments.map((s, i) => (
          <div
            key={s.symbol ?? "cash"}
            title={s.label}
            data-symbol={s.symbol ?? "cash"}
            data-weight={s.weight.toFixed(4)}
            className={s.kind === "cash"
              /* The void: the page's own inset colour, so it reads as a hole
                 in the strip rather than as a grey holding. A left border
                 separates it from the last position without spending a
                 second colour. */
              ? "h-full border-l border-[var(--kt-border)] bg-[var(--kt-inset)]"
              /* Positions alternate between two neutral steps rather than
                 taking the categorical ramp: seven hues across a $2,000 book
                 is a pie chart's worth of colour on a surface whose argument
                 is that hierarchy comes from type and space. Width IS the
                 encoding; colour only separates neighbours. */
              : i % 2 === 0
                ? "h-full bg-[var(--kt-text-dim)]"
                : "h-full bg-[var(--kt-text-muted)]"}
            style={{ width: `${(s.weight * 100).toFixed(3)}%` }}
          />
        ))}
      </div>
      {/* THE INLINE CAPTION, not a hover-only legend. A picture whose labels
          live behind a mouse is unreadable on the first pass and invisible on
          a touch screen. Four names and the void; the rest ride the titles. */}
      <p className={`mt-1.5 font-mono text-[10px] ${KT.muted}`}>
        {strip.segments
          .filter((s) => s.kind === "position")
          .slice(0, 4)
          .map((s) => (
            <span key={s.symbol} className="mr-3 tabular-nums">
              {s.symbol} {(s.weight * 100).toFixed(0)}%
            </span>
          ))}
        {strip.positionCount > 4 && (
          <span className="mr-3 tabular-nums">
            +{strip.positionCount - 4} more
          </span>
        )}
        {strip.cashWeight == null ? (
          <span className={KT.sev.warn}>cash figure unreadable</span>
        ) : (
          <span className="tabular-nums">
            cash {(strip.cashWeight * 100).toFixed(0)}%
          </span>
        )}
      </p>
    </div>
  );
}

/** The one-sentence read, for a caller that wants words under the picture. */
export function BookHeadline({ strip }: { strip: BookStrip }) {
  return (
    <p className={`text-xs leading-relaxed ${KT.muted}`}>{bookHeadline(strip)}</p>
  );
}

/* --------------------------------------------------------- the sparkline -- */

/**
 * The struck NAV series, as a line. No axes, no grid, no tooltip.
 *
 * WHAT A READER LEARNS BEFORE READING A WORD: which way the fund has gone,
 * and whether the newest mark is at the top of its range or the bottom.
 *
 * The last point carries a dot because the eye needs to know which end is
 * now — a line with two identical ends is a shape, not a time series.
 */
export function NavSparkline({ spark, width = 132, height = 32 }: {
  spark: Spark;
  width?: number;
  height?: number;
}) {
  if (spark.state !== "line") {
    /* THE THREE NON-LINE STATES ARE WORDS, and the tone is the difference:
       an unreadable history is a control being down and takes the warn tone;
       "too few strikes" and "flat" are facts about a young or quiet fund and
       are muted. Absence renders as a sentence, never as an empty box. */
    return (
      <p className={`max-w-[26rem] text-[11px] leading-relaxed ${
        spark.state === "unreadable" ? KT.sev.warn : KT.muted}`}
         data-spark={spark.state}>
        {spark.note}
      </p>
    );
  }
  const change = sparkChange(spark);
  return (
    <span className="inline-flex items-center gap-2" data-spark="line">
      <svg
        width={width} height={height}
        viewBox={`0 0 ${SPARK_W} ${SPARK_H}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={spark.note}
        /* `overflow-visible` so the emphasis dot at the right pad is not
           clipped by the viewBox edge — the dot's radius is in viewBox units
           and the path's own padding only accounts for the stroke. */
        className="overflow-visible"
      >
        <title>{spark.note}</title>
        <path
          d={spark.path!}
          fill="none"
          /* The `stroke` ATTRIBUTE, not a Tailwind class. Tailwind cannot
             apply an arbitrary CSS variable through `stroke-[var(--x)]` with
             any modifier, and an SVG that silently falls back to black is
             invisible on a black panel — measured, KP9. */
          stroke="var(--kt-text-dim)"
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
        <circle
          cx={spark.last!.x} cy={spark.last!.y} r={2}
          fill="var(--kt-text-strong)"
        />
      </svg>
      {change != null && (
        <span className={`font-mono text-[11px] tabular-nums ${
          change > 0 ? KT.up : change < 0 ? KT.down : KT.muted}`}>
          {change > 0 ? "+" : ""}{(change * 100).toFixed(2)}%
        </span>
      )}
    </span>
  );
}

/* -------------------------------------------------------- the big number -- */

/**
 * A figure at the size its importance earns, with its label above it.
 *
 * THE DEFECT THIS REPLACES: `label: value` text rows. A colon-separated row
 * gives the label and the number the same weight, in the same font, on the
 * same line — so a $2,003 NAV and the word "NAV" compete, and the eye reads
 * left to right instead of straight to the figure. The studio's own tokens
 * have said otherwise since the first page: a 10px mono uppercase label sits
 * ABOVE its figure, and the figure carries the size.
 *
 * `tabular-nums` on every figure, without exception — two numbers stacked in
 * proportional digits do not align, and a column that does not align is a
 * column nobody compares.
 */
export function StatFigure({ label, value, sub, tone = "measured", title }: {
  label: string;
  /** Already formatted. This component never formats — a component that
   *  formatted would be a second opinion about what a dash means. */
  value: string;
  sub?: string | null;
  /** `measured` is the fund's own fold; `asserted` is a step back (the
   *  studio's provenance register); `absent` is muted, for a figure nobody
   *  could read. */
  tone?: "measured" | "asserted" | "absent";
  title?: string;
}) {
  const face = tone === "measured"
    ? "text-[var(--kt-text-strong)]"
    : tone === "asserted" ? "text-[var(--kt-text-dim)]"
    : "text-[var(--kt-text-muted)]";
  return (
    <div className="min-w-0" title={title}>
      <p className={KT.label}>{label}</p>
      <p className={`mt-1 font-mono text-2xl font-light tabular-nums ${face}`}>
        {value}
      </p>
      {sub && (
        <p className={`mt-0.5 font-mono text-[10px] tabular-nums ${KT.muted}`}>
          {sub}
        </p>
      )}
    </div>
  );
}
