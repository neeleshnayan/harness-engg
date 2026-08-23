"use client";

import React from "react";
import { FaceSpec, faceFor } from "./faces";

/**
 * `<SeatFace>` — one inline SVG portrait, drawn from the registry in faces.ts.
 *
 * No image assets, no external hosts, no emoji: the face is geometry in this
 * file, so it renders with the spine down, in both themes, at any size, and
 * cannot drift between surfaces. It is a pure function of the spec, which is a
 * pure function of the actor id — which is what makes "the pm's face is the pm's
 * face everywhere" true by construction rather than by discipline.
 *
 * Colour: every path strokes `currentColor` and nothing fills. The face takes
 * the colour of the type it sits beside, so it can never introduce a hue and
 * never needs a theme branch (theme.ts: components never branch on theme).
 *
 * Stroke: a 1.25px HAIRLINE at every size, via non-scaling-stroke. A face that
 * thickens as it grows reads as a logo; a constant hairline reads as a drawing.
 */

const VB = 40;

export function SeatFace({
  actor,
  size = 28,
  decorative = false,
  className = "",
}: {
  /** The actor id exactly as the log records it — "pm", "ceo", "auto-policy-v1". */
  actor: string | null | undefined;
  size?: number;
  /** True when the name is already rendered beside the face; the SVG is then
   *  hidden from assistive tech instead of repeating it. */
  decorative?: boolean;
  className?: string;
}) {
  const f = faceFor(actor);
  const name = f
    ? `${f.label} — ${f.role}`
    : `no face on file for "${actor ?? "unnamed"}"`;

  return (
    <svg
      viewBox={`0 0 ${VB} ${VB}`}
      width={size}
      height={size}
      className={`shrink-0 ${className}`}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.25}
      strokeLinecap="round"
      strokeLinejoin="round"
      vectorEffect="non-scaling-stroke"
      {...(decorative
        ? { "aria-hidden": true as const }
        : { role: "img" as const, "aria-label": name })}
    >
      {!decorative && <title>{name}</title>}
      {f ? <Portrait f={f} /> : <Faceless />}
    </svg>
  );
}

/* `SeatBadge` was DELETED here (D31, cleanup ticket dce47670). Its docstring
   claimed it was "the way the office writes it everywhere"; measured, it had
   no caller anywhere in the repo and every surface composes the face and the
   name inline. A helper nobody uses whose comment says everybody does is worse
   than no helper. */

/* ------------------------------------------------------------------ parts -- */

function Portrait({ f }: { f: FaceSpec }) {
  return (
    <g vectorEffect="non-scaling-stroke">
      <Head f={f} />
      <Eyes f={f} />
      <Mouth f={f} />
      <Feature f={f} />
      <Shoulders />
    </g>
  );
}

/** The stated absence. A dashed, featureless head: something acted, and the
 *  office does not know who. Deliberately NOT a generated portrait — see the
 *  header note in faces.ts. */
function Faceless() {
  return (
    <g vectorEffect="non-scaling-stroke" strokeDasharray="2 2.6" opacity={0.75}>
      <circle cx={20} cy={18.5} r={9.5} />
      <path d="M7.5 37.5 a12.5 12.5 0 0 1 25 0" />
    </g>
  );
}

function Head({ f }: { f: FaceSpec }) {
  if (f.head === "square") {
    return <rect x={10.5} y={9} width={19} height={19.5} rx={5.5} />;
  }
  if (f.head === "oval") {
    return <ellipse cx={20} cy={18.6} rx={8.6} ry={10} />;
  }
  return <circle cx={20} cy={18.5} r={9.5} />;
}

/** A soft shoulder line under every portrait. Without it a head alone reads as
 *  a token; with it, it reads as a person at a desk. */
function Shoulders() {
  return <path d="M7.5 37.6 a12.5 12.5 0 0 1 25 0" />;
}

function Eyes({ f }: { f: FaceSpec }) {
  const y = 17.6;
  if (f.eyes === "lines") {
    return (
      <>
        <path d={`M14.6 ${y} h2.6`} />
        <path d={`M22.8 ${y} h2.6`} />
      </>
    );
  }
  const r = f.eyes === "wide" ? 1.7 : 1.05;
  return (
    <>
      <circle cx={16.1} cy={y} r={r} />
      <circle cx={23.9} cy={y} r={r} />
    </>
  );
}

