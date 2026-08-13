"use client";

import { KT } from "./theme";
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
  OrderHistoryRow,
  PendingOrder,
  StrategiesResponse,
  StrategyView,
  ThesisView,
} from "@/lib/fund_api";
import { CreateStrategyModal } from "./components/CreateStrategyModal";
import { StrategyDetailModal } from "./components/StrategyDetailModal";
import { StrategyManageModal } from "./components/StrategyManageModal";
import { BacktestModal } from "./components/BacktestModal";
import { AllocationModal } from "./components/AllocationModal";
import { RebalanceModal } from "./components/RebalanceModal";
import { SimulationModal } from "./components/SimulationModal";
import { ShieldAlert, Radio, Scale } from "lucide-react";
import { RiskPanel } from "./components/RiskPanel";
import { ThesisPanel } from "./components/ThesisPanel";
import { OrderBlotter } from "./components/OrderBlotter";
import { AllocationDonut } from "./components/charts/AllocationDonut";
import { StrategyPerformanceBar } from "./components/charts/StrategyPerformanceBar";
import HeroChart from "./components/charts/HeroChart";
import { StatusPulse } from "./components/ui/StatusPulse";
import { StrategyCard } from "./components/ui/StrategyCard";
import { StudioHeader } from "./components/StudioHeader";
import { TVPoint } from "./components/TVAreaChart";

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
  deployed: "bg-emerald-500/15 text-[var(--kt-accent)] border-emerald-500/30",
  backtested: "bg-[var(--kt-accent-bg)] text-[var(--kt-accent-soft)] border-[var(--kt-accent-border)]",
  draft: "bg-zinc-500/15 text-[var(--kt-text-dim)] border-zinc-500/30",
  paused: "bg-amber-500/15 text-[var(--kt-warn)] border-amber-500/30",
};

