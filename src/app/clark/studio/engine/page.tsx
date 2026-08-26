"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Loader2, RefreshCw } from "lucide-react";

import { fundApiClient } from "@/lib/fund_api";
import { StudioHeader } from "../components/StudioHeader";
import { KT } from "../theme";
import { readState, readError } from "../desk/deskRead";
import {
  cardBuckets,
  datasourceLine,
  assetsLine,
  driftExplanation,
  fateBuckets,
  sessionLabel,
  classLine,
  sortedCards,
  sortedSymbolRows,
  strategiesAbsence,
  syncLabel,
  reconcileHeadline,
  engineHeadline,
  unmatchedSessionNote,
  type EngineStrategyCard,
  type EngineSymbolRow,
  type EngineView,
  type SignalRow,
  type Tone,
} from "./engineView";
import {
  ageLabel,
  fateBar,
  foldedCaveats,
  glanceTiles,
  signalDensity,
  signalLabel,
  signalTimeline,
  sortedSignals,
  surfacedCaveats,
  type GlanceTile,
} from "./engineGlance";

/**
 * ENGINE — is it alive, what did it say, what happened to it, do the books
 * agree, and does anything need you.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * THIS PAGE WAS REDESIGNED ON 2026-08-27 (CEO, verbatim: *"Engine page is too
 * much text; we need analytics and graphs and meaningful and minimal UI"*).
 *
 * What it replaced was honest and unreadable: five stacked panels, every one
 * opening with a paragraph, ~2,000 rendered pixels, and not a single number on
 * an axis. Every sentence was true and the CEO still could not answer "is it
 * alive and does anything need me" without reading all of it. A surface whose
 * facts are correct and whose reader cannot find them has not published them.
 *
 * THE SHAPE NOW, and the reason for each part:
 *
 *   1. THE TRADE-READY BAR — five tiles, five questions, one glance. Computed
 *      by `glanceTiles` as ONE state from ONE input, so no renderer can produce
 *      half of it (the ENG1 lesson: a caller that patches two of five fields
 *      ships a payload that contradicts itself).
 *   2. WARN LINES — anything saying a CONTROL IS DOWN stays on the surface, in
 *      warn, one line, with its full paragraph one click away. theme.ts
 *      illumination clause 5. Demoting THESE would be the quiet half of a
 *      loosening, and `surfacedCaveats` is what keeps them up here.
 *   3. THE TIMELINE — the ledger as a picture. The axis ends at NOW, not at the
 *      last signal, so an engine that has been silent for eleven days looks
 *      silent. A distribution is drawn only from three points or more, the same
 *      rule NavPanel has refused to draw a two-point curve under since
 *      2026-08-20.
 *   4. THE REST — strategies, the reconciliation table, and every remaining
 *      paragraph behind one fold that carries its own count in the summary.
 *
 * NOTHING WAS DELETED. Every sentence the old page rendered is still computed
 * by the same function and still on this page; `engineCaveats` gathers them and
 * the fold holds them. Demotion, not deletion — an absence is still a word.
 *
 * NOTHING HERE ACTS. No button, no halt, no threshold. It is a reading.
 */

const TONE_TEXT: Record<Tone, string> = {
  good: "text-[var(--kt-up)]",
  bad: "text-[var(--kt-down)]",
  warn: "text-[var(--kt-warn)]",
  neutral: "text-[var(--kt-text-strong)]",
  quiet: "text-[var(--kt-text-muted)]",
};

const TONE_CHIP: Record<Tone, string> = {
  good: "border-[var(--kt-up)]/40 bg-[var(--kt-up)]/10 text-[var(--kt-up)]",
  bad: "border-[var(--kt-down)]/40 bg-[var(--kt-down)]/10 text-[var(--kt-down)]",
  warn: "border-[var(--kt-warn)]/40 bg-[var(--kt-warn)]/10 text-[var(--kt-warn)]",
  neutral: "border-[var(--kt-border)] bg-[var(--kt-inset)] text-[var(--kt-text)]",
  quiet: "border-[var(--kt-border)] bg-[var(--kt-inset)] text-[var(--kt-text-muted)]",
};

