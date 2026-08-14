"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Loader2, MessageSquare, X } from "lucide-react";
import { KT } from "../theme";
import { processNaturalLanguageQuery } from "@/lib/agents_api";
import { fundApiClient } from "@/lib/fund_api";

/**
 * Clark, over the cockpit rather than instead of it.
 *
 * The header used to link to /clark, which navigated away from the very screen
 * the operator wanted to ask about. By the time Clark was open the numbers were
 * gone, so any question had to re-state them from memory — and a question that
 * begins "I think NAV was around two thousand" is one the answer cannot be
 * trusted against.
 *
 * So this is a slide-over. The book stays on screen behind it, and the question
 * arrives with the fund's actual state attached.
 *
 * Two rules it follows, both inherited from the rest of the harness:
 *
 *   1. **Never send a number we did not read.** The context block is built from
 *      live spine responses. Anything unreadable is sent as "unknown", never as
 *      zero and never omitted — Clark reasoning from a silently missing cash
 *      balance is worse than Clark saying it cannot see one.
 *
 *   2. **Show the operator what Clark was told.** The context is inspectable
 *      before sending. An assistant answering from invisible state is a machine
 *      whose reasoning cannot be checked, which is the opposite of what this
 *      fund is built around.
 *
 * The suggested questions are derived from what is actually happening — a
 * breach, a day-trade budget nearly spent, a closed venue. A static list would
 * suggest asking about a drawdown on a day there isn't one.
 */

type Msg = { role: "you" | "clark"; text: string; ts: number };

/** What Clark is told about the screen. Every field can be "unknown". */
type Ctx = {
  lines: string[];
  suggestions: string[];
};

const val = (n: number | null | undefined, dp = 2, prefix = "") =>
  n == null || !Number.isFinite(n) ? "unknown" : `${prefix}${Number(n).toFixed(dp)}`;

