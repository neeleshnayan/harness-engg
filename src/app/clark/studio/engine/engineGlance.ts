/**
 * ENGINE, AT A GLANCE — the reading logic behind the trade-ready bar, the
 * signal timeline and the fate bar.
 *
 * WHY THIS FILE EXISTS (CEO, 2026-08-27, verbatim: *"Engine page is too much
 * text; we need analytics and graphs and meaningful and minimal UI"*).
 *
 * The page it replaces was honest and unreadable. Measured on the live
 * reading, 2026-08-27: ~2,000 rendered pixels, five stacked panels, every one
 * of them opening with a paragraph, and not one number placed on an axis. Every
 * sentence on it was true; the CEO still could not answer *"is the engine
 * alive and does anything need me"* without reading all of it.
 *
 * SO THE DEMOTION IS THE DESIGN, AND IT IS NOT A DELETION. Each paragraph the
 * old page rendered at the front is still on the page — `engineCaveats` below
 * gathers every one of them, gives it a ONE-LINE form for the surface and
 * keeps the full text one click away. Nothing is dropped, and the ones that
 * describe a CONTROL BEING DOWN (theme.ts, illumination clause 5) stay visible
 * in the warn tone rather than going behind the fold with the rest.
 *
 * THE ABSENCE RULES ARE UNCHANGED AND THIS FILE IS WHERE THEY GET HARDEST,
 * because a tile is four words wide:
 *
 *   · A tile whose figure could not be read says UNKNOWN, never 0. Every tile
 *     carries `unknown` so the renderer cannot style an absence like a fact.
 *   · "NEVER" is a MEASUREMENT and only when the read was unbounded. A ledger
 *     whose scan window BOUND has not established that nothing was raised —
 *     it has established that it did not look far enough (`glanceTiles`, the
 *     `signal` tile).
 *   · A signal with no timestamp cannot go on a time axis, and dropping it
 *     would make the timeline disagree with the count beside it. `undated`
 *     carries those rows out to the renderer instead.
 *
 * Nothing here acts, halts, or crosses a threshold. It is a reading.
 */

import {
  FATE_HELP,
  FATE_LABEL,
  FATE_ORDER,
  countTone,
  fateTone,
  fenceBlindSpots,
  fenceNote,
  impliedCaveat,
  ledgerAbsence,
  plural,
  unclassifiedNote,
  unknownsList,
  venueNote,
  engineHeadline,
  reconcileHeadline,
  type EngineView,
  type Fate,
  type SignalLedger,
  type SignalRow,
  type Tone,
} from "./engineView.ts";

// ------------------------------------------------------------------- clocks

/** A parsed instant, or null. Never NaN, never a silent 0 (which is 1970). */
export function instant(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  return Number.isNaN(t) ? null : t;
}

export interface Age {
  /** "just now" · "7m ago" · "11d ago" · "ahead of this clock". */
  text: string;
  /** Milliseconds elapsed. Negative when the stamp is ahead of `nowMs`. */
  ms: number;
}

/**
 * How long ago, in the coarsest unit that is still honest.
 *
 * `now` is a PARAMETER, not `Date.now()`, so every test of this is
 * deterministic — the measured reason is that a clock read inside a pure
 * function is a test that passes at 23:59 and fails at 00:00.
 *
 * A stamp AHEAD of the reader's clock is reported as such rather than as a
 * negative age or a cheerful "just now". Two clocks disagreeing is a fact
 * about the fund's instruments and the reader is entitled to see it.
 */
export function ageLabel(
  iso: string | null | undefined,
  nowMs: number,
): Age | null {
  const t = instant(iso);
  if (t == null) return null;
  const ms = nowMs - t;
  if (ms < -60_000) return { text: "ahead of this clock", ms };
  if (ms < 60_000) return { text: "just now", ms };
  const mins = Math.floor(ms / 60_000);
  if (mins < 60) return { text: `${mins}m ago`, ms };
  const hours = Math.floor(ms / 3_600_000);
  if (hours < 48) return { text: `${hours}h ago`, ms };
  return { text: `${Math.floor(ms / 86_400_000)}d ago`, ms };
}

