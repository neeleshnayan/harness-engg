"use client";

import React, { useEffect, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Loader2, Plus, RefreshCw } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { fundApiClient, StrategyView, StrategiesResponse } from "@/lib/fund_api";
import { StrategyStudioCard } from "./components/StrategyStudioCard";
import { CreateStrategyModal } from "./components/CreateStrategyModal";
import { BacktestModal } from "./components/BacktestModal";
import { AllocationModal } from "./components/AllocationModal";

export default function StrategyStudioPage() {
  const [data, setData] = useState<StrategiesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [backtestTarget, setBacktestTarget] = useState<StrategyView | null>(null);
  const [allocTarget, setAllocTarget] = useState<StrategyView | null>(null);
  const { toast } = useToast();

  const load = useCallback(async () => {
    try {
      setErr(null);
      setData(await fundApiClient.getStrategies());
    } catch (e: any) {
      setErr(e?.message || "Could not reach the fund harness.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const deploy = async (s: StrategyView) => {
    try {
      await fundApiClient.setState(s.strategy_id, "deployed");
      toast({ title: "Deployed", description: s.name });
      load();
    } catch (e: any) {
      toast({
        title: "Deploy failed",
        description: e?.response?.data?.detail || e?.message,
        variant: "destructive",
      });
    }
  };

  const pause = async (s: StrategyView) => {
    try {
      await fundApiClient.setState(s.strategy_id, "paused");
      toast({ title: "Paused", description: s.name });
      load();
    } catch (e: any) {
      toast({
        title: "Pause failed",
        description: e?.response?.data?.detail || e?.message,
        variant: "destructive",
      });
    }
  };

  const strategies = data?.strategies || [];

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      <div className="max-w-5xl mx-auto px-5 py-8">
        <div className="flex items-center gap-3 mb-6 flex-wrap">
          <div>
            <h1 className="text-2xl font-semibold">Strategy Studio</h1>
            <p className="text-sm text-zinc-400">
              Create, backtest, deploy and allocate the fund&apos;s strategies.
              {data ? ` · NAV $${Number(data.nav_usd).toLocaleString()}` : ""}
            </p>
          </div>
          <div className="ml-auto flex gap-2">
            <Button
              variant="outline"
              className="bg-transparent border-zinc-700 text-zinc-200"
              onClick={load}
            >
              <RefreshCw size={16} className="mr-2" />
              Refresh
            </Button>
            <Button
              className="bg-gradient-to-r from-blue-600 to-purple-600 text-white"
              onClick={() => setCreateOpen(true)}
            >
              <Plus size={16} className="mr-2" />
              New strategy
            </Button>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 text-zinc-400">
            <Loader2 className="animate-spin" size={18} /> Loading strategies…
          </div>
        ) : err ? (
          <div className="rounded-xl border border-red-800/50 bg-red-950/30 p-4 text-red-300 text-sm">
            {err} — is ClarkHarness running and NEXT_PUBLIC_HARNESS_API_URL set?
          </div>
        ) : strategies.length === 0 ? (
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-8 text-center text-zinc-400">
            No strategies yet. Create one to begin.
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {strategies.map((s) => (
              <StrategyStudioCard
                key={s.strategy_id}
                s={s}
                onBacktest={setBacktestTarget}
                onDeploy={deploy}
                onPause={pause}
                onAllocate={setAllocTarget}
              />
            ))}
          </div>
        )}
      </div>

      <CreateStrategyModal isOpen={createOpen} onClose={() => setCreateOpen(false)} onSuccess={load} />
      <BacktestModal strategy={backtestTarget} onClose={() => setBacktestTarget(null)} onSuccess={load} />
      <AllocationModal strategy={allocTarget} onClose={() => setAllocTarget(null)} onSuccess={load} />
    </div>
  );
}
