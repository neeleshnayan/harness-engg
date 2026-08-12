"use client";

import React from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { StrategyView } from "@/lib/fund_api";

interface Props {
  strategy: StrategyView | null;
  all: StrategyView[];
  navUsd?: number;
  onClose: () => void;
}

const money = (n?: number | null, dp = 2) =>
  n == null ? "—" : `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp })}`;
const pct = (n?: number | null, dp = 1) => (n == null ? "—" : `${Number(n).toFixed(dp)}%`);

function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-lg border border-[var(--kt-border)] bg-[var(--kt-bg)] px-3 py-2">
      <div className="text-[10px] uppercase tracking-widest text-[var(--kt-text-muted)]">{label}</div>
      <div className={`font-mono text-base ${accent || "text-[var(--kt-text)]"}`}>{value}</div>
    </div>
  );
}

export function StrategyDetailModal({ strategy: s, all, navUsd, onClose }: Props) {
  if (!s) return null;

  const isContainer = !!s.is_container;
  const exposure = isContainer ? s.rolled_exposure_usd ?? s.exposure_usd : s.exposure_usd;
  const pnl = isContainer ? s.rolled_pnl_usd ?? s.pnl_usd : s.pnl_usd;
  const actual = isContainer ? s.rolled_actual_pct : s.actual_pct;
  const bt = s.backtest;
  const positions = Object.entries(s.positions || {});
  const children = (s.children || [])
    .map((id) => all.find((x) => x.strategy_id === id))
    .filter(Boolean) as StrategyView[];
  const parent = s.parent_id ? all.find((x) => x.strategy_id === s.parent_id) : null;

  return (
    <Dialog open={!!s} onOpenChange={onClose}>
      <DialogContent className="w-[calc(100%-2rem)] max-w-[620px] max-h-[92vh] overflow-y-auto border-[var(--kt-border)] bg-[var(--kt-surface)] text-[var(--kt-text-strong)]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {s.name}
            <span className="rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase text-[var(--kt-text-dim)] border border-[var(--kt-border)]">{s.state}</span>
            {isContainer && <span className="rounded bg-[var(--kt-accent-bg)] px-1.5 py-0.5 text-[10px] font-semibold uppercase text-[var(--kt-accent-soft)]">container</span>}
          </DialogTitle>
        </DialogHeader>

        <div className="grid gap-4 py-2">
          {parent && (
            <div className="text-xs text-[var(--kt-text-muted)]">nested under <span className="text-[var(--kt-text-dim)]">{parent.name}</span></div>
          )}

          {/* live performance */}
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label={isContainer ? "Exposure (rolled)" : "Exposure"} value={money(exposure)} />
            <Stat label="Unrealized P&L" value={pnl == null ? "—" : `${pnl >= 0 ? "+" : ""}${money(pnl)}`} accent={(pnl ?? 0) >= 0 ? "text-[var(--kt-accent)]" : "text-[var(--kt-down)]"} />
            <Stat label="Target alloc" value={pct(s.allocation_pct)} />
            <Stat label="Actual alloc" value={pct(actual)} />
          </div>

          {/* backtest */}
          <div>
            <div className="mb-1 text-[11px] uppercase tracking-widest text-[var(--kt-text-muted)]">Latest backtest</div>
            {bt ? (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <Stat label="Return" value={`${(bt.total_return * 100).toFixed(2)}%`} accent={bt.total_return >= 0 ? "text-[var(--kt-accent)]" : "text-[var(--kt-down)]"} />
                <Stat label="Sharpe" value={bt.sharpe.toFixed(2)} />
                <Stat label="Max DD" value={`${(bt.max_drawdown * 100).toFixed(2)}%`} accent="text-[var(--kt-down)]" />
                <Stat label="Trades / bars" value={`${bt.n_trades} / ${bt.bars}`} />
              </div>
            ) : (
              <div className="rounded-lg border border-[var(--kt-border)] bg-[var(--kt-bg)] p-3 text-sm text-[var(--kt-text-muted)]">
                No backtest yet — run one from the Backtest button.
              </div>
            )}
          </div>

          {/* positions */}
          <div>
            <div className="mb-1 text-[11px] uppercase tracking-widest text-[var(--kt-text-muted)]">Positions</div>
            {positions.length === 0 ? (
              <div className="rounded-lg border border-[var(--kt-border)] bg-[var(--kt-bg)] p-3 text-sm text-[var(--kt-text-muted)]">Flat — no open positions.</div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[10px] uppercase tracking-wide text-[var(--kt-text-muted)]">
                    <th className="py-1 text-left font-medium">Symbol</th>
                    <th className="py-1 text-right font-medium">Qty</th>
                    <th className="py-1 text-right font-medium">Avg price</th>
                  </tr>
                </thead>
                <tbody className="font-mono">
                  {positions.map(([sym, pos]) => {
                    const pp = pos as { qty?: number; avg_price?: number };
                    return (
                      <tr key={sym} className="border-t border-[var(--kt-border)]">
                        <td className="py-1 font-sans">{sym}</td>
                        <td className="py-1 text-right text-[var(--kt-text-dim)]">{pp.qty}</td>
                        <td className="py-1 text-right text-[var(--kt-text-dim)]">{money(pp.avg_price)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>

          {/* children (container breakdown) */}
          {isContainer && children.length > 0 && (
            <div>
              <div className="mb-1 text-[11px] uppercase tracking-widest text-[var(--kt-text-muted)]">Sub-strategies ({children.length})</div>
              <div className="divide-y divide-zinc-800/70 rounded-lg border border-[var(--kt-border)]">
                {children.map((c) => {
                  const up = (c.pnl_usd ?? 0) >= 0;
                  return (
                    <div key={c.strategy_id} className="flex items-center gap-3 px-3 py-2">
                      <span className="flex-1 truncate text-sm">{c.name}</span>
                      <span className="text-[10px] uppercase text-[var(--kt-text-muted)]">{c.state}</span>
                      <span className="w-24 text-right font-mono text-xs text-[var(--kt-text-dim)]">{money(c.exposure_usd)}</span>
                      <span className={`w-16 text-right font-mono text-xs ${up ? "text-[var(--kt-accent)]" : "text-[var(--kt-down)]"}`}>
                        {c.pnl_usd == null ? "—" : `${up ? "+" : ""}${Number(c.pnl_usd).toFixed(0)}`}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