// -------------------------------------------------------------- the glance

export type GlanceKey = "engine" | "spoke" | "signals" | "books" | "needs";

export interface GlanceTile {
  key: GlanceKey;
  /** The question, in the fewest words that still ask it. */
  label: string;
  /** The answer, four words at most. */
  value: string;
  tone: Tone;
  /** One line under the answer. Never empty — a blank region gets filled in
   *  optimistically, which is the whole reason this page exists. */
  sub: string;
  /** True when `value` is an absence rather than a measurement. The renderer
   *  keys the figure's weight off this, so an UNKNOWN can never be styled like
   *  a number the fund computed. */
  unknown: boolean;
}

/**
 * THE TRADE-READY BAR — five questions, one row, one function.
 *
 * ONE INPUT, ONE FUNCTION, ALL FIVE FIELDS (the ENG1 lesson, priced): when a
 * payload carries several fields describing one condition, a caller that
 * computes some of them and patches the rest ships a state that contradicts
 * itself. So the whole bar is computed here from the whole view, and the page
 * renders what it is handed.
 *
 * ALWAYS FIVE TILES, in this order, empty or not. A tile that disappears when
 * it has nothing to say makes "no signal is waiting on you" and "this reading
 * does not report what is waiting on you" the same rendering.
 */
export function glanceTiles(
  view: EngineView | null | undefined,
  nowMs: number,
): GlanceTile[] {
  const status = view?.status ?? null;
  const ledger = view?.ledger ?? null;
  const leg = view?.reconcile ?? null;

  // ---- 1. is it alive
  const head = engineHeadline(status);
  const sessions = status?.sessions ?? [];
  const running = sessions.filter((s) => s.state === "running");
  const sessionsUnreadable = status?.sessions_readable === false;
  let engineSub: string;
  if (!status) {
    engineSub = "the engine has not been read";
  } else if (sessionsUnreadable) {
    engineSub = "the session list could not be read — not the same as nothing running";
  } else if (running.length === 1) {
    const started = ageLabel(running[0].started_at, nowMs);
    engineSub = `${running[0].algorithm ?? "unnamed algorithm"}` +
      (started ? ` · started ${started.text}` : " · start time UNKNOWN");
  } else if (running.length > 1) {
    engineSub = `${plural(running.length, "session")} running`;
  } else if (sessions.length > 0) {
    engineSub = `${plural(sessions.length, "session")} on record, none running`;
  } else {
    engineSub = "no session on record since the spine last started";
  }

  // ---- 2. when did it last speak
  // "NEVER" IS A MEASUREMENT AND ONLY WHEN THE READ WAS UNBOUNDED. A window
  // that BOUND has not established that nothing was raised; it has established
  // that it did not look far enough back to say.
  const spokeAge = ageLabel(status?.last_signal_at, nowMs);
  const windowBound = ledger?.domain?.window_bound === true;
  let spokeValue: string;
  let spokeTone: Tone;
  let spokeSub: string;
  let spokeUnknown: boolean;
  if (spokeAge) {
    spokeValue = spokeAge.text;
    spokeTone = "neutral";
    spokeSub = status?.last_signal_scope ?? "the last signal any engine raised";
    spokeUnknown = false;
  } else if (!status) {
    spokeValue = "UNKNOWN";
    spokeTone = "warn";
    spokeSub = "the engine has not been read";
    spokeUnknown = true;
  } else if (windowBound) {
    spokeValue = "UNKNOWN";
    spokeTone = "warn";
    spokeSub = `the read bound at ${ledger?.domain?.scan_limit?.toLocaleString() ?? "its limit"}` +
      " events — an older signal would be unread, not absent";
    spokeUnknown = true;
  } else {
    spokeValue = "NEVER";
    spokeTone = "quiet";
    spokeSub = "no engine has raised a signal on this record";
    spokeUnknown = false;
  }

  // ---- 3. how many signals, and how many still testify about a live engine
  const total = ledger?.total ?? null;
  const fenced = ledger?.fenced ?? null;
  let signalsSub: string;
  if (total == null) {
    signalsSub = "the signal ledger could not be read";
  } else if (total === 0) {
    signalsSub = "nothing raised — which is not the same as nothing wrong";
  } else if (fenced == null) {
    signalsSub = "how many are fenced is UNKNOWN — nothing could ask what is running";
  } else if (fenced === 0) {
    signalsSub = `all ${total === 1 ? "of it" : "of them"} from a session still on record`;
  } else {
    signalsSub = `${fenced} fenced — raised by a session that no longer exists`;
  }

  // ---- 4. do the books agree
  const recon = reconcileHeadline(leg);
  const outOfSync = leg?.implied?.symbols_out_of_sync ?? null;
  const undetermined = leg?.implied?.symbols_undetermined ?? null;
  let booksSub: string;
  if (!leg) {
    booksSub = "the reconciliation leg has not been read";
  } else if (leg.implied?.book_readable === false) {
    booksSub = "the fund's own book could not be read, so nothing was compared";
  } else if ((outOfSync ?? 0) > 0) {
    booksSub = `${plural(outOfSync ?? 0, "symbol")} where the engine and the fund disagree`;
  } else if ((undetermined ?? 0) > 0) {
    booksSub = `${plural(undetermined ?? 0, "symbol")} could not be determined either way`;
  } else {
    booksSub = recon.sentence.split(".")[0] + ".";
  }

  // ---- 5. does anything need the CEO
  const awaiting = ledger?.counts?.awaiting ?? null;
  const unclassified = ledger?.counts?.unclassified ?? 0;
  let needsValue: string;
  let needsTone: Tone;
  let needsSub: string;
  let needsUnknown: boolean;
  if (!ledger) {
    needsValue = "UNKNOWN";
    needsTone = "warn";
    needsSub = "the approval queue could not be read from here";
    needsUnknown = true;
  } else if ((awaiting ?? 0) > 0) {
    needsValue = String(awaiting);
    needsTone = "warn";
    needsSub = `${(awaiting ?? 0) === 1 ? "one signal is" : "signals are"} waiting on your click`;
    needsUnknown = false;
  } else {
    needsValue = "NOTHING";
    needsTone = "quiet";
    needsSub = "no engine signal is waiting on a decision";
    needsUnknown = false;
  }
  if (unclassified > 0) {
    needsSub += ` · ${plural(unclassified, "signal")} in a state this page has no word for`;
  }

  return [
    {
      key: "engine",
      label: "Engine",
      value: head.word,
      tone: head.tone,
      sub: engineSub,
      unknown: !status || sessionsUnreadable || head.word === "UNKNOWN" || head.word === "UNREAD",
    },
    { key: "spoke", label: "Last signal", value: spokeValue, tone: spokeTone, sub: spokeSub, unknown: spokeUnknown },
    {
      key: "signals",
      label: "Signals raised",
      value: total == null ? "UNKNOWN" : String(total),
      tone: total == null ? "warn" : total === 0 ? "quiet" : "neutral",
      sub: signalsSub,
      unknown: total == null,
    },
    {
      key: "books",
      label: "Books agree",
      value: recon.word,
      tone: recon.tone,
      sub: booksSub,
      unknown: !leg || leg.implied?.book_readable === false,
    },
    { key: "needs", label: "Needs you", value: needsValue, tone: needsTone, sub: needsSub, unknown: needsUnknown },
  ];
}