/* ---------- small presentational pieces ---------- */
function Stat({ label, value, sub, accent, rawValue }: { label: string; value: string; sub?: string; accent?: string; rawValue?: number }) {
  return (
    <div className={`${KT.panel} flex flex-col gap-1 p-3`}>
      <span className={KT.label}>{label}</span>
      <span className={`tabular-nums text-lg leading-tight font-medium font-mono ${accent || "text-[var(--kt-text)]"}`}>{value}</span>
      {sub && <span className="text-[11px] text-[var(--kt-text-muted)]">{sub}</span>}
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
  const [rebalanceOpen, setRebalanceOpen] = useState(false);
  const [simOpen, setSimOpen] = useState(false);
  const [events, setEvents] = useState<any[]>([]);
  const [backtestTarget, setBacktestTarget] = useState<StrategyView | null>(null);
  const [detailTarget, setDetailTarget] = useState<StrategyView | null>(null);
  const [allocTarget, setAllocTarget] = useState<StrategyView | null>(null);
  const [manageTarget, setManageTarget] = useState<StrategyView | null>(null);

  // Chart panel state — NAV movement is the default; price is opt-in.
  const [chartMode, setChartMode] = useState<"nav" | "price">("nav");
  const [navHistory, setNavHistory] = useState<TVPoint[]>([]);
  const [chartSymbol, setChartSymbol] = useState("SPY");
  const [chartInput, setChartInput] = useState("SPY");
  const [chartData, setChartData] = useState<TVPoint[]>([]);
  const [chartMeta, setChartMeta] = useState<{ source?: string; range?: string } | null>(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartErr, setChartErr] = useState<string | null>(null);

  // Order blotter (trade history), filterable by strategy (parent rolls up children).
  const [orderHistory, setOrderHistory] = useState<OrderHistoryRow[]>([]);
  const [blotterFilter, setBlotterFilter] = useState<string | null>(null);

  const { toast } = useToast();
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async (soft = false) => {
    try {
      if (!soft) setErr(null);
      const [s, n, l, p, nh, oh, ev] = await Promise.all([
        fundApiClient.getStrategies(),
        fundApiClient.getNav(),
        fundApiClient.getLps(),
        fundApiClient.getPending(),
        fundApiClient.getNavHistory(90),
        fundApiClient.getOrderHistory(blotterFilter, 200),
        fundApiClient.getEvents(100).catch(() => ({ events: [] })),
      ]);
      setStrat(s);
      setNav(n);
      setLps(l.lps || []);
      setPending(p.pending || []);
      setNavHistory((nh.history || []).map((h) => ({ t: h.ts || "", v: h.total_nav_usd })));
      setOrderHistory(oh.orders || []);
      setEvents(ev.events || []);
      setLastSync(new Date());
      setTick((v) => v + 1);
      setErr(null);
    } catch (e: unknown) {
      const msg = (e as { message?: string })?.message || "Could not reach the fund spine.";
      if (!soft) setErr(msg);
    } finally {
      setLoading(false);
    }
  }, [blotterFilter]);

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
    timer.current = setInterval(() => load(true), 6000);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [load]);

  const strategies = (strat?.strategies || []).filter((s) => !s.archived);
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

  const liveStrategies = useMemo(() => {
    return orderedStrategies.filter((s) => s.state === "deployed");
  }, [orderedStrategies]);

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
    <div className="min-h-screen bg-[var(--kt-bg)] text-[var(--kt-text)]">
      {/* top bar */}
      <StudioHeader
        status={
          <>
            <StatusPulse
              state={err ? "offline" : lastSync ? "live" : "syncing"}
              label={err ? "spine unreachable" : "live"}
            />
            {lastSync && !err && <span>· synced {lastSync.toLocaleTimeString()}</span>}
          </>
        }
        actions={
          <>
            <button className={`flex h-8 items-center ${KT.btnGhost}`} onClick={() => load()}>
              <RefreshCw size={14} className="mr-1.5" /> Refresh
            </button>
          </>
        }
      />

      <div className="mx-auto max-w-[1400px] px-4 py-4">
        {err && (
          <div className="mb-4 rounded-lg border border-red-800/50 bg-red-950/30 p-3 text-sm text-[var(--kt-down)]">
            {err} — is ClarkHarness running on :8090 and <code>NEXT_PUBLIC_HARNESS_API_URL</code> set?
          </div>
        )}

        {/* KPI strip with exact un-compacted NAV calculation */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Stat
            label="Fund NAV"
            value={money(live?.total_nav_usd)}
            rawValue={live?.total_nav_usd}
            sub={`${money(live?.nav_per_unit, 4)}/unit · (${money(live?.breakdown?.positions)} pos + ${money(live?.breakdown?.cash)} cash)`}
            accent="text-[var(--kt-accent)] glow-emerald"
          />
          <Stat label="Idle Cash" value={money(live?.breakdown?.cash)} rawValue={live?.breakdown?.cash} sub={`${pct(live && live.total_nav_usd ? (live.breakdown.cash / live.total_nav_usd) * 100 : 0)} of NAV`} />
          <Stat label="Deployed Exp." value={money(totalExposure)} rawValue={totalExposure} sub={`${deployedCount} live ${deployedCount === 1 ? "strategy" : "strategies"}`} />
          <Stat label="Unrealized P&L" value={signed(totalPnl)} rawValue={Math.abs(totalPnl)} sub={totalPnl >= 0 ? "Profit" : "Loss"} accent={totalPnl >= 0 ? "text-[var(--kt-accent)]" : "text-[var(--kt-down)]"} />
          <Stat label="LPs" value={String(lps.length)} rawValue={lps.length} sub={`${(live?.units_outstanding || 0).toLocaleString()} units`} />
          <Stat label="Pending" value={String(pending.length)} rawValue={pending.length} sub="awaiting approval" accent={pending.length ? "text-[var(--kt-warn)]" : "text-[var(--kt-text)]"} />
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
          {/* left: strategies + chart */}
          <div className="lg:col-span-2 space-y-4">
            {/* chart panel — fund NAV movement by default, symbol price opt-in */}
            <div className={`${KT.panel} p-4`}>
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <Activity size={14} className="text-[var(--kt-accent)]" />
                {/* NAV | Price toggle */}
                <div className="flex overflow-hidden rounded-md border border-[var(--kt-border)]">
                  <button
                    onClick={() => setChartMode("nav")}
                    className={`px-2 py-1 text-xs ${chartMode === "nav" ? "bg-[var(--kt-accent-bg)] text-[var(--kt-text-strong)]" : "bg-transparent text-[var(--kt-text-dim)] hover:bg-[var(--kt-inset)]"}`}
                  >
                    Fund NAV
                  </button>
                  <button
                    onClick={() => {
                      setChartMode("price");
                      if (!chartData.length) loadChart(chartSymbol);
                    }}
                    className={`px-2 py-1 text-xs ${chartMode === "price" ? "bg-[var(--kt-accent-bg)] text-[var(--kt-text-strong)]" : "bg-transparent text-[var(--kt-text-dim)] hover:bg-[var(--kt-inset)]"}`}
                  >
                    Price
                  </button>
                </div>
                {chartMode === "nav" ? (
                  <span className="text-[11px] text-[var(--kt-text-muted)]">
                    total NAV · {navHistory.length} strike{navHistory.length === 1 ? "" : "s"}
                  </span>
                ) : (
                  <>
                    <span className="text-sm font-semibold">{chartSymbol}</span>
                    <span className="text-[11px] text-[var(--kt-text-muted)]">
                      daily · {chartMeta?.source || "—"} {chartMeta?.range ? `· ${chartMeta.range}` : ""}
                    </span>
                    <form
                      className="ml-auto flex items-center gap-1"
                      onSubmit={(e) => {
                        e.preventDefault();
                        if (chartInput.trim()) loadChart(chartInput.trim().toUpperCase());
                      }}
                    >
                      <div className="flex items-center rounded-md border border-[var(--kt-border)] bg-[var(--kt-inset)] px-2">
                        <Search size={12} className="text-[var(--kt-text-muted)]" />
                        <input
                          value={chartInput}
                          onChange={(e) => setChartInput(e.target.value)}
                          placeholder="symbol"
                          className="w-20 bg-transparent px-1.5 py-1 text-xs uppercase outline-none placeholder:text-[var(--kt-text-muted)]"
                        />
                      </div>
                      <Button type="submit" variant="outline" className="h-7 border-[var(--kt-border)] bg-transparent px-2 text-xs text-[var(--kt-text)]">
                        Load
                      </Button>
                    </form>
                  </>
                )}
              </div>

              {chartMode === "nav" ? (
                navHistory.length === 0 ? (
                  <div className="flex h-[320px] items-center justify-center text-xs text-[var(--kt-text-muted)]">
                    No NAV history struck yet. Strike a NAV to see history.
                  </div>
                ) : (
                  <HeroChart
                    data={navHistory.map((h) => ({ t: h.t, v: h.v }))}
                    height={320}
                  />
                )
              ) : chartErr ? (
                <div className="flex h-[320px] items-center justify-center text-xs text-[var(--kt-down)]">{chartErr}</div>
              ) : chartLoading && !chartData.length ? (
                <div className="flex h-[320px] items-center justify-center text-[var(--kt-text-muted)]">
                  <Loader2 className="animate-spin text-[var(--kt-accent)]" size={18} />
                </div>
              ) : (
                <HeroChart data={chartData} height={320} />
              )}
            </div>

            {/* High Level Analytics */}
            <div className="grid gap-4 md:grid-cols-2">
              <div className={`${KT.panel} p-5 space-y-3`}>
                <h3 className={KT.title}>Asset Allocation</h3>
                <AllocationDonut positions={positions} cash={live?.breakdown.cash || 0} totalNav={live?.total_nav_usd || 0} />
              </div>
              <div className={`${KT.panel} p-5 space-y-3`}>
                <h3 className={KT.title}>Strategy Performance</h3>
                <StrategyPerformanceBar strategies={liveStrategies} />
              </div>
            </div>

            <div className="mt-8 mb-4">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-[var(--kt-text)]">Live Strategies</h2>
                <span className="text-[11px] text-[var(--kt-text-muted)]">{liveStrategies.length} active · target vs actual allocation</span>
              </div>
              {loading ? (
                <div className="flex items-center gap-2 p-6 text-sm text-[var(--kt-text-muted)]">
                  <Loader2 className="animate-spin" size={16} /> Loading…
                </div>
              ) : liveStrategies.length === 0 ? (
                <div className={`${KT.panel} p-8 text-center text-sm text-[var(--kt-text-muted)]`}>
                  No live deployed strategies currently active. Draft and backtested strategies are managed in the Strategies tab.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {liveStrategies.map((s) => (
                    <StrategyCard
                      key={s.strategy_id}
                      strategy={s}
                      onClick={() => setDetailTarget(s)}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* positions */}
            <div className={`${KT.panel} p-5 space-y-3`}>
              <h3 className={KT.title}>Positions</h3>
              {positions.length === 0 ? (
                <div className="py-6 text-center text-sm text-[var(--kt-text-muted)]">Flat — no open positions.</div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-[10px] uppercase tracking-wide text-[var(--kt-text-muted)]">
                      <th className="px-4 py-1.5 text-left font-medium">Symbol</th>
                      <th className="px-4 py-1.5 text-right font-medium">Qty</th>
                      <th className="px-4 py-1.5 text-right font-medium">Mark</th>
                      <th className="px-4 py-1.5 text-right font-medium">Value</th>
                      <th className="px-4 py-1.5 text-right font-medium">% NAV</th>
                    </tr>
                  </thead>
                  <tbody className="font-mono">
                    {positions.map((p) => (
                      <tr key={p.symbol} className="border-t border-[var(--kt-border)]">
                        <td className="px-4 py-1.5 font-sans font-medium">{p.symbol}</td>
                        <td className="px-4 py-1.5 text-right text-[var(--kt-text-dim)]">{p.qty}</td>
                        <td className="px-4 py-1.5 text-right text-[var(--kt-text-dim)]">{money(p.mark)}</td>
                        <td className="px-4 py-1.5 text-right text-[var(--kt-text)]">{money(p.usd_value)}</td>
                        <td className="px-4 py-1.5 text-right text-[var(--kt-text-muted)]">
                          {pct(live && live.total_nav_usd ? (p.usd_value / live.total_nav_usd) * 100 : 0)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* order history (trade blotter), filterable by strategy */}
            <OrderBlotter
              orders={orderHistory}
              strategies={strategies}
              filter={blotterFilter}
              onFilter={setBlotterFilter}
            />
          </div>

          <div className="space-y-4">
            {/* pending approvals */}
            <div className={`${KT.panel} p-5 space-y-3`}>
              <div className="flex items-center justify-between">
                <h3 className={KT.title}>Pending approvals</h3>
                {pending.length > 0 && (
                  <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-[var(--kt-warn)]">
                    {pending.length}
                  </span>
                )}
              </div>

              {pending.length === 0 ? (
                <div className="py-6 text-center text-sm text-[var(--kt-text-muted)]">Queue clear.</div>
              ) : (
                <div className="divide-y divide-zinc-800/70">
                  {pending.map((o) => {
                    const ip = o.impact_preview || {};
                    const ctx = o.thesis_id ? thesisCtx[o.thesis_id] : undefined;
                    return (
                      <div key={o.order_id} className="py-3">
                        <div className="flex items-center gap-2">
                          <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${o.side === "buy" ? "bg-emerald-500/15 text-[var(--kt-accent)]" : "bg-red-500/15 text-[var(--kt-down)]"}`}>
                            {o.side}
                          </span>
                          <span className="font-mono text-sm">{o.qty} {o.symbol}</span>
                          <span className="ml-auto font-mono text-xs text-[var(--kt-text-dim)]">{money(ip.notional_usd)}</span>
                        </div>
                        <div className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-0.5 font-mono text-[10px] text-[var(--kt-text-muted)]">
                          <span>px {money(ip.quote_price)}</span>
                          <span>cash → {money(ip.cash_after)}</span>
                        </div>
                        {/* the case for the trade: thesis + Clark's memo */}
                        {ctx ? (
                          <div className="mt-2 rounded-md border border-[var(--kt-accent-border)] bg-[var(--kt-accent-bg)] p-2">
                            <div className="flex items-center gap-1.5">
                              <span className="rounded bg-[var(--kt-accent-bg)] px-1 py-0.5 text-[9px] font-semibold uppercase text-[var(--kt-accent)]">thesis</span>
                              <span className="min-w-0 truncate text-[11px] font-medium text-[var(--kt-text)]">{ctx.thesis.title}</span>
                            </div>
                            {ctx.thesis.claim && <p className="mt-1 text-[11px] text-[var(--kt-text)]">{ctx.thesis.claim}</p>}
                            {ctx.memo?.recommendation && (
                              <p className="mt-1 text-[11px] font-medium text-[var(--kt-text)]">▸ {ctx.memo.recommendation}</p>
                            )}
                          </div>
                        ) : o.thesis_id ? null : (
                          <div className="mt-2 text-[10px] italic text-[var(--kt-warn)]/70">discretionary — no thesis</div>
                        )}
                        <div className="mt-2 flex gap-2">
                          <Button
                            className="h-7 flex-1 bg-emerald-600 text-[var(--kt-text-strong)] hover:bg-emerald-700 font-bold text-xs"
                            disabled={busyOrder === o.order_id}
                            onClick={() => decide(o, true)}
                          >
                            {busyOrder === o.order_id ? <Loader2 size={13} className="animate-spin" /> : <><Check size={13} className="mr-1" /> Approve</>}
                          </Button>
                          <Button
                            variant="outline"
                            className="h-7 flex-1 border-[var(--kt-border)] bg-transparent text-[var(--kt-text-dim)] text-xs"
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
            <div className="rounded-xl border border-[var(--kt-border)] bg-[var(--kt-surface)]">
              <div className="flex items-center justify-between border-b border-[var(--kt-border)] px-4 py-2.5">
                <span className="text-sm font-semibold">LP book</span>
                <span className="text-[11px] text-[var(--kt-text-muted)]">{lps.length} investors</span>
              </div>
              {lps.length === 0 ? (
                <div className="p-6 text-center text-sm text-[var(--kt-text-muted)]">No LPs yet.</div>
              ) : (
                <div className="divide-y divide-zinc-800/70">
                  {lps.map((l) => {
                    const ownership = live && live.total_nav_usd ? (l.value_usd / live.total_nav_usd) * 100 : 0;
                    return (
                      <div key={l.lp_id} className="flex items-center gap-3 px-4 py-2">
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm">{l.name || l.lp_id}</div>
                          <div className="font-mono text-[10px] text-[var(--kt-text-muted)]">{l.units.toLocaleString()} units · {pct(ownership)}</div>
                        </div>
                        <div className="text-right font-mono text-sm text-[var(--kt-text)]">{money(l.value_usd)}</div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="flex items-center justify-center gap-1 text-[11px] text-[var(--kt-text-muted)]">
              <ArrowUpRight size={12} /> spine :8090 · free bars via Yahoo/Alpaca
            </div>
          </div>
        </div>
      </div>

      <CreateStrategyModal isOpen={createOpen} onClose={() => setCreateOpen(false)} onSuccess={() => load(true)} strategies={strategies} />
      <RebalanceModal
        open={rebalanceOpen}
        onOpenChange={setRebalanceOpen}
        strategies={strategies}
        totalNavUsd={live?.total_nav_usd || 100000}
        onSuccess={() => load(true)}
      />
      <SimulationModal
        open={simOpen}
        onOpenChange={setSimOpen}
        onSuccess={() => load(true)}
      />
      <BacktestModal
        strategy={backtestTarget}
        onClose={() => setBacktestTarget(null)}
        onSuccess={() => load(true)}
        onCharted={(symbol, points) => {
          setChartMode("price");
          setChartData(points);
          setChartSymbol(symbol);
          setChartMeta({ source: "backtest" });
        }}
      />
      <AllocationModal strategy={allocTarget} onClose={() => setAllocTarget(null)} onSuccess={() => load(true)} />
      <StrategyManageModal strategy={manageTarget} all={strategies} onClose={() => setManageTarget(null)} onSuccess={() => load(true)} />
      <StrategyDetailModal strategy={detailTarget} all={strategies} navUsd={strat?.nav_usd} onClose={() => setDetailTarget(null)} />
    </div>
  );
}
