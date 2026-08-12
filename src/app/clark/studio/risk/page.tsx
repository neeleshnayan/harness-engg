"use client";

import React, { useState, useEffect, useCallback } from "react";
import { StudioHeader } from "../components/StudioHeader";
import { ClarkActionBar } from "../components/ClarkActionBar";
import { GlassPanel } from "../components/ui/GlassPanel";
import { ConcentrationTreemap } from "../components/charts/ConcentrationTreemap";
import { AuditLogFeed } from "../components/AuditLogFeed";
import {
  fundApiClient,
  RiskMonitorResponse,
  RiskAlarmItem,
  RiskLimitsConfig,
  RiskMonitorPosition,
  RiskMonitorStrategy,
  SpineEvent,
} from "@/lib/fund_api";
import {
  Loader2,
  AlertTriangle,
  Zap,
  ShieldCheck,
  RefreshCw,
  Radio,
  ShieldAlert,
  Sliders,
  CheckCircle2,
  Activity,
  Play,
  OctagonAlert,
  ArrowUpRight,
  TrendingDown,
  Lock,
  Unlock,
  AlertCircle,
  Clock,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";

const pct = (n?: number | null, dp = 1) => (n == null ? "—" : `${Number(n).toFixed(dp)}%`);
const money = (n?: number | null) =>
  n == null
    ? "—"
    : `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function RiskPage() {
  const [monitor, setMonitor] = useState<RiskMonitorResponse | null>(null);
  const [activeAlerts, setActiveAlerts] = useState<RiskAlarmItem[]>([]);
  const [alertHistory, setAlertHistory] = useState<any[]>([]);
  const [events, setEvents] = useState<SpineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [livePolling, setLivePolling] = useState(true);
  const [actionBusy, setActionBusy] = useState(false);

  // Modals
  const [haltModalOpen, setHaltModalOpen] = useState(false);
  const [haltReason, setHaltReason] = useState("Manual risk intervention by operator");

  const [limitsModalOpen, setLimitsModalOpen] = useState(false);
  const [limitsForm, setLimitsForm] = useState<Partial<RiskLimitsConfig>>({});

  const load = useCallback(async (isSilent = false) => {
    if (!isSilent) setLoading(true);
    try {
      const [monRes, alertRes, historyRes, eventsRes] = await Promise.all([
        fundApiClient.getRiskMonitor(),
        fundApiClient.getRiskAlerts().catch(() => ({ active: [] })),
        fundApiClient.getRiskAlertHistory(50).catch(() => ({ history: [] })),
        fundApiClient.getEvents(100).catch(() => ({ events: [] })),
      ]);

      setMonitor(monRes);
      setActiveAlerts(alertRes.active || []);
      setAlertHistory(historyRes.history || []);
      setEvents(eventsRes.events || []);

      if (monRes.limits && !limitsModalOpen) {
        setLimitsForm(monRes.limits);
      }
    } catch (e) {
      // Ignore transient errors during polling
    } finally {
      setLoading(false);
    }
  }, [limitsModalOpen]);

  // 3-second live auto-polling loop
  useEffect(() => {
    load();
    let timer: NodeJS.Timeout | null = null;
    if (livePolling) {
      timer = setInterval(() => load(true), 3000);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [load, livePolling]);

  // Kill-Switch Actions
  const handleHalt = async () => {
    setActionBusy(true);
    try {
      await fundApiClient.haltTrading(haltReason, "operator");
      setHaltModalOpen(false);
      await load(false);
    } catch (err: any) {
      alert(`Halt failed: ${err.message || err}`);
    } finally {
      setActionBusy(false);
    }
  };

  const handleResume = async () => {
    if (!confirm("Confirm trading resumption? (Human operator sign-off required)")) return;
    setActionBusy(true);
    try {
      await fundApiClient.resumeTrading("operator");
      await load(false);
    } catch (err: any) {
      alert(`Resume failed: ${err.message || err}`);
    } finally {
      setActionBusy(false);
    }
  };

  const handleRunMonitor = async () => {
    setActionBusy(true);
    try {
      await fundApiClient.runRiskMonitor("operator");
      await load(false);
    } catch (err: any) {
      alert(`Monitor run failed: ${err.message || err}`);
    } finally {
      setActionBusy(false);
    }
  };

  const handleSaveLimits = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionBusy(true);
    try {
      await fundApiClient.setRiskLimits(limitsForm, "operator");
      setLimitsModalOpen(false);
      await load(false);
    } catch (err: any) {
      alert(`Limits update failed: ${err.message || err}`);
    } finally {
      setActionBusy(false);
    }
  };

  const isHalted = monitor?.halted ?? false;
  const drawdown = monitor?.drawdown;
  const util = monitor?.utilization;
  const limits = monitor?.limits;

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans selection:bg-teal-500/30">
      <StudioHeader subtitle="Institutional Live Risk Engine — Continuous Surveillance & Kill-Switch Cockpit" />

      <div className="mx-auto max-w-[1600px] space-y-6 px-6 py-6">
        {/* Top Control Bar & Live Status */}
        <div className="flex flex-wrap items-center justify-between gap-4 p-5 rounded-2xl bg-zinc-900/90 border border-zinc-800 shadow-xl backdrop-blur-md">
          <div className="flex items-center gap-4">
            <div
              className={`p-3 rounded-2xl border shadow-inner ${
                isHalted
                  ? "bg-rose-500/10 border-rose-500/30 text-rose-400"
                  : "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
              }`}
            >
              {isHalted ? <OctagonAlert size={28} className="animate-pulse" /> : <ShieldCheck size={28} />}
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-lg font-extrabold tracking-tight text-white font-mono">RISK ENGINE COCKPIT</h1>
                <span
                  className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono font-bold border ${
                    isHalted
                      ? "bg-rose-500/15 border-rose-500/40 text-rose-300 shadow-[0_0_12px_rgba(244,63,94,0.3)]"
                      : "bg-emerald-500/15 border-emerald-500/40 text-emerald-300 shadow-[0_0_12px_rgba(16,185,129,0.2)]"
                  }`}
                >
                  <span
                    className={`w-2.5 h-2.5 rounded-full ${
                      isHalted ? "bg-rose-500 animate-ping" : "bg-emerald-400 animate-pulse"
                    }`}
                  />
                  {isHalted ? "TRADING HALTED — KILL-SWITCH ACTIVE" : "TRADING LIVE — SURVEILLANCE ACTIVE"}
                </span>
              </div>
              <p className="text-xs text-zinc-400 mt-0.5">
                Deterministic event-sourced risk monitor folded directly from the spine event log
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {isHalted ? (
              <Button
                onClick={handleResume}
                disabled={actionBusy}
                className="bg-emerald-600 hover:bg-emerald-500 text-white font-mono font-bold text-xs px-4 h-9 shadow-lg shadow-emerald-950/50"
              >
                <Unlock size={14} className="mr-2" />
                Resume Trading (Human Only)
              </Button>
            ) : (
              <Button
                onClick={() => setHaltModalOpen(true)}
                disabled={actionBusy}
                className="bg-rose-600 hover:bg-rose-500 text-white font-mono font-bold text-xs px-4 h-9 shadow-lg shadow-rose-950/50"
              >
                <Lock size={14} className="mr-2" />
                Engage Kill-Switch Halt
              </Button>
            )}

            <Button
              onClick={handleRunMonitor}
              disabled={actionBusy}
              className="bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-mono text-xs px-3.5 h-9 border border-zinc-700"
            >
              <Zap size={14} className="mr-1.5 text-teal-400" />
              Run Monitor Tick
            </Button>

            <button
              onClick={() => setLivePolling((v) => !v)}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl border text-xs font-mono font-bold transition-all shadow-md ${
                livePolling
                  ? "bg-emerald-950/60 border-emerald-500/50 text-emerald-300 shadow-[0_0_15px_rgba(16,185,129,0.15)]"
                  : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:bg-zinc-800"
              }`}
            >
              <Radio size={14} className={livePolling ? "animate-pulse text-emerald-400" : "text-zinc-500"} />
              {livePolling ? "POLLING (3s)" : "PAUSED"}
            </button>

            <Button
              onClick={() => load(false)}
              disabled={loading}
              className="bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 text-xs px-3.5 h-9 text-zinc-200 font-mono font-semibold"
            >
              <RefreshCw size={13} className={`mr-1.5 ${loading ? "animate-spin text-teal-400" : ""}`} />
              Sync
            </Button>
          </div>
        </div>

        {/* Action Prompt */}
        <ClarkActionBar
          placeholder="Ask Clark AI… e.g. 'check portfolio drawdown limit' or 'explain active underwater positions'"
          suggestions={["check portfolio drawdown", "show live risk alarms", "edit mandate limits"]}
          onDone={() => load(false)}
        />

        {loading && !monitor ? (
          <div className="flex flex-col items-center justify-center py-28 text-zinc-400 gap-3 bg-zinc-900/40 rounded-2xl border border-zinc-800">
            <Loader2 className="animate-spin text-teal-400" size={36} />
            <span className="text-xs font-mono tracking-wide text-zinc-300">
              Folding live risk picture from spine event log...
            </span>
          </div>
        ) : !monitor ? (
          <div className="py-20 text-center text-zinc-500 bg-zinc-900/40 rounded-2xl border border-zinc-800">
            Spine risk engine unreachable. Ensure ClarkHarness server is running on :8090.
          </div>
        ) : (
          <>
            {/* KILL-SWITCH BANNER */}
            {isHalted && (
              <div className="p-5 rounded-2xl border-2 border-rose-500 bg-rose-950/40 shadow-2xl backdrop-blur-md flex items-center justify-between">
                <div className="flex items-start gap-4">
                  <div className="p-3 rounded-xl bg-rose-500/20 text-rose-400 border border-rose-500/40">
                    <OctagonAlert size={28} className="animate-bounce" />
                  </div>
                  <div>
                    <h2 className="text-base font-extrabold text-rose-200 font-mono tracking-wide">
                      TRADING HALTED — KILL-SWITCH ENGAGED
                    </h2>
                    <p className="text-xs text-rose-300/90 mt-1">
                      New BUY orders are automatically blocked by the pre-trade pipeline. SELL orders (de-risking) remain explicitly enabled.
                    </p>
                  </div>
                </div>

                <Button
                  onClick={handleResume}
                  disabled={actionBusy}
                  className="bg-rose-500 hover:bg-rose-400 text-zinc-950 font-mono font-black text-xs px-5 py-2.5 rounded-xl shadow-lg"
                >
                  <Unlock size={16} className="mr-2" />
                  RESUME TRADING
                </Button>
              </div>
            )}

            {/* KPI STAT CARDS */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              <div className="p-4 rounded-2xl bg-zinc-900/80 border border-zinc-800 shadow-lg backdrop-blur-md flex flex-col justify-between">
                <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-400">Total NAV</span>
                <div className="my-1.5">
                  <span className="text-2xl font-black font-mono text-white tracking-tight">
                    {money(monitor.nav_usd)}
                  </span>
                </div>
                <span className="text-[10px] text-zinc-500">Live Spine Valuation</span>
              </div>

              <div className="p-4 rounded-2xl bg-zinc-900/80 border border-zinc-800 shadow-lg backdrop-blur-md flex flex-col justify-between">
                <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-400">Cash Buffer</span>
                <div className="my-1.5">
                  <span className="text-2xl font-black font-mono text-emerald-400 tracking-tight">
                    {pct(monitor.cash_pct, 1)}
                  </span>
                </div>
                <span className="text-[10px] font-mono text-emerald-500">{money(monitor.cash_usd)}</span>
              </div>

              <div className="p-4 rounded-2xl bg-zinc-900/80 border border-zinc-800 shadow-lg backdrop-blur-md flex flex-col justify-between">
                <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-400">Gross Exposure</span>
                <div className="my-1.5">
                  <span className="text-2xl font-black font-mono text-teal-300 tracking-tight">
                    {pct(monitor.gross_exposure_pct, 1)}
                  </span>
                </div>
                <span className="text-[10px] font-mono text-zinc-400">{money(monitor.gross_exposure_usd)}</span>
              </div>

              <div className="p-4 rounded-2xl bg-zinc-900/80 border border-zinc-800 shadow-lg backdrop-blur-md flex flex-col justify-between">
                <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-400">Current Drawdown</span>
                <div className="my-1.5">
                  <span
                    className={`text-2xl font-black font-mono tracking-tight ${
                      (drawdown?.drawdown_pct ?? 0) > 0 ? "text-rose-400" : "text-emerald-400"
                    }`}
                  >
                    -{pct(drawdown?.drawdown_pct, 2)}
                  </span>
                </div>
                <span className="text-[10px] text-zinc-500 font-mono">Limit: {pct(drawdown?.limit_pct, 1)}</span>
              </div>

              <div className="p-4 rounded-2xl bg-zinc-900/80 border border-zinc-800 shadow-lg backdrop-blur-md flex flex-col justify-between">
                <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-400">Worst Position</span>
                <div className="my-1.5 flex items-baseline gap-2">
                  <span className="text-xl font-black font-mono text-rose-400 tracking-tight">
                    {monitor.worst_position ? pct(monitor.worst_position.unrealized_pnl_pct, 1) : "N/A"}
                  </span>
                  {monitor.worst_position && (
                    <span className="text-xs font-bold text-rose-300 bg-rose-950/80 px-2 py-0.5 rounded border border-rose-800 font-mono">
                      {monitor.worst_position.symbol}
                    </span>
                  )}
                </div>
                <span className="text-[10px] text-zinc-500 font-mono">
                  Limit: -{pct((limits?.underwater_pct ?? 0.15) * 100, 0)}
                </span>
              </div>

              <div className="p-4 rounded-2xl bg-zinc-900/80 border border-zinc-800 shadow-lg backdrop-blur-md flex flex-col justify-between">
                <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-400">Active Breaches</span>
                <div className="my-1.5 flex items-center gap-2">
                  <span
                    className={`text-2xl font-black font-mono ${
                      activeAlerts.length > 0 ? "text-amber-400" : "text-emerald-400"
                    }`}
                  >
                    {activeAlerts.length}
                  </span>
                  <span className="text-xs text-zinc-400 font-mono">Alarms</span>
                </div>
                <button
                  onClick={() => setLimitsModalOpen(true)}
                  className="text-[10px] text-teal-400 hover:text-teal-300 font-mono font-bold underline text-left"
                >
                  Edit Mandate Limits →
                </button>
              </div>
            </div>

            {/* MANDATE LIMIT UTILIZATION GAUGES */}
            <div className="p-6 rounded-2xl bg-zinc-900/90 border border-zinc-800 shadow-xl backdrop-blur-md space-y-4">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-xl bg-teal-500/10 text-teal-400 border border-teal-500/20">
                    <Activity size={18} />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-white tracking-tight">MANDATE LIMIT UTILIZATION GAUGES</h2>
                    <p className="text-xs text-zinc-400">Real-time risk budget utilization across fund safety thresholds</p>
                  </div>
                </div>

                <Button
                  onClick={() => setLimitsModalOpen(true)}
                  className="bg-zinc-800 hover:bg-zinc-700 text-teal-300 border border-zinc-700 text-xs px-3.5 h-8 font-mono"
                >
                  <Sliders size={13} className="mr-1.5" />
                  Configure Limits
                </Button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 pt-1 font-mono">
                {/* Gauge 1: Position Concentration */}
                <div className="p-4 rounded-xl bg-zinc-950/70 border border-zinc-800/80">
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-zinc-400 font-sans font-bold">Max Position Weight</span>
                    <span className="text-teal-300 font-bold">{pct((util?.max_position_pct ?? 0) * 100, 0)}</span>
                  </div>
                  <div className="w-full h-2.5 rounded-full bg-zinc-900 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        (util?.max_position_pct ?? 0) >= 1.0
                          ? "bg-rose-500"
                          : (util?.max_position_pct ?? 0) >= 0.8
                          ? "bg-amber-400"
                          : "bg-teal-400"
                      }`}
                      style={{ width: `${Math.min(100, (util?.max_position_pct ?? 0) * 100)}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-zinc-500 mt-1.5 block">
                    Limit: {pct((limits?.max_position_pct ?? 0.2) * 100, 0)} of NAV
                  </span>
                </div>

                {/* Gauge 2: Strategy Exposure */}
                <div className="p-4 rounded-xl bg-zinc-950/70 border border-zinc-800/80">
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-zinc-400 font-sans font-bold">Max Strategy Cap</span>
                    <span className="text-teal-300 font-bold">{pct((util?.max_strategy_pct ?? 0) * 100, 0)}</span>
                  </div>
                  <div className="w-full h-2.5 rounded-full bg-zinc-900 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        (util?.max_strategy_pct ?? 0) >= 1.0
                          ? "bg-rose-500"
                          : (util?.max_strategy_pct ?? 0) >= 0.8
                          ? "bg-amber-400"
                          : "bg-emerald-400"
                      }`}
                      style={{ width: `${Math.min(100, (util?.max_strategy_pct ?? 0) * 100)}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-zinc-500 mt-1.5 block">
                    Limit: {pct((limits?.max_strategy_pct ?? 0.4) * 100, 0)} of NAV
                  </span>
                </div>

                {/* Gauge 3: Minimum Cash Floor */}
                <div className="p-4 rounded-xl bg-zinc-950/70 border border-zinc-800/80">
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-zinc-400 font-sans font-bold">Cash Buffer Deficit</span>
                    <span className="text-teal-300 font-bold">{pct((util?.min_cash_pct ?? 0) * 100, 0)}</span>
                  </div>
                  <div className="w-full h-2.5 rounded-full bg-zinc-900 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        (util?.min_cash_pct ?? 0) > 0 ? "bg-amber-400" : "bg-emerald-400"
                      }`}
                      style={{ width: `${Math.min(100, (util?.min_cash_pct ?? 0) * 100)}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-zinc-500 mt-1.5 block">
                    Floor: {pct((limits?.min_cash_pct ?? 0.1) * 100, 0)} of NAV
                  </span>
                </div>

                {/* Gauge 4: Drawdown Cap */}
                <div className="p-4 rounded-xl bg-zinc-950/70 border border-zinc-800/80">
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-zinc-400 font-sans font-bold">Drawdown Budget</span>
                    <span className="text-teal-300 font-bold">{pct((drawdown?.utilization ?? 0) * 100, 0)}</span>
                  </div>
                  <div className="w-full h-2.5 rounded-full bg-zinc-900 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        (drawdown?.utilization ?? 0) >= 1.0
                          ? "bg-rose-500"
                          : (drawdown?.utilization ?? 0) >= 0.8
                          ? "bg-amber-400"
                          : "bg-teal-400"
                      }`}
                      style={{ width: `${Math.min(100, (drawdown?.utilization ?? 0) * 100)}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-zinc-500 mt-1.5 block">
                    Limit: -{pct((limits?.max_drawdown_pct ?? 0.15) * 100, 0)}
                  </span>
                </div>
              </div>
            </div>

            {/* LIVE RISK ALARM FEED & AUDIT LOG */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Active Alarms */}
              <div className="p-6 rounded-2xl bg-zinc-900/90 border border-zinc-800 shadow-xl backdrop-blur-md space-y-4">
                <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
                      <ShieldAlert size={18} />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-white tracking-tight">ACTIVE RISK BREACH ALARMS</h3>
                      <p className="text-xs text-zinc-400">Currently open mandate breaches (deduped by key)</p>
                    </div>
                  </div>
                  <span className="text-xs font-mono font-bold px-2.5 py-1 rounded bg-zinc-950 border border-zinc-800 text-amber-300">
                    {activeAlerts.length} Active
                  </span>
                </div>

                {activeAlerts.length === 0 ? (
                  <div className="py-12 text-center text-zinc-500 font-mono text-xs bg-zinc-950/40 rounded-xl border border-zinc-800/60 flex flex-col items-center gap-2">
                    <CheckCircle2 size={24} className="text-emerald-400" />
                    All risk metrics within mandate safety parameters
                  </div>
                ) : (
                  <div className="space-y-2.5 max-h-[320px] overflow-y-auto pr-1">
                    {activeAlerts.map((alarm, idx) => (
                      <div
                        key={alarm.key || idx}
                        className={`p-3.5 rounded-xl border text-xs font-mono flex items-start justify-between ${
                          alarm.severity === "critical"
                            ? "bg-rose-950/40 border-rose-500/50 text-rose-200"
                            : "bg-amber-950/40 border-amber-500/50 text-amber-200"
                        }`}
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2 font-bold font-sans">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] uppercase font-mono ${
                                alarm.severity === "critical"
                                  ? "bg-rose-500 text-zinc-950 font-black"
                                  : "bg-amber-500 text-zinc-950 font-black"
                              }`}
                            >
                              {alarm.severity}
                            </span>
                            <span className="text-white">{alarm.message}</span>
                          </div>
                          <div className="text-[11px] text-zinc-400 flex items-center gap-3">
                            <span>Key: {alarm.key}</span>
                            <span>Observed: {alarm.metric.toFixed(2)}</span>
                            <span>Threshold: {alarm.threshold.toFixed(2)}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Alarm Audit Feed */}
              <div className="p-6 rounded-2xl bg-zinc-900/90 border border-zinc-800 shadow-xl backdrop-blur-md space-y-4">
                <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-xl bg-teal-500/10 text-teal-400 border border-teal-500/20">
                      <Clock size={18} />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-white tracking-tight">ALARM AUDIT EVENT STREAM</h3>
                      <p className="text-xs text-zinc-400">Chronological feed of raised & cleared risk alarm events</p>
                    </div>
                  </div>
                  <span className="text-xs font-mono text-zinc-400">Event-Sourced</span>
                </div>

                {alertHistory.length === 0 ? (
                  <div className="py-12 text-center text-zinc-500 font-mono text-xs bg-zinc-950/40 rounded-xl border border-zinc-800/60">
                    No alarm history events recorded.
                  </div>
                ) : (
                  <div className="space-y-2 max-h-[320px] overflow-y-auto pr-1">
                    {alertHistory.map((e: any, idx: number) => {
                      const isRaised = e.type === "RISK_ALARM_RAISED";
                      const p = e.payload || {};
                      return (
                        <div
                          key={idx}
                          className="flex items-center justify-between p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/80 text-xs font-mono"
                        >
                          <div className="flex items-center gap-3">
                            <span
                              className={`w-2.5 h-2.5 rounded-full ${
                                isRaised ? "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.5)]" : "bg-emerald-400"
                              }`}
                            />
                            <span className="text-zinc-400">{e.created_at ? new Date(e.created_at).toLocaleTimeString() : `Seq #${e.seq}`}</span>
                            <span className="text-zinc-200 font-sans">
                              {p.message || p.key || e.type}
                            </span>
                          </div>
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              isRaised
                                ? "bg-amber-950/80 text-amber-400 border border-amber-800/50"
                                : "bg-emerald-950/80 text-emerald-400 border border-emerald-800/50"
                            }`}
                          >
                            {isRaised ? "RAISED" : "CLEARED"}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* IMMUTABLE SPINE EVENT STREAM AUDIT LOG */}
            <div className="pt-2">
              <AuditLogFeed events={events} />
            </div>

            {/* PER-ASSET RISK TABLE */}
            <div className="p-6 rounded-2xl bg-zinc-900/90 border border-zinc-800 shadow-xl backdrop-blur-md space-y-4">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-xl bg-teal-500/10 text-teal-400 border border-teal-500/20">
                    <Activity size={18} />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-white tracking-tight">PER-ASSET RISK & SENSITIVITY TABLE</h2>
                    <p className="text-xs text-zinc-400">Position weights, unrealized P&L %, and -20% factor shock vulnerability</p>
                  </div>
                </div>
                <span className="text-xs font-mono text-zinc-400">
                  Active Names: <strong className="text-white">{monitor.positions.length}</strong>
                </span>
              </div>

              {monitor.positions.length === 0 ? (
                <div className="py-12 text-center text-zinc-500 font-mono text-xs bg-zinc-950/40 rounded-xl border border-zinc-800/60">
                  No active asset positions in portfolio.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-zinc-800/80 text-[11px] font-bold uppercase tracking-wider text-zinc-400 bg-zinc-950/60">
                        <th className="px-4 py-3.5 text-left">Symbol</th>
                        <th className="px-4 py-3.5 text-right">Quantity</th>
                        <th className="px-4 py-3.5 text-right">Mark Price</th>
                        <th className="px-4 py-3.5 text-right">Value USD</th>
                        <th className="px-4 py-3.5 text-right">Weight in NAV</th>
                        <th className="px-4 py-3.5 text-right">Unrealized P&L (%)</th>
                        <th className="px-4 py-3.5 text-right">-20% Shock Impact</th>
                        <th className="px-4 py-3.5 text-center">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/60 font-mono">
                      {monitor.positions.map((p: RiskMonitorPosition) => {
                        const isUnderwater = p.unrealized_pnl_pct < -((limits?.underwater_pct ?? 0.15) * 100);
                        const isOverweight = p.weight_pct > ((limits?.max_position_pct ?? 0.20) * 100);

                        return (
                          <tr key={p.symbol} className="hover:bg-zinc-800/40 transition-colors">
                            <td className="px-4 py-3.5 font-sans font-bold text-teal-300">
                              <span className="bg-zinc-950 px-2.5 py-1 rounded border border-zinc-800 font-mono">
                                {p.symbol}
                              </span>
                            </td>
                            <td className="px-4 py-3.5 text-right text-zinc-200">{p.qty}</td>
                            <td className="px-4 py-3.5 text-right text-zinc-200">{money(p.mark)}</td>
                            <td className="px-4 py-3.5 text-right font-bold text-white">{money(p.value_usd)}</td>
                            <td className="px-4 py-3.5 text-right font-bold text-teal-300">
                              <span className={isOverweight ? "text-rose-400 font-black" : ""}>
                                {pct(p.weight_pct, 1)}
                              </span>
                            </td>
                            <td className="px-4 py-3.5 text-right">
                              <span
                                className={`font-bold ${
                                  p.unrealized_pnl_pct >= 0
                                    ? "text-emerald-400"
                                    : isUnderwater
                                    ? "text-rose-400 font-black"
                                    : "text-rose-300"
                                }`}
                              >
                                {p.unrealized_pnl_pct >= 0 ? "+" : ""}
                                {pct(p.unrealized_pnl_pct, 2)}
                              </span>
                            </td>
                            <td className="px-4 py-3.5 text-right text-rose-400 font-bold">
                              {money(p.shock_20_usd)}
                            </td>
                            <td className="px-4 py-3.5 text-center">
                              {isOverweight ? (
                                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-950 text-rose-300 border border-rose-800">
                                  OVERWEIGHT
                                </span>
                              ) : isUnderwater ? (
                                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950 text-amber-300 border border-amber-800">
                                  UNDERWATER
                                </span>
                              ) : (
                                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">
                                  COMPLIANT
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* PER-STRATEGY RISK TABLE */}
            <div className="p-6 rounded-2xl bg-zinc-900/90 border border-zinc-800 shadow-xl backdrop-blur-md space-y-4">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-xl bg-teal-500/10 text-teal-400 border border-teal-500/20">
                    <Sliders size={18} />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-white tracking-tight">PER-STRATEGY RISK ATTRIBUTION</h2>
                    <p className="text-xs text-zinc-400">Strategy exposures, NAV weights, P&L, and strategy cap utilization</p>
                  </div>
                </div>
                <span className="text-xs font-mono text-zinc-400">
                  Strategies: <strong className="text-white">{monitor.strategies.length}</strong>
                </span>
              </div>

              {monitor.strategies.length === 0 ? (
                <div className="py-12 text-center text-zinc-500 font-mono text-xs bg-zinc-950/40 rounded-xl border border-zinc-800/60">
                  No active strategies deployed.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-zinc-800/80 text-[11px] font-bold uppercase tracking-wider text-zinc-400 bg-zinc-950/60">
                        <th className="px-4 py-3.5 text-left">Strategy Name</th>
                        <th className="px-4 py-3.5 text-right">Exposure USD</th>
                        <th className="px-4 py-3.5 text-right">Weight in NAV</th>
                        <th className="px-4 py-3.5 text-right">Net P&L USD</th>
                        <th className="px-4 py-3.5 text-right">Strategy Cap Limit</th>
                        <th className="px-4 py-3.5 text-right">Cap Utilization</th>
                        <th className="px-4 py-3.5 text-center">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/60 font-mono">
                      {monitor.strategies.map((s: RiskMonitorStrategy) => (
                        <tr key={s.strategy_id} className="hover:bg-zinc-800/40 transition-colors">
                          <td className="px-4 py-3.5 font-sans font-semibold text-white">
                            {s.name}
                            <span className="text-[10px] font-mono text-zinc-400 block font-normal">{s.strategy_id}</span>
                          </td>
                          <td className="px-4 py-3.5 text-right font-bold text-white">{money(s.exposure_usd)}</td>
                          <td className="px-4 py-3.5 text-right font-bold text-teal-300">{pct(s.weight_pct, 1)}</td>
                          <td
                            className={`px-4 py-3.5 text-right font-bold ${
                              s.pnl_usd >= 0 ? "text-emerald-400" : "text-rose-400"
                            }`}
                          >
                            {s.pnl_usd >= 0 ? "+" : ""}
                            {money(s.pnl_usd)}
                          </td>
                          <td className="px-4 py-3.5 text-right text-zinc-400">{pct(s.limit_pct, 0)}</td>
                          <td className="px-4 py-3.5 text-right text-teal-300">{pct(s.utilization * 100, 0)}</td>
                          <td className="px-4 py-3.5 text-center">
                            {s.breach ? (
                              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-950 text-rose-300 border border-rose-800">
                                BREACH
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">
                                COMPLIANT
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* TREEMAP EXPOSURE VISUALIZER */}
            {monitor.positions.length > 0 && (
              <GlassPanel title="Portfolio Exposure Concentration Treemap" className="border-zinc-800">
                <div className="min-h-[300px] pt-2">
                  <ConcentrationTreemap
                    positions={monitor.positions.map((p) => ({ symbol: p.symbol, usd_value: p.value_usd }))}
                    totalNav={monitor.nav_usd || 0}
                    height={300}
                  />
                </div>
              </GlassPanel>
            )}
          </>
        )}
      </div>

      {/* HALT CONFIRMATION MODAL */}
      {haltModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-rose-500/50 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center gap-2 text-rose-400 font-bold font-mono">
                <Lock size={18} />
                <span>CONFIRM KILL-SWITCH HALT</span>
              </div>
              <button onClick={() => setHaltModalOpen(false)} className="text-zinc-400 hover:text-white">
                <X size={18} />
              </button>
            </div>

            <p className="text-xs text-zinc-300">
              Engaging the kill-switch will immediately halt all BUY order submissions across the fund pipeline.
            </p>

            <div className="space-y-1.5">
              <label className="text-[11px] font-bold uppercase tracking-wider text-zinc-400 font-mono">
                Halt Reason / Audit Note
              </label>
              <textarea
                value={haltReason}
                onChange={(e) => setHaltReason(e.target.value)}
                rows={3}
                className="w-full rounded-xl bg-zinc-950 border border-zinc-800 p-3 text-xs text-white font-mono outline-none focus:border-rose-500"
              />
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <Button
                onClick={() => setHaltModalOpen(false)}
                className="bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-300 font-mono"
              >
                Cancel
              </Button>
              <Button
                onClick={handleHalt}
                disabled={actionBusy}
                className="bg-rose-600 hover:bg-rose-500 text-white font-mono font-bold text-xs"
              >
                Confirm Kill-Switch Halt
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* LIMITS CONFIGURATION MODAL */}
      {limitsModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <form
            onSubmit={handleSaveLimits}
            className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center gap-2 text-teal-400 font-bold font-mono">
                <Sliders size={18} />
                <span>CONFIGURE MANDATE RISK LIMITS</span>
              </div>
              <button type="button" onClick={() => setLimitsModalOpen(false)} className="text-zinc-400 hover:text-white">
                <X size={18} />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4 font-mono text-xs">
              <div className="space-y-1">
                <label className="text-[10px] uppercase font-bold text-zinc-400">Max Position Weight</label>
                <input
                  type="number"
                  step="0.01"
                  value={limitsForm.max_position_pct ?? 0.20}
                  onChange={(e) => setLimitsForm({ ...limitsForm, max_position_pct: parseFloat(e.target.value) })}
                  className="w-full rounded-xl bg-zinc-950 border border-zinc-800 p-2.5 text-white outline-none focus:border-teal-500"
                />
                <span className="text-[9px] text-zinc-500">e.g. 0.20 = 20% of NAV</span>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] uppercase font-bold text-zinc-400">Max Strategy Weight</label>
                <input
                  type="number"
                  step="0.01"
                  value={limitsForm.max_strategy_pct ?? 0.40}
                  onChange={(e) => setLimitsForm({ ...limitsForm, max_strategy_pct: parseFloat(e.target.value) })}
                  className="w-full rounded-xl bg-zinc-950 border border-zinc-800 p-2.5 text-white outline-none focus:border-teal-500"
                />
                <span className="text-[9px] text-zinc-500">e.g. 0.40 = 40% of NAV</span>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] uppercase font-bold text-zinc-400">Min Cash Floor</label>
                <input
                  type="number"
                  step="0.01"
                  value={limitsForm.min_cash_pct ?? 0.10}
                  onChange={(e) => setLimitsForm({ ...limitsForm, min_cash_pct: parseFloat(e.target.value) })}
                  className="w-full rounded-xl bg-zinc-950 border border-zinc-800 p-2.5 text-white outline-none focus:border-teal-500"
                />
                <span className="text-[9px] text-zinc-500">e.g. 0.10 = 10% of NAV</span>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] uppercase font-bold text-zinc-400">Max Drawdown Limit</label>
                <input
                  type="number"
                  step="0.01"
                  value={limitsForm.max_drawdown_pct ?? 0.15}
                  onChange={(e) => setLimitsForm({ ...limitsForm, max_drawdown_pct: parseFloat(e.target.value) })}
                  className="w-full rounded-xl bg-zinc-950 border border-zinc-800 p-2.5 text-white outline-none focus:border-teal-500"
                />
                <span className="text-[9px] text-zinc-500">e.g. 0.15 = 15% drawdown</span>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] uppercase font-bold text-zinc-400">Max Daily Loss Limit</label>
                <input
                  type="number"
                  step="0.01"
                  value={limitsForm.max_daily_loss_pct ?? 0.05}
                  onChange={(e) => setLimitsForm({ ...limitsForm, max_daily_loss_pct: parseFloat(e.target.value) })}
                  className="w-full rounded-xl bg-zinc-950 border border-zinc-800 p-2.5 text-white outline-none focus:border-teal-500"
                />
                <span className="text-[9px] text-zinc-500">e.g. 0.05 = 5% daily loss</span>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] uppercase font-bold text-zinc-400">Underwater Limit</label>
                <input
                  type="number"
                  step="0.01"
                  value={limitsForm.underwater_pct ?? 0.15}
                  onChange={(e) => setLimitsForm({ ...limitsForm, underwater_pct: parseFloat(e.target.value) })}
                  className="w-full rounded-xl bg-zinc-950 border border-zinc-800 p-2.5 text-white outline-none focus:border-teal-500"
                />
                <span className="text-[9px] text-zinc-500">e.g. 0.15 = 15% loss on position</span>
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-3 border-t border-zinc-800">
              <Button
                type="button"
                onClick={() => setLimitsModalOpen(false)}
                className="bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-300 font-mono"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={actionBusy}
                className="bg-teal-600 hover:bg-teal-500 text-white font-mono font-bold text-xs"
              >
                Save Mandate Limits
              </Button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
