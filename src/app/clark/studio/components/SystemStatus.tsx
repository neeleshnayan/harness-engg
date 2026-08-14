"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { spineError } from "@/lib/spine_error";
import { KT } from "../theme";
import { ComplianceStatus, LedgerVerification, SpineEvent, fundApiClient } from "@/lib/fund_api";

/**
 * What is actually working, and the event log tailing underneath it.
 *
 * The rule this panel is built on: **a component reports healthy only when
 * something it produced proves it.** A scheduler that says "running" is worth
 * nothing; a scheduler whose NAV samples are advancing has proved it. So each
 * row here is derived from an observable artefact, and where no artefact exists
 * the row says "unknown" rather than green.
 *
 * That distinction is not pedantry. The settlement poller ran on a 300-second
 * interval for a whole session — every self-reported health check would have
 * said "scheduler: OK" while a fill sat unrecorded for five minutes.
 *
 * The log below is the fund's own event stream, not console output. Console
 * lines are noise a developer reads; these are the facts the fund is made of,
 * and the same rows the audit trail is built from.
 */

type Level = "ok" | "warn" | "bad" | "unknown";

const DOT: Record<Level, string> = {
  ok: "bg-[var(--kt-accent)]",
  warn: "bg-[var(--kt-warn)]",
  bad: "bg-[var(--kt-down)]",
  unknown: "bg-[var(--kt-text-dim)]",
};

const EVENT_TONE = (t: string) =>
  t.includes("Rejected") || t.includes("Failed") || t.includes("Halted") ? KT.down
    : t.includes("Filled") || t.includes("Resumed") ? KT.up
    : t.includes("Alarm") ? "text-[var(--kt-warn)]"
    : KT.muted;

