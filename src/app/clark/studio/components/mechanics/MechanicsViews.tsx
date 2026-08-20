"use client";

import React, { useMemo, useState } from "react";
import { FlaskConical, GitBranch, Skull, Sparkles } from "lucide-react";
import { MechanicsView, MechanicsCandidate } from "@/lib/fund_api";
import { KT } from "../../theme";

/**
 * The Mechanics views, extracted from the Mechanics tab so each can hang off
 * the seat that OWNS it.
 *
 * Mechanics answered "what is the system doing" on a tab of its own, which put
 * the funnel, the causes of death and the gate's lineage one navigation away
 * from the only place they change a decision: the quant's page, where a
 * candidate is judged, and the desk, where the firm is reviewed. The rule the
 * CEO set for charts is that one — a chart stays only if it informs a specific
 * click or dispatch — so these moved rather than being restyled, and the tab
 * that hosted them is now a redirect.
 *
 * Nothing about the rendering changed in the move. Every figure is still read
 * from GET /fund/mechanics; the pieces the fund does NOT have (population
 * search, inheritance) are still drawn unlit rather than implied.
 */

const STATUS_TONE: Record<string, { dot: string; text: string }> = {
  running: { dot: "bg-[var(--kt-accent)]", text: "text-[var(--kt-accent)]" },
  partial: { dot: "bg-[var(--kt-warn)]", text: "text-[var(--kt-warn)]" },
  scaffolded: {
    dot: "bg-[var(--kt-text-muted)]",
    text: "text-[var(--kt-text-dim)]",
  },
  blocked: { dot: "bg-[var(--kt-down)]", text: "text-[var(--kt-down)]" },
  "not started": {
    dot: "bg-[var(--kt-border-strong)]",
    text: "text-[var(--kt-text-muted)]",
  },
};

export function MechSectionHead({ title, lede }: { title: string; lede: string }) {
  return (
    <div className="mb-4">
      <h2 className="text-lg font-medium tracking-tight">{title}</h2>
      <p className={`mt-0.5 max-w-2xl text-sm ${KT.muted}`}>{lede}</p>
    </div>
  );
}

/* ------------------------------------------------------------------ arc --- */

/**
 * The story, first, before any chart.
 *
 * A dashboard tells you the state. It cannot tell you WHY the state is what it is,
 * and the why is the only part that survives being handed to someone else. Each
 * beat carries the measurement that produced it, so the narrative cannot quietly
 * become folklore: if a number moves, the beat is wrong and gets rewritten.
 */
export function Arc({ m }: { m: MechanicsView }) {
  const beats = m.arc?.beats ?? [];
  const [open, setOpen] = useState<number | null>(
    beats.length ? beats[beats.length - 1].beat : null,
  );
  if (!beats.length) return null;

  return (
    <section className="mb-12">
      <MechSectionHead
        title="How it got here"
        lede="Seven beats. Every serious change to this machine was forced by something measured, not chosen — so the story is the evidence in order."
      />
      <ol className="relative space-y-0">
        <span
          aria-hidden
          className="absolute bottom-4 left-[0.42rem] top-3 w-px bg-[var(--kt-border)]"
        />
        {beats.map((b) => {
          const isOpen = open === b.beat;
          const isNow = b.at === "now";
          return (
            <li key={b.beat} className="relative pb-4 pl-8">
              <span
                className={`absolute left-0 top-2.5 h-[0.85rem] w-[0.85rem] rounded-full border-2 transition-colors ${
                  isNow
                    ? "border-[var(--kt-accent)] bg-[var(--kt-accent)]"
                    : isOpen
                      ? "border-[var(--kt-accent)] bg-[var(--kt-bg)]"
                      : "border-[var(--kt-border-strong)] bg-[var(--kt-bg)]"
                }`}
              />
              <button
                type="button"
                onClick={() => setOpen(isOpen ? null : b.beat)}
                aria-expanded={isOpen}
                className="w-full text-left"
              >
                <span className="flex flex-wrap items-baseline gap-2">
                  <span className={`font-mono text-[10px] uppercase tracking-[0.14em] ${KT.muted}`}>
                    {b.at}
                  </span>
                  <span
                    className={`text-[15px] font-medium leading-snug ${isNow ? KT.accent : ""}`}
                  >
                    {b.title}
                  </span>
                </span>
              </button>
              {isOpen && (
                <div className="mt-2">
                  <p className="max-w-2xl text-sm leading-relaxed">{b.body}</p>
                  <p className="mt-2 border-l-2 border-[var(--kt-border-strong)] pl-3 font-mono text-[10px] leading-relaxed text-[var(--kt-text-muted)]">
                    {b.evidence}
                  </p>
                </div>
              )}
            </li>
          );
        })}
      </ol>
      <p className={`mt-1 pl-8 text-xs italic ${KT.muted}`}>{m.arc?.note}</p>
    </section>
  );
}

