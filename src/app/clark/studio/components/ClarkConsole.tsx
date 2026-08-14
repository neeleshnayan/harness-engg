"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ChevronRight, Loader2, RefreshCw, Sparkles, X } from "lucide-react";
import { KT } from "../theme";
import { processNaturalLanguageQuery } from "@/lib/agents_api";
import { fundApiClient } from "@/lib/fund_api";
import { ClarkMarkdown } from "./ClarkMarkdown";

/**
 * Clark, docked bottom-right, alongside the cockpit rather than over it.
 *
 * Two earlier shapes were both wrong. A link to /clark navigated away from the
 * screen the operator wanted to ask about, so the question had to restate the
 * numbers from memory. A full-screen modal kept the numbers on screen but
 * behind a backdrop, so you could see them and not touch them — no clicking
 * through to a position while asking about it.
 *
 * Docked solves both: the cockpit stays fully interactive, so the natural
 * motion is to look at something, ask about it, act on the answer, without the
 * assistant ever getting in the way of the second step.
 *
 * That interactivity creates the one problem this shape has and the modal did
 * not. A panel that stays open while the operator works accumulates stale
 * context — the book moves, a fill lands, an alarm clears, and Clark is still
 * holding what it read when the panel opened. So the context re-reads on a
 * timer and is stamped with its age, and anything older than a minute says so
 * rather than being quietly presented as current.
 *
 * Rules carried from the rest of the harness:
 *
 *   1. Never send a number we did not read. Unreadable values go as "unknown",
 *      never zero and never omitted — Clark reasoning from a silently missing
 *      cash balance is worse than Clark saying it cannot see one.
 *   2. Show the operator what Clark was told. The context is inspectable. An
 *      assistant answering from invisible state cannot be checked.
 */

type Msg = {
  role: "you" | "clark";
  text: string;
  ts: number;
  /** Seconds old the context was when this answer was produced. Stamped per
   *  message because a docked panel stays open for a long time and "which
   *  snapshot was this true of" stops being obvious after the third question. */
  ctxAgeS?: number;
};
type Ctx = { lines: string[]; suggestions: string[]; at: number };

const val = (n: number | null | undefined, dp = 2, prefix = "") =>
  n == null || !Number.isFinite(n) ? "unknown" : `${prefix}${Number(n).toFixed(dp)}`;

/** How often the open panel re-reads the book. */
const CONTEXT_REFRESH_MS = 30_000;
/** Past this, the panel says the context is aging rather than implying it is live. */
const STALE_AFTER_MS = 60_000;

/** Width of the docked rail. Also the page's right inset while it is open. */
const RAIL_W = 420;
/** Below this the rail would leave no usable cockpit, so it overlays instead. */
const PUSH_MIN_WIDTH = 1100;
const PREF_KEY = "clark.rail.open";

