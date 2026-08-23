/**
 * Krypton Studio design tokens — THE single source of truth for Studio styling.
 *
 * Distilled from the "Krypton Fund — Your Position" artifact:
 *   emerald accent · big light numerals · small uppercase mono labels ·
 *   thin-bordered rounded cards · generous whitespace · calm & minimal.
 *
 * RULE: every Studio page/component styles itself ONLY from these constants, and
 * NEVER branches on the active theme. Light/dark differ in exactly one place —
 * the CSS variables in `studio-theme.css`, swapped via `data-kt-theme` on the
 * Studio root. Components stay theme-agnostic, which is what keeps the palettes
 * from drifting apart the way they did before.
 *
 * THE ILLUMINATION PRINCIPLE (CEO, 2026-08-24, verbatim: "I wont be hunting
 * down JSON and codefiles with you on the seat so the UI needs to be designed
 * in a way to illuminate beneath the surface"). The reader of these pages is
 * a human who will never open the payload. Therefore every surface answers,
 * ON the surface, the questions a reader of the raw record could answer:
 *
 *   1. WHERE FROM — every number's provenance is at most one click away
 *      (lineage, the producing run, the as-of stamp). A figure with no path
 *      back to the record is decoration.
 *   2. WHAT IS MISSING — absence, unknown, unreadable and truncation render
 *      as WORDS, never as zero, never as an empty region, never as omission.
 *      "Showing nothing rather than a clear board" is the house sentence.
 *   3. WHERE THEY DISAGREE — when two sources answer one question (the
 *      fund's count vs the page's fold; live vs last-recorded), show BOTH
 *      with the difference named. A surface that picks the prettier number
 *      teaches the reader to distrust whichever they saw elsewhere.
 *   4. HOW OLD — anything that can go stale carries its `since`/`as-of`
 *      where it is read, so a three-day-old lamp reads as three days old
 *      (the analyst's stale "working", caught by the CEO in one glance,
 *      is this clause's founding measurement).
 *   5. WHEN A CONTROL IS DOWN — a disclosure written for auditors
 *      (`supersession_readable: false`, a dead store, a tripped guard)
 *      renders where the CEO looks, in the warn tone, the moment it exists.
 *
 * Every KP brief cites this principle; the dead-spine CDP pass (all states
 * read as words, never zeros) is its standing acceptance test.
 */

export const KT = {
  // --- surfaces ---
  page: "bg-[var(--kt-bg)] text-[var(--kt-text)] min-h-screen",
  panel: "rounded-2xl border border-[var(--kt-border)] bg-[var(--kt-surface)]", // add your own padding
  card: "rounded-2xl border border-[var(--kt-border)] bg-[var(--kt-surface)] p-5",
  cardHover: "transition-colors hover:border-[var(--kt-border-strong)]",
  inset: "rounded-xl border border-[var(--kt-border)] bg-[var(--kt-inset)]",
  border: "border-[var(--kt-border)]",

  // --- typography ---
  // small caps mono label, e.g. "LIVE NAV", "WHAT THE FUND HOLDS"
  label: "font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--kt-text-muted)]",
  hero: "font-mono tabular-nums text-4xl font-light tracking-tight text-[var(--kt-text-strong)]",
  numberLg: "font-mono tabular-nums text-2xl font-light text-[var(--kt-text-strong)]",
  number: "font-mono tabular-nums text-sm text-[var(--kt-text)]",
  title: "text-sm font-semibold text-[var(--kt-text)]",
  body: "text-sm text-[var(--kt-text-dim)]",
  muted: "text-[var(--kt-text-muted)]",

  // --- accent (emerald — the ONLY brand color) ---
  accent: "text-[var(--kt-accent)]",
  accentSoft: "text-[var(--kt-accent-soft)]",
  chip: "rounded-full border border-[var(--kt-accent-border)] bg-[var(--kt-accent-bg)] px-2 py-0.5 text-[11px] text-[var(--kt-accent)]",
  up: "text-[var(--kt-up)]",
  down: "text-[var(--kt-down)]",
  dot: "h-1.5 w-1.5 rounded-full bg-[var(--kt-accent)]",

  // --- agent (violet — the SECOND accent, reserved for Clark) ---
  // Emerald is the fund. Violet is the machine. Keeping them apart is not
  // decoration: an operator scanning in seconds must never mistake a sentence
  // a model wrote for a number the fund computed.
  agent: {
    text: "text-[var(--kt-agent)]",
    soft: "text-[var(--kt-agent-soft)]",
    bg: "bg-[var(--kt-agent-bg)]",
    border: "border-[var(--kt-agent-border)]",
    chip: "rounded-full border border-[var(--kt-agent-border)] bg-[var(--kt-agent-bg)] px-2 py-0.5 text-[11px] text-[var(--kt-agent)]",
    btn: "rounded-lg border border-[var(--kt-agent-border)] bg-[var(--kt-agent-bg)] px-3 py-1.5 text-sm text-[var(--kt-agent)] transition-colors hover:border-[var(--kt-agent)]",
    // No gradient, deliberately. A wash on a panel that sits on screen all day
    // is decoration that never stops asking for attention, and the cockpit it
    // sits beside earns its hierarchy from type and whitespace alone. The rail
    // is distinguished by its border and its labels, nothing more.
    wash: "",
  },

  // --- holdings / allocation bars ---
  barTrack: "h-1.5 rounded-full bg-[var(--kt-track)] overflow-hidden",
  barFill: "h-full rounded-full bg-[var(--kt-accent)]",

  // --- controls ---
  btn: "rounded-lg border border-[var(--kt-accent-border)] bg-[var(--kt-accent-bg)] px-3 py-1.5 text-sm text-[var(--kt-accent)] transition-colors hover:border-[var(--kt-accent)]",
  btnGhost: "rounded-lg border border-[var(--kt-border)] px-3 py-1.5 text-sm text-[var(--kt-text-dim)] transition-colors hover:bg-[var(--kt-hover)]",
  btnDanger: "rounded-lg border border-[var(--kt-down)]/30 bg-[var(--kt-down)]/10 px-3 py-1.5 text-sm text-[var(--kt-down)] transition-colors hover:bg-[var(--kt-down)]/20",
  input: "rounded-lg border border-[var(--kt-border)] bg-[var(--kt-inset)] px-3 py-2 text-sm text-[var(--kt-text)] outline-none placeholder:text-[var(--kt-text-muted)] focus:border-[var(--kt-accent)]",

  // --- status (limit breaches / severity) ---
  sev: {
    info: "text-[var(--kt-text-dim)]",
    warn: "text-[var(--kt-warn)]",
    critical: "text-[var(--kt-down)]",
  },

  // --- layout ---
  container: "mx-auto max-w-[1200px] px-6 py-6",
  containerNarrow: "mx-auto max-w-[880px] px-6 py-6", // LP-style single column
  gap: "gap-4",
} as const;

export type KtTheme = "dark" | "light";

/** Studio default. Dark is the design reference. */
export const KT_DEFAULT_THEME: KtTheme = "dark";

/** Where the user's choice is remembered. */
export const KT_THEME_STORAGE_KEY = "kt-studio-theme";
