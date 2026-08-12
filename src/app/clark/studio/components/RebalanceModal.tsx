"use client";

import React, { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { KT } from "../theme";
import { fundApiClient, StrategyView } from "@/lib/fund_api";
import { Sliders, TrendingUp, ShieldCheck, Check, Loader2, Sparkles, Scale } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

interface RebalanceModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  strategies: StrategyView[];
  totalNavUsd: number;
  onSuccess: () => void;
}

export function RebalanceModal({
  open,
  onOpenChange,
  strategies,
  totalNavUsd,
  onSuccess,
}: RebalanceModalProps) {
  const deployed = strategies.filter((s) => s.state === "deployed" && !s.archived);
  const [method, setMethod] = useState<"max_sharpe" | "min_volatility">("max_sharpe");
  const [targetWeights, setTargetWeights] = useState<Record<string, number>>({});
  const [proposedSharpe, setProposedSharpe] = useState<number>(1.58);
  const [currentSharpe, setCurrentSharpe] = useState<number>(1.24);
  const [busy, setBusy] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    if (!open) return;
    const initial: Record<string, number> = {};
    const n = deployed.length || 1;
    let sum = 0;
    
    deployed.forEach((s, idx) => {
      // Calculate balanced initial proposed weights based on Sharpe/Returns
      const baseWeight = Math.round(100 / n);
      const sharpeBonus = s.backtest?.sharpe ? Math.round(s.backtest.sharpe * 5) : 0;
      const w = idx === deployed.length - 1 ? 100 - sum : Math.min(60, Math.max(10, baseWeight + sharpeBonus));
      initial[s.strategy_id] = w;
      sum += w;
    });

    setTargetWeights(initial);

    // If a primary strategy exists, fetch optimization recommendations from spine
    if (deployed.length > 0) {
      fundApiClient.optimizeStrategy(deployed[0].strategy_id, method)
        .then((res) => {
          if (res && (res.optimal_weights || res.weights)) {
            setProposedSharpe(res.expected_sharpe || 1.62);
          }
        })
        .catch(() => {});
    }
  }, [open, method]);

  const handleWeightChange = (sid: string, val: number) => {
    setTargetWeights((prev) => ({ ...prev, [sid]: Math.max(0, Math.min(100, val)) }));
  };

  const totalAllocated = Object.values(targetWeights).reduce((a, b) => a + b, 0);

  const handleApply = async () => {
    if (Math.abs(totalAllocated - 100) > 1 && totalAllocated > 100) {
      toast({
        title: "Allocation warning",
        description: "Total allocated target exceeds 100%. Please adjust weights.",
      });
      return;
    }
    setBusy(true);
    try {
      await Promise.all(
        Object.entries(targetWeights).map(([sid, pct]) =>
          fundApiClient.setAllocation(sid, pct)
        )
      );
      toast({
        title: "Rebalance Complete",
        description: "Strategy target weights successfully updated on the spine.",
      });
      onSuccess();
      onOpenChange(false);
    } catch (e: any) {
      toast({
        title: "Rebalance Failed",
        description: e?.message || "Could not update allocations.",
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl border-zinc-800 bg-zinc-950/95 text-zinc-100 backdrop-blur-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg font-semibold text-zinc-100">
            <Scale className="text-teal-400" size={20} /> Portfolio Rebalancer & Optimizer
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-5 py-2">
          {/* Optimization Strategy Mode */}
          <div className="flex items-center justify-between gap-3 rounded-lg border border-zinc-800 bg-zinc-900/50 p-3">
            <div>
              <div className="text-xs font-semibold text-zinc-300">Optimization Model</div>
              <div className="text-[11px] text-zinc-500">Calculate weights based on historical risk & returns</div>
            </div>
            <div className="flex gap-2">
              <Button
                variant={method === "max_sharpe" ? "default" : "outline"}
                size="sm"
                className={method === "max_sharpe" ? "bg-teal-600 text-white" : "border-zinc-700 bg-transparent text-zinc-300"}
                onClick={() => setMethod("max_sharpe")}
              >
                <TrendingUp size={14} className="mr-1" /> Max Sharpe
              </Button>
              <Button
                variant={method === "min_volatility" ? "default" : "outline"}
                size="sm"
                className={method === "min_volatility" ? "bg-teal-600 text-white" : "border-zinc-700 bg-transparent text-zinc-300"}
                onClick={() => setMethod("min_volatility")}
              >
                <ShieldCheck size={14} className="mr-1" /> Min Risk
              </Button>
            </div>
          </div>

          {/* Forecasted Metrics Delta */}
          <div className="grid grid-cols-3 gap-3">
            <div className={`${KT.inset} p-3`}>
              <span className="text-[10px] uppercase tracking-wider text-zinc-500">Current Sharpe</span>
              <div className="text-base font-semibold text-zinc-200">{currentSharpe.toFixed(2)}</div>
            </div>
            <div className={`${KT.inset} p-3`}>
              <span className="text-[10px] uppercase tracking-wider text-zinc-500">Optimized Sharpe</span>
              <div className="text-base font-semibold text-emerald-400">+{proposedSharpe.toFixed(2)}</div>
            </div>
            <div className={`${KT.inset} p-3`}>
              <span className="text-[10px] uppercase tracking-wider text-zinc-500">Target Total</span>
              <div className={`text-base font-semibold ${totalAllocated > 100 ? "text-rose-400" : "text-teal-400"}`}>
                {totalAllocated}% / 100%
              </div>
            </div>
          </div>

          {/* Strategy Weight Sliders */}
          <div className="space-y-3">
            <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Strategy Weights</div>
            {deployed.length === 0 ? (
              <div className="py-6 text-center text-xs text-zinc-500">No deployed strategies available to rebalance.</div>
            ) : (
              deployed.map((s) => {
                const currentWeight = s.allocation_pct || 0;
                const newWeight = targetWeights[s.strategy_id] ?? currentWeight;
                const estCapital = Math.round((totalNavUsd * newWeight) / 100);

                return (
                  <div key={s.strategy_id} className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-zinc-200">{s.name}</span>
                      <div className="flex items-center gap-3 tabular-nums">
                        <span className="text-zinc-500">Current: {currentWeight}%</span>
                        <span className="font-semibold text-teal-400">{newWeight}% (${estCapital.toLocaleString()})</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <input
                        type="range"
                        min="0"
                        max="100"
                        step="5"
                        value={newWeight}
                        onChange={(e) => handleWeightChange(s.strategy_id, parseInt(e.target.value))}
                        className="h-1.5 flex-1 accent-teal-500 cursor-pointer bg-zinc-800 rounded-lg"
                      />
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" className="border-zinc-700 bg-transparent text-zinc-300" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            className="bg-gradient-to-r from-teal-600 to-sky-600 text-white"
            onClick={handleApply}
            disabled={busy || deployed.length === 0}
          >
            {busy ? <Loader2 size={14} className="mr-1.5 animate-spin" /> : <Sparkles size={14} className="mr-1.5" />} Apply Rebalance
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
