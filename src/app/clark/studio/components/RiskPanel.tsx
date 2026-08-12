"use client";

import React, { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Loader2, ShieldAlert, Zap } from "lucide-react";
import { fundApiClient, RiskAnalytics, RiskScenario } from "@/lib/fund_api";
import { AllocationDonut } from "./charts/AllocationDonut";

const money = (n?: number | null) =>
  n == null ? "—" : `$${Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const pct = (n?: number | null, dp = 1) => (n == null ? "—" : `${Number(n).toFixed(dp)}%`);

/** Read-only analytical risk cockpit: concentration + scenario shocks. */
export function RiskPanel({ refreshKey, hideDonut }: { refreshKey?: number; hideDonut?: boolean }) {
  const [data, setData] = useState<RiskAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [shockSym, setShockSym] = useState("");
  const [shockPct, setShockPct] = useState(-20);
  const [custom, setCustom] = useState<RiskScenario | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await fundApiClient.getRiskAnalytics());
    } catch {
      /* spine unreachable — leave prior data */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  const runShock = async () => {
    setBusy(true);
    try {
      setCustom(await fundApiClient.runRiskShock(shockSym.trim().toUpperCase() || null, shockPct));
    } catch {
      setCustom(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl border border-[var(--kt-border)] bg-[var(--kt-surface)]">
      <div className="flex items-center gap-2 border-b border-[var(--kt-border)] px-4 py-2.5">
        <ShieldAlert size={14} className="text-[var(--kt-down)]" />
        <span className="text-sm font-semibold">Risk cockpit</span>
        {data && (
          <span className="ml-auto font-mono text-[10px] text-[var(--kt-text-muted)]">
            HHI {data.concentration_hhi.toFixed(0)}
          </span>
        )}
      </div>

      {loading && !data ? (
        <div className="flex items-center gap-2 p-6 text-sm text-[var(--kt-text-muted)]">
          <Loader2 className="animate-spin" size={16} /> Loading…
        </div>
      ) : !data ? (
        <div className="p-6 text-center text-sm text-[var(--kt-text-muted)]">No risk data.</div>
      ) : (
        <div className="space-y-3 p-3">
          {/* concentration snapshot */}
          <div className="grid grid-cols-3 gap-2 font-mono text-[11px]">
            <div className="rounded-md border border-[var(--kt-border)] bg-[var(--kt-surface)] px-2 py-1.5">
              <div className="text-[9px] uppercase tracking-wide text-[var(--kt-text-muted)]">Cash</div>
              <div className="text-[var(--kt-text)]">{pct(data.cash_pct, 0)}</div>
            </div>
            <div className="rounded-md border border-[var(--kt-border)] bg-[var(--kt-surface)] px-2 py-1.5">
              <div className="text-[9px] uppercase tracking-wide text-[var(--kt-text-muted)]">Gross</div>
              <div className="text-[var(--kt-text)]">{pct(data.gross_exposure_pct, 0)}</div>
            </div>
            <div className="rounded-md border border-[var(--kt-border)] bg-[var(--kt-surface)] px-2 py-1.5">
              <div className="text-[9px] uppercase tracking-wide text-[var(--kt-text-muted)]">Top name</div>
              <div className="text-[var(--kt-text)]">
                {data.largest_position ? `${pct(data.largest_position.weight_pct, 0)}` : "—"}
              </div>
            </div>
          </div>

          {/* Allocation Donut */}
          {!hideDonut && (
            <div className="py-2">
              <AllocationDonut
                positions={data.positions.map(p => ({
                  symbol: p.symbol,
                  qty: p.qty,
                  mark: p.mark,
                  usd_value: p.usd_value
                }))}
                cash={data.cash_usd}
                totalNav={data.nav_usd}
                height={200}
              />
            </div>
          )}

          {/* breach flags */}
          {data.flags.length > 0 && (
            <div className="space-y-1">
              {data.flags.map((f, i) => (
                <div key={i} className="flex items-start gap-1.5 rounded-md border border-amber-800/40 bg-amber-950/20 px-2 py-1 text-[11px] text-[var(--kt-warn)]">
                  <AlertTriangle size={12} className="mt-0.5 shrink-0" /> {f}
                </div>
              ))}
            </div>
          )}

          {/* default stress scenarios */}
          <div>
            <div className="mb-1 text-[10px] font-medium uppercase tracking-widest text-[var(--kt-text-muted)]">Stress scenarios</div>
            <div className="space-y-1">
              {data.scenarios.map((s, i) => (
                <div key={i} className="flex items-center justify-between rounded-md bg-[var(--kt-surface)] px-2 py-1 font-mono text-[11px]">
                  <span className="text-[var(--kt-text-dim)]">{s.label}</span>
                  <span className={s.pnl_usd >= 0 ? "text-[var(--kt-accent)]" : "text-[var(--kt-down)]"}>
                    {money(s.pnl_usd)} ({s.nav_change_pct.toFixed(1)}%)
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* custom what-if */}
          <div className="rounded-md border border-[var(--kt-border)] bg-[var(--kt-surface)] p-2">
            <div className="mb-1.5 flex items-center gap-1 text-[10px] font-medium uppercase tracking-widest text-[var(--kt-text-muted)]">
              <Zap size={11} className="text-[var(--kt-accent)]" /> What-if
            </div>
            <div className="flex items-center gap-1.5">
              <input
                value={shockSym}
                onChange={(e) => setShockSym(e.target.value)}
                placeholder="all"
                className="w-16 rounded border border-[var(--kt-border)] bg-[var(--kt-inset)] px-1.5 py-1 text-xs uppercase outline-none placeholder:text-[var(--kt-text-muted)]"
              />
              <input
                type="number"
                value={shockPct}
                onChange={(e) => setShockPct(Number(e.target.value))}
                className="w-16 rounded border border-[var(--kt-border)] bg-[var(--kt-inset)] px-1.5 py-1 text-right font-mono text-xs outline-none"
              />
              <span className="text-xs text-[var(--kt-text-muted)]">%</span>
              <button
                onClick={runShock}
                disabled={busy}
                className="ml-auto rounded bg-rose-600/90 px-2 py-1 text-[11px] text-[var(--kt-text-strong)] hover:bg-rose-600 disabled:opacity-50"
              >
                {busy ? <Loader2 size={12} className="animate-spin" /> : "Shock"}
              </button>
            </div>
            {custom && (
              <div className="mt-2 flex items-center justify-between rounded bg-[var(--kt-bg)] px-2 py-1 font-mono text-[11px]">
                <span className="text-[var(--kt-text-dim)]">{custom.label}</span>
                <span className={custom.pnl_usd >= 0 ? "text-[var(--kt-accent)]" : "text-[var(--kt-down)]"}>
                  {money(custom.pnl_usd)} → NAV {money(custom.nav_after)}
                </span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