// ------------------------------------------------------------ the fate bar

export interface FateSegment {
  fate: string;
  label: string;
  help: string;
  n: number;
  /** Percent of `covered`, NOT of `total` — see the note below. */
  pct: number;
  tone: Tone;
}

export interface FateBar {
  /** Only non-empty fates. The five-bucket strip beside it still shows every
   *  bucket including the zeros, so nothing vanishes by being empty here. */
  segments: FateSegment[];
  /** What the ledger says it holds. `null` when the ledger could not be read. */
  total: number | null;
  /** What the fate counts actually sum to — the bar's own domain. */
  covered: number;
  empty: boolean;
  /** Set when `covered` and `total` disagree: a row is in the total and in no
   *  bucket, or in a bucket and not in the total. Either way one signal is
   *  invisible on one of the two surfaces and that must be a sentence, not a
   *  silently renormalised bar. */
  note: string | null;
}

/**
 * The composition of every signal's fate as one bar.
 *
 * A BAR, NOT A TREND. At n=1 a sparkline would draw a flat line and imply a
 * series; a composition bar at n=1 is one full-width segment that says "one
 * signal, refused", which is exactly true. It reads at 1 and it reads at 100,
 * which is the property the design was asked for.
 */
export function fateBar(ledger: SignalLedger | null | undefined): FateBar {
  const counts = ledger?.counts ?? null;
  if (!counts) {
    return { segments: [], total: ledger?.total ?? null, covered: 0, empty: true, note: null };
  }
  let covered = 0;
  for (const v of Object.values(counts)) covered += v ?? 0;

  const known: FateSegment[] = FATE_ORDER.map((fate: Fate) => ({
    fate,
    label: FATE_LABEL[fate],
    help: FATE_HELP[fate],
    n: counts[fate] ?? 0,
    pct: covered > 0 ? ((counts[fate] ?? 0) / covered) * 100 : 0,
    tone: fateTone(fate),
  }));
  // Every bucket the spine reports that this page's vocabulary does not name.
  // Folding them into "other" and moving on is how a row vanishes; they get a
  // segment of their own, in the warn tone, and the caveat says the vocabulary
  // needs extending rather than the count.
  const extra: FateSegment[] = Object.keys(counts)
    .filter((k) => !(FATE_ORDER as string[]).includes(k))
    .filter((k) => (counts[k] ?? 0) > 0)
    .sort()
    .map((k) => ({
      fate: k,
      label: k === "unclassified" ? "No word for it" : k,
      help: "A lifecycle state this page has no word for. It is counted, and the vocabulary is what needs extending.",
      n: counts[k] ?? 0,
      pct: covered > 0 ? ((counts[k] ?? 0) / covered) * 100 : 0,
      tone: "warn" as Tone,
    }));

  const total = ledger?.total ?? null;
  const note = total != null && total !== covered
    ? `The fate counts sum to ${covered} and the ledger reports ${plural(total, "signal")} — ` +
      `${Math.abs(total - covered)} ${Math.abs(total - covered) === 1 ? "row is" : "rows are"} ` +
      `on one surface and not the other. The bar below covers ${covered}.`
    : null;

  return {
    segments: [...known, ...extra].filter((s) => s.n > 0),
    total,
    covered,
    empty: covered === 0,
    note,
  };
}

