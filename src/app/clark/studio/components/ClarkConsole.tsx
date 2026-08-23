"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ChevronRight, Loader2, RefreshCw, Sparkles, X } from "lucide-react";
import { KT } from "../theme";
import { processNaturalLanguageQuery } from "@/lib/agents_api";
import { fundApiClient } from "@/lib/fund_api";
import { ClarkMarkdown } from "./ClarkMarkdown";
import { bodyPaddingRight, openByDefault, railLayout } from "./railLayout";

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

const PREF_KEY = "clark.rail.open";

export function ClarkConsole() {
  // Open by default WHERE THE RAIL PUSHES — the point of a rail is that it is
  // simply there, the way a terminal pane is. Where it cannot push, "open by
  // default" would mean a full-viewport chat sheet over a cockpit the operator
  // has not asked anything about yet (CDO D1). The pill is the honest default
  // there. `openByDefault` derives that from the layout law rather than from a
  // second breakpoint; a stated preference always wins over both.
  const [open, setOpen] = useState(true);
  /* The LAYOUT viewport width, in px, or null before it has been read.
     `documentElement.clientWidth`, never `innerWidth`: they differ by the
     classic scrollbar (1009 against 1024 on the probe machine) and a `right:0`
     fixed panel sits at the layout edge — deciding the layout with the larger
     number is a 15px error in the direction that clips. null is UNREAD, and
     `railLayout` refuses to dock against it. */
  const [vw, setVw] = useState<number | null>(null);
  //: True once the mount effect has decided the default. Until then the
  //: persistence effect below must not write, or the computed default would be
  //: recorded as a preference the operator never expressed — and a phone visit
  //: would then keep the rail shut on the desktop.
  const settled = useRef(false);
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
    const width = document.documentElement.clientWidth;
    setVw(width);
    let saved: string | null = null;
    try {
      saved = window.localStorage.getItem(PREF_KEY);
    } catch {
      /* private mode — fall through to the width-derived default */
    }
    if (saved !== null) {
      setOpen(saved === "1");
    } else {
      // Width-derived, not device-sniffed: the question is whether this
      // viewport can hold the rail BESIDE the cockpit, which is exactly the
      // question the layout law answers for the reflow below.
      setOpen(openByDefault(width));
    }
    settled.current = true;
  }, []);

  useEffect(() => {
    if (!settled.current) return;
    try {
      window.localStorage.setItem(PREF_KEY, open ? "1" : "0");
    } catch {
      /* not worth failing the panel over */
    }
  }, [open]);

  // Track the layout viewport, because the rail's WIDTH is now a function of
  // it and not only its mode. The old code only had to re-apply a padding, so
  // a listener that wrote to the DOM directly was enough; a width that varies
  // has to reach the render.
  //
  // A ResizeObserver, NOT just `resize` — and that is a measured correction to
  // my own first cut. The layout viewport shrinks by the scrollbar's width the
  // moment the page grows tall enough to need one, and THAT FIRES NO RESIZE
  // EVENT. Probed at an emulated 900px: the mount read 900, the desk's content
  // loaded, `clientWidth` became 885, and the sheet rendered 900px wide with
  // its left edge at −15. Harmless there; in the shrink band it would hold the
  // cockpit 15px under its measured floor. The observer sees it because it
  // watches the element, not the window.
  useEffect(() => {
    const read = () => setVw(document.documentElement.clientWidth);
    read();
    window.addEventListener("resize", read);
    const ro = typeof ResizeObserver === "function" ? new ResizeObserver(read) : null;
    ro?.observe(document.documentElement);
    return () => {
      window.removeEventListener("resize", read);
      ro?.disconnect();
    };
  }, []);

  const layout = railLayout(vw ?? Number.NaN, open);

  // Reflow the cockpit BESIDE the rail rather than under it.
  //
  // THE DEFECT THIS CLOSES, measured by CDP probe at 1024px: the rail sat at
  // x=589 over content running to x=1009 with NO inset, and 501 elements
  // across the six Studio pages — the risk bar's breach sentence, the position
  // ticker, the right half of every decision card — had their clicks
  // intercepted by an opaque panel (65 of them on the CEO desk alone).
  // The comment that used to sit here called that "a temporary overlap"; the
  // probe says it is permanent for every 1024 laptop whose stored preference
  // is open. `railLayout` now shrinks the rail instead, and covers the whole
  // viewport only when even that will not fit. The inset is the rail's OWN
  // width, read from the same object, so the two cannot drift apart.
  // Keyed on the STRING, not on `layout` — `railLayout` returns a fresh object
  // every render, so depending on it would re-run this effect on every render
  // for no change.
  const padRight = bodyPaddingRight(layout);
  useEffect(() => {
    document.body.style.paddingRight = padRight;
    return () => { document.body.style.paddingRight = ""; };
  }, [padRight]);

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

    // Situational suggestions come first — they are derived from what is
    // actually wrong right now. These are the standing ones, and they exist to
    // teach the surface: an operator cannot ask for a backtest or a cost
    // breakdown if nothing ever hints those are questions Clark can answer.
    //
    // Rotated rather than listed, because four fixed prompts become furniture
    // the eye skips after a day. The rotation is keyed to the minute so it is
    // stable within a session but different across them.
    const standing = [
      "What is the single riskiest thing about the fund right now?",
      "Walk me through what this book is actually exposed to.",
      "Backtest NVDA over the last 6 months with an SMA crossover.",
      "Are our trading costs running above what the backtests assume?",
      "What can I still do today without burning a day trade?",
      "Which position is furthest from where its strategy wants it?",
      "Does our book agree with the broker right now?",
      "Do a pass over the fund and tell me anything that deserves attention.",
      "Compare our INTC position against the concentration limit.",
      "What did each strategy actually trade today?",
    ];
    const offset = Math.floor(Date.now() / 60000) % standing.length;
    for (let i = 0; i < standing.length; i += 1) {
      suggestions.push(standing[(offset + i) % standing.length]);
    }

    setCtx({ lines, suggestions: suggestions.slice(0, 5), at: Date.now() });
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

  // Orientation, not a data dump.
  //
  // This used to inject every number the panel had read — NAV, positions, cash,
  // alarms — and instruct Clark to answer from those figures alone. That was
  // right while Clark had no way to reach the spine. It became actively wrong
  // the moment it did: the panel's copy is up to 30 seconds stale, so Clark
  // would get NAV $2,027.60 in the prompt and $2,032.22 from fund_nav() in the
  // same turn and have to choose. Two sources of truth for the fund's own
  // numbers is precisely the failure this system exists to prevent.
  //
  // So the prompt now carries only what Clark CANNOT fetch — which screen the
  // operator is on, and what is visibly wrong — and tells it to read the rest.
  // That also hands most of an 8k window back to tool results.
  const contextBlock = useMemo(() => {
    const pick = (prefix: string) => ctx.lines.find((l) => l.startsWith(prefix));
    return [
      "[Krypton Fund cockpit — the operator is looking at the Monitor screen.]",
      pick("Market:") ? `- ${pick("Market:")}` : null,
      pick("ACTIVE ALARMS") ? `- ${pick("ACTIVE ALARMS")}` : null,
      "",
      "Read live figures with your tools (fund_nav, fund_risk, fund_positions,",
      "fund_compliance and the rest) rather than assuming any number. If a tool",
      "cannot be reached, say so — never estimate a figure the fund could have",
      "told you.",
    ]
      .filter(Boolean)
      .join("\n");
  }, [ctx.lines]);

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
  // `pill` covers both "the operator closed it" and "the viewport could not be
  // measured" — see railLayout: docking against an unread width is how content
  // ends up under something that eats its clicks.
  const dock = layout.mode === "pill" ? renderPill() : renderPanel();
  return mounted ? createPortal(dock, document.body) : null;

  // --- collapsed ----------------------------------------------------------
  function renderPill() {
    return (
      <button
        onClick={() => setOpen(true)}
        title="Ask Clark about what is on screen (Ctrl/Cmd-K)"
        className="fixed bottom-5 right-5 z-40 flex h-11 items-center gap-2 rounded-full border border-[var(--kt-agent-border)] bg-[var(--kt-agent-bg)] px-4 text-sm font-medium text-[var(--kt-agent)] backdrop-blur transition hover:border-[var(--kt-agent)]"
      >
        <Sparkles size={15} /> Ask Clark
      </button>
    );
  }

  // --- docked -------------------------------------------------------------
  // No backdrop in `push`: the cockpit stays clickable BESIDE the rail, which
  // is the whole reason for this shape. In `sheet` the rail is the viewport,
  // so there is nothing behind it to click and it announces itself as a dialog
  // — offering covered content to a screen reader as though it were reachable
  // is the same defect as offering it to a mouse.
  //
  // NOT DONE, and deliberately: the sheet does NOT lock the body's scroll.
  // `overflow: hidden` on <body> removes the classic scrollbar, which changes
  // `documentElement.clientWidth` by ~15px, which the ResizeObserver above
  // feeds straight back into the mode decision. In a ~15px band either side of
  // the sheet boundary that is a loop — sheet hides the bar, the width grows
  // past the boundary, the mode becomes push, the bar returns, the width
  // shrinks. Background scroll-chaining is the smaller defect. A focus trap is
  // also absent; both are worth doing with a width source that does not move.
  //
  // The width comes from `layout` and nowhere else. It used to be a constant
  // beside a `max-w-[92vw]`, which is two owners of one edge: they agree only
  // while neither binds, and in sheet mode the 92vw would leave exactly the
  // 8% strip of half-clickable content this fix removes.
  function renderPanel() {
    const sheet = layout.mode === "sheet";
    return (
      <aside
        style={{ width: layout.railWidth }}
        role={sheet ? "dialog" : undefined}
        aria-modal={sheet ? true : undefined}
        aria-label={sheet ? "Clark" : undefined}
        className="fixed inset-y-0 right-0 z-40 flex flex-col border-l border-[var(--kt-border)] bg-[var(--kt-surface)]"
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
