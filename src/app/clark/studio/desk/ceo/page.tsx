"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AlertTriangle, OctagonX } from "lucide-react";
import {
  fundApiClient, DeskView, PendingOrder, RiskMonitorResponse, SpineEvent,
} from "@/lib/fund_api";
import { KT } from "../../theme";
import { money } from "../../format";
import { StudioHeader } from "../../components/StudioHeader";
import { memoParts } from "../../memo";
import { SeatFace } from "../SeatFace";
import { RecRow } from "../components";
import { fmtAt } from "../seatLib";
import {
  DeskItem, cooMemos, decisionVelocity, moneyGap, orderItems, rankDeskItems,
  recItems, splitDeskItems,
} from "../execDesk";
import { CooTriageChip } from "../components";

/**
 * The CEO's desk — everything awaiting Neelesh's click, in one place.
 *
 * Full build against docs/briefs/EXEC_DESKS_2026-08-20.md (v1 was lean; this
 * upgrades it in place and keeps its honesty semantics verbatim).
 *
 * The page is ORDERED, not merely listed: money → reversibility → staleness,
 * the way the coo seat ranks. The arithmetic is in ../execDesk.ts with tests,
 * because a ranking derived inline in JSX cannot be checked, and a queue that
 * silently mis-ranks is worse than an unranked one — the CEO would trust the
 * top of it.
 *
 * What this page will NOT do:
 *
 *   - It does not price a recommendation. No recommendation on the live desk
 *     carries a money field (47 of 47 on 2026-08-20), and lifting a figure out
 *     of prose would put a number on the CEO's screen that no endpoint ever
 *     returned. The unpriced count is printed instead.
 *   - It does not restate the drawdown or the breach list; the RiskBar in the
 *     shell owns "is anything broken" (design audit: say the alarm once). The
 *     HALT is the one exception the brief asks for, because a halt changes what
 *     a click on this page will DO, and it names where the resume control is
 *     rather than offering one — resuming is not a desk action.
 */
