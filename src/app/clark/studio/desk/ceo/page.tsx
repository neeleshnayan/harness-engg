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
  CooMemo, DeskItem, QueuedAsk, asksForCeo, cooMemos, decisionVelocity,
  moneyGap, orderItems, queuedAsks, rankDeskItems, recItems, splitDeskItems,
} from "../execDesk";
import {
  OfficerQueue, hasContent, officerDesk,
} from "../officerQueues";
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

  /* The by-kind split moved INTO each officer section (2026-08-21): orders and
     recommendations are now separated per queue rather than page-wide. */
  const decidedItems = split.awaitingExecution;
  const halted = risk?.halted === true;

  /* Seat-filed and human-filed ASKS. Found live 2026-08-21: these rendered only
     on the CTO console, so this page read "0 awaiting you" while `desk_load`
     counted 2 — the CEO could not see, let alone click, items that were waiting
     on the CEO. Kept as their own section rather than folded into `ranked`,
     because an ask is not priced and not reversibility-classified, and pushing
     it through a money-first ranking would give it a position it has not
     earned. It IS counted in the headline, because it does await a decision. */
  const asks = useMemo(
    () => asksForCeo(queuedAsks(desk?.requests ?? [])), [desk]);

  /* The four queues (CEO, 2026-08-21). The headline count comes from HERE and
     not from the flat split, because the two disagree by design: Donna's notes
     are in the desk but are not decisions, and counting them would make a day
     of pure observations read as a backlog. */
  const officers = useMemo(
    () => officerDesk({
      awaitingDecision: split.awaitingDecision,
      awaitingExecution: split.awaitingExecution,
      memos,
      asks,
    }),
    [split, memos, asks],
  );
  const awaitingCount = officers.awaitingTotal;

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
                {desk === null ? "unknown" : awaitingCount}
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

        {/* ── FOUR QUEUES, BY PERSON ───────────────────────────────────────
            CEO verbatim, 2026-08-21: "my desk should have 4 queues -> Vishesh,
            Donna, Fable and Others segregated by team member name."

            The routing is in ../officerQueues.ts with tests, for the same
            reason the RANKING is: an attribution derived inline in JSX cannot
            be checked, and a queue that mis-attributes is worse than an
            unattributed one because the CEO would trust the label.

            Order within each queue is untouched — money → reversibility →
            staleness, exactly as before. Whose desk an item came off says who
            is asking, not how urgent it is. */}
        {desk === null ? (
          <section className="mb-8">
            <p className={`${KT.label} mb-2`}>Your queues</p>
            <p className={`text-sm ${KT.sev.warn}`}>
              The desk is unreadable — every queue below is UNKNOWN, not empty.
              Anything waiting is still waiting.
            </p>
          </section>
        ) : (
          officers.all.map((q) => (
            <OfficerSection
              key={q.id}
              q={q}
              pendingUnreadable={pending === null}
              gap={gap}
              onChanged={load}
            />
          ))
        )}

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

/**
 * ONE officer's queue: their face, their name, what they are owed.
 *
 * Each queue renders only what that officer actually produces — memos for
 * Vishesh, notes and suggestions for Donna, orders and asks for Fable, the
 * bench grouped by seat for Others. The empty states are per-officer and say
 * something true about that person rather than reusing one generic sentence:
 * "Donna has not filed today" and "nothing pending at the venue" are different
 * facts and a shared string would flatten them.
 */
