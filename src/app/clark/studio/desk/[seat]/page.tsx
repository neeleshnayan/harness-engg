"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { notFound, useParams } from "next/navigation";
import { AlertTriangle, ArrowLeft, Send } from "lucide-react";
import { fundApiClient, DeskView, SpineEvent } from "@/lib/fund_api";
import { KT } from "../../theme";
import { StudioNav } from "../../components/StudioNav";
import { RiskBar } from "../../components/RiskBar";
import {
  Metric, RecRow, RunRow, SectionHead, TraceFlow, WindowNote,
} from "../components";
import { LaneTrackRecord } from "../laneViews";
import {
  ASSUMED_INPUT_SHARE,
  DeskRun,
  PRICE_TABLE,
  SEAT_PLACEMENT,
  SEAT_REQUEST_KIND,
  SeatId,
  dispatchStats,
  fmtAt,
  fmtTokens,
  fmtUsd,
  isSeat,
  tokenStats,
  traceThreads,
} from "../seatLib";

/**
 * One page per seat — the CEO's working surface WITH that agent.
 *
 * Not a dashboard about an agent. The layout mirrors the loop, top to bottom,
 * because that is the order the work actually happens in:
 *
 *   1. THE SEAT'S ASKS OF YOU — its open recommendations, decidable in place.
 *      What needs the human comes first, always.
 *   2. YOUR ASK OF THE SEAT — the request composer, pre-filled with this seat's
 *      kind, so "ask the pm to re-review" is one field and one click.
 *   3. THE EVIDENCE — runs with their reasoning, artifacts, and the chatter
 *      threads that replay a chain. Why the seat believes what it asks.
 *   4. THE TRACK RECORD — the lane-native measure. Whether to keep trusting it.
 *
 * So the page reads: decide -> ask -> inspect -> calibrate trust. The decision
 * controls sit next to the evidence that justifies them, never on another tab.
 *
 * Everything is read from the spine. A seat that has never been dispatched says
 * so — "an idle seat costs zero and that is a feature" — rather than rendering
 * a metrics strip of zeros, which would read as a seat that worked and produced
 * nothing.
 */

export default function SeatPage() {
  const params = useParams<{ seat: string }>();
  const raw = typeof params?.seat === "string" ? params.seat : "";
  if (!isSeat(raw)) notFound();
  return <Seat seat={raw as SeatId} />;
}