export default function CeoDeskPage() {
  const [desk, setDesk] = useState<DeskView | null>(null);
  const [pending, setPending] = useState<PendingOrder[] | null>(null);
  const [events, setEvents] = useState<SpineEvent[] | null>(null);
  const [risk, setRisk] = useState<RiskMonitorResponse | null>(null);
  const [riskErr, setRiskErr] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [d, p, ev, rk] = await Promise.allSettled([
      fundApiClient.getDesk(),
      fundApiClient.getPending(),
      fundApiClient.getEvents(1000, 0),
      fundApiClient.getRiskMonitor(),
    ]);
    if (d.status === "fulfilled") { setDesk(d.value); setErr(null); }
    else { setDesk(null); setErr(d.reason instanceof Error ? d.reason.message : "unreachable"); }
    setPending(p.status === "fulfilled" ? (p.value.pending || []) : null);
    setEvents(ev.status === "fulfilled" ? (ev.value.events || []) : null);
    if (rk.status === "fulfilled") { setRisk(rk.value); setRiskErr(false); }
    else { setRisk(null); setRiskErr(true); }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  /** The ranked queue. Orders and recommendations in ONE order, because the
   *  CEO's attention is one queue however many endpoints it came from. The
   *  `?? []` fallbacks live INSIDE the memos — a fresh array identity in the
   *  dependency list re-ranks on every render (lint: exhaustive-deps). */
  const ranked = useMemo(
    () => rankDeskItems([
      ...orderItems(pending ?? []),
      ...recItems(desk?.open_recommendations ?? [], desk?.runs ?? []),
    ]),
    [pending, desk],
  );
  /* Two queues, not one list (CDO D4). "Awaiting your decision" is the CEO's
     actual work; "decided, awaiting execution" is a promise the firm has made
     and not yet kept. Counting them together meant a desk where everything had
     been decided read exactly like one where nothing had. */
  const split = useMemo(() => splitDeskItems(ranked), [ranked]);
  const gap = useMemo(() => moneyGap(split.awaitingDecision), [split]);
  const memos = useMemo(() => cooMemos(desk?.runs ?? [], memoParts), [desk]);
  const velocity = useMemo(() => decisionVelocity(events, new Date()), [events]);

  const orders = split.awaitingDecision.filter((i) => i.kind === "order");
  const recItemsRanked = split.awaitingDecision.filter((i) => i.kind === "recommendation");
  const decidedItems = split.awaitingExecution;
  const halted = risk?.halted === true;

  return (
    <div className="min-h-screen bg-[var(--kt-bg)] text-[var(--kt-text)]">
      <StudioHeader subtitle="The CEO's desk — everything awaiting your click" />
      <div className={KT.container}>
        <header className="mb-7 flex items-center gap-4">
          <SeatFace actor="ceo" size={64} />
          <div>
            <p className={KT.label}>Krypton Fund · the corner office</p>
            <h1 className="text-2xl font-medium tracking-tight">Neelesh · CEO</h1>
            {/* The headline count: ONLY what awaits a decision. Anything already
                decided is reported beside it, not inside it. */}
            <p className={`mt-1 text-sm ${KT.body}`}>
              <span className="font-mono tabular-nums text-[var(--kt-text-strong)]">
                {desk === null ? "unknown" : split.awaitingDecision.length}
              </span>{" "}
              awaiting your decision
              {desk !== null && decidedItems.length > 0 && (
                <span className={KT.muted}>
                  {" · "}
                  <span className="font-mono tabular-nums">{decidedItems.length}</span>{" "}
                  decided, awaiting execution
                </span>
              )}
              <CooTriageChip load={desk?.desk_load} />
            </p>
            <p className={`mt-0.5 text-xs ${KT.muted}`}>
              decisions recorded{" "}
              <span className="font-mono tabular-nums">
                {velocity.today ?? "— (event log unreadable, not zero)"}
              </span>{" "}
              today
              {velocity.week != null && (
                <> · <span className="font-mono tabular-nums">{velocity.week}</span> this week</>
              )}
              {" "}· <Link href="/clark/studio/desk" className={`${KT.accent} hover:underline`}>back to the floor</Link>
            </p>
          </div>
        </header>

        {err && (
          <div className={`${KT.card} mb-6 flex items-start gap-2 border-[var(--kt-warn)]`}>
            <AlertTriangle size={15} className="mt-0.5 text-[var(--kt-warn)]" />
            <p className="text-sm">The desk could not be read — what waits on you is unknown, not empty. {err}</p>
          </div>
        )}

        {/* ── 0 · THE HALT ─────────────────────────────────────────────────
            Only when engaged. It changes what approving on this page does, so
            it goes above the queue — and it NAMES the resume control rather
            than being one. Resuming the fund from a summary screen, two
            clicks from where the reason lives, is not a control this desk
            should offer. */}
        {halted && (
          <div className={`${KT.card} mb-6 flex flex-wrap items-start gap-2 border-[var(--kt-down)]`}>
            <OctagonX size={16} className="mt-0.5 shrink-0 text-[var(--kt-down)]" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-[var(--kt-down)]">Trading is halted.</p>
              <p className={`mt-0.5 text-sm ${KT.body}`}>
                Buys are blocked; sells still go through, so the exits below remain
                approvable. Resume is manual and lives on{" "}
                <Link href="/clark/studio" className={`${KT.accent} hover:underline`}>Monitor</Link>,
                in the halt control beside the risk limits — deliberately not here, next
                to the reason it was raised.
              </p>
              {(risk?.alarms ?? []).filter((a) => a.severity === "critical").length > 0 && (
                <p className={`mt-1 text-[11px] ${KT.muted}`}>
                  {(risk?.alarms ?? [])
                    .filter((a) => a.severity === "critical")
                    .map((a) => a.message)
                    .join(" · ")}
                </p>
              )}
            </div>
          </div>
        )}
        {riskErr && (
          <div className={`${KT.card} mb-6 flex items-start gap-2 border-[var(--kt-warn)]`}>
            <AlertTriangle size={15} className="mt-0.5 text-[var(--kt-warn)]" />
            <p className="text-sm">
              The risk monitor is unreadable, so whether the fund is halted is unknown —
              not &ldquo;running normally&rdquo;.
            </p>
          </div>
        )}

        {/* ── 1 · THE COO'S BATCH MEMOS ────────────────────────────────────
            The intended top of this page once triage is flowing: the CEO
            decides batches, not items. */}
        <section className="mb-8">
          <p className={`${KT.label} mb-2 flex items-center gap-2`}>
            <SeatFace actor="coo" size={16} decorative /> Vishesh&apos;s batch memos
          </p>
          {/* Three states, not two. An unread desk rendering an EMPTY section
              is the absence-as-value error with the sentence removed — the
              heading alone reads as "no memos on file". Caught on the
              dead-spine pass, 2026-08-20. */}
          {desk === null ? (
            <p className={`text-sm ${KT.sev.warn}`}>
              Unreadable — whether the COO has filed a memo is unknown, not none.
            </p>
          ) : memos.length === 0 ? (
            <p className={`text-sm ${KT.muted}`}>
              No triage on file. The COO has not run — the queue below is unbatched, which
              is the state this seat exists to end.
            </p>
          ) : (
            <div className="space-y-1.5">
              {memos.map((m) => (
                <div key={m.runId} className={`${KT.card} p-3`}>
                  <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <span className={`font-mono text-[10px] tabular-nums ${KT.muted}`}>
                      {m.at ? m.at.slice(0, 10) : "undated"}
                    </span>
                    <span className="min-w-0 flex-1 text-[13px] font-medium leading-snug">
                      {m.headline || (
                        <span className={KT.sev.warn}>
                          filed no verdict — the memo exists, its conclusion was not recorded
                        </span>
                      )}
                    </span>
                    <span className={`font-mono text-[10px] tabular-nums ${
                      m.openRecCount > 0 ? "text-[var(--kt-accent)]" : KT.muted}`}>
                      {m.openRecCount} of {m.recCount} still open
                    </span>
                  </div>
                  {m.rest && (
                    <p className={`mt-1 text-[12px] leading-relaxed ${KT.body}`}>{m.rest}</p>
                  )}
                  <p className={`mt-1.5 font-mono text-[10px] ${KT.muted}`}>
                    {m.artifactPath ?? "no artifact filed on this run"}
                    {" · "}
                    <Link href="/clark/studio/desk/coo" className={`${KT.accent} hover:underline`}>
                      open the COO&apos;s desk
                    </Link>
                  </p>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* ── 2 · ORDERS ───────────────────────────────────────────────────
            First in the ranked queue by construction: they are the only items
            that carry a dollar figure AND the only irreversible ones. */}
        <section className="mb-8">
          <p className={`${KT.label} mb-2`}>Orders awaiting your approval</p>
          {pending === null ? (
            <p className={`text-sm ${KT.sev.warn}`}>
              The approval queue is unreadable — anything waiting is still waiting.
            </p>
          ) : orders.length === 0 ? (
            <p className={`text-sm ${KT.muted}`}>Nothing pending at the venue.</p>
          ) : (
            <div className="space-y-1.5">
              {orders.map((item) => {
                const o = item.order!;
                const m = memoParts(o.rationale);
                const age = o.age_minutes;
                const expiresIn = age != null ? Math.max(0, 120 - age) : null;
                return (
                  <div key={item.key}
                       className={`${KT.card} flex flex-wrap items-baseline gap-x-3 gap-y-1 p-3 text-sm`}>
                    <span className="font-semibold uppercase">{o.side}</span>
                    <span className="font-mono tabular-nums">{o.qty}</span>
                    <span className="font-semibold">{o.symbol}</span>
                    {/* The ranking key, shown. A queue that sorts by a number
                        it does not display is asking to be trusted blind. */}
                    <span className="font-mono text-[11px] tabular-nums text-[var(--kt-text-strong)]">
                      {item.moneyUsd == null
                        ? <span className={KT.sev.warn}>notional not previewed</span>
                        : money(item.moneyUsd)}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-[12px]">{m.headline}</span>
                    <span className={`font-mono text-[10px] tabular-nums ${
                      expiresIn != null && expiresIn < 30 ? "text-[var(--kt-warn)]" : KT.muted}`}>
                      {expiresIn != null
                        ? `expires in ~${Math.round(expiresIn)}m`
                        : "age unknown"}
                    </span>
                  </div>
                );
              })}
              <p className={`text-[11px] italic ${KT.muted}`}>
                Approve and decline live on <Link href="/clark/studio" className={`${KT.accent} hover:underline`}>Monitor</Link> — one approval surface, deliberately.
              </p>
            </div>
          )}
        </section>

        {/* ── 3 · RECOMMENDATIONS, RANKED ──────────────────────────────────── */}
        <section className="mb-8">
          <p className={`${KT.label} mb-2`}>
            {/* A count folded from an unread desk is a zero nobody measured. */}
            Recommendations awaiting your decision ({desk === null ? "unknown" : recItemsRanked.length})
          </p>
          <p className={`mb-2 text-xs leading-relaxed ${KT.muted}`}>
            Ranked money → reversibility → staleness.{" "}
            {gap.unpriced > 0 && (
              <>
                <span className={KT.sev.warn}>
                  {gap.unpriced} of {gap.priced + gap.unpriced} items carry no money figure
                </span>{" "}
                — <code>money_at_stake</code> is optional on a recommendation and these
                seats stated none, so they are ranked on the two remaining keys rather than
                on a number read out of their prose. Reversibility is derived from each
                item&apos;s kind and shown beside it.
              </>
            )}
          </p>
          {desk === null ? (
            <p className={`text-sm ${KT.sev.warn}`}>
              Unreadable — the bench may be owed decisions. This is not an empty queue.
            </p>
          ) : recItemsRanked.length === 0 ? (
            <p className={`text-sm ${KT.muted}`}>Nothing awaiting you — the bench owes you no decisions right now.</p>
          ) : null}
          <div className="space-y-1.5">
            {recItemsRanked.map((item) => (
              <RankedRec key={item.key} item={item} onDecide={load} />
            ))}
          </div>
        </section>

        {/* ── 4 · DECIDED, AWAITING EXECUTION ──────────────────────────────
            Still on the desk, deliberately: a decision that never executes is a
            decision that did not happen, and the CEO is the only person who can
            see that it has stalled. NOT counted in the headline — it is not work
            to do, it is work owed. */}
        {desk !== null && decidedItems.length > 0 && (
          <section className="mb-8">
            <p className={`${KT.label} mb-2`}>
              Decided, awaiting execution ({decidedItems.length})
            </p>
            <p className={`mb-2 text-xs leading-relaxed ${KT.muted}`}>
              You decided these; they are the CTO&apos;s to stage through the ordinary
              propose path. They are listed so a decision cannot go quiet — but they
              are not counted above, because nothing here is waiting on you.
            </p>
            <div className="space-y-1.5">
              {decidedItems.map((item) => (
                <div key={item.key} className={`${KT.card} p-3`}>
                  <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.accent}`}>
                      {item.rec?.status}
                    </span>
                    <span className="min-w-0 flex-1 text-[13px] leading-snug">
                      {item.rec?.text}
                    </span>
                    <span className={`font-mono text-[10px] ${KT.muted}`}>
                      {item.rec?.seat}
                    </span>
                  </div>
                  <p className={`mt-0.5 font-mono text-[10px] ${KT.muted}`}>
                    {item.rec?.decided_by
                      ? `decided by ${item.rec.decided_by}${item.rec.decided_at ? ` · ${fmtAt(item.rec.decided_at)}` : ""}`
                      : "decided — the decision event recorded no actor"}
                  </p>
                </div>
              ))}
            </div>
          </section>
        )}

        <p className={`text-[11px] italic leading-relaxed ${KT.muted}`}>
          Folded from {events?.length ?? 0} spine events
          {events === null && " — the event log could not be read, so the decision counts above are absent, not zero"}
          {events !== null && velocity.oldestSeen &&
            ` back to ${fmtAt(velocity.oldestSeen)}; the endpoint caps at 1000 rows, so anything older is outside this view rather than quiet`}
          .
        </p>
      </div>
    </div>
  );
}

/** A ranked recommendation: the existing RecRow, plus the keys it was ranked
 *  on, so the ordering is auditable from the page itself. */
function RankedRec({ item, onDecide }: {
  item: DeskItem;
  onDecide: () => Promise<void> | void;
}) {
  const tone =
    item.reversibility === "hard" ? "text-[var(--kt-warn)]"
      : item.reversibility === "unclassified" ? "text-[var(--kt-warn)]"
        : KT.muted;
  return (
    <div>
      <RecRow r={item.rec!} onDecide={onDecide} />
      <p className={`mt-0.5 flex flex-wrap gap-x-3 pl-3 font-mono text-[10px] ${KT.muted}`}>
        <span className={tone}>
          {item.reversibility === "unclassified"
            ? `kind "${item.rec?.kind ?? "none"}" is unclassified — ranked as if hard to undo`
            : `${item.reversibility} to undo`}
        </span>
        <span>
          {item.waitingSince
            ? `waiting since ${fmtAt(item.waitingSince)}`
            : "undated — its run recorded no resolve time"}
        </span>
      </p>
    </div>
  );
}
