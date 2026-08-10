"use client";

import React, { useCallback, useEffect, useState } from "react";
import { StudioHeader } from "../components/StudioHeader";
import { ClarkActionBar } from "../components/ClarkActionBar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  fundApiClient,
  StrategyView,
  StrategyRiskResponse,
  StrategyBarsResponse,
  BacktestBySymbolResponse,
  StrategyTemplate,
} from "@/lib/fund_api";
import {
  AlertTriangle,
  Layers,
  Loader2,
  Plus,
  TrendingUp,
  X,
  Play,
  ShieldAlert,
  BarChart3,
  Crosshair,
  Target,
} from "lucide-react";
import { AllocationDonut } from "../components/charts/AllocationDonut";
import { EfficientFrontierChart } from "../components/charts/EfficientFrontierChart";
import { CorrelationMatrix } from "../components/charts/CorrelationMatrix";
import { StrategyOptimizeResponse } from "@/lib/fund_api";

/* ---------- formatting ---------- */
const money = (n?: number | null, dp = 2) =>
  n == null
    ? "—"
    : `${n < 0 ? "-" : ""}$${Math.abs(Number(n)).toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp })}`;
const pct = (n?: number | null, dp = 1) => (n == null ? "0.0%" : `${Number(n).toFixed(dp)}%`);
const signed = (n?: number | null) => (n == null ? "—" : `${n >= 0 ? "+" : ""}${money(n)}`);

const STATE_STYLE: Record<string, string> = {
  deployed: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  backtested: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  draft: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
  paused: "bg-amber-500/15 text-amber-300 border-amber-500/30",
};

/* ---------- sparkline SVG ---------- */
function Sparkline({ closes, w = 100, h = 28 }: { closes: number[]; w?: number; h?: number }) {
  if (closes.length < 2)
    return (
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
        <text x={w / 2} y={h / 2 + 4} textAnchor="middle" fill="rgb(113 113 122)" fontSize="9">
          —
        </text>
      </svg>
    );
  const min = Math.min(...closes),
    max = Math.max(...closes),
    span = max - min || 1;
  const pts = closes.map((c, i) => [
    (i * w) / (closes.length - 1),
    4 + ((h - 8) * (1 - (c - min) / span)),
  ]);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ");
  const up = closes[closes.length - 1] >= closes[0];
  const col = up ? "rgb(52 211 153)" : "rgb(248 113 113)";
  const area = `M 0 ${h} ${pts.map((p) => `L ${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ")} L ${w} ${h} Z`;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      <defs>
        <linearGradient id={`sg-${closes.length}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={col} stopOpacity="0.15" />
          <stop offset="100%" stopColor={col} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#sg-${closes.length})`} />
      <path d={d} fill="none" stroke={col} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

/* ---------- stat box ---------- */
function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-lg border border-zinc-800/80 bg-zinc-900/40 px-3.5 py-2.5 min-w-[110px]">
      <span className="text-[10px] font-medium uppercase tracking-widest text-zinc-500">{label}</span>
      <span className={`font-mono text-lg leading-tight ${accent || "text-zinc-100"}`}>{value}</span>
    </div>
  );
}

/* ============================================================
   PAGE
   ============================================================ */
