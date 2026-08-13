"use client";

import React, { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Radio } from "lucide-react";
import { fundApiClient, RiskMonitorPosition } from "@/lib/fund_api";
import { KT } from "../theme";

/**
 * Portfolio ticker strip — the fund's own holdings, not a market index reel.
 *
 * A Yahoo-style band is only useful here if it shows what we actually own, so
 * every tile is a live position: mark, weight, and unrealized P&L.
 *
 * Deliberately NOT a daily change %: the spine stores marks and cost basis, not
 * a previous close, so a "day change" would have to be invented. Unrealized P&L
 * against cost basis is the real number we have, and it is labelled as such.
 */
export function PositionTicker({ pollMs = 60000 }: { pollMs?: number }) {
  const [positions, setPositions] = useState<RiskMonitorPosition[] | null>(null);
  const [err, setErr] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const m = await fundApiClient.getRiskMonitor();
        if (alive) { setPositions(m.positions ?? []); setErr(false); }
      } catch {
        if (alive) setErr(true);
      }
    };
    load();
    const t = setInterval(load, pollMs);
    return () => { alive = false; clearInterval(t); };
  }, [pollMs]);

  const nudge = (dir: -1 | 1) =>
    scroller.current?.scrollBy({ left: dir * 320, behavior: "smooth" });

  if (err) {
    return (
      <Strip>
        <span className={`px-4 text-[11px] ${KT.muted}`}>Prices unavailable — fund service unreachable</span>
      </Strip>
    );
  }
  if (!positions) {
    return <Strip><span className={`px-4 text-[11px] ${KT.muted}`}>Loading positions…</span></Strip>;
  }
  if (positions.length === 0) {
    return <Strip><span className={`px-4 text-[11px] ${KT.muted}`}>No open positions</span></Strip>;
  }

  return (
    <Strip>
      <div className="flex shrink-0 items-center gap-1.5 pl-4 pr-3">
        <Radio size={13} className={KT.accent} />
        <span className={KT.label}>Portfolio</span>
      </div>

      <div ref={scroller} className="flex flex-1 gap-6 overflow-x-auto scroll-smooth px-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {positions.map((p) => {
          const pnl = p.unrealized_pnl_pct;
          const up = (pnl ?? 0) >= 0;
          return (
            <div key={p.symbol} className="flex shrink-0 flex-col justify-center py-1.5">
              <div className="flex items-baseline gap-2">
                <span className="text-[11px] font-semibold tracking-wide">{p.symbol}</span>
                <span className={`text-[10px] ${KT.muted}`}>{p.weight_pct?.toFixed(1)}%</span>
              </div>
              <div className="flex items-baseline gap-2">
                <span className={`font-mono tabular-nums text-[13px] ${KT.number}`}>
                  {p.mark?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
                {pnl != null && (
                  <span className={`font-mono tabular-nums text-[11px] ${up ? KT.up : KT.down}`}>
                    {up ? "+" : ""}{pnl.toFixed(2)}%
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex shrink-0 items-center gap-0.5 pr-3">
        <button onClick={() => nudge(-1)} aria-label="Scroll positions left"
                className={`rounded p-1 ${KT.muted} hover:bg-[var(--kt-inset)]`}>
          <ChevronLeft size={14} />
        </button>
        <button onClick={() => nudge(1)} aria-label="Scroll positions right"
                className={`rounded p-1 ${KT.muted} hover:bg-[var(--kt-inset)]`}>
          <ChevronRight size={14} />
        </button>
      </div>
    </Strip>
  );
}

function Strip({ children }: { children: React.ReactNode }) {
  return (
    <div className="border-b border-[var(--kt-border)] bg-[var(--kt-surface)]">
      <div className="mx-auto flex max-w-[1600px] items-stretch">{children}</div>
    </div>
  );
}