/** The five buckets, zeros included, for the compact strip beside the bar. */
export function fateStrip(ledger: SignalLedger | null | undefined): FateSegment[] {
  const counts = ledger?.counts ?? {};
  return FATE_ORDER.map((fate: Fate) => ({
    fate,
    label: FATE_LABEL[fate],
    help: FATE_HELP[fate],
    n: counts[fate] ?? 0,
    pct: 0,
    tone: countTone(fate, counts[fate] ?? 0),
  }));
}

// -------------------------------------------------------------- the timeline

export interface TimelinePoint {
  order_id: string;
  /** 0..1 across the axis, left to right. */
  x: number;
  at: string;
  fate: string;
  tone: Tone;
  /** A fenced signal describes a paper book that is gone. Drawn hollow. */
  fenced: boolean;
  /** "BUY 0.1 GLD" — never a bare id. */
  label: string;
}

export interface Timeline {
  points: TimelinePoint[];
  /** Signals the axis CANNOT place, carried out rather than dropped. */
  undated: { order_id: string; label: string; fate: string; tone: Tone; fenced: boolean }[];
  startIso: string | null;
  endIso: string | null;
  /** The right edge is the reading's own clock, so the SILENCE since the last
   *  signal is part of the picture rather than cropped out of it. */
  endIsNow: boolean;
  /** Every dated signal shares one instant: x carries no information and the
   *  renderer must say so instead of drawing a line through one point. */
  degenerate: boolean;
  absence: string | null;
  /** Truncation, as a sentence. Never a silently shorter axis. */
  note: string | null;
}