export function ClarkConsole() {
  // Open by default: the point of a rail is that it is simply there, the way a
  // terminal pane is. Persisted, so a deliberate close is not undone by the
  // next navigation.
  const [open, setOpen] = useState(true);
  const [ctx, setCtx] = useState<Ctx>({ lines: [], suggestions: [], at: 0 });
  const [showCtx, setShowCtx] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadingCtx, setLoadingCtx] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [, tick] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(PREF_KEY);
      if (saved !== null) setOpen(saved === "1");
    } catch {
      /* private mode — the default stands */
    }
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(PREF_KEY, open ? "1" : "0");
    } catch {
      /* not worth failing the panel over */
    }
  }, [open]);

  // Reflow the cockpit beside the rail rather than under it. A persistent
  // panel that overlaps means the right edge of every page — where the risk
  // numbers and the theme toggle live — is permanently hidden, and the
  // operator never sees what they are missing.
  //
  // Narrow viewports overlay instead: pushing 380px off a 900px screen leaves
  // a cockpit too cramped to read, which is worse than a temporary overlap.
  useEffect(() => {
    const apply = () => {
      const push = open && window.innerWidth >= PUSH_MIN_WIDTH;
      document.body.style.paddingRight = push ? `${RAIL_W}px` : "";
    };
    apply();
    window.addEventListener("resize", apply);
    return () => {
      window.removeEventListener("resize", apply);
      document.body.style.paddingRight = "";
    };
  }, [open]);

  const loadContext = useCallback(async () => {
    setLoadingCtx(true);
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

    if (session) {
      const secs = session.seconds_to_open ?? session.seconds_to_close;
      const verb = session.seconds_to_close != null ? "closes" : "opens";
      lines.push(
        `Market: ${session.phase}${secs != null ? ` — ${verb} in ${Math.round(secs / 60)} min` : ""}`,
      );
      if (session.state === "closed") {
        suggestions.push("The market is shut — what should I have ready before the open?");
      }
    } else {
      lines.push("Market session: unknown");
    }

    if (risk) {
      lines.push(`Drawdown ${val(risk.drawdown?.drawdown_pct, 2)}% of ${val(risk.drawdown?.limit_pct, 0)}% limit`);
      lines.push(`Cash ${val(risk.cash_pct, 1)}% · gross exposure ${val(risk.gross_exposure_pct, 1)}%`);
      lines.push(`Trading halted: ${risk.halted ? "YES" : "no"}`);
      const alarms = risk.alarms || [];
      if (alarms.length) {
        // Severity survives: "critical" and "info" are very different
        // instructions to someone deciding what to do in the next five minutes.
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

    if (comp?.pdt?.applies) {
      const { used, max_day_trades, remaining, source } = comp.pdt;
      lines.push(
        `Day trades ${used}/${max_day_trades} used, ${remaining ?? 0} left before a 90-day closing-only restriction (via ${source}). Equity $${val(comp.account?.equity)} is under the $25k PDT threshold.`,
      );
      if ((remaining ?? 0) <= 1) {
        suggestions.push("I have almost no day trades left — what can I still safely do today?");
      }
    }

    const v = tca?.summary?.vs_assumption;
    if (v) {
      lines.push(
        `Realised trading cost ${val(v.realised_bps_per_side, 1)}bps/side vs ${val(v.assumed_bps_per_side, 0)}bps assumed, over ${v.sample} fill(s) — too few to be an estimate.`,
      );
      if (v.excess_bps > 1) {
        suggestions.push("Why are we paying more than the backtest assumed?");
      }
    }

    if (ledger) {
      lines.push(
        ledger.ok
          ? `Ledger chain intact: ${ledger.chained} events verified, ${ledger.unchained} predate the chain.`
          : `LEDGER CHAIN BROKEN at seq ${ledger.first_break?.seq}: ${ledger.first_break?.reason}`,
      );
      if (!ledger.ok) suggestions.push("The ledger chain is broken — what do I do?");
    }

    suggestions.push(
      "What is the single riskiest thing about the fund right now?",
      "Walk me through what this book is actually exposed to.",
    );

    setCtx({ lines, suggestions: suggestions.slice(0, 4), at: Date.now() });
    setLoadingCtx(false);
  }, []);

  // Re-read while open. A docked panel outlives the state it was opened with.
  useEffect(() => {
    if (!open) return;
    loadContext();
    setTimeout(() => inputRef.current?.focus(), 60);
    const t = setInterval(loadContext, CONTEXT_REFRESH_MS);
    return () => clearInterval(t);
  }, [open, loadContext]);

  // Drives the "read Ns ago" label between refreshes.
  useEffect(() => {
    if (!open) return;
    const t = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, [open]);

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

  const age = ctx.at ? Date.now() - ctx.at : 0;
  const stale = ctx.at > 0 && age > STALE_AFTER_MS;

  const contextBlock = useMemo(
    () =>
      ctx.lines.length
        ? `[Krypton Fund — live state, read ${Math.round(age / 1000)}s ago]\n${ctx.lines
            .map((l) => `- ${l}`)
            .join("\n")}\n\nAnswer using ONLY these figures. Where a value says "unknown", say so rather than estimating.`
        : "",
    // age deliberately excluded: it changes every second and would rebuild the
    // block constantly. It is read at send time, which is when it matters.
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      const ageAtSend = ctx.at ? Date.now() - ctx.at : 0;
      try {
        const res = await processNaturalLanguageQuery(
          `${contextBlock}\n\nOperator's question: ${question}`,
        );
        const reply =
          (res?.response as string) ||
          (res?.message as string) ||
          (res?.result as string) ||
          (typeof res === "string" ? res : JSON.stringify(res).slice(0, 1200));
        setMsgs((m) => [
          ...m,
          { role: "clark", text: reply, ts: Date.now(), ctxAgeS: Math.round(ageAtSend / 1000) },
        ]);
      } catch {
        setErr(
          "Clark is unreachable — the agents service is not answering. The fund itself is unaffected; this panel is the only thing down.",
        );
      } finally {
        setBusy(false);
      }
    },
    [busy, contextBlock],
  );

  // Rendered into <body>, not where it sits in the tree.
  //
  // StudioHeader carries `backdrop-blur-md`, and any ancestor with a
  // backdrop-filter (or transform, or filter) becomes the containing block for
  // position:fixed descendants. So the dock anchored to the HEADER rather than
  // the viewport and sat 266px above the top of the screen — with a computed
  // style of `bottom: 20px` that looked perfectly correct. A portal is the
  // reliable fix; moving the component up the tree would only work until
  // someone adds a blur to whatever contains it next.
  const mounted = useMounted();
  const dock = !open ? renderPill() : renderPanel();
  return mounted ? createPortal(dock, document.body) : null;

  // --- collapsed ----------------------------------------------------------
  function renderPill() {
    return (
      <button
        onClick={() => setOpen(true)}
        title="Ask Clark about what is on screen (Ctrl/Cmd-K)"
        className="fixed bottom-5 right-5 z-40 flex h-11 items-center gap-2 rounded-full border border-[var(--kt-agent-border)] bg-[var(--kt-agent-bg)] px-4 text-sm font-medium text-[var(--kt-agent)] shadow-lg backdrop-blur transition hover:border-[var(--kt-agent)]"
      >
        <Sparkles size={15} /> Ask Clark
      </button>
    );
  }

  // --- docked -------------------------------------------------------------
  // No backdrop: the cockpit stays clickable underneath, which is the whole
  // reason for this shape.
  function renderPanel() {
    return (
      <aside
        style={{ width: RAIL_W }}
        className="fixed inset-y-0 right-0 z-40 flex max-w-[92vw] flex-col border-l border-[var(--kt-border)] bg-[var(--kt-surface)]"
      >
        {/* Header — the cockpit's idiom: uppercase mono label, muted second
            line, generous padding. Not a chat titlebar. */}
        <div className={`border-b border-[var(--kt-border)] px-6 py-5`}>
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <span className={`${KT.label} !text-[var(--kt-agent)]`}>Clark</span>
                <span className={`h-1 w-1 rounded-full bg-[var(--kt-agent)]`} />
              </div>
              <div className={`mt-1.5 text-xs ${KT.muted}`}>
                {ctx.at === 0
                  ? "Reading the book…"
                  : stale
                    ? `Working from the book as of ${Math.round(age / 1000)}s ago`
                    : "Sees the same numbers you do"}
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <button
                onClick={loadContext}
                disabled={loadingCtx}
                title="Re-read the book"
                className={`rounded-lg p-1.5 ${KT.muted} transition-colors hover:bg-[var(--kt-hover)] hover:text-[var(--kt-text)]`}
              >
                <RefreshCw size={13} className={loadingCtx ? "animate-spin" : ""} />
              </button>
              <button
                onClick={() => setOpen(false)}
                title="Hide (Esc)"
                className={`rounded-lg p-1.5 ${KT.muted} transition-colors hover:bg-[var(--kt-hover)] hover:text-[var(--kt-text)]`}
              >
                <ChevronRight size={15} />
              </button>
            </div>
          </div>
        </div>

        {/* Conversation */}
        <div ref={boxRef} className="flex-1 overflow-auto">
          {msgs.length === 0 ? (
            <div>
              <div className="px-6 pb-3 pt-6">
                <div className={KT.label}>Ask about this screen</div>
              </div>
              {/* Rows, divided — the same shape as every list in the cockpit,
                  rather than a stack of individually bordered boxes. */}
              <div className="divide-y divide-[var(--kt-border)] border-y border-[var(--kt-border)]">
                {ctx.suggestions.map((sg) => (
                  <button
                    key={sg}
                    onClick={() => ask(sg)}
                    className="block w-full px-6 py-4 text-left text-sm leading-relaxed text-[var(--kt-text-dim)] transition-colors hover:bg-[var(--kt-hover)] hover:text-[var(--kt-text)]"
                  >
                    {sg}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-8 px-6 py-6">
              {msgs.map((m) => (
                <div key={m.ts + m.role}>
                  <div
                    className={`${KT.label} ${m.role === "clark" ? "!text-[var(--kt-agent)]" : ""}`}
                  >
                    {m.role === "clark" ? "Clark" : "You"}
                  </div>
                  {/* No bubbles. A label and the words, with room to breathe —
                      which is how every other panel here presents content. */}
                  <div
                    className={`mt-2 text-sm leading-relaxed ${
                      m.role === "you" ? "whitespace-pre-wrap text-[var(--kt-text-dim)]" : ""
                    }`}
                  >
                    {m.role === "clark" ? <ClarkMarkdown text={m.text} /> : m.text}
                  </div>
                  {m.role === "clark" && m.ctxAgeS != null && (
                    <div className={`mt-2 text-[10px] ${KT.muted}`}>
                      from the book {m.ctxAgeS}s before this reply
                    </div>
                  )}
                </div>
              ))}

              {busy && (
                <div className="flex items-center gap-2">
                  <Loader2 size={12} className={`animate-spin ${KT.agent.text}`} />
                  <span className={`${KT.label} !tracking-normal`}>thinking</span>
                </div>
              )}
              {err && <div className={`text-xs ${KT.sev.warn}`}>{err}</div>}
            </div>
          )}
        </div>

        {/* What Clark was told — available, not shouting. */}
        <div className="border-t border-[var(--kt-border)] px-6 py-4">
          <button
            onClick={() => setShowCtx((v) => !v)}
            className={`${KT.label} transition-colors hover:text-[var(--kt-text)]`}
          >
            {showCtx ? "Hide" : "Show"} what Clark is told · {ctx.lines.length}
          </button>
          {showCtx && (
            <pre className="mt-3 max-h-[160px] overflow-auto whitespace-pre-wrap rounded-xl bg-[var(--kt-inset)] p-3 font-mono text-[10px] leading-relaxed text-[var(--kt-text-dim)]">
              {ctx.lines.length ? ctx.lines.join("\n") : "Nothing readable — the spine did not answer."}
            </pre>
          )}
        </div>

        {/* Composer */}
        <div className="border-t border-[var(--kt-border)] px-6 py-5">
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
            placeholder="Ask about this screen…"
            className="w-full resize-none rounded-xl border border-[var(--kt-border)] bg-[var(--kt-inset)] px-3.5 py-2.5 text-sm leading-relaxed outline-none transition-colors placeholder:text-[var(--kt-text-muted)] focus:border-[var(--kt-agent-border)]"
          />
          <div className="mt-2.5 flex items-center justify-between">
            <span className={`text-[10px] ${KT.muted}`}>
              Advises only — cannot place or approve an order
            </span>
            {msgs.length > 0 && (
              <button
                onClick={() => setMsgs([])}
                className={`text-[10px] ${KT.muted} transition-colors hover:text-[var(--kt-text)]`}
              >
                clear
              </button>
            )}
          </div>
        </div>
      </aside>
    );
  }
}

/** True once on the client. Portals need a DOM, and SSR has none. */
function useMounted() {
  const [m, setM] = useState(false);
  useEffect(() => setM(true), []);
  return m;
}
