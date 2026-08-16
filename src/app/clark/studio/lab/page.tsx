"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { FlaskConical, Loader2, Play, Trash2 } from "lucide-react";
import { StudioHeader } from "../components/StudioHeader";
import { LeanLab } from "../components/LeanLab";
import { Stat } from "../components/Stat";
import { KT } from "../theme";
import { CandidateVerdict } from "../components/CandidateVerdict";
import { spineError } from "@/lib/spine_error";
import { EquityChart } from "./EquityChart";
import {
  fundApiClient,
  ResearchBacktestResponse,
  StrategyTemplate,
} from "@/lib/fund_api";

/**
 * LAB — the strategy tester.
 *
 * Research, not fund state: nothing here is registered or persisted, and it
 * touches no event log, so the loop keeps working when the ledger does not.
 *
 * Two opinions are built into the layout. Buy & hold is always shown beside the
 * strategy, because a strategy that cannot beat owning the thing is not
 * interesting and that comparison should be impossible to skip. And every run is
 * kept, because the question in research is rarely "is this good" — it is "did
 * that change help", which needs the previous run still on screen.
 */

const TEMPLATES: { id: StrategyTemplate; label: string; params: string[] }[] = [
  { id: "sma", label: "SMA crossover", params: ["fast", "slow"] },
  { id: "rsi", label: "RSI mean-reversion", params: ["rsi_period", "rsi_low", "rsi_high"] },
  { id: "breakout", label: "Breakout", params: ["breakout_lookback"] },
  { id: "macd", label: "MACD", params: ["macd_fast", "macd_slow", "macd_signal"] },
  { id: "bollinger", label: "Bollinger", params: ["boll_period", "boll_k"] },
  { id: "momentum", label: "Momentum", params: ["momentum_lookback"] },
  { id: "atr_trail", label: "ATR trail", params: ["atr_period", "atr_mult"] },
  { id: "buy_hold", label: "Buy & hold", params: [] },
];

const DEFAULTS: Record<string, number> = {
  fast: 10, slow: 30,
  rsi_period: 14, rsi_low: 30, rsi_high: 70,
  breakout_lookback: 20,
  macd_fast: 12, macd_slow: 26, macd_signal: 9,
  boll_period: 20, boll_k: 2,
  momentum_lookback: 20,
  atr_period: 14, atr_mult: 3,
};

type Run = ResearchBacktestResponse & { id: number; ranAt: string };

const pct = (n?: number | null, dp = 2) => (n == null ? "—" : `${(n * 100).toFixed(dp)}%`);
const num = (n?: number | null, dp = 2) => (n == null ? "—" : n.toFixed(dp));