export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<StrategyView[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);

  // per-strategy data
  const [risk, setRisk] = useState<StrategyRiskResponse | null>(null);
  const [bars, setBars] = useState<StrategyBarsResponse | null>(null);
  const [barsLoading, setBarsLoading] = useState(false);
  const [riskLoading, setRiskLoading] = useState(false);

  // asset add input
  const [addSym, setAddSym] = useState("");
  const [addBusy, setAddBusy] = useState(false);

  // backtest
  const [btTemplate, setBtTemplate] = useState<StrategyTemplate>("sma");
  const [btLookback, setBtLookback] = useState(365);
  
  // backtest advanced parameters
  const [btFast, setBtFast] = useState(20);
  const [btSlow, setBtSlow] = useState(50);
  const [btRsiPeriod, setBtRsiPeriod] = useState(14);
  const [btRsiLow, setBtRsiLow] = useState(30);
  const [btRsiHigh, setBtRsiHigh] = useState(70);

  const [btRunning, setBtRunning] = useState(false);
  const [btResults, setBtResults] = useState<(BacktestBySymbolResponse & { symbol: string })[]>([]);

  /* ---------- load strategies ---------- */
  const load = useCallback(async () => {
    try {
      const d = await fundApiClient.getStrategies();
      const rows = (d.strategies || []).filter((s) => !s.archived);
      setStrategies(rows);
      if (!selected && rows.length) setSelected(rows[0].strategy_id);
    } catch {
      /* empty */
    } finally {
      setLoading(false);
    }
  }, [selected]);

  useEffect(() => {
    load();
  }, [load, tick]);

  /* ---------- load per-strategy data when selection changes ---------- */
  useEffect(() => {
    if (!selected) return;
    setRiskLoading(true);
    setBarsLoading(true);
    setBtResults([]);
    fundApiClient
      .getStrategyRisk(selected)
      .then(setRisk)
      .catch(() => setRisk(null))
      .finally(() => setRiskLoading(false));
    fundApiClient
      .getStrategyBars(selected)
      .then(setBars)
      .catch(() => setBars(null))
      .finally(() => setBarsLoading(false));
  }, [selected, tick]);

  const strat = strategies.find((s) => s.strategy_id === selected) || null;
  const assets: string[] = strat?.assets || [];

  /* ---------- add / remove asset ---------- */
  const addAsset = async () => {
    const sym = addSym.trim().toUpperCase();
    if (!sym || !selected) return;
    if (assets.includes(sym)) {
      setAddSym("");
      return;
    }
    setAddBusy(true);
    try {
      await fundApiClient.setStrategyAssets(selected, [...assets, sym]);
      setAddSym("");
      setTick((v) => v + 1);
    } catch {
      /* ignore */
    } finally {
      setAddBusy(false);
    }
  };

  const removeAsset = async (sym: string) => {
    if (!selected) return;
    const next = assets.filter((a) => a !== sym);
    try {
      if (next.length) {
        await fundApiClient.setStrategyAssets(selected, next);
      }
      setTick((v) => v + 1);
    } catch {
      /* ignore */
    }
  };

  /* ---------- create strategy sandbox ---------- */
  const createSandbox = async () => {
    const name = window.prompt("Enter name for the new Strategy Sandbox:", "My Sandbox");
    if (!name) return;
    try {
      const s = await fundApiClient.registerStrategy(name, "Draft Sandbox", undefined, "operator");
      await load();
      setSelected(s.strategy_id);
    } catch {
      alert("Failed to create strategy sandbox.");
    }
  };

  /* ---------- run backtest on all scoped assets ---------- */
  const runBacktest = async () => {
    if (!selected || !assets.length) return;
    setBtRunning(true);
    const results: typeof btResults = [];
    for (const sym of assets) {
      try {
        const res = await fundApiClient.runBacktestBySymbol(selected, {
          symbol: sym,
          strategy: btTemplate,
          lookback_days: btLookback,
          fast: btFast,
          slow: btSlow,
          rsi_period: btRsiPeriod,
          rsi_low: btRsiLow,
          rsi_high: btRsiHigh,
        });
        results.push({ ...res, symbol: sym });
      } catch {
        /* skip failed */
      }
    }
    setBtResults(results);
    setBtRunning(false);
    setTick((v) => v + 1);
  };

  const [optMethod, setOptMethod] = useState<'max_sharpe' | 'min_volatility'>('max_sharpe');
  const [optRunning, setOptRunning] = useState(false);
  const [optResponse, setOptResponse] = useState<StrategyOptimizeResponse | null>(null);

  const runOptimization = async () => {
    if (!selected || !assets.length) return;
    setOptRunning(true);
    try {
      const res = await fundApiClient.optimizeStrategy(selected, optMethod, btLookback);
      setOptResponse(res);
    } catch {
      /* ignore */
    } finally {
      setOptRunning(false);
    }
  };

  /* ============================================================ */
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <StudioHeader subtitle="Scope assets · backtest · price tickers · risk" />

      <div className="mx-auto max-w-[1400px] px-4 py-4 space-y-5">
        {/* Clark action bar */}
        <ClarkActionBar
          placeholder="Ask Clark… e.g. 'backtest momentum on AAPL' or 'scope NVDA into this strategy'"
          suggestions={["backtest sma on AAPL", "show strategy risk", "scope NVDA MSFT into Momentum"]}
          onDone={() => setTick((v) => v + 1)}
        />

        {loading ? (
          <div className="flex items-center justify-center py-20 text-zinc-500">
            <Loader2 className="animate-spin mr-2" size={18} /> Loading strategies…
          </div>
        ) : strategies.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-zinc-500 text-sm">
            <Layers size={40} className="mb-3 opacity-30" />
            No strategies registered yet.
          </div>
        ) : (
          <>
            {/* ---------- Strategy selector rail ---------- */}
            <div className="flex items-center gap-3 overflow-x-auto pb-1 scrollbar-thin scrollbar-track-transparent scrollbar-thumb-zinc-700">
              <button
                onClick={createSandbox}
                className="flex flex-col items-center justify-center gap-2 flex-none rounded-2xl border border-dashed border-zinc-700 bg-zinc-900/30 hover:bg-zinc-800/50 hover:border-teal-500/50 text-zinc-500 hover:text-teal-400 transition-all min-w-[120px] h-full py-4 min-h-[140px]"
              >
                <Plus size={24} />
                <span className="text-[11px] font-medium uppercase tracking-wider">New Sandbox</span>
              </button>
              {strategies.map((s) => {
                const active = s.strategy_id === selected;
                const pnl = s.pnl_usd ?? 0;
                const up = pnl >= 0;
                const actual = Math.min(100, s.actual_pct ?? 0);
                const target = Math.min(100, s.allocation_pct ?? 0);
                return (
                  <button
                    key={s.strategy_id}
                    onClick={() => setSelected(s.strategy_id)}
                    className={`flex-none rounded-2xl border p-4 min-w-[210px] text-left transition-all ${
                      active
                        ? "border-teal-500 bg-teal-500/5 shadow-lg shadow-teal-500/5"
                        : "border-zinc-800 bg-zinc-900/60 hover:border-zinc-700"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <span className="font-semibold text-sm text-white">{s.name}</span>
                      <span
                        className={`text-[9px] uppercase tracking-wide px-1.5 py-0.5 rounded-full border ${
                          STATE_STYLE[s.state] || STATE_STYLE.draft
                        }`}
                      >
                        {s.state}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-xs font-mono text-zinc-400">
                      <span className={up ? "text-emerald-400" : "text-red-400"}>
                        {up ? "+" : ""}
                        {money(pnl)}
                      </span>
                      <span>exp {money(s.exposure_usd)}</span>
                    </div>
                    <div className="relative mt-2.5 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-teal-500 to-sky-500 transition-all duration-500"
                        style={{ width: `${actual}%` }}
                      />
                      <div
                        className="absolute -top-0.5 h-2.5 w-0.5 bg-white/70 rounded"
                        style={{ left: `${target}%` }}
                        title="target"
                      />
                    </div>
                    <div className="flex justify-between text-[10px] text-zinc-500 font-mono mt-1">
                      <span>actual {pct(s.actual_pct)}</span>
                      <span>target {pct(s.allocation_pct)}</span>
                    </div>
                    {(s.assets?.length ?? 0) > 0 && (
                      <div className="flex gap-1 mt-2 flex-wrap">
                        {s.assets!.map((sym) => (
                          <span
                            key={sym}
                            className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700"
                          >
                            {sym}
                          </span>
                        ))}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>

            {/* ---------- Two-column layout ---------- */}
            {strat && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* ===== LEFT COLUMN ===== */}
                <div className="space-y-4">
                  {/* Assets panel */}
                  <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 overflow-hidden">
                    <div className="flex items-center justify-between px-5 py-3.5 border-b border-zinc-800">
                      <div className="flex items-center gap-2">
                        <Crosshair size={14} className="text-teal-400" />
                        <span className="text-xs font-medium uppercase tracking-widest text-zinc-500">
                          Scoped Assets
                        </span>
                      </div>
                      <span className="text-xs font-mono text-teal-400">{assets.length}</span>
                    </div>
                    <div className="px-5 py-3 space-y-1">
                      {assets.length === 0 && (
                        <p className="text-xs text-zinc-500 font-mono py-2">No assets scoped yet.</p>
                      )}
                      {assets.map((sym) => {
                        const b = bars?.bars?.[sym];
                        const last = b?.closes?.length ? b.closes[b.closes.length - 1] : null;
                        const prev =
                          b?.closes && b.closes.length > 1 ? b.closes[b.closes.length - 2] : last;
                        const chg = prev && last ? ((last - prev) / prev) * 100 : 0;
                        const up = chg >= 0;
                        return (
                          <div
                            key={sym}
                            className="flex items-center gap-3 py-2 border-b border-zinc-800/60 last:border-0"
                          >
                            <span className="font-mono text-sm font-bold text-white bg-zinc-800 px-2.5 py-1 rounded border border-zinc-700">
                              {sym}
                            </span>
                            <span className="font-mono text-sm text-zinc-300 ml-auto">
                              {last != null ? money(last) : "—"}
                            </span>
                            <span
                              className={`font-mono text-xs w-[54px] text-right ${up ? "text-emerald-400" : "text-red-400"}`}
                            >
                              {last != null ? `${up ? "+" : ""}${chg.toFixed(2)}%` : ""}
                            </span>
                            <button
                              onClick={() => removeAsset(sym)}
                              className="p-1 rounded hover:bg-zinc-800 text-zinc-500 hover:text-red-400 transition"
                            >
                              <X size={14} />
                            </button>
                          </div>
                        );
                      })}
                      <div className="flex gap-2 pt-2">
                        <Input
                          value={addSym}
                          onChange={(e) => setAddSym(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && addAsset()}
                          placeholder="Add symbol…"
                          className="bg-zinc-800 border-zinc-700 text-sm font-mono"
                        />
                        <Button
                          size="sm"
                          onClick={addAsset}
                          disabled={addBusy || !addSym.trim()}
                          className="bg-teal-600 hover:bg-teal-500 text-white"
                        >
                          {addBusy ? <Loader2 className="animate-spin" size={14} /> : <Plus size={14} />}
                        </Button>
                      </div>
                    </div>
                  </div>

                  {/* Price tickers */}
                  <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 overflow-hidden">
                    <div className="flex items-center gap-2 px-5 py-3.5 border-b border-zinc-800">
                      <BarChart3 size={14} className="text-teal-400" />
                      <span className="text-xs font-medium uppercase tracking-widest text-zinc-500">
                        Price Tickers
                      </span>
                    </div>
                    <div className="px-5 py-3">
                      {barsLoading ? (
                        <div className="flex items-center justify-center py-8 text-zinc-500">
                          <Loader2 className="animate-spin mr-2" size={16} /> Loading bars…
                        </div>
                      ) : !assets.length ? (
                        <p className="text-xs text-zinc-500 font-mono py-4 text-center">
                          Add assets to see price tickers.
                        </p>
                      ) : (
                        <table className="w-full text-xs font-mono">
                          <thead>
                            <tr className="text-zinc-500 text-[10px] uppercase tracking-wider">
                              <th className="text-left py-1.5">Sym</th>
                              <th className="text-right py-1.5">Last</th>
                              <th className="text-right py-1.5">1d</th>
                              <th className="text-right py-1.5 w-[110px]">Trend</th>
                            </tr>
                          </thead>
                          <tbody>
                            {assets.map((sym) => {
                              const b = bars?.bars?.[sym];
                              const closes = b?.closes || [];
                              const last = closes.length ? closes[closes.length - 1] : 0;
                              const prev = closes.length > 1 ? closes[closes.length - 2] : last;
                              const chg = prev ? ((last - prev) / prev) * 100 : 0;
                              const up = chg >= 0;
                              return (
                                <tr key={sym} className="border-t border-zinc-800/50">
                                  <td className="py-2 font-semibold text-zinc-200">{sym}</td>
                                  <td className="py-2 text-right text-zinc-300">{money(last)}</td>
                                  <td
                                    className={`py-2 text-right ${up ? "text-emerald-400" : "text-red-400"}`}
                                  >
                                    {up ? "+" : ""}
                                    {chg.toFixed(2)}%
                                  </td>
                                  <td className="py-2 text-right">
                                    <Sparkline closes={closes.slice(-60)} />
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      )}
                    </div>
                  </div>

                  {/* Portfolio Optimization */}
                  <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 overflow-hidden mt-5">
                    <div className="flex items-center gap-2 px-5 py-3.5 border-b border-zinc-800">
                      <Target size={14} className="text-teal-400" />
                      <span className="text-xs font-medium uppercase tracking-widest text-zinc-500">
                        PyPortfolioOpt Weights
                      </span>
                    </div>
                    <div className="px-5 py-4 space-y-4">
                      <div className="flex items-end gap-3">
                        <div className="flex-1 space-y-1">
                          <label className="text-[10px] uppercase tracking-wider text-zinc-500">
                            Objective
                          </label>
                          <select
                            value={optMethod}
                            onChange={(e) => setOptMethod(e.target.value as any)}
                            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg h-9 px-3 text-sm focus:ring-1 focus:ring-teal-500 focus:border-teal-500 outline-none"
                          >
                            <option value="max_sharpe">Max Sharpe Ratio</option>
                            <option value="min_volatility">Min Volatility</option>
                          </select>
                        </div>
                        <Button
                          onClick={runOptimization}
                          disabled={optRunning || !assets.length}
                          className="bg-teal-600 hover:bg-teal-500 text-white min-w-[120px]"
                        >
                          {optRunning ? <Loader2 className="animate-spin mr-2" size={16} /> : "Optimize"}
                        </Button>
                      </div>

                      {optResponse && (
                        <div className="pt-2">
                          <table className="w-full text-xs font-mono mb-4">
                            <thead>
                              <tr className="text-zinc-500 text-[10px] uppercase tracking-wider">
                                <th className="text-left py-1.5">Asset</th>
                                <th className="text-right py-1.5">Optimal Weight</th>
                              </tr>
                            </thead>
                            <tbody>
                              {Object.entries(optResponse.weights || {})
                                .sort((a, b) => b[1] - a[1])
                                .map(([sym, w]) => (
                                  <tr key={sym} className="border-t border-zinc-800/50">
                                    <td className="py-2 text-zinc-200">{sym}</td>
                                    <td className="py-2 text-right text-emerald-400">
                                      {(w * 100).toFixed(1)}%
                                    </td>
                                  </tr>
                                ))}
                            </tbody>
                          </table>
                          
                          <div className="space-y-6">
                            <div>
                              <div className="text-[10px] font-medium uppercase tracking-widest text-zinc-500 mb-2">Efficient Frontier</div>
                              <EfficientFrontierChart points={optResponse.frontier_points || []} optimalWeights={optResponse.weights || {}} height={200} />
                            </div>
                            
                            <div>
                              <div className="text-[10px] font-medium uppercase tracking-widest text-zinc-500 mb-2">Asset Correlation</div>
                              <CorrelationMatrix correlation={optResponse.correlation || {}} />
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* ===== RIGHT COLUMN ===== */}
                <div className="space-y-4">
                  {/* Backtest */}
                  <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 overflow-hidden">
                    <div className="flex items-center gap-2 px-5 py-3.5 border-b border-zinc-800">
                      <TrendingUp size={14} className="text-teal-400" />
                      <span className="text-xs font-medium uppercase tracking-widest text-zinc-500">
                        Backtest
                      </span>
                    </div>
                    <div className="px-5 py-4 space-y-3">
                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <label className="text-[10px] uppercase tracking-wider text-zinc-500">
                            Template
                          </label>
                          <select
                            value={btTemplate}
                            onChange={(e) => setBtTemplate(e.target.value as StrategyTemplate)}
                            className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm font-mono text-zinc-200 outline-none focus:border-teal-500"
                          >
                            <option value="sma">SMA Crossover</option>
                            <option value="rsi">RSI Mean-Reversion</option>
                            <option value="macd">MACD Trend</option>
                            <option value="bollinger">Bollinger Bands</option>
                            <option value="breakout">Donchian Breakout</option>
                            <option value="momentum">Momentum</option>
                            <option value="atr_trail">ATR Trailing</option>
                            <option value="buy_hold">Buy & Hold</option>
                          </select>
                        </div>
                        <div className="space-y-1">
                          <label className="text-[10px] uppercase tracking-wider text-zinc-500">
                            Lookback
                          </label>
                          <Input
                            type="number"
                            value={btLookback}
                            onChange={(e) => setBtLookback(Number(e.target.value) || 365)}
                            min={30}
                            max={2000}
                            className="bg-zinc-800 border-zinc-700 font-mono"
                          />
                        </div>
                      </div>

                      {/* dynamic parameters */}
                      {btTemplate === "sma" && (
                        <div className="grid grid-cols-2 gap-3 pt-1">
                          <div className="space-y-1">
                            <label className="text-[10px] uppercase tracking-wider text-zinc-500">Fast MA</label>
                            <Input type="number" value={btFast} onChange={(e) => setBtFast(Number(e.target.value))} className="bg-zinc-800 border-zinc-700 font-mono h-8 text-sm" />
                          </div>
                          <div className="space-y-1">
                            <label className="text-[10px] uppercase tracking-wider text-zinc-500">Slow MA</label>
                            <Input type="number" value={btSlow} onChange={(e) => setBtSlow(Number(e.target.value))} className="bg-zinc-800 border-zinc-700 font-mono h-8 text-sm" />
                          </div>
                        </div>
                      )}
                      {btTemplate === "rsi" && (
                        <div className="grid grid-cols-3 gap-3 pt-1">
                          <div className="space-y-1">
                            <label className="text-[10px] uppercase tracking-wider text-zinc-500">Period</label>
                            <Input type="number" value={btRsiPeriod} onChange={(e) => setBtRsiPeriod(Number(e.target.value))} className="bg-zinc-800 border-zinc-700 font-mono h-8 text-sm" />
                          </div>
                          <div className="space-y-1">
                            <label className="text-[10px] uppercase tracking-wider text-zinc-500">Oversold</label>
                            <Input type="number" value={btRsiLow} onChange={(e) => setBtRsiLow(Number(e.target.value))} className="bg-zinc-800 border-zinc-700 font-mono h-8 text-sm" />
                          </div>
                          <div className="space-y-1">
                            <label className="text-[10px] uppercase tracking-wider text-zinc-500">Overbought</label>
                            <Input type="number" value={btRsiHigh} onChange={(e) => setBtRsiHigh(Number(e.target.value))} className="bg-zinc-800 border-zinc-700 font-mono h-8 text-sm" />
                          </div>
                        </div>
                      )}

                      <Button
                        onClick={runBacktest}
                        disabled={btRunning || !assets.length}
                        className="bg-gradient-to-r from-teal-600 to-sky-600 text-white w-full"
                      >
                        {btRunning ? (
                          <>
                            <Loader2 className="animate-spin mr-2" size={14} /> Running…
                          </>
                        ) : (
                          <>
                            <Play size={14} className="mr-2" /> Run on {assets.length} asset
                            {assets.length > 1 ? "s" : ""}
                          </>
                        )}
                      </Button>

                      {/* Backtest results */}
                      {btResults.length > 0 && (
                        <div className="space-y-3 pt-2 animate-in fade-in slide-in-from-bottom-2 duration-300">
                          {/* aggregate KPIs */}
                          <div className="flex gap-2 flex-wrap">
                            <Stat
                              label="Avg Return"
                              value={pct(
                                (btResults.reduce((s, r) => s + (r.result?.total_return ?? 0), 0) /
                                  btResults.length) *
                                  100,
                                2,
                              )}
                              accent={
                                btResults.reduce((s, r) => s + (r.result?.total_return ?? 0), 0) >= 0
                                  ? "text-emerald-400"
                                  : "text-red-400"
                              }
                            />
                            <Stat
                              label="Avg Sharpe"
                              value={(
                                btResults.reduce((s, r) => s + (r.result?.sharpe ?? 0), 0) /
                                btResults.length
                              ).toFixed(2)}
                            />
                            <Stat
                              label="Worst DD"
                              value={pct(
                                Math.min(...btResults.map((r) => r.result?.max_drawdown ?? 0)) * 100,
                                2,
                              )}
                              accent="text-red-400"
                            />
                          </div>
                          {/* per-asset table */}
                          <table className="w-full text-xs font-mono">
                            <thead>
                              <tr className="text-zinc-500 text-[10px] uppercase tracking-wider">
                                <th className="text-left py-1">Sym</th>
                                <th className="text-right py-1">Return</th>
                                <th className="text-right py-1">Sharpe</th>
                                <th className="text-right py-1">DD</th>
                                <th className="text-right py-1">Trades</th>
                              </tr>
                            </thead>
                            <tbody>
                              {btResults.map((r) => {
                                const up = (r.result?.total_return ?? 0) >= 0;
                                return (
                                  <tr key={r.symbol} className="border-t border-zinc-800/50">
                                    <td className="py-1.5 font-semibold">{r.symbol}</td>
                                    <td
                                      className={`py-1.5 text-right ${up ? "text-emerald-400" : "text-red-400"}`}
                                    >
                                      {pct((r.result?.total_return ?? 0) * 100, 2)}
                                    </td>
                                    <td className="py-1.5 text-right text-zinc-300">
                                      {(r.result?.sharpe ?? 0).toFixed(2)}
                                    </td>
                                    <td className="py-1.5 text-right text-red-400">
                                      {pct((r.result?.max_drawdown ?? 0) * 100, 2)}
                                    </td>
                                    <td className="py-1.5 text-right text-zinc-300">
                                      {r.result?.n_trades ?? 0}
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                          {/* Equity sparkline for first result */}
                          {btResults[0]?.bars?.closes?.length > 1 && (
                            <div className="rounded-xl border border-zinc-800 bg-zinc-800/40 p-3">
                              <span className="text-[10px] uppercase tracking-wider text-zinc-500">
                                Equity · {btResults[0].symbol}
                              </span>
                              <div className="mt-2">
                                <Sparkline closes={btResults[0].bars.closes} w={500} h={80} />
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Risk */}
                  <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 overflow-hidden">
                    <div className="flex items-center gap-2 px-5 py-3.5 border-b border-zinc-800">
                      <ShieldAlert size={14} className="text-teal-400" />
                      <span className="text-xs font-medium uppercase tracking-widest text-zinc-500">
                        Strategy Risk
                      </span>
                    </div>
                    <div className="px-5 py-4">
                      {riskLoading ? (
                        <div className="flex items-center justify-center py-8 text-zinc-500">
                          <Loader2 className="animate-spin mr-2" size={16} /> Loading risk…
                        </div>
                      ) : !risk ? (
                        <p className="text-xs text-zinc-500 font-mono py-4 text-center">
                          No risk data yet.
                        </p>
                      ) : (
                        <div className="space-y-3">
                          {/* KPIs */}
                          <div className="flex gap-2 flex-wrap">
                            <Stat label="Exposure" value={money(risk.exposure_usd)} />
                            <Stat
                              label="P&L"
                              value={signed(risk.pnl_usd)}
                              accent={(risk.pnl_usd ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"}
                            />
                            <Stat label="HHI" value={String(Math.round(risk.concentration_hhi))} />
                            <Stat label="Assets" value={String(risk.n_assets)} />
                          </div>

                          {/* Allocation Donut */}
                          {risk.assets.length > 0 && (
                            <div className="py-2">
                              <AllocationDonut
                                positions={risk.assets.map(a => ({
                                  symbol: a.symbol,
                                  qty: a.qty,
                                  mark: 0,
                                  usd_value: a.value_usd
                                }))}
                                cash={0}
                                totalNav={risk.exposure_usd}
                                height={200}
                              />
                            </div>
                          )}

                          {/* per-asset risk table */}
                          {risk.assets.length > 0 && (
                            <table className="w-full text-xs font-mono">
                              <thead>
                                <tr className="text-zinc-500 text-[10px] uppercase tracking-wider">
                                  <th className="text-left py-1">Sym</th>
                                  <th className="text-right py-1">Qty</th>
                                  <th className="text-right py-1">Value</th>
                                  <th className="text-right py-1">Wt</th>
                                  <th className="text-right py-1">−10%</th>
                                  <th className="text-right py-1">−20%</th>
                                </tr>
                              </thead>
                              <tbody>
                                {risk.assets.map((a) => (
                                  <tr key={a.symbol} className="border-t border-zinc-800/50">
                                    <td className="py-1.5 font-semibold">{a.symbol}</td>
                                    <td className="py-1.5 text-right text-zinc-300">
                                      {a.qty.toFixed(2)}
                                    </td>
                                    <td className="py-1.5 text-right text-zinc-300">
                                      {money(a.value_usd)}
                                    </td>
                                    <td className="py-1.5 text-right text-zinc-400">{pct(a.weight_pct)}</td>
                                    <td className="py-1.5 text-right text-red-400">
                                      {money(a.shock_10_pct)}
                                    </td>
                                    <td className="py-1.5 text-right text-red-400">
                                      {money(a.shock_20_pct)}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}

                          {/* breach flags */}
                          {risk.flags.length > 0 && (
                            <div className="space-y-1.5">
                              {risk.flags.map((f, i) => (
                                <div
                                  key={i}
                                  className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs bg-red-500/10 border border-red-500/20 text-red-400"
                                >
                                  <AlertTriangle size={13} /> {f}
                                </div>
                              ))}
                            </div>
                          )}

                          {/* scenarios */}
                          {risk.scenarios.map((sc, i) => (
                            <div
                              key={i}
                              className="flex justify-between items-center py-1.5 border-b border-zinc-800/50 last:border-0 text-xs font-mono"
                            >
                              <span className="text-zinc-500">{sc.label}</span>
                              <span className="text-red-400">
                                {money(sc.pnl_usd)} → {money(sc.exposure_after)}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        <p className="text-center text-[11px] text-zinc-600 pt-4">
          Scope assets into a strategy · backtest against built-in templates · monitor asset + strategy risk
        </p>
      </div>
    </div>
  );
}