function OfficerSection({ q, pendingUnreadable, gap, onChanged }: {
  q: OfficerQueue;
  pendingUnreadable: boolean;
  gap: { priced: number; unpriced: number };
  onChanged: () => Promise<void> | void;
}) {
  const orders = q.awaiting.filter((i) => i.kind === "order");
  const recs = q.awaiting.filter((i) => i.kind === "recommendation");

  return (
    <section className="mb-8">
      <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1">
        {q.seat ? <SeatFace actor={q.seat} size={22} decorative /> : null}
        <span className="text-[15px] font-medium tracking-tight">{q.label}</span>
        <span className={`font-mono tabular-nums text-[11px] ${
          q.awaitingCount > 0 ? "text-[var(--kt-accent)]" : KT.muted}`}>
          {q.awaitingCount} awaiting you
        </span>
        {q.decided.length > 0 && (
          <span className={`font-mono tabular-nums text-[10px] ${KT.muted}`}>
            · {q.decided.length} decided, listed at the foot of the page
          </span>
        )}
        {q.seat && (
          <Link href={`/clark/studio/desk/${q.seat}`}
                className={`ml-auto text-[11px] ${KT.accent} hover:underline`}>
            open their desk
          </Link>
        )}
      </div>
      <p className={`mb-2 text-xs ${KT.muted}`}>{q.role}</p>

      {/* ---- Vishesh: the batch memos ---- */}
      {q.id === "vishesh" && (
        q.memos.length === 0 ? (
          <p className={`mb-2 text-sm ${KT.muted}`}>
            No triage on file. The COO has not run — the queues below are
            unbatched, which is the state this seat exists to end.
          </p>
        ) : (
          <div className="mb-2 space-y-1.5">
            {q.memos.map((m) => <MemoCard key={m.runId} m={m} />)}
          </div>
        )
      )}

      {/* ---- Fable: orders ---- */}
      {q.id === "fable" && (
        pendingUnreadable ? (
          <p className={`mb-2 text-sm ${KT.sev.warn}`}>
            The approval queue is unreadable — anything waiting is still waiting.
          </p>
        ) : orders.length === 0 ? (
          <p className={`mb-2 text-sm ${KT.muted}`}>Nothing pending at the venue.</p>
        ) : (
          <div className="mb-2 space-y-1.5">
            {orders.map((item) => <OrderRow key={item.key} item={item} />)}
            <p className={`text-[11px] italic ${KT.muted}`}>
              Approve and decline live on{" "}
              <Link href="/clark/studio" className={`${KT.accent} hover:underline`}>Monitor</Link>
              {" "}— one approval surface, deliberately.
            </p>
          </div>
        )
      )}

      {/* ---- Fable: the seat-filed asks ---- */}
      {q.id === "fable" && q.asks.length > 0 && (
        <div className="mb-2 space-y-1.5">
          <p className={`text-xs leading-relaxed ${KT.muted}`}>
            A seat, or a human, has asked the desk for work. Approving is an
            ENDORSEMENT and not a trigger — the CTO fires the dispatch, and no
            agent runs until a human does. Declining is terminal and takes a
            written reason.
          </p>
          {q.asks.map((a) => <AskRow key={a.requestId} ask={a} onDecided={onChanged} />)}
        </div>
      )}

      {/* ---- Donna: notes, deliberately WITHOUT decision buttons ---- */}
      {q.id === "donna" && q.notes.length > 0 && (
        <div className="mb-2 space-y-1.5">
          <p className={`text-xs leading-relaxed ${KT.muted}`}>
            Observations, to be READ rather than decided — the CTO marks them
            noted. They carry no accept/reject and are not counted above, because
            they are not work you owe anyone.
          </p>
          {q.notes.map((item) => <NoteRow key={item.key} item={item} />)}
        </div>
      )}

      {/* ---- Others: grouped by seat ---- */}
      {q.id === "others" && q.groups.length > 0 && (
        <div className="space-y-4">
          {q.groups.map((g) => (
            <div key={g.seat}>
              <p className={`${KT.label} mb-1.5 flex items-center gap-2`}>
                <SeatFace actor={g.seat} size={14} decorative />
                {g.seat} ({g.items.length})
              </p>
              <div className="space-y-1.5">
                {g.items.map((item) => (
                  <RankedRec key={item.key} item={item} onDecide={onChanged} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ---- everyone else's recommendations ---- */}
      {q.id !== "others" && recs.length > 0 && (
        <div className="space-y-1.5">
          {recs.map((item) => (
            <RankedRec key={item.key} item={item} onDecide={onChanged} />
          ))}
        </div>
      )}

      {/* ---- nothing at all ----
           PRESENT TENSE, deliberately. "Donna has filed nothing" reads as
           "never filed"; what is true is that nothing of hers is on the desk
           RIGHT NOW — she has filed before and every item was marked noted.
           The same distinction the rest of this page draws between absent,
           empty and unknown. */}
      {!hasContent(q) && (
        <p className={`text-sm ${KT.muted}`}>
          {q.id === "donna"
            ? "Nothing of Donna's is on your desk right now. Her daily lands here when she runs at end of day; anything she filed earlier has been marked noted."
            : q.id === "vishesh"
              ? "Nothing of the COO's is on your desk right now."
              : q.id === "fable"
                ? "Nothing staged at the venue, and no bench asks awaiting you."
                : "The bench owes you no decisions right now."}
        </p>
      )}

      {q.id === "others" && gap.unpriced > 0 && q.awaitingCount > 0 && (
        <p className={`mt-2 text-xs leading-relaxed ${KT.muted}`}>
          <span className={KT.sev.warn}>
            {gap.unpriced} of {gap.priced + gap.unpriced} items carry no money figure
          </span>{" "}
          — <code>money_at_stake</code> is optional on a recommendation and these
          seats stated none, so they are ranked on the two remaining keys rather
          than on a number read out of their prose.
        </p>
      )}
    </section>
  );
}

/** One COO batch memo. Extracted verbatim from the old section 1. */
function MemoCard({ m }: { m: CooMemo }) {
  return (
    <div className={`${KT.card} p-3`}>
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
      {m.rest && <p className={`mt-1 text-[12px] leading-relaxed ${KT.body}`}>{m.rest}</p>}
      <p className={`mt-1.5 font-mono text-[10px] ${KT.muted}`}>
        {m.artifactPath ?? "no artifact filed on this run"}
      </p>
    </div>
  );
}

/** One pending order. Extracted verbatim from the old section 2. */
function OrderRow({ item }: { item: DeskItem }) {
  const o = item.order!;
  const m = memoParts(o.rationale);
  const age = o.age_minutes;
  const expiresIn = age != null ? Math.max(0, 120 - age) : null;
  return (
    <div className={`${KT.card} flex flex-wrap items-baseline gap-x-3 gap-y-1 p-3 text-sm`}>
      <span className="font-semibold uppercase">{o.side}</span>
      <span className="font-mono tabular-nums">{o.qty}</span>
      <span className="font-semibold">{o.symbol}</span>
      {/* The ranking key, shown. A queue that sorts by a number it does not
          display is asking to be trusted blind. */}
      <span className="font-mono text-[11px] tabular-nums text-[var(--kt-text-strong)]">
        {item.moneyUsd == null
          ? <span className={KT.sev.warn}>notional not previewed</span>
          : money(item.moneyUsd)}
      </span>
      <span className="min-w-0 flex-1 truncate text-[12px]">{m.headline}</span>
      <span className={`font-mono text-[10px] tabular-nums ${
        expiresIn != null && expiresIn < 30 ? "text-[var(--kt-warn)]" : KT.muted}`}>
        {expiresIn != null ? `expires in ~${Math.round(expiresIn)}m` : "age unknown"}
      </span>
    </div>
  );
}

/**
 * One of Donna's NOTES — read-only by construction.
 *
 * No accept/reject, deliberately and per her seat definition: a note "asks to
 * be READ, not decided". The CEO's own words on the alternative: "this seems
 * more like a note and I don't know what to accept". Rendering buttons here
 * would ask for a decision that means nothing.
 */
function NoteRow({ item }: { item: DeskItem }) {
  const r = item.rec!;
  return (
    <div className={`${KT.card} p-3`}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        {/* The kind is only worth printing when it says something the word
            "note" does not — `note · note` is noise. Her pre-vocabulary kinds
            (record_keeping, org_observation) DO say something and are kept. */}
        <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
          {r.kind && r.kind !== "note" ? `note · ${r.kind}` : "note"}
        </span>
        <span className="min-w-0 flex-1 text-[13px] leading-snug">{r.text}</span>
      </div>
      <p className={`mt-1 font-mono text-[10px] ${KT.muted}`}>
        read-only — the CTO marks it noted
      </p>
    </div>
  );
}

/**
 * ONE queued ask, in whichever of its four states it is in.
 *
 * Approve carries the guard's confirm echo (the client derives it from the
 * rendered id — guard v1). Decline deliberately does NOT: declines sit outside
 * the guard on the spine, exactly like order declines, because the guard exists
 * to stop an accidental YES and making a NO harder to give than a YES is the
 * wrong asymmetry on a control whose safe direction is refusal.
 *
 * The actor is the page's existing `ceo` desk convention (faces.ts), which is
 * this console's identity for every decision on it — the same one the approve
 * and decline buttons above already use.
 */
function AskRow({ ask, onDecided }: {
  ask: QueuedAsk; onDecided: () => Promise<void> | void;
}) {
  const [busy, setBusy] = useState<"approve" | "decline" | null>(null);
  const [declining, setDeclining] = useState(false);
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const act = async (what: "approve" | "decline") => {
    setBusy(what);
    setErr(null);
    try {
      if (what === "approve") {
        await fundApiClient.approveDeskRequest(ask.requestId, { actor: "ceo" });
      } else {
        await fundApiClient.declineDeskRequest(ask.requestId, reason.trim(), "ceo");
      }
      setDeclining(false);
      setReason("");
      await onDecided();
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      setErr(detail ?? (e instanceof Error ? e.message : "the spine refused it"));
    } finally {
      setBusy(null);
    }
  };

  const stageTone =
    ask.stage === "declined" ? KT.muted
      : ask.stage === "cleared_to_trigger" ? KT.accent
        : "text-[var(--kt-warn)]";
  const stageLabel =
    ask.stage === "declined" ? "declined"
      : ask.stage === "cleared_to_trigger" ? "cleared — CTO will trigger"
        : "awaiting you";

  return (
    <div className={`${KT.card} p-3 ${ask.stage === "declined" ? "opacity-60" : ""}`}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${stageTone}`}>
          {stageLabel}
        </span>
        <span className="min-w-0 flex-1 text-[13px] leading-snug">
          {ask.subject || (
            <span className={KT.sev.warn}>
              this ask recorded no subject — unreadable, not empty
            </span>
          )}
        </span>
        <span className={`font-mono text-[10px] ${KT.muted}`}>
          {ask.actor || "unattributed"}
          {ask.seatFiled && " · seat"}
          {ask.serves ? ` → ${ask.serves}` : ""}
        </span>
      </div>
      {ask.note && <p className={`mt-1 text-[11px] ${KT.body}`}>{ask.note}</p>}
      <p className={`mt-0.5 font-mono text-[10px] ${KT.muted}`}>
        {ask.at ? `filed ${fmtAt(ask.at)}` : "undated — the request recorded no time"}
        {ask.stage === "cleared_to_trigger" && (
          ask.approvedBy
            ? ` · approved by ${ask.approvedBy}${ask.approvedAt ? ` · ${fmtAt(ask.approvedAt)}` : ""}`
            : " · approved — the approval event recorded no actor")}
        {ask.stage === "declined" && (
          ask.declinedBy
            ? ` · declined by ${ask.declinedBy}${ask.declinedAt ? ` · ${fmtAt(ask.declinedAt)}` : ""}`
            : " · declined — the decline event recorded no actor")}
      </p>
      {ask.stage === "declined" && (
        <p className={`mt-1 text-[11px] ${KT.muted}`}>
          {ask.declineReason
            ? `“${ask.declineReason}”`
            : "no reason was recorded with this decline — the reason is absent, not blank"}
        </p>
      )}
      {err && <p className={`mt-1.5 text-[11px] ${KT.down}`}>{err}</p>}

      {ask.stage === "awaiting_ceo" && !declining && (
        <div className="mt-2 flex flex-wrap gap-2">
          <button disabled={busy !== null} onClick={() => act("approve")}
                  className={`${KT.btn} disabled:opacity-40`}>
            {busy === "approve" ? "Approving…" : "Approve"}
          </button>
          <button disabled={busy !== null} onClick={() => setDeclining(true)}
                  className={`${KT.btnGhost} disabled:opacity-40`}>
            Decline…
          </button>
        </div>
      )}

      {ask.stage === "awaiting_ceo" && declining && (
        <div className={`mt-2 p-3 ${KT.inset}`}>
          <div className="text-[12px] font-medium">Decline this ask?</div>
          <textarea
            autoFocus
            rows={2}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Why? (mandatory — recorded verbatim, and the ask cannot be revived)"
            className="mt-2 w-full rounded border border-[var(--kt-border)] bg-transparent px-2 py-1.5 text-[12px] outline-none focus:border-[var(--kt-accent)]"
          />
          <div className="mt-2 flex gap-2">
            <button
              disabled={busy !== null || reason.trim().length === 0}
              onClick={() => act("decline")}
              className={`${KT.btnDanger} disabled:opacity-40`}
            >
              {busy === "decline" ? "Declining…" : "Yes, decline"}
            </button>
            <button disabled={busy !== null}
                    onClick={() => { setDeclining(false); setReason(""); setErr(null); }}
                    className={KT.btnGhost}>
              Cancel
            </button>
          </div>
          {reason.trim().length === 0 && (
            <p className={`mt-1.5 text-[11px] ${KT.muted}`}>
              A reason is required. The spine refuses a decline without one.
            </p>
          )}
        </div>
      )}
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