function Seat({ seat }: { seat: SeatId }) {
  const [desk, setDesk] = useState<DeskView | null>(null);
  const [runs, setRuns] = useState<DeskRun[] | null>(null);
  const [events, setEvents] = useState<SpineEvent[] | null>(null);
  const [deskErr, setDeskErr] = useState<string | null>(null);
  const [runsErr, setRunsErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    // Three independent reads, three independent failures. A page that hides
    // its runs because the event log timed out would be reporting an absence it
    // did not measure.
    const [d, r, e] = await Promise.allSettled([
      fundApiClient.getDesk(),
      fundApiClient.getDeskRuns(seat, 200),
      fundApiClient.getEvents(1000, 0),
    ]);
    if (d.status === "fulfilled") { setDesk(d.value); setDeskErr(null); }
    else setDeskErr(d.reason instanceof Error ? d.reason.message : "unreachable");
    if (r.status === "fulfilled") { setRuns(r.value.runs || []); setRunsErr(null); }
    else setRunsErr(r.reason instanceof Error ? r.reason.message : "unreachable");
    if (e.status === "fulfilled") setEvents(e.value.events || []);
    else setEvents(null);
  }, [seat]);

  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [load]);

  const roster = desk?.roster?.find((r) => r.agent === seat) ?? null;
  const seatRuns = runs ?? [];
  const stats = useMemo(() => tokenStats(seatRuns), [seatRuns]);
  const dispatches = useMemo(
    () => dispatchStats(events ?? [], seat), [events, seat],
  );
  const threads = useMemo(
    () => traceThreads((events ?? []).filter((ev) => {
      const p = (ev.payload || {}) as Record<string, unknown>;
      return p.seat === seat || p.serves === seat;
    }), seatRuns),
    [events, seatRuns, seat],
  );
  const openRecs = (desk?.open_recommendations ?? []).filter((r) => r.seat === seat);
  const observedModels = Array.from(
    new Set(seatRuns.map((r) => r.model).filter((m): m is string => !!m)),
  );

  const neverDispatched = runs != null && seatRuns.length === 0 && !dispatches.dispatches;

  return (
    <>
      <RiskBar />
      <div className={KT.container}>
        <header className="mb-7 flex flex-wrap items-start justify-between gap-3">
          <div>
            <Link href="/clark/studio/desk"
                  className={`flex items-center gap-1.5 text-xs ${KT.muted} hover:text-[var(--kt-text)]`}>
              <ArrowLeft size={12} /> the office
            </Link>
            <h1 className="mt-1 flex items-center gap-3 text-2xl font-medium tracking-tight">
              <span className="font-mono text-[var(--kt-accent)]">{seat}</span>
              <SeatStatus roster={roster} />
            </h1>
            <p className="mt-1 max-w-2xl text-sm leading-relaxed">
              {roster?.lane ?? (deskErr
                ? "Lane unreadable — the spine is unreachable, so the roster it defines cannot be shown."
                : "…")}
            </p>
            {roster && (
              <p className={`mt-1 text-xs ${KT.muted}`}>
                emits: {roster.emits}
              </p>
            )}
          </div>
          <StudioNav />
        </header>

        {(deskErr || runsErr) && (
          <div className={`${KT.card} mb-6 flex items-start gap-2 border-[var(--kt-warn)]`}>
            <AlertTriangle size={15} className="mt-0.5 text-[var(--kt-warn)]" />
            <div className="text-sm">
              <p>Part of this page could not be read — what is missing is missing, not empty.</p>
              <p className={`mt-1 text-xs ${KT.muted}`}>
                {deskErr && <>desk: {deskErr}. </>}
                {runsErr && <>runs: {runsErr}.</>}
              </p>
            </div>
          </div>
        )}

        {/* ---------------------------------------------- dispatch economics -- */}
        <section className="mb-8">
          <div className={`${KT.card} flex flex-wrap gap-x-10 gap-y-4`}>
            <Metric
              label="dispatches"
              value={dispatches.dispatches ?? "never"}
              sub={events == null
                ? "event log unreadable"
                : dispatches.lastAt
                  ? `last ${fmtAt(dispatches.lastAt)}${dispatches.actors.length ? ` by ${dispatches.actors.join(", ")}` : ""}`
                  : "no dispatch event on record"}
            />
            <Metric
              label="runs recorded"
              value={runs == null ? "—" : seatRuns.length}
              sub={runs == null ? "flight recorder unreadable" : "rows in the flight recorder"}
            />
            <Metric
              label="tokens / dispatch"
              value={stats.avg == null ? "—" : fmtTokens(Math.round(stats.avg))}
              sub={stats.reported === 0
                ? "no run recorded a token total"
                : `${fmtTokens(stats.min)}–${fmtTokens(stats.max)} · ${stats.reported} of ${stats.runs} runs reported`}
            />
            <Metric
              label="tokens total"
              value={stats.total == null ? "—" : fmtTokens(stats.total)}
            />
            <Metric
              label="cost (estimate)"
              value={stats.costUsd == null ? "—" : fmtUsd(stats.costUsd)}
              sub={stats.costUsd == null
                ? "no run could be priced"
                : `${stats.priced} of ${stats.runs} runs priced`}
            />
          </div>
          <PriceTable />
          <p className={`mt-2 text-xs ${KT.muted}`}>
            Placement, declared: <span className="font-mono">{SEAT_PLACEMENT[seat]}</span>
            {" · "}observed on runs:{" "}
            <span className="font-mono">
              {observedModels.length ? observedModels.join(", ") : "none recorded"}
            </span>
            . The declaration comes from the constitution; the observation comes
            from <span className="font-mono">run.model</span>. When they disagree,
            that gap is the finding — two early dispatches ran on the wrong model
            for exactly this reason.
          </p>
        </section>

        {neverDispatched ? (
          <section className={`${KT.card} mb-8`}>
            <p className={`${KT.label} mb-2`}>Never dispatched</p>
            <p className="text-sm leading-relaxed">
              This seat has no runs and no dispatch events in the window read. An
              idle seat costs zero and that is a feature — it is not a seat that
              worked and produced nothing.
            </p>
          </section>
        ) : null}

        {/* ------------------------------------------------- 1. the seat asks -- */}
        <section className="mb-8">
          <SectionHead
            title="What this seat is asking of you"
            lede="Its open recommendations, decidable here. Accepting records the decision on the event log; it stages nothing and moves no money."
          />
          {openRecs.length === 0 ? (
            <p className={`text-sm ${KT.muted}`}>
              {desk
                ? "Nothing awaiting your decision from this seat."
                : "The desk is unreadable, so whether this seat is waiting on you is unknown."}
            </p>
          ) : (
            <div className="space-y-1.5">
              {openRecs.map((r) => (
                <RecRow key={`${r.run_id}-${r.rec_id}`} r={r} onDecide={load} />
              ))}
            </div>
          )}
        </section>

        {/* -------------------------------------------------- 2. you ask it --- */}
        <AskSeat seat={seat} onSent={load} executionNote={desk?.execution_note} />

        {/* --------------------------------------------------- 3. the evidence */}
        <section className="mb-8">
          <SectionHead
            title="The evidence"
            lede="Every dispatch stored whole in Postgres. Open a run for the distilled why; the full record lives at the artifact path."
          />
          {runs == null ? (
            <p className={`text-sm ${KT.muted}`}>Reading the flight recorder…</p>
          ) : seatRuns.length === 0 ? (
            <p className={`text-sm ${KT.muted}`}>No runs recorded for this seat.</p>
          ) : (
            <div className="space-y-1">
              {seatRuns.map((r) => (
                <RunRow key={r.run_id} run={r} showSeat={false} />
              ))}
            </div>
          )}
        </section>

        {threads.length > 0 && (
          <section className="mb-8">
            <SectionHead
              title="Chatter threads"
              lede="One trace id replays a chain: the ask, the dispatch, the run and its verdict, then the decisions. Threads here are filtered to this seat."
            />
            <div className="space-y-2">
              {threads.slice(0, 8).map((t) => (
                <TraceFlow key={t.traceId} t={t} dense />
              ))}
            </div>
            {events != null && (
              <WindowNote events={events.length} capped={events.length >= 1000} />
            )}
          </section>
        )}

        {/* ------------------------------------------------ 4. track record --- */}
        <LaneTrackRecord seat={seat} runs={seatRuns} desk={desk} events={events ?? []} />
      </div>
    </>
  );
}

