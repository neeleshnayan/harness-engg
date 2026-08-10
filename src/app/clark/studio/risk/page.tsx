"use client";

import React, { useState, useEffect, useCallback } from "react";
import { StudioHeader } from "../components/StudioHeader";
import { ClarkActionBar } from "../components/ClarkActionBar";
import { GlassPanel } from "../components/ui/GlassPanel";
import { ConcentrationTreemap } from "../components/charts/ConcentrationTreemap";
import { StressGrid, StressScenario } from "../components/ui/StressGrid";
import { AnimatedNumber } from "../components/ui/AnimatedNumber";
import { fundApiClient, RiskAnalytics } from "@/lib/fund_api";
import { Loader2, AlertTriangle, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";

const pct = (n?: number | null, dp = 1) => (n == null ? "—" : `${Number(n).toFixed(dp)}%`);

export default function RiskPage() {
  const [tick, setTick] = useState(0);
  const [data, setData] = useState<RiskAnalytics | null>(null);
  const [loading, setLoading] = useState(true);

  // Custom shock state
  const [shockSym, setShockSym] = useState("");
  const [shockPct, setShockPct] = useState(-20);
  const [busy, setBusy] = useState(false);
  const [customShock, setCustomShock] = useState<StressScenario | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await fundApiClient.getRiskAnalytics());
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, tick]);

  const runShock = async () => {
    setBusy(true);
    try {
      const res = await fundApiClient.runRiskShock(shockSym.trim().toUpperCase() || null, shockPct);
      setCustomShock({
        id: "custom",
        name: res.label,
        description: `Custom ${shockPct}% shock on ${shockSym || "all positions"}`,
        impact_pct: res.nav_change_pct,
        impact_usd: res.pnl_usd,
        is_historical: false,
      });
    } catch {
      setCustomShock(null);
    } finally {
      setBusy(false);
    }
  };

  const stressScenarios: StressScenario[] = (data?.scenarios || []).map((s, i) => ({
    id: `scene-${i}`,
    name: s.label,
    description: "Standard model scenario",
    impact_pct: s.nav_change_pct,
    impact_usd: s.pnl_usd,
    is_historical: s.label.toLowerCase().includes("2008") || s.label.toLowerCase().includes("covid"),
  }));

  if (customShock) {
    stressScenarios.unshift(customShock);
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <StudioHeader subtitle="Risk cockpit — concentration and scenario stress" />
      <div className="mx-auto max-w-[1200px] space-y-6 px-4 py-6">
        <ClarkActionBar
          placeholder="Ask Clark… e.g. 'show the risk' or 'what if AAPL drops 20%'"
          suggestions={["what if AAPL drops 20%", "what if NVDA drops 30%", "show risk flags"]}
          onDone={() => setTick((v) => v + 1)}
        />

        {loading && !data ? (
          <div className="flex items-center justify-center py-20 text-zinc-500">
            <Loader2 className="animate-spin text-teal-500 mr-2" size={24} /> Loading risk analytics...
          </div>
        ) : !data ? (
          <div className="py-20 text-center text-zinc-500">No risk data available.</div>
        ) : (
          <>
            {/* Top KPIs */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <GlassPanel className="p-4 flex flex-col justify-center">
                <span className="text-[10px] font-medium uppercase tracking-widest text-zinc-500 mb-1">Gross Exposure</span>
                <span className="text-2xl font-medium font-mono text-zinc-100">{pct(data.gross_exposure_pct, 1)}</span>
              </GlassPanel>
              <GlassPanel className="p-4 flex flex-col justify-center">
                <span className="text-[10px] font-medium uppercase tracking-widest text-zinc-500 mb-1">Cash Buffer</span>
                <span className="text-2xl font-medium font-mono text-zinc-100">{pct(data.cash_pct, 1)}</span>
              </GlassPanel>
              <GlassPanel className="p-4 flex flex-col justify-center">
                <span className="text-[10px] font-medium uppercase tracking-widest text-zinc-500 mb-1">Concentration (HHI)</span>
                <AnimatedNumber value={data.concentration_hhi} decimals={0} className="text-2xl font-medium font-mono text-amber-400" />
              </GlassPanel>
              <GlassPanel className="p-4 flex flex-col justify-center">
                <span className="text-[10px] font-medium uppercase tracking-widest text-zinc-500 mb-1">Top Position</span>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-medium font-mono text-zinc-100">{pct(data.largest_position?.weight_pct, 1)}</span>
                  <span className="text-sm text-zinc-500">{data.largest_position?.symbol}</span>
                </div>
              </GlassPanel>
            </div>

            {/* Breach Flags */}
            {data.flags.length > 0 && (
              <GlassPanel className="p-4 border-amber-500/30 bg-amber-950/10">
                <div className="flex items-center gap-2 text-amber-400 font-semibold mb-3">
                  <AlertTriangle size={18} /> Risk Limits Breached
                </div>
                <div className="space-y-2">
                  {data.flags.map((f, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm text-amber-300 bg-amber-950/40 p-2 rounded border border-amber-800/30">
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                      {f}
                    </div>
                  ))}
                </div>
              </GlassPanel>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Treemap */}
              <GlassPanel title="Portfolio Concentration" className="flex flex-col">
                <div className="flex-1 min-h-[350px]">
                  <ConcentrationTreemap
                    positions={data.positions.map(p => ({ symbol: p.symbol, usd_value: p.usd_value }))}
                    totalNav={data.nav_usd}
                    height={350}
                  />
                </div>
              </GlassPanel>

              {/* Stress Scenarios */}
              <div className="space-y-6 flex flex-col">
                <StressGrid scenarios={stressScenarios} />
                
                <GlassPanel title="Custom What-If Shock">
                  <div className="flex flex-col gap-3 pt-2">
                    <p className="text-sm text-zinc-400">Run an ad-hoc deterministic shock to evaluate instantaneous portfolio impact.</p>
                    <div className="flex items-center gap-3">
                      <div className="flex flex-col gap-1.5 flex-1">
                        <label className="text-[10px] uppercase tracking-wider text-zinc-500">Symbol (Empty = All)</label>
                        <input
                          value={shockSym}
                          onChange={(e) => setShockSym(e.target.value)}
                          placeholder="ALL"
                          className="w-full rounded border border-zinc-700 bg-zinc-900/60 px-3 py-2 text-sm uppercase outline-none focus:border-teal-500/50 transition-colors"
                        />
                      </div>
                      <div className="flex flex-col gap-1.5 flex-1">
                        <label className="text-[10px] uppercase tracking-wider text-zinc-500">Shock (%)</label>
                        <div className="relative">
                          <input
                            type="number"
                            value={shockPct}
                            onChange={(e) => setShockPct(Number(e.target.value))}
                            className="w-full rounded border border-zinc-700 bg-zinc-900/60 px-3 py-2 pr-6 text-sm font-mono outline-none focus:border-teal-500/50 transition-colors"
                          />
                          <span className="absolute right-3 top-2.5 text-zinc-500 text-sm">%</span>
                        </div>
                      </div>
                      <div className="flex flex-col gap-1.5 justify-end h-[58px]">
                        <Button
                          onClick={runShock}
                          disabled={busy}
                          className="h-[38px] bg-rose-600/90 text-white hover:bg-rose-600 disabled:opacity-50"
                        >
                          {busy ? <Loader2 size={16} className="animate-spin" /> : <><Zap size={14} className="mr-2" /> Shock</>}
                        </Button>
                      </div>
                    </div>
                  </div>
                </GlassPanel>
              </div>
            </div>

            <p className="text-center text-[11px] text-zinc-600 mt-8">
              Read-only situational awareness. The deterministic pre-trade risk gate enforces limits at approval.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
