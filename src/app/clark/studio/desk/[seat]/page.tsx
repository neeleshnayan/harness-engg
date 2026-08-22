"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { notFound, useParams } from "next/navigation";
import { AlertTriangle, ArrowLeft, Send } from "lucide-react";
import { fundApiClient, DeskView, SpineEvent } from "@/lib/fund_api";
import { KT } from "../../theme";
import { StudioHeader } from "../../components/StudioHeader";
import {
  Metric, ProductionShelf, RecRow, RunRow, SectionHead, WindowNote,
} from "../components";
import { MemoThread } from "../MemoThread";
import { SeatFace } from "../SeatFace";
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
  productionShelf,
  tokenStats,
  traceThreads,
  seatStatusLabel,
  seatStatusTone,
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
 *   3. THE PRODUCTION SHELF — what this desk has produced, across time, as memo
 *      spines. The CEO's question ("what is each desk producing?") answered
 *      before the machinery of how it produced it.
 *   4. THE EVIDENCE — runs with their reasoning, and the memo threads that
 *      replay a chain. Why the seat believes what it asks.
 *   5. THE TRACK RECORD — the lane-native measure. Whether to keep trusting it.
 *
 * So the page reads: decide -> ask -> see the output -> inspect -> calibrate
 * trust. The decision controls sit next to the evidence that justifies them,
 * never on another tab.
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
  // Memoised: `?? []` is a fresh array each render, and the folds below key off it.
  const seatRuns = useMemo(() => runs ?? [], [runs]);
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
  /* Two queues, not one (CDO D4). `/fund/desk` returns open, accepted AND
     staged recommendations under one key, so "what this seat is asking of you"
     was listing things the CEO had already decided — and a seat whose every ask
     had been accepted looked exactly as demanding as one whose asks were all
     untouched. */
  const seatRecs = (desk?.open_recommendations ?? []).filter((r) => r.seat === seat);
  const openRecs = seatRecs.filter((r) => r.status === "open");
  const decidedRecs = seatRecs.filter((r) => r.status !== "open");
  const observedModels = Array.from(
    new Set(seatRuns.map((r) => r.model).filter((m): m is string => !!m)),
  );

  // "Never dispatched" needs BOTH records read. With the event log unreadable
  // it was asserted from the flight recorder alone, which cannot see a
  // dispatch that produced no run.
  const neverDispatched =
    runs != null && events != null && seatRuns.length === 0 && !dispatches.dispatches;
  // What this desk produced, across time. Run-anchored (see productionShelf):
  // the spine has no author field, so a shelf built any other way would credit
  // the wrong desk.
  const shelf = useMemo(
    () => productionShelf(seatRuns, desk?.artifacts ?? []),
    [seatRuns, desk],
  );

  return (
    <div className="min-h-screen bg-[var(--kt-bg)] text-[var(--kt-text)]">
      {/* the ONE Studio shell — theme, nav, risk bar; forking it is how the
          desk pages ended up in a different mode from the rest of the Studio */}
      <StudioHeader subtitle="A seat's office — decide, ask, inspect, calibrate trust" />
      <div className={KT.container}>
        <header className="mb-7 flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
          <div className="min-w-0 flex-1">
            <Link href="/clark/studio/desk"
                  className={`flex items-center gap-1.5 text-xs ${KT.muted} hover:text-[var(--kt-text)]`}>
              <ArrowLeft size={12} /> the floor
            </Link>
            {/* The seat's face at desk scale — the same drawing it wears on the
                floor, on every memo card and on its recommendation chips. It is
                the largest thing on the page because walking into a colleague's
                office should feel like meeting them. */}
            <div className="mt-2 flex items-start gap-4">
              {/* Not decorative here: this is the one place the face is the
                  subject rather than a marker, so it carries its own name and
                  role for assistive tech and on hover. */}
              <span className="text-[var(--kt-text-dim)]">
                <SeatFace actor={seat} size={64} />
              </span>
              <div className="min-w-0">
                <h1 className="flex flex-wrap items-center gap-3 text-2xl font-medium tracking-tight">
                  <span className="font-mono text-[var(--kt-text-strong)]">{seat}</span>
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
                {/* The face's own `role` string is NOT rendered here: the lane
                    above is the spine's, and a second sentence saying nearly
                    the same thing is a second thing to drift. It lives only in
                    the face's tooltip, where nothing else is competing. */}
                <LastDelivered roster={roster} />
              </div>
            </div>
          </div>
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
            {/* "never" is a CLAIM about the record, so it may only be made
                when the record was actually read. With the event log
                unreadable this used to read "never" over a caption saying the
                log could not be read — the headline asserting the opposite of
                its own footnote. Verified 2026-08-20 against a dead spine. */}
            <Metric
              label="dispatches"
              value={events == null ? "—" : dispatches.dispatches ?? "never"}
              sub={events == null
                ? "event log unreadable — dispatches unknown, not zero"
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
            title={`What this seat is asking of you${desk ? ` (${openRecs.length})` : ""}`}
            lede="Its UNDECIDED recommendations, decidable here. Accepting records the decision on the event log; it stages nothing and moves no money."
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
          {decidedRecs.length > 0 && (
            <div className="mt-4">
              <p className={`${KT.label} mb-2`}>
                Decided, awaiting execution ({decidedRecs.length})
              </p>
              <p className={`mb-2 text-xs ${KT.muted}`}>
                Already decided — listed so a decision cannot go quiet, and NOT counted
                above, because nothing here is waiting on you.
              </p>
              <div className="space-y-1.5">
                {decidedRecs.map((r) => (
                  <RecRow key={`${r.run_id}-${r.rec_id}`} r={r} onDecide={load} />
                ))}
              </div>
            </div>
          )}
        </section>

        {/* -------------------------------------------------- 2. you ask it --- */}
        <AskSeat seat={seat} onSent={load} executionNote={desk?.execution_note} />

        {/* ------------------------------------------ 3. the production shelf */}
        <section className="mb-8">
          <SectionHead
            title="What this desk has produced"
            lede="Every delivery in time order, newest first — the date, the document, the verdict where one was stamped. A run that filed nothing appears saying so."
          />
          {/* Three states, kept apart: still loading, could not be read, and
              read-and-empty. "Reading…" for a read that already FAILED is a
              progress bar for something that is not in progress. */}
          {runsErr ? (
            <p className={`text-sm ${KT.sev.warn}`}>
              The flight recorder could not be read ({runsErr}) — what this desk
              produced is unknown, not nothing.
            </p>
          ) : runs == null ? (
            <p className={`text-sm ${KT.muted}`}>Reading the flight recorder…</p>
          ) : (
            <ProductionShelf
              items={shelf}
              emptyNote="Nothing filed. This desk has no runs in the flight recorder — which is an absence of dispatches, not an absence of output."
            />
          )}
          {desk == null && runs != null && seatRuns.length > 0 && (
            <p className={`mt-2 text-[11px] ${KT.sev.warn}`}>
              The artifact fold could not be read, so these spines carry the
              run&apos;s task rather than the document&apos;s own title, and no
              status rule.
            </p>
          )}
        </section>

        {/* --------------------------------- 3b. Donna's archive shelf ------
            The secretary's output is not only a run record — it is a DATED
            FILE, one per day, and the run's own shelf spine cannot show which
            days exist or which of them rendered a PDF. Only her desk carries
            this, because only she files into docs/archives/. */}
        {seat === "secretary" && <ArchiveShelf />}

        {/* --------------------------------------------------- 4. the evidence */}
        <section className="mb-8">
          <SectionHead
            title="The evidence"
            lede="Every dispatch stored whole in Postgres. Open a run for the distilled why; the full record lives at the artifact path."
          />
          {runsErr ? (
            <p className={`text-sm ${KT.sev.warn}`}>
              The flight recorder could not be read ({runsErr}) — this seat&apos;s
              runs are unknown, not absent.
            </p>
          ) : runs == null ? (
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
              title="Memo threads"
              lede="One trace id replays a chain, memo by memo: the ask, the dispatch, the delivery and its verdict, then the decisions. Threads here are filtered to this seat."
            />
            <div className="space-y-3">
              {threads.slice(0, 8).map((t) => (
                <MemoThread key={t.traceId} t={t} dense />
              ))}
            </div>
            {events != null && (
              <WindowNote events={events.length} capped={events.length >= 1000} />
            )}
          </section>
        )}

        {/* ------------------------------------------------ 5. track record --- */}
        <LaneTrackRecord seat={seat} runs={seatRuns} desk={desk} events={events ?? []} />
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- pieces -- */

/** The status word beside the seat's name.
 *
 * Only the WORD is set in tracked uppercase; what was last delivered is a
 * separate, sentence-cased line. It used to be concatenated into the same
 * letterspaced run, which turned an artifact path into 90 characters of
 * uppercase mono shouting across the header and buried the one word — working
 * or idle — the reader came for. */
function SeatStatus({ roster }: { roster: DeskView["roster"][number] | null }) {
  if (!roster) return null;
  const a = roster.activity;
  const tone = seatStatusTone(a.status);
  return (
    <span
      className={`flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.1em] ${
        tone === "working" ? "text-[var(--kt-warn)]"
          : tone === "awaiting" ? "text-[var(--kt-text-strong)]" : KT.muted
      }`}
    >
      {/* kt-breathe, not animate-pulse: the Tailwind utility ignores
          prefers-reduced-motion, so a reader who asked the OS for no animation
          got one anyway. The class drops the motion and keeps the marker.
          AWAITING REVIEW is a hollow ring and does NOT breathe: nothing is
          happening at that desk — the obligation has moved to the chair. */}
      <span className={`h-1.5 w-1.5 rounded-full ${
        tone === "working" ? "kt-breathe bg-[var(--kt-warn)]"
          : tone === "awaiting" ? "border border-[var(--kt-text-strong)]"
          : "bg-[var(--kt-border-strong)]"
      }`} />
      {seatStatusLabel(a.status)}
      {tone === "working" && a.since && <> since {fmtAt(a.since)}</>}
      {tone === "awaiting" && a.since && <> since {fmtAt(a.since)}</>}
    </span>
  );
}

/** What the seat last filed, in its own words — one quiet line under the lane,
 *  not a suffix on the status chip. */
function LastDelivered({ roster }: { roster: DeskView["roster"][number] | null }) {
  const d = roster?.activity.last_delivered;
  if (!d) return null;
  return (
    <p className={`mt-1 line-clamp-2 text-xs ${KT.muted}`} title={d.artifact}>
      last delivered <span className="text-[var(--kt-text-dim)]">{d.task}</span>
      {d.at ? <span className="font-mono text-[10px]"> · {d.at.slice(0, 10)}</span> : null}
    </p>
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

  // A SEAT THE DESK QUEUE CANNOT ROUTE TO GETS A SENTENCE, NOT A FORM.
  // `SEAT_REQUEST_KIND` mirrors the spine's REQUEST_KINDS, and an empty entry
  // means the spine has no kind that reaches this seat (the cfo, 2026-08-22).
  // Rendering the composer anyway would draw a control whose only possible
  // outcome is a 422 — a button with no caller, dressed as a working one.
  if (!kind) {
    return (
      <section className={`${KT.card} mb-8`}>
        <p className={`${KT.label} mb-2`}>Asking {seat} for work is not wired yet</p>
        <p className={`text-sm ${KT.body}`}>
          The desk queue has no request kind that routes to this seat, so there
          is nothing this form could post — the spine would reject it. The seat
          is dispatched by the chair directly today. Filing a request here becomes
          possible when <code className="font-mono">REQUEST_KINDS</code> in{" "}
          <code className="font-mono">app/fund/desk.py</code> gains an entry for{" "}
          <span className="font-mono">{seat}</span>; until it does, this seat also
          reports no runs-today at all, because the per-seat telemetry enumerates
          that same map.
        </p>
        {executionNote && (
          <p className={`mt-3 text-xs italic leading-relaxed ${KT.muted}`}>{executionNote}</p>
        )}
      </section>
    );
  }

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

/**
 * Every Daily Donna has filed, newest first.
 *
 * Brief Part B: "her seat page lists every archived Daily over time ... serve
 * via a small spine endpoint — the UI must not read the filesystem". So this
 * reads `GET /fund/desk/archives`; the spine owns what is on disk.
 *
 * FOUR STATES, and they are four different facts. A shelf that rendered
 * "no dailies" for a permissions error would be a missing record showing up as
 * a clean one — which is the same class as an unread desk rendering an empty
 * section, caught on this page's own dead-spine pass in August.
 */
function ArchiveShelf() {
  const [got, setGot] = useState<
    Awaited<ReturnType<typeof fundApiClient.getDeskArchives>> | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    fundApiClient.getDeskArchives()
      .then((d) => { if (alive) { setGot(d); setErr(null); } })
      .catch((e: unknown) => {
        if (alive) setErr(e instanceof Error ? e.message : "unreachable");
      });
    return () => { alive = false; };
  }, []);

  const rows = got?.archives ?? [];
  return (
    <section className="mb-8">
      <SectionHead
        title="The archive — every day on file"
        lede="One dated record per day, filed to docs/archives/. The short memo is the CEO's sixty-second read; this is the long record behind it."
      />
      {err ? (
        <p className={`text-sm ${KT.sev.warn}`}>
          The archive could not be read ({err}) — what has been filed is unknown,
          not nothing.
        </p>
      ) : got === null ? (
        <p className={`text-sm ${KT.muted}`}>Reading the archive…</p>
      ) : got.readable === false ? (
        <p className={`text-sm ${KT.sev.warn}`}>
          {got.note ?? "docs/archives/ could not be read — UNKNOWN, not none."}
        </p>
      ) : got.exists === false ? (
        <p className={`text-sm ${KT.muted}`}>
          {got.note ?? "docs/archives/ does not exist — she has never filed."}
        </p>
      ) : rows.length === 0 ? (
        <p className={`text-sm ${KT.muted}`}>
          {got.note ?? "Nothing filed yet."}
        </p>
      ) : (
        <>
          <ul className="divide-y divide-[var(--kt-border)]">
            {rows.map((a) => (
              <li key={a.path}
                  className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-2 text-[12px]">
                <span className={`w-24 font-mono tabular-nums ${
                  a.date ? "" : KT.sev.warn}`}>
                  {a.date ?? "undated"}
                </span>
                <span className="min-w-0 flex-1 truncate">{a.title}</span>
                <span className={`font-mono text-[10px] ${KT.muted}`}>
                  {a.bytes == null ? "size unknown" : `${Math.round(a.bytes / 1024)}k`}
                </span>
                {/* The PDF is a RENDER of the markdown, so its absence is
                    normal rather than a fault — a day filed before that step
                    existed has only the first. Said, not blanked. */}
                <span className={`w-16 text-right font-mono text-[10px] ${KT.muted}`}>
                  {a.pdf_path ? "md · pdf" : "md only"}
                </span>
                {a.note && (
                  <span className={`w-full text-[11px] ${KT.sev.warn}`}>{a.note}</span>
                )}
                <span className={`w-full font-mono text-[10px] ${KT.muted}`}>
                  {a.path}
                </span>
              </li>
            ))}
          </ul>
          <p className={`mt-2 text-[11px] ${KT.muted}`}>
            {got.count ?? rows.length} day(s) on file
            {got.with_pdf != null && `, ${got.with_pdf} with a rendered PDF`}.
            The paths are the spine&apos;s; this page never reads the filesystem.
          </p>
        </>
      )}
    </section>
  );
}