/* ---------------------------------------------------------------- pieces -- */

function SeatStatus({ roster }: { roster: DeskView["roster"][number] | null }) {
  if (!roster) return null;
  const a = roster.activity;
  return (
    <span
      className={`flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.1em] ${
        a.status === "working" ? "text-[var(--kt-warn)]" : KT.muted
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${
        a.status === "working" ? "animate-pulse bg-[var(--kt-warn)]" : "bg-[var(--kt-border-strong)]"
      }`} />
      {a.status}
      {a.status === "working" && a.since && <> since {fmtAt(a.since)}</>}
      {a.status === "idle" && a.last_delivered && (
        <> · last delivered {a.last_delivered.artifact}</>
      )}
    </span>
  );
}

/** The composer, pre-filled with this seat's request kind. The kind field is
 *  fixed rather than a dropdown: on a seat's own page, asking a different seat
 *  for work is a navigation, not a form field. */
function AskSeat({ seat, onSent, executionNote }: {
  seat: SeatId;
  onSent: () => Promise<void> | void;
  executionNote?: string;
}) {
  const kind = SEAT_REQUEST_KIND[seat];
  const [subject, setSubject] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState<string | null>(null);

  const submit = async () => {
    if (!subject.trim() || busy) return;
    setBusy(true);
    setSent(null);
    try {
      await fundApiClient.postDeskRequest({ kind, subject: subject.trim(), note });
      setSent("Recorded to the event log. The CTO session picks it up from here.");
      setSubject("");
      setNote("");
      await onSent();
    } catch (e) {
      setSent(`Failed: ${e instanceof Error ? e.message : "unreachable"}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className={`${KT.card} mb-8 border-[var(--kt-accent-border)]`}>
      <p className={`${KT.label} mb-3`}>Ask {seat} for work</p>
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
            kind
          </span>
          <span className={`${KT.inset} px-3 py-2 font-mono text-sm`}>{kind}</span>
        </div>
        <label className="flex min-w-[16rem] flex-1 flex-col gap-1">
          <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
            subject
          </span>
          <input
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder={`what to ask ${seat} for`}
            className={KT.input}
          />
        </label>
        <label className="flex min-w-[14rem] flex-1 flex-col gap-1">
          <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
            note (optional)
          </span>
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="context, constraints, what would make it wrong"
            className={KT.input}
          />
        </label>
        <button
          type="button"
          onClick={submit}
          disabled={busy || !subject.trim()}
          className={`${KT.btn} flex items-center gap-1.5 disabled:opacity-40`}
        >
          <Send size={13} /> {busy ? "Recording…" : "Record request"}
        </button>
      </div>
      {sent && <p className={`mt-2 text-xs ${KT.muted}`}>{sent}</p>}
      {executionNote && (
        <p className={`mt-3 text-xs italic leading-relaxed ${KT.muted}`}>{executionNote}</p>
      )}
    </section>
  );
}

/** The price table, on the page, beside the only figure derived from it.
 *
 * The constitution forbids a hardcoded financial number; a cost estimate is
 * allowed only when it is computed from measured tokens AND the reader can see
 * the prices it was computed with. So they are here, collapsed by default and
 * one click from any dollar figure on the page. */
function PriceTable() {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2">
      <button type="button" onClick={() => setOpen((v) => !v)}
              className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted} hover:text-[var(--kt-text)]`}>
        {open ? "− " : "+ "}how the cost estimate is computed
      </button>
      {open && (
        <div className={`${KT.inset} mt-2 p-3 text-xs leading-relaxed`}>
          <p className={KT.muted}>
            The flight recorder stores a token TOTAL, not an input/output split, so
            every dollar figure on this page is a blend ESTIMATE:{" "}
            {Math.round(ASSUMED_INPUT_SHARE * 100)}% input /{" "}
            {Math.round((1 - ASSUMED_INPUT_SHARE) * 100)}% output, the same split the
            fund&apos;s cost model uses for its working number. A run whose model is
            not in this table produces no figure at all rather than a default-priced one.
          </p>
          <table className="mt-2 w-full max-w-md text-left font-mono text-[11px] tabular-nums">
            <thead className={KT.muted}>
              <tr>
                <th className="py-1 font-normal">model</th>
                <th className="py-1 font-normal">$/MTok in</th>
                <th className="py-1 font-normal">$/MTok out</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(PRICE_TABLE).map(([k, p]) => (
                <tr key={k} className="border-t border-[var(--kt-border)]">
                  <td className="py-1">{k}</td>
                  <td className="py-1">{p.inPerMTok.toFixed(2)}</td>
                  <td className="py-1">{p.outPerMTok.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className={`mt-2 ${KT.muted}`}>
            Source: ClarkHarness/docs/COST_MODEL_2026-08-20.md — Anthropic
            first-party list prices checked 2026-08-20. Local inference on the
            4090 is a measured zero: no API call is made. Prices move; this table
            is a dated claim, not a live feed.
          </p>
        </div>
      )}
    </div>
  );
}
