"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { StudioHeader } from "../components/StudioHeader";
import { KT } from "../theme";
import {
  fundApiClient,
  StrategyView,
  CompositeView,
  ComposeWeightsResponse,
} from "../../../../lib/fund_api";
import { TVAreaChart } from "../components/TVAreaChart";
import {
  Layers,
  Plus,
  Sliders,
  ShieldAlert,
  Check,
  RotateCcw,
  Sparkles,
  TrendingUp,
  PieChart,
  Info,
  AlertTriangle,
  ArrowRight,
  Activity,
} from "lucide-react";

export default function StrategyComposerPage() {
  const [strategies, setStrategies] = useState<StrategyView[]>([]);
  const [selectedParentId, setSelectedParentId] = useState<string | null>(null);
  const [newParentName, setNewParentName] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [composite, setComposite] = useState<CompositeView | null>(null);
  const [memberWeights, setMemberWeights] = useState<Record<string, number>>({});
  const [selectedChildren, setSelectedChildren] = useState<string[]>([]);
  const [optLoading, setOptLoading] = useState(false);
  const [optMethod, setOptMethod] = useState<string | null>(null);
  const [optResults, setOptResults] = useState<ComposeWeightsResponse | null>(null);
  const [saving, setSaving] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  // 1. Fetch available strategies
  const fetchStrategies = useCallback(async () => {
    try {
      const res = await fundApiClient.getStrategies();
      setStrategies(res.strategies || []);
      if (!selectedParentId && res.strategies && res.strategies.length > 0) {
        const container = res.strategies.find((s) => (s.members && s.members.length > 0) || (s.children && s.children.length > 0));
        if (container) {
          setSelectedParentId(container.strategy_id);
        } else if (res.strategies[0]) {
          setSelectedParentId(res.strategies[0].strategy_id);
        }
      }
    } catch (err) {
      console.error("Failed to load strategies", err);
    }
  }, [selectedParentId]);

  useEffect(() => {
    fetchStrategies();
  }, [fetchStrategies]);

  // 2. Fetch composite view for selected parent strategy
  const fetchComposite = useCallback(async (parentId: string) => {
    try {
      const comp = await fundApiClient.getComposite(parentId);
      setComposite(comp);

      const weightsMap: Record<string, number> = {};
      const kids: string[] = [];
      (comp.members || []).forEach((m) => {
        weightsMap[m.child_id] = m.weight;
        kids.push(m.child_id);
      });
      setMemberWeights(weightsMap);
      setSelectedChildren(kids);
    } catch (err) {
      console.error("Failed to load composite view", err);
      setComposite(null);
    }
  }, []);

  useEffect(() => {
    if (selectedParentId) {
      fetchComposite(selectedParentId);
    }
  }, [selectedParentId, fetchComposite]);

  // Selected parent record
  const currentParent = useMemo(() => {
    return strategies.find((s) => s.strategy_id === selectedParentId) || null;
  }, [strategies, selectedParentId]);

  // Eligible child strategies (exclude self and descendants)
  const eligibleChildren = useMemo(() => {
    if (!selectedParentId) return strategies;
    return strategies.filter((s) => s.strategy_id !== selectedParentId && !s.archived);
  }, [strategies, selectedParentId]);

  // 3. Create container strategy
  const handleCreateParent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newParentName.trim()) return;
    setIsCreating(true);
    try {
      const created = await fundApiClient.registerStrategy(newParentName.trim(), "Composite Container", undefined, "operator");
      await fetchStrategies();
      setSelectedParentId(created.strategy_id);
      setNewParentName("");
      setStatusMsg({ type: "success", msg: `Created composite strategy "${created.name}"` });
    } catch (err: any) {
      setStatusMsg({ type: "error", msg: err?.response?.data?.detail || "Failed to create strategy" });
    } finally {
      setIsCreating(false);
    }
  };

  // 4. Member selection toggle
  const handleToggleChild = (childId: string) => {
    if (selectedChildren.includes(childId)) {
      const updated = selectedChildren.filter((id) => id !== childId);
      setSelectedChildren(updated);
      const newWeights = { ...memberWeights };
      delete newWeights[childId];
      setMemberWeights(newWeights);
    } else {
      setSelectedChildren([...selectedChildren, childId]);
      setMemberWeights({ ...memberWeights, [childId]: 0.25 });
    }
  };

  // 5. Weight change handler
  const handleWeightChange = (childId: string, val: number) => {
    const clamped = Math.max(0, Math.min(1, val));
    setMemberWeights((prev) => ({
      ...prev,
      [childId]: Math.round(clamped * 10000) / 10000,
    }));
  };

  // 6. Auto-weight optimizer handler (S2)
  const handleAutoWeight = async (method: "equal" | "risk_parity" | "hrp" | "max_sharpe" | "min_volatility") => {
    if (!selectedParentId) return;
    setOptLoading(true);
    setOptMethod(method);
    try {
      const res = await fundApiClient.composeWeights(selectedParentId, method, 365);
      setOptResults(res);
      if (res.weights) {
        setMemberWeights(res.weights);
        setSelectedChildren(Object.keys(res.weights));
      }
      setStatusMsg({ type: "success", msg: `Suggested weights via ${method.toUpperCase()}` });
    } catch (err: any) {
      setStatusMsg({ type: "error", msg: err?.response?.data?.detail || "Failed to optimize weights" });
    } finally {
      setOptLoading(false);
    }
  };

  // 7. Save & Deploy handler (S1 + lifecycle transition)
  const handleSaveAndDeploy = async (deploy = false) => {
    if (!selectedParentId) return;
    setSaving(true);
    try {
      await fundApiClient.setMemberWeights(selectedParentId, memberWeights, "operator");
      if (deploy) {
        await fundApiClient.setState(selectedParentId, "deployed", "operator");
      }
      await fetchStrategies();
      await fetchComposite(selectedParentId);
      setStatusMsg({
        type: "success",
        msg: deploy
          ? "Composite weights persisted and strategy deployed!"
          : "Composite weights updated.",
      });
    } catch (err: any) {
      setStatusMsg({ type: "error", msg: err?.response?.data?.detail || "Failed to persist composite" });
    } finally {
      setSaving(false);
    }
  };

  // Weight statistics calculation
  const totalWeightPct = useMemo(() => {
    const sum = Object.values(memberWeights).reduce((a, b) => a + b, 0);
    return Math.round(sum * 1000) / 10;
  }, [memberWeights]);

  const cashRemainderPct = useMemo(() => {
    return Math.max(0, Math.round((100 - totalWeightPct) * 10) / 10);
  }, [totalWeightPct]);

  return (
    <div className={KT.page}>
      <StudioHeader />

      <main className={KT.container}>
        {/* Top Title & Subtitle */}
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Sliders className="h-6 w-6 text-[var(--kt-accent)]" />
              <h1 className="text-2xl font-light tracking-tight text-[var(--kt-text-strong)]">Strategy Composer</h1>
            </div>
            <p className={KT.muted}>
              Multi-sleeve capital allocator — blend child strategies into composite meta-portfolios with HRP & Purged CV.
            </p>
          </div>

          {/* Quick Stats Pill */}
          <div className="flex items-center gap-3">
            <div className={`${KT.inset} flex items-center gap-3 px-4 py-2`}>
              <div className="text-right">
                <div className={KT.label}>TOTAL WEIGHT</div>
                <div className={`font-mono text-sm font-semibold ${totalWeightPct > 100 ? "text-[var(--kt-down)]" : "text-[var(--kt-text-strong)]"}`}>
                  {totalWeightPct}%
                </div>
              </div>
              <div className="h-6 w-px bg-[var(--kt-inset)]" />
              <div className="text-right">
                <div className={KT.label}>UNALLOCATED CASH</div>
                <div className="font-mono text-sm font-semibold text-[var(--kt-accent)]">
                  {cashRemainderPct}%
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Status Toast Notification */}
        {statusMsg && (
          <div
            className={`mb-6 flex items-center justify-between rounded-xl border px-4 py-3 text-sm ${
              statusMsg.type === "success"
                ? "border-emerald-500/30 bg-emerald-500/10 text-[var(--kt-accent)]"
                : "border-rose-500/30 bg-rose-500/10 text-[var(--kt-down)]"
            }`}
          >
            <div className="flex items-center gap-2">
              {statusMsg.type === "success" ? <Check size={16} /> : <AlertTriangle size={16} />}
              <span>{statusMsg.msg}</span>
            </div>
            <button onClick={() => setStatusMsg(null)} className="text-[var(--kt-text-dim)] hover:text-[var(--kt-text-strong)]">
              ✕
            </button>
          </div>
        )}

        {/* SECTION 1: Identity & Strategy Selection */}
        <div className={`${KT.card} mb-6`}>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="rounded-lg border border-[var(--kt-border)] bg-[var(--kt-surface)] p-2 text-[var(--kt-accent)]">
                <Layers size={20} />
              </div>
              <div>
                <div className={KT.label}>TARGET COMPOSITE STRATEGY</div>
                <select
                  value={selectedParentId || ""}
                  onChange={(e) => setSelectedParentId(e.target.value)}
                  className="mt-1 rounded-lg border border-[var(--kt-border)] bg-[var(--kt-inset)] px-3 py-1.5 font-mono text-sm text-[var(--kt-text)] outline-none focus:border-emerald-500/50"
                >
                  {strategies.map((s) => (
                    <option key={s.strategy_id} value={s.strategy_id}>
                      {s.name} ({s.state.toUpperCase()}) — {s.allocation_pct}% NAV
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Create New Composite Form */}
            <form onSubmit={handleCreateParent} className="flex items-center gap-2">
              <input
                type="text"
                placeholder="New composite name..."
                value={newParentName}
                onChange={(e) => setNewParentName(e.target.value)}
                className={KT.input}
              />
              <button
                type="submit"
                disabled={isCreating || !newParentName.trim()}
                className={`${KT.btn} flex items-center gap-1.5`}
              >
                <Plus size={14} /> Create Composite
              </button>
            </form>
          </div>

          {currentParent && (
            <div className="mt-4 flex flex-wrap items-center gap-4 border-t border-[var(--kt-border)] pt-3 text-xs">
              <span className={KT.chip}>{currentParent.state.toUpperCase()}</span>
              <span className={KT.muted}>Target Allocation: <strong className="text-[var(--kt-text-strong)]">{currentParent.allocation_pct}% NAV</strong></span>
              {currentParent.members && (
                <span className={KT.muted}>Active Sleeves: <strong className="text-[var(--kt-accent)]">{currentParent.members.length}</strong></span>
              )}
            </div>
          )}
        </div>

        {/* MAIN COMPOSER WORKSPACE GRID */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* LEFT COLUMN: Sleeve Selection & Weight Optimizers (col-span-7) */}
          <div className="space-y-6 lg:col-span-7">
            {/* Block 2: Sleeve Chooser */}
            <div className={KT.card}>
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <h3 className={KT.title}>1. Pick Child Sleeves</h3>
                  <p className={KT.muted}>Select component strategies to compose into this parent</p>
                </div>
                <span className={KT.label}>{selectedChildren.length} SELECTED</span>
              </div>

              <div className="space-y-2">
                {eligibleChildren.map((child) => {
                  const isSelected = selectedChildren.includes(child.strategy_id);
                  const sharpe = child.backtest?.sharpe;
                  return (
                    <div
                      key={child.strategy_id}
                      onClick={() => handleToggleChild(child.strategy_id)}
                      className={`flex cursor-pointer items-center justify-between rounded-xl border p-3 transition-colors ${
                        isSelected
                          ? "border-emerald-500/40 bg-emerald-500/5"
                          : "border-[var(--kt-border)] bg-[var(--kt-inset)] hover:border-[var(--kt-border)]"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={`flex h-5 w-5 items-center justify-center rounded border transition-colors ${
                            isSelected ? "border-emerald-400 bg-emerald-500/20 text-[var(--kt-accent)]" : "border-[var(--kt-border)] bg-[var(--kt-surface)]"
                          }`}
                        >
                          {isSelected && <Check size={12} />}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-[var(--kt-text)]">{child.name}</span>
                            <span className="rounded border border-[var(--kt-border)] bg-[var(--kt-surface)] px-1.5 py-0.5 text-[10px] text-[var(--kt-text-dim)]">
                              {child.state}
                            </span>
                          </div>
                          <div className="text-xs text-[var(--kt-text-muted)]">
                            Assets: {child.assets && child.assets.length ? child.assets.join(", ") : "All market"}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-4 text-right">
                        {sharpe !== undefined && sharpe !== null ? (
                          <div>
                            <div className={KT.label}>SHARPE</div>
                            <div className="font-mono text-xs font-semibold text-[var(--kt-accent)]">{sharpe.toFixed(2)}</div>
                          </div>
                        ) : (
                          <div className="text-xs text-[var(--kt-text-muted)]">No backtest</div>
                        )}
                        {child.exposure_usd ? (
                          <div>
                            <div className={KT.label}>EXPOSURE</div>
                            <div className="font-mono text-xs text-[var(--kt-text)]">${child.exposure_usd.toLocaleString()}</div>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Block 3: Weights & Auto-Optimizer Bar */}
            <div className={KT.card}>
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className={KT.title}>2. Sleeve Weights & Optimization</h3>
                  <p className={KT.muted}>Adjust manual weights or generate robust HRP allocations</p>
                </div>

                {/* Auto Buttons Bar */}
                <div className="flex flex-wrap items-center gap-1.5">
                  <button
                    onClick={() => handleAutoWeight("hrp")}
                    disabled={optLoading}
                    className={`${KT.btn} flex items-center gap-1 text-xs font-semibold`}
                  >
                    <Sparkles size={13} /> HRP (Default)
                  </button>
                  <button
                    onClick={() => handleAutoWeight("equal")}
                    disabled={optLoading}
                    className={`${KT.btnGhost} text-xs`}
                  >
                    Equal (1/N)
                  </button>
                  <button
                    onClick={() => handleAutoWeight("risk_parity")}
                    disabled={optLoading}
                    className={`${KT.btnGhost} text-xs`}
                  >
                    Risk-Parity
                  </button>
                  <button
                    onClick={() => handleAutoWeight("max_sharpe")}
                    disabled={optLoading}
                    className={`${KT.btnGhost} text-xs`}
                  >
                    Max-Sharpe
                  </button>
                </div>
              </div>

              {/* Sliders & Numeric Inputs */}
              {selectedChildren.length === 0 ? (
                <div className={`${KT.inset} py-8 text-center text-xs text-[var(--kt-text-muted)]`}>
                  No sleeves selected. Pick sleeves above to configure portfolio weights.
                </div>
              ) : (
                <div className="space-y-4">
                  {selectedChildren.map((cid) => {
                    const child = strategies.find((s) => s.strategy_id === cid);
                    const weightVal = memberWeights[cid] || 0;
                    const pctVal = Math.round(weightVal * 100);

                    return (
                      <div key={cid} className={`${KT.inset} p-3`}>
                        <div className="mb-2 flex items-center justify-between">
                          <span className="text-sm font-medium text-[var(--kt-text)]">{child?.name || cid}</span>
                          <div className="flex items-center gap-2">
                            <input
                              type="number"
                              min="0"
                              max="100"
                              step="1"
                              value={pctVal}
                              onChange={(e) => handleWeightChange(cid, (parseFloat(e.target.value) || 0) / 100)}
                              className="w-16 rounded border border-[var(--kt-border)] bg-[var(--kt-surface)] px-2 py-1 font-mono text-right text-xs text-[var(--kt-accent)] outline-none focus:border-emerald-500"
                            />
                            <span className="font-mono text-xs text-[var(--kt-text-dim)]">%</span>
                          </div>
                        </div>

                        <div className="flex items-center gap-3">
                          <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.01"
                            value={weightVal}
                            onChange={(e) => handleWeightChange(cid, parseFloat(e.target.value))}
                            className="h-1.5 flex-1 cursor-pointer accent-emerald-400"
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Cross-Validation & Purged CV Readout (S2) */}
              {optResults && (
                <div className="mt-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <span className={KT.label}>SKFOLIO PURGED CV DIAGNOSTICS ({optResults.method.toUpperCase()})</span>
                    <span className="text-xs text-[var(--kt-accent)] font-medium">Overfitting Risk (PBO)</span>
                  </div>
                  <div className="grid grid-cols-4 gap-2 text-center">
                    <div className="rounded border border-[var(--kt-border)] bg-[var(--kt-surface)] p-2">
                      <div className={KT.label}>EXPECTED SHARPE</div>
                      <div className="font-mono text-sm text-[var(--kt-accent)]">{optResults.expected?.sharpe ?? "—"}</div>
                    </div>
                    <div className="rounded border border-[var(--kt-border)] bg-[var(--kt-surface)] p-2">
                      <div className={KT.label}>ANNUALIZED VOL</div>
                      <div className="font-mono text-sm text-[var(--kt-text)]">
                        {optResults.expected?.vol ? `${(optResults.expected.vol * 100).toFixed(1)}%` : "—"}
                      </div>
                    </div>
                    <div className="rounded border border-[var(--kt-border)] bg-[var(--kt-surface)] p-2">
                      <div className={KT.label}>OUT-OF-SAMPLE SHARPE</div>
                      <div className="font-mono text-sm text-[var(--kt-accent)]">{optResults.cv?.oos_sharpe ?? "—"}</div>
                    </div>
                    <div className="rounded border border-[var(--kt-border)] bg-[var(--kt-surface)] p-2">
                      <div className={KT.label}>PBO (OVERFIT)</div>
                      <div className={`font-mono text-sm ${optResults.cv?.pbo > 0.3 ? "text-[var(--kt-down)]" : "text-[var(--kt-accent)]"}`}>
                        {optResults.cv?.pbo !== undefined ? `${(optResults.cv.pbo * 100).toFixed(0)}%` : "—"}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* RIGHT COLUMN: Live Composite Rollup & Performance (col-span-5) */}
          <div className="space-y-6 lg:col-span-5">
            {/* Block 4: Blended Equity Curve & Metrics (S3) */}
            <div className={KT.card}>
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h3 className={KT.title}>3. Live Composite Rollup</h3>
                  <p className={KT.muted}>Blended equity curve & combined risk/return</p>
                </div>
                <button
                  onClick={() => selectedParentId && fetchComposite(selectedParentId)}
                  className="text-[var(--kt-text-dim)] hover:text-[var(--kt-text-strong)]"
                  title="Refresh Rollup"
                >
                  <RotateCcw size={14} />
                </button>
              </div>

              {/* Combined Metrics Bar */}
              <div className="mb-4 grid grid-cols-3 gap-3">
                <div className={`${KT.inset} p-3 text-center`}>
                  <div className={KT.label}>BLENDED RETURN</div>
                  <div className="font-mono text-lg font-light text-[var(--kt-accent)]">
                    {composite?.metrics?.total_return !== undefined ? `+${composite.metrics.total_return}%` : "—"}
                  </div>
                </div>
                <div className={`${KT.inset} p-3 text-center`}>
                  <div className={KT.label}>BLENDED SHARPE</div>
                  <div className="font-mono text-lg font-light text-[var(--kt-text-strong)]">
                    {composite?.metrics?.sharpe ?? "—"}
                  </div>
                </div>
                <div className={`${KT.inset} p-3 text-center`}>
                  <div className={KT.label}>MAX DRAWDOWN</div>
                  <div className="font-mono text-lg font-light text-[var(--kt-down)]">
                    {composite?.metrics?.max_drawdown !== undefined ? `${(composite.metrics.max_drawdown * 100).toFixed(1)}%` : "—"}
                  </div>
                </div>
              </div>

              {/* Blended Equity Curve Chart */}
              {composite?.blended_equity && composite.blended_equity.length > 0 ? (
                <div className="rounded-xl border border-[var(--kt-border)] bg-[var(--kt-inset)] p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <span className={KT.label}>COMPOSITE PERFORMANCE</span>
                    <span className="font-mono text-xs text-[var(--kt-accent)] font-medium">Normalized (1.00)</span>
                  </div>
                  <TVAreaChart data={composite.blended_equity} height={200} />
                </div>
              ) : (
                <div className={`${KT.inset} flex h-48 items-center justify-center text-center text-xs text-[var(--kt-text-muted)]`}>
                  No equity curve available. Select child sleeves with backtests to preview blended performance.
                </div>
              )}
            </div>

            {/* Block 5: Composite Risk & Concentration */}
            <div className={KT.card}>
              <div className="mb-3 flex items-center justify-between">
                <h3 className={KT.title}>Composite Risk & Concentration</h3>
                <ShieldAlert size={16} className="text-[var(--kt-text-dim)]" />
              </div>

              <div className="mb-4 grid grid-cols-2 gap-3">
                <div className={`${KT.inset} p-3`}>
                  <div className={KT.label}>CONCENTRATION (HHI)</div>
                  <div className="font-mono text-base font-medium text-[var(--kt-text-strong)]">
                    {composite?.risk?.concentration_hhi ?? "0.000"}
                  </div>
                  <div className="text-[10px] text-[var(--kt-text-muted)]">Target HHI &lt; 0.40</div>
                </div>

                <div className={`${KT.inset} p-3`}>
                  <div className={KT.label}>DRAWDOWN VS LIMIT</div>
                  <div className="font-mono text-base font-medium text-[var(--kt-accent)]">
                    {composite?.risk?.drawdown_pct !== undefined ? `${(composite.risk.drawdown_pct * 100).toFixed(1)}%` : "0.0%"}
                  </div>
                  <div className="text-[10px] text-[var(--kt-text-muted)]">Max limit 15.0%</div>
                </div>
              </div>

              {/* Warning Flags List */}
              <div className="space-y-2">
                <span className={KT.label}>RISK FLAGS</span>
                {composite?.risk?.flags && composite.risk.flags.length > 0 ? (
                  composite.risk.flags.map((flag, idx) => (
                    <div key={idx} className="flex items-center gap-2 rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-[var(--kt-warn)]">
                      <AlertTriangle size={14} className="shrink-0" />
                      <span>{flag}</span>
                    </div>
                  ))
                ) : (
                  <div className="flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-xs text-[var(--kt-accent)]">
                    <Check size={14} className="shrink-0" />
                    <span>No portfolio concentration or leverage breaches detected.</span>
                  </div>
                )}
              </div>
            </div>

            {/* Block 6: Deploy Action Bar */}
            <div className={KT.card}>
              <div className="mb-3">
                <h3 className={KT.title}>Deploy Composite Allocation</h3>
                <p className={KT.muted}>Persist sleeve target weights to the spine and activate allocation</p>
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={() => handleSaveAndDeploy(true)}
                  disabled={saving || !selectedParentId}
                  className={`${KT.btn} flex-1 flex items-center justify-center gap-2 py-2.5 font-semibold`}
                >
                  <TrendingUp size={16} /> Save & Deploy Composite
                </button>
                <button
                  onClick={() => handleSaveAndDeploy(false)}
                  disabled={saving || !selectedParentId}
                  className={`${KT.btnGhost} px-4 py-2.5`}
                >
                  Save Weights
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
