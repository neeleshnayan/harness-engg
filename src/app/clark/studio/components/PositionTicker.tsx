"use client";

import React, { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { fundApiClient, MarketQuote } from "@/lib/fund_api";
import { KT } from "../theme";

/**
 * Ticker strip — the fund's own universe, not a market index reel.
 *
 * Shows what we hold plus what is scoped to a live strategy, so the strip stays
 * useful before the book holds anything (the previous version rendered only
 * open positions and so read "No open positions" exactly when you were watching
 * for an entry).
 *
 * The day change is a real one: live price against the previous session close
 * from daily bars. Where a symbol cannot be priced it renders a dash rather
 * than a flat zero, and a price with no live tick is marked stale rather than
 * passed off as live.
 */
export function PositionTicker({ pollMs = 120000 }: { pollMs?: number }) {
  const [quotes, setQuotes] = useState<MarketQuote[] | null>(null);
  const [err, setErr] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const r = await fundApiClient.getMarketQuotes();
        if (alive) { setQuotes(r.quotes ?? []); setErr(false); }
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

  if (err) return <Strip><Msg>Prices unavailable — fund service unreachable</Msg></Strip>;
  if (!quotes) return <Strip><Msg>Loading quotes…</Msg></Strip>;
  if (quotes.length === 0) return <Strip><Msg>No assets held or scoped to a strategy</Msg></Strip>;

  return (
    <Strip>
      <div
        ref={scroller}
        className="flex flex-1 gap-5 overflow-x-auto scroll-smooth px-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {quotes.map((q) => {
          const up = (q.change_pct ?? 0) >= 0;
          return (
            <div key={q.symbol} className="flex shrink-0 flex-col justify-center py-1.5">
              <div className="flex items-baseline gap-1.5">
                <span className="text-[11px] font-semibold tracking-wide">{q.symbol}</span>
                {q.held ? (
                  <span className={`text-[9px] ${KT.accent}`} title="held in the book">
                    ● {q.weight_pct != null ? `${q.weight_pct.toFixed(1)}%` : "held"}
                  </span>
                ) : (
                  <span className={`text-[9px] ${KT.muted}`} title="scoped to a strategy, not held">
                    watch
                  </span>
                )}
                {q.stale && (
                  <span className={`text-[9px] ${KT.muted}`} title="no live tick — last close">
                    stale
                  </span>
                )}
              </div>
              <div className="flex items-baseline gap-2">
                <span className={`font-mono tabular-nums text-[13px] ${KT.number}`}>
                  {q.price != null
                    ? q.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                    : "—"}
                </span>
                <span className={`font-mono tabular-nums text-[11px] ${
                  q.change_pct == null ? KT.muted : up ? KT.up : KT.down
                }`}>
                  {q.change_pct == null
                    ? "—"
                    : `${up ? "+" : ""}${q.change?.toFixed(2)} (${up ? "+" : ""}${q.change_pct.toFixed(2)}%)`}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex shrink-0 items-center gap-0.5 pr-3">
        <button onClick={() => nudge(-1)} aria-label="Scroll quotes left"
                className={`rounded p-1 ${KT.muted} hover:bg-[var(--kt-inset)]`}>
          <ChevronLeft size={14} />
        </button>
        <button onClick={() => nudge(1)} aria-label="Scroll quotes right"
                className={`rounded p-1 ${KT.muted} hover:bg-[var(--kt-inset)]`}>
          <ChevronRight size={14} />
        </button>
      </div>
    </Strip>
  );
}

const Msg = ({ children }: { children: React.ReactNode }) => (
  <span className={`px-4 py-2 text-[11px] ${KT.muted}`}>{children}</span>
);

function Strip({ children }: { children: React.ReactNode }) {
  return (
    <div className="border-b border-[var(--kt-border)] bg-[var(--kt-surface)]">
      <div className="mx-auto flex max-w-[1600px] items-stretch">{children}</div>
    </div>
  );
}
