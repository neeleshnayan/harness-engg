"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";

import { fundApiClient } from "@/lib/fund_api";
import { StudioHeader } from "../components/StudioHeader";
import { KT } from "../theme";
import { readState, readError } from "../desk/deskRead";
import {
  engineHeadline,
  fateBuckets,
  impliedCaveat,
  ledgerAbsence,
  ledgerTruncation,
  unclassifiedNote,
  reconcileHeadline,
  sortedSymbolRows,
  driftExplanation,
  syncWord,
  syncTone,
  unknownsList,
  venueNote,
  type EngineView,
  type EngineSymbolRow,
  type SignalRow,
  type Tone,
} from "./engineView";

/**
 * ENGINE — what LEAN is doing, what it raised, and whether the books agree.
 *
 * TWO CEO SENTENCES, one page (2026-08-26): *"Lean should publish to our UI and
 * DB what is filling vs whats not and our books should reconcile"* and *"can
 * you also add some UI element that helps me see whats hppening on Lean."*
 *
 * The measured reason it exists: a live LEAN session keeps its OWN paper book,
 * which agrees with the fund's only while every signal it raises is approved.
 * The first DECLINED signal makes them part, after which the engine eventually
 * proposes an exit for stock the fund does not hold. That has already happened
 * on this record — GLD, 2026-08-16 — and no surface showed it.
 *
 * NOTHING HERE ACTS. No button, no halt, no threshold. It is a reading, and
 * every unknown on it is a word rather than a zero (theme.ts, clause 2).
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

export default function EnginePage() {
  const [view, setView] = useState<EngineView | null>(null);
  const [failed, setFailed] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setView(await fundApiClient.getEngine());
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

  const head = engineHeadline(status);
  const recon = reconcileHeadline(leg);
  const buckets = fateBuckets(ledger);
  const absence = ledgerAbsence(ledger);
  const truncated = ledgerTruncation(ledger);
  const unclassified = unclassifiedNote(ledger);
  const caveat = impliedCaveat(leg);
  const rows = sortedSymbolRows(leg);
  const unknowns = unknownsList(view);
  const venue = venueNote(ledger);

  return (
    <div className={KT.page}>
      <StudioHeader
        subtitle="Engine — what LEAN is doing, what it raised, and whether the books agree"
        actions={
          <button onClick={() => void load()} className={KT.btnGhost} disabled={busy}>
            {busy ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          </button>
        }
      />

      <div className={`${KT.container} space-y-4`}>
        {/* ------------------------------------------------ the read itself */}
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
            {/* --------------------------------------------- is it running? */}
            <Panel
              title="Is LEAN running"
              subtitle="A session that is silent and a session that is dead look identical from here — so this never guesses."
              right={
                <span className={`rounded-full border px-2.5 py-0.5 text-[11px] ${TONE_CHIP[head.tone]}`}>
                  {head.word}
                </span>
              }
            >
              <div className="space-y-3 px-5 py-4">
                <div className={`text-sm ${KT.body}`}>{head.sentence}</div>

                <div className="grid gap-3 sm:grid-cols-3">
                  <div className={`${KT.inset} px-4 py-3`}>
                    <div className={KT.label}>Last signal, any engine</div>
                    <div className={`mt-1 font-mono text-sm ${status?.last_signal_at ? "text-[var(--kt-text)]" : KT.muted}`}>
                      {status?.last_signal_at ? stamp(status.last_signal_at) : "NEVER"}
                    </div>
                    <div className={`mt-1 text-[10px] ${KT.muted}`}>{status?.last_signal_scope}</div>
                  </div>
                  <div className={`${KT.inset} px-4 py-3`}>
                    <div className={KT.label}>Last bar seen</div>
                    <div className={`mt-1 font-mono text-sm ${KT.muted}`}>
                      {status?.last_bar_seen ?? "UNKNOWN"}
                    </div>
                    <div className={`mt-1 text-[10px] ${KT.muted}`}>
                      The engine does not report one.
                    </div>
                  </div>
                  <div className={`${KT.inset} px-4 py-3`}>
                    <div className={KT.label}>Sessions on record</div>
                    <div className="mt-1 font-mono text-sm text-[var(--kt-text)]">
                      {status?.sessions_readable === false ? "UNREADABLE" : status?.sessions.length ?? 0}
                    </div>
                    <div className={`mt-1 text-[10px] ${KT.muted}`}>
                      Sessions live in the spine&rsquo;s memory and do not survive a restart.
                    </div>
                  </div>
                </div>

                {(status?.sessions ?? []).map((s) => (
                  <div key={s.session_id ?? Math.random()} className={`${KT.inset} px-4 py-3`}>
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <div className={KT.title}>{s.algorithm ?? "unnamed algorithm"}</div>
                      <div className={`font-mono text-[11px] ${KT.muted}`}>
                        {s.state ?? "state unknown"} · started {stamp(s.started_at)}
                      </div>
                    </div>
                    {s.error && (
                      <div className="mt-1 text-[12px] text-[var(--kt-down)]">{s.error}</div>
                    )}
                    {s.log_tail_pending ? (
                      <div className={`mt-2 text-[11px] ${KT.muted}`}>
                        No log yet — the engine&rsquo;s output is captured when the session
                        ENDS, so an empty log here means &ldquo;not captured&rdquo;, not
                        &ldquo;nothing happened&rdquo;.
                      </div>
                    ) : (
                      (s.log_tail ?? []).length > 0 && (
                        <pre className={`mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-[11px] ${KT.muted}`}>
                          {(s.log_tail ?? []).join("\n")}
                        </pre>
                      )
                    )}
                  </div>
                ))}
              </div>
            </Panel>

            {/* ------------------------------------------- do the books agree */}
            <Panel
              title="Do the books agree"
              subtitle="The third reconciliation leg: the engine against the fund's own fold. Read-only — nothing acts on it."
              right={
                <span className={`rounded-full border px-2.5 py-0.5 text-[11px] ${TONE_CHIP[recon.tone]}`}>
                  {recon.word}
                </span>
              }
            >
              <div className="space-y-3 px-5 py-4">
                <div className={`text-sm ${TONE_TEXT[recon.tone]}`}>{recon.sentence}</div>
                {caveat && (
                  <div className={`${KT.inset} px-4 py-3 text-[11px] ${KT.muted}`}>{caveat}</div>
                )}

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
                            <td className="py-2 pr-4"><Qty v={r.engine_implied_qty} /></td>
                            <td className="py-2 pr-4"><Qty v={r.book_qty} /></td>
                            <td className="py-2 pr-4"><Qty v={r.drift} unknown="—" /></td>
                            <td className={`py-2 text-[11px] ${TONE_TEXT[syncTone(r.in_sync)]}`}>
                              {syncWord(r.in_sync)}
                              {driftExplanation(r) && (
                                <div className={`mt-1 text-[10px] ${KT.muted}`}>{driftExplanation(r)}</div>
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

            {/* ------------------------------------- what filled and what did not */}
            <Panel
              title="What filled and what did not"
              subtitle="Every signal an engine has raised, and the fate of each one."
              right={
                <span className={`font-mono text-[11px] ${KT.muted}`}>
                  {ledger?.total ?? 0} signal{(ledger?.total ?? 0) === 1 ? "" : "s"}
                </span>
              }
            >
              <div className="space-y-3 px-5 py-4">
                <div className="grid gap-2 sm:grid-cols-5">
                  {buckets.map((b) => (
                    <div key={b.fate} className={`${KT.inset} px-3 py-2`} title={b.help}>
                      <div className={KT.label}>{b.label}</div>
                      {/* countTone, not tone: a zero is quiet whatever bucket
                          it is in. Measured — the live reading's only real
                          count was the dimmest figure on the strip. */}
                      <div className={`mt-0.5 font-mono tabular-nums text-xl font-light ${TONE_TEXT[b.countTone]}`}>
                        {b.n}
                      </div>
                    </div>
                  ))}
                </div>
                <div className={`text-[10px] ${KT.muted}`}>
                  &ldquo;Awaiting a click&rdquo; is not a failure — nobody has decided yet.
                  &ldquo;Refused&rdquo; is a decision somebody took.
                </div>

                {venue && (
                  <div className={`${KT.inset} px-4 py-3 text-[11px] ${KT.muted}`}>{venue}</div>
                )}
                {unclassified && (
                  <div className={`${KT.inset} border-[var(--kt-warn)]/40 px-4 py-3 text-[11px] text-[var(--kt-warn)]`}>
                    {unclassified}
                  </div>
                )}

                {absence ? (
                  <div className={`${KT.inset} px-4 py-3 text-[12px] ${KT.muted}`}>{absence}</div>
                ) : (
                  <>
                    {truncated && <div className={`text-[11px] ${KT.muted}`}>{truncated}</div>}
                    <div className="space-y-2">
                      {(ledger?.signals ?? []).map((s: SignalRow) => {
                        const tone = (buckets.find((b) => b.fate === s.outcome)?.tone ?? "quiet") as Tone;
                        return (
                          <div key={s.order_id} className={`${KT.inset} px-4 py-3`}>
                            <div className="flex flex-wrap items-baseline justify-between gap-2">
                              <div className="flex items-baseline gap-2">
                                <span className="font-mono text-sm text-[var(--kt-text-strong)]">
                                  {s.side?.toUpperCase()} {s.qty} {s.symbol}
                                </span>
                                <span className={`rounded-full border px-2 py-0.5 text-[10px] ${TONE_CHIP[tone]}`}>
                                  {s.status}
                                </span>
                              </div>
                              <span className={`font-mono text-[11px] ${KT.muted}`}>
                                {s.source ?? "unknown source"}
                                {s.algo_id ? ` · ${s.algo_id}` : " · algorithm not stated"}
                                {" · "}{stamp(s.raised_at)}
                              </span>
                            </div>
                            {s.reason && <div className={`mt-1 text-[12px] ${KT.body}`}>{s.reason}</div>}
                            <div className={`mt-1 text-[11px] ${KT.muted}`}>
                              {s.strategy_name ?? s.strategy_id ?? "unattributed"}
                              {s.decided_by ? ` · decided by ${s.decided_by} at ${stamp(s.decided_at)}` : " · nobody has decided"}
                              {s.filled_qty != null ? ` · filled ${s.filled_qty} @ ${s.avg_price}` : ""}
                              {s.failure_reason ? ` · ${s.failure_reason}` : ""}
                            </div>
                            {(s.annotations ?? []).length > 0 && (
                              <div className={`mt-1 text-[10px] ${KT.muted}`}>
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
                  </>
                )}
              </div>
            </Panel>

            {/* ------------------------------------------- what this cannot say */}
            {unknowns.length > 0 && (
              <Panel
                title="What this page cannot tell you"
                subtitle="Named, because a blank region gets filled in optimistically."
              >
                <ul className={`space-y-2 px-5 py-4 text-[12px] ${KT.muted}`}>
                  {unknowns.map((u, i) => <li key={i}>· {u}</li>)}
                </ul>
              </Panel>
            )}

            <div className={`text-[10px] ${KT.muted}`}>
              Read over {ledger?.domain?.events_scanned?.toLocaleString() ?? "?"} events
              {ledger?.domain?.seq_first != null && ledger?.domain?.seq_last != null
                ? ` (seq ${ledger.domain.seq_first}–${ledger.domain.seq_last})`
                : ""}
              {ledger?.domain?.window_bound ? " — THE WINDOW BOUND; older signals are unread." : "."}
              {" "}Nothing on this page writes, halts, or crosses a threshold.
            </div>
          </>
        )}
      </div>
    </div>
  );
}