export function signalLabel(s: SignalRow): string {
  const side = (s.side ?? "").toUpperCase();
  const qty = s.qty == null ? "qty UNKNOWN" : String(s.qty);
  const sym = (s.symbol ?? "").trim().toUpperCase() || "SYMBOL UNKNOWN";
  return `${side ? side + " " : ""}${qty} ${sym}`.trim();
}

/**
 * Every signal on one time axis.
 *
 * THE RIGHT EDGE IS NOW, NOT THE LAST SIGNAL. An axis that ends at the last
 * signal always shows a point at its right edge, so an engine that spoke ten
 * days ago and an engine that spoke a minute ago draw identically. Ending at
 * the reading's own clock makes the gap the picture's largest feature, which
 * is what it is.
 *
 * A SIGNAL WITH NO TIMESTAMP IS NOT PLOTTED AND NOT DROPPED. It goes to
 * `undated`, because a timeline showing four points beside a header saying
 * five signals is a row that vanished — the defect class this whole surface
 * was built to catch.
 */
export function signalTimeline(
  ledger: SignalLedger | null | undefined,
  nowMs: number,
): Timeline {
  const empty: Timeline = {
    points: [], undated: [], startIso: null, endIso: null,
    endIsNow: false, degenerate: false, absence: null, note: null,
  };
  if (!ledger) {
    return { ...empty, absence: "The signal ledger has not been read — UNKNOWN, not empty." };
  }
  const rows = ledger.signals ?? [];
  const note = ledger.returned < ledger.total
    ? `The axis covers ${ledger.returned} of ${plural(ledger.total, "signal")}.`
    : null;

  if (rows.length === 0) {
    return { ...empty, absence: ledgerAbsence(ledger) ?? "No signal to place on an axis.", note };
  }

  const undated = rows
    .filter((s) => instant(s.raised_at) == null)
    .map((s) => ({
      order_id: s.order_id,
      label: signalLabel(s),
      fate: String(s.outcome),
      tone: fateTone(s.outcome),
      fenced: s.fenced === true,
    }));

  const dated = rows
    .map((s) => ({ s, t: instant(s.raised_at) }))
    .filter((r): r is { s: SignalRow; t: number } => r.t != null)
    .sort((a, b) => a.t - b.t);

  if (dated.length === 0) {
    return {
      ...empty,
      undated,
      note,
      absence: `${plural(rows.length, "signal")}, none carrying a timestamp — ` +
        `nothing can be placed on a time axis. They are listed below instead.`,
    };
  }

  const t0 = dated[0].t;
  const tLast = dated[dated.length - 1].t;
  const tEnd = Math.max(tLast, nowMs);
  const span = tEnd - t0;
  const degenerate = span <= 0;

  return {
    points: dated.map(({ s, t }) => ({
      order_id: s.order_id,
      // A degenerate span cannot be divided. Every point sits at the right
      // edge and `degenerate` tells the renderer to drop the axis rather than
      // draw one whose positions mean nothing.
      x: degenerate ? 1 : (t - t0) / span,
      at: s.raised_at as string,
      fate: String(s.outcome),
      tone: fateTone(s.outcome),
      fenced: s.fenced === true,
      label: signalLabel(s),
    })),
    undated,
    startIso: dated[0].s.raised_at ?? null,
    endIso: new Date(tEnd).toISOString(),
    endIsNow: tEnd === nowMs && nowMs > tLast,
    degenerate,
    absence: null,
    note,
  };
}

