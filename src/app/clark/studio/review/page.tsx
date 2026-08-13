"use client";

import React, { useCallback, useEffect, useState } from "react";
import { spineError } from "@/lib/spine_error";
import { StudioHeader } from "../components/StudioHeader";
import { KT } from "../theme";
import { fundApiClient, StrategyView } from "@/lib/fund_api";

/**
 * REVIEW — how it went, and the input to the next decision.
 *
 * Attribution (realized vs unrealized), the NAV record, and the audit trail.
 * Every number here comes from the spine; anything the spine cannot answer is
 * shown as an empty state rather than filled in.
 */

const money = (n?: number | null, dp = 2) =>
  n == null
    ? "—"
    : `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp })}`;
const signed = (n?: number | null) =>
  n == null ? "—" : `${n >= 0 ? "+" : ""}${money(n)}`;
const toneOf = (n?: number | null) => (n == null ? KT.muted : n >= 0 ? KT.up : KT.down);

export default function ReviewPage() {
  const [strategies, setStrategies] = useState<StrategyView[]>([]);
  const [navHistory, setNavHistory] = useState<{ ts?: string; total_nav_usd: number }[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [s, nh, ev] = await Promise.all([
        fundApiClient.getStrategies(),
        fundApiClient.getNavHistory(90),
        fundApiClient.getEvents(60).catch(() => ({ events: [] })),
      ]);
      setStrategies(s.strategies || []);
      setNavHistory(nh.history || []);
      setEvents(ev.events || []);
      setErr(null);
    } catch (e: any) {
      setErr(spineError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Only strategies the spine has attribution for; no zero-filling.
  const attributed = strategies.filter(
    (s) => s.realized_pnl_usd != null || s.unrealized_pnl_usd != null || s.pnl_usd != null,
  );
  const totalRealized = attributed.reduce((a, s) => a + (s.realized_pnl_usd ?? 0), 0);
  const totalUnrealized = attributed.reduce((a, s) => a + (s.unrealized_pnl_usd ?? 0), 0);

  const first = navHistory[0]?.total_nav_usd;
  const last = navHistory[navHistory.length - 1]?.total_nav_usd;
  const periodPnl = first != null && last != null ? last - first : null;

  return (
    <div className={KT.page}>
      <StudioHeader subtitle="Attribution, post-mortems and the audit trail" />

      <div className="mx-auto max-w-[1600px] px-6 py-6">
        {err && (
          <div className={`mb-4 p-3 text-sm ${KT.inset} ${KT.down}`}>
            {err}
          </div>
        )}

        {/* headline: the split the spine can now actually make */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className={KT.card}>
            <div className={KT.label}>Realized P&amp;L</div>
            <div className={`mt-1 ${KT.numberLg} ${toneOf(totalRealized)}`}>
              {attributed.length ? signed(totalRealized) : "—"}
            </div>
            <div className={`mt-1 text-[11px] ${KT.muted}`}>Locked in by closed trades</div>
          </div>
          <div className={KT.card}>
            <div className={KT.label}>Unrealized P&amp;L</div>
            <div className={`mt-1 ${KT.numberLg} ${toneOf(totalUnrealized)}`}>
              {attributed.length ? signed(totalUnrealized) : "—"}
            </div>
            <div className={`mt-1 text-[11px] ${KT.muted}`}>Mark-to-market on open positions</div>
          </div>
          <div className={KT.card}>
            <div className={KT.label}>NAV change over period</div>
            <div className={`mt-1 ${KT.numberLg} ${toneOf(periodPnl)}`}>{signed(periodPnl)}</div>
            <div className={`mt-1 text-[11px] ${KT.muted}`}>
              {navHistory.length ? `${navHistory.length} recorded valuations` : "No valuations recorded yet"}
            </div>
          </div>
        </div>

        {/* per-strategy attribution */}
        <div className={`mt-6 ${KT.panel}`}>
          <div className={`border-b border-[var(--kt-border)] px-5 py-3 ${KT.label}`}>
            Attribution by strategy
          </div>
          {loading ? (
            <div className={`px-5 py-8 text-sm ${KT.muted}`}>Loading…</div>
          ) : attributed.length === 0 ? (
            <div className={`px-5 py-8 text-sm ${KT.muted}`}>
              No attribution yet — it appears once a strategy has filled orders.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className={`border-b border-[var(--kt-border)] ${KT.label}`}>
                    <th className="px-5 py-2 text-left font-normal">Strategy</th>
                    <th className="px-5 py-2 text-right font-normal">Gross Exposure</th>
                    <th className="px-5 py-2 text-right font-normal">Cost Basis</th>
                    <th className="px-5 py-2 text-right font-normal">Realized</th>
                    <th className="px-5 py-2 text-right font-normal">Unrealized</th>
                    <th className="px-5 py-2 text-right font-normal">Total P&amp;L</th>
                  </tr>
                </thead>
                <tbody>
                  {attributed.map((s) => (
                    <tr key={s.strategy_id} className="border-b border-[var(--kt-border)] last:border-0">
                      <td className="px-5 py-2.5">{s.name}</td>
                      <td className={`px-5 py-2.5 text-right ${KT.number}`}>{money(s.exposure_usd)}</td>
                      <td className={`px-5 py-2.5 text-right ${KT.number}`}>{money(s.cost_basis_usd)}</td>
                      <td className={`px-5 py-2.5 text-right font-mono tabular-nums ${toneOf(s.realized_pnl_usd)}`}>
                        {signed(s.realized_pnl_usd)}
                      </td>
                      <td className={`px-5 py-2.5 text-right font-mono tabular-nums ${toneOf(s.unrealized_pnl_usd)}`}>
                        {signed(s.unrealized_pnl_usd)}
                      </td>
                      <td className={`px-5 py-2.5 text-right font-mono tabular-nums ${toneOf(s.pnl_usd)}`}>
                        {signed(s.pnl_usd)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* audit trail — the fund's memory */}
        <div className={`mt-6 ${KT.panel}`}>
          <div className={`border-b border-[var(--kt-border)] px-5 py-3 ${KT.label}`}>Audit trail</div>
          {events.length === 0 ? (
            <div className={`px-5 py-8 text-sm ${KT.muted}`}>No events recorded.</div>
          ) : (
            <ul className="max-h-[420px] divide-y divide-[var(--kt-border)] overflow-y-auto">
              {events.map((e, i) => (
                <li key={e.seq ?? i} className="flex items-baseline gap-3 px-5 py-2 text-[12px]">
                  <span className={`w-14 shrink-0 font-mono tabular-nums ${KT.muted}`}>#{e.seq}</span>
                  <span className="w-44 shrink-0 truncate font-medium">{e.type}</span>
                  <span className={`shrink-0 font-mono text-[11px] ${KT.muted}`}>
                    {String(e.ts ?? "").slice(0, 19).replace("T", " ")}
                  </span>
                  <span className={`truncate ${KT.muted}`}>{e.actor}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
