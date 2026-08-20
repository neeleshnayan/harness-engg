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
import { fundApiClient, DeskView, MechanicsView, SpineEvent } from "@/lib/fund_api";
import { KT } from "../theme";
import { StudioNav } from "../components/StudioNav";
import { RiskBar } from "../components/RiskBar";
import { Arc, Ladder } from "../components/mechanics/MechanicsViews";
import {
  Metric, RecRow, RunRow, SectionHead, TraceFlow, WindowNote,
} from "./components";
import {
  DayFold,
  activeDays,
  dayKey,
  fmtAt,
  fmtTokens,
  fmtUsd,
  foldDay,
  isSeat,
  traceThreads,
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
  const [mech, setMech] = useState<MechanicsView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [eventsErr, setEventsErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ kind: "proposal", subject: "", note: "" });
  const [sent, setSent] = useState<string | null>(null);
  /** null = today, live. A chosen day freezes the fold on that date. */
  const [day, setDay] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [desk, ev, m] = await Promise.allSettled([
      fundApiClient.getDesk(),
      fundApiClient.getEvents(1000, 0),
      fundApiClient.getMechanics(),
    ]);
    if (desk.status === "fulfilled") { setD(desk.value); setErr(null); }
    else setErr(desk.reason instanceof Error ? desk.reason.message : "unreachable");
    if (ev.status === "fulfilled") { setEvents(ev.value.events || []); setEventsErr(null); }
    else setEventsErr(ev.reason instanceof Error ? ev.reason.message : "unreachable");
    // Mechanics is the slow read (it walks several subsystems); the office
    // survives without it and says so.
    setMech(m.status === "fulfilled" ? m.value : null);
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
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

  const runs = d?.runs ?? [];
  const evs = events ?? [];
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

  return (
    <>
      <RiskBar />
      <div className={KT.container}>
        <header className="mb-7 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className={KT.label}>Krypton Fund · The office</p>
            <h1 className="mt-1 flex items-center gap-2 text-2xl font-medium tracking-tight">
              <Swords size={22} className={KT.accent} />
              The firm that builds the fund
            </h1>
          </div>
          <StudioNav />
        </header>

        {err && (
          <div className={`${KT.card} mb-6 flex items-start gap-2 border-[var(--kt-warn)]`}>
            <AlertTriangle size={15} className="mt-0.5 text-[var(--kt-warn)]" />
            <p className="text-sm">Spine unreachable — showing nothing rather than a healthy desk. {err}</p>
          </div>
        )}
        {!d && !err && <p className={`text-sm ${KT.muted}`}>Reading the desk…</p>}

        {/* ------------------------------------------------- the day scrubber */}
        {days.length > 0 && (
          <section className="mb-8">
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
            {events != null && (
              <WindowNote events={events.length} capped={events.length >= 1000} />
            )}
            {eventsErr && (
              <p className={`mt-2 text-xs ${KT.sev.warn}`}>
                The event log could not be read ({eventsErr}) — the day view is
                blank because it is unknown, not because nothing happened.
              </p>
            )}
          </section>
        )}

        {d && (
          <>
            {/* -------------------------------------------- the day's chains */}
            {dayThreads.length > 0 && (
              <section className="mb-8">
                <SectionHead
                  title={isLive ? "Chains alive today" : `Chains alive on ${shownDay}`}
                  lede="Each trace is one conversation: the ask, the dispatch, the run and its verdict, then the decisions. Nodes carry who and when — the working view and the audit view are the same drawing."
                />
                <div className="space-y-2">
                  {dayThreads.slice(0, 6).map((t) => (
                    <TraceFlow key={t.traceId} t={t} />
                  ))}
                </div>
              </section>
            )}

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

            {/* open requests */}
            {d.requests.filter((r) => r.status === "open").length > 0 && (
              <section className="mb-8">
                <p className={`${KT.label} mb-2`}>
                  Waiting for the CTO session ({d.open_requests})
                </p>
                <div className="space-y-1.5">
                  {d.requests
                    .filter((r) => r.status === "open")
                    .map((r) => (
                      <div key={r.request_id} className={`${KT.card} p-3 text-sm`}>
                        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--kt-warn)]">
                          {r.kind} → {isSeat(r.serves)
                            ? <Link href={`/clark/studio/desk/${r.serves}`} className="hover:underline">{r.serves}</Link>
                            : r.serves}
                        </span>
                        <span className="ml-3">{r.subject}</span>
                        {r.actor && (
                          <span className={`ml-2 font-mono text-[10px] ${KT.muted}`}>
                            asked by {r.actor}{r.at ? ` · ${fmtAt(r.at)}` : ""}
                          </span>
                        )}
                        {r.note && (
                          <p className={`mt-1 text-xs ${KT.muted}`}>{r.note}</p>
                        )}
                      </div>
                    ))}
                </div>
              </section>
            )}

            {/* recommendations awaiting decisions — attribution is the point */}
            {d.open_recommendations?.length > 0 && (
              <section className="mb-8">
                <p className={`${KT.label} mb-2`}>
                  Recommendations awaiting your decision
                </p>
                <div className="space-y-1.5">
                  {d.open_recommendations.map((r) => (
                    <RecRow key={`${r.run_id}-${r.rec_id}`} r={r} onDecide={load} />
                  ))}
                </div>
              </section>
            )}

            {/* the flight recorder, filtered to the day in view */}
            {fold && (
              <section className="mb-8">
                <p className={`${KT.label} mb-2`}>
                  {isLive ? "Runs resolved today" : `Runs resolved on ${shownDay}`}
                </p>
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
                <p className={`mt-2 text-[11px] italic ${KT.muted}`}>
                  The desk payload carries the 25 most recent runs across all
                  seats; a seat&apos;s full record is on its own page.
                </p>
              </section>
            )}

            {/* the artifact chain */}
            <section className="mb-8">
              <div className="mb-3 flex items-baseline justify-between gap-2">
                <p className={KT.label}>The artifact chain</p>
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
            </section>

            {/* the bench — now a set of doors */}
            <section className="mb-8">
              <p className={`${KT.label} mb-3 flex items-center gap-2`}>
                <Users size={12} /> The bench — one page each
              </p>
              <div className="grid gap-3 md:grid-cols-3">
                {d.roster.map((r) => {
                  const card = (
                    <>
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-mono text-sm text-[var(--kt-accent)]">
                          {r.agent}
                        </p>
                        <span
                          className={`flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.1em] ${
                            r.activity.status === "working"
                              ? "text-[var(--kt-warn)]"
                              : KT.muted
                          }`}
                        >
                          <span
                            className={`h-1.5 w-1.5 rounded-full ${
                              r.activity.status === "working"
                                ? "animate-pulse bg-[var(--kt-warn)]"
                                : "bg-[var(--kt-border-strong)]"
                            }`}
                          />
                          {r.activity.status}
                        </span>
                      </div>
                      {r.activity.status === "working" && r.activity.task && (
                        <p className="mt-1.5 rounded bg-[var(--kt-inset)] px-2 py-1 text-xs leading-snug">
                          {r.activity.task}
                        </p>
                      )}
                      {r.activity.last_delivered && (
                        <p className={`mt-1.5 text-[11px] ${KT.muted}`}>
                          last delivered:{" "}
                          <span className="font-mono">
                            {r.activity.last_delivered.artifact}
                          </span>
                        </p>
                      )}
                      <p className="mt-1.5 text-xs leading-relaxed">{r.lane}</p>
                      <p className={`mt-2 font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
                        emits
                      </p>
                      <p className={`text-xs ${KT.muted}`}>{r.emits}</p>
                    </>
                  );
                  return isSeat(r.agent) ? (
                    <Link key={r.agent} href={`/clark/studio/desk/${r.agent}`}
                          className={`${KT.card} ${KT.cardHover} block p-4`}>
                      {card}
                      <p className={`mt-2 font-mono text-[10px] uppercase tracking-[0.1em] ${KT.accent}`}>
                        open seat page →
                      </p>
                    </Link>
                  ) : (
                    <div key={r.agent} className={`${KT.card} p-4`}>{card}</div>
                  );
                })}
              </div>
            </section>

            {/* the protocol, verbatim */}
            <section className={`${KT.card} mb-8 p-4`}>
              <p className={`${KT.label} mb-2`}>The working protocol</p>
              <ol className="space-y-1.5">
                {d.protocol.map((line, i) => (
                  <li key={i} className="flex gap-3 text-xs leading-relaxed">
                    <span className="font-mono text-[var(--kt-accent)]">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    {line}
                  </li>
                ))}
              </ol>
            </section>

            {/* How the machine got here — moved from the Mechanics tab, which
                no longer exists. The story and the ladder are about the FIRM,
                so they live in the office; the belt's charts moved to quant. */}
            {mech && (
              <section className="mb-4">
                <Arc m={mech} />
                <Ladder m={mech} />
              </section>
            )}
            {!mech && (
              <p className={`mb-8 text-xs ${KT.muted}`}>
                The machinery view (GET /fund/mechanics) could not be read — its
                sections are absent from this page rather than drawn empty.
              </p>
            )}
          </>
        )}
      </div>
    </>
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
        <p className="mt-1 flex flex-wrap gap-1.5">
          {fold.seats.length === 0 ? (
            <span className={`text-sm ${KT.muted}`}>—</span>
          ) : (
            fold.seats.map((s) => (
              isSeat(s) ? (
                <Link key={s} href={`/clark/studio/desk/${s}`}
                      className={`font-mono text-[11px] ${KT.accent} hover:underline`}>
                  {s}
                </Link>
              ) : (
                <span key={s} className={`font-mono text-[11px] ${KT.muted}`}>{s}</span>
              )
            ))
          )}
        </p>
      </div>
    </div>
  );
}