// ---------------------------------------------------------------- the prose

export interface Caveat {
  key: string;
  /** The one line that goes on the surface. */
  short: string;
  /** The paragraph, one click away. Equal to `short` when there is no more. */
  full: string;
  /** `warn` keeps it on the surface (illumination clause 5 — a control being
   *  down renders where the CEO looks). Everything else goes behind the fold. */
  tone: Tone;
}

/**
 * EVERY PARAGRAPH THE OLD PAGE RENDERED AT THE FRONT, GATHERED IN ONE PLACE.
 *
 * This is the demotion, and it is why the redesign is not a deletion: the
 * fence note, the model caveat, the orphan note, the venue note, the
 * unclassified note and the whole "what this page cannot tell you" list are
 * all still computed by the same functions that computed them before, still
 * carrying the same words. What changed is that the surface shows the first
 * line and the reader asks for the rest.
 *
 * THE WARN ONES DO NOT GO BEHIND THE FOLD. A blind spot in the fence removes
 * rows from a verdict the CEO reads; hiding it behind a click would be the
 * quiet half of a loosening. `tone` is the discriminator and the page keys off
 * it rather than off the list's order.
 */
export function engineCaveats(view: EngineView | null | undefined): Caveat[] {
  if (!view) return [];
  const out: Caveat[] = [];
  const leg = view.reconcile ?? null;
  const ledger = view.ledger ?? null;

  const fence = fenceNote(leg);
  if (fence) {
    out.push({
      key: "fence",
      short: firstSentence(fence),
      full: fence,
      tone: "quiet",
    });
  }

  // THE FENCE'S OWN BLIND SPOTS — read from `fenceBlindSpots`, never
  // re-worded here. A second copy of these sentences in this file is exactly
  // the "the page and its module start disagreeing" defect the engine page's
  // own tests were written to prevent, and it is the defect this seat has
  // measured most often: a fix applied to one member of a family and not its
  // sibling. One implementation, two forms — `short` is a clipped view of
  // `full`, never a rewrite.
  //
  // Each one means the fence proved LESS than it looks like it proved, so
  // each is `warn` and each stays on the surface.
  for (const [i, b] of fenceBlindSpots(leg).entries()) {
    out.push({ key: `fence-blind-${i}`, short: firstSentence(b), full: b, tone: "warn" });
  }

  const caveat = impliedCaveat(leg);
  if (caveat) {
    out.push({
      key: "implied",
      short: firstSentence(caveat),
      full: caveat,
      tone: "quiet",
    });
  }

  const model = leg?.implied?.model;
  if (model) {
    out.push({ key: "model", short: firstSentence(model), full: model, tone: "quiet" });
  }

  const venue = venueNote(ledger);
  if (venue) {
    out.push({ key: "venue", short: firstSentence(venue), full: venue, tone: "quiet" });
  }

  const unclassified = unclassifiedNote(ledger);
  if (unclassified) {
    out.push({ key: "unclassified", short: firstSentence(unclassified), full: unclassified, tone: "warn" });
  }

  for (const [i, u] of unknownsList(view).entries()) {
    out.push({ key: `unknown-${i}`, short: firstSentence(u), full: u, tone: "quiet" });
  }
  return out;
}

/**
 * The first sentence, for the one-line form.
 *
 * Clipped at the sentence boundary, NEVER at a character count: a paragraph cut
 * mid-word with an ellipsis is how a surface tells its reader that the words do
 * not matter. When the first sentence is itself long the full text is what
 * renders — a long true line beats a mangled one.
 */
export function firstSentence(text: string): string {
  const trimmed = text.trim();
  const m = /^[\s\S]*?[.!?](?=\s|$)/.exec(trimmed);
  const first = m ? m[0].trim() : trimmed;
  return first.length > 0 && first.length < trimmed.length ? first : trimmed;
}

