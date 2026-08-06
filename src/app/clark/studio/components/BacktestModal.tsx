"use client";

import React, { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, AlertCircle } from "lucide-react";
import { fundApiClient, StrategyView, BacktestResult } from "@/lib/fund_api";

interface Props {
  strategy: StrategyView | null;
  onClose: () => void;
  onSuccess: () => void;
}

const asPct = (n: number) => `${(n * 100).toFixed(2)}%`;

export function BacktestModal({ strategy, onClose, onSuccess }: Props) {
  const [type, setType] = useState<"sma" | "buy_hold">("sma");
  const [fast, setFast] = useState(10);
  const [slow, setSlow] = useState(30);
  const [pricesText, setPricesText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);

  if (!strategy) return null;

  const run = async () => {
    const prices = pricesText
      .split(/[\s,]+/)
      .map((x) => parseFloat(x))
      .filter((x) => !isNaN(x));
    if (prices.length < 2) {
      setError("Enter at least 2 close prices (comma or space separated).");
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const res = await fundApiClient.runBacktest(strategy.strategy_id, {
        prices,
        strategy: type,
        fast,
        slow,
      });
      setResult(res.result);
      onSuccess();
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || "Backtest failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={!!strategy} onOpenChange={onClose}>
      <DialogContent className="bg-zinc-900 border-zinc-800 text-white w-[calc(100%-2rem)] max-w-[480px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Backtest — {strategy.name}</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="btype">Strategy</Label>
            <select
              id="btype"
              value={type}
              onChange={(e) => setType(e.target.value as "sma" | "buy_hold")}
              className="bg-zinc-800 border border-zinc-700 rounded-md h-10 px-3 text-sm"
            >
              <option value="sma">SMA crossover</option>
              <option value="buy_hold">Buy &amp; hold</option>
            </select>
          </div>

          {type === "sma" && (
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-2">
                <Label htmlFor="fast">Fast window</Label>
                <Input
                  id="fast"
                  type="number"
                  value={fast}
                  onChange={(e) => setFast(parseInt(e.target.value) || 1)}
                  className="bg-zinc-800 border-zinc-700"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="slow">Slow window</Label>
                <Input
                  id="slow"
                  type="number"
                  value={slow}
                  onChange={(e) => setSlow(parseInt(e.target.value) || 1)}
                  className="bg-zinc-800 border-zinc-700"
                />
              </div>
            </div>
          )}

          <div className="grid gap-2">
            <Label htmlFor="prices">Close prices (comma / space separated)</Label>
            <textarea
              id="prices"
              value={pricesText}
              onChange={(e) => setPricesText(e.target.value)}
              rows={4}
              placeholder="100, 102, 101, 105, 108, ..."
              className="bg-zinc-800 border border-zinc-700 rounded-md p-3 text-sm font-mono"
            />
            <span className="text-xs text-zinc-500">
              Alpaca historical bars will feed this automatically in a later pass.
            </span>
          </div>

          {error && (
            <div className="text-red-400 text-sm flex items-center gap-2">
              <AlertCircle size={16} /> {error}
            </div>
          )}

          {result && (
            <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 p-4 grid grid-cols-2 gap-3 font-mono text-sm">
              <div>
                <div className="text-zinc-400 text-xs">Total return</div>
                <div className={result.total_return >= 0 ? "text-emerald-400" : "text-red-400"}>
                  {asPct(result.total_return)}
                </div>
              </div>
              <div>
                <div className="text-zinc-400 text-xs">Sharpe</div>
                <div>{result.sharpe.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-zinc-400 text-xs">Max drawdown</div>
                <div className="text-red-400">{asPct(result.max_drawdown)}</div>
              </div>
              <div>
                <div className="text-zinc-400 text-xs">Trades</div>
                <div>{result.n_trades}</div>
              </div>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} className="bg-transparent border-zinc-700 text-zinc-300">
            Close
          </Button>
          <Button
            onClick={run}
            disabled={loading}
            className="bg-gradient-to-r from-blue-600 to-purple-600 text-white"
          >
            {loading && <Loader2 className="animate-spin mr-2" size={16} />}
            {loading ? "Running..." : "Run backtest"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