const TONE_DOT: Record<Tone, string> = {
  good: "bg-[var(--kt-up)]",
  bad: "bg-[var(--kt-down)]",
  warn: "bg-[var(--kt-warn)]",
  neutral: "bg-[var(--kt-text-dim)]",
  quiet: "bg-[var(--kt-text-muted)]",
};

function Panel({ title, subtitle, right, children }: {
  title: string; subtitle?: string; right?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <section className={KT.panel}>
      <div className="flex items-start justify-between gap-4 border-b border-[var(--kt-border)] px-5 py-3">
        <div>
          <div className={KT.label}>{title}</div>
          {subtitle && <div className={`mt-1 text-[11px] ${KT.muted}`}>{subtitle}</div>}
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

/** A quantity that may genuinely be unknown. Never prints 0 for an absence. */
function Qty({ v, unknown = "UNKNOWN" }: { v: number | null | undefined; unknown?: string }) {
  if (v == null) {
    return <span className={`font-mono text-[11px] ${KT.muted}`}>{unknown}</span>;
  }
  return <span className="font-mono tabular-nums text-sm text-[var(--kt-text)]">{v}</span>;
}

const stamp = (iso?: string | null) => {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toISOString().replace("T", " ").slice(0, 16) + "Z";
};

/**
 * ONE TILE OF THE TRADE-READY BAR.
 *
 * `unknown` decides the WEIGHT of the figure, not just its colour: an absence
 * renders in the muted tone at the same size, so it cannot be mistaken at a
 * glance for a number the fund computed. It is the tile-scale form of the rule
 * that `KT.heroDim` exists for.
 */
function Tile({ t }: { t: GlanceTile }) {
  return (
    <div className={`${KT.inset} px-4 py-3`} title={t.sub}>
      <div className={KT.label}>{t.label}</div>
      <div
        className={`mt-1 font-mono text-lg font-light leading-tight ${
          t.unknown ? "text-[var(--kt-text-muted)]" : TONE_TEXT[t.tone]
        }`}
      >
        {t.value}
      </div>
      <div className={`mt-1 text-[10px] leading-snug ${KT.muted}`}>{t.sub}</div>
    </div>
  );
}

/**
 * A one-line disclosure with its paragraph one click away.
 *
 * The whole redesign rests on this component behaving: the short line is a
 * PREFIX of the full text (asserted in engineGlance.test.ts), never a
 * rewrite, so opening it can add detail and can never contradict what the
 * reader already saw.
 */
function Fold({ short, full, className = "" }: { short: string; full: string; className?: string }) {
  if (full === short) return <div className={className}>{short}</div>;
  return (
    <details className={`group ${className}`}>
      <summary className="cursor-pointer list-none marker:hidden">
        {short}
        <span className={`ml-1 ${KT.muted} group-open:hidden`}>more</span>
      </summary>
      <div className="mt-1 opacity-90">{full}</div>
    </details>
  );
}

export default function EnginePage() {
  const [view, setView] = useState<EngineView | null>(null);
  const [failed, setFailed] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  /** The clock the ages on this page are measured against — stamped when the
   *  payload landed, not at render, so "11d ago" refers to the reading and not
   *  to whenever React last re-drew. Zero until the first successful read. */
  const [readAt, setReadAt] = useState(0);
  const [openSignal, setOpenSignal] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setView(await fundApiClient.getEngine());
      setReadAt(Date.now());
      setFailed(false);
      setErr(null);
    } catch (e) {
      // The payload is CLEARED on failure, deliberately: this page's whole
      // subject is what is true right now, and a stale engine reading beside a
      // failed refresh is the shape that produced the CEO's three-day-old lamp.
      setView(null);
      setFailed(true);
      setErr(readError(e));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const read = readState(view !== null, failed);
  const status = view?.status ?? null;
  const ledger = view?.ledger ?? null;
  const leg = view?.reconcile ?? null;

  const tiles = glanceTiles(view, readAt);
  const warn = surfacedCaveats(view);
  const folded = foldedCaveats(view);
  const bar = fateBar(ledger);
  const strip = fateBuckets(ledger);
  const timeline = signalTimeline(ledger, readAt);
  const density = signalDensity(timeline);
  const recon = reconcileHeadline(leg);
  const rows = sortedSymbolRows(leg);
  const cards = sortedCards(view?.strategies);
  const noCards = strategiesAbsence(view?.strategies);
  const unmatched = unmatchedSessionNote(view?.strategies);
  const head = engineHeadline(status);

  return (
    <div className={KT.page}>
      <StudioHeader
        subtitle="Engine — is it alive, what did it say, and do the books agree"
        actions={
          <button onClick={() => void load()} className={KT.btnGhost} disabled={busy}>
            {busy ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          </button>
        }
      />

      <div className={`${KT.container} space-y-4`}>
        {read === "loading" && (
          <div className={`${KT.card} ${KT.body}`}>Reading the engine…</div>
        )}
        {read === "unreadable" && (
          <div className={`${KT.card} border-[var(--kt-warn)]/40`}>
            <div className={`${KT.title} text-[var(--kt-warn)]`}>
              The engine could not be read — UNKNOWN, not &ldquo;not running&rdquo;
            </div>
            <div className={`mt-1 text-[12px] ${KT.body}`}>{err}</div>
            <div className={`mt-2 text-[11px] ${KT.muted}`}>
              A spine that cannot be reached and an engine that is not running are
              different facts. Nothing on this screen is a measurement right now.
            </div>
          </div>
        )}

        {read === "readable" && (
          <>
            {/* ═══════════════════════════ 1 · the trade-ready bar ═══════════
                Five questions, one row. The whole point of the redesign: the
                answer to "is it alive and does anything need me" is above the
                fold, in figures, before a single paragraph. */}
            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
              {tiles.map((t) => <Tile key={t.key} t={t} />)}
            </div>

            {/* ═══════════════════════════ 2 · controls that are down ════════
                Illumination clause 5: a disclosure that a control is down
                renders where the CEO looks, in the warn tone, the moment it
                exists. These are the ONLY paragraphs that stay on the surface,
                and each is one line until asked. */}
            {warn.map((c) => (
              <div
                key={c.key}
                className={`${KT.inset} border-[var(--kt-warn)]/40 px-4 py-2 text-[11px] text-[var(--kt-warn)]`}
              >
                <Fold short={c.short} full={c.full} />
              </div>
            ))}

            {/* ═══════════════════════════ 3 · the signals, as a picture ═════ */}
            <Panel
              title="Signals"
              subtitle="Every signal an engine has raised, on one axis, with what became of it."
              right={
                <div className="flex items-center gap-2">
                  {strip.map((b) => (
                    <span key={b.fate} className={`text-[10px] ${KT.muted}`} title={b.help}>
                      <span className={`mr-1 inline-block h-1.5 w-1.5 rounded-full align-middle ${TONE_DOT[b.countTone]}`} />
                      <span className={`font-mono tabular-nums ${TONE_TEXT[b.countTone]}`}>{b.n}</span>
                      <span className="ml-1 hidden lg:inline">{b.label}</span>
                    </span>
                  ))}
                </div>
              }
            >
              <div className="space-y-4 px-5 py-4">
                {/* --- the fate bar: a COMPOSITION, not a trend. One segment at
                        n=1 says "one signal, refused", which is exactly true. */}
                {/* AN EMPTY BAR AND A FULL ONE MUST NOT LOOK ALIKE. Caught in
                    the look-pass: the live reading's single REFUSED signal
                    tones `neutral` (a refusal is a decision somebody took —
                    ENG1's measured call), which painted a full-width bar in
                    the same grey as the empty track. "One signal, refused" and
                    "nothing has ever been raised" rendered identically, which
                    is the absence-as-zero defect drawn instead of written. The
                    empty case is DASHED and hollow and says so. */}
                {bar.empty ? (
                  <div className="flex h-2 w-full items-center rounded-full border border-dashed border-[var(--kt-border-strong)]">
                    <span className="sr-only">no signal has been raised</span>
                  </div>
                ) : (
                  <div className="flex h-2 w-full overflow-hidden rounded-full">
                    {bar.segments.map((s) => (
                      <div
                        key={s.fate}
                        style={{ width: `${s.pct}%` }}
                        title={`${s.label}: ${s.n} — ${s.help}`}
                        className={TONE_DOT[s.tone]}
                      />
                    ))}
                  </div>
                )}
                {bar.note && (
                  <div className={`text-[11px] text-[var(--kt-warn)]`}>{bar.note}</div>
                )}

                {/* --- the axis */}
                {timeline.absence ? (
                  <div className={`${KT.inset} px-4 py-3 text-[12px] ${KT.muted}`}>{timeline.absence}</div>
                ) : (
                  <div>
                    {/* The distribution, drawn only once there are three points
                        — NavPanel's own rule, borrowed rather than re-decided. */}
                    {density.drawn ? (
                      <svg
                        viewBox="0 0 100 20"
                        preserveAspectRatio="none"
                        className="h-10 w-full"
                        role="img"
                        aria-label="signals over time"
                      >
                        {density.bins.map((b, i) => (
                          <rect
                            key={i}
                            x={b.x0 * 100}
                            width={(b.x1 - b.x0) * 100}
                            y={20 - (density.max > 0 ? (b.n / density.max) * 20 : 0)}
                            height={density.max > 0 ? (b.n / density.max) * 20 : 0}
                            /* PAINTED THROUGH THE `fill` ATTRIBUTE, not a
                               Tailwind class. Caught by LOOKING at the many-
                               signal arm: `fill-[var(--kt-accent)]/40` renders
                               BLACK, because the `/40` opacity modifier cannot
                               be applied to an arbitrary CSS variable and the
                               whole declaration is dropped — leaving SVG's own
                               default fill. Every bar on the graph was black on
                               a black panel and the suite could not see it. */
                            fill="var(--kt-accent)"
                            fillOpacity={0.45}
                          />
                        ))}
                      </svg>
                    ) : (
                      density.note && <div className={`text-[10px] ${KT.muted}`}>{density.note}</div>
                    )}

                    {/* THE AXIS IS INSET BY HALF A DOT. Caught by geometry in
                        the look-pass: a point at x = 0 carries
                        `-translate-x-1/2`, so the OLDEST signal — always at the
                        left edge — was drawn half outside the panel and read as
                        a rendering glitch rather than as the first thing the
                        engine ever said. */}
                    <div className="relative mx-2 mt-2 h-8">
                      <div className="absolute inset-x-0 top-3 h-px bg-[var(--kt-border)]" />
                      {timeline.points.map((p) => (
                        <button
                          key={p.order_id}
                          onClick={() => setOpenSignal(openSignal === p.order_id ? null : p.order_id)}
                          title={`${p.label} · ${p.fate} · ${stamp(p.at)}${p.fenced ? " · fenced history" : ""}`}
                          style={{ left: `${p.x * 100}%` }}
                          className="absolute top-1 -translate-x-1/2"
                        >
                          {/* A FENCED point is drawn HOLLOW. It describes a
                              paper book that is gone, and a solid dot would
                              claim it still testifies about a live engine. */}
                          <span
                            className={`block h-3 w-3 rounded-full border-2 ${
                              p.fenced
                                ? `border-[var(--kt-text-muted)] bg-transparent`
                                : `border-transparent ${TONE_DOT[p.tone]}`
                            } ${openSignal === p.order_id ? "ring-2 ring-[var(--kt-accent)] ring-offset-1 ring-offset-[var(--kt-surface)]" : ""}`}
                          />
                        </button>
                      ))}
                    </div>
                    <div className={`mx-2 flex justify-between text-[10px] ${KT.muted}`}>
                      <span>{stamp(timeline.startIso)}</span>
                      {timeline.degenerate ? (
                        <span>one instant — the axis carries no spacing</span>
                      ) : (
                        <span>{timeline.endIsNow ? "now" : stamp(timeline.endIso)}</span>
                      )}
                    </div>
                  </div>
                )}
                {timeline.note && <div className={`text-[10px] ${KT.muted}`}>{timeline.note}</div>}
                {/* A SIGNAL THE AXIS CANNOT PLACE IS LISTED, NOT DROPPED. A
                    timeline showing four points beside a header saying five is
                    the vanishing row this surface exists to catch. */}
                {timeline.undated.length > 0 && (
                  <div className={`${KT.inset} px-4 py-2 text-[11px] text-[var(--kt-warn)]`}>
                    {timeline.undated.length} signal{timeline.undated.length === 1 ? "" : "s"} carr
                    {timeline.undated.length === 1 ? "ies" : "y"} no timestamp and cannot be placed
                    on the axis: {timeline.undated.map((u) => u.label).join(", ")}.
                  </div>
                )}

                {/* --- the ledger itself, one line each, detail on click.
                    THE ABSENCE IS SAID ONCE, BY THE TIMELINE. This block used
                    to render `ledgerAbsence(ledger)` as well, and on the
                    no-signals arm the SAME paragraph printed twice, one inset
                    above the other — found by looking at that arm, not by the
                    suite. `signalTimeline` already returns the ledger's own
                    absence sentence, and the list below is simply empty when
                    there is nothing in it. */}
                  <div className="divide-y divide-[var(--kt-border)]">
                    {sortedSignals(ledger).map((s: SignalRow) => {
                      const open = openSignal === s.order_id;
                      const tone = (strip.find((b) => b.fate === s.outcome)?.tone ?? "quiet") as Tone;
                      const age = ageLabel(s.raised_at, readAt);
                      return (
                        <div key={s.order_id} className="py-2">
                          <button
                            onClick={() => setOpenSignal(open ? null : s.order_id)}
                            className="flex w-full flex-wrap items-baseline gap-x-3 gap-y-1 rounded text-left transition-colors hover:bg-[var(--kt-hover)]"
                          >
                            <span className={`font-mono text-[11px] ${KT.muted} w-[90px] shrink-0`}>
                              {age ? age.text : "no timestamp"}
                            </span>
                            <span className="font-mono text-sm text-[var(--kt-text-strong)]">
                              {signalLabel(s)}
                            </span>
                            <span className={`rounded-full border px-2 py-0.5 text-[10px] ${TONE_CHIP[tone]}`}>
                              {s.status}
                            </span>
                            {s.fenced && (
                              <span className={`rounded-full border px-2 py-0.5 text-[10px] ${TONE_CHIP.quiet}`}>
                                fenced history
                              </span>
                            )}
                            <span className={`ml-auto text-[10px] ${KT.muted}`}>
                              {s.strategy_name ?? s.strategy_id ?? "unattributed"}
                            </span>
                          </button>
                          {open && (
                            <div className={`mt-2 space-y-1 border-l border-[var(--kt-border)] pl-3 text-[11px] ${KT.muted}`}>
                              {s.reason && <div className={KT.body}>{s.reason}</div>}
                              <div>
                                raised {stamp(s.raised_at)} · {s.source ?? "unknown source"}
                                {s.algo_id ? ` · ${s.algo_id}` : " · algorithm not stated"}
                                {s.venue ? ` · ${s.venue} venue` : " · venue not stated"}
                              </div>
                              <div>
                                {s.decided_by
                                  ? `decided by ${s.decided_by} at ${stamp(s.decided_at)}`
                                  : "nobody has decided"}
                                {s.filled_qty != null ? ` · filled ${s.filled_qty} @ ${s.avg_price}` : ""}
                                {s.failure_reason ? ` · ${s.failure_reason}` : ""}
                              </div>
                              {s.liveness?.reason && <div>{s.liveness.reason}</div>}
                              {(s.annotations ?? []).map((a, i) => (
                                <div key={i}>
                                  {a.type} by {a.actor ?? "unknown"} — {a.reason ?? "no reason recorded"}
                                  {" "}(an annotation, not this signal&rsquo;s fate)
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
              </div>
            </Panel>

            {/* ═══════════════════════════ 4 · the strategies ════════════════ */}
            <Panel
              title="Engine strategies"
              subtitle="What each one trades, on what data, and what it has actually said."
              right={
                <span className={`font-mono text-[11px] ${KT.muted}`}>
                  {view?.strategies?.readable === false
                    ? "UNKNOWN"
                    : `${cards.length} strateg${cards.length === 1 ? "y" : "ies"}`}
                </span>
              }
            >
              <div className="divide-y divide-[var(--kt-border)]">
                {unmatched && (
                  <div className={`px-5 py-2 text-[11px] text-[var(--kt-warn)]`}>{unmatched}</div>
                )}
                {noCards ? (
                  <div className={`px-5 py-4 text-[12px] ${KT.muted}`}>{noCards}</div>
                ) : (
                  cards.map((c: EngineStrategyCard) => {
                    const sess = sessionLabel(c);
                    const last = c.last_signal;
                    const buckets = cardBuckets(c);
                    return (
                      <div key={c.strategy_id} className="px-5 py-3">
                        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                          <div className="flex flex-wrap items-baseline gap-2">
                            <span className={KT.title}>{c.name ?? "unnamed strategy"}</span>
                            {/* ARCHIVED STAYS VISIBLE. It is the record of what
                                ran, and the fenced row below has nothing to
                                point at without it. */}
                            {c.archived && (
                              <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wide ${TONE_CHIP.quiet}`}>
                                archived
                              </span>
                            )}
                            <span className={`rounded-full border px-2 py-0.5 text-[10px] ${TONE_CHIP[sess.tone]}`}>
                              {sess.word}
                            </span>
                          </div>
                          <div className="flex items-center gap-3">
                            {buckets.map((b) => (
                              <span key={b.fate} className={`text-[10px] ${KT.muted}`} title={`${b.label} — ${b.help}`}>
                                <span className={`font-mono tabular-nums ${TONE_TEXT[b.countTone]}`}>{b.n}</span>
                                <span className="ml-1 hidden xl:inline">{b.label.toLowerCase()}</span>
                              </span>
                            ))}
                            <span className={`font-mono text-[11px] ${KT.muted}`}>
                              {c.state ?? "state unknown"}
                              {" · "}
                              {c.allocation_pct == null ? "allocation UNKNOWN" : `${c.allocation_pct}%`}
                            </span>
                          </div>
                        </div>

                        <div className={`mt-1 text-[11px] ${KT.muted}`}>
                          {c.rule ?? "no rule recorded"}
                          {" · "}
                          <span className={c.assets.length ? "" : KT.muted}>{assetsLine(c)}</span>
                        </div>

                        {/* THE DETAIL IS ONE CLICK AWAY, NOT DELETED. The
                            datasource is the field most likely to differ
                            between two algorithms that look identical — the
                            two on this record ask for 700 and 2000 days. */}
                        <details className={`mt-1 text-[10px] ${KT.muted}`}>
                          <summary className="cursor-pointer list-none marker:hidden">
                            {c.algorithm ?? "algorithm NOT DECLARED"} · datasource, class, last signal
                          </summary>
                          <div className="mt-1 space-y-0.5 border-l border-[var(--kt-border)] pl-3">
                            <div>{datasourceLine(c.datasource)}</div>
                            <div>{classLine(c)}</div>
                            {c.purpose && <div>{c.purpose}</div>}
                            <div>
                              {last
                                ? <>Last signal {stamp(last.raised_at)} — {signalLabel(last)}, {last.status}
                                    {last.fenced ? " (fenced history — the session that raised it is gone)" : ""}</>
                                : "This strategy has never raised a signal."}
                              {/* CARRIED OVER FROM THE OLD PAGE WITH ITS
                                  DEFECT FIXED: this read `{c.signals?.raised
                                  ?? 0}` and printed "1 of 0 fenced" whenever
                                  the card's counts could not be read — an
                                  arithmetic impossibility rendered as a
                                  measurement. Found by this page's own
                                  `?? 0` pin, on a line inherited rather than
                                  written this dispatch. */}
                              {c.signals_fenced != null && c.signals_fenced > 0 && (
                                <> · {c.signals_fenced} of{" "}
                                  {c.signals?.raised == null
                                    ? "an UNKNOWN number of"
                                    : c.signals.raised}{" "}
                                  fenced.</>
                              )}
                            </div>
                          </div>
                        </details>
                      </div>
                    );
                  })
                )}
              </div>
            </Panel>

            {/* ═══════════════════════════ 5 · do the books agree ════════════ */}
            <Panel
              title="Do the books agree"
              subtitle="The engine's implied position against the fund's own fold. Read-only."
              right={
                <span className={`rounded-full border px-2.5 py-0.5 text-[11px] ${TONE_CHIP[recon.tone]}`}>
                  {recon.word}
                </span>
              }
            >
              <div className="space-y-3 px-5 py-4">
                <div className={`text-[12px] ${TONE_TEXT[recon.tone]}`}>{recon.sentence}</div>

                {rows.length === 0 ? (
                  <div className={`text-[12px] ${KT.muted}`}>
                    No symbol has ever been signalled on, so there is nothing to line up.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead>
                        <tr className={KT.label}>
                          <th className="py-2 pr-4 font-normal">Symbol</th>
                          <th className="py-2 pr-4 font-normal">Strategy</th>
                          <th className="py-2 pr-4 font-normal">Engine (reported)</th>
                          <th className="py-2 pr-4 font-normal">Engine (implied)</th>
                          <th className="py-2 pr-4 font-normal">Fund book</th>
                          <th className="py-2 pr-4 font-normal">Drift</th>
                          <th className="py-2 font-normal">Verdict</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((r: EngineSymbolRow) => (
                          <tr key={`${r.strategy_id}-${r.symbol}`} className="border-t border-[var(--kt-border)] align-top">
                            <td className="py-2 pr-4 font-mono text-[var(--kt-text-strong)]">{r.symbol}</td>
                            <td className={`py-2 pr-4 text-[11px] ${KT.muted}`}>
                              {r.strategy_name ?? r.strategy_id ?? "unattributed"}
                            </td>
                            <td className="py-2 pr-4"><Qty v={r.engine_qty} /></td>
                            <td className="py-2 pr-4">
                              <Qty v={r.engine_implied_qty} />
                              {/* The dead engine's quantity, beside the live
                                  absence rather than instead of it — annotate,
                                  never erase. */}
                              {r.fenced && r.fenced_implied_qty != null && (
                                <div className={`mt-0.5 font-mono text-[10px] ${KT.muted}`}>
                                  was {r.fenced_implied_qty} (dead session)
                                </div>
                              )}
                            </td>
                            <td className="py-2 pr-4"><Qty v={r.book_qty} /></td>
                            <td className="py-2 pr-4"><Qty v={r.drift} unknown="—" /></td>
                            <td className={`py-2 text-[11px] ${TONE_TEXT[syncLabel(r.sync_state).tone]}`}>
                              {syncLabel(r.sync_state).word}
                              {driftExplanation(r) && (
                                <details className={`mt-0.5 text-[10px] ${KT.muted}`}>
                                  <summary className="cursor-pointer list-none marker:hidden">why</summary>
                                  <div className="mt-1">{driftExplanation(r)}</div>
                                </details>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </Panel>

            {/* ═══════════════════════════ 6 · everything demoted ════════════
                THE COUNT IS IN THE SUMMARY. A fold whose label does not say how
                much is behind it is an omission with a chevron on it; a fold
                that says "7 things this reading cannot say" has published the
                fact and is only asking whether the reader wants the words. */}
            {folded.length > 0 && (
              <details className={KT.panel}>
                <summary className={`cursor-pointer list-none px-5 py-3 marker:hidden ${KT.label}`}>
                  {folded.length} thing{folded.length === 1 ? "" : "s"} this reading cannot say,
                  and the caveats behind the numbers above
                </summary>
                <ul className={`space-y-2 border-t border-[var(--kt-border)] px-5 py-4 text-[12px] ${KT.muted}`}>
                  {folded.map((c) => (
                    <li key={c.key}>· <Fold short={c.short} full={c.full} className="inline" /></li>
                  ))}
                </ul>
              </details>
            )}

            <div className={`flex flex-wrap items-center gap-x-3 text-[10px] ${KT.muted}`}>
              <span>
                Read over {ledger?.domain?.events_scanned?.toLocaleString() ?? "?"} events
                {ledger?.domain?.seq_first != null && ledger?.domain?.seq_last != null
                  ? ` (seq ${ledger.domain.seq_first}–${ledger.domain.seq_last})`
                  : ""}
                {ledger?.domain?.window_bound ? " — THE WINDOW BOUND; older signals are unread." : "."}
              </span>
              <span>·</span>
              <span>{head.sentence}</span>
              <span>·</span>
              <Link href="/clark/studio/allocate" className={KT.accent}>
                size these strategies on Allocate
              </Link>
              <span>·</span>
              <span>Nothing on this page writes, halts, or crosses a threshold.</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
