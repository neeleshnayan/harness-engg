"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { fundApiClient, DeskView, SpineEvent } from "@/lib/fund_api";
import { KT } from "../../theme";
import { StudioHeader } from "../../components/StudioHeader";
import { SeatFace } from "../SeatFace";
import { faceFor } from "../faces";
import { estimateCostUsd, fmtAt, fmtUsd, isSeat } from "../seatLib";
import { QueuedAsk, queuedAsks } from "../execDesk";

/**
 * The CTO's desk — what waits on Fable's hands, and what the bench costs.
 *
 * Full build against docs/briefs/EXEC_DESKS_2026-08-20.md. Everything here is
 * CTO WORK, not CEO decisions: the dispatch queue, unresolved dispatches, the
 * accepted-but-unbuilt backlog, and the week's dispatch economics.
 *
 * The queue is where the constitution's 2026-08-20 amendment becomes visible.
 * A seat may FILE a dispatch request tagged with its own name — "mechanism
 * requests validator" — but a seat-filed request is an ASK, never a trigger:
 * it sits until a human fires it, exactly like a CEO-typed one. So each row
 * renders three things the old version collapsed into two: who filed it (with
 * their face, and whether that filer is a seat or a human), where it sits on
 * the seat files → CEO approves → CTO triggers path, and how long it has
 * waited. The first live instance is request 5fc56190, filed by `mechanism`
 * against `validator` — it renders as "awaiting CEO approval" because no
 * DeskRequestApproved event exists for it, and that is the honest state, not a
 * missing feature.
 */
