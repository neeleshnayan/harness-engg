"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Check, Loader2, X } from "lucide-react";
import { fundApiClient, MemoView, PendingOrder, ThesisView } from "@/lib/fund_api";

const money = (n?: number | null) =>
  n == null ? "—" : `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

type Ctx = Record<string, { thesis: ThesisView; memo?: MemoView }>;

/** Self-contained approval desk: pending orders + the thesis/memo case, human-gated. */
export function ApprovalsPanel({ onChanged }: { onChanged?: () => void }) {
  const [pending, setPending] = useState<PendingOrder[]>([]);
  const [ctx, setCtx] = useState<Ctx>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const p = await fundApiClient.getPending();
      setPending(p.pending || []);
    } catch {
      /* leave prior */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    timer.current = setInterval(load, 6000);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [load]);

  useEffect(() => {
    const ids = Array.from(new Set(pending.map((o) => o.thesis_id).filter(Boolean))) as string[];
    if (!ids.length) {
      setCtx({});
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
      if (!cancelled) setCtx(Object.fromEntries(entries.filter(Boolean) as [string, { thesis: ThesisView; memo?: MemoView }][]));
    })();
    return () => { cancelled = true; };
  }, [pending]);

  const decide = async (o: PendingOrder, approve: boolean) => {
    setBusy(o.order_id);
    try {
      if (approve) {
        await fundApiClient.approveOrder(o.order_id, "rushi");
        await fundApiClient.settle();
      } else {
        await fundApiClient.declineOrder(o.order_id, "rushi");
      }
      await load();
      onChanged?.();
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40">
      <div className="flex items-center gap-2 border-b border-zinc-800 px-4 py-2.5">
        <span className="text-sm font-semibold">Pending approvals</span>
        {pending.length > 0 && (
          <span className="rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-amber-300">{pending.length}</span>
        )}
      </div>
      {loading && !pending.length ? (
        <div className="flex items-center gap-2 p-6 text-sm text-zinc-500"><Loader2 className="animate-spin" size={16} /> Loading…</div>
      ) : pending.length === 0 ? (
        <div className="p-6 text-center text-sm text-zinc-500">Queue clear.</div>
      ) : (
        <div className="divide-y divide-zinc-800/70">
          {pending.map((o) => {
            const ip = o.impact_preview || {};
            const c = o.thesis_id ? ctx[o.thesis_id] : undefined;
            return (
              <div key={o.order_id} className="p-3">
                <div className="flex items-center gap-2">
                  <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${o.side === "buy" ? "bg-emerald-500/15 text-emerald-300" : "bg-red-500/15 text-red-300"}`}>{o.side}</span>
                  <span className="font-mono text-sm">{o.qty} {o.symbol}</span>
                  <span className="ml-auto font-mono text-xs text-zinc-400">{money(ip.notional_usd)}</span>
                </div>
                <div className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-0.5 font-mono text-[10px] text-zinc-500">
                  <span>px {money(ip.quote_price)}</span>
                  <span>cash → {money(ip.cash_after)}</span>
                </div>
                {c ? (
                  <div className="mt-2 rounded-md border border-teal-800/40 bg-teal-950/20 p-2">
                    <div className="flex items-center gap-1.5">
                      <span className="rounded bg-teal-500/20 px-1 py-0.5 text-[9px] font-semibold uppercase text-teal-300">thesis</span>
                      <span className="min-w-0 truncate text-[11px] font-medium text-teal-200">{c.thesis.title}</span>
                    </div>
                    {c.thesis.claim && <p className="mt-1 text-[11px] text-zinc-400">{c.thesis.claim}</p>}
                    {c.memo?.recommendation && <p className="mt-1 text-[11px] text-teal-300">▸ {c.memo.recommendation}</p>}
                  </div>
                ) : o.thesis_id ? null : (
                  <div className="mt-2 text-[10px] italic text-amber-500/70">discretionary — no thesis</div>
                )}
                <div className="mt-2 flex gap-2">
                  <button
                    className="flex h-7 flex-1 items-center justify-center gap-1 rounded bg-emerald-600 text-sm text-white hover:bg-emerald-700 disabled:opacity-50"
                    disabled={busy === o.order_id}
                    onClick={() => decide(o, true)}
                  >
                    {busy === o.order_id ? <Loader2 size={13} className="animate-spin" /> : <><Check size={13} /> Approve</>}
                  </button>
                  <button
                    className="flex h-7 flex-1 items-center justify-center gap-1 rounded border border-zinc-700 text-sm text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
                    disabled={busy === o.order_id}
                    onClick={() => decide(o, false)}
                  >
                    <X size={13} /> Decline
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