/* ---------------------------------------------------------------- funnel --- */

export function Funnel({ m }: { m: MechanicsView }) {
  const steps = m.funnel?.steps ?? [];
  const max = Math.max(1, ...steps.map((s) => s.count ?? 0));
  const cal = m.funnel?.calibration;

  return (
    <section className="mb-10">
      <MechSectionHead
        title="The pipeline, end to end"
        lede="Each bar is a real count. The drop-off is the point: the bar exists to kill things cheaply."
      />
      <div className="space-y-2">
        {steps.map((s, i) => {
          const uncounted = s.count == null;
          const prev = i > 0 ? steps[i - 1].count : null;
          const lost =
            prev != null && s.count != null && prev > s.count ? prev - s.count : null;
          return (
            <div key={s.step} className={`${KT.card} p-4`}>
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <div className="flex items-baseline gap-3">
                  <span className={KT.label}>{s.step}</span>
                  <span className="text-2xl font-light tabular-nums">
                    {uncounted ? "—" : s.count}
                  </span>
                  {lost != null && lost > 0 && (
                    <span className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--kt-down)]">
                      <Skull size={10} /> {lost} lost here
                    </span>
                  )}
                </div>
              </div>
              <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-[var(--kt-inset)]">
                <div
                  className="h-full rounded-full bg-[var(--kt-accent)] transition-[width] duration-1000 ease-out"
                  style={{ width: uncounted ? "0%" : `${((s.count ?? 0) / max) * 100}%` }}
                />
              </div>
              <p className={`mt-2 text-xs leading-relaxed ${KT.muted}`}>{s.what}</p>
              {/* An unavailable subsystem must never render as a zero. */}
              {s.absent_note && (
                <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--kt-warn)]">
                  {s.absent_note}
                </p>
              )}
            </div>
          );
        })}
      </div>
      <p className={`mt-3 text-xs leading-relaxed ${KT.muted}`}>{m.funnel?.honest_note}</p>

      {/* Instruments, kept visibly apart from the funnel. A null passing is the
          gate leaking, and it is the measurement that drove v1 -> v4 — so it
          belongs beside the belt prominently, and nowhere near the survival rate. */}
      {cal && (
        <div className={`${KT.card} mt-4 border-l-2 border-l-[var(--kt-warn)] p-4`}>
          <p className={`${KT.label} flex items-center gap-2`}>
            <FlaskConical size={12} /> Calibration instruments
          </p>
          <div className="mt-2 flex flex-wrap items-baseline gap-x-6 gap-y-1">
            <MechStat n={cal.submitted} label="run" />
            <MechStat n={cal.judged} label="judged" />
            <MechStat n={cal.passed} label="passed = gate leaked" tone="text-[var(--kt-down)]" />
          </div>
          <p className={`mt-2 text-xs leading-relaxed ${KT.muted}`}>{cal.note}</p>
          <p className={`mt-1.5 text-xs italic ${KT.muted}`}>{cal.caveat}</p>
        </div>
      )}
    </section>
  );
}

/* -------------------------------------------------------------- timeline --- */