export function SystemStatus({ refreshSignal = 0 }: { refreshSignal?: number }) {
  const [book, setBook] = useState<Record<string, unknown> | null>(null);
  const [events, setEvents] = useState<SpineEvent[] | null>(null);
  const [intraday, setIntraday] = useState<{ n: number; to_ts: string | null } | null>(null);
  const [drift, setDrift] = useState<{ symbols_out_of_sync?: number } | null>(null);
  const [halted, setHalted] = useState<boolean | null>(null);
  const [compliance, setCompliance] = useState<ComplianceStatus | null>(null);
  const [ledger, setLedger] = useState<LedgerVerification | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [b, ev, intr, dr, risk, comp, chain] = await Promise.all([
        fundApiClient.getBookIdentity(),
        fundApiClient.getEvents(40),
        fundApiClient.getIntradayNav(30).catch(() => null),
        fundApiClient.getVenueReconcile().catch(() => null),
        fundApiClient.getRiskMonitor().catch(() => null),
        fundApiClient.getCompliance().catch(() => null),
        fundApiClient.verifyLedger().catch(() => null),
      ]);
      setBook(b as Record<string, unknown>);
      setEvents(ev.events || []);
      setIntraday(intr ? { n: intr.n, to_ts: intr.to_ts } : null);
      setDrift(dr);
      setHalted(risk ? risk.halted : null);
      setCompliance(comp);
      setLedger(chain);
      setErr(null);
    } catch (e: unknown) {
      setErr(spineError(e));
      setBook(null);
      setEvents(null);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load, refreshSignal]);

  const rows = useMemo(() => {
    const out: { label: string; level: Level; detail: string }[] = [];

    out.push(err || !book
      ? { label: "Spine", level: "bad", detail: err || "unreachable" }
      : { label: "Spine", level: "ok", detail: "reachable" });

    if (book) {
      const prod = book.is_production === true;
      out.push({
        label: "Book",
        level: prod ? "bad" : "ok",
        detail: prod
          ? `PRODUCTION (${book.project_id}) — the real ledger`
          : `${book.env} · ${book.project_id}`,
      });
      out.push({
        label: "Orders",
        level: book.orders_are_real ? "warn" : "ok",
        detail: book.orders_are_real
          ? `real, to ${book.venue}`
          : "simulated — nothing reaches a venue",
      });
    }

    // The scheduler proves itself by producing samples. Anything else is a
    // claim; a fresh sample is evidence.
    if (intraday?.to_ts) {
      const ageS = (Date.now() - new Date(intraday.to_ts).getTime()) / 1000;
      out.push({
        label: "Scheduler",
        level: ageS < 180 ? "ok" : ageS < 600 ? "warn" : "bad",
        detail: `last NAV sample ${ageS < 90 ? "just now" : `${Math.round(ageS / 60)}m ago`}`
          + ` · ${intraday.n} in 30m`,
      });
    } else {
      out.push({ label: "Scheduler", level: "unknown",
                 detail: "no samples yet — cannot confirm it is running" });
    }

    if (drift) {
      const n = drift.symbols_out_of_sync ?? 0;
      out.push({
        label: "Ledger vs broker",
        level: n === 0 ? "ok" : "bad",
        detail: n === 0 ? "every position agrees" : `${n} position(s) diverge`,
      });
    } else {
      out.push({ label: "Ledger vs broker", level: "unknown",
                 detail: "reconciler unreachable — divergence unknown" });
    }

    out.push(halted === null
      ? { label: "Trading", level: "unknown", detail: "halt state unreadable" }
      : halted
        ? { label: "Trading", level: "bad", detail: "HALTED — buys blocked" }
        : { label: "Trading", level: "ok", detail: "active" });

    // The day-trade budget. Unlike every other row here this one is a cliff:
    // the fourth day trade in five sessions restricts the account to
    // closing-only for ninety days, so the useful number is how many are left
    // — and it has to be readable BEFORE an order is proposed, not at the
    // rejection. Counted from our own event log when the broker does not
    // report it, which on the paper venue is always.
    if (compliance?.pdt?.applies) {
      const { remaining, used, max_day_trades, source, diverges } = compliance.pdt;
      const left = remaining ?? 0;
      out.push({
        label: "Day-trade budget",
        level: left <= 0 ? "bad" : left === 1 ? "warn" : "ok",
        detail: `${used}/${max_day_trades} used · ${left} left before a 90-day`
          + ` restriction · via ${source}${diverges ? " (counts disagree)" : ""}`,
      });
    } else if (compliance && !compliance.pdt.applies) {
      out.push({ label: "Day-trade budget", level: "ok",
                 detail: "above $25k — the rule does not restrict this account" });
    }

    // Tamper evidence. "Append-only" is a description of how we write, not a
    // property anyone outside can check — this row is the check. An unchained
    // prefix is reported as unproved rather than green, because events written
    // before the chain existed cannot be verified after the fact and saying
    // otherwise would be the exact dishonesty the chain exists to prevent.
    if (ledger) {
      out.push(
        !ledger.ok
          ? { label: "Ledger integrity", level: "bad",
              detail: `BROKEN at seq ${ledger.first_break?.seq ?? "?"} — ${ledger.first_break?.reason ?? "chain does not hold"}` }
          : ledger.chained === 0
            ? { label: "Ledger integrity", level: "warn",
                detail: `no tamper evidence — all ${ledger.unchained} events predate the chain` }
            : ledger.unchained > 0
              ? { label: "Ledger integrity", level: "warn",
                  detail: `${ledger.chained} chained, ${ledger.unchained} predate the chain (unproved)` }
              : { label: "Ledger integrity", level: "ok",
                  detail: `all ${ledger.chained} events chained and verified` },
      );
    } else {
      out.push({ label: "Ledger integrity", level: "unknown",
                 detail: "chain unreadable — tampering would not be visible" });
    }

    // A silent event log on a live fund is itself a signal.
    if (events && events.length) {
      const newest = events[0]?.ts;
      const ageM = newest ? (Date.now() - new Date(newest).getTime()) / 60000 : null;
      out.push({
        label: "Event log",
        level: "ok",
        detail: ageM == null ? `${events.length} recent`
          : `newest ${ageM < 1 ? "just now" : `${Math.round(ageM)}m ago`}`,
      });
    }

    return out;
  }, [book, err, intraday, drift, halted, events, compliance, ledger]);

  return (
    <div className={KT.panel}>
      <div className="flex items-center justify-between border-b border-[var(--kt-border)] px-5 py-3">
        <div>
          <span className={KT.label}>System status</span>
          <div className={`mt-1 text-[11px] ${KT.muted}`}>
            Each row is derived from something the component actually produced —
            a self-reported &quot;OK&quot; proves nothing.
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-x-6 gap-y-1.5 px-5 py-3 sm:grid-cols-2 lg:grid-cols-3">
        {rows.map((r) => (
          <div key={r.label} className="flex items-baseline gap-2 text-[12px]">
            <span className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${DOT[r.level]}`} />
            <span className="shrink-0 font-medium">{r.label}</span>
            <span className={`truncate ${r.level === "bad" ? KT.down
              : r.level === "warn" ? "text-[var(--kt-warn)]" : KT.muted}`}>
              {r.detail}
            </span>
          </div>
        ))}
      </div>

      {/* The fund's own event stream, newest first. */}
      <div className="border-t border-[var(--kt-border)]">
        <div className={`px-5 py-2 ${KT.label}`}>Event log</div>
        <div className="max-h-[220px] overflow-auto bg-[var(--kt-inset,rgba(0,0,0,0.25))] px-5 py-2 font-mono text-[11px] leading-relaxed">
          {events === null ? (
            <div className={KT.down}>event log unreadable — this is not an empty log</div>
          ) : events.length === 0 ? (
            <div className={KT.muted}>no events yet</div>
          ) : (
            events.map((e) => (
              <div key={e.event_id ?? `${e.seq}`} className="whitespace-nowrap">
                <span className={KT.muted}>{String(e.ts ?? "").slice(11, 19)}</span>{" "}
                <span className={KT.muted}>#{e.seq}</span>{" "}
                <span className={EVENT_TONE(e.type)}>{e.type}</span>{" "}
                <span className={KT.muted}>
                  {summarise(e)}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

/** One line of the payload that actually says what happened. */
function summarise(e: SpineEvent): string {
  const p = e.payload || {};
  const bits: string[] = [];
  if (p.side && p.symbol) bits.push(`${p.side} ${p.qty ?? p.filled_qty ?? ""} ${p.symbol}`.trim());
  else if (p.symbol) bits.push(String(p.symbol));
  if (p.avg_price) bits.push(`@ ${p.avg_price}`);
  if (p.usd_amount) bits.push(`$${p.usd_amount}`);
  if (p.message) bits.push(String(p.message));
  if (Array.isArray(p.breaches) && p.breaches.length) bits.push(p.breaches[0]);
  if (p.approver) bits.push(`by ${p.approver}`);
  if (p.reason) bits.push(String(p.reason));
  return bits.join(" ").slice(0, 120);
}
