'use client';

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { fundApiClient, SimulationResponse, HedgingProposal } from '@/lib/fund_api';
import { ShieldAlert, Activity, Flame, TrendingDown, RefreshCw, CheckCircle2, ArrowRight, Zap } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface SimulationModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: () => void;
}

const PRESET_OPTIONS = [
  { key: 'oil_spike', label: '🛢️ Geopolitical Oil Spike ($110/bbl)', oil: 110, rate: 35, mkt: -4.2, vix: 30 },
  { key: 'rate_surge', label: '📈 Hawkish Fed Yield Surge (+60bps)', oil: 78, rate: 60, mkt: -5.5, vix: 25 },
  { key: 'tech_selloff', label: '📉 Tech Sector De-risking (-12%)', oil: 72, rate: -15, mkt: -8.5, vix: 45 },
  { key: 'crypto_crash', label: '⚡ Crypto Liquidity Crunch (-25%)', oil: 74, rate: -5, mkt: -3.0, vix: 20 },
];

export function SimulationModal({ open, onOpenChange, onSuccess }: SimulationModalProps) {
  const { toast } = useToast();
  const [selectedPreset, setSelectedPreset] = useState<string>('oil_spike');
  const [crudeOil, setCrudeOil] = useState<number>(110);
  const [yieldBps, setYieldBps] = useState<number>(35);
  const [marketShock, setMarketShock] = useState<number>(-4.2);
  const [vixSpike, setVixSpike] = useState<number>(30);
  const [loading, setLoading] = useState<boolean>(false);
  const [applyingHedge, setApplyingHedge] = useState<boolean>(false);
  const [simResult, setSimResult] = useState<SimulationResponse | null>(null);

  const runSimulation = async (
    presetKey?: string,
    oil?: number,
    rate?: number,
    mkt?: number,
    vix?: number
  ) => {
    setLoading(true);
    try {
      const res = await fundApiClient.simulateRisk({
        scenario: presetKey || selectedPreset,
        crude_oil_price: oil !== undefined ? oil : crudeOil,
        yield_10y_bps: rate !== undefined ? rate : yieldBps,
        market_shock_pct: mkt !== undefined ? mkt : marketShock,
        vix_spike_pct: vix !== undefined ? vix : vixSpike,
      });
      setSimResult(res);
    } catch (e: any) {
      toast({
        title: 'Simulation Error',
        description: e?.message || 'Could not calculate stress scenario.',
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      runSimulation('oil_spike', 110, 35, -4.2, 30);
    }
  }, [open]);

  const handleSelectPreset = (preset: typeof PRESET_OPTIONS[0]) => {
    setSelectedPreset(preset.key);
    setCrudeOil(preset.oil);
    setYieldBps(preset.rate);
    setMarketShock(preset.mkt);
    setVixSpike(preset.vix);
    runSimulation(preset.key, preset.oil, preset.rate, preset.mkt, preset.vix);
  };

  const handleApplyHedge = async (hedge: HedgingProposal) => {
    setApplyingHedge(true);
    try {
      const strats = await fundApiClient.getStrategies();
      const stratMap: Record<string, string> = {};
      strats.strategies.forEach((s) => {
        stratMap[s.name] = s.strategy_id;
      });

      for (const action of hedge.actions) {
        const sid = stratMap[action.strategy_name];
        if (sid) {
          await fundApiClient.setAllocation(sid, action.recommended_pct);
        }
      }

      toast({
        title: 'Hedge Executed',
        description: 'Rebalance target allocations updated on the spine.',
      });
      onSuccess?.();
      onOpenChange(false);
    } catch (e: any) {
      toast({
        title: 'Hedge Application Failed',
        description: e?.message || 'Could not update allocations.',
      });
    } finally {
      setApplyingHedge(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl bg-[var(--kt-bg)] border-[var(--kt-border)] text-[var(--kt-text)] p-6 rounded-2xl shadow-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader className="border-b border-[var(--kt-border)] pb-4 mb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-[var(--kt-warn)]">
                <ShieldAlert className="w-5 h-5" />
              </div>
              <div>
                <DialogTitle className="text-lg font-semibold text-[var(--kt-text)] flex items-center gap-2">
                  Clark Counterfactual Stress Workbench
                  <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-[var(--kt-accent)] border border-emerald-500/20">
                    Live Spine Connected
                  </span>
                </DialogTitle>
                <DialogDescription className="text-xs text-[var(--kt-text-dim)] mt-0.5">
                  Simulate macro factor shocks against active portfolio holdings before executing rebalances.
                </DialogDescription>
              </div>
            </div>
          </div>
        </DialogHeader>

        {/* Presets Bar */}
        <div className="space-y-4">
          <div>
            <label className="text-[11px] font-medium uppercase tracking-wider text-[var(--kt-text-dim)] mb-2 block">
              Famous Macro Shock Presets
            </label>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {PRESET_OPTIONS.map((p) => (
                <button
                  key={p.key}
                  onClick={() => handleSelectPreset(p)}
                  className={`px-3 py-2 text-xs rounded-xl border text-left transition-all ${
                    selectedPreset === p.key
                      ? 'bg-amber-500/15 border-amber-500/40 text-[var(--kt-warn)] font-medium'
                      : 'bg-[var(--kt-surface)] border-[var(--kt-border)] text-[var(--kt-text-dim)] hover:border-[var(--kt-border)] hover:text-[var(--kt-text)]'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* Slider Inputs Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 bg-[var(--kt-surface)] p-3.5 rounded-xl border border-[var(--kt-border)]">
            <div>
              <div className="flex justify-between text-[11px] text-[var(--kt-text-dim)] mb-1">
                <span>Brent Crude Oil</span>
                <span className="font-mono text-[var(--kt-warn)] font-semibold">${crudeOil}/bbl</span>
              </div>
              <input
                type="range"
                min="50"
                max="150"
                value={crudeOil}
                onChange={(e) => setCrudeOil(parseFloat(e.target.value))}
                onMouseUp={() => runSimulation()}
                className="w-full accent-amber-500"
              />
            </div>
            <div>
              <div className="flex justify-between text-[11px] text-[var(--kt-text-dim)] mb-1">
                <span>10Y Yield Delta</span>
                <span className="font-mono text-[var(--kt-warn)] font-semibold">+{yieldBps} bps</span>
              </div>
              <input
                type="range"
                min="-50"
                max="120"
                value={yieldBps}
                onChange={(e) => setYieldBps(parseFloat(e.target.value))}
                onMouseUp={() => runSimulation()}
                className="w-full accent-amber-500"
              />
            </div>
            <div>
              <div className="flex justify-between text-[11px] text-[var(--kt-text-dim)] mb-1">
                <span>Market Shock (S&P)</span>
                <span className="font-mono text-[var(--kt-down)] font-semibold">{marketShock}%</span>
              </div>
              <input
                type="range"
                min="-20"
                max="10"
                step="0.5"
                value={marketShock}
                onChange={(e) => setMarketShock(parseFloat(e.target.value))}
                onMouseUp={() => runSimulation()}
                className="w-full accent-rose-500"
              />
            </div>
            <div>
              <div className="flex justify-between text-[11px] text-[var(--kt-text-dim)] mb-1">
                <span>VIX Spike</span>
                <span className="font-mono text-[var(--kt-down)] font-semibold">+{vixSpike}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="80"
                value={vixSpike}
                onChange={(e) => setVixSpike(parseFloat(e.target.value))}
                onMouseUp={() => runSimulation()}
                className="w-full accent-rose-500"
              />
            </div>
          </div>

          {/* Results Summary Cards */}
          {simResult && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <div className="bg-rose-950/20 border border-rose-900/40 rounded-xl p-3.5">
                  <div className="text-[10px] font-medium uppercase tracking-wider text-[var(--kt-down)] mb-1 flex items-center gap-1.5">
                    <TrendingDown className="w-3.5 h-3.5" /> Forecast Drawdown
                  </div>
                  <div className="text-xl font-bold font-mono text-[var(--kt-down)]">
                    {simResult.summary.drawdown_pct}%
                  </div>
                  <div className="text-xs text-[var(--kt-down)]/70 font-mono mt-0.5">
                    -${Math.abs(simResult.summary.drawdown_usd).toLocaleString()} USD
                  </div>
                </div>

                <div className="bg-[var(--kt-surface)] border border-[var(--kt-border)] rounded-xl p-3.5">
                  <div className="text-[10px] font-medium uppercase tracking-wider text-[var(--kt-text-dim)] mb-1">
                    Simulated Total NAV
                  </div>
                  <div className="text-xl font-bold font-mono text-[var(--kt-text)]">
                    ${simResult.summary.nav_usd_after.toLocaleString()}
                  </div>
                  <div className="text-xs text-[var(--kt-text-muted)] font-mono mt-0.5">
                    Base: ${simResult.summary.nav_usd_before.toLocaleString()}
                  </div>
                </div>

                <div className="bg-[var(--kt-surface)] border border-[var(--kt-border)] rounded-xl p-3.5">
                  <div className="text-[10px] font-medium uppercase tracking-wider text-[var(--kt-text-dim)] mb-1">
                    Portfolio Beta
                  </div>
                  <div className="text-xl font-bold font-mono text-[var(--kt-warn)]">
                    {simResult.summary.portfolio_beta}
                  </div>
                  <div className="text-xs text-[var(--kt-text-muted)] mt-0.5">Factor Sensitivity</div>
                </div>

                <div className="bg-[var(--kt-surface)] border border-[var(--kt-border)] rounded-xl p-3.5">
                  <div className="text-[10px] font-medium uppercase tracking-wider text-[var(--kt-text-dim)] mb-1">
                    Sharpe Shift
                  </div>
                  <div className="text-xl font-bold font-mono text-cyan-400">
                    {simResult.summary.sharpe_before} → {simResult.summary.sharpe_after}
                  </div>
                  <div className="text-xs text-[var(--kt-text-muted)] mt-0.5">Delta: {(simResult.summary.sharpe_after - simResult.summary.sharpe_before).toFixed(2)}</div>
                </div>
              </div>

              {/* Position P&L Heatmap Table */}
              <div className="bg-[var(--kt-surface)] border border-[var(--kt-border)] rounded-xl p-3.5">
                <div className="text-[11px] font-medium uppercase tracking-wider text-[var(--kt-text-dim)] mb-2">
                  Position P&L Impact & Factor Sensitivities
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead>
                      <tr className="border-b border-[var(--kt-border)] text-[var(--kt-text-muted)]">
                        <th className="py-1.5 font-medium">Asset</th>
                        <th className="py-1.5 font-medium text-right">Qty</th>
                        <th className="py-1.5 font-medium text-right">Mark (Before → After)</th>
                        <th className="py-1.5 font-medium text-right">Shock %</th>
                        <th className="py-1.5 font-medium text-right">P&L ($)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {simResult.position_impacts.map((pos) => (
                        <tr key={pos.symbol} className="border-b border-[var(--kt-border)]">
                          <td className="py-2 font-semibold text-[var(--kt-text)]">{pos.symbol}</td>
                          <td className="py-2 text-right font-mono text-[var(--kt-text-dim)]">{pos.qty}</td>
                          <td className="py-2 text-right font-mono text-[var(--kt-text-dim)]">
                            ${pos.mark_before} → ${pos.mark_after}
                          </td>
                          <td className={`py-2 text-right font-mono font-medium ${pos.shock_pct < 0 ? 'text-[var(--kt-down)]' : 'text-[var(--kt-accent)]'}`}>
                            {pos.shock_pct > 0 ? '+' : ''}{pos.shock_pct}%
                          </td>
                          <td className={`py-2 text-right font-mono font-semibold ${pos.pnl_usd < 0 ? 'text-[var(--kt-down)]' : 'text-[var(--kt-accent)]'}`}>
                            {pos.pnl_usd < 0 ? '-' : '+'}${Math.abs(pos.pnl_usd).toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Automated Hedging Proposals Box */}
              {simResult.hedging_proposals && simResult.hedging_proposals.length > 0 && (
                <div className="bg-emerald-950/20 border border-emerald-500/30 rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-[var(--kt-accent)] font-semibold text-sm">
                      <Zap className="w-4 h-4" /> Automated Hedging Rebalance Proposal
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-[var(--kt-accent)]">
                      Clark Recommendation
                    </span>
                  </div>
                  {simResult.hedging_proposals.map((hedge) => (
                    <div key={hedge.proposal_id} className="space-y-2">
                      <div className="text-xs text-[var(--kt-text-dim)] font-medium">{hedge.title}</div>
                      <div className="text-xs text-[var(--kt-text-dim)]">{hedge.description}</div>
                      <div className="flex items-center justify-between pt-2">
                        <div className="text-xs text-[var(--kt-accent)] font-mono">
                          Reduces drawdown to {hedge.mitigated_drawdown_pct}% (Saves ${Math.abs(hedge.mitigated_drawdown_usd).toLocaleString()})
                        </div>
                        <Button
                          size="sm"
                          disabled={applyingHedge}
                          onClick={() => handleApplyHedge(hedge)}
                          className="bg-emerald-600 hover:bg-emerald-500 text-[var(--kt-text-strong)] font-medium text-xs rounded-xl"
                        >
                          {applyingHedge ? (
                            <RefreshCw className="w-3.5 h-3.5 animate-spin mr-1" />
                          ) : (
                            <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                          )}
                          Apply Recommended Hedge
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
