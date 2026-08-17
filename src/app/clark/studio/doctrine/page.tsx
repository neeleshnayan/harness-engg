"use client";

import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  Check,
  CircleHelp,
  Gauge,
  Lock,
  ScrollText,
  X,
} from "lucide-react";
import { fundApiClient, DoctrineReview, DoctrineStage } from "@/lib/fund_api";
import { KT } from "../theme";
import { StudioNav } from "../components/StudioNav";
import { RiskBar } from "../components/RiskBar";

/**
 * Fund Genesis — the seven-stage workflow, with each stage's status read live.
 *
 * The whole reason this is a page and not a document: a workflow nobody can see
 * violated is a workflow nobody follows. Two design rules follow from that, and
 * both matter more than the styling.
 *
 * **Nothing here is hardcoded.** Every status comes from GET /fund/doctrine.
 * Stage 02 exists because a control was documented as operating while nothing
 * called it; a page that carried its own copy of "stage 02: holds" would be that
 * bug wearing a nicer font, and it would be the first thing to rot.
 *
 * **Three statuses, not two.** `unknown` renders differently from both `holds`
 * and `gap`, because "could not tell" is its own answer. The fund has spent a
 * week removing places where a missing reading was silently scored as a good one.
 *
 * An unreachable spine says so rather than showing an empty page — the same rule
 * RiskBar follows. Silence must never look like compliance.
 */

const TONE: Record<
  DoctrineStage["status"],
  { icon: typeof Check; label: string; chip: string; rail: string }
> = {
  holds: {
    icon: Check,
    label: "Holds",
    chip:
      "border-[var(--kt-accent-border)] bg-[var(--kt-accent-bg)] text-[var(--kt-accent)]",
    rail: "bg-[var(--kt-accent)]",
  },
  gap: {
    icon: X,
    label: "Gap",
    chip: "border-transparent bg-[var(--kt-inset)] text-[var(--kt-down)]",
    rail: "bg-[var(--kt-down)]",
  },
  unknown: {
    icon: CircleHelp,
    label: "Unknown",
    chip: "border-transparent bg-[var(--kt-inset)] text-[var(--kt-warn)]",
    rail: "bg-[var(--kt-warn)]",
  },
};

