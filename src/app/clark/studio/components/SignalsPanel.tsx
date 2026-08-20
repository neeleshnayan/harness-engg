"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowUp, Check, Loader2, RefreshCw } from "lucide-react";
import { spineError } from "@/lib/spine_error";
import { KT } from "../theme";
import { ProvenanceChip } from "./Provenance";
import { SignalRunResult, SignalSizedRow, fundApiClient } from "@/lib/fund_api";

/**
 * What every live strategy wants to do right now — and one click to act on it.
 *
 * This closes a gap that was invisible for a long time: the fund had strategies
 * with allocations and universes, but nothing ever evaluated them, so "what does
 * the book want to do" had no answer anywhere in the product.
 *
 * A row that names a trade and cannot start one is a to-do list, so each
 * actionable row carries the share count and price it would trade at, and a
 * Propose button. **Propose is not execute.** It creates a proposal that passes
 * the risk gate and then waits in the approval queue at the top of this page —
 * the same gate and the same human step as any other order.
 *
 * Skips are shown, not hidden. A strategy that cannot be evaluated — no bars, an
 * unwarmed indicator, no allocation — is the most important row here, because a
 * silent skip looks exactly like a decision to do nothing.
 */

const money = (n?: number | null) =>
  n == null ? "—" : `$${Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

const ACTION_TONE: Record<string, string> = {
  buy: KT.up,
  sell: KT.down,
  hold: KT.muted,
  skip: KT.sev.warn,
};

export function SignalsPanel({ onProposed, bookChanged = 0 }: {
  onProposed?: () => void;
  /** Bumped when the book moves under us (an order approved, a fill landed).
   *  These figures are then computed against a book that no longer exists, so
   *  the panel says so instead of quietly showing a stale "buy". It does NOT
   *  auto-refetch: evaluating pulls bars for every symbol. */
  bookChanged?: number;
}) {
  const [res, setRes] = useState<SignalRunResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAll, setShowAll] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [done, setDone] = useState<Record<string, string>>({});
  // Which book version these numbers were computed against.
  const [evaluatedAt, setEvaluatedAt] = useState(0);

  const bookRef = React.useRef(bookChanged);
  bookRef.current = bookChanged;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      // dry run: sizes every trade without writing anything.
      setRes(await fundApiClient.runSignals(true));
      setErr(null);
      setDone({});
      setEvaluatedAt(bookRef.current);
    } catch (e: unknown) {
      setErr(spineError(e));
      setRes(null);          // unknown, not empty
    } finally {
      setLoading(false);
    }
  }, []);

  // Evaluating fetches bars for every symbol, so this does NOT poll on a timer.
  // A panel that quietly hammers the data vendor every minute is how a free
  // feed starts rate-limiting the thing the fund actually needs it for.
  useEffect(() => { load(); }, [load]);

  const key = (r: { strategy_id: string; symbol: string }) => `${r.strategy_id}:${r.symbol}`;

  // Sized trades are the actionable ones; everything else is context.
  const { rows, holding } = useMemo(() => {
    if (!res) return { rows: [] as SignalSizedRow[], holding: [] as SignalSizedRow[] };
    const sized = new Map<string, SignalSizedRow>();
    for (const r of [...res.proposed, ...res.suppressed, ...res.rejected]) sized.set(key(r), r);
    const all: SignalSizedRow[] = res.evaluated.map((d) => ({ ...d, ...(sized.get(key(d)) ?? {}) }));
    return {
      rows: all.filter((d) => d.action !== "hold"),
      holding: all.filter((d) => d.action === "hold"),
    };
  }, [res]);

  const shown = showAll ? [...rows, ...holding] : rows;

  const propose = async (r: SignalSizedRow) => {
    if (!r.qty || (r.action !== "buy" && r.action !== "sell")) return;
    setBusy(key(r));
    try {
      const out = await fundApiClient.proposeOrder({
        symbol: r.symbol,
        side: r.action,
        qty: r.qty,
        strategy_id: r.strategy_id,
        // A systematic signal IS the case for the trade; it is not an
        // unexplained discretionary punt, but it has no written thesis either.
        discretionary: true,
      });
      setDone((d) => ({
        ...d,
        [key(r)]: out.status === "rejected"
          ? `rejected: ${(out.breaches || []).join("; ") || "risk gate"}`
          : "pending approval",
      }));
      onProposed?.();
    } catch (e: unknown) {
      setDone((d) => ({ ...d, [key(r)]: spineError(e) }));
    } finally {
      setBusy(null);
    }
  };

  const closed = res?.market_open === false;

  return (
    <div className={KT.panel}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--kt-border)] px-5 py-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className={KT.label}>What the strategies want</span>
            {/* Found live by the CEO: this panel suggests trades and gave no way
                to tell whether an agent was recommending them. It is arithmetic
                — a registered strategy's rule evaluated against live bars, with
                no model in the loop — and now says so. */}
            <ProvenanceChip kind="deterministic" source="strategy signal (no agent)" />
          </div>
          <div className={`mt-1 text-[11px] ${KT.muted}`}>
            Evaluated from live bars. Proposing sends it to the approval queue
            above — it does not reach the venue.
          </div>
        </div>
        <div className="flex items-center gap-3">
          {closed && <span className={`text-[11px] ${KT.sev.warn}`}>market closed</span>}
          {holding.length > 0 && (
            <button onClick={() => setShowAll((s) => !s)} className={`text-[11px] ${KT.accent} underline underline-offset-2`}>
              {showAll ? "hide" : "show"} {holding.length} holding
            </button>
          )}
          <button onClick={load} disabled={loading}
                  className={`flex h-7 items-center ${KT.btnGhost} text-[11px]`}>
            <RefreshCw size={12} className={`mr-1.5 ${loading ? "animate-spin" : ""}`} />
            {loading ? "Evaluating…" : "Re-evaluate"}
          </button>
        </div>
      </div>

      {bookChanged !== evaluatedAt && res && (
        <div className={`flex items-center gap-2 border-b border-[var(--kt-border)] px-5 py-2 text-[11px] ${KT.sev.warn}`}>
          <AlertTriangle size={12} />
          The book has changed since this was evaluated — these targets are stale.
          <button onClick={load} className={`ml-1 ${KT.accent} underline underline-offset-2`}>
            re-evaluate
          </button>
        </div>
      )}

      {err ? (
        <div className={`px-5 py-6 text-sm ${KT.down}`}>
          {err} — signals unknown, which is not the same as no signals.
        </div>
      ) : loading && res === null ? (
        <div className={`px-5 py-8 text-sm ${KT.muted}`}>Evaluating strategies against live bars…</div>
      ) : shown.length === 0 ? (
        <div className={`px-5 py-6 text-sm ${KT.muted}`}>
          {(res?.evaluated.length ?? 0) === 0
            ? "No live strategies to evaluate."
            : "Every strategy is already where it wants to be."}
        </div>
      ) : (
        <div className="overflow-x-auto px-2 pb-3">
          <table className="w-full text-left text-[12px]">
            <thead className={KT.muted}>
              <tr>
                <th className="px-3 py-2 font-normal">Strategy</th>
                <th className="px-3 py-2 font-normal">Symbol</th>
                <th className="px-3 py-2 font-normal">Wants</th>
                <th className="px-3 py-2 text-right font-normal">Target</th>
                <th className="px-3 py-2 text-right font-normal">Held</th>
                <th className="px-3 py-2 text-right font-normal">Trade</th>
                <th className="px-3 py-2 font-normal">Why / status</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {shown.map((d) => {
                const k = key(d);
                const blocked = d.status === "would_be_rejected";
                const actionable = (d.action === "buy" || d.action === "sell")
                  && !!d.qty && !blocked;
                const status = done[k];
                return (
                  <tr key={k} className="border-t border-[var(--kt-border)]">
                    <td className="px-3 py-1.5">{d.strategy_name}</td>
                    <td className="px-3 py-1.5 font-mono">{d.symbol}</td>
                    <td className={`px-3 py-1.5 font-medium uppercase ${ACTION_TONE[d.action] || ""}`}>
                      {d.action}
                    </td>
                    <td className="px-3 py-1.5 text-right font-mono tabular-nums">{money(d.target_usd)}</td>
                    <td className="px-3 py-1.5 text-right font-mono tabular-nums">{money(d.current_usd)}</td>
                    <td className="px-3 py-1.5 text-right font-mono tabular-nums">
                      {d.qty ? `${d.qty} @ ${money(d.price)}` : "—"}
                    </td>
                    <td className={`px-3 py-1.5 ${status || blocked ? "" : KT.muted}`}>
                      {blocked && !status ? (
                        <span className={KT.sev.warn} title={(d.breaches || []).join("; ")}>
                          the risk gate would refuse this — {(d.breaches || [])[0]}
                        </span>
                      ) : status ? (
                        status.startsWith("pending") ? (
                          <a href="#top" className={`inline-flex items-center gap-1 ${KT.up}`}>
                            <ArrowUp size={11} /> in the approval queue above
                          </a>
                        ) : (
                          <span className={KT.down}>{status}</span>
                        )
                      ) : d.reason}
                    </td>
                    <td className="px-3 py-1.5 text-right">
                      {actionable && !status && (
                        <button
                          disabled={busy === k}
                          onClick={() => propose(d)}
                          className={`flex items-center gap-1 ${KT.btnGhost} px-2 py-0.5 text-[11px]`}
                        >
                          {busy === k
                            ? <Loader2 size={11} className="animate-spin" />
                            : <Check size={11} />}
                          Propose
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className={`mt-2 px-3 text-[11px] ${KT.muted}`}>
            Proposing runs the venue check and the risk gate, then places the order
            in the approval queue. Nothing here can reach the venue on its own.
          </p>
        </div>
      )}
    </div>
  );
}