function Mouth({ f }: { f: FaceSpec }) {
  if (f.mouth === "smile") return <path d="M16.5 23.2 q3.5 2.8 7 0" />;
  if (f.mouth === "flat") return <path d="M16.8 23.9 h6.4" />;
  return <path d="M18.4 23.9 h3.2" />;
}

/**
 * The distinguishing mark.
 *
 * Head-worn marks (glasses, antenna, headset, tie) sit on the portrait; held
 * marks live in one fixed slot — the upper-right, clear of the head — so the
 * eye learns where to look once and every face reads the same way.
 */
function Feature({ f }: { f: FaceSpec }) {
  switch (f.feature) {
    case "glasses":
      return (
        <>
          <circle cx={16.1} cy={17.6} r={3.2} />
          <circle cx={23.9} cy={17.6} r={3.2} />
          <path d="M19.3 17.6 h1.4" />
        </>
      );
    case "antenna":
      return (
        <>
          <path d="M20 9 v-3.4" />
          <circle cx={20} cy={4.4} r={1.3} />
        </>
      );
    case "headset":
      return (
        <>
          <path d="M11 18.4 v-2.2 a9 9 0 0 1 18 0 v2.2" />
          <rect x={8.9} y={17.4} width={3} height={4.4} rx={1.3} />
          <rect x={28.1} y={17.4} width={3} height={4.4} rx={1.3} />
        </>
      );
    case "tie":
      return (
        <>
          <path d="M16.4 29.4 L20 32.6 l3.6 -3.2" />
          <path d="M20 32.6 l-1.5 1.5 1.5 4.6 1.5 -4.6 z" />
        </>
      );
    case "pen":
      return (
        <>
          <path d="M30 17.2 L36.3 8.4" />
          <path d="M34.6 6.6 l2.9 2.1 -1.2 1.7 -2.9 -2.1 z" />
          <path d="M30 17.2 l2.1 0.4 -0.6 -2.1 z" />
        </>
      );
    case "magnifier":
      return (
        <>
          <circle cx={33.4} cy={10.2} r={3.7} />
          <path d="M30.7 12.9 L28 16.1" />
        </>
      );
    case "curve":
      return <path d="M28.6 15.8 L31.5 11.2 L33.8 13.6 L37.6 7.4" />;
    case "book":
      return (
        <>
          <path d="M33 9.2 c-1.4 -1.2 -3 -1.6 -4.7 -1.3 v7.4 c1.7 -0.3 3.3 0.1 4.7 1.3 c1.4 -1.2 3 -1.6 4.7 -1.3 v-7.4 c-1.7 -0.3 -3.3 0.1 -4.7 1.3 z" />
          <path d="M33 9.2 v7.4" />
        </>
      );
    case "shield":
      return <path d="M33.2 5.8 l4.4 1.7 v4.3 c0 2.9 -2.3 4.8 -4.4 5.6 c-2.1 -0.8 -4.4 -2.7 -4.4 -5.6 v-4.3 z" />;
    case "hammer":
      return (
        <>
          <path d="M29.3 16.9 L33.9 11.6" />
          <path d="M32.2 9.1 l4.9 4.3 -1.9 2.1 -4.9 -4.3 z" />
        </>
      );
    case "gear":
      return (
        <>
          <circle cx={33.2} cy={11.4} r={3.1} />
          <path d="M33.2 5.9 v1.6 M33.2 15.3 v1.6 M27.7 11.4 h1.6 M37.1 11.4 h1.6" />
        </>
      );
    case "spark":
      return (
        <path d="M33.2 6 v3.2 M33.2 13.6 v3.2 M28.8 11.4 h3.2 M34.4 11.4 h3.2 M30.1 8.3 l2.2 2.2 M34.1 12.3 l2.2 2.2 M36.3 8.3 l-2.2 2.2 M32.3 12.3 l-2.2 2.2" />
      );
    case "bolt":
      return <path d="M34.8 5.6 l-5 6.9 h3.4 l-1.4 5.5 5 -7.2 h-3.4 z" />;
    case "none":
    default:
      return null;
  }
}
