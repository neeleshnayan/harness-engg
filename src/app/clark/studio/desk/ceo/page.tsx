"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AlertTriangle, OctagonX } from "lucide-react";
import {
  fundApiClient, ArchiveMemo, CeoDeskView, DeskView, PendingOrder,
  RiskMonitorResponse, SpineEvent,
} from "@/lib/fund_api";
import { KT } from "../../theme";
import { money } from "../../format";
import { StudioHeader } from "../../components/StudioHeader";
import { memoParts } from "../../memo";
import { SeatFace } from "../SeatFace";
import { fmtAt } from "../seatLib";
import {
  CooMemo, DeskItem, QueuedAsk, asksForCeo, contractDrift, cooMemos,
  decisionVelocity, memoDayLabel, moneyGap, orderItems, queuedAsks,
  rankCoverage, rankDeskItems, rankReason, recItems, splitDeskItems,
  unwrapMemoMarkdown,
} from "../execDesk";
import type { Decision, DecisionGroup } from "../decisionList";
import {
  countCheck, decisionList, foldedCounts, orderingHazard,
} from "../decisionList";
import { officerDesk } from "../officerQueues";
import { CooTriageChip, ProvenanceChip } from "../components";
import { cardStyle } from "../deskCardStyle";
import { ClarkMarkdown } from "../../components/ClarkMarkdown";
import { blockedRecs } from "../deskEngine";
import {
  BriefingsShelf, Fold, GreetingHeader, SupersessionNotice,
} from "../EngineViews";

/**
 * The CEO's desk — A DECISION LIST, and everything else behind a named door.
 *
 * RESTRUCTURED 2026-08-22 on the CEO's complaint ("since morning my desk has
 * stale; out of order and poorly designed stuff. Making my flow messy") and on
 * a measurement of the page it replaces. The previous version was honest, well
 * tested, and unusable, and the numbers say why — taken against the live
 * corpus replayed through the merged spine's own code:
 *
 *   | block                                    |     px |  chars | buttons |
 *   |------------------------------------------|-------:|-------:|--------:|
 *   | Vishesh — 3 COO memos, all "0 of N open" |    708 |  2,548 |       0 |
 *   | Donna — her daily, already read          |    951 |  3,052 |       0 |
 *   | **Fable — 23 asks, NONE awaiting him**   |**9,596**| 42,986 |      0 |
 *   | Others — the 3 actual decisions          |    754 |  2,642 |   **6** |
 *   | Decided, awaiting execution (103)        | 12,050 | 35,972 |       0 |
 *
 * **The first Accept button was 11,608px — 14.7 screenfuls — below his name,
 * behind 49,549 characters, and the three decisions he owed were 3% of a
 * 24,627px page.** The single largest block was a section headed "0 awaiting
 * you": 22 asks already cleared for the chair to fire, and one terminal
 * decline.
 *
 * THE FOUR RULES THIS PAGE NOW OBEYS:
 *
 *   1. **The first screenful is exactly N cards and nothing above them**,
 *      where N is the header number. `decisionList()` builds the cards FROM
 *      the officer desk's own queues, so the two numbers are one number by
 *      construction, and a test asserts it over ten shapes plus the live
 *      corpus. This desk has shipped one-quantity-computed-twice twice.
 *   2. **A batch is a GROUPING, not a card.** The COO's memo heads the rows it
 *      filed instead of sitting above them as 900 characters of prose the CEO
 *      has already read. That renders the 31→7 reduction rather than
 *      restating it.
 *   3. **A dated row is the only row that carries a chip, and it is always
 *      first.** One visual token, reserved for the one key that does not wait
 *      for a click.
 *   4. **Everything else is behind named disclosure at the foot** — and named
 *      is the operative word. Every folded section says what and how many is
 *      behind it before it is opened, and every row stays counted where it
 *      belongs. Disclosure is not concealment; a section labelled "more" would
 *      be concealment with a chevron.
 *
 * HIERARCHY FROM TYPE AND SPACE, NEVER COLOUR (the design brief, and the
 * specific defect it fixes here): every row used to render at 13px in one
 * tone, so a $750 armed short and a doc-indexing chore were visually
 * identical, and the previous page reached for the WARN colour to separate
 * them — which is hierarchy from colour, and puts an alarm tone on rows where
 * nothing is wrong. Reversibility now drives SIZE and SPACE (`cardStyle`
  * in deskCardStyle.ts); colour stays what the theme says it is — emerald for the fund,
 * violet for the machine, warn for a genuine warning.
 *
 * WHAT THIS PAGE STILL WILL NOT DO, unchanged: it does not price a
 * recommendation from its prose, it does not restate the drawdown (the RiskBar
 * owns "is anything broken"), and it does not offer a resume control.
 */
