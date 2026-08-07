"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Activity,
  ArrowUpRight,
  Check,
  Loader2,
  MessageSquare,
  Plus,
  RefreshCw,
  Search,
  TrendingUp,
  X,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import {
  fundApiClient,
  LpView,
  MemoView,
  NavResponse,
  PendingOrder,
  StrategiesResponse,
  StrategyView,
  ThesisView,
} from "@/lib/fund_api";
import { CreateStrategyModal } from "./components/CreateStrategyModal";
import { StrategyDetailModal } from "./components/StrategyDetailModal";
import { BacktestModal } from "./components/BacktestModal";
import { AllocationModal } from "./components/AllocationModal";
import { RiskPanel } from "./components/RiskPanel";
import { ThesisPanel } from "./components/ThesisPanel";
import { TVAreaChart, TVPoint } from "./components/TVAreaChart";

/* ---------- formatting helpers ---------- */
const money = (n?: number | null, dp = 2) =>
  n == null
    ? "—"
    : `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp })}`;
const compact = (n?: number | null) =>
  n == null ? "—" : `$${Number(n).toLocaleString(undefined, { notation: "compact", maximumFractionDigits: 1 })}`;
const pct = (n?: number | null, dp = 1) => (n == null ? "0.0%" : `${Number(n).toFixed(dp)}%`);
const signed = (n?: number | null) => (n == null ? "—" : `${n >= 0 ? "+" : ""}${money(n)}`);

const STATE_STYLE: Record<string, string> = {
  deployed: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  backtested: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  draft: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
  paused: "bg-amber-500/15 text-amber-300 border-amber-500/30",
};

/* ---------- small presentational pieces ---------- */
function Stat({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-lg border border-zinc-800/80 bg-zinc-900/40 px-3.5 py-2.5">
      <span className="text-[10px] font-medium uppercase tracking-widest text-zinc-500">{label}</span>
      <span className={`font-mono text-lg leading-tight ${accent || "text-zinc-100"}`}>{value}</span>
      {sub && <span className="text-[11px] text-zinc-500">{sub}</span>}
    </div>
  );
}

function StateBadge({ state }: { state: string }) {
  return (
    <span className={`rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide border ${STATE_STYLE[state] || STATE_STYLE.draft}`}>
      {state}
    </span>
  );
}

