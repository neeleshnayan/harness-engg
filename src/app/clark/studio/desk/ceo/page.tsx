"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { fundApiClient, DeskView, PendingOrder } from "@/lib/fund_api";
import { KT } from "../../theme";
import { StudioHeader } from "../../components/StudioHeader";
import { memoParts } from "../../memo";
import { SeatFace } from "../SeatFace";
import { RecRow } from "../components";
import { dayKey } from "../seatLib";

/**
 * The CEO's desk — everything awaiting Neelesh's click, in one place.
 *
 * Lean v1 (CEO-blessed design, docs/briefs/EXEC_DESKS_2026-08-20.md; the
 * builder's next dispatch upgrades it). Three panels, ranked the way the coo
 * seat ranks: money first (pending orders, with the 120-minute freshness
 * clock), then open recommendations, then the CEO's own decision velocity.
 * The halt state is NOT restated here — the RiskBar in the shell owns "is
 * anything broken" (design audit: say the alarm once).
 */
export default function CeoDeskPage() {
  const [desk, setDesk] = useState<DeskView | null>(null);
  const [pending, setPending] = useState<PendingOrder[] | null>(null);
  const [decidedToday, setDecidedToday] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [d, p, ev] = await Promise.allSettled([
      fundApiClient.getDesk(),
      fundApiClient.getPending(),
      fundApiClient.getEvents(1000, 0),
    ]);
    if (d.status === "fulfilled") { setDesk(d.value); setErr(null); }
    else setErr(d.reason instanceof Error ? d.reason.message : "unreachable");
    setPending(p.status === "fulfilled" ? (p.value.pending || []) : null);
    if (ev.status === "fulfilled") {
      const today = dayKey(new Date().toISOString());
      setDecidedToday((ev.value.events || []).filter((e) =>
        (e.type === "DeskRecommendationDecided" || e.type === "DeskRequestApproved")
        && dayKey(e.ts) === today).length);
    } else {
      setDecidedToday(null);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  const recs = desk?.open_recommendations ?? [];

  return (
    <div className="min-h-screen bg-[var(--kt-bg)] text-[var(--kt-text)]">
      <StudioHeader subtitle="The CEO's desk — everything awaiting your click" />
      <div className={KT.container}>
        <header className="mb-7 flex items-center gap-4">
          <SeatFace actor="ceo" size={64} />
          <div>
            <p className={KT.label}>Krypton Fund · the corner office</p>
            <h1 className="text-2xl font-medium tracking-tight">Neelesh · CEO</h1>
            <p className={`mt-0.5 text-xs ${KT.muted}`}>
              decisions recorded today:{" "}
              <span className="font-mono tabular-nums">
                {decidedToday ?? "— (event log unreadable, not zero)"}
              </span>
              {" "}· <Link href="/clark/studio/desk" className={`${KT.accent} hover:underline`}>back to the floor</Link>
            </p>
          </div>
        </header>

        {err && (
          <div className={`${KT.card} mb-6 flex items-start gap-2 border-[var(--kt-warn)]`}>
            <AlertTriangle size={15} className="mt-0.5 text-[var(--kt-warn)]" />
            <p className="text-sm">The desk could not be read — what waits on you is unknown, not empty. {err}</p>
          </div>
        )}

        <section className="mb-8">
          <p className={`${KT.label} mb-2`}>Orders awaiting your approval</p>
          {pending === null ? (
            <p className={`text-sm ${KT.sev.warn}`}>
              The approval queue is unreadable — anything waiting is still waiting.
            </p>
          ) : pending.length === 0 ? (
            <p className={`text-sm ${KT.muted}`}>Nothing pending at the venue.</p>
          ) : (
            <div className="space-y-1.5">
              {pending.map((o) => {
                const m = memoParts(o.rationale);
                const age = o.age_minutes;
                const expiresIn = age != null ? Math.max(0, 120 - age) : null;
                return (
                  <div key={o.order_id}
                       className={`${KT.card} flex flex-wrap items-baseline gap-x-3 gap-y-1 p-3 text-sm`}>
                    <span className="font-semibold uppercase">{o.side}</span>
                    <span className="font-mono tabular-nums">{o.qty}</span>
                    <span className="font-semibold">{o.symbol}</span>
                    <span className="min-w-0 flex-1 truncate text-[12px]">{m.headline}</span>
                    <span className={`font-mono text-[10px] tabular-nums ${
                      expiresIn != null && expiresIn < 30 ? "text-[var(--kt-warn)]" : KT.muted}`}>
                      {expiresIn != null
                        ? `expires in ~${Math.round(expiresIn)}m`
                        : "age unknown"}
                    </span>
                  </div>
                );
              })}
              <p className={`text-[11px] italic ${KT.muted}`}>
                Approve and decline live on <Link href="/clark/studio" className={`${KT.accent} hover:underline`}>Monitor</Link> — one approval surface, deliberately.
              </p>
            </div>
          )}
        </section>

        <section className="mb-8">
          <p className={`${KT.label} mb-2`}>
            Recommendations awaiting your decision ({recs.length})
          </p>
          {desk && recs.length === 0 && (
            <p className={`text-sm ${KT.muted}`}>Nothing awaiting you — the bench owes you no decisions right now.</p>
          )}
          <div className="space-y-1.5">
            {recs.map((r) => (
              <RecRow key={`${r.run_id}-${r.rec_id}`} r={r} onDecide={load} />
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