export default function CtoDeskPage() {
  const [desk, setDesk] = useState<DeskView | null>(null);
  const [events, setEvents] = useState<SpineEvent[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [d, ev] = await Promise.allSettled([
      fundApiClient.getDesk(),
      fundApiClient.getEvents(1000, 0),
    ]);
    if (d.status === "fulfilled") { setDesk(d.value); setErr(null); }
    else { setDesk(null); setErr(d.reason instanceof Error ? d.reason.message : "unreachable"); }
    setEvents(ev.status === "fulfilled" ? (ev.value.events || []) : null);
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  const queue = useMemo(() => queuedAsks(desk?.requests ?? []), [desk]);
  const seatFiled = queue.filter((a) => a.seatFiled).length;
  const cleared = queue.filter((a) => a.stage === "cleared_to_trigger").length;

  const unresolvedDispatches = useMemo(() => {
    if (!events) return null;
    const resolved = new Set(
      events.filter((e) => e.type === "DeskRequestResolved")
            .map((e) => (e.payload as { request_id?: string })?.request_id));
    return events.filter((e) => e.type === "DeskDispatched")
      .map((e) => e.payload as { task_id?: string; seat?: string; task?: string; at?: string })
      .filter((p) => p.task_id && !resolved.has(p.task_id));
  }, [events]);

  const backlog = useMemo(() => (desk?.runs ?? []).flatMap((run) =>
    (run.recommendations ?? [])
      .filter((r) => r.status === "accepted"
                     && ["fix", "harness", "envelope_v2", "infra", "code_fix",
                         "measurement", "dispatch"].includes(r.kind ?? ""))
      .map((r) => ({ ...r, run_id: run.run_id }))), [desk]);

  const weekCost = useMemo(() => {
    const cutoff = Date.now() - 7 * 86400_000;
    let usd = 0, tokens = 0, priced = 0, runs = 0;
    for (const run of desk?.runs ?? []) {
      const at = run.resolved_at ? Date.parse(run.resolved_at) : NaN;
      if (Number.isNaN(at) || at < cutoff) continue;
      runs += 1;
      if (run.tokens != null) tokens += run.tokens;
      const c = estimateCostUsd(run.model, run.tokens);
      if (c != null) { usd += c; priced += 1; }
    }
    return { usd, tokens, priced, runs };
  }, [desk]);

  return (
    <div className="min-h-screen bg-[var(--kt-bg)] text-[var(--kt-text)]">
      <StudioHeader subtitle="The CTO's desk — the build and dispatch queue, and what the bench costs" />
      <div className={KT.container}>
        <header className="mb-7 flex items-center gap-4">
          <SeatFace actor="cto" size={64} />
          <div>
            <p className={KT.label}>Krypton Fund · the console</p>
            <h1 className="text-2xl font-medium tracking-tight">Fable · CTO</h1>
            <p className={`mt-0.5 text-xs ${KT.muted}`}>
              {/* "0 runs · $— est." folded from an unread desk claims a week in
                  which the bench cost nothing. Say unknown instead. */}
              {desk === null ? (
                <span className={KT.sev.warn}>
                  bench economics unreadable — the week&apos;s cost is unknown, not zero
                </span>
              ) : (
                <>
                  bench, last 7 days: {weekCost.runs} runs ·{" "}
                  <span className="font-mono tabular-nums">
                    {weekCost.tokens ? `${Math.round(weekCost.tokens / 1000)}k tokens` : "no tokens recorded"}
                  </span>{" "}
                  · {fmtUsd(weekCost.priced ? weekCost.usd : null)} est.
                  ({weekCost.priced} of {weekCost.runs} runs priced)
                </>
              )}
              {" "}· <Link href="/clark/studio/desk" className={`${KT.accent} hover:underline`}>back to the floor</Link>
            </p>
          </div>
        </header>

        {err && (
          <div className={`${KT.card} mb-6 flex items-start gap-2 border-[var(--kt-warn)]`}>
            <AlertTriangle size={15} className="mt-0.5 text-[var(--kt-warn)]" />
            <p className="text-sm">The desk could not be read — the queue is unknown, not empty. {err}</p>
          </div>
        )}

        <section className="mb-8">
          <p className={`${KT.label} mb-2`}>
            The dispatch queue ({desk === null ? "unknown" : queue.length})
          </p>
          {/* The summary line is a CLAIM ABOUT THE QUEUE'S COMPOSITION. Made
              from an unread desk it asserted "every open ask was filed by a
              human" about asks nobody had loaded — the loudest instance of the
              absence-as-value error on this page. Caught on the dead-spine
              pass, 2026-08-20. */}
          {desk === null ? (
            <p className={`mb-2 text-sm ${KT.sev.warn}`}>
              The queue could not be read. How many asks are open, who filed them, and
              whether any are cleared to fire are all unknown — not none.
            </p>
          ) : (
            <>
              <p className={`mb-2 text-xs leading-relaxed ${KT.muted}`}>
                {cleared > 0
                  ? `${cleared} cleared by the CEO and waiting on your trigger; `
                  : "Nothing is cleared to fire; "}
                {seatFiled > 0
                  ? `${seatFiled} filed by a bench seat rather than a human — a seat-filed ask is an ASK, never a trigger.`
                  : "every open ask was filed by a human."}
              </p>
              {queue.length === 0 && (
                <p className={`text-sm ${KT.muted}`}>Empty — every filed ask has been triggered and resolved.</p>
              )}
            </>
          )}
          <div className="space-y-1.5">
            {queue.map((a) => <AskRow key={a.requestId} a={a} />)}
          </div>
        </section>

        <section className="mb-8">
          <p className={`${KT.label} mb-2`}>Dispatched, not yet resolved</p>
          {unresolvedDispatches === null ? (
            <p className={`text-sm ${KT.sev.warn}`}>Event log unreadable — in-flight work is unknown, not none.</p>
          ) : unresolvedDispatches.length === 0 ? (
            <p className={`text-sm ${KT.muted}`}>Nothing in flight — every dispatch has been resolved.</p>
          ) : (
            <div className="space-y-1.5">
              {unresolvedDispatches.map((p) => (
                <div key={p.task_id} className={`${KT.card} flex flex-wrap items-baseline gap-x-3 gap-y-1 p-3 text-sm`}>
                  <span className="flex shrink-0 items-center gap-1.5 font-mono text-[11px] text-[var(--kt-accent)]">
                    <SeatFace actor={p.seat} size={16} decorative /> {p.seat}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-[13px]">{p.task}</span>
                  {p.at && <span className={`font-mono text-[10px] ${KT.muted}`}>{fmtAt(p.at)}</span>}
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="mb-8">
          <p className={`${KT.label} mb-2`}>
            Accepted, not yet built ({desk === null ? "unknown" : backlog.length})
          </p>
          <p className={`mb-2 text-xs ${KT.muted}`}>
            CEO-accepted recommendations of buildable kinds — the CTO&apos;s backlog,
            straight from the flight recorder.
          </p>
          {desk === null ? (
            <p className={`text-sm ${KT.sev.warn}`}>
              The flight recorder could not be read — the backlog is unknown, not clear.
            </p>
          ) : backlog.length === 0 ? (
            <p className={`text-sm ${KT.muted}`}>Empty — everything accepted has been implemented.</p>
          ) : null}
          <div className="space-y-1.5">
            {backlog.map((r) => (
              <div key={`${r.run_id}-${r.rec_id}`} className={`${KT.card} flex flex-wrap items-baseline gap-x-3 gap-y-1 p-3 text-sm`}>
                <span className="flex shrink-0 items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--kt-agent)]">
                  <SeatFace actor={r.seat} size={14} decorative /> {r.seat} · rec {r.rec_id}
                </span>
                <span className="min-w-0 flex-1 text-[13px] leading-snug">{r.text}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

/**
 * One queued ask: who filed it, who it serves, where it sits, how long it has
 * waited.
 *
 * The filer's face is drawn from the same registry as everywhere else, so a
 * seat-filed ask is recognisable at a glance without reading the name — and an
 * actor with NO face on file draws the dashed "unknown" head rather than
 * borrowing someone's. `faceFor` is exact-match by design: the live log carries
 * `actor` strings that are whole sentences, and a prefix match would hand one
 * of those a colleague's portrait.
 */
function AskRow({ a }: { a: QueuedAsk }) {
  const cleared = a.stage === "cleared_to_trigger";
  const face = faceFor(a.actor);
  const ageHours = a.at ? (Date.now() - Date.parse(a.at)) / 3_600_000 : null;
  return (
    <div className={`${KT.card} p-3 text-sm ${cleared ? "border-[var(--kt-accent-border)]" : ""}`}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <span className="flex shrink-0 items-center gap-1.5 font-mono text-[11px]">
          <SeatFace actor={a.actor} size={18} decorative />
          {face?.label ?? (a.actor || "unattributed")}
          {/* The constitutional distinction, on the row. A seat asking for
              another seat is the org chart gaining an edge; it must not look
              identical to the CEO typing the same words. */}
          {a.seatFiled && (
            <span className={`rounded-full border border-[var(--kt-border)] px-1.5 text-[9px] uppercase tracking-[0.1em] ${KT.muted}`}>
              seat-filed
            </span>
          )}
        </span>
        <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>asks</span>
        <span className="flex shrink-0 items-center gap-1.5 font-mono text-[11px]">
          <SeatFace actor={a.serves} size={18} decorative />
          {isSeat(a.serves)
            ? <Link href={`/clark/studio/desk/${a.serves}`} className={`${KT.accent} hover:underline`}>{a.serves}</Link>
            : a.serves}
        </span>
        <span className="min-w-0 flex-1 text-[13px] leading-snug">{a.subject}</span>
        {cleared ? (
          <span className="shrink-0 rounded-full border border-[var(--kt-accent-border)] bg-[var(--kt-accent-bg)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--kt-accent)]">
            CEO-approved — trigger it
          </span>
        ) : (
          <span className={`shrink-0 font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
            awaiting CEO approval
          </span>
        )}
      </div>
      <p className={`mt-1 flex flex-wrap gap-x-3 font-mono text-[10px] ${KT.muted}`}>
        <span>
          {a.at
            ? `filed ${fmtAt(a.at)}${ageHours != null ? ` · ${ageHours < 24 ? `${ageHours.toFixed(1)}h` : `${(ageHours / 24).toFixed(1)}d`} ago` : ""}`
            : "undated — the request carries no timestamp"}
        </span>
        {cleared && (
          <span className="text-[var(--kt-accent)]">
            approved by {a.approvedBy ?? "an unrecorded actor"}
            {a.approvedAt ? ` ${fmtAt(a.approvedAt)}` : ""}
          </span>
        )}
        <span className="font-mono">{a.requestId.slice(0, 8)}</span>
      </p>
      {a.note && <p className={`mt-1 text-xs ${KT.muted}`}>{a.note}</p>}
    </div>
  );
}