export default function LabPage() {
  const [symbol, setSymbol] = useState("INTC");
  const [template, setTemplate] = useState<StrategyTemplate>("sma");
  const [lookback, setLookback] = useState(365);
  const [params, setParams] = useState<Record<string, number>>({ ...DEFAULTS });
  const [runs, setRuns] = useState<Run[]>([]);
  const [active, setActive] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  // A ref, not state. `const id = seq; setSeq(s => s + 1)` reads the counter
  // from the render closure, so two runs fired before React re-renders both
  // read the same value and both get id 1 — which is exactly the duplicate-key
  // warning, and worse than a warning: React reuses the DOM node for the
  // second run, so the results list can show a row that belongs to a different
  // backtest. A double-click does it, and StrictMode's double-invoke does it
  // every time in dev. A ref increments synchronously and cannot go stale.
  const seqRef = useRef(0);

  const spec = TEMPLATES.find((t) => t.id === template)!;
  const current = runs.find((r) => r.id === active) ?? runs[0] ?? null;

  const run = useCallback(async () => {
    setBusy(true);
    setErr(null);
    try {
      const body: any = { symbol: symbol.trim().toUpperCase(), strategy: template, lookback_days: lookback };
      spec.params.forEach((p) => { body[p] = params[p]; });
      const res = await fundApiClient.researchBacktest(body);
      const id = ++seqRef.current;
      setRuns((r) => [{ ...res, id, ranAt: new Date().toLocaleTimeString() }, ...r].slice(0, 12));
      setActive(id);
    } catch (e: any) {
      setErr(spineError(e));
    } finally {
      setBusy(false);
    }
  }, [symbol, template, lookback, params, spec]);

  // one run on arrival so the page is never an empty shell
  useEffect(() => { run(); /* eslint-disable-next-line */ }, []);

  const r = current?.result;
  const b = current?.benchmark;
  const beatsBenchmark = r && b ? r.total_return > b.total_return : null;

  return (
    <div className={KT.page}>
      <StudioHeader subtitle="Backtest, compare and iterate — nothing here is registered or persisted" />

      <div className="mx-auto grid max-w-[1600px] grid-cols-1 gap-4 px-6 py-6 lg:grid-cols-[320px_1fr]">
        {/* ---------------- controls ---------------- */}
        <div className="space-y-4">
          <div className={KT.card}>
            <div className={KT.label}>Symbol</div>
            <input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && run()}
              className={`mt-1 w-full ${KT.input}`}
              placeholder="INTC"
            />

            <div className={`mt-4 ${KT.label}`}>Strategy</div>
            <select
              value={template}
              onChange={(e) => setTemplate(e.target.value as StrategyTemplate)}
              className={`mt-1 w-full ${KT.input}`}
            >
              {TEMPLATES.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
            </select>

            <div className={`mt-4 ${KT.label}`}>Lookback (days)</div>
            <input
              type="number" min={30} max={2000} value={lookback}
              onChange={(e) => setLookback(Number(e.target.value))}
              className={`mt-1 w-full ${KT.input}`}
            />

            {spec.params.length > 0 && (
              <>
                <div className={`mt-4 ${KT.label}`}>Parameters</div>
                <div className="mt-1 space-y-2">
                  {spec.params.map((p) => (
                    <div key={p} className="flex items-center gap-2">
                      <label className={`w-32 shrink-0 text-[11px] ${KT.muted}`}>{p.replace(/_/g, " ")}</label>
                      <input
                        type="number" value={params[p] ?? 0}
                        onChange={(e) => setParams((v) => ({ ...v, [p]: Number(e.target.value) }))}
                        className={`w-full ${KT.input} py-1`}
                      />
                    </div>
                  ))}
                </div>
              </>
            )}

            <button onClick={run} disabled={busy} className={`mt-4 flex w-full items-center justify-center gap-2 ${KT.btn}`}>
              {busy ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
              Run backtest
            </button>

            {err && <div className={`mt-3 p-2 text-[11px] ${KT.inset} ${KT.down}`}>{err}</div>}
          </div>

          {/* run history — research is comparison, not a single verdict */}
          <div className={KT.panel}>
            <div className="flex items-center justify-between border-b border-[var(--kt-border)] px-4 py-2.5">
              <span className={KT.label}>Runs</span>
              {runs.length > 0 && (
                <button onClick={() => { setRuns([]); setActive(null); }} className={`${KT.muted} hover:text-[var(--kt-down)]`}>
                  <Trash2 size={13} />
                </button>
              )}
            </div>
            {runs.length === 0 ? (
              <div className={`px-4 py-6 text-[11px] ${KT.muted}`}>No runs yet.</div>
            ) : (
              <ul className="max-h-[360px] divide-y divide-[var(--kt-border)] overflow-y-auto">
                {runs.map((x) => {
                  const won = x.result.total_return > x.benchmark.total_return;
                  return (
                    <li key={x.id}>
                      <button
                        onClick={() => setActive(x.id)}
                        className={`flex w-full items-baseline gap-2 px-4 py-2 text-left text-[11px] ${
                          x.id === current?.id ? "bg-[var(--kt-inset)]" : ""
                        }`}
                      >
                        <span className="font-semibold">{x.symbol}</span>
                        <span className={KT.muted}>{x.strategy}</span>
                        <span className={`ml-auto font-mono ${x.result.total_return >= 0 ? KT.up : KT.down}`}>
                          {pct(x.result.total_return, 1)}
                        </span>
                        <span className={won ? KT.up : KT.muted} title={won ? "beat buy & hold" : "trailed buy & hold"}>
                          {won ? "▲" : "▼"}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>

        {/* ---------------- results ---------------- */}
        <div className="space-y-4">
          {!current ? (
            <div className={`${KT.card} flex items-center gap-2 py-16 text-sm ${KT.muted}`}>
              <FlaskConical size={16} /> Run a backtest to see results.
            </div>
          ) : (
            <>
              {/* the comparison that decides whether this is worth anything */}
              <div className={KT.card}>
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <div>
                    <div className={KT.label}>
                      {current.symbol} · {current.strategy} · {current.bars.dates?.length ?? 0} bars · {current.source}
                    </div>
                    <div className={`mt-1 ${KT.hero} ${(r?.total_return ?? 0) >= 0 ? KT.up : KT.down}`}>
                      {pct(r?.total_return)}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={KT.label}>Buy &amp; hold</div>
                    <div className={`mt-1 ${KT.numberLg} ${KT.muted}`}>{pct(b?.total_return)}</div>
                  </div>
                </div>

                <div className={`mt-2 text-[12px] ${beatsBenchmark ? KT.up : KT.down}`}>
                  {beatsBenchmark
                    ? `Beats buy & hold by ${pct((r!.total_return) - (b!.total_return))}.`
                    : `Trails buy & hold by ${pct((b!.total_return) - (r!.total_return))} — simply owning ${current.symbol} did better.`}
                </div>

                <div className="mt-4">
                  <EquityChart
                    equity={r?.equity_curve ?? []}
                    benchmark={b?.equity_curve}
                    dates={current.bars.dates}
                  />
                  <div className={`mt-1 flex gap-4 text-[10px] ${KT.muted}`}>
                    <span><span className={KT.accent}>———</span> strategy</span>
                    <span>- - - buy &amp; hold</span>
                    <span className={KT.down}>▨ drawdown</span>
                  </div>
                </div>
              </div>

              {/* statistics */}
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <Stat label="Sharpe" value={num(r?.sharpe)} sub={`buy & hold ${num(b?.sharpe)}`}
                      tone={(r?.sharpe ?? 0) > (b?.sharpe ?? 0) ? KT.up : undefined} />
                <Stat label="Max drawdown" value={pct(r?.max_drawdown)} sub={`buy & hold ${pct(b?.max_drawdown)}`} tone={KT.down} />
                <Stat label="Win rate" value={pct(r?.win_rate, 1)} sub={`${r?.trades.length ?? 0} closed trades`} />
                <Stat label="Profit factor" value={r?.profit_factor ? num(r.profit_factor) : "—"}
                      sub={r?.profit_factor ? "gross win / gross loss" : "no losing trades"} />
                <Stat label="Exposure" value={`${num(r?.exposure_pct, 1)}%`} sub="of bars in market" />
                <Stat label="Volatility" value={pct(r?.volatility, 1)} sub="annualised" />
                <Stat label="Avg win" value={`${num(r?.avg_win)}%`} tone={KT.up} />
                <Stat label="Avg loss" value={`${num(r?.avg_loss)}%`} tone={KT.down} />
              </div>

              <CandidateVerdict
                equityCurve={r?.equity_curve}
                dates={current.bars.dates ?? undefined}
                symbol={current.symbol}
                template={template}
                params={Object.fromEntries(spec.params.map((p) => [p, params[p]]))}
              />

              {/* what it actually did */}
              <div className={KT.panel}>
                <div className={`border-b border-[var(--kt-border)] px-5 py-3 ${KT.label}`}>
                  Trades ({r?.trades.length ?? 0})
                </div>
                {!r?.trades.length ? (
                  <div className={`px-5 py-8 text-sm ${KT.muted}`}>
                    No trades — the signal never entered a position over this window.
                  </div>
                ) : (
                  <div className="max-h-[320px] overflow-auto">
                    <table className="w-full text-sm">
                      <thead className="sticky top-0 bg-[var(--kt-surface)]">
                        <tr className={`border-b border-[var(--kt-border)] ${KT.label}`}>
                          <th className="px-5 py-2 text-left font-normal">#</th>
                          <th className="px-5 py-2 text-left font-normal">Side</th>
                          <th className="px-5 py-2 text-left font-normal">Entry</th>
                          <th className="px-5 py-2 text-right font-normal">In</th>
                          <th className="px-5 py-2 text-right font-normal">Out</th>
                          <th className="px-5 py-2 text-right font-normal">Bars</th>
                          <th className="px-5 py-2 text-right font-normal">P&amp;L</th>
                        </tr>
                      </thead>
                      <tbody>
                        {r.trades.map((t, i) => (
                          <tr key={i} className="border-b border-[var(--kt-border)] last:border-0">
                            <td className={`px-5 py-2 ${KT.muted}`}>{i + 1}</td>
                            <td className="px-5 py-2 uppercase">{t.side}</td>
                            <td className={`px-5 py-2 ${KT.muted}`}>
                              {current.bars.dates?.[t.entry_index] ?? `bar ${t.entry_index}`}
                            </td>
                            <td className={`px-5 py-2 text-right ${KT.number}`}>{t.entry_price}</td>
                            <td className={`px-5 py-2 text-right ${KT.number}`}>{t.exit_price}</td>
                            <td className={`px-5 py-2 text-right ${KT.number}`}>{t.bars_held}</td>
                            <td className={`px-5 py-2 text-right font-mono tabular-nums ${t.pnl_pct >= 0 ? KT.up : KT.down}`}>
                              {t.pnl_pct >= 0 ? "+" : ""}{t.pnl_pct.toFixed(2)}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* The in-process backtester above is the fast loop; the engine of record
          is its own desk — one lab, page level, below the research grid. */}
      <div className="mx-auto max-w-[1600px] px-6 pb-10">
        <LeanLab />
      </div>
    </div>
  );
}

