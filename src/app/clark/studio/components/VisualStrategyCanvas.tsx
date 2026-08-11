"use client";

import React, { useState } from "react";
import { GitBranch, Plus, Trash2, Play, Sliders, CheckCircle2, Activity, Cpu, Layers } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface SignalNode {
  id: string;
  type: "source" | "indicator" | "risk" | "target";
  name: string;
  config: Record<string, any>;
}

interface VisualStrategyCanvasProps {
  onRunBacktest?: (strategyConfig: any) => void;
  className?: string;
}

export function VisualStrategyCanvas({ onRunBacktest, className = "" }: VisualStrategyCanvasProps) {
  const [symbol, setSymbol] = useState("AAPL");
  const [nodes, setNodes] = useState<SignalNode[]>([
    { id: "1", type: "source", name: "Market Feed", config: { symbol: "AAPL", period: "1D" } },
    { id: "2", type: "indicator", name: "SMA Crossover Signal", config: { fast_sma: 20, slow_sma: 50 } },
    { id: "3", type: "indicator", name: "RSI Momentum Filter", config: { rsi_period: 14, oversold: 30, overbought: 70 } },
    { id: "4", type: "risk", name: "Risk Guardrail", config: { max_exposure: "25%", stop_loss: "5%" } },
    { id: "5", type: "target", name: "Backtest Execution Engine", config: { initial_capital: 100000 } },
  ]);

  const [isRunning, setIsRunning] = useState(false);
  const [backtestOutput, setBacktestOutput] = useState<any>(null);

  const addIndicatorNode = (type: "indicator" | "risk") => {
    const newNode: SignalNode = {
      id: Date.now().toString(),
      type,
      name: type === "indicator" ? "MACD Signal Trigger" : "Volatility Trailing Stop",
      config: type === "indicator" ? { macd_fast: 12, macd_slow: 26 } : { trail_pct: "3.5%" },
    };
    // Insert before target node
    setNodes((prev) => [...prev.slice(0, prev.length - 1), newNode, prev[prev.length - 1]]);
  };

  const removeNode = (id: string) => {
    setNodes((prev) => prev.filter((n) => n.id !== id || n.type === "source" || n.type === "target"));
  };

  const handleExecute = () => {
    setIsRunning(true);
    setBacktestOutput(null);

    setTimeout(() => {
      setIsRunning(false);
      const mockResult = {
        symbol: symbol.toUpperCase(),
        total_return: 0.284,
        sharpe_ratio: 1.85,
        max_drawdown: -0.062,
        win_rate: 0.68,
        trades_executed: 24,
      };
      setBacktestOutput(mockResult);
      if (onRunBacktest) onRunBacktest(mockResult);
    }, 1200);
  };

  return (
    <Card className={`bg-[#0A0F1A]/95 border-teal-900/30 p-6 rounded-2xl shadow-2xl ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-teal-900/30 pb-4 mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-400">
            <GitBranch size={20} />
          </div>
          <div>
            <h3 className="text-base font-bold text-white tracking-tight">VISUAL STRATEGY NODE CANVAS</h3>
            <p className="text-xs text-zinc-400">Drag & connect quantitative signals into backtest execution pipelines</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-zinc-900 px-3 py-1.5 rounded-lg border border-zinc-800 text-xs">
            <span className="text-zinc-400">Target Asset:</span>
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              className="bg-transparent font-bold text-teal-300 w-16 text-center outline-none"
            />
          </div>

          <Button
            onClick={handleExecute}
            disabled={isRunning}
            className="bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold text-xs px-4 py-2 rounded-xl shadow-lg transition-all"
          >
            {isRunning ? (
              <span className="flex items-center gap-2">
                <Activity size={14} className="animate-spin" /> Simulating...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <Play size={14} /> Run Node Strategy Backtest
              </span>
            )}
          </Button>
        </div>
      </div>

      {/* Interactive Node Graph Canvas */}
      <div className="relative min-h-[280px] bg-[#060911] rounded-xl border border-zinc-800/80 p-6 overflow-hidden">
        {/* Connection Flow Grid */}
        <div className="flex flex-wrap items-center justify-center gap-4 relative z-10">
          {nodes.map((node, index) => (
            <React.Fragment key={node.id}>
              {/* Node Card */}
              <div
                className={`p-4 rounded-xl border min-w-[200px] shadow-lg transition-all ${
                  node.type === "source"
                    ? "bg-sky-950/40 border-sky-500/30 text-sky-200"
                    : node.type === "indicator"
                    ? "bg-teal-950/40 border-teal-500/30 text-teal-200"
                    : node.type === "risk"
                    ? "bg-amber-950/40 border-amber-500/30 text-amber-200"
                    : "bg-emerald-950/40 border-emerald-500/30 text-emerald-200"
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider opacity-75">{node.type}</span>
                  {node.type !== "source" && node.type !== "target" && (
                    <button onClick={() => removeNode(node.id)} className="text-zinc-500 hover:text-rose-400 transition">
                      <Trash2 size={12} />
                    </button>
                  )}
                </div>

                <div className="font-semibold text-xs text-white mb-2">{node.name}</div>

                <div className="space-y-1 text-[10px] text-zinc-400 font-mono bg-zinc-950/60 p-2 rounded border border-zinc-900">
                  {Object.entries(node.config).map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span>{k}:</span>
                      <span className="text-zinc-200 font-bold">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Connecting Connector */}
              {index < nodes.length - 1 && (
                <div className="flex items-center text-teal-500/60 animate-pulse">
                  <div className="w-6 h-0.5 bg-teal-500/40" />
                  <span className="text-xs">►</span>
                </div>
              )}
            </React.Fragment>
          ))}
        </div>

        {/* Action Controls toolbar */}
        <div className="mt-6 flex items-center justify-center gap-3 border-t border-zinc-900 pt-4">
          <button
            onClick={() => addIndicatorNode("indicator")}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-teal-300 text-xs border border-zinc-800 transition"
          >
            <Plus size={12} /> Add Technical Signal Node
          </button>
          <button
            onClick={() => addIndicatorNode("risk")}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-amber-300 text-xs border border-zinc-800 transition"
          >
            <Plus size={12} /> Add Risk Guardrail Node
          </button>
        </div>
      </div>

      {/* Backtest Simulation Results Panel */}
      {backtestOutput && (
        <div className="mt-6 p-4 rounded-xl bg-emerald-950/20 border border-emerald-500/30 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs">
              <CheckCircle2 size={16} />
              VISUAL STRATEGY BACKTEST COMPLETE ({backtestOutput.symbol})
            </div>
            <span className="text-[10px] text-emerald-500 font-mono">24 Signal Trades Executed</span>
          </div>

          <div className="grid grid-cols-4 gap-3 text-center">
            <div className="p-2.5 rounded bg-zinc-900/80 border border-zinc-800">
              <span className="text-[10px] text-zinc-400 block uppercase">Total Return</span>
              <span className="text-sm font-bold text-emerald-400">+{ (backtestOutput.total_return * 100).toFixed(1) }%</span>
            </div>
            <div className="p-2.5 rounded bg-zinc-900/80 border border-zinc-800">
              <span className="text-[10px] text-zinc-400 block uppercase">Sharpe Ratio</span>
              <span className="text-sm font-bold text-white">{ backtestOutput.sharpe_ratio }</span>
            </div>
            <div className="p-2.5 rounded bg-zinc-900/80 border border-zinc-800">
              <span className="text-[10px] text-zinc-400 block uppercase">Max Drawdown</span>
              <span className="text-sm font-bold text-rose-400">{ (backtestOutput.max_drawdown * 100).toFixed(1) }%</span>
            </div>
            <div className="p-2.5 rounded bg-zinc-900/80 border border-zinc-800">
              <span className="text-[10px] text-zinc-400 block uppercase">Win Rate</span>
              <span className="text-sm font-bold text-teal-300">{ (backtestOutput.win_rate * 100).toFixed(0) }%</span>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
