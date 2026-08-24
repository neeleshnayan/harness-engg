"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Send,
  Skull,
  Swords,
  Users,
} from "lucide-react";
import { fundApiClient, DeskView, SpineEvent } from "@/lib/fund_api";
import { KT } from "../theme";
import { StudioHeader } from "../components/StudioHeader";
import { faceFor } from "./faces";
import {
  Metric, ProductionShelf, RecRow, RunRow, SeatTelemetryChips, WindowNote,
} from "./components";
import { Fold } from "./EngineViews";
import { splitRecordRows } from "./recordRow";
import { SeatTelemetry, seatTelemetry } from "./deskTelemetry";
import { MemoThread } from "./MemoThread";
import { SeatFace } from "./SeatFace";
import { floorEnabled } from "./floor/floorPlan";
import {
  DayFold,
  FeedItem,
  activeDays,
  dayKey,
  fmtAt,
  fmtTokens,
  fmtUsd,
  foldDay,
  isSeat,
  productionShelf,
  traceThreads,
  wireFeed,
  seatStatusLabel,
  seatStatusTone,
} from "./seatLib";

/**
 * The Desk — the OFFICE. How the firm is doing, day by day, with past days as
 * reviewable as today.
 *
 * It used to be a list: request work, the artifact chain, the bench. That
 * answered "who exists" and never "what happened yesterday, and who asked for
 * it" — the question a manager actually has. So the page now folds the desk AS
 * OF a chosen day: which seats ran, how many times, who triggered each, what
 * was delivered, what was decided. Scrubbing back re-renders everything; today
 * is the default and is live.
 *
 * The fold is parameterised by date over data the spine already stores — desk
 * events carry timestamps and actors, runs carry resolved_at. No new storage,
 * and nothing here is a stored aggregate that could disagree with the log.
 *
 * One honesty rule the page keeps in front of the reader: the events endpoint
 * returns at most 1000 rows, so a day older than the oldest event read is a day
 * this view CANNOT SEE, not a quiet day. That sentence is rendered, not implied.
 */

const STATUS_CHIP: Record<string, string> = {
  killed: "border-transparent bg-[var(--kt-inset)] text-[var(--kt-down)]",
  survives:
    "border-[var(--kt-accent-border)] bg-[var(--kt-accent-bg)] text-[var(--kt-accent)]",
  under_review: "border-transparent bg-[var(--kt-inset)] text-[var(--kt-warn)]",
};