export function Timeline({ m }: { m: MechanicsView }) {
  const t = m.timeline;
  const days = t?.days ?? [];
  const maxEv = Math.max(1, ...days.map((d) => d.events));

  const byDay = useMemo(() => {
    const out: Record<string, { builds: typeof t.builds; verdicts: typeof t.verdicts }> = {};
    for (const d of days) out[d.day] = { builds: [], verdicts: [] };
    for (const b of t?.builds ?? []) if (out[b.at]) out[b.at].builds.push(b);
    for (const v of t?.verdicts ?? []) if (out[v.day]) out[v.day].verdicts.push(v);
    return out;
  }, [t, days]);

  if (!t || !days.length) return null;

  return (
    <section className="mb-10">
      <MechSectionHead
        title="How it evolved, against the actual runs"
        lede="Two streams on one UTC axis. Events carry a hash-chain seq and are independently verifiable; build marks are dated claims about the machinery, which the log cannot know about."
      />

      <div className="overflow-x-auto">
        <div className="flex min-w-[36rem] items-end gap-3">
          {days.map((d) => {
            const cell = byDay[d.day];
            const passed = cell?.verdicts.filter((v) => v.passed === true).length ?? 0;
            const killed = cell?.verdicts.filter((v) => v.passed === false).length ?? 0;
            return (
              <div key={d.day} className="flex min-w-[5.5rem] flex-1 flex-col gap-1.5">
                {/* build marks sit ABOVE the axis — they are causes, not activity */}
                <div className="flex min-h-[3.2rem] flex-col justify-end gap-1">
                  {cell?.builds.map((b) => (
                    <span
                      key={b.label}
                      title={b.detail}
                      className="cursor-help truncate rounded border border-[var(--kt-accent-border)] bg-[var(--kt-accent-bg)] px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.08em] text-[var(--kt-accent)]"
                    >
                      {b.label}
                    </span>
                  ))}
                </div>

                <div className="relative h-24 rounded-md bg-[var(--kt-inset)]"
                     title={`${d.events} log event(s)`}>
                  <div
                    className="absolute bottom-0 w-full rounded-md bg-[var(--kt-accent)]/25 transition-[height] duration-1000 ease-out"
                    style={{ height: `${(d.events / maxEv) * 100}%` }}
                  />
                  <div className="absolute inset-x-0 bottom-1 flex flex-wrap justify-center gap-[3px] px-1">
                    {cell?.verdicts.map((v) => (
                      <span
                        key={v.candidate_id}
                        title={`${v.algorithm}${
                          v.is_calibration ? " (calibration instrument)" : ""
                        } — ${
                          v.passed === true
                            ? "passed"
                            : v.passed === false
                              ? "killed: " + v.causes.join(", ")
                              : "unjudged"
                        }`}
                        className={`h-1.5 w-1.5 rounded-full ${
                          v.passed === true
                            ? "bg-[var(--kt-accent)]"
                            : v.passed === false
                              ? "bg-[var(--kt-down)]"
                              : "bg-[var(--kt-text-muted)]"
                        } ${v.is_calibration ? "ring-1 ring-[var(--kt-warn)]" : ""}`}
                      />
                    ))}
                  </div>
                </div>

                <p className="text-center font-mono text-[10px] tabular-nums text-[var(--kt-text-muted)]">
                  {d.day.slice(5)}
                </p>
                <p className="text-center font-mono text-[9px] tabular-nums text-[var(--kt-text-muted)]">
                  {d.events} ev{d.verdicts ? ` · ${d.verdicts} run` : ""}
                </p>
                {(passed > 0 || killed > 0) && (
                  <p className="text-center font-mono text-[9px] tabular-nums">
                    <span className="text-[var(--kt-accent)]">{passed}✓</span>{" "}
                    <span className="text-[var(--kt-down)]">{killed}✗</span>
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <Legend />
      <p className={`mt-2 text-xs ${KT.muted}`}>{t.note}</p>
      <p className={`mt-1 text-xs italic ${KT.muted}`}>{t.caveat}</p>
    </section>
  );
}

function Legend() {
  return (
    <div className={`mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] ${KT.muted}`}>
      <Key className="bg-[var(--kt-accent)]" label="verdict: passed" />
      <Key className="bg-[var(--kt-down)]" label="verdict: killed" />
      <Key className="bg-[var(--kt-text-muted)]" label="unjudged" />
      <Key
        className="bg-[var(--kt-text-muted)] ring-1 ring-[var(--kt-warn)]"
        label="calibration instrument, not a money attempt"
      />
      <span className="font-mono uppercase tracking-[0.08em]">
        bar height = log events that day
      </span>
    </div>
  );
}

function Key({ className, label }: { className: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`h-1.5 w-1.5 rounded-full ${className}`} />
      {label}
    </span>
  );
}

/* -------------------------------------------------------------- pressure --- */

export function Pressure({ m }: { m: MechanicsView }) {
  const p = m.selection_pressure;
  const causes = p?.causes ?? [];
  const max = Math.max(1, ...causes.map((c) => c.count));
  if (!causes.length) return null;

  return (
    <section className="mb-10">
      <MechSectionHead
        title="What does the killing"
        lede="The most useful chart here. A gate that only ever fires one rule is a one-rule gate wearing five."
      />
      <div className="space-y-1.5">
        {causes.map((c) => (
          <div key={c.cause} className="flex items-center gap-3">
            <span className="w-8 shrink-0 text-right font-mono text-xs tabular-nums text-[var(--kt-down)]">
              {c.count}
            </span>
            <div className="h-5 min-w-0 flex-1 overflow-hidden rounded bg-[var(--kt-inset)]">
              <div
                className="flex h-full items-center rounded bg-[var(--kt-down)]/20 pl-2 transition-[width] duration-1000 ease-out"
                style={{ width: `${(c.count / max) * 100}%` }}
              >
                <span className="truncate whitespace-nowrap text-[11px]">{c.cause}</span>
              </div>
            </div>
            <span className={`w-10 shrink-0 font-mono text-[10px] tabular-nums ${KT.muted}`}>
              {c.share_pct}%
            </span>
          </div>
        ))}
      </div>
      <p className={`mt-3 text-xs ${KT.muted}`}>{p?.note}</p>
    </section>
  );
}

/* ---------------------------------------------------------------- cohort --- */

export function Cohort({ m }: { m: MechanicsView }) {
  const rows = m.cohort?.candidates ?? [];
  const [showCal, setShowCal] = useState(false);
  const shown = showCal ? rows : rows.filter((r) => !r.is_calibration);
  if (!rows.length) return null;

  return (
    <section className="mb-10">
      <MechSectionHead
        title="The cohort"
        lede="Every candidate is a GRID, not a strategy — so the population the sweep explored is bigger than the number of candidates."
      />
      <label className={`mb-3 flex cursor-pointer items-center gap-2 text-xs ${KT.muted}`}>
        <input
          type="checkbox"
          checked={showCal}
          onChange={(e) => setShowCal(e.target.checked)}
          className="accent-[var(--kt-accent)]"
        />
        Show the {m.cohort?.calibration_count ?? 0} calibration instruments (nulls and
        oracles — they measure the gate, they are not attempts to make money)
      </label>
      <div className="space-y-1.5">
        {shown.map((c) => (
          <CohortRow key={c.candidate_id} c={c} />
        ))}
      </div>
      <p className={`mt-3 text-xs italic ${KT.muted}`}>{m.cohort?.note}</p>
    </section>
  );
}

function CohortRow({ c }: { c: MechanicsCandidate }) {
  const tone =
    c.passed === true
      ? "border-l-[var(--kt-accent)]"
      : c.passed === false
        ? "border-l-[var(--kt-down)]"
        : "border-l-[var(--kt-text-muted)]";
  return (
    <div className={`${KT.card} border-l-2 p-3 ${tone}`}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-mono text-xs">{c.algorithm}</span>
        {c.is_calibration && (
          <span className="rounded border border-[var(--kt-warn)] px-1.5 font-mono text-[9px] uppercase tracking-[0.08em] text-[var(--kt-warn)]">
            instrument
          </span>
        )}
        <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
          {c.variants} variant{c.variants === 1 ? "" : "s"} swept
        </span>
        <span
          className={`font-mono text-[10px] uppercase tracking-[0.1em] ${
            c.passed === true
              ? "text-[var(--kt-accent)]"
              : c.passed === false
                ? "text-[var(--kt-down)]"
                : KT.muted
          }`}
        >
          {c.passed === true ? "survived" : c.passed === false ? "killed" : c.state}
        </span>
        {c.finished_at && (
          <span className={`ml-auto font-mono text-[10px] tabular-nums ${KT.muted}`}>
            {c.finished_at.slice(0, 16).replace("T", " ")}
          </span>
        )}
      </div>
      {c.causes.length > 0 && (
        <p className={`mt-1.5 text-[11px] ${KT.muted}`}>
          <span className="text-[var(--kt-down)]">died of:</span> {c.causes.join(" · ")}
        </p>
      )}
    </div>
  );
}

/* -------------------------------------------------------------- selector --- */

export function Selector({ m }: { m: MechanicsView }) {
  const gens = m.selector?.generations ?? [];
  if (!gens.length) return null;

  return (
    <section className="mb-10">
      <MechSectionHead
        title="The selector is under selection too"
        lede="Generations of the thing doing the judging. Each one died of something measured, not of taste."
      />
      <div className="overflow-x-auto">
        <div className="flex min-w-[34rem] gap-2">
          {gens.map((g, i) => {
            const alive = !g.died_of;
            return (
              <React.Fragment key={g.version}>
                {i > 0 && (
                  <span className={`self-center font-mono text-xs ${KT.muted}`}>→</span>
                )}
                <div
                  className={`${KT.card} flex-1 p-3 ${
                    alive
                      ? "border-[var(--kt-accent-border)] bg-[var(--kt-accent-bg)]"
                      : "opacity-70"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className={`font-mono text-sm ${alive ? KT.accent : "text-[var(--kt-text-dim)]"}`}>
                      {g.version}
                    </span>
                    {alive ? (
                      <Sparkles size={11} className={KT.accent} />
                    ) : (
                      <Skull size={11} className="text-[var(--kt-down)]" />
                    )}
                  </div>
                  <p className="mt-1.5 text-[11px] font-medium leading-snug">
                    {g.died_of ?? "current"}
                  </p>
                  <p className={`mt-1 text-[10px] leading-snug ${KT.muted}`}>{g.evidence}</p>
                  <p className="mt-1.5 font-mono text-[9px] uppercase tracking-[0.08em] text-[var(--kt-warn)]">
                    {g.metric}
                  </p>
                </div>
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </section>
  );
}

/* ---------------------------------------------------------------- ladder --- */

export function Ladder({ m }: { m: MechanicsView }) {
  const rungs = m.ladder?.rungs ?? [];
  if (!rungs.length) return null;

  return (
    <section className="mb-10">
      <MechSectionHead
        title="The self-evolving ladder — lit and unlit"
        lede="Read bottom-up. The lower rungs run today; the upper ones are named so the ladder can be read honestly rather than implied."
      />
      <div className="space-y-1.5">
        {[...rungs].reverse().map((r) => {
          const tone = STATUS_TONE[r.status] ?? STATUS_TONE["not started"];
          return (
            <div
              key={r.rung}
              className={`${KT.card} flex items-start gap-3 p-3 ${
                r.status === "running" ? "" : "opacity-75"
              }`}
            >
              <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${tone.dot}`} />
              <div className="min-w-0">
                <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
                  {r.rung}
                  <span className={`font-mono text-[9px] uppercase tracking-[0.1em] ${tone.text}`}>
                    {r.status}
                  </span>
                </p>
                <p className={`mt-0.5 text-xs leading-relaxed ${KT.muted}`}>{r.detail}</p>
              </div>
            </div>
          );
        })}
      </div>
      <p className={`mt-3 text-xs italic ${KT.muted}`}>{m.ladder?.note}</p>

      {m.lineage && (
        <div className={`${KT.card} mt-4 p-4`}>
          <p className={`${KT.label} flex items-center gap-2`}>
            <GitBranch size={12} /> Composition that exists today
          </p>
          <div className="mt-2.5 space-y-1">
            {(m.lineage.nodes ?? []).map((n) => (
              <div
                key={n.strategy_id}
                className="flex flex-wrap items-center gap-2 text-xs"
                style={{ paddingLeft: `${(n.depth ?? 0) * 1.1}rem` }}
              >
                <span className={KT.muted}>{n.depth ? "└" : "•"}</span>
                <span className="font-medium">{n.name}</span>
                <span className={`font-mono text-[10px] uppercase ${KT.muted}`}>{n.state}</span>
                {n.assets.length > 0 && (
                  <span className={`font-mono text-[10px] ${KT.muted}`}>
                    {n.assets.join(", ")}
                  </span>
                )}
              </div>
            ))}
          </div>
          <p className={`mt-3 text-xs italic ${KT.muted}`}>{m.lineage.note}</p>
        </div>
      )}
    </section>
  );
}

/* ----------------------------------------------------------------- chrome --- */

function MechStat({ n, label, tone }: { n: number; label: string; tone?: string }) {
  return (
    <span className="flex items-baseline gap-1.5">
      <span className={`text-xl font-light tabular-nums ${tone ?? ""}`}>{n}</span>
      <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
        {label}
      </span>
    </span>
  );
}
