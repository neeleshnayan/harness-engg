'use client';

import React, { useState, useEffect } from 'react';
import { fundApiClient, SentinelSignal } from '@/lib/fund_api';
import { Radio, RefreshCw, Sparkles, ShieldCheck, ChevronRight, AlertCircle, ArrowUpRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';

interface SentinelRadarFeedProps {
  onSelectThesis?: (thesisId: string) => void;
}

export function SentinelRadarFeed({ onSelectThesis }: SentinelRadarFeedProps) {
  const { toast } = useToast();
  const [signals, setSignals] = useState<SentinelSignal[]>([]);
  const [scanning, setScanning] = useState<boolean>(false);

  const fetchSignals = async () => {
    try {
      const res = await fundApiClient.getSentinelSignals();
      setSignals(res.signals || []);
    } catch (e) {}
  };

  useEffect(() => {
    fetchSignals();
    const interval = setInterval(fetchSignals, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleScan = async () => {
    setScanning(true);
    try {
      const res = await fundApiClient.scanSentinel();
      setSignals(res.signals || []);
      toast({
        title: 'Alpha Radar Scan Complete',
        description: `Scanned ${res.total_signals_scanned} multi-modal feeds. Autonomously drafted ${res.newly_drafted_theses.length} theses & memos.`,
      });
    } catch (e: any) {
      toast({
        title: 'Scan Error',
        description: e?.message || 'Radar scan failed.',
      });
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-4 space-y-4 shadow-xl">
      <div className="flex items-center justify-between border-b border-zinc-800/60 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="relative flex items-center justify-center">
            <span className="animate-ping absolute inline-flex h-3 w-3 rounded-full bg-emerald-400 opacity-75"></span>
            <Radio className="w-4 h-4 text-emerald-400 relative" />
          </div>
          <div>
            <div className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
              Clark Sentinel Alpha Radar
              <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                24/7 Autonomous
              </span>
            </div>
            <div className="text-[11px] text-zinc-400">
              SEC 13F accumulation, options IV sweeps, and supply-chain channel checks.
            </div>
          </div>
        </div>
        <Button
          size="sm"
          variant="outline"
          disabled={scanning}
          onClick={handleScan}
          className="border-zinc-800 bg-zinc-900/60 text-zinc-300 hover:bg-zinc-800 text-xs rounded-xl"
        >
          <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${scanning ? 'animate-spin' : ''}`} />
          Run Radar Scan
        </Button>
      </div>

      <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1">
        {signals.length === 0 ? (
          <div className="text-center py-6 text-xs text-zinc-500">
            No active signals detected. Click Run Radar Scan to scan feeds.
          </div>
        ) : (
          signals.map((sig) => (
            <div
              key={sig.signal_id}
              className="bg-zinc-900/40 border border-zinc-800/80 hover:border-zinc-700/80 transition-all rounded-xl p-3.5 space-y-2.5"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold font-mono px-2 py-0.5 rounded bg-zinc-800 text-amber-300 border border-zinc-700">
                      {sig.symbol}
                    </span>
                    <span className="text-xs font-semibold text-zinc-200">
                      {sig.title}
                    </span>
                  </div>
                  <div className="text-[10px] text-zinc-400 flex items-center gap-1.5">
                    <Sparkles className="w-3 h-3 text-amber-400" />
                    <span>{sig.source}</span>
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-xs font-mono font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                    {sig.conviction_score}% Conviction
                  </div>
                  <div className="text-[10px] text-emerald-300/80 font-mono mt-0.5">
                    +{sig.target_upside_pct}% Target Upside
                  </div>
                </div>
              </div>

              <div className="text-xs text-zinc-300 bg-zinc-950/40 p-2.5 rounded-lg border border-zinc-800/50">
                {sig.summary}
              </div>

              <div className="flex items-center justify-between pt-1 text-xs">
                <div className="text-[11px] text-zinc-400 font-mono">
                  Target Exposure: <span className="text-amber-400 font-semibold">+{sig.target_exposure_pct}%</span>
                </div>
                {sig.thesis_id && (
                  <button
                    onClick={() => onSelectThesis?.(sig.thesis_id!)}
                    className="text-xs font-medium text-amber-400 hover:text-amber-300 flex items-center gap-1"
                  >
                    Review Auto-Drafted Thesis <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
