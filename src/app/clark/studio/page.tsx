"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, Check, Loader2, RefreshCw, X } from "lucide-react";
import { StudioHeader } from "./components/StudioHeader";
import { KT } from "./theme";
import { spineError } from "@/lib/spine_error";
import {
  fundApiClient,
  MemoView,
  PendingOrder,
  ThesisView,
} from "@/lib/fund_api";

/**
 * DECIDE — what needs a human right now.
 *
 * Deliberately narrow. This was a 627-line dashboard importing 17 components,
 * which made the rarest activity (a decision) compete with every number in the
 * fund. Everything else moved to its proper surface: sizing to Allocate, live
 * state to Monitor, attribution to Review.
 *
 * The honesty rule this page exists to respect: when the spine cannot be read it
 * must NOT render "0 pending". An unknown queue is not an empty queue, and the
 * difference decides whether Rushi walks away from a trade that is waiting.
 */

const money = (n?: number | null, dp = 2) =>
  n == null ? "—" : `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp })}`;

export default function DecidePage() {
  const [pending, setPending] = useState<PendingOrder[] | null>(null);
  const [ctx, setCtx] = useState<Record<string, { thesis: ThesisView; memo?: MemoView }>>({});
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const p = await fundApiClient.getPending();
      setPending(p.pending || []);
      setErr(null);
    } catch (e: any) {
      setPending(null);            // unknown — never fall back to an empty list
      setErr(spineError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Enrich each order with the case behind it — the thesis and its latest memo.
  useEffect(() => {
    const ids = Array.from(new Set((pending ?? []).map((o) => o.thesis_id).filter(Boolean))) as string[];
    if (!ids.length) { setCtx({}); return; }
    let cancelled = false;
    (async () => {
      const entries = await Promise.all(ids.map(async (id) => {
        try {
          const thesis = await fundApiClient.getThesis(id);
          let memo: MemoView | undefined;
          if (thesis.memo_ids?.length) {
            const m = await fundApiClient.getThesisMemos(id);
            memo = m.memos?.[m.memos.length - 1];
          }
          return [id, { thesis, memo }] as const;
        } catch { return null; }
      }));
      if (!cancelled) setCtx(Object.fromEntries(entries.filter(Boolean) as any));
    })();
    return () => { cancelled = true; };
  }, [pending]);

  const act = async (o: PendingOrder, approve: boolean) => {
    setBusy(o.order_id);
    try {
      if (approve) await fundApiClient.approveOrder(o.order_id, "rushi");
      else await fundApiClient.declineOrder(o.order_id, "rushi");
      await load();
    } catch (e: any) {
      setErr(spineError(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className={KT.page}>
      <StudioHeader
        subtitle="What needs a human right now"
        actions={
          <button className={`flex h-8 items-center ${KT.btnGhost}`} onClick={() => load()}>
            <RefreshCw size={14} className="mr-1.5" /> Refresh
          </button>
        }
      />

      <div className="mx-auto max-w-[1000px] px-6 py-6">
        {err && (
          <div className={`mb-4 flex items-start gap-2 p-3 text-sm ${KT.inset} ${KT.sev.warn}`}>
            <AlertTriangle size={15} className="mt-0.5 shrink-0" />
            <div>
              <div className="font-medium">Cannot read the approval queue</div>
              <div className={`mt-0.5 ${KT.muted}`}>{err}</div>
              <div className="mt-1 text-[11px]">
                Anything awaiting your approval is still waiting — this is not an empty queue.
              </div>
            </div>
          </div>
        )}

        {loading ? (
          <div className={`flex items-center gap-2 px-1 py-16 text-sm ${KT.muted}`}>
            <Loader2 size={14} className="animate-spin" /> Loading…
          </div>
        ) : pending === null ? (
          <div className={`${KT.card} text-sm ${KT.muted}`}>
            The queue is unreadable, so its contents are unknown.
          </div>
        ) : pending.length === 0 ? (
          <div className={`${KT.card} text-center`}>
            <div className={`${KT.numberLg} ${KT.accent}`}>Nothing awaiting you</div>
            <div className={`mt-1 text-sm ${KT.muted}`}>
              No orders pending approval. New proposals land here.
            </div>
            <div className="mt-4 flex justify-center gap-2">
              <Link href="/clark/studio/monitor" className={KT.btnGhost}>Check the fund</Link>
              <Link href="/clark/studio/lab" className={KT.btnGhost}>Research an idea</Link>
            </div>
          </div>
        ) : (
          <>
            <div className={`mb-3 ${KT.label}`}>{pending.length} awaiting approval</div>
            <div className="space-y-4">
              {pending.map((o) => {
                const c = o.thesis_id ? ctx[o.thesis_id] : undefined;
                const ip = o.impact_preview || {};
                return (
                  <div key={o.order_id} className={KT.card}>
                    {/* the ticket */}
                    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                      <span className="text-base font-semibold uppercase">{o.side}</span>
                      <span className={KT.numberLg}>{o.qty}</span>
                      <span className="text-base font-semibold">{o.symbol}</span>
                      {ip.notional_usd != null && (
                        <span className={`text-sm ${KT.muted}`}>
                          ≈ {money(ip.notional_usd)}
                          {ip.nav_before
                            ? ` · ${((ip.notional_usd / ip.nav_before) * 100).toFixed(1)}% of NAV`
                            : ""}
                        </span>
                      )}
                    </div>

                    {/* the case for it */}
                    {c ? (
                      <div className={`mt-3 p-3 ${KT.inset}`}>
                        <div className="flex items-center gap-1.5">
                          <span className={KT.chip}>thesis</span>
                          <span className="text-[12px] font-medium">{c.thesis.title}</span>
                        </div>
                        {c.thesis.claim && <p className={`mt-1.5 text-[12px] ${KT.body}`}>{c.thesis.claim}</p>}
                        {c.memo?.recommendation && (
                          <p className="mt-1.5 text-[12px] font-medium">▸ {c.memo.recommendation}</p>
                        )}
                        {!!c.thesis.invalidation_conditions?.length && (
                          <div className="mt-2">
                            <div className={KT.label}>Invalidated if</div>
                            <ul className={`mt-1 space-y-0.5 text-[11px] ${KT.muted}`}>
                              {c.thesis.invalidation_conditions.map((x, i) => <li key={i}>· {x}</li>)}
                            </ul>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className={`mt-3 p-3 text-[12px] ${KT.inset} ${KT.sev.warn}`}>
                        No thesis attached — there is no stated case for this trade.
                      </div>
                    )}

                    {/* what it does to the book */}
                    {ip.cash_before != null && ip.cash_after != null && (
                      <div className={`mt-3 flex flex-wrap gap-x-6 gap-y-1 text-[12px] ${KT.muted}`}>
                        <span>NAV {money(ip.nav_before)}</span>
                        <span>cash {money(ip.cash_before)} → {money(ip.cash_after)}</span>
                        {ip.quote_price != null && <span>quote {money(ip.quote_price)}</span>}
                      </div>
                    )}

                    <div className="mt-4 flex gap-2">
                      <button
                        disabled={busy === o.order_id}
                        onClick={() => act(o, true)}
                        className={`flex items-center gap-1.5 ${KT.btn}`}
                      >
                        {busy === o.order_id ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                        Approve
                      </button>
                      <button
                        disabled={busy === o.order_id}
                        onClick={() => act(o, false)}
                        className={`flex items-center gap-1.5 ${KT.btnDanger}`}
                      >
                        <X size={14} /> Decline
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
