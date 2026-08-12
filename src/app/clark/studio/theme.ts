/**
 * Krypton Studio design tokens — THE single source of truth for Studio styling.
 *
 * Distilled from the "Krypton Fund — Your Position" artifact:
 *   emerald-on-near-black · big light white numerals · small uppercase mono
 *   labels · thin-bordered rounded cards · generous whitespace · calm & minimal.
 *
 * RULE: every Studio page/component styles itself ONLY from these constants.
 * Do NOT hardcode colors. Delete the Terracotta Orange (#D97757 / orange-*) and
 * the dark-glassmorphism variants; both adopt this system. No per-page palettes,
 * no per-page theme switchers. This is a dark-only system (the artifact is dark).
 */

export const KT = {
  // --- surfaces ---
  page: "bg-[#0A0A0B] text-zinc-100 min-h-screen",
  panel: "rounded-2xl border border-zinc-800/70 bg-[#111113]",   // add your own padding
  card: "rounded-2xl border border-zinc-800/70 bg-[#111113] p-5",
  cardHover: "transition-colors hover:border-zinc-700/70",
  inset: "rounded-xl border border-zinc-800/60 bg-[#0D0D0F]",
  border: "border-zinc-800/70",

  // --- typography ---
  // small caps mono label, e.g. "YOUR VALUE OVER TIME", "WHAT THE FUND HOLDS"
  label: "font-mono text-[10px] uppercase tracking-[0.18em] text-zinc-500",
  hero: "font-mono tabular-nums text-4xl font-light tracking-tight text-white", // the big $ figure
  numberLg: "font-mono tabular-nums text-2xl font-light text-white",
  number: "font-mono tabular-nums text-sm text-zinc-200",
  title: "text-sm font-semibold text-zinc-100",
  body: "text-sm text-zinc-300",
  muted: "text-zinc-500",

  // --- accent (emerald/mint — the ONLY brand color) ---
  accent: "text-emerald-400",
  accentSoft: "text-emerald-300",
  chip: "rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-300",
  up: "text-emerald-400",
  down: "text-rose-400",
  dot: "h-1.5 w-1.5 rounded-full bg-emerald-400",

  // --- holdings / allocation bars ---
  barTrack: "h-1.5 rounded-full bg-zinc-800/70 overflow-hidden",
  barFill: "h-full rounded-full bg-emerald-400/80",

  // --- controls ---
  btn: "rounded-lg border border-emerald-500/25 bg-emerald-500/15 px-3 py-1.5 text-sm text-emerald-300 transition-colors hover:bg-emerald-500/25",
  btnGhost: "rounded-lg border border-zinc-800 px-3 py-1.5 text-sm text-zinc-300 transition-colors hover:bg-zinc-900",
  btnDanger: "rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-1.5 text-sm text-rose-300 transition-colors hover:bg-rose-500/20",
  input: "rounded-lg border border-zinc-800 bg-[#0D0D0F] px-3 py-2 text-sm text-zinc-100 outline-none placeholder:text-zinc-600 focus:border-emerald-500/50",

  // --- status (alarms/severity) ---
  sev: {
    info: "text-zinc-400",
    warn: "text-amber-400",
    critical: "text-rose-400",
  },

  // --- layout ---
  container: "mx-auto max-w-[1200px] px-6 py-6",
  containerNarrow: "mx-auto max-w-[880px] px-6 py-6", // LP-style single column
  gap: "gap-4",
} as const;

/** Set `body` to the page ground so the app never shows a lighter seam. */
export const KT_BODY_BG = "#0A0A0B";