/* ---------- page ---------- */
export default function StrategyStudioPage() {
  const [strat, setStrat] = useState<StrategiesResponse | null>(null);
  const [nav, setNav] = useState<NavResponse | null>(null);
  const [lps, setLps] = useState<LpView[]>([]);
  const [pending, setPending] = useState<PendingOrder[]>([]);
  const [thesisCtx, setThesisCtx] = useState<Record<string, { thesis: ThesisView; memo?: MemoView }>>({});
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [lastSync, setLastSync] = useState<Date | null>(null);
  const [tick, setTick] = useState(0);
  const [busyOrder, setBusyOrder] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [backtestTarget, setBacktestTarget] = useState<StrategyView | null>(null);
  const [detailTarget, setDetailTarget] = useState<StrategyView | null>(null);
  const [allocTarget, setAllocTarget] = useState<StrategyView | null>(null);

  // Chart panel state
  const [chartSymbol, setChartSymbol] = useState("SPY");
  const [chartInput, setChartInput] = useState("SPY");
  const [chartData, setChartData] = useState<TVPoint[]>([]);
  const [chartMeta, setChartMeta] = useState<{ source?: string; range?: string } | null>(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartErr, setChartErr] = useState<string | null>(null);

  const { toast } = useToast();
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async (soft = false) => {
    try {
      if (!soft) setErr(null);
      const [s, n, l, p] = await Promise.all([
        fundApiClient.getStrategies(),
        fundApiClient.getNav(),
        fundApiClient.getLps(),
        fundApiClient.getPending(),
      ]);
      setStrat(s);
      setNav(n);
      setLps(l.lps || []);
      setPending(p.pending || []);
      setLastSync(new Date());
      setTick((v) => v + 1);
      setErr(null);
    } catch (e: unknown) {
      const msg = (e as { message?: string })?.message || "Could not reach the fund spine.";
      if (!soft) setErr(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  // Enrich pending orders that reference a thesis with the thesis + its latest
  // memo, so the approval card renders the *case*, not just the ticket.
  useEffect(() => {
    const ids = Array.from(new Set(pending.map((o) => o.thesis_id).filter(Boolean))) as string[];
    if (ids.length === 0) {
      setThesisCtx({});
      return;
    }
    let cancelled = false;
    (async () => {
      const entries = await Promise.all(
        ids.map(async (id) => {
          try {
            const thesis = await fundApiClient.getThesis(id);
            let memo: MemoView | undefined;
            if (thesis.memo_ids?.length) {
              const m = await fundApiClient.getThesisMemos(id);
              memo = m.memos?.[m.memos.length - 1];
            }
            return [id, { thesis, memo }] as const;
          } catch {
            return null;
          }
        }),
      );
      if (!cancelled) {
        setThesisCtx(Object.fromEntries(entries.filter(Boolean) as [string, { thesis: ThesisView; memo?: MemoView }][]));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pending]);

  const loadChart = useCallback(async (symbol: string) => {
    setChartLoading(true);
    setChartErr(null);
    try {
      const b = await fundApiClient.getBars(symbol, 180);
      const dates = b.dates || [];
      const points: TVPoint[] = b.closes.map((v, i) => ({ t: dates[i] || String(i), v }));
      setChartData(points);
      setChartSymbol(b.symbol);
      setChartMeta({ source: b.source, range: b.start && b.end ? `${b.start} → ${b.end}` : undefined });
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setChartErr(detail || "Could not load bars.");
      setChartData([]);
    } finally {
      setChartLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    loadChart("SPY");
    timer.current = setInterval(() => load(true), 6000);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [load, loadChart]);

  const strategies = strat?.strategies || [];
  const live = nav?.live;
  const positions = live?.positions || [];

  // Layered cake: order children directly under their parent for the table.
  const orderedStrategies = useMemo(() => {
    const byParent = new Map<string, StrategyView[]>();
    strategies.forEach((s) => {
      if (s.parent_id) {
        const a = byParent.get(s.parent_id) || [];
        a.push(s);
        byParent.set(s.parent_id, a);
      }
    });
    const out: StrategyView[] = [];
    const pushWithKids = (s: StrategyView) => {
      out.push(s);
      (byParent.get(s.strategy_id) || []).forEach(pushWithKids);
    };
    strategies.filter((s) => !s.parent_id).forEach(pushWithKids);
    strategies.forEach((s) => {
      if (!out.includes(s)) out.push(s);
    }); // orphans (parent missing)
    return out;
  }, [strategies]);

  const deployedCount = strategies.filter((s) => s.state === "deployed").length;
  const totalExposure = strategies.reduce((a, s) => a + (s.exposure_usd || 0), 0);
  const totalPnl = strategies.reduce((a, s) => a + (s.pnl_usd || 0), 0);

  const setState = async (s: StrategyView, state: "deployed" | "paused") => {
    try {
      await fundApiClient.setState(s.strategy_id, state);
      toast({ title: state === "deployed" ? "Deployed" : "Paused", description: s.name });
      load(true);
    } catch (e: unknown) {
      const d = (e as { response?: { data?: { detail?: string } }; message?: string });
      toast({ title: "Action failed", description: d?.response?.data?.detail || d?.message });
    }
  };

  const decide = async (o: PendingOrder, approve: boolean) => {
    setBusyOrder(o.order_id);
    try {
      const r = approve
        ? await fundApiClient.approveOrder(o.order_id, "rushi")
        : await fundApiClient.declineOrder(o.order_id, "rushi");
      if (approve) await fundApiClient.settle();
      toast({
        title: approve ? "Order approved" : "Order declined",
        description: `${o.side.toUpperCase()} ${o.qty} ${o.symbol}${approve ? ` — ${r?.status || "working"}` : ""}`,
      });
      load(true);
    } catch (e: unknown) {
      const d = (e as { response?: { data?: { detail?: string } }; message?: string });
      toast({ title: "Failed", description: d?.response?.data?.detail || d?.message });
    } finally {
      setBusyOrder(null);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* top bar */}
      <div className="sticky top-0 z-10 border-b border-zinc-800/80 bg-zinc-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-3 px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded bg-gradient-to-br from-teal-500 to-sky-600">
              <TrendingUp size={15} className="text-white" />
            </div>
            <div className="leading-tight">
              <div className="text-sm font-semibold">Krypton Fund · Strategy Studio</div>
              <div className="flex items-center gap-1.5 text-[11px] text-zinc-500">
                <span className={`h-1.5 w-1.5 rounded-full ${err ? "bg-red-500" : "bg-emerald-500"}`} />
                {err ? "spine unreachable" : "live"}
                {lastSync && !err && <span>· synced {lastSync.toLocaleTimeString()}</span>}
              </div>
            </div>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <Link
              href="/clark"
              className="flex h-8 items-center gap-1.5 rounded-md border border-zinc-700 px-3 text-sm text-zinc-200 hover:bg-zinc-800"
            >
              <MessageSquare size={14} /> Clark
            </Link>
            <Button variant="outline" className="h-8 border-zinc-700 bg-transparent text-zinc-200" onClick={() => load()}>
              <RefreshCw size={14} className="mr-1.5" /> Refresh
            </Button>
            <Button className="h-8 bg-gradient-to-r from-teal-600 to-sky-600 text-white" onClick={() => setCreateOpen(true)}>
              <Plus size={14} className="mr-1.5" /> New strategy
            </Button>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-[1400px] px-4 py-4">
        {err && (
          <div className="mb-4 rounded-lg border border-red-800/50 bg-red-950/30 p-3 text-sm text-red-300">
            {err} — is ClarkHarness running on :8090 and <code>NEXT_PUBLIC_HARNESS_API_URL</code> set?
          </div>
        )}

        {/* KPI strip */}
        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label="NAV" value={compact(live?.total_nav_usd)} sub={`${money(live?.nav_per_unit, 4)}/unit`} accent="text-teal-300" />
          <Stat label="Cash" value={compact(live?.breakdown?.cash)} sub={`${pct(live && live.total_nav_usd ? (live.breakdown.cash / live.total_nav_usd) * 100 : 0)} of NAV`} />
          <Stat label="Deployed Exp." value={compact(totalExposure)} sub={`${deployedCount} live ${deployedCount === 1 ? "strategy" : "strategies"}`} />
          <Stat label="Unrealized P&L" value={signed(totalPnl)} accent={totalPnl >= 0 ? "text-emerald-400" : "text-red-400"} />
          <Stat label="LPs" value={String(lps.length)} sub={`${(live?.units_outstanding || 0).toLocaleString()} units`} />
          <Stat label="Pending" value={String(pending.length)} sub="awaiting approval" accent={pending.length ? "text-amber-300" : "text-zinc-100"} />
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
          {/* left: strategies + chart */}
          <div className="lg:col-span-2 space-y-4">
            {/* chart panel */}
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-3">
              <div className="mb-2 flex items-center gap-2">
                <Activity size={14} className="text-teal-400" />
                <span className="text-sm font-semibold">{chartSymbol}</span>
                <span className="text-[11px] text-zinc-500">
                  daily · {chartMeta?.source || "—"} {chartMeta?.range ? `· ${chartMeta.range}` : ""}
                </span>
                <form
                  className="ml-auto flex items-center gap-1"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (chartInput.trim()) loadChart(chartInput.trim().toUpperCase());
                  }}
                >
                  <div className="flex items-center rounded-md border border-zinc-700 bg-zinc-800/60 px-2">
                    <Search size={12} className="text-zinc-500" />
                    <input
                      value={chartInput}
                      onChange={(e) => setChartInput(e.target.value)}
                      placeholder="symbol"
                      className="w-20 bg-transparent px-1.5 py-1 text-xs uppercase outline-none placeholder:text-zinc-600"
                    />
                  </div>
                  <Button type="submit" variant="outline" className="h-7 border-zinc-700 bg-transparent px-2 text-xs text-zinc-200">
                    Load
                  </Button>
                </form>
              </div>
              {chartErr ? (
                <div className="flex h-[220px] items-center justify-center text-xs text-red-400">{chartErr}</div>
              ) : chartLoading && !chartData.length ? (
                <div className="flex h-[220px] items-center justify-center text-zinc-500">
                  <Loader2 className="animate-spin" size={18} />
                </div>
              ) : (
                <TVAreaChart data={chartData} height={220} />
              )}
            </div>

            {/* strategies table */}
            <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/40">
              <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-2.5">
                <span className="text-sm font-semibold">Strategies</span>
                <span className="text-[11px] text-zinc-500">{strategies.length} total · target vs actual allocation</span>
              </div>
              {loading ? (
                <div className="flex items-center gap-2 p-6 text-sm text-zinc-500">
                  <Loader2 className="animate-spin" size={16} /> Loading…
                </div>
              ) : strategies.length === 0 ? (
                <div className="p-8 text-center text-sm text-zinc-500">No strategies yet. Create one to begin.</div>
              ) : (
                <div className="divide-y divide-zinc-800/70">
                  {orderedStrategies.map((s) => {
                    const isChild = !!s.parent_id;
                    const exposureShown = s.is_container ? s.rolled_exposure_usd ?? s.exposure_usd : s.exposure_usd;
                    const pnlShown = s.is_container ? s.rolled_pnl_usd ?? s.pnl_usd : s.pnl_usd;
                    const up = (pnlShown ?? 0) >= 0;
                    const actual = Math.min(100, (s.is_container ? s.rolled_actual_pct : s.actual_pct) ?? 0);
                    const target = Math.min(100, s.allocation_pct ?? 0);
                    const sharpe = s.backtest?.sharpe;
                    const ret = s.backtest?.total_return;
                    return (
                      <div key={s.strategy_id} className="grid grid-cols-12 items-center gap-2 px-4 py-2.5 hover:bg-zinc-800/30">
                        <div className="col-span-3 min-w-0">
                          <div className={`flex items-center gap-1.5 ${isChild ? "pl-4" : ""}`}>
                            {isChild && <span className="text-zinc-600">└</span>}
                            <button
                              onClick={() => setDetailTarget(s)}
                              className="truncate text-left text-sm font-medium hover:text-teal-300 hover:underline"
                              title="View performance"
                            >
                              {s.name}
                            </button>
                            {s.is_container && (
                              <span className="rounded bg-sky-500/15 px-1 py-0.5 text-[9px] font-semibold uppercase text-sky-300">container</span>
                            )}
                          </div>
                          <div className={`mt-0.5 ${isChild ? "pl-4" : ""}`}><StateBadge state={s.state} /></div>
                        </div>
                        {/* allocation bar */}
                        <div className="col-span-3">
                          <div className="relative h-1.5 rounded-full bg-zinc-800">
                            <div className="h-full rounded-full bg-gradient-to-r from-teal-500 to-sky-500" style={{ width: `${actual}%` }} />
                            <div className="absolute -top-1 h-3.5 w-0.5 bg-zinc-100/80" style={{ left: `${target}%` }} title={`target ${target}%`} />
                          </div>
                          <div className="mt-1 flex justify-between font-mono text-[10px] text-zinc-500">
                            <span>act {pct(s.actual_pct)}</span>
                            <span>tgt {pct(s.allocation_pct)}</span>
                          </div>
                        </div>
                        <div className="col-span-2 text-right font-mono text-xs text-zinc-300">{money(exposureShown)}</div>
                        <div className={`col-span-1 text-right font-mono text-xs ${up ? "text-emerald-400" : "text-red-400"}`}>
                          {pnlShown == null ? "—" : `${up ? "+" : ""}${Number(pnlShown).toFixed(0)}`}
                        </div>
                        <div className="col-span-1 text-right font-mono text-[11px] text-zinc-400" title="backtest sharpe / return">
                          {sharpe != null ? sharpe.toFixed(2) : "—"}
                          {ret != null && <div className={ret >= 0 ? "text-emerald-500/80" : "text-red-500/80"}>{(ret * 100).toFixed(1)}%</div>}
                        </div>
                        <div className="col-span-2 flex justify-end gap-1">
                          <button className="rounded border border-zinc-700 px-1.5 py-0.5 text-[10px] text-zinc-300 hover:bg-zinc-800" onClick={() => setBacktestTarget(s)}>
                            Test
                          </button>
                          {s.state !== "deployed" ? (
                            <button className="rounded bg-teal-600/90 px-1.5 py-0.5 text-[10px] text-white hover:bg-teal-600" onClick={() => setState(s, "deployed")}>
                              Deploy
                            </button>
                          ) : (
                            <button className="rounded border border-amber-700/50 px-1.5 py-0.5 text-[10px] text-amber-300 hover:bg-amber-900/20" onClick={() => setState(s, "paused")}>
                              Pause
                            </button>
                          )}
                          <button className="rounded border border-zinc-700 px-1.5 py-0.5 text-[10px] text-zinc-300 hover:bg-zinc-800" onClick={() => setAllocTarget(s)}>
                            Alloc
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* positions */}
            <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/40">
              <div className="border-b border-zinc-800 px-4 py-2.5 text-sm font-semibold">Positions</div>
              {positions.length === 0 ? (
                <div className="p-6 text-center text-sm text-zinc-500">Flat — no open positions.</div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-[10px] uppercase tracking-wide text-zinc-500">
                      <th className="px-4 py-1.5 text-left font-medium">Symbol</th>
                      <th className="px-4 py-1.5 text-right font-medium">Qty</th>
                      <th className="px-4 py-1.5 text-right font-medium">Mark</th>
                      <th className="px-4 py-1.5 text-right font-medium">Value</th>
                      <th className="px-4 py-1.5 text-right font-medium">% NAV</th>
                    </tr>
                  </thead>
                  <tbody className="font-mono">
                    {positions.map((p) => (
                      <tr key={p.symbol} className="border-t border-zinc-800/60">
                        <td className="px-4 py-1.5 font-sans font-medium">{p.symbol}</td>
                        <td className="px-4 py-1.5 text-right text-zinc-300">{p.qty}</td>
                        <td className="px-4 py-1.5 text-right text-zinc-300">{money(p.mark)}</td>
                        <td className="px-4 py-1.5 text-right text-zinc-100">{money(p.usd_value)}</td>
                        <td className="px-4 py-1.5 text-right text-zinc-500">
                          {pct(live && live.total_nav_usd ? (p.usd_value / live.total_nav_usd) * 100 : 0)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {/* right rail */}
          <div className="space-y-4">
            {/* pending approvals */}
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40">
              <div className="flex items-center gap-2 border-b border-zinc-800 px-4 py-2.5">
                <span className="text-sm font-semibold">Pending approvals</span>
                {pending.length > 0 && (
                  <span className="rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-amber-300">{pending.length}</span>
                )}
              </div>
              {pending.length === 0 ? (
                <div className="p-6 text-center text-sm text-zinc-500">Queue clear.</div>
              ) : (
                <div className="divide-y divide-zinc-800/70">
                  {pending.map((o) => {
                    const ip = o.impact_preview || {};
                    const ctx = o.thesis_id ? thesisCtx[o.thesis_id] : undefined;
                    return (
                      <div key={o.order_id} className="p-3">
                        <div className="flex items-center gap-2">
                          <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${o.side === "buy" ? "bg-emerald-500/15 text-emerald-300" : "bg-red-500/15 text-red-300"}`}>
                            {o.side}
                          </span>
                          <span className="font-mono text-sm">{o.qty} {o.symbol}</span>
                          <span className="ml-auto font-mono text-xs text-zinc-400">{money(ip.notional_usd)}</span>
                        </div>
                        <div className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-0.5 font-mono text-[10px] text-zinc-500">
                          <span>px {money(ip.quote_price)}</span>
                          <span>cash → {money(ip.cash_after)}</span>
                        </div>
                        {/* the case for the trade: thesis + Clark's memo */}
                        {ctx ? (
                          <div className="mt-2 rounded-md border border-teal-800/40 bg-teal-950/20 p-2">
                            <div className="flex items-center gap-1.5">
                              <span className="rounded bg-teal-500/20 px-1 py-0.5 text-[9px] font-semibold uppercase text-teal-300">thesis</span>
                              <span className="min-w-0 truncate text-[11px] font-medium text-teal-200">{ctx.thesis.title}</span>
                            </div>
                            {ctx.thesis.claim && <p className="mt-1 text-[11px] text-zinc-400">{ctx.thesis.claim}</p>}
                            {ctx.memo?.recommendation && (
                              <p className="mt-1 text-[11px] text-teal-300">▸ {ctx.memo.recommendation}</p>
                            )}
                          </div>
                        ) : o.thesis_id ? null : (
                          <div className="mt-2 text-[10px] italic text-amber-500/70">discretionary — no thesis</div>
                        )}
                        <div className="mt-2 flex gap-2">
                          <Button
                            className="h-7 flex-1 bg-emerald-600 text-white hover:bg-emerald-700"
                            disabled={busyOrder === o.order_id}
                            onClick={() => decide(o, true)}
                          >
                            {busyOrder === o.order_id ? <Loader2 size={13} className="animate-spin" /> : <><Check size={13} className="mr-1" /> Approve</>}
                          </Button>
                          <Button
                            variant="outline"
                            className="h-7 flex-1 border-zinc-700 bg-transparent text-zinc-300"
                            disabled={busyOrder === o.order_id}
                            onClick={() => decide(o, false)}
                          >
                            <X size={13} className="mr-1" /> Decline
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* theses — every trade should reference one */}
            <ThesisPanel refreshKey={tick} onChanged={() => load(true)} />

            {/* analytical risk cockpit */}
            <RiskPanel refreshKey={tick} />

            {/* LP book */}
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40">
              <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-2.5">
                <span className="text-sm font-semibold">LP book</span>
                <span className="text-[11px] text-zinc-500">{lps.length} investors</span>
              </div>
              {lps.length === 0 ? (
                <div className="p-6 text-center text-sm text-zinc-500">No LPs yet.</div>
              ) : (
                <div className="divide-y divide-zinc-800/70">
                  {lps.map((l) => {
                    const ownership = live && live.total_nav_usd ? (l.value_usd / live.total_nav_usd) * 100 : 0;
                    return (
                      <div key={l.lp_id} className="flex items-center gap-3 px-4 py-2">
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm">{l.name || l.lp_id}</div>
                          <div className="font-mono text-[10px] text-zinc-500">{l.units.toLocaleString()} units · {pct(ownership)}</div>
                        </div>
                        <div className="text-right font-mono text-sm text-zinc-200">{money(l.value_usd)}</div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="flex items-center justify-center gap-1 text-[11px] text-zinc-600">
              <ArrowUpRight size={12} /> spine :8090 · free bars via Yahoo/Alpaca
            </div>
          </div>
        </div>
      </div>

      <CreateStrategyModal isOpen={createOpen} onClose={() => setCreateOpen(false)} onSuccess={() => load(true)} strategies={strategies} />
      <BacktestModal
        strategy={backtestTarget}
        onClose={() => setBacktestTarget(null)}
        onSuccess={() => load(true)}
        onCharted={(symbol, points) => {
          setChartData(points);
          setChartSymbol(symbol);
          setChartMeta({ source: "backtest" });
        }}
      />
      <AllocationModal strategy={allocTarget} onClose={() => setAllocTarget(null)} onSuccess={() => load(true)} />
      <StrategyDetailModal strategy={detailTarget} all={strategies} navUsd={strat?.nav_usd} onClose={() => setDetailTarget(null)} />
    </div>
  );
}
