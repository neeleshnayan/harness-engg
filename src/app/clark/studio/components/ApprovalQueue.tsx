"use client";

import React, { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Check, Loader2, X } from "lucide-react";
import { spineError } from "@/lib/spine_error";
import { KT } from "../theme";
import { MemoView, PendingOrder, ThesisView, fundApiClient } from "@/lib/fund_api";

/**
 * Orders waiting on a human, with the case for each one attached.
 *
 * This was its own page. It is a panel now because an approval queue you have to
 * navigate to is a queue you check when you remember to — and the one question
 * an operator with five minutes must not miss is "is anything waiting on me?".
 * So it leads the landing page instead of sitting one click away.
 *
 * The honesty rule it exists to respect: when the spine cannot be read it must
 * NOT render "0 pending". An unknown queue is not an empty queue, and the
 * difference decides whether someone walks away from a trade that is waiting.
 */

const money = (n?: number | null, dp = 2) =>
  n == null ? "—" : `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp })}`;

export function ApprovalQueue({ onChanged, refreshSignal = 0, compact = false,
                                embedded = false }: {
  onChanged?: () => void;
  /** Render without panel chrome, so a parent can put this and the orders it
   *  becomes inside ONE frame — the two halves of a single flow, not two
   *  unrelated boxes that happen to be adjacent. */
  embedded?: boolean;
  /** Bump this to force an immediate reload — e.g. after something elsewhere on
   *  the page creates a proposal. Without it this panel only refreshed on its
   *  own timer, so proposing an order left the queue reading "nothing awaiting
   *  you" for up to 45 seconds: you acted, and the UI showed no result. */
  refreshSignal?: number;
  compact?: boolean;
}) {
  const [pending, setPending] = useState<PendingOrder[] | null>(null);
  const [ctx, setCtx] = useState<Record<string, { thesis: ThesisView; memo?: MemoView }>>({});
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  // What happened to orders acted on in THIS session. Without it an approved
  // card simply vanished and the operator was left with no idea whether the
  // order filled, is still working, or failed at the venue.
  const [outcome, setOutcome] = useState<Record<string, {
    kind: "filled" | "working" | "failed" | "declined";
    detail: string;
    symbol: string;
    side: string;
  }>>({});

  const load = useCallback(async () => {
    try {
      const p = await fundApiClient.getPending();
      setPending(p.pending || []);
      setErr(null);
    } catch (e: unknown) {
      setPending(null);            // unknown — never fall back to an empty list
      setErr(spineError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 45000);
    return () => clearInterval(t);
  }, [load, refreshSignal]);

  // Each order carries the case behind it — the thesis and its latest memo.
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
        } catch {
          return null;
        }
      }));
      if (!cancelled) {
        setCtx(Object.fromEntries(entries.filter(Boolean) as [string, { thesis: ThesisView; memo?: MemoView }][]));
      }
    })();
    return () => { cancelled = true; };
  }, [pending]);

  const act = async (o: PendingOrder, approve: boolean) => {
    setBusy(o.order_id);
    try {
      if (approve) {
        const r = await fundApiClient.approveOrder(o.order_id, "rushi");
        const detail =
          r.status === "filled"
            ? `filled ${r.filled_qty ?? o.qty} @ ${money(r.avg_price)}`
            : r.status === "failed"
              ? `failed at the venue${r.reason ? `: ${r.reason}` : ""}`
              : "sent to the venue — working, not yet filled";
        setOutcome((m) => ({
          ...m,
          [o.order_id]: {
            kind: r.status === "filled" ? "filled" : r.status === "failed" ? "failed" : "working",
            detail, symbol: o.symbol, side: o.side,
          },
        }));
      } else {
        await fundApiClient.declineOrder(o.order_id, "rushi");
        setOutcome((m) => ({
          ...m,
          [o.order_id]: { kind: "declined", detail: "declined — nothing was sent",
                          symbol: o.symbol, side: o.side },
        }));
      }
      await load();
      onChanged?.();
    } catch (e: unknown) {
      setErr(spineError(e));
    } finally {
      setBusy(null);
    }
  };

  const recent = Object.entries(outcome);

  const n = pending?.length ?? 0;

  return (
    <div className={embedded ? "flex h-full flex-col" : KT.panel}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--kt-border)] px-5 py-3">
        <div>
          <span className={KT.label}>Awaiting your approval</span>
          <div className={`mt-1 text-[11px] ${KT.muted}`}>
            Nothing reaches the venue until you approve it here.
          </div>
        </div>
        <span className={`font-mono text-sm tabular-nums ${
          pending === null ? KT.sev.warn : n > 0 ? KT.sev.warn : KT.muted}`}>
          {pending === null ? "unknown" : `${n} pending`}
        </span>
      </div>

      {err && (
        <div className={`m-4 flex items-start gap-2 p-3 text-sm ${KT.inset} ${KT.sev.warn}`}>
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

      {recent.length > 0 && (
        <ul className="divide-y divide-[var(--kt-border)] border-b border-[var(--kt-border)]">
          {recent.map(([id, o]) => (
            <li key={id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-5 py-2.5 text-sm">
              {o.kind === "filled" ? <Check size={14} className={KT.up} />
                : o.kind === "declined" ? <X size={14} className={KT.muted} />
                : o.kind === "failed" ? <AlertTriangle size={14} className={KT.down} />
                : <Loader2 size={14} className={`animate-spin ${KT.muted}`} />}
              <span className="font-medium uppercase">{o.side}</span>
              <span className="font-semibold">{o.symbol}</span>
              <span className={
                o.kind === "filled" ? KT.up : o.kind === "failed" ? KT.down : KT.muted
              }>{o.detail}</span>
              {o.kind === "working" && (
                <span className={`text-[11px] ${KT.muted}`}>
                  — it will appear under Orders below as it settles
                </span>
              )}
              <button onClick={() => setOutcome((m) => {
                        const n = { ...m }; delete n[id]; return n;
                      })}
                      className={`ml-auto text-[11px] ${KT.muted} hover:underline`}>
                dismiss
              </button>
            </li>
          ))}
        </ul>
      )}

      {loading ? (
        <div className={`flex items-center gap-2 px-5 py-8 text-sm ${KT.muted}`}>
          <Loader2 size={14} className="animate-spin" /> Loading…
        </div>
      ) : pending === null ? (
        <div className={`px-5 py-6 text-sm ${KT.muted}`}>
          The queue is unreadable, so its contents are unknown.
        </div>
      ) : n === 0 ? (
        <div className={`px-5 py-6 text-sm ${KT.muted}`}>
          Nothing awaiting you. New proposals land here.
        </div>
      ) : (
        <div className="space-y-4 p-4">
          {pending.map((o) => {
            const c = o.thesis_id ? ctx[o.thesis_id] : undefined;
            const ip = o.impact_preview || {};
            return (
              <div key={o.order_id} className={KT.card}>
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

                {!compact && (c ? (
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
                ))}

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
      )}
    </div>
  );
}