export function ClarkConsole() {
  const [open, setOpen] = useState(false);
  const [ctx, setCtx] = useState<Ctx>({ lines: [], suggestions: [] });
  const [showCtx, setShowCtx] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  /** Read the fund's state fresh each time the panel opens. */
  const loadContext = useCallback(async () => {
    const [nav, session, comp, risk, tca, ledger] = await Promise.all([
      fundApiClient.getNav().catch(() => null),
      fundApiClient.getMarketSession().catch(() => null),
      fundApiClient.getCompliance().catch(() => null),
      fundApiClient.getRiskMonitor().catch(() => null),
      fundApiClient.getTca(200).catch(() => null),
      fundApiClient.verifyLedger().catch(() => null),
    ]);

    const lines: string[] = [];
    const suggestions: string[] = [];

    // --- the book -------------------------------------------------------
    const live = nav?.live;
    if (live) {
      lines.push(`NAV $${val(live.total_nav_usd)} · ${val(live.units_outstanding, 0)} units · $${val(live.nav_per_unit, 6)}/unit`);
      const held = (live.positions || [])
        .map((p) => `${p.symbol} ${p.qty}@$${val(p.mark)} = $${val(p.usd_value)}`)
        .join("; ");
      lines.push(`Positions: ${held || "none"}`);
      lines.push(`Cash $${val(live.breakdown?.cash)}`);
    } else {
      lines.push("NAV: unknown — the spine did not answer");
    }

    // --- venue ----------------------------------------------------------
    if (session) {
      const mins = session.seconds_to_open ?? session.seconds_to_close;
      const verb = session.seconds_to_close != null ? "closes" : "opens";
      lines.push(
        `Market: ${session.phase}${mins != null ? ` — ${verb} in ${Math.round(mins / 60)} min` : ""}`,
      );
      if (session.state === "closed") {
        suggestions.push("The market is shut — what should I have ready before the open?");
      }
    } else {
      lines.push("Market session: unknown");
    }

    // --- risk -----------------------------------------------------------
    if (risk) {
      lines.push(`Drawdown ${val(risk.drawdown?.drawdown_pct, 2)}% of ${val(risk.drawdown?.limit_pct, 0)}% limit`);
      lines.push(`Cash ${val(risk.cash_pct, 1)}% · gross exposure ${val(risk.gross_exposure_pct, 1)}%`);
      lines.push(`Trading halted: ${risk.halted ? "YES" : "no"}`);
      // Severity is carried through rather than flattened: "critical" and
      // "info" are very different instructions to someone deciding what to do
      // in the next five minutes.
      const alarms = risk.alarms || [];
      if (alarms.length) {
        lines.push(
          `ACTIVE ALARMS: ${alarms
            .map((a) => `[${a.severity}] ${a.message} (${a.metric} vs limit ${a.threshold})`)
            .join(" | ")}`,
        );
        const worst = alarms.find((a) => a.severity === "critical") || alarms[0];
        suggestions.push(`How do I clear this: ${worst.message}`);
      } else {
        lines.push("Active alarms: none");
      }
    } else {
      lines.push("Risk state: unknown — this is NOT an all-clear");
    }

    // --- the cliff ------------------------------------------------------
    if (comp?.pdt?.applies) {
      const { used, max_day_trades, remaining, source } = comp.pdt;
      lines.push(
        `Day trades ${used}/${max_day_trades} used, ${remaining ?? 0} left before a 90-day closing-only restriction (counted via ${source}). Equity $${val(comp.account?.equity)} is under the $25k PDT threshold.`,
      );
      if ((remaining ?? 0) <= 1) {
        suggestions.push("I have almost no day trades left — what can I still safely do today?");
      }
    }

    // --- execution ------------------------------------------------------
    const v = tca?.summary?.vs_assumption;
    if (v) {
      lines.push(
        `Realised trading cost ${val(v.realised_bps_per_side, 1)}bps/side vs ${val(v.assumed_bps_per_side, 0)}bps assumed, over ${v.sample} fill(s) — too few to be an estimate.`,
      );
      if (v.excess_bps > 1) {
        suggestions.push("Why are we paying more than the backtest assumed, and what would reduce it?");
      }
    }

    // --- integrity ------------------------------------------------------
    if (ledger) {
      lines.push(
        ledger.ok
          ? `Ledger chain intact: ${ledger.chained} events verified, ${ledger.unchained} predate the chain.`
          : `LEDGER CHAIN BROKEN at seq ${ledger.first_break?.seq}: ${ledger.first_break?.reason}`,
      );
      if (!ledger.ok) suggestions.push("The ledger chain is broken — what do I do?");
    }

    // Always-useful fallbacks, appended so situational ones lead.
    suggestions.push(
      "Walk me through what this book is actually exposed to.",
      "What is the single riskiest thing about the fund right now?",
    );

    setCtx({ lines, suggestions: suggestions.slice(0, 4) });
  }, []);

  useEffect(() => {
    if (open) {
      loadContext();
      setTimeout(() => inputRef.current?.focus(), 60);
    }
  }, [open, loadContext]);

  // Cmd/Ctrl-K to open, Escape to close — the panel should be reachable
  // without moving the mouse off whatever you were reading.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    boxRef.current?.scrollTo({ top: boxRef.current.scrollHeight, behavior: "smooth" });
  }, [msgs, busy]);

  const contextBlock = useMemo(
    () =>
      ctx.lines.length
        ? `[Krypton Fund — live state, read from the spine just now]\n${ctx.lines
            .map((l) => `- ${l}`)
            .join("\n")}\n\nAnswer using ONLY these figures. Where a value says "unknown", say so rather than estimating.`
        : "",
    [ctx.lines],
  );

  const ask = useCallback(
    async (text: string) => {
      const question = text.trim();
      if (!question || busy) return;
      setMsgs((m) => [...m, { role: "you", text: question, ts: Date.now() }]);
      setQ("");
      setBusy(true);
      setErr(null);
      try {
        const res = await processNaturalLanguageQuery(
          `${contextBlock}\n\nOperator's question: ${question}`,
        );
        const reply =
          (res?.response as string) ||
          (res?.message as string) ||
          (res?.result as string) ||
          (typeof res === "string" ? res : JSON.stringify(res).slice(0, 1200));
        setMsgs((m) => [...m, { role: "clark", text: reply, ts: Date.now() }]);
      } catch {
        // Named plainly: a copilot that silently fails looks like one that has
        // nothing to say.
        setErr(
          "Clark is unreachable — the agents service is not answering. The fund itself is unaffected; this panel is the only thing that is down.",
        );
      } finally {
        setBusy(false);
      }
    },
    [busy, contextBlock],
  );

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className={`flex h-8 items-center gap-1.5 ${KT.btn}`}
        title="Ask Clark about what is on screen (Ctrl/Cmd-K)"
      >
        <MessageSquare size={13} /> Clark
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex justify-end">
          {/* The book stays visible behind — that is the point of an overlay. */}
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-[2px]"
            onClick={() => setOpen(false)}
          />

          <aside className="relative flex h-full w-full max-w-[560px] flex-col border-l border-[var(--kt-border)] bg-[var(--kt-bg)] shadow-2xl">
            <div className="flex items-start justify-between border-b border-[var(--kt-border)] px-5 py-3">
              <div>
                <div className={KT.title}>Clark</div>
                <div className={`mt-0.5 text-[11px] ${KT.muted}`}>
                  Sees the same numbers you do — asked with the book attached.
                </div>
              </div>
              <button onClick={() => setOpen(false)} className={KT.btn} title="Close (Esc)">
                <X size={14} />
              </button>
            </div>

            {/* What Clark is being told. Inspectable on purpose. */}
            <div className="border-b border-[var(--kt-border)] px-5 py-2">
              <button
                onClick={() => setShowCtx((s) => !s)}
                className={`text-[11px] ${KT.muted} hover:text-[var(--kt-text)]`}
              >
                {showCtx ? "▾" : "▸"} Context sent with every question ({ctx.lines.length} facts)
              </button>
              {showCtx && (
                <pre className="mt-2 max-h-[180px] overflow-auto whitespace-pre-wrap rounded bg-[var(--kt-hover)] p-2 font-mono text-[10px] leading-relaxed">
                  {ctx.lines.length
                    ? ctx.lines.join("\n")
                    : "Nothing readable — the spine did not answer."}
                </pre>
              )}
            </div>

            <div ref={boxRef} className="flex-1 space-y-3 overflow-auto px-5 py-4">
              {msgs.length === 0 && (
                <div className="space-y-2">
                  <div className={`text-[12px] ${KT.muted}`}>
                    Ask anything about the book in front of you.
                  </div>
                  {ctx.suggestions.map((s) => (
                    <button
                      key={s}
                      onClick={() => ask(s)}
                      className="block w-full rounded border border-[var(--kt-border)] px-3 py-2 text-left text-[12px] hover:bg-[var(--kt-hover)]"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}

              {msgs.map((m) => (
                <div
                  key={m.ts + m.role}
                  className={m.role === "you" ? "text-right" : "text-left"}
                >
                  <div
                    className={`inline-block max-w-[92%] whitespace-pre-wrap rounded-lg px-3 py-2 text-[12.5px] leading-relaxed ${
                      m.role === "you"
                        ? "bg-[var(--kt-accent-bg)] text-[var(--kt-accent)]"
                        : "border border-[var(--kt-border)]"
                    }`}
                  >
                    {m.text}
                  </div>
                </div>
              ))}

              {busy && (
                <div className={`flex items-center gap-2 text-[12px] ${KT.muted}`}>
                  <Loader2 size={13} className="animate-spin" /> Thinking…
                </div>
              )}
              {err && <div className={`text-[12px] ${KT.sev.warn}`}>{err}</div>}
            </div>

            <div className="border-t border-[var(--kt-border)] p-3">
              <textarea
                ref={inputRef}
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    ask(q);
                  }
                }}
                rows={2}
                placeholder="Ask about this screen…  (Enter to send, Shift-Enter for a new line)"
                className="w-full resize-none rounded border border-[var(--kt-border)] bg-transparent px-3 py-2 text-[12.5px] outline-none focus:border-[var(--kt-accent)]"
              />
              <div className={`mt-1 flex justify-between text-[10px] ${KT.muted}`}>
                <span>Clark advises. It cannot place or approve an order.</span>
                <span>Ctrl/Cmd-K</span>
              </div>
            </div>
          </aside>
        </div>
      )}
    </>
  );
}
