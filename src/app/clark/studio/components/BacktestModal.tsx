"use client";

import React, { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, AlertCircle } from "lucide-react";
import { fundApiClient, StrategyView, BacktestResult } from "@/lib/fund_api";
import { TVAreaChart, TVPoint } from "./TVAreaChart";

interface Props {
  strategy: StrategyView | null;
  onClose: () => void;
  onSuccess: () => void;
  /** Feeds the fetched price series back to the cockpit chart. */
  onCharted?: (symbol: string, points: TVPoint[]) => void;
}

const asPct = (n: number) => `${(n * 100).toFixed(2)}%`;

export function BacktestModal({ strategy, onClose, onSuccess, onCharted }: Props) {
  const [mode, setMode] = useState<"symbol" | "manual">("symbol");
  const [type, setType] = useState<"sma" | "buy_hold">("sma");
  const [fast, setFast] = useState(20);
  const [slow, setSlow] = useState(50);
  const [symbol, setSymbol] = useState("AAPL");
  const [lookback, setLookback] = useState(365);
  const [pricesText, setPricesText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [series, setSeries] = useState<TVPoint[]>([]);
  const [source, setSource] = useState<string | null>(null);

  if (!strategy) return null;

  const runManual = async () => {
    const prices = pricesText.split(/[\s,]+/).map((x) => parseFloat(x)).filter((x) => !isNaN(x));
    if (prices.length < 2) {
      setError("Enter at least 2 close prices (comma or space separated).");
      return;
    }
    if (type === "sma" && prices.length < slow) {
      setError(`SMA needs at least ${slow} bars (the slow window); you entered ${prices.length}.`);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await fundApiClient.runBacktest(strategy.strategy_id, { prices, strategy: type, fast, slow });
      setResult(res.result);
      setSeries(prices.map((v, i) => ({ t: String(i), v })));
      setSource("manual");
      onSuccess();
    } catch (e: unknown) {
      setError(errText(e));
    } finally {
      setLoading(false);
    }
  };

  const runSymbol = async () => {
    const sym = symbol.trim().toUpperCase();
    if (!sym) {
      setError("Enter a symbol (e.g. AAPL).");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await fundApiClient.runBacktestBySymbol(strategy.strategy_id, {
        symbol: sym,
        strategy: type,
        fast,
        slow,
        lookback_days: lookback,
      });
      setResult(res.result);
      const dates = res.bars.dates || [];
      const points: TVPoint[] = res.bars.closes.map((v, i) => ({ t: dates[i] || String(i), v }));
      setSeries(points);
      setSource(res.source);
      onCharted?.(res.symbol, points);
      onSuccess();
    } catch (e: unknown) {
      setError(errText(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={!!strategy} onOpenChange={onClose}>
      <DialogContent className="w-[calc(100%-2rem)] max-w-[560px] max-h-[92vh] overflow-y-auto border-zinc-800 bg-zinc-900 text-white">
        <DialogHeader>
          <DialogTitle>Backtest — {strategy.name}</DialogTitle>
        </DialogHeader>

        {/* mode toggle */}
        <div className="mt-1 inline-flex rounded-lg border border-zinc-700 bg-zinc-800/60 p-0.5 text-xs">
          <button
            className={`rounded-md px-3 py-1.5 ${mode === "symbol" ? "bg-zinc-700 text-white" : "text-zinc-400"}`}
            onClick={() => setMode("symbol")}
          >
            By symbol · free data
          </button>
          <button
            className={`rounded-md px-3 py-1.5 ${mode === "manual" ? "bg-zinc-700 text-white" : "text-zinc-400"}`}
            onClick={() => setMode("manual")}
          >
            Paste prices
          </button>
        </div>

        <div className="grid gap-4 py-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label htmlFor="btype">Strategy</Label>
              <select
                id="btype"
                value={type}
                onChange={(e) => setType(e.target.value as "sma" | "buy_hold")}
                className="h-10 rounded-md border border-zinc-700 bg-zinc-800 px-3 text-sm"
              >
                <option value="sma">SMA crossover</option>
                <option value="buy_hold">Buy &amp; hold</option>
              </select>
            </div>
            {mode === "symbol" && (
              <div className="grid gap-2">
                <Label htmlFor="sym">Symbol</Label>
                <Input
                  id="sym"
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                  placeholder="AAPL"
                  className="border-zinc-700 bg-zinc-800 uppercase"
                />
              </div>
            )}
          </div>

          {type === "sma" && (
            <div className="grid grid-cols-3 gap-3">
              <div className="grid gap-2">
                <Label htmlFor="fast">Fast</Label>
                <Input id="fast" type="number" value={fast} onChange={(e) => setFast(parseInt(e.target.value) || 1)} className="border-zinc-700 bg-zinc-800" />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="slow">Slow</Label>
                <Input id="slow" type="number" value={slow} onChange={(e) => setSlow(parseInt(e.target.value) || 1)} className="border-zinc-700 bg-zinc-800" />
              </div>
              {mode === "symbol" && (
                <div className="grid gap-2">
                  <Label htmlFor="lb">Lookback (d)</Label>
                  <Input id="lb" type="number" value={lookback} onChange={(e) => setLookback(parseInt(e.target.value) || 30)} className="border-zinc-700 bg-zinc-800" />
                </div>
              )}
            </div>
          )}

          {mode === "manual" && (
            <div className="grid gap-2">
              <Label htmlFor="prices">Close prices (comma / space separated)</Label>
              <textarea
                id="prices"
                value={pricesText}
                onChange={(e) => setPricesText(e.target.value)}
                rows={3}
                placeholder="100, 102, 101, 105, 108, ..."
                className="rounded-md border border-zinc-700 bg-zinc-800 p-3 font-mono text-sm"
              />
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 text-sm text-red-400">
              <AlertCircle size={16} /> {error}
            </div>
          )}

          {series.length > 0 && (
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-2">
              <div className="mb-1 px-1 text-[11px] text-zinc-500">
                {mode === "symbol" ? `${symbol} · ${source} · ${series.length} bars` : `${series.length} bars`}
              </div>
              <TVAreaChart data={series} height={160} valuePrefix="$" />
            </div>
          )}

          {result && (
            <div className="grid grid-cols-4 gap-3 rounded-lg border border-zinc-700 bg-zinc-800/50 p-4 font-mono text-sm">
              <Metric label="Return" value={asPct(result.total_return)} good={result.total_return >= 0} />
              <Metric label="Sharpe" value={result.sharpe.toFixed(2)} />
              <Metric label="Max DD" value={asPct(result.max_drawdown)} bad />
              <Metric label="Trades" value={String(result.n_trades)} />
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} className="border-zinc-700 bg-transparent text-zinc-300">
            Close
          </Button>
          <Button
            onClick={mode === "symbol" ? runSymbol : runManual}
            disabled={loading}
            className="bg-gradient-to-r from-teal-600 to-sky-600 text-white"
          >
            {loading && <Loader2 className="mr-2 animate-spin" size={16} />}
            {loading ? "Running…" : mode === "symbol" ? "Fetch & backtest" : "Run backtest"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Metric({ label, value, good, bad }: { label: string; value: string; good?: boolean; bad?: boolean }) {
  const color = good ? "text-emerald-400" : bad ? "text-red-400" : "text-zinc-100";
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</div>
      <div className={color}>{value}</div>
    </div>
  );
}

function errText(e: unknown): string {
  const err = e as { response?: { data?: { detail?: string } }; message?: string };
  return err?.response?.data?.detail || err?.message || "Backtest failed.";
}