export default function DoctrinePage() {
  const [d, setD] = useState<DoctrineReview | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const r = await fundApiClient.getDoctrine();
        if (alive) {
          setD(r);
          setErr(null);
        }
      } catch (e) {
        if (alive) setErr(e instanceof Error ? e.message : "unreachable");
      }
    };
    load();
    const t = setInterval(load, 60000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  return (
    <>
      <RiskBar />
      <div className={KT.container}>
        <header className="mb-7 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className={KT.label}>Krypton Fund · Operating Doctrine</p>
            <h1 className="mt-1 text-2xl font-medium tracking-tight">
              Fund Genesis
            </h1>
          </div>
          <StudioNav />
        </header>

        {/* The thesis. Static prose, because it is an argument rather than a
            reading — and it is the argument the whole page rests on. */}
        <section className={`${KT.card} mb-6 border-l-2 border-l-[var(--kt-accent)]`}>
          <p className="text-[15px] leading-relaxed">
            Every serious mistake this fund has made was a{" "}
            <strong className="font-medium">false belief about itself</strong>,
            not a wrong guess about markets. A gate was loosened and documented
            as a tightening. Kill switches were written, tested, and connected to
            nothing. A test asserted the very bug it existed to catch. A proposed
            improvement measured better and was worse where it counted.
          </p>
          <p className={`mt-3 text-[15px] leading-relaxed ${KT.muted}`}>
            None were prediction errors — a fund that never traded could make all
            four. So this workflow is not about being careful. Care does not
            scale and does not survive a tired evening. Each stage below exists
            because something false got all the way through without it.
          </p>
        </section>

        {err && (
          <div
            className={`${KT.card} mb-6 flex items-start gap-2 border-[var(--kt-warn)]`}
          >
            <AlertTriangle size={15} className="mt-0.5 text-[var(--kt-warn)]" />
            <div>
              <p className="text-sm font-medium">Spine unreachable</p>
              <p className={`text-xs ${KT.muted}`}>
                Cannot read any stage&rsquo;s status — so this page is showing
                nothing rather than showing compliance. {err}
              </p>
            </div>
          </div>
        )}

        {!d && !err && (
          <p className={`text-sm ${KT.muted}`}>Reading live status…</p>
        )}

        {d && (
          <>
            <div className="mb-6 flex flex-wrap items-center gap-2">
              <Gauge size={14} className={KT.muted} />
              <p className={`text-xs ${KT.muted}`}>{d.note}</p>
            </div>

            <ol className="mb-10 space-y-3">
              {d.stages.map((s) => (
                <StageRow key={s.n} s={s} />
              ))}
            </ol>

            {/* The absence doctrine — one rule under all seven. Rendered as a
                table because every row was a real collapse found in live code,
                which makes it data, not prose. */}
            <section className="mb-10">
              <h2 className="mb-1 text-lg font-medium tracking-tight">
                The absence doctrine
              </h2>
              <p className={`mb-4 max-w-2xl text-sm ${KT.muted}`}>
                One rule under all seven, and the source of most of the bugs
                above: missing information has to look missing. Every row here
                was found in live code.
              </p>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[34rem] border-collapse text-sm">
                  <thead>
                    <tr>
                      <th className={`${KT.label} border-b border-[var(--kt-border)] pb-2 pr-4 text-left`}>
                        This
                      </th>
                      <th className={`${KT.label} border-b border-[var(--kt-border)] pb-2 pr-4 text-left`}>
                        is never
                      </th>
                      <th className={`${KT.label} border-b border-[var(--kt-border)] pb-2 text-left`}>
                        Because
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.absence_doctrine.map((r) => (
                      <tr key={r.this}>
                        <td className="whitespace-nowrap border-b border-[var(--kt-border)] py-2.5 pr-4 font-medium">
                          {r.this}
                        </td>
                        <td className="whitespace-nowrap border-b border-[var(--kt-border)] py-2.5 pr-4 font-medium text-[var(--kt-down)]">
                          {r.is_never}
                        </td>
                        <td className={`border-b border-[var(--kt-border)] py-2.5 ${KT.muted}`}>
                          {r.because}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {/* Invariants. Surfaced next to the workflow rather than living in a
                builder's working memory, which is the thing that erodes. */}
            <section className={`${KT.card} mb-8 border-[var(--kt-accent-border)]`}>
              <div className="mb-3 flex items-center gap-2">
                <Lock size={14} className={KT.accent} />
                <p className={KT.label}>Two invariants, not preferences</p>
              </div>
              <ol className="space-y-2.5">
                {d.invariants.map((inv, i) => (
                  <li key={i} className="flex gap-3 text-sm leading-relaxed">
                    <span className="font-mono text-xs text-[var(--kt-accent)]">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span>{inv}</span>
                  </li>
                ))}
              </ol>
            </section>

            <footer
              className={`flex flex-wrap items-center gap-2 border-t border-[var(--kt-border)] pt-4 text-xs ${KT.muted}`}
            >
              <ScrollText size={13} />
              <span>
                Canonical copy:{" "}
                <code className="font-mono">{d.canon}</code> — that copy is what
                the work follows. If this page and the repo ever disagree, the
                repo wins.
              </span>
            </footer>
          </>
        )}
      </div>
    </>
  );
}

function StageRow({ s }: { s: DoctrineStage }) {
  const tone = TONE[s.status];
  const Icon = tone.icon;
  const [open, setOpen] = useState(false);

  return (
    <li className={`${KT.card} ${KT.cardHover} relative overflow-hidden p-0`}>
      <span className={`absolute inset-y-0 left-0 w-[2px] ${tone.rail}`} />
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-start gap-4 px-5 py-4 text-left"
      >
        <span className="mt-0.5 font-mono text-xs tabular-nums text-[var(--kt-accent)]">
          {String(s.n).padStart(2, "0")}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-[15px] font-medium">{s.title}</span>
            <span
              className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] ${tone.chip}`}
            >
              <Icon size={10} /> {tone.label}
            </span>
            {/* How much the status is worth. "Attested" is a human claim with no
                automatic reading — weaker, and labelled weaker. */}
            <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
              {s.basis}
            </span>
          </span>
          {s.detail && (
            <span className={`mt-1.5 block text-sm leading-relaxed ${KT.muted}`}>
              {s.detail}
            </span>
          )}
          {!open && (
            <span className={`mt-2 block font-mono text-[10px] uppercase tracking-[0.14em] ${KT.muted}`}>
              {"› why this exists"}
            </span>
          )}
        </span>
      </button>

      {open && (
        <div className="border-t border-[var(--kt-border)] px-5 py-4 pl-[3.4rem]">
          <p className="text-sm leading-relaxed">{s.why}</p>
          <p className="mt-3 rounded-lg bg-[var(--kt-inset)] px-3 py-2 text-sm">
            <span className={`${KT.label} mr-2`}>Ask</span>
            {s.ask}
          </p>
          <div className="mt-3">
            <p className={KT.label}>Earned by</p>
            <p className={`mt-1 text-sm leading-relaxed ${KT.muted}`}>
              {s.earned_by}
            </p>
          </div>
          {s.mechanism && (
            <div className="mt-3">
              <p className={KT.label}>Mechanism</p>
              <p className={`mt-1 font-mono text-xs ${KT.muted}`}>
                {s.mechanism}
              </p>
            </div>
          )}
        </div>
      )}
    </li>
  );
}