/** The caveats that stay on the surface, in the warn tone. */
export function surfacedCaveats(view: EngineView | null | undefined): Caveat[] {
  return engineCaveats(view).filter((c) => c.tone === "warn");
}

/** The caveats that go behind the fold. */
export function foldedCaveats(view: EngineView | null | undefined): Caveat[] {
  return engineCaveats(view).filter((c) => c.tone !== "warn");
}

// ------------------------------------------------------------- the density

/**
 * The fewest points this fund will draw a distribution from.
 *
 * BORROWED, NOT INVENTED: `NavPanel.MIN_POINTS_FOR_CURVE` is 3 for the same
 * reason and has been since 2026-08-20 — *"two points is a line, not a curve"*.
 * A one-signal engine drawing a histogram would be the same lie in a new
 * costume, and the engine will spend its first weeks at n = 1.
 */
export const MIN_POINTS_FOR_DENSITY = 3;

export interface DensityBin {
  /** Left and right edge, 0..1 on the same axis the points use. */
  x0: number;
  x1: number;
  n: number;
}

export interface Density {
  bins: DensityBin[];
  /** The tallest bin, so a renderer can scale without re-folding. */
  max: number;
  /** False when there are too few points to draw an honest distribution. */
  drawn: boolean;
  /** Why it was not drawn. `null` when it was. */
  note: string | null;
}

/**
 * How many signals fell in each slice of the axis — the graph that appears
 * once the engine has actually been speaking.
 *
 * Shares the timeline's x-axis exactly, so the bars sit above their own
 * points. The last bin is CLOSED on the right (`x <= x1`) or the point at
 * x = 1 — always the most recent signal, and the one a reader cares about
 * most — would fall outside every bin and vanish from its own graph.
 */
export function signalDensity(tl: Timeline, binCount = 24): Density {
  const n = tl.points.length;
  if (n < MIN_POINTS_FOR_DENSITY || tl.degenerate) {
    return {
      bins: [], max: 0, drawn: false,
      note: `${plural(n, "signal")} on the axis — this fund draws a distribution ` +
        `from ${MIN_POINTS_FOR_DENSITY} points, not fewer. The points below are the whole record.`,
    };
  }
  const bins: DensityBin[] = Array.from({ length: binCount }, (_, i) => ({
    x0: i / binCount, x1: (i + 1) / binCount, n: 0,
  }));
  for (const p of tl.points) {
    const idx = Math.min(binCount - 1, Math.floor(p.x * binCount));
    bins[idx].n += 1;
  }
  const max = bins.reduce((m, b) => Math.max(m, b.n), 0);
  return { bins, max, drawn: true, note: null };
}

// ---------------------------------------------------------------- the list

/**
 * The ledger, NEWEST FIRST, with the undated rows kept and placed last.
 *
 * WHY IT IS SORTED HERE AND NOT LEFT IN PAYLOAD ORDER. Measured by looking at
 * the 42-signal arm: the spine's order is its fold's order, and on screen it
 * read 19d · 5d · 21d · 8d · 13d — a list beneath a TIME AXIS in no time order
 * at all, on a page whose central question is "when did the engine last speak".
 * The reader cannot find the most recent row, which is the row that matters.
 *
 * UNDATED ROWS ARE KEPT, NOT FILTERED. They sort last because they cannot be
 * placed, and they are still listed because the count above them includes them
 * — the same rule the timeline's `undated` list follows. A sort that dropped
 * them would make the list disagree with its own header.
 */
export function sortedSignals(ledger: SignalLedger | null | undefined): SignalRow[] {
  const rows = [...(ledger?.signals ?? [])];
  return rows.sort((a, b) => {
    const ta = instant(a.raised_at);
    const tb = instant(b.raised_at);
    if (ta == null && tb == null) return 0;
    if (ta == null) return 1;      // undated last, both directions
    if (tb == null) return -1;
    return tb - ta;                // newest first
  });
}
