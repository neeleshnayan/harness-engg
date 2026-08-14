"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { KT } from "../theme";
import { MarketSessionResponse, fundApiClient } from "@/lib/fund_api";

/**
 * Whether the venue is open, and how long until that changes.
 *
 * Lives in the header because almost everything on every other surface is
 * downstream of it. A flat NAV chart, an empty signals table, a proposal that
 * will not execute for six hours — each of those reads as a fault until you
 * know the market is shut, and the operator should never have to work that out
 * from the shape of a chart.
 *
 * Two deliberate choices:
 *
 *  - The countdown ticks locally between polls. The spine is asked every 60s;
 *    the number on screen moves every second. Polling once a second to animate
 *    a clock would be a request per second per open tab for information that is
 *    entirely predictable in between.
 *
 *  - Both zones are shown. The venue runs on New York time and the operator
 *    does not, so a bare "16:00" is a small trap. The market's own time is the
 *    one that governs, so it leads.
 *
 * `is_open === null` is rendered as its own state, never as closed. The spine
 * is careful to keep "unknown" distinct from "shut" all the way through, and
 * collapsing it here would throw that away at the last step.
 */

type Tone = "open" | "edge" | "shut" | "unknown";

const DOT: Record<Tone, string> = {
  open: "bg-[var(--kt-accent)]",
  edge: "bg-[var(--kt-warn)]",
  shut: "bg-[var(--kt-text-dim)]",
  unknown: "bg-[var(--kt-down)]",
};

const TEXT: Record<Tone, string> = {
  open: "text-[var(--kt-accent)]",
  edge: "text-[var(--kt-warn)]",
  shut: KT.muted,
  unknown: KT.down,
};

const LABEL: Record<MarketSessionResponse["phase"], string> = {
  regular: "Open",
  "pre-market": "Pre-market",
  "after-hours": "After-hours",
  closed: "Closed",
  weekend: "Weekend",
  unknown: "Clock unreachable",
};

function toneOf(s: MarketSessionResponse): Tone {
  if (s.state === "unknown") return "unknown";
  if (s.state === "open") return "open";
  return s.phase === "pre-market" || s.phase === "after-hours" ? "edge" : "shut";
}

/** "5h 43m", "43m 12s", "12s" — coarse far out, precise near the bell. */
function countdown(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${sec}s`;
  return `${sec}s`;
}

/** 09:30 in the market's own zone, from an ISO string that already carries it. */
function clockIn(iso: string | null, timeZone?: string): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit", minute: "2-digit", hour12: false,
    ...(timeZone ? { timeZone } : {}),
  });
}

export function MarketClock() {
  const [session, setSession] = useState<MarketSessionResponse | null>(null);
  const [fetchedAt, setFetchedAt] = useState<number>(0);
  const [, forceTick] = useState(0);
  const [err, setErr] = useState(false);

  const load = useCallback(async () => {
    try {
      const s = await fundApiClient.getMarketSession();
      setSession(s);
      setFetchedAt(Date.now());
      setErr(false);
    } catch {
      setErr(true);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [load]);

  // Local tick, so the countdown moves without a request behind it.
  useEffect(() => {
    const t = setInterval(() => forceTick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, []);

  const view = useMemo(() => {
    if (err || !session) return null;
    const elapsed = (Date.now() - fetchedAt) / 1000;
    const tone = toneOf(session);
    const label = LABEL[session.phase] ?? "Unknown";

    // Only one of these is ever set — open counts to the close, closed to the
    // open. Subtracting the elapsed time is what makes it tick between polls.
    const raw = session.seconds_to_close ?? session.seconds_to_open ?? null;
    const verb = session.seconds_to_close != null ? "closes" : "opens";
    const remaining = raw == null ? null : raw - elapsed;

    return { tone, label, verb, remaining, session };
  }, [session, fetchedAt, err]);

  if (!view) {
    return (
      <div className={`flex items-center gap-1.5 text-[11px] ${KT.muted}`}>
        <span className={`h-1.5 w-1.5 rounded-full ${DOT.unknown}`} />
        <span>Session unknown</span>
      </div>
    );
  }

  const { tone, label, verb, remaining, session: s } = view;
  const marketTime = clockIn(s.now, s.timezone);
  const target = s.seconds_to_close != null ? s.next_close : s.next_open;

  // The title carries the precision the compact line drops: both zones, and
  // the phase note that says what it means for this fund specifically.
  const title = [
    s.note,
    marketTime ? `Market time ${marketTime} (${s.timezone.split("/")[1]?.replace("_", " ")})` : null,
    target ? `Next ${verb} ${new Date(target).toLocaleString()} your time` : null,
    s.simulated ? "Simulated venue — no exchange session" : null,
  ].filter(Boolean).join("\n");

  return (
    <div className="flex items-center gap-1.5 text-[11px]" title={title}>
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${DOT[tone]}`} />
      <span className={`font-medium ${TEXT[tone]}`}>{label}</span>
      {remaining != null && (
        <span className={KT.muted}>
          · {verb} in <span className="font-mono tabular-nums">{countdown(remaining)}</span>
        </span>
      )}
      {marketTime && (
        <span className={`hidden font-mono tabular-nums lg:inline ${KT.muted}`}>
          · {marketTime} ET
        </span>
      )}
    </div>
  );
}