export default function CeoDeskPage() {
  const [desk, setDesk] = useState<DeskView | null>(null);
  const [pending, setPending] = useState<PendingOrder[] | null>(null);
  const [events, setEvents] = useState<SpineEvent[] | null>(null);
  const [risk, setRisk] = useState<RiskMonitorResponse | null>(null);
  const [riskErr, setRiskErr] = useState(false);
  /* Donna's short memo. `null` is UNREACHABLE, not "she filed nothing" — the
     endpoint's own `available: false` carries that, with one of five reasons. */
  const [memo, setMemo] = useState<ArchiveMemo | null>(null);
  const [memoErr, setMemoErr] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  /* The desk engine's fold: the greeting, the briefings shelf, and — the part
     that changes what this page may RENDER — every row carrying a live
     supersession edge. `null` is unreachable, and the page then says the
     lineage is UNKNOWN rather than drawing rows as though none were blocked. */
  const [engine, setEngine] = useState<CeoDeskView | null>(null);
  const [engineErr, setEngineErr] = useState(false);
  /* The client's own last visit, so the greeting can say what changed. Stamped
     by the BROWSER, never by the spine: a GET that writes is a GET that lies
     about being safe. Read once on mount, before this visit overwrites it. */
  const [since, setSince] = useState<string | null>(null);

  useEffect(() => {
    try {
      setSince(window.localStorage.getItem("kt.desk.ceo.lastVisit"));
      window.localStorage.setItem("kt.desk.ceo.lastVisit", new Date().toISOString());
    } catch {
      /* Private mode, or storage disabled. `since` stays null and the greeting
         says "no previous visit was supplied" — which is true, and is a
         different sentence from "nothing has changed". */
    }
  }, []);

  const load = useCallback(async () => {
    const [d, p, ev, rk, mm, en] = await Promise.allSettled([
      fundApiClient.getDesk(),
      fundApiClient.getPending(),
      fundApiClient.getEvents(1000, 0),
      fundApiClient.getRiskMonitor(),
      fundApiClient.getArchiveMemo(),
      fundApiClient.getCeoDesk(since, false),
    ]);
    if (d.status === "fulfilled") { setDesk(d.value); setErr(null); }
    else { setDesk(null); setErr(d.reason instanceof Error ? d.reason.message : "unreachable"); }
    setPending(p.status === "fulfilled" ? (p.value.pending || []) : null);
    setEvents(ev.status === "fulfilled" ? (ev.value.events || []) : null);
    if (rk.status === "fulfilled") { setRisk(rk.value); setRiskErr(false); }
    else { setRisk(null); setRiskErr(true); }
    if (mm.status === "fulfilled") { setMemo(mm.value); setMemoErr(false); }
    else { setMemo(null); setMemoErr(true); }
    if (en.status === "fulfilled") { setEngine(en.value); setEngineErr(false); }
    else { setEngine(null); setEngineErr(true); }
  }, [since]);

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  /* SUPERSEDED ROWS NEVER REACH A CARD.
     This page builds its cards from `/fund/desk`, which knows nothing about
     supersession — so without this filter it would render an Accept control
     the spine refuses with a 409. The R37 case is exactly that: a `staged`
     row whose premise dies at a named future event, sitting in a queue where
     it could be clicked after the event that made it wrong.
     Read from `blocked`, which the spine leaves UNCAPPED, and not from the
     matrix cells, which it caps at 25 apiece. */
  const blocked = useMemo(() => blockedRecs(engine), [engine]);
  const withdrawn = useMemo(
    () => (desk?.open_recommendations ?? []).filter(
      (r) => blocked.has(`${r.run_id}#${r.rec_id}`)),
    [desk, blocked]);
  const liveRecs = useMemo(
    () => (desk?.open_recommendations ?? []).filter(
      (r) => !blocked.has(`${r.run_id}#${r.rec_id}`)),
    [desk, blocked]);

  const ranked = useMemo(
    () => rankDeskItems([
      ...orderItems(pending ?? []),
      ...recItems(liveRecs, desk?.runs ?? []),
    ]),
    [pending, liveRecs, desk],
  );
  const split = useMemo(() => splitDeskItems(ranked), [ranked]);
  const memos = useMemo(() => cooMemos(desk?.runs ?? [], memoParts), [desk]);
  const velocity = useMemo(() => decisionVelocity(events, new Date()), [events]);
  const asks = useMemo(
    () => asksForCeo(queuedAsks(desk?.requests ?? [])), [desk]);

  const officers = useMemo(
    () => officerDesk({
      awaitingDecision: split.awaitingDecision,
      awaitingExecution: split.awaitingExecution,
      ownedElsewhere: split.ownedElsewhere,
      memos,
      asks,
    }),
    [split, memos, asks],
  );

  /* THE LIST. Built from the officer desk rather than from the payload, so the
     header number and the number of cards cannot disagree. */
  const list = useMemo(
    () => decisionList(officers, asks, desk?.runs ?? [], memoParts),
    [officers, asks, desk],
  );
  const folded = useMemo(
    () => foldedCounts(officers, asks, memo?.available === true),
    [officers, asks, memo],
  );
  const awaitingCount = officers.awaitingTotal;

  /* Do the header's number and the chip's number — eight pixels apart, from
     two different implementations — still agree? See `countCheck`. */
  const countDrift = countCheck({
    spineTotal: desk?.desk_load?.total,
    pageTotal: awaitingCount,
    divertedNotes: officers.donna.notes.length,
  });

  /* Coverage over the CARDS, not over the flat split — the sentence about what
     the ranking could not see must describe the rows on screen. */
  const cardItems = useMemo(
    () => list.all.flatMap((d) => (d.kind === "ask" ? [] : [d.item])), [list]);
  const gap = useMemo(() => moneyGap(cardItems), [cardItems]);
  const coverage = useMemo(() => rankCoverage(cardItems), [cardItems]);

  const halted = risk?.halted === true;
  const drift = contractDrift(desk?.desk_load?.contract_digest);

  return (
    <div className="min-h-screen bg-[var(--kt-bg)] text-[var(--kt-text)]">
      <StudioHeader subtitle="The CEO's desk — everything awaiting your click" />
      <div className={KT.container}>
        <header className="mb-6 flex items-center gap-4">
          <SeatFace actor="ceo" size={64} />
          <div>
            <p className={KT.label}>Krypton Fund · the corner office</p>
            <h1 className="text-2xl font-medium tracking-tight">Neelesh · CEO</h1>
            <p className={`mt-1 text-sm ${KT.body}`}>
              <span className="font-mono tabular-nums text-[var(--kt-text-strong)]">
                {desk === null ? "unknown" : awaitingCount}
              </span>{" "}
              awaiting your decision
              {/* The GROUP count, gated on there being more than one group —
                  not on there being a COO batch, which is what the first cut
                  did. Those are different conditions and the number rendered
                  was the group count either way, so a desk with three
                  unbatched groups said nothing while a desk with one batch
                  said "in 1 group". One group is not a grouping worth naming;
                  three are, batch or not. */}
              {desk !== null && list.groups.length > 1 && (
                <span className={KT.muted}>
                  {" · "}in{" "}
                  <span className="font-mono tabular-nums">{list.groups.length}</span>{" "}
                  groups
                  {list.batches > 0 && (
                    <>
                      {", "}
                      <span className="font-mono tabular-nums">{list.batches}</span>
                      {list.batches === 1 ? " a COO batch" : " of them COO batches"}
                    </>
                  )}
                </span>
              )}
              {desk !== null && folded.total > 0 && (
                <span className={KT.muted}>
                  {" · "}
                  <span className="font-mono tabular-nums">{folded.total}</span>{" "}
                  more on file, at the foot
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

        {/* ── THE GREETING ─────────────────────────────────────────────────
            CEO instruction (ticket cec27460, absorbed into the desk engine):
            each desk view opens with what changed since your last visit, what
            needs you, and what is on fire — GENERATED from the same folds the
            page renders, never hand-written. A hand-written "all quiet" would
            be the one line here nobody could falsify. */}
        <GreetingHeader view={engine} needsYou={desk === null ? null : awaitingCount} />
        {engineErr && (
          <div className={`${KT.card} mb-6 flex items-start gap-2 border-[var(--kt-warn)]`}>
            <AlertTriangle size={15} className="mt-0.5 shrink-0 text-[var(--kt-warn)]" />
            <p className="text-sm">
              The desk engine could not be read, so supersession lineage is
              UNKNOWN on this page — a withdrawn row could still be rendered
              below with its controls. The spine still refuses the click; the
              warning is that the page cannot warn you first.
            </p>
          </div>
        )}

        {err && (
          <div className={`${KT.card} mb-6 flex items-start gap-2 border-[var(--kt-warn)]`}>
            <AlertTriangle size={15} className="mt-0.5 text-[var(--kt-warn)]" />
            <p className="text-sm">The desk could not be read — what waits on you is unknown, not empty. {err}</p>
          </div>
        )}

        {/* ── THE HALT ─────────────────────────────────────────────────────
            The one thing that outranks the list, because it changes what a
            click on the list DOES. It names the resume control rather than
            being one: resuming the fund from a summary screen, two clicks from
            where the reason lives, is not a control this desk should offer. */}
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

        {/* ── CONTRACT DRIFT ───────────────────────────────────────────────
            The number on this page and the spine's own counter are two
            implementations of one question, and they have disagreed twice
            (11 vs 6, then 1 vs 0). A shared contract file, checked in to both
            repos, now pins them — and this says so when the spine is running
            against a different one. `drifted` is the real disagreement;
            `unverified` is a spine that sent no digest, which is NOT the same
            as agreement and must never render as it. */}
        {desk !== null && drift === "drifted" && (
          <div className={`${KT.card} mb-6 flex items-start gap-2 border-[var(--kt-warn)]`}>
            <AlertTriangle size={15} className="mt-0.5 shrink-0 text-[var(--kt-warn)]" />
            <p className="text-sm">
              This page and the spine were built against DIFFERENT routing
              contracts, so the count above may not mean what it says. The
              spine reports{" "}
              <code className="font-mono text-[11px]">
                {desk.desk_load?.rules_version ?? "no rules version"}
              </code>{" "}
              and a contract digest this build does not recognise.
            </p>
          </div>
        )}

        {desk !== null && countDrift && (
          <div className={`${KT.card} mb-6 flex items-start gap-2 border-[var(--kt-warn)]`}>
            <AlertTriangle size={15} className="mt-0.5 shrink-0 text-[var(--kt-warn)]" />
            <p className="text-sm">{countDrift}</p>
          </div>
        )}

        {/* ── 1 · THE DECISION LIST ────────────────────────────────────── */}
        {desk === null ? (
          <section className="mb-10">
            <p className={`text-sm ${KT.sev.warn}`}>
              The desk is unreadable, so what awaits you is UNKNOWN, not none.
              Anything waiting is still waiting.
            </p>
          </section>
        ) : awaitingCount === 0 ? (
          <section className="mb-10">
            <p className="text-[15px] leading-relaxed">Nothing awaits your decision.</p>
            <p className={`mt-1 text-sm ${KT.body}`}>
              That is a measurement of this moment, not of the firm:{" "}
              <span className="font-mono tabular-nums">{folded.total}</span>{" "}
              item{folded.total === 1 ? " is" : "s are"} on file at the foot of
              this page — decided work awaiting execution, open work owned by
              the chair or a seat, and reading. None of it needs a click from
              you.
            </p>
          </section>
        ) : (
          <section className="mb-10 space-y-7">
            {list.groups.map((g) => (
              <DecisionGroupBlock key={g.key} group={g} onChanged={load} />
            ))}
            <RankingNote gap={gap} coverage={coverage} batches={list.batches}
                         hazard={orderingHazard(list.all)} />
          </section>
        )}

        {/* ── 1b · THE BRIEFINGS SHELF ─────────────────────────────────────
            Seat memos reach the CEO DIRECTLY (CEO instruction 3: "COO reaches
            to me directly with you in CC"). Published at filing, stamped
            chair-unverified until the chair's parallel verification flips the
            badge. Folded, because reading is not a decision — but folded with
            its count, which is the difference between disclosure and
            concealment. */}
        <Fold title="Briefings — seat memos, direct to you"
              n={engine?.briefings ? engine.briefings.total : null}
              lede="Donna's dailies, Vishesh's triages, Grace's ledgers. The chair verifies in parallel and is CC, never a relay; a discrepancy found after publication becomes a visible correction chip, never a silent edit.">
          <BriefingsShelf shelf={engine?.briefings ?? null} />
        </Fold>

        {/* ── 1c · WITHDRAWN BY LINEAGE ────────────────────────────────────
            CEO instruction 5, verbatim: "where supersed happens; this r37
            withdraw and r39 acceptance fills the same pattern". These rows are
            NOT above, and that is the point: the server refuses their
            approval, so offering one would be a button that fails. They are
            here whole, with the event that kills the premise and the branch
            that revives it. */}
        {withdrawn.length > 0 && (
          <Fold title="Withdrawn by lineage — cannot be approved"
                n={withdrawn.length}
                defaultOpen
                lede="Each of these was replaced or killed by a later row. They are kept on the page with their lineage rather than deleted, because a row that vanishes is a row nobody can revive.">
            {/* KT.panel, not KT.card, on the rows below: `card` already
                carries p-5 and Tailwind resolves by stylesheet order, so a
                `p-3` written beside it is an invisible class. An existing test
                caught exactly this in the first cut of this block. */}
            <div className="space-y-2">
              {withdrawn.map((r) => (
                <div key={`${r.run_id}-${r.rec_id}`} className={`${KT.panel} p-3`}>
                  <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
                      {r.seat} · {r.status}
                    </span>
                    <span className="min-w-0 flex-1 text-[13px] leading-snug">
                      {r.text}
                    </span>
                  </div>
                  <SupersessionNotice
                    edge={blocked.get(`${r.run_id}#${r.rec_id}`) ?? null} />
                </div>
              ))}
            </div>
          </Fold>
        )}

        {/* ── 2 · EVERYTHING ELSE, BEHIND NAMED DOORS ───────────────────── */}
        {desk !== null && (
          <div className="space-y-2 border-t border-[var(--kt-border)] pt-6">
            <p className={`${KT.label} mb-1`}>On file — nothing here needs you</p>

            <Folded
              label="Decided by you, awaiting execution"
              count={folded.decided}
              blurb="You decided these; they are the chair's to stage through the ordinary propose path. They are listed so a decision cannot go quiet — and not counted above, because nothing here is waiting on you."
            >
              <div className="space-y-1.5">
                {officers.all.flatMap((q) => q.decided).map((item) => (
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
            </Folded>

            <Folded
              label="Open, and not yours"
              count={folded.elsewhere}
              blurb="Nobody has decided these and nobody is waiting on you for them — engineering tickets, seat-to-seat handoffs. Each names the actor it went to and why. They stay on this page so that taking them off your count does not take them off your screen."
            >
              <div className="space-y-1.5">
                {officers.all.flatMap((q) => q.elsewhere).map((item) => (
                  <div key={item.key} className={`${KT.card} p-3`}>
                    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                      <span
                        className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}
                        title={item.rec?.next_actor_why ?? undefined}
                      >
                        {item.nextActor ?? "unrouted"}
                      </span>
                      <span className="min-w-0 flex-1 text-[13px] leading-snug">
                        {item.rec?.text}
                      </span>
                      <span className={`font-mono text-[10px] ${KT.muted}`}>
                        {item.rec?.seat}
                      </span>
                    </div>
                    <p className={`mt-0.5 font-mono text-[10px] ${KT.muted}`}>
                      {item.rec?.next_actor_why
                        ?? "routed away from your desk; the spine stated no reason"}
                    </p>
                  </div>
                ))}
              </div>
            </Folded>

            <Folded
              label="Vishesh · the COO's triage memos"
              count={folded.memos}
              blurb="His batch memos, newest first. They are here rather than above the list because the list is now GROUPED by them — the reduction is rendered, not restated."
              seat="coo"
              emptyNote="the COO has not run, so the list above is unbatched — the state this seat exists to end"
            >
              <div className="space-y-1.5">
                {officers.vishesh.memos.map((m) => <MemoCard key={m.runId} m={m} />)}
              </div>
            </Folded>

            {/* The count includes HER MEMO when there is one. It read "0" on
                the first render while a filed daily sat behind the door — a
                door that understates what is behind it teaches a reader not to
                open it, which is concealment arrived at by arithmetic. */}
            <Folded
              label="Donna · her daily, and her notes"
              count={folded.donna}
              blurb="Her memo asks to be read, not decided. Notes carry no accept or reject and are not counted above, because they are not work you owe anyone."
              seat="secretary"
              alwaysOpenable
            >
              <DailyMemoCard memo={memo} unreachable={memoErr} />
              {officers.donna.notes.length > 0 && (
                <div className="mt-2 space-y-1.5">
                  {officers.donna.notes.map((item) => (
                    <NoteRow key={item.key} item={item} />
                  ))}
                </div>
              )}
            </Folded>

            <Folded
              label="Bench asks already settled"
              count={folded.settledAsks}
              blurb="Cleared asks are the chair's to fire; declined ones are terminal. Neither can be moved by a click of yours, which is why neither is on the list above — a queue of these headed '0 awaiting you' was the single largest block on the old page, at 9,596px."
              seat="cto"
            >
              <div className="space-y-1.5">
                {asks.filter((a) => a.stage !== "awaiting_ceo").map((a) => (
                  <AskRow key={a.requestId} ask={a} onDecided={load} />
                ))}
              </div>
            </Folded>
          </div>
        )}

        <p className={`mt-6 text-[11px] italic leading-relaxed ${KT.muted}`}>
          Folded from {events?.length ?? 0} spine events
          {events === null && " — the event log could not be read, so the decision counts above are absent, not zero"}
          {events !== null && velocity.oldestSeen &&
            ` back to ${fmtAt(velocity.oldestSeen)}; the endpoint caps at 1000 rows, so anything older is outside this view rather than quiet`}
          {desk !== null && drift === "unverified" &&
            ". The spine sent no routing-contract digest, so whether its counter and this page agree is UNVERIFIED — not confirmed"}
          .
        </p>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------- the list --- */

/**
 * ONE group of decisions, headed by the memo that proposed them.
 *
 * The heading is CHROME and the decisions are CONTENT, and the type says so:
 * the heading is a 10px mono label, each decision's first sentence is 14–16px.
 * The previous page inverted this — 900 characters of COO memo at 13px above
 * three decisions at 13px — which is how an already-read summary came to
 * outrank the thing it was summarising.
 */
function DecisionGroupBlock({ group, onChanged }: {
  group: DecisionGroup;
  onChanged: () => Promise<void> | void;
}) {
  /* Only rows the spine will actually accept: open recommendations. An order
     is approved on Monitor and an ask has its own control, so neither can be
     part of a group accept — offering one would be a button that silently
     skipped half of what it sat under. */
  const bulk = group.decisions.flatMap(
    (d) => (d.kind === "rec" && d.item.rec?.status === "open" ? [d.item] : []));

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-baseline gap-x-2 gap-y-1">
        {group.seat && <SeatFace actor={group.seat} size={16} decorative />}
        {group.isBatch && (
          /* The ONE place a batch is named as such. Not a colour — a word. */
          <span className={`${KT.label} text-[var(--kt-accent)]`}>batch</span>
        )}
        {/* NOT `KT.label`. That style is uppercase at 0.18em tracking, which
            is right for a two-word label and unreadable for a sentence — the
            first render put a 197-character dispatch brief through it. Small,
            dim, sentence case: chrome that can still be read. */}
        <span className={`min-w-0 flex-1 text-[11px] leading-snug ${KT.muted}`}>
          {group.heading ?? (
            <span className={KT.sev.warn}>
              the run that filed {group.decisions.length === 1 ? "this" : "these"} is
              outside the payload&apos;s 25-run window — heading unknown, not absent
            </span>
          )}
        </span>
        <span className={`font-mono tabular-nums text-[10px] ${KT.muted}`}>
          {group.decisions.length} to decide
        </span>
      </div>

      <div className="space-y-2">
        {group.decisions.map((d) => (
          <DecisionCard key={d.key} d={d} onChanged={onChanged} />
        ))}
      </div>

      {bulk.length > 1 && (
        <GroupAccept items={bulk} isBatch={group.isBatch} onChanged={onChanged} />
      )}
    </div>
  );
}

/** One decision: the first sentence, why it is where it is, and the buttons. */
function DecisionCard({ d, onChanged }: {
  d: Decision; onChanged: () => Promise<void> | void;
}) {
  if (d.kind === "ask") return <AskRow ask={d.ask} onDecided={onChanged} />;
  if (d.kind === "order") return <OrderCard item={d.item} />;
  return <RecCard item={d.item} onDecide={onChanged} />;
}

/**
 * THE DATE CHIP — the only chip on any row, deliberately.
 *
 * One visual token, reserved for the one ranking key that does not wait for a
 * click: a dated commitment happens whether or not anybody decides. Giving
 * money or reversibility a chip too would spend the token on things the type
 * scale already says, and a page where every row has a badge is a page with no
 * badges.
 */
function DueChip({ date }: { date: string }) {
  return (
    <span className={`${KT.chip} shrink-0 font-mono tabular-nums`}>
      due {date}
    </span>
  );
}

function RecCard({ item, onDecide }: {
  item: DeskItem; onDecide: () => Promise<void> | void;
}) {
  const r = item.rec!;
  const parts = memoParts(r.text);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const scale = cardStyle(item.reversibility);

  const decide = async (status: "accepted" | "rejected") => {
    setBusy(true);
    setErr(null);
    try {
      await fundApiClient.decideRecommendation(r.run_id, r.rec_id,
                                               { status, actor: "ceo" });
      await onDecide();
    } catch (e) {
      // A decision that failed must not look like a decision that landed.
      setErr(e instanceof Error ? e.message : "the spine did not record it");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={scale.container}>
      <div className="flex flex-wrap items-start gap-x-3 gap-y-2">
        {item.dueDate && <DueChip date={item.dueDate} />}
        <p className={`min-w-0 flex-1 ${scale.text}`}>{parts.headline}</p>
        <span className="flex shrink-0 gap-2">
          <button type="button" disabled={busy} onClick={() => decide("accepted")}
                  className={`${KT.btn} disabled:opacity-40`}>
            {busy ? "…" : "Accept"}
          </button>
          <button type="button" disabled={busy} onClick={() => decide("rejected")}
                  className={`${KT.btnGhost} hover:border-[var(--kt-down)] hover:text-[var(--kt-down)] disabled:opacity-40`}>
            Reject
          </button>
        </span>
      </div>

      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
        <ProvenanceChip kind="agent" seat={r.seat} recId={r.rec_id} />
        {/* ALWAYS MUTED, and this line was amber until I looked at the page.
            `reversibilityOf`'s own docstring already carries the lesson: the
            amber "unclassified kind" sentence "fired on almost every row of
            his own queue — honest, and noise, and noise on every row is how a
            warning stops being read". It fired on two of three rows here. The
            words say "unclassified kind — ranked as if hard to undo" perfectly
            well without a colour, and the design brief is explicit that
            hierarchy comes from type and space. */}
        <span className={`min-w-0 flex-1 font-mono text-[10px] ${KT.muted}`}>
          {rankReason(item)}
        </span>
        {parts.rest && (
          <button type="button" onClick={() => setOpen((v) => !v)}
                  className={`font-mono text-[10px] ${KT.accent} hover:underline`}>
            {open ? "− less" : "+ the rest"}
          </button>
        )}
      </div>

      {open && parts.rest && (
        <p className={`mt-2 border-t border-[var(--kt-border)] pt-2 text-[12px] leading-relaxed ${KT.body}`}>
          {parts.rest}
        </p>
      )}
      {err && (
        <p className={`mt-1.5 text-[11px] ${KT.down}`}>
          Not recorded: {err} — the recommendation is still open.
        </p>
      )}
    </div>
  );
}

/**
 * A pending order on the list.
 *
 * NO BUTTONS, deliberately and unchanged: approve and decline live on Monitor,
 * one approval surface. It is a CARD rather than a line because it is the only
 * irreversible thing on this page and the type scale says so — and because the
 * headline number counts it, so it must be one of the N.
 */
function OrderCard({ item }: { item: DeskItem }) {
  const o = item.order!;
  const m = memoParts(o.rationale);
  const age = o.age_minutes;
  const expiresIn = age != null ? Math.max(0, 120 - age) : null;
  const scale = cardStyle(item.reversibility);
  return (
    <div className={scale.container}>
      <div className="flex flex-wrap items-start gap-x-3 gap-y-2">
        <p className={`min-w-0 flex-1 ${scale.text}`}>
          <span className="font-semibold uppercase">{o.side}</span>{" "}
          <span className="font-mono tabular-nums">{o.qty}</span>{" "}
          <span className="font-semibold">{o.symbol}</span>
          {" — "}
          {item.moneyUsd == null
            ? <span className={KT.sev.warn}>notional not previewed</span>
            : <span className="font-mono tabular-nums">{money(item.moneyUsd)}</span>}
        </p>
        <Link href="/clark/studio" className={`${KT.btn} shrink-0`}>
          Approve on Monitor
        </Link>
      </div>
      {m.headline && (
        <p className={`mt-1.5 text-[12px] leading-relaxed ${KT.body}`}>{m.headline}</p>
      )}
      <p className={`mt-1.5 font-mono text-[10px] ${
        expiresIn != null && expiresIn < 30 ? KT.sev.warn : KT.muted}`}>
        {rankReason(item)}
        {" · "}
        {expiresIn != null ? `expires in ~${Math.round(expiresIn)}m` : "age unknown"}
      </p>
    </div>
  );
}

/**
 * Accept every open recommendation in this group, in one act.
 *
 * THE CONSTITUTION ASKS FOR THIS AND ALSO CONSTRAINS IT. "The CEO decides
 * batches, not items" is the reason the COO seat exists; this is that sentence
 * made clickable. But it is also a control that fires N decisions from one
 * click on the firm's decision channel, so:
 *
 *   * it CONFIRMS, listing exactly how many and which rows it will accept —
 *     nothing is accepted from a single click;
 *   * it fires SEQUENTIALLY, not in parallel. A burst of concurrent writes to
 *     the decision channel is not something a layout change should introduce,
 *     and sequential keeps one clean event per row;
 *   * it reports PARTIAL FAILURE HONESTLY. If five of seven land, it says five
 *     of seven and names the two that did not, and those two are still open. A
 *     bulk control that reported success because it finished would be the
 *     worst possible thing on this page;
 *   * it only ever offers ACCEPT. There is no bulk reject: rejecting is the
 *     cheap direction to get wrong in volume, and a rejection carries a reason
 *     per row.
 */
function GroupAccept({ items, isBatch, onChanged }: {
  items: DeskItem[]; isBatch: boolean; onChanged: () => Promise<void> | void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<
    { ok: number; failed: { text: string; err: string }[] } | null>(null);

  const run = async () => {
    setBusy(true);
    let ok = 0;
    const failed: { text: string; err: string }[] = [];
    for (const item of items) {
      const r = item.rec!;
      try {
        // Sequential, on purpose. See the docstring.
        // eslint-disable-next-line no-await-in-loop
        await fundApiClient.decideRecommendation(r.run_id, r.rec_id,
                                                 { status: "accepted", actor: "ceo" });
        ok += 1;
      } catch (e) {
        failed.push({
          text: memoParts(r.text).headline,
          err: e instanceof Error ? e.message : "the spine did not record it",
        });
      }
    }
    setResult({ ok, failed });
    setBusy(false);
    setConfirming(false);
    await onChanged();
  };

  if (result) {
    return (
      <div className={`mt-2 p-3 ${KT.inset}`}>
        <p className={`text-[12px] ${result.failed.length ? KT.sev.warn : KT.body}`}>
          Accepted <span className="font-mono tabular-nums">{result.ok}</span> of{" "}
          <span className="font-mono tabular-nums">{items.length}</span>
          {result.failed.length > 0 && (
            <> · <span className="font-mono tabular-nums">{result.failed.length}</span>{" "}
              were NOT recorded and are still open</>
          )}
        </p>
        {result.failed.map((f, i) => (
          <p key={i} className={`mt-1 text-[11px] ${KT.down}`}>
            {f.text} — {f.err}
          </p>
        ))}
      </div>
    );
  }

  if (!confirming) {
    return (
      <button type="button" onClick={() => setConfirming(true)}
              className={`${KT.btnGhost} mt-2 text-xs`}>
        Accept all {items.length} {isBatch ? "in this batch" : "in this group"}
      </button>
    );
  }

  return (
    <div className={`mt-2 p-3 ${KT.inset}`}>
      <p className="text-[12px] font-medium">
        Accept {items.length} recommendation{items.length === 1 ? "" : "s"}?
      </p>
      <ul className={`mt-1.5 space-y-0.5 text-[11px] ${KT.body}`}>
        {items.map((i) => (
          <li key={i.key} className="flex gap-2">
            <span className={KT.muted}>·</span>
            <span className="min-w-0 flex-1">{memoParts(i.rec!.text).headline}</span>
          </li>
        ))}
      </ul>
      <p className={`mt-1.5 text-[11px] ${KT.muted}`}>
        Each is recorded as its own decision, one at a time. If any fails, the
        ones that failed stay open and this will say which.
      </p>
      <div className="mt-2 flex gap-2">
        <button type="button" disabled={busy} onClick={run}
                className={`${KT.btn} disabled:opacity-40`}>
          {busy ? "Recording…" : `Yes, accept ${items.length}`}
        </button>
        <button type="button" disabled={busy} onClick={() => setConfirming(false)}
                className={KT.btnGhost}>
          Cancel
        </button>
      </div>
    </div>
  );
}

/**
 * What the ranking could and could not see, under the list rather than in it.
 *
 * Printed rather than implied: a ranking that silently pretends to know the
 * money on 47 of 48 rows is worse than one that says which rows it could not
 * price. The `covered_by` sentence is here for the same reason — the grouping
 * is honest about the relation it does NOT have.
 */
function RankingNote({ gap, coverage, batches, hazard }: {
  gap: { priced: number; unpriced: number };
  coverage: ReturnType<typeof rankCoverage>;
  batches: number;
  /** Set only when the ordering is ACTUALLY resting on an unrecognised kind
   *  over a priced row — null the rest of the time. A warning about a
   *  hypothetical is noise, and noise on every render is how a warning stops
   *  being read. See `orderingHazard`. */
  hazard: string | null;
}) {
  return (
    <>
    {hazard && (
      <p className={`text-[12px] leading-relaxed ${KT.sev.warn}`}>{hazard}</p>
    )}
    <p className={`text-[11px] leading-relaxed ${KT.muted}`}>
      Ranked by <strong>deadline</strong>, then reversibility, then money, then
      age — a versioned change can be reversed in an afternoon and a fill
      cannot. Grouping does not re-rank: a group leads because its best row
      does.
      {gap.unpriced > 0 && (
        <>
          {" "}
          <span className={KT.sev.warn}>
            {gap.unpriced} of {gap.priced + gap.unpriced} carry no money figure
          </span>{" "}
          — <code>money_at_stake</code> is optional and these seats stated none,
          so they sit at the foot of their own band rather than being priced
          from their prose.
        </>
      )}
      {coverage.dated === 0 && (
        <>
          {" "}None carries a <code>due_date</code>, so the deadline key — which
          outranks everything else — separated nothing here. That is a gap in
          what seats record, not a claim that nothing is dated.
        </>
      )}
      {batches > 0 && (
        <>
          {" "}A batch groups the rows its own memo FILED. It cannot yet gather
          rows from other seats that the memo endorses, because no field records
          that link — so accepting a batch here decides its own rows and leaves
          the ones it speaks for open under their seats.
        </>
      )}
    </p>
    </>
  );
}

/* --------------------------------------------------------- the foot ------- */

/**
 * A named door.
 *
 * The label says WHAT and HOW MANY before it is opened. A `<details>` reading
 * only "more" would be concealment with a chevron — the thing the brief
 * explicitly forbids, and the reason every count here is rendered in the
 * summary rather than discovered by clicking.
 *
 * A door with nothing behind it renders as a sentence rather than a control,
 * because an expander that opens onto nothing teaches a reader to stop opening
 * them.
 */
function Folded({ label, count, blurb, seat, children, alwaysOpenable,
                 emptyNote }: {
  label: string;
  count: number;
  blurb: string;
  seat?: string;
  children: React.ReactNode;
  /** Donna's door opens even at zero notes: her memo card lives behind it and
   *  renders its own five absences, which a "nothing here" line would
   *  contradict from an inch away. */
  alwaysOpenable?: boolean;
  /** What the zero MEANS, when it means something. "0 triage memos" and "the
   *  COO has not run, so the list above is unbatched" are the same number and
   *  different facts, and only the second tells the CEO anything. A door at
   *  zero renders no children, so this is the only place that sentence can
   *  live — the first cut put it inside the door, where it was unreachable
   *  code. */
  emptyNote?: string;
}) {
  if (count === 0 && !alwaysOpenable) {
    return (
      <p className={`text-[12px] ${KT.muted}`}>
        {label} — <span className="font-mono tabular-nums">0</span>
        {emptyNote && <> · {emptyNote}</>}
      </p>
    );
  }
  return (
    <details className={`${KT.panel} px-4 py-3`}>
      <summary className="flex cursor-pointer select-none flex-wrap items-center gap-2">
        {seat && <SeatFace actor={seat} size={16} decorative />}
        <span className="text-[13px]">{label}</span>
        <span className={`font-mono tabular-nums text-[11px] ${KT.muted}`}>
          {count}
        </span>
      </summary>
      <p className={`mt-2 mb-2 text-[11px] leading-relaxed ${KT.muted}`}>{blurb}</p>
      {children}
    </details>
  );
}

/** One COO batch memo. */
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

/**
 * Donna's latest daily.
 *
 * FIVE absences, kept apart on purpose. "Unreachable" is not "she has not
 * filed"; "never filed" is not "filed and empty"; and a file that is present
 * but carries no memo section is a DEFECT in the artifact rather than a
 * missing memo — collapsing them would send the reader to the wrong place.
 *
 * As of 2026-08-22 this card can finally be right: `GET /fund/desk/archives/memo`
 * did not exist, so it rendered a permanent absence it was manufacturing
 * itself.
 */
function DailyMemoCard({ memo, unreachable }: {
  memo: ArchiveMemo | null;
  unreachable: boolean;
}) {
  if (unreachable || memo === null) {
    return (
      <p className={`mb-2 text-sm ${KT.sev.warn}`}>
        Her memo could not be read — UNKNOWN, not absent. Anything she filed is
        still filed; this surface could not reach it.
      </p>
    );
  }
  if (!memo.available) {
    const said = memo.reason === "never_filed"
      ? "The archive has never been written to — she has not run yet."
      : memo.reason === "none_yet"
        ? "No daily has been filed yet. Hers lands here when she runs at end of day."
        : memo.reason === "no_such_day"
          ? "Nothing was documented for that day — which is not the same as a quiet day."
          : memo.reason === "unreadable"
            ? "Her memo is on file and could not be read — UNKNOWN, not absent."
            : memo.reason === "no_memo_section"
              ? "A daily is filed but carries neither a TL;DR nor a THE DAILY section — a defect in the artifact, not a missing memo."
              : "Her memo is unavailable and the reason was not stated.";
    return (
      <p className={`mb-2 text-sm ${
        memo.reason === "unreadable" || memo.reason === "no_memo_section"
          ? KT.sev.warn : KT.muted}`}>
        {said}
      </p>
    );
  }

  const age = memoDayLabel(memo.date, new Date());
  return (
    <div className={`${KT.card} mb-2 p-3`}>
      <div className="mb-1.5 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-[13px] font-medium tracking-tight">Her daily</span>
        <span className={`font-mono text-[11px] tabular-nums ${KT.muted}`}>
          {memo.date ?? "undated"}
        </span>
        {/* Only when it is known. An unparseable date renders NOTHING here
            rather than a soothing "today". */}
        {age && (
          <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${
            age === "today" || age === "yesterday" ? KT.muted : KT.sev.warn}`}>
            {age}
          </span>
        )}
        {memo.pdf_path && (
          <span className={`ml-auto font-mono text-[10px] ${KT.muted}`}
                title={memo.pdf_path}>
            pdf filed
          </span>
        )}
      </div>

      {memo.tldr ? (
        <p className={`whitespace-pre-line text-[13px] leading-relaxed ${KT.body}`}>
          {memo.tldr}
        </p>
      ) : (
        <p className={`text-[12px] ${KT.sev.warn}`}>
          This daily carries no TL;DR — the section below is the whole memo.
        </p>
      )}

      {memo.daily_markdown && (
        <ClarkMarkdown
          text={unwrapMemoMarkdown(memo.daily_markdown)}
          className={`mt-2 border-t border-[var(--kt-border)] pt-2 text-[12px] ${KT.body}`}
        />
      )}

      <p className={`mt-2 font-mono text-[10px] ${KT.muted}`}>
        {memo.path ?? "no path returned"}
        {memo.has_long_record
          ? " · the long record is on her desk, not here"
          : " · this daily carries no long record"}
      </p>
    </div>
  );
}

/**
 * One of Donna's NOTES — read-only by construction.
 *
 * No accept/reject, per her seat definition: a note "asks to be READ, not
 * decided". The CEO's own words on the alternative: "this seems more like a
 * note and I don't know what to accept".
 */
function NoteRow({ item }: { item: DeskItem }) {
  const r = item.rec!;
  return (
    <div className={`${KT.card} p-3`}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
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
  const mine = ask.stage === "awaiting_ceo";

  return (
    <div className={`${KT.panel} ${mine ? "p-4" : "p-3"} ${
      ask.stage === "declined" ? "opacity-60" : ""}`}>
      <div className="flex flex-wrap items-start gap-x-3 gap-y-2">
        <p className={`min-w-0 flex-1 ${mine ? "text-[14px] leading-relaxed" : "text-[13px] leading-snug"}`}>
          {ask.subject || (
            <span className={KT.sev.warn}>
              this ask recorded no subject — unreadable, not empty
            </span>
          )}
        </p>
        {mine && !declining && (
          <span className="flex shrink-0 gap-2">
            <button disabled={busy !== null} onClick={() => act("approve")}
                    className={`${KT.btn} disabled:opacity-40`}>
              {busy === "approve" ? "Approving…" : "Approve"}
            </button>
            <button disabled={busy !== null} onClick={() => setDeclining(true)}
                    className={`${KT.btnGhost} disabled:opacity-40`}>
              Decline…
            </button>
          </span>
        )}
      </div>
      <p className={`mt-1 font-mono text-[10px] ${KT.muted}`}>
        <span className={stageTone}>{stageLabel}</span>
        {" · "}
        {ask.actor || "unattributed"}
        {ask.seatFiled && " · seat"}
        {ask.serves ? ` → ${ask.serves}` : ""}
        {" · "}
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
      {ask.note && <p className={`mt-1 text-[11px] ${KT.body}`}>{ask.note}</p>}
      {ask.stage === "declined" && (
        <p className={`mt-1 text-[11px] ${KT.muted}`}>
          {ask.declineReason
            ? `“${ask.declineReason}”`
            : "no reason was recorded with this decline — the reason is absent, not blank"}
        </p>
      )}
      {err && <p className={`mt-1.5 text-[11px] ${KT.down}`}>{err}</p>}

      {mine && declining && (
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