export default function DeskPage() {
  const [d, setD] = useState<DeskView | null>(null);
  const [events, setEvents] = useState<SpineEvent[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [eventsErr, setEventsErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ kind: "proposal", subject: "", note: "" });
  const [sent, setSent] = useState<string | null>(null);
  /** null = today, live. A chosen day freezes the fold on that date. */
  const [day, setDay] = useState<string | null>(null);

  const load = useCallback(async () => {
    // TWO READS, NOT THREE. The `GET /fund/desk/ceo` poll went with the ticket
    // board to the room: this page had kept it running every ten seconds for a
    // block it no longer renders, which is a cost with no consumer.
    const [desk, ev] = await Promise.allSettled([
      fundApiClient.getDesk(),
      fundApiClient.getEvents(1000, 0),
    ]);
    if (desk.status === "fulfilled") { setD(desk.value); setErr(null); }
    else setErr(desk.reason instanceof Error ? desk.reason.message : "unreachable");
    if (ev.status === "fulfilled") { setEvents(ev.value.events || []); setEventsErr(null); }
    else setEventsErr(ev.reason instanceof Error ? ev.reason.message : "unreachable");
  }, []);

  useEffect(() => {
    load();
    // 10s, not 60: this page is the OFFICE — the CEO watches the seats
    // interact in close to real time. The reads are cheap folds.
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [load]);

  const submit = async () => {
    if (!form.subject.trim() || busy) return;
    setBusy(true);
    setSent(null);
    try {
      await fundApiClient.postDeskRequest(form);
      setSent("Recorded to the event log. The CTO session picks it up from here.");
      setForm({ ...form, subject: "", note: "" });
      await load();
    } catch (e) {
      setSent(`Failed: ${e instanceof Error ? e.message : "unreachable"}`);
    } finally {
      setBusy(false);
    }
  };

  // Memoised because `?? []` mints a new array every render, which would make
  // every fold below recompute on every keystroke in the composer.
  const runs = useMemo(() => d?.runs ?? [], [d]);
  const evs = useMemo(() => events ?? [], [events]);
  const days = useMemo(() => activeDays(evs, runs), [evs, runs]);
  const today = dayKey(new Date().toISOString());
  const shownDay = day ?? days[0] ?? today;
  const isLive = day == null;
  const fold = useMemo(
    () => (shownDay ? foldDay(evs, runs, shownDay) : null),
    [evs, runs, shownDay],
  );
  const dayThreads = useMemo(() => {
    const all = traceThreads(evs, runs);
    if (!shownDay) return all;
    // A thread belongs to a day if any of its nodes happened on it — the chain
    // that started yesterday and was decided today is alive on both.
    return all.filter((t) => t.nodes.some((n) => dayKey(n.at) === shownDay));
  }, [evs, runs, shownDay]);

  const idx = days.indexOf(shownDay ?? "");
  const older = idx >= 0 && idx + 1 < days.length ? days[idx + 1] : null;
  const newer = idx > 0 ? days[idx - 1] : null;

  const feed = useMemo(() => wireFeed(evs, runs, 25), [evs, runs]);

  // The floor's shelf for the day in view: every desk's deliveries, in time
  // order. Same runs the strip counts — the shelf is a rendering of them, not a
  // second source that could disagree about what was filed.
  const dayShelf = useMemo(
    () => productionShelf(fold?.runs ?? [], d?.artifacts ?? []),
    [fold, d],
  );

  return (
    <div className="min-h-screen bg-[var(--kt-bg)] text-[var(--kt-text)]">
      {/* The ONE Studio shell — theme toggle, nav, risk bar and all. The desk
          previously rolled its own header, which dropped the ThemeToggle and
          the themed background: the office rendered in a different mode from
          every other page (found by the CEO, live). Forking the shell is how
          that class of drift happens; this page no longer does. */}
      <StudioHeader subtitle="The office — the firm live, one desk per seat, every past day reviewable" />
      <div className={KT.container}>
        <header className="mb-7">
          <p className={KT.label}>Krypton Fund · The office</p>
          <h1 className="mt-1 flex items-center gap-2 text-2xl font-medium tracking-tight">
            <Swords size={22} className={KT.accent} />
            The firm that builds the fund
          </h1>
        </header>

        {err && (
          <div className={`${KT.card} mb-6 flex items-start gap-2 border-[var(--kt-warn)]`}>
            <AlertTriangle size={15} className="mt-0.5 text-[var(--kt-warn)]" />
            <p className="text-sm">Spine unreachable — showing nothing rather than a healthy desk. {err}</p>
          </div>
        )}
        {!d && !err && <p className={`text-sm ${KT.muted}`}>Reading the desk…</p>}

          {/* THE TICKET BOARD IS NOT HERE ANY MORE.
              CEO instruction 2026-08-23, verbatim: "And put the matrix in the
              room not the desk page." It moved WHOLE to
              /clark/studio/desk/floor — the same component, the same spine
              fold, one mount instead of two. A link, never a second copy:
              rendering the board on both surfaces would give the firm two
              places to read one number, which is how this desk came to show
              11 and 6 for the same question. */}
          <p className={`mb-8 text-sm ${KT.muted}`}>
            The firm&apos;s ticket board — every open thing, one row per seat —
            lives in{" "}
            <Link href="/clark/studio/desk/floor"
                  className={`${KT.accent} underline underline-offset-2`}>
              the room
            </Link>.
          </p>
        {d && (
          <>

            {/* --------------------------------------------------- the floor */}
            <section className="mb-8">
              <p className={`${KT.label} mb-3 flex items-center gap-2`}>
                <Users size={12} /> The floor — live
                {/* The 2.5D room, when the build carries the flag. A LINK from
                    here rather than a seventh nav tab: the room is presence,
                    not a workflow, and the spec's first acceptance criterion is
                    that the floor adds ZERO navigations to the approval path. */}
                {floorEnabled() && (
                  <Link href="/clark/studio/desk/floor"
                        className={`ml-1 normal-case tracking-normal ${KT.accent} underline underline-offset-2`}>
                    walk the room
                  </Link>
                )}
              </p>
              {/* The top row is the executives: hierarchy reads top-down
                  (CEO → COO → CTO → bench). The COO joined the row by CEO
                  decision 2026-08-20 and carries Vishesh's name; it keeps its
                  live status dot because unlike the humans, the seat IS
                  dispatched. Names on, clickable. */}
              <div className="mb-3 grid gap-3 sm:grid-cols-3">
                <Link href="/clark/studio/desk/ceo"
                      className={`${KT.card} ${KT.cardHover} flex items-center gap-3 p-3`}>
                  <SeatFace actor="ceo" size={42} />
                  <span>
                    <span className="block font-medium">Neelesh</span>
                    <span className={`block text-[11px] ${KT.muted}`}>
                      CEO — everything awaiting your click, in one place
                    </span>
                  </span>
                </Link>
                <Link href="/clark/studio/desk/coo"
                      className={`${KT.card} ${KT.cardHover} flex items-center gap-3 p-3`}>
                  <SeatFace actor="coo" size={42} />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center justify-between gap-2">
                      <span className="font-medium">Vishesh</span>
                      {(() => {
                        const coo = d.roster.find((r) => r.agent === "coo");
                        const tone = seatStatusTone(coo?.activity.status);
                        return coo ? (
                          <span className={`flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.1em] ${
                            tone === "working" ? "text-[var(--kt-warn)]"
                              : tone === "awaiting" ? "text-[var(--kt-text-strong)]" : KT.muted}`}>
                            <span className={`h-1.5 w-1.5 rounded-full ${
                              tone === "working" ? "kt-breathe bg-[var(--kt-warn)]"
                                : tone === "awaiting" ? "border border-[var(--kt-text-strong)]"
                                : "bg-[var(--kt-border-strong)]"}`} />
                            {seatStatusLabel(coo.activity.status)}
                          </span>
                        ) : null;
                      })()}
                    </span>
                    <span className={`block text-[11px] ${KT.muted}`}>
                      COO · Opus — your desk, triaged into batch decisions
                    </span>
                    {/* The COO is a dispatched seat like the bench, so it
                        carries the same three figures. The two humans beside it
                        do not: the spine cannot count a human's runs, and
                        drawing them zero would be a lie about a colleague. */}
                    <SeatTelemetryChips t={seatTelemetry(d, "coo")} compact />
                  </span>
                </Link>
                <Link href="/clark/studio/desk/cto"
                      className={`${KT.card} ${KT.cardHover} flex items-center gap-3 p-3`}>
                  <SeatFace actor="cto" size={42} />
                  <span>
                    <span className="block font-medium">Fable</span>
                    <span className={`block text-[11px] ${KT.muted}`}>
                      CTO — the build and dispatch queue, and what it costs
                    </span>
                  </span>
                </Link>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {d.roster
                  .filter((r) => r.agent !== "coo")   // the coo sits in the exec row
                  .map((r) => <Desk key={r.agent} r={r} t={seatTelemetry(d, r.agent)} />)}
              </div>
              {/* The telemetry block's honesty line, once, under the floor —
                  rather than repeated on nine cards. Both branches are stated:
                  the "no rollup" case is the one a reader would otherwise read
                  as a quiet firm, so it gets the longer sentence. */}
              <p className={`mt-2 text-[11px] italic leading-relaxed ${KT.muted}`}>
                {d.seat_telemetry
                  ? d.seat_telemetry.note
                  : "This spine does not return per-seat telemetry yet (`seat_telemetry` " +
                    "on GET /fund/desk), so no seat's run count or token cost for today " +
                    "is on screen. Running-now still comes from the roster. The counts " +
                    "are NOT folded from the run list above: it carries the 25 most " +
                    "recent runs across all seats, so a per-seat day count taken from it " +
                    "would be a floor wearing a count's clothes."}
              </p>
            </section>

            {/* -------------------------------------- the wire: what, as it happens */}
            {/* The section renders ALWAYS (CDO D10). It used to disappear
                entirely when `feed` was empty, which made "the log could not be
                read" and "nothing has happened yet" render identically: as
                nothing at all. Those are different facts and the second one is
                reassuring, so the first must never be able to wear it. */}
            <Fold title="The wire — every interaction between the desks"
                  n={feed.length}
                  lede="The ask, the dispatch, the delivery, the decision, newest first. Folded because the board above already says what is outstanding; this is how it got there.">
              {feed.length > 0 ? (
                <div className={`${KT.card} divide-y divide-[var(--kt-border)] p-0`}>
                  {feed.map((f, i) => <WireRow key={`${f.traceId}-${f.kind}-${f.at}-${i}`} f={f} />)}
                </div>
              ) : eventsErr ? (
                <div className={`${KT.card} p-4`}>
                  <p className={`text-sm ${KT.sev.warn}`}>
                    The wire could not be read ({eventsErr}).
                  </p>
                  <p className={`mt-1 text-xs ${KT.muted}`}>
                    This is an absence, not an empty desk — interactions may have
                    happened that this panel cannot currently see.
                  </p>
                </div>
              ) : (
                <div className={`${KT.card} p-4`}>
                  <p className={`text-sm ${KT.muted}`}>
                    No interactions recorded yet.
                  </p>
                  <p className={`mt-1 text-xs ${KT.muted}`}>
                    The wire is readable and empty — the desks have not spoken to
                    each other since the log begins.
                  </p>
                </div>
              )}
              {feed.length > 0 && eventsErr && (
                <p className={`mt-2 text-xs ${KT.sev.warn}`}>
                  The event log could not be read ({eventsErr}) — the wire shows
                  only the flight recorder until it returns.
                </p>
              )}
            </Fold>

            {/* ------------------------------------------------- request work */}
            <section className={`${KT.card} mb-8 border-[var(--kt-accent-border)]`}>
              <p className={`${KT.label} mb-3`}>Request work from the bench</p>
              <div className="flex flex-wrap items-end gap-3">
                <label className="flex flex-col gap-1">
                  <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
                    kind
                  </span>
                  <select
                    value={form.kind}
                    onChange={(e) => setForm({ ...form, kind: e.target.value })}
                    className={KT.input}
                  >
                    <option value="proposal">proposal — mechanism</option>
                    <option value="thesis">thesis — analyst</option>
                    <option value="portfolio_review">portfolio review — pm</option>
                    <option value="implement">implement — quant</option>
                    <option value="attack">attack — adversary</option>
                    <option value="audit">audit — validator</option>
                    <option value="policy_audit">policy audit — riskofficer</option>
                    <option value="build">build — builder</option>
                    <option value="triage">triage my desk — coo</option>
                  </select>
                </label>
                <label className="flex min-w-[16rem] flex-1 flex-col gap-1">
                  <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
                    subject
                  </span>
                  <input
                    value={form.subject}
                    onChange={(e) => setForm({ ...form, subject: e.target.value })}
                    placeholder="what to propose on / attack / audit"
                    className={KT.input}
                  />
                </label>
                <button
                  type="button"
                  onClick={submit}
                  disabled={busy || !form.subject.trim()}
                  className={`${KT.btn} flex items-center gap-1.5 disabled:opacity-40`}
                >
                  <Send size={13} /> {busy ? "Recording…" : "Record request"}
                </button>
              </div>
              {sent && <p className={`mt-2 text-xs ${KT.muted}`}>{sent}</p>}
              <p className={`mt-3 text-xs italic leading-relaxed ${KT.muted}`}>
                {d.execution_note}
              </p>
            </section>

            {/* ------------------------------- requests: who is asking for whom
                The chain (constitution amendment, 2026-08-20): a seat or human
                FILES an ask → the CEO APPROVES it → the CTO TRIGGERS the
                dispatch. Approval is recorded as an event and is never itself
                a trigger. Requests already blessed render as "approved —
                awaiting the CTO"; open ones carry the Approve control. */}
            {d.requests.filter((r) => r.status !== "resolved").length > 0 && (
              <Fold title="Requests between desks"
                    n={d.requests.filter((r) => r.status !== "resolved").length}
                    lede="Who wants to call whom, and for what. Approving records your blessing on the log and hands the ask to the CTO to trigger — it runs nothing by itself.">
                <div className="space-y-1.5">
                  {d.requests
                    .filter((r) => r.status !== "resolved")
                    .map((r) => (
                      <RequestRow key={r.request_id} r={r} onChanged={load} />
                    ))}
                </div>
              </Fold>
            )}

            {/* Recommendations, SPLIT THREE WAYS.
                (CDO D4) `/fund/desk` returns open, accepted and staged under
                one key, so this heading counted decisions the CEO had already
                made as decisions they still owed.
                (D42) And `open` is still not the same question as "awaiting a
                decision": a row the spine routes to `nobody` is filed FOR THE
                RECORD and will be open forever. It was counted here and
                rendered with Accept and Reject — the CEO's *"like WTF"*. It
                now has its own fold, is not counted, and carries no control. */}
            {d.open_recommendations?.length > 0 && (() => {
              const { awaiting: undecided, record, decided } =
                splitRecordRows(d.open_recommendations);
              return (
                <>
                  <Fold title="Recommendations awaiting a decision"
                        n={undecided.length}
                        lede="Undecided rows only. The board above splits these by seat; this is the flat list with its controls.">
                    <div className="space-y-1.5">
                      {undecided.map((r) => (
                        <RecRow key={`${r.run_id}-${r.rec_id}`} r={r} onDecide={load} />
                      ))}
                    </div>
                  </Fold>
                  {record.length > 0 && (
                    <Fold title="Filed for the record — no decision owed"
                          n={record.length}
                          lede="The fund routed these to nobody: findings and notes filed so they cannot go quiet. Open forever, and not work. Shown, never counted.">
                      <div className="space-y-1.5">
                        {record.map((r) => (
                          <RecRow key={`${r.run_id}-${r.rec_id}`} r={r} onDecide={load} />
                        ))}
                      </div>
                    </Fold>
                  )}
                  {decided.length > 0 && (
                    <Fold title="Decided, awaiting execution"
                          n={decided.length}
                          lede="The CEO already said yes to these; what remains is the chair's to execute. They are the board's TICKING column.">
                      <div className="space-y-1.5">
                        {decided.map((r) => (
                          <RecRow key={`${r.run_id}-${r.rec_id}`} r={r} onDecide={load} />
                        ))}
                      </div>
                    </Fold>
                  )}
                </>
              );
            })()}

            {/* ------------------- rewind: any past day, as reviewable as today */}
            {days.length > 0 && (
              <Fold title="Rewind — any past day, as reviewable as today"
                    n={days.length}
                    lede="How many times each seat ran on a chosen day, who triggered them, what it cost, and that day's chains replayed. Today is live.">
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <button type="button" disabled={!older} onClick={() => setDay(older)}
                          className={`${KT.btnGhost} flex h-8 items-center gap-1 px-2 text-xs disabled:opacity-30`}>
                    <ChevronLeft size={13} /> older
                  </button>
                  <div className="flex flex-wrap gap-1">
                    {days.slice(0, 14).map((dk) => (
                      <button
                        key={dk}
                        type="button"
                        onClick={() => setDay(dk === days[0] ? null : dk)}
                        aria-current={dk === shownDay ? "date" : undefined}
                        className={`rounded-lg border px-2 py-1 font-mono text-[11px] tabular-nums transition-colors ${
                          dk === shownDay
                            ? "border-[var(--kt-accent-border)] bg-[var(--kt-accent-bg)] text-[var(--kt-accent)]"
                            : "border-transparent text-[var(--kt-text-dim)] hover:bg-[var(--kt-inset)]"
                        }`}
                      >
                        {dk.slice(5)}
                      </button>
                    ))}
                  </div>
                  <button type="button" disabled={!newer} onClick={() => setDay(newer === days[0] ? null : newer)}
                          className={`${KT.btnGhost} flex h-8 items-center gap-1 px-2 text-xs disabled:opacity-30`}>
                    newer <ChevronRight size={13} />
                  </button>
                  <span className={`ml-2 font-mono text-[10px] uppercase tracking-[0.1em] ${isLive ? KT.accent : KT.muted}`}>
                    {isLive ? "today · live" : `as of ${shownDay}`}
                  </span>
                  {!isLive && (
                    <button type="button" onClick={() => setDay(null)}
                            className={`text-[11px] ${KT.accent} underline underline-offset-2`}>
                      back to today
                    </button>
                  )}
                </div>

                {fold && <ProductivityStrip fold={fold} />}

                {/* The floor AS OF the day in view. Only when scrubbed back:
                    today's floor is the live one at the top of the page, and
                    drawing it twice would invite the reader to compare two
                    renderings of the same thing. */}
                {!isLive && fold && (
                  <div className="mb-5">
                    <p className={`${KT.label} mb-2`}>The floor on {shownDay}</p>
                    <FloorAsOf roster={d.roster} fold={fold} />
                  </div>
                )}

                {/* What the floor PRODUCED on the day in view — the shelf, one
                    spine per delivery. Sits above the threads because "what came
                    out" is the question a manager asks before "how it went". */}
                {fold && (
                  <div className="mt-5">
                    <p className={`${KT.label} mb-2`}>
                      {isLive ? "Filed today" : `Filed on ${shownDay}`}
                    </p>
                    <ProductionShelf
                      items={dayShelf}
                      emptyNote="Nothing was filed on this day."
                    />
                  </div>
                )}

                {dayThreads.length > 0 && (
                  <div className="mt-5 space-y-3">
                    <p className={`${KT.label} mb-1`}>
                      {isLive ? "Memo threads alive today" : `Memo threads alive on ${shownDay}`}
                    </p>
                    {dayThreads.slice(0, 6).map((t) => (
                      <MemoThread key={t.traceId} t={t} />
                    ))}
                  </div>
                )}

                {/* The window this whole section can see, stated last, once —
                    a day older than the oldest event read is a day this view
                    CANNOT SEE, not a quiet day. */}
                {events != null && (
                  <WindowNote events={events.length} capped={events.length >= 1000} />
                )}
              </Fold>
            )}

            {/* the flight recorder, filtered to the day in view */}
            {fold && (
              <Fold title={isLive ? "Runs resolved today" : `Runs resolved on ${shownDay}`}
                    n={fold.runs.length}
                    lede="The flight recorder for the day in view. The desk payload carries the 25 most recent runs across all seats; a seat's full record is on its own page.">
                {fold.runs.length === 0 ? (
                  <p className={`text-sm ${KT.muted}`}>
                    No run was resolved on this day.
                  </p>
                ) : (
                  <div className="space-y-1">
                    {fold.runs.map((run) => (
                      <RunRow key={run.run_id} run={run} />
                    ))}
                  </div>
                )}
              </Fold>
            )}

            {/* the artifact chain */}
            <Fold title="The artifact chain"
                  n={d.artifacts.length}
                  lede={`Proposals and designs paired with the verdicts that reviewed them. ${d.kills} kill${d.kills === 1 ? "" : "s"} — at this firm a demonstrated kill is a win.`}>
              <div className="mb-3 flex items-baseline justify-end gap-2">
                <p className={`flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
                  <Skull size={11} className="text-[var(--kt-down)]" />
                  {d.kills} kill{d.kills === 1 ? "" : "s"} — at this firm a
                  demonstrated kill is a win
                </p>
              </div>
              <div className="space-y-2">
                {d.artifacts.map((a) => (
                  <div
                    key={a.path}
                    className={`${KT.card} border-l-2 p-4 ${
                      a.status === "killed"
                        ? "border-l-[var(--kt-down)]"
                        : a.status === "survives"
                          ? "border-l-[var(--kt-accent)]"
                          : "border-l-[var(--kt-warn)]"
                    }`}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
                        {a.kind}
                      </span>
                      <span className="text-sm font-medium">{a.title}</span>
                      <span
                        className={`rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] ${STATUS_CHIP[a.status] ?? ""}`}
                      >
                        {a.status.replace("_", " ")}
                      </span>
                    </div>
                    <p className={`mt-1 font-mono text-[10px] ${KT.muted}`}>{a.path}</p>
                    {a.review && (
                      <p className={`mt-1.5 text-xs ${KT.muted}`}>
                        <span className="text-[var(--kt-down)]">
                          {a.review.verdict}
                        </span>{" "}
                        — {a.review.review_title}{" "}
                        <span className="font-mono text-[10px]">
                          ({a.review.review_path})
                        </span>
                      </p>
                    )}
                    {a.note && (
                      <p className={`mt-1.5 text-xs italic ${KT.muted}`}>{a.note}</p>
                    )}
                  </div>
                ))}
              </div>
            </Fold>

            {/* the protocol, verbatim */}
            <Fold title="The working protocol" n={d.protocol.length}
                  lede="The five rules every artifact at this firm is judged against, verbatim from the constitution.">
              <ol className={`${KT.card} space-y-1.5 p-4`}>
                {d.protocol.map((line, i) => (
                  <li key={i} className="flex gap-3 text-xs leading-relaxed">
                    <span className="font-mono text-[var(--kt-accent)]">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    {line}
                  </li>
                ))}
              </ol>
            </Fold>

            {/* "How it got here" (the Arc + Ladder from Mechanics) was retired
                from this page 2026-08-20 by CEO decision — it read as stale on
                a live surface, and the firm's origin story is Doctrine's job
                (/clark/studio/doctrine, the design audit's reference page).
                Removing it also dropped the slow /fund/mechanics fetch from
                the office's 10-second poll. The belt-native views stay on the
                quant's page, where they inform dispatches. */}
          </>
        )}
      </div>
    </div>
  );
}

/**
 * ONE DESK on the floor.
 *
 * The CEO's ask, verbatim: "a human type org where you have desks and you can
 * see what each desk is doing". So the card is a desk, not a row in a table —
 * the face first (a face is how a human indexes a colleague), then the name,
 * then the one line of what this desk is doing or last produced.
 *
 * Two honesty rules survive the re-skin:
 *   - A WORKING desk breathes (kt-breathe, which honours prefers-reduced-motion
 *     by dropping the motion and keeping the marker). An idle desk rests, and
 *     idle is not a fault: "an idle seat costs zero and that is a feature".
 *   - The line under the name is the spine's own `activity`, in priority order
 *     — the live task, else the last thing filed, else the lane. It never
 *     invents a status; a roster entry the route whitelist does not know
 *     (`isSeat`) renders as a desk you cannot walk into rather than a dead link.
 */
/** The file name off a path, for a desk card that has one line to spend. The
 *  full path stays in the title attribute — shortened, never dropped. */
const fileName = (p: string): string => p.split(/[\\/]/).pop() || p;

function Desk({ r, t }: { r: DeskView["roster"][number]; t: SeatTelemetry }) {
  const working = r.activity.status === "working";
  // The third state (CEO, request 907ecc74): the seat came back and nobody has
  // reviewed it. It is NOT working — it does not breathe, because nothing is
  // happening there — and it is NOT idle, because it is an obligation on this
  // chair. Three finished dispatches read as WORKING for hours before this.
  const awaiting = r.activity.status === "awaiting_review";
  // Both states carry the dispatch's task; only WORKING is present tense.
  const dispatched = working || awaiting;
  const inner = (
    <>
      <div className="flex items-start gap-3">
        <span className={working ? "text-[var(--kt-text-strong)]" : "text-[var(--kt-text-muted)]"}>
          <SeatFace actor={r.agent} size={42} decorative />
        </span>
        <div className="min-w-0 flex-1">
          {/* Every bench seat wears its model's name the way the CTO wears
              Fable's (CEO decision 2026-08-20: "other agents get Opus name").
              Judgement placement is Opus for the whole bench per the
              constitution; hybrid/local phases are detail for the seat page. */}
          <p className="truncate font-mono text-sm text-[var(--kt-text-strong)]">
            {r.agent}
            <span className={`ml-1.5 text-[11px] font-normal ${KT.muted}`}>· Opus</span>
          </p>
          <p className={`mt-1 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.1em] ${
            working ? "text-[var(--kt-warn)]"
              : awaiting ? "text-[var(--kt-text-strong)]" : KT.muted}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${
              working ? "kt-breathe bg-[var(--kt-warn)]"
                : awaiting ? "border border-[var(--kt-text-strong)]"
                : "bg-[var(--kt-border-strong)]"}`} />
            {awaiting ? "awaiting review" : r.activity.status}
          </p>
        </div>
      </div>
      {/* What this desk is doing, in the reader's words. The last delivery is
          shown by its TASK, not by its file path: a path is an address, and a
          floor plan that reads as a list of addresses is not a floor. The path
          is still there, as the second line, in the file name only. */}
      {dispatched && r.activity.task ? (
        <>
          <p className={`mt-3 line-clamp-3 text-[12px] leading-relaxed ${KT.body}`}>
            {r.activity.task}
          </p>
          {/* What the chair has to DO, said plainly. A dispatch closes on a
              resolution, never on a run coming back — so this line stays until
              somebody reviews it and resolves the request. */}
          {awaiting && (
            <p className={`mt-1.5 font-mono text-[10px] ${KT.muted}`}>
              returned{r.activity.returned_run_id ? ` · ${r.activity.returned_run_id}` : ""}
              {" · review, then resolve to close"}
            </p>
          )}
          {/* Detection is incomplete and says so rather than implying a clean
              reading: measured 2026-08-21, only 8 of 23 dispatched task_ids
              carry a run with a matching trace. WORKING is then a floor. */}
          {working && r.activity.review_detectable === false && (
            <p className={`mt-1.5 font-mono text-[10px] ${KT.muted}`}
               title="the run recorder could not be read, so a returned dispatch would look the same as a running one">
              return not detectable
            </p>
          )}
        </>
      ) : r.activity.last_delivered ? (
        <div className="mt-3">
          <p className={`line-clamp-2 text-[12px] leading-relaxed ${KT.muted}`}>
            {r.activity.last_delivered.task}
          </p>
          <p className={`mt-1 truncate font-mono text-[10px] ${KT.muted}`}
             title={r.activity.last_delivered.artifact}>
            {fileName(r.activity.last_delivered.artifact)}
            {r.activity.last_delivered.at ? ` · ${r.activity.last_delivered.at.slice(0, 10)}` : ""}
          </p>
        </div>
      ) : (
        <p className={`mt-3 line-clamp-3 text-[12px] leading-relaxed ${KT.muted}`}>{r.lane}</p>
      )}
      {/* Running now / runs today / tokens today (CEO ask, 2026-08-21). */}
      <SeatTelemetryChips t={t} compact />
    </>
  );
  return isSeat(r.agent) ? (
    <Link key={r.agent} href={`/clark/studio/desk/${r.agent}`}
          className={`${KT.card} ${KT.cardHover} block p-4`}>
      {inner}
    </Link>
  ) : (
    <div key={r.agent} className={`${KT.card} p-4`}
         title="Not a seat with its own page — the route whitelist does not carry this agent.">
      {inner}
    </div>
  );
}

/**
 * The floor as it stood on a past day.
 *
 * The spine's `roster.activity` is a LIVE fold — it has no history, so a past
 * day's floor cannot be read from it. What CAN be read is what each desk did
 * that day: the runs it resolved and whether it appears among the day's
 * dispatched seats. That is what this renders, and the wording keeps the three
 * cases apart, because on a dashboard they look identical and mean opposite
 * things:
 *
 *   filed something · dispatched but nothing resolved · no record at all
 *
 * The third is NOT "did nothing": the events endpoint caps at 1000 rows, and
 * the WindowNote under this section says so.
 */
function FloorAsOf({ roster, fold }: { roster: DeskView["roster"]; fold: DayFold }) {
  const bySeat = new Map<string, DayFold["runs"]>();
  for (const r of fold.runs) {
    const list = bySeat.get(r.seat) ?? [];
    list.push(r);
    bySeat.set(r.seat, list);
  }
  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
      {roster.map((r) => {
        const ran = bySeat.get(r.agent) ?? [];
        const touched = fold.seats.includes(r.agent);
        const body = (
          <>
            <div className="flex items-center gap-2.5">
              <span className={ran.length ? "text-[var(--kt-text-strong)]" : "text-[var(--kt-text-muted)]"}>
                <SeatFace actor={r.agent} size={26} decorative />
              </span>
              <span className="truncate font-mono text-xs">{r.agent}</span>
              <span className={`ml-auto font-mono text-[10px] tabular-nums ${KT.muted}`}>
                {ran.length ? `${ran.length} filed` : touched ? "dispatched" : "—"}
              </span>
            </div>
            <p className={`mt-1.5 line-clamp-2 text-[11px] leading-relaxed ${
              ran.length ? KT.body : KT.muted}`}>
              {ran.length
                ? ran[0].task
                : touched
                  ? "dispatched, but no run resolved on this day"
                  : "no dispatch and no delivery on this day, in the events read"}
            </p>
          </>
        );
        return isSeat(r.agent) ? (
          <Link key={r.agent} href={`/clark/studio/desk/${r.agent}`}
                className={`${KT.inset} ${KT.cardHover} block p-3`}>
            {body}
          </Link>
        ) : (
          <div key={r.agent} className={`${KT.inset} p-3`}>{body}</div>
        );
      })}
    </div>
  );
}

/** One ask between desks: FROM requester TO the seat it calls, with the CEO's
 *  approve control while it is open, and its blessing state once given. The
 *  approve posts an event — it triggers nothing, and the row says so. */
function RequestRow({ r, onChanged }: {
  r: DeskView["requests"][number];
  onChanged: () => Promise<void> | void;
}) {
  const [busy, setBusy] = useState(false);
  const approve = async () => {
    setBusy(true);
    try {
      await fundApiClient.approveDeskRequest(r.request_id, { actor: "ceo" });
      await onChanged();
    } finally {
      setBusy(false);
    }
  };
  const requester = (r.actor || "").trim();
  return (
    <div className={`${KT.card} flex flex-wrap items-center gap-x-3 gap-y-1.5 p-3 text-sm`}>
      <span className="flex shrink-0 items-center gap-1.5 font-mono text-[11px]">
        <SeatFace actor={requester} size={18} decorative />
        {faceFor(requester)?.label ?? (requester || "unattributed")}
      </span>
      <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
        asks
      </span>
      <span className="flex shrink-0 items-center gap-1.5 font-mono text-[11px]">
        <SeatFace actor={r.serves} size={18} decorative />
        {isSeat(r.serves)
          ? <Link href={`/clark/studio/desk/${r.serves}`} className={`${KT.accent} hover:underline`}>{r.serves}</Link>
          : r.serves}
      </span>
      <span className="min-w-0 flex-1 text-[13px] leading-snug">{r.subject}</span>
      {r.at && (
        <span className={`font-mono text-[10px] tabular-nums ${KT.muted}`}>{fmtAt(r.at)}</span>
      )}
      {r.status === "open" ? (
        <button type="button" disabled={busy} onClick={approve}
                className={`${KT.btn} shrink-0 px-2 py-1 text-xs disabled:opacity-40`}>
          {busy ? "Recording…" : "Approve for dispatch"}
        </button>
      ) : (
        <span className="shrink-0 rounded-full border border-[var(--kt-accent-border)] bg-[var(--kt-accent-bg)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--kt-accent)]">
          approved — awaiting the CTO&apos;s trigger
        </span>
      )}
      {r.note && (
        <p className={`w-full text-xs ${KT.muted}`}>{r.note}</p>
      )}
    </div>
  );
}

/** One interaction on the wire. Reads as a sentence: who did what to whom —
 *  "ceo asked pm: …", "cto dispatched adversary: …", "pm delivered: … KILL",
 *  "ceo accepted rec 4: …". The seat name is a door into its office. */
function WireRow({ f }: { f: FeedItem }) {
  const verb =
    f.kind === "request" ? "asked" :
    f.kind === "dispatch" ? "dispatched" :
    f.kind === "run" ? "delivered" :
    f.status ? f.status : "decided";
  const who = f.kind === "run" ? f.seat : f.actor || "?";
  const target = f.kind === "run" ? null : f.seat;
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 px-3 py-2 text-xs">
      <span className={`w-24 shrink-0 font-mono text-[10px] tabular-nums ${KT.muted}`}>
        {fmtAt(f.at)}
      </span>
      {/* The same face this actor wears on the floor and on every memo. An
          actor with no face on file draws the dashed "unknown" head rather
          than borrowing someone else's — see faces.ts. */}
      <SeatFace actor={who} size={18} decorative />
      <span className="font-mono text-[11px]">{who}</span>
      <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${
        f.kind === "decision" ? "text-[var(--kt-accent)]" : KT.muted}`}>
        {verb}
      </span>
      {target && (
        isSeat(target) ? (
          <Link href={`/clark/studio/desk/${target}`}
                className={`inline-flex items-center gap-1.5 font-mono text-[11px] ${KT.accent} hover:underline`}>
            <SeatFace actor={target} size={18} decorative />
            {target}
          </Link>
        ) : (
          <span className="inline-flex items-center gap-1.5 font-mono text-[11px]">
            <SeatFace actor={target} size={18} decorative />
            {target}
          </span>
        )
      )}
      <span className="min-w-0 flex-1 truncate">{f.label}</span>
      {f.verdict && (
        <span className={`font-mono text-[10px] uppercase ${
          f.verdict.startsWith("KILL") ? "text-[var(--kt-down)]" : KT.muted}`}>
          {f.verdict.length > 28 ? f.verdict.slice(0, 28) + "…" : f.verdict}
        </span>
      )}
    </div>
  );
}

/** The day's work in one line of figures. A kill is rendered as a win, because
 *  it is one — a day of killing that reads as a day of nothing would push the
 *  firm toward shipping instead of falsifying. */
function ProductivityStrip({ fold }: { fold: DayFold }) {
  return (
    <div className={`${KT.card} flex flex-wrap gap-x-8 gap-y-4`}>
      <Metric label="dispatches" value={fold.dispatches}
              sub={fold.actors.length ? `by ${fold.actors.join(", ")}` : "none"} />
      <Metric label="asks recorded" value={fold.requests} />
      <Metric label="runs resolved" value={fold.runs.length} />
      <Metric label="verdicts" value={fold.verdicts} />
      <Metric label="kills" value={fold.kills} tone={fold.kills ? KT.accent : undefined}
              sub="a kill is a win" />
      <Metric label="decisions" value={fold.decisions}
              sub="recommendations accepted or rejected" />
      <Metric label="tokens" value={fmtTokens(fold.tokens)}
              sub={fold.tokens == null ? "no run reported tokens" : "over runs resolved this day"} />
      <Metric label="cost (estimate)" value={fmtUsd(fold.costUsd)}
              sub="blend estimate — see a seat page for the price table" />
      <div className="min-w-[10rem]">
        <p className={KT.label}>seats active</p>
        <p className="mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-1">
          {fold.seats.length === 0 ? (
            <span className={`text-sm ${KT.muted}`}>—</span>
          ) : (
            fold.seats.map((s) => (
              isSeat(s) ? (
                <Link key={s} href={`/clark/studio/desk/${s}`}
                      className={`inline-flex items-center gap-1.5 font-mono text-[11px] ${KT.accent} hover:underline`}>
                  <SeatFace actor={s} size={18} decorative /> {s}
                </Link>
              ) : (
                <span key={s} className={`inline-flex items-center gap-1.5 font-mono text-[11px] ${KT.muted}`}>
                  <SeatFace actor={s} size={18} decorative /> {s}
                </span>
              )
            ))
          )}
        </p>
      </div>
    </div>
  );
}
