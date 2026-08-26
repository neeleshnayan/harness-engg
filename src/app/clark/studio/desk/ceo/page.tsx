"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AlertTriangle, Flame, OctagonX } from "lucide-react";
import {
  fundApiClient, ArchiveMemo, CeoDeskView, DeskSupersessionEdge, DeskView,
  PendingOrder, RiskMonitorResponse, SpineEvent,
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
  decisionList, foldedCounts, orderingHazard,
} from "../decisionList";
import {
  awaitingHeadline, deskShelves, heroFigure, shelfAbsenceNote,
} from "../deskAwaiting";
import { officerDesk } from "../officerQueues";
import { CooTriageChip, ProvenanceChip } from "../components";
import { cardStyle } from "../deskCardStyle";
import { ClarkMarkdown } from "../../components/ClarkMarkdown";
import { blockedRecs } from "../deskEngine";
import { BriefingsShelf, Fold, SupersessionNotice } from "../EngineViews";
import { steeringSentence } from "../deskSteer";
import {
  ClickFeedback, adjudicationOf, cardText, cascadeChip, cascadeOf,
  executionYours, looksUnreadable, rowLamp, supersededBy,
} from "../cardState";
import { deskLanes } from "../deskLanes";
import {
  READING_DESK, readError, readState, type DeskRead,
} from "../deskRead";
import {
  ASK_HEADLINE_MAX, CARD_HEADLINE_MAX, REC_STAGE_LABEL, bodyWithTail,
  clampLine, recLifecycle,
} from "../cardAnatomy";
import { isRecordRow } from "../recordRow";
import { StageRail } from "../CardRail";
import type { LineageSources } from "../lineage";
import { LaneBlock, LineageInline } from "../DeskLaneViews";
import { RequestCardBody } from "../RequestCard";

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
  /* The event log's read carries its own failure flag for the same reason the
     desk's does: `events === null` is the state before the first answer AND
     after a failed one, and the footer below makes an "could not be read"
     claim from it. */
  const [eventsErr, setEventsErr] = useState(false);
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
  /* Supersession edges, read WHOLE and separately from the CEO fold.
     `null` is the store being unreadable, and every lineage stage that reads
     it then says UNKNOWN instead of "no edge" — the D22 review's own rule
     about a capped or absent control query. */
  const [edges, setEdges] = useState<DeskSupersessionEdge[] | null>(null);
  const [edgesTruncated, setEdgesTruncated] = useState<
    { shown: number; total: number } | null>(null);
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
    const [d, p, ev, rk, mm, en, sp] = await Promise.allSettled([
      fundApiClient.getDesk(),
      fundApiClient.getPending(),
      fundApiClient.getEvents(1000, 0),
      fundApiClient.getRiskMonitor(),
      fundApiClient.getArchiveMemo(),
      fundApiClient.getCeoDesk(since, false),
      fundApiClient.getDeskSupersessions(),
    ]);
    if (d.status === "fulfilled") { setDesk(d.value); setErr(null); }
    else { setDesk(null); setErr(readError(d.reason)); }
    setPending(p.status === "fulfilled" ? (p.value.pending || []) : null);
    if (ev.status === "fulfilled") { setEvents(ev.value.events || []); setEventsErr(false); }
    else { setEvents(null); setEventsErr(true); }
    if (rk.status === "fulfilled") { setRisk(rk.value); setRiskErr(false); }
    else { setRisk(null); setRiskErr(true); }
    if (mm.status === "fulfilled") { setMemo(mm.value); setMemoErr(false); }
    else { setMemo(null); setMemoErr(true); }
    if (en.status === "fulfilled") { setEngine(en.value); setEngineErr(false); }
    else { setEngine(null); setEngineErr(true); }
    if (sp.status === "fulfilled") {
      setEdges(sp.value.edges ?? []);
      // FETCHING A PAGE IS NOT READING A TABLE. The endpoint caps at `limit`
      // and reports `total` counted independently; a lineage view built on a
      // truncated page would answer "no edge" for every row it did not reach.
      setEdgesTruncated(sp.value.truncated === true
        ? { shown: sp.value.shown, total: sp.value.total } : null);
    } else { setEdges(null); setEdgesTruncated(null); }
  }, [since]);

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  /* THE THREE STATES OF EACH READ — the CEO's own ticket, fccb9cf3.
     `desk === null` is TWO facts wearing one expression: the payload before
     the first answer, and the payload after a failure. Every sentence on this
     page that reads "could not be read" used to fire on both, so a recompile
     that left the fetches pending for thirty seconds rendered the fund's
     loudest honesty language about an outage that had not happened. The two
     reads are tracked separately because they are two endpoints with two
     failures: the desk feeds the number and the lanes, the engine feeds the
     greeting, the lineage and the steer. */
  const deskRead = readState(desk !== null, err !== null);
  const engineRead = readState(engine !== null, engineErr);
  const eventsRead = readState(events !== null, eventsErr);
  const memoRead = readState(memo !== null, memoErr);

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
  /* DECLINED ONLY, and separated here rather than at the render site so the
     door's COUNT and its CONTENTS come from one expression. A door whose
     label counts one population and whose body renders another is exactly the
     kind of quiet mismatch this page has shipped before. */
  const declinedAsks = useMemo(
    () => asks.filter((a) => a.stage === "declined"), [asks]);

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
  /* ONE FOLD FOR "WHAT AWAITS YOU".
     This page used to render its OWN count in the header and let the triage
     chip render the SPINE's on the line below — measured live on
     2026-08-23 as "96 awaiting your decision" over "97 / 50 AWAITING YOU",
     with nothing on screen saying which to believe, because the difference
     was the one divergence the drift check is designed to stay quiet about.
     `awaitingHeadline` folds once: the served counter is the figure, less the
     measured read-only notes, with the subtraction stated; the page's own
     fold survives only where the spine serves nothing, and says so when used.
     `list.total === officers.awaitingTotal` by construction, so the cards are
     the honest thing to reconcile the served figure against. */
  const headline = useMemo(
    () => awaitingHeadline({
      read: deskRead,
      servedTotal: desk?.desk_load?.total,
      servedComplete: desk?.desk_load?.complete,
      servedUnreadable: desk?.desk_load?.unreadable,
      divertedNotes: officers.donna.notes.length,
      cardCount: list.total,
    }),
    [desk, deskRead, officers, list],
  );

  /* Coverage over the CARDS, not over the flat split — the sentence about what
     the ranking could not see must describe the rows on screen. */
  const cardItems = useMemo(
    () => list.all.flatMap((d) => (d.kind === "ask" ? [] : [d.item])), [list]);

  /* THE FUND'S CLOCK, NOT THE BROWSER'S, in one place.
     "Resolved today" must mean the fund's UTC day, and a card's "how long has
     this sat here" must be measured on the same clock the lanes use — two
     clocks on one page is the same class of defect as two counters, which this
     desk has already shipped twice. Falls back to the browser only when the
     spine sent no timestamp at all, and every reader is then a best effort
     rather than wrong. */
  const deskNow = engine?.at ?? new Date().toISOString();

  /* THE SHELVES. CEO, 2026-08-24, on seeing "51 AWAITING YOU": "are you
     sure?" — he was right. One number conflated four different obligations:
     things to DECIDE today, things he already decided whose EXECUTION is
     his, open ASKS on his figure only by the routing default (the P-2
     decision on this very desk), and no-deadline reading. The hero number
     stays the served total (the integrity fold above is untouched); this
     line SHELVES it, computed from fields every row already carries — no
     new count, a partition of the existing one. */
  const shelves = useMemo(
    () => deskShelves(
      deskRead,
      cardItems.map((it) => ({
        dueDate: it.dueDate, executionYours: executionYours(it),
      })),
      list.all.filter((d) => d.kind === "ask").length,
      // THE FUND'S DAY, not the browser's — "due today" is a claim about the
      // fund's UTC day, and `deskNow` is the one clock this page reads.
      deskNow.slice(0, 10),
    ),
    [deskRead, cardItems, list, deskNow]);
  const gap = useMemo(() => moneyGap(cardItems), [cardItems]);
  const coverage = useMemo(() => rankCoverage(cardItems), [cardItems]);

  /* THE ONE STEERING SENTENCE. Reads the spine's own ranking — `decisions`
     is already ordered by due date then money, absent last on both — and
     refuses to name a "most urgent" row when the top of that ranking states
     neither. See `deskSteer`. */
  const steer = useMemo(
    () => steeringSentence({
      view: engine, read: engineRead, needsYou: headline.value,
    }),
    [engine, engineRead, headline]);

  /* THE FIVE LANES. Lane (a) is the decision list this page already builds;
     the other four are folded here from the same payload, each carrying the
     FUND's count beside the number of rows this page can render. */
  const lanes = useMemo(
    () => deskLanes({
      desk,
      read: deskRead,
      awaitingShown: list.total,
      awaitingServed: headline.value,
      blocked,
      now: deskNow,
    }),
    [desk, deskRead, list.total, headline.value, blocked, deskNow]);

  /* Everything the lineage fold reads. Each field is independently nullable
     and null means UNREADABLE — a chain drawn over an outage would make the
     outage look like a tidy record. */
  const lineageSources: LineageSources = useMemo(() => ({
    desk,
    events,
    edges,
    runsDeclaringService: engine?.hygiene?.runs_declaring_service ?? null,
    runsRead: engine?.hygiene?.runs_read ?? null,
  }), [desk, events, edges, engine]);

  const halted = risk?.halted === true;
  const drift = contractDrift(desk?.desk_load?.contract_digest);

  return (
    <div className="min-h-screen bg-[var(--kt-bg)] text-[var(--kt-text)]">
      <StudioHeader subtitle="The CEO's desk — everything awaiting your click" />
      <div className={KT.container}>
        {/* ── THE HEADER IS THE ANSWER, NOT A DASHBOARD ───────────────────
            CEO instruction for this redesign: a greeting line, THE one number,
            and ONE steering sentence. What used to live here — the group
            count, the folded-items count, the decision velocity, the triage
            chip and a five-line greeting card — was six figures answering five
            different questions above the first thing he had to decide. They
            are not deleted: every one of them is under the lanes, where it is
            context rather than a competitor for the eye.

            HIERARCHY FROM TYPE AND SPACE. The number is the only hero-scale
            thing on the page (`KT.hero`, 4xl light tabular), the greeting and
            the steer are body text, and the label above them is the Studio's
            10px mono. No colour is spent here at all unless something dated is
            actually overdue. */}
        <header className="mb-8 flex items-start gap-5">
          <SeatFace actor="ceo" size={64} />
          <div className="min-w-0 flex-1">
            <p className={KT.label}>Krypton Fund · the corner office</p>
            {/* THE GREETING IS THE SPINE'S, VERBATIM. A hand-written "all
                quiet" would be the one line on this desk nobody could
                falsify — the reason `GreetingHeader` was generated in the
                first place, kept when the card it lived in was removed. */}
            <p className={`mt-1 text-sm leading-relaxed ${KT.body}`}>
              {engine?.greeting?.changed
                ?? (engineErr
                  ? "The desk engine could not be read, so what changed since "
                    + "your last visit is unknown."
                  : READING_DESK)}
            </p>
            <p className="mt-3 flex items-baseline gap-3">
              {/* THE HERO SAYS WHICH KIND OF NOT-A-NUMBER IT IS.
                  `unknown` is a finding: the fund was asked and could not
                  answer, and it is rendered at full strength because it means
                  work may be waiting that nobody can see. `…` is a read still
                  in flight — no finding, nothing to alarm about, and muted so
                  the eye passes over it. Rendering the first for the second is
                  ticket fccb9cf3, thirty seconds of it on the CEO's screen.
                  The choice itself is `heroFigure`, in a file tests can run. */}
              <span className={
                headline.source === "loading" ? KT.heroDim : KT.hero}>
                {heroFigure(headline)}
              </span>
              <span className={`${KT.label} pb-1`}>awaiting your decision</span>
            </p>
            {/* THE SHELF LINE — the honest partition of the hero number.
                "51" alone reads as 51 decisions; the truth is four shelves
                and only the first is this morning's. */}
            <p className={`mt-1 text-sm ${KT.body}`}>
              {shelves === null ? (
                /* FOUR ZEROES UNDER AN "unknown" HERO IS THE ABSENCE-AS-ZERO
                   ERROR, on this fund's most-read line. Caught in D42's
                   dead-spine pass: the hero said `unknown` and this line
                   underneath it said "0 to decide today", about the same
                   rows. A partition of an unknown number is unknown.

                   AND A PARTITION OF A NUMBER NOBODY HAS YET IS NOT UNKNOWN
                   EITHER — it is not computed. Same null from `deskShelves`,
                   two different true sentences, chosen by the read state
                   rather than by the null. */
                <span className={KT.muted}>{shelfAbsenceNote(deskRead)}</span>
              ) : (
                <>
                  <span className={steer.overdue ? KT.sev.warn : "font-medium"}>
                    {shelves.decideToday} to decide today
                  </span>
                  {" · "}{shelves.exec} decided — execution yours
                  {" · "}{shelves.asks} asks awaiting your routing call
                  {" · "}{shelves.noDeadline} with no deadline
                </>
              )}
            </p>
            {/* WHICH FOLD PRODUCED THAT NUMBER. A figure this build computed
                and a figure the fund computed are different claims, and the
                one time the reader must know is the one time nothing used to
                say. It stays in the header, under the number it qualifies:
                moving it below the lanes would separate a caveat from the
                figure it is about, which is how a caveat stops being read. */}
            {headline.note && (
              <p className={`mt-2 max-w-3xl text-xs leading-relaxed ${KT.muted}`}>
                {headline.note}
              </p>
            )}
            {/* ── THE EXCEPTIONS DESK, LINKED AND NOT SUBSTITUTED ────────────
                The ticket highway's exceptions view splits the decisions you
                owe from the executions you owe and states the rule behind
                every row. It reads `GET /fund/tickets`, which ships on a
                build the chair has not merged — so this is a LINK and not a
                redirect: repointing the screen you click approvals on at an
                endpoint that 404s today would take the control down with the
                count. Promoting it is one routing line, after the merge.

                NOTHING ABOVE OR BELOW THIS LINE CHANGED. It adds a
                destination and removes no control — the D39 lesson is that a
                default often carries one. */}
            <p className={`mt-2 text-xs ${KT.muted}`}>
              <Link href="/clark/studio/desk/ceo/exceptions" className="underline">
                exceptions only
              </Link>
              {" — the same rows, split into the decisions you owe and the "}
              {"executions you owe, each stating why it is on your desk"}
            </p>
            {/* ── THE STEERING SENTENCE, DEMOTED (2026-08-24) ─────────────────
                IT WAS THE LARGEST THING IN THE HEADER. Measured on the live
                desk before this change: 73px tall at 15px in the warn amber,
                282 characters, THREE lines — taller than the hero line (41px)
                and 30% of the header's whole 244px. Three amber lines arguing
                for attention directly under a spec whose first rule is that
                the number is the only hero-scale thing on the page and whose
                design brief says hierarchy comes from type and space, never
                colour. The CEO reads this header first, every day.

                DEMOTED, NOT DELETED — its content is real and it is the one
                sentence that says what to do next. It moves into the same
                metadata register the spend-demotion rule put the token counts
                in (docs/design/RUN_PAGE_2026-08-24.md: "the work is the face;
                the spend is a footnote"): 12px, below the shelves and below
                the caveat about the number, joined to the ranking key it has
                always been arguing with.

                THE COLOUR GOES; THE SIGNAL DOES NOT. Overdue is still the one
                condition on this desk that earns a hue — it is the only one
                true whether or not anybody clicks — but it earns it ON THE
                COUNT, in the shelf line above, where it already is. Spending
                it a second time on three lines of prose about the same fact is
                the two-counters defect wearing colour: one condition, two
                alarms, and the prose one is thirty times the area. Demoting
                the size and keeping the amber was tried first and LOOKED at:
                three amber lines at 12px are still three amber lines, and the
                CEO's complaint was about the amber. Nothing is silenced — the
                words "due TODAY" and "N days OVERDUE" are in the sentence
                either way, and `steer.overdue` still drives the count above.

                THE ONE CASE THIS COSTS, named rather than hidden: desk read
                DOWN and engine read UP. The shelf line is then the failure
                sentence (no count to colour) and this line is muted, so an
                overdue commitment is stated in words with no hue anywhere.
                That reader is already looking at an outage banner; a reader
                with everything working sees the colour on the number. */}
            {/* The reading measure STAYS. Widening this line to the header's
                full 873px was tried and MEASURED: identical text wrapped to
                exactly 59px at both 768px and 873px, so the cap costs nothing
                and a 40-em metadata line would be harder to scan for no gain.
                Recorded because the guess going in was that it would save a
                line, and it did not. */}
            <p className={`mt-2 max-w-3xl text-xs leading-relaxed ${KT.muted}`}>
              {steer.text}
              {" · "}
              {/* The spine's own ranking key, so a reader can disagree with
                  the steer rather than absorb it. Same register now, and on
                  the same line: they are one thought, and they were two
                  paragraphs only because the steer used to be a headline. */}
              <span className={KT.muted}>
                {engine?.decisions?.ranked_by
                  ? `ranked by ${engine.decisions.ranked_by}`
                  : "the spine stated no ranking key"}
              </span>
            </p>
            <p className={`mt-2 text-xs ${KT.muted}`}>
              <Link href="/clark/studio/desk" className={`${KT.accent} hover:underline`}>
                back to the floor
              </Link>
              {" · "}
              <Link href="/clark/studio/desk/floor"
                    className={`${KT.accent} hover:underline`}>
                the room, and the firm&apos;s ticket board
              </Link>
            </p>
          </div>
        </header>

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

        {/* The residual. The figure above is the fund's; the cards below are
            this page's fold. When they still disagree after the one measured
            adjustment, neither is safe to present alone — so this says so
            loudly rather than the page quietly showing both. */}
        {headline.reconciliation && (
          <div className={`${KT.card} mb-6 flex items-start gap-2 border-[var(--kt-warn)]`}>
            <AlertTriangle size={15} className="mt-0.5 shrink-0 text-[var(--kt-warn)]" />
            <p className="text-sm">{headline.reconciliation}</p>
          </div>
        )}

        {/* ── THE LANES ───────────────────────────────────────────────────
            CEO instruction for this redesign, verbatim: lanes, not a scroll.
            Five named queues; only the first is open. Every lane renders its
            count SHUT, so folding hides no quantity, and every lane's number
            is the fund's own with the page's row count beside it where they
            differ (`deskLanes.laneCount`).

            The lanes replace a foot section of five `<details>` doors that had
            grown to carry three of the five queues below and none of their
            counts in a comparable form. Nothing that was behind those doors
            has been dropped: the two READING doors (COO memos, Donna's daily)
            are still doors, at the foot, because reading is not a queue. */}
        {edgesTruncated && (
          <div className={`${KT.card} mb-6 flex items-start gap-2 border-[var(--kt-warn)]`}>
            <AlertTriangle size={15} className="mt-0.5 shrink-0 text-[var(--kt-warn)]" />
            <p className="text-sm">
              The supersession edge store returned a TRUNCATED page —{" "}
              <span className="font-mono tabular-nums">{edgesTruncated.shown}</span>
              {" "}of{" "}
              <span className="font-mono tabular-nums">{edgesTruncated.total}</span>
              . Lineage below can answer &ldquo;no edge&rdquo; for a row whose
              edge simply did not fit on the page.
            </p>
          </div>
        )}

        <div className={`${KT.panel} mb-8 px-6`}>
          <LaneBlock lane={lanes[0]} sources={lineageSources}>
            {deskRead === "loading" ? (
              /* NOT AN OUTAGE. The read is in flight, so there are no cards
                 for the same reason there is no number: nobody has answered
                 yet. Muted, and it does not borrow the warn tone below. */
              <p className={`text-sm ${KT.muted}`}>{READING_DESK}</p>
            ) : deskRead === "unreadable" ? (
              /* The "UNKNOWN, not none" sentence lives ONCE, under the figure
                 it describes — `headline.note`. What belongs here is the
                 different fact: why there is nothing in this lane. */
              <p className={`text-sm ${KT.sev.warn}`}>
                No decision cards can be built from a desk that cannot be read.
              </p>
            ) : list.total === 0 ? (
              <>
                {/* "Nothing awaits your decision" is a claim about the CARDS,
                    and it may only be made when the fund's own counter agrees.
                    If the served figure says otherwise, the banner above is
                    already shouting and this sentence must not contradict it. */}
                <p className="text-[15px] leading-relaxed">
                  {headline.reconciliation
                    ? "This page has no decision cards to show — and the fund's own counter disagrees, above."
                    : "Nothing awaits your decision."}
                </p>
                <p className={`mt-1 text-sm ${KT.body}`}>
                  That is a measurement of this moment, not of the firm — the
                  lanes below hold what is decided, dispatched, owned elsewhere
                  and closed today. None of it needs a click from you.
                </p>
              </>
            ) : (
              <div className="space-y-7">
                {list.groups.map((g) => (
                  <DecisionGroupBlock key={g.key} group={g} onChanged={load}
                                      sources={lineageSources} now={deskNow} />
                ))}
                <RankingNote gap={gap} coverage={coverage} batches={list.batches}
                             hazard={orderingHazard(list.all)} />
              </div>
            )}
          </LaneBlock>

          {lanes.slice(1).map((lane) => (
            <LaneBlock key={lane.id} lane={lane} sources={lineageSources} />
          ))}
        </div>

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

        {/* ── READING — NOT A QUEUE ───────────────────────────────────────
            What is left behind doors is what asks to be READ. The two queues
            that used to live here — decided-awaiting-execution and
            open-elsewhere — are lanes now, with the fund's own counts; keeping
            a second rendering of them here would put two numbers on one page
            for one question, which is the defect this desk has shipped three
            times. */}
        {desk !== null && (
          <div className="space-y-2 border-t border-[var(--kt-border)] pt-6">
            <p className={`${KT.label} mb-1`}>On file — reading, not decisions</p>

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
              <DailyMemoCard memo={memo} read={memoRead} />
              {officers.donna.notes.length > 0 && (
                <div className="mt-2 space-y-1.5">
                  {officers.donna.notes.map((item) => (
                    <NoteRow key={item.key} item={item} />
                  ))}
                </div>
              )}
            </Folded>

            {/* DECLINED ONLY. Cleared asks are the chair's dispatch queue and
                are now a LANE with the fund's own figure beside them; leaving
                a copy of them here as well would be the same queue counted
                twice on one page. A decline is terminal and belongs to
                neither the lanes nor your click, which is why it is here. */}
            <Folded
              label="Bench asks declined — terminal"
              count={declinedAsks.length}
              blurb="A decline cannot be revived and carries its written reason verbatim. Cleared asks are not here: they are the chair's dispatch lane above, counted by the fund."
              seat="cto"
              emptyNote="nothing has been declined in the window this page reads"
            >
              <div className="space-y-1.5">
                {declinedAsks.map((a) => (
                  <AskRow key={a.requestId} ask={a} onDecided={load} />
                ))}
              </div>
            </Folded>
          </div>
        )}

        {/* ── CONTEXT — the figures that are not the answer ────────────────
            Everything the header used to carry beside the number. It is not
            deleted and it is not hidden: it is BELOW the thing it is context
            for. `on_fire`, the hygiene sentence and the readability warnings
            come from the spine's own greeting fold, verbatim, because a
            hand-written "all quiet" would be the one line on this desk nobody
            could falsify. */}
        <div className={`${KT.panel} mt-8 p-5`}>
          <p className={`${KT.label} mb-3`}>Context</p>
          <p className="flex items-start gap-1.5 text-sm leading-relaxed">
            {(engine?.on_fire.total ?? 0) > 0 && (
              <Flame size={13} className="mt-0.5 shrink-0 text-[var(--kt-warn)]" />
            )}
            {/* THREE TONES FOR THREE FACTS, and the third is the one a `?? 0`
                would have flattened: something IS on fire (warn), nothing is
                (calm), and WE CANNOT TELL (also warn — an unreadable engine
                rendered in the calm tone is a reassurance nobody measured).
                The flame itself stays off in the unknown case, because a flame
                is a positive claim about fire and there is none to make. */}
            {/* FOUR FACTS NOW, not three: the fourth is the read still being
                in flight, which is neither a fire nor a failure to look for
                one. It is muted and it makes no claim (ticket fccb9cf3). */}
            <span className={engineRead === "loading" ? KT.muted
              : engine === null || (engine.on_fire.total ?? 0) > 0
                ? KT.sev.warn : KT.body}>
              {engine?.greeting?.on_fire
                ?? (engineRead === "loading"
                  ? "Reading the desk engine… whether anything is on fire has "
                    + "not been checked yet."
                  : "The desk engine could not be read, so whether anything is "
                    + "on fire is UNKNOWN — not no.")}
            </span>
          </p>
          {/* THREE-VALUED, and rendered that way: `null` is the risk control
              being unreachable, and a desk printing "not halted" because it
              could not reach the monitor would be the absence-as-zero error on
              the one control that stops losses. */}
          {engine?.on_fire.risk_halted === null && (
            <p className={`mt-1 text-[11px] italic ${KT.sev.warn}`}>
              The risk control could not be read, so whether trading is halted
              is UNKNOWN — not &ldquo;running&rdquo;.
            </p>
          )}
          <p className={`mt-2 text-xs ${KT.muted}`}>
            decisions recorded{" "}
            <span className="font-mono tabular-nums">
              {velocity.today ?? (eventsRead === "loading"
                ? "… (not read yet)" : "— (event log unreadable, not zero)")}
            </span>{" "}
            today
            {velocity.week != null && (
              <> · <span className="font-mono tabular-nums">{velocity.week}</span> this week</>
            )}
            {desk !== null && list.groups.length > 1 && (
              <>
                {" · "}the lane above is in{" "}
                <span className="font-mono tabular-nums">{list.groups.length}</span>{" "}
                groups
                {list.batches > 0 && (
                  <>
                    {", "}
                    <span className="font-mono tabular-nums">{list.batches}</span>
                    {list.batches === 1 ? " a COO batch" : " of them COO batches"}
                  </>
                )}
              </>
            )}
          </p>
          {engine?.greeting?.hygiene && (
            <p className={`mt-2 max-w-3xl text-[11px] leading-relaxed ${KT.muted}`}>
              {engine.greeting.hygiene}
            </p>
          )}
          {engine && (!engine.readable.recommendations
            || !engine.readable.supersessions || !engine.readable.intray) && (
            <p className={`mt-2 flex items-start gap-1.5 text-[11px] ${KT.sev.warn}`}>
              <AlertTriangle size={12} className="mt-0.5 shrink-0" />
              <span>
                Part of the desk could not be read
                {!engine.readable.recommendations && " · recommendations"}
                {!engine.readable.supersessions && " · supersession lineage"}
                {!engine.readable.intray && " · in-trays"}
                . What is above is incomplete, not empty.
              </span>
            </p>
          )}
          {/* The triage trigger, the elsewhere split and the partial flag —
              none of which the headline carries. `already-on-screen` keeps it
              from printing a second copy of the figure in the header. */}
          <div className="mt-2">
            <CooTriageChip load={desk?.desk_load} total="already-on-screen" />
          </div>
        </div>

        <p className={`mt-6 text-[11px] italic leading-relaxed ${KT.muted}`}>
          {/* "Folded from 0 spine events" is a MEASUREMENT of an empty log and
              must not be printed for a log nobody has finished reading — the
              `?? 0` said 0 in both cases and the clause after it called the
              second an outage. */}
          {eventsRead === "loading"
            ? "Still folding the spine's events; the counts above are not "
              + "final and none of them is a zero"
            : `Folded from ${events?.length ?? 0} spine events`}
          {eventsRead === "unreadable" && " — the event log could not be read, so the decision counts above are absent, not zero"}
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
function DecisionGroupBlock({ group, onChanged, sources, now }: {
  group: DecisionGroup;
  onChanged: () => Promise<void> | void;
  sources: LineageSources;
  now: string;
}) {
  /* Only rows the spine will actually accept: open recommendations. An order
     is approved on Monitor and an ask has its own control, so neither can be
     part of a group accept — offering one would be a button that silently
     skipped half of what it sat under.
     AND NOT A RECORD ROW (D42). `stageOfItem` already keeps a `nobody` row off
     this list, so this guard is the SECOND lock rather than the fix; it is
     here because a bulk control is the one place where a single routing change
     upstream would fire N decisions on rows nobody may decide, and a test
     pins both halves. */
  const bulk = group.decisions.flatMap(
    (d) => (d.kind === "rec" && d.item.rec?.status === "open"
      && !isRecordRow(d.item.rec) ? [d.item] : []));

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
          <DecisionCard key={d.key} d={d} onChanged={onChanged}
                        sources={sources} now={now} />
        ))}
      </div>

      {bulk.length > 1 && (
        <GroupAccept items={bulk} isBatch={group.isBatch} onChanged={onChanged} />
      )}
    </div>
  );
}

/** One decision: the first sentence, why it is where it is, and the buttons. */
function DecisionCard({ d, onChanged, sources, now }: {
  d: Decision;
  onChanged: () => Promise<void> | void;
  sources: LineageSources;
  now: string;
}) {
  if (d.kind === "ask") {
    return <AskRow ask={d.ask} onDecided={onChanged} sources={sources} />;
  }
  if (d.kind === "order") return <OrderCard item={d.item} />;
  return <RecCard item={d.item} onDecide={onChanged} sources={sources}
                  now={now} />;
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

/**
 * One recommendation, wearing the ratified card anatomy.
 *
 * D42 — the CEO, on D39's data repair: *"SO WHAT DID WE DO?"* The rows became
 * TRUTHFUL and still looked like the thing he rejected. Two of the spec's four
 * questions were missing here, and the answers were on the payload already:
 *
 *   1. WHAT IS THIS — `memoParts` gives the first SENTENCE, and on his live
 *      desk those ran 188, 163, 158 and 138 characters, i.e. two and three
 *      rendered lines apiece (RE-DERIVED — the first draft of this comment
 *      said 190/152/148/121 in THREE files and was wrong in all three;
 *      `cardAnatomy.test.ts` now asserts the four lengths so no copy can
 *      drift again). Clamped to a name; the tail joins the body
 *      behind "+ the rest" and `clampLine`'s test proves nothing is lost.
 *   2. WHERE DOES IT STAND — the same rail the request card wears, from the
 *      same component, built from `resolved_at` and `decided_at`.
 *
 * QUESTION 4 IS DELIBERATELY NOT ADDED HERE, and that is a judgement worth
 * writing down. `rowLamp` already names the mover on every shape this card
 * can be in — "execution yours", "the chair owes the execution", "filed for
 * the record" — and the Accept button names it on the rest. A "next move"
 * line beside those would be two sentences saying the same thing, which is
 * the exact defect `cascadeChip`'s docstring records being caught by looking
 * at the page. The whose-move line went to `RecRow` instead, where the
 * question genuinely had no answer.
 */
function RecCard({ item, onDecide, sources, now }: {
  item: DeskItem;
  onDecide: () => Promise<void> | void;
  sources: LineageSources;
  /** The FUND's clock, threaded rather than read from the browser — the same
   *  rule `deskLanes` follows, and the reason the rail's age is testable. */
  now: string;
}) {
  const r = item.rec!;
  /* THE DISPLAY LINE, NOT THE STORED ONE. Two rows on his live desk were
     rendering as a raw Python dict repr; `cardText` prefers the spine's
     repaired `text_display` and falls back to the stored value unchanged. */
  const display = cardText(r);
  const parts = memoParts(display.headline);
  const [open, setOpen] = useState(false);
  /* Separate from `open`: the rest of a memo and the chain behind it are
     different questions, and one toggle for both would make a reader open the
     prose to see the provenance. */
  const [chain, setChain] = useState(false);
  const [feedback, setFeedback] = useState<ClickFeedback>({ state: "idle" });
  const scale = cardStyle(item.reversibility);
  const adj = adjudicationOf(r);
  const superseded = supersededBy(r);
  const cascade = cascadeOf(r);
  const chip = cascadeChip(cascade);
  const lamp = rowLamp(item, feedback);
  /* The budget follows the TYPE SCALE, measured per size — see
     `CardStyle.headlineMax`. A single number clamped the 16px card to two
     lines, which is the thing the clamp exists to stop. */
  const face = clampLine(parts.headline, scale.headlineMax);
  const rail = recLifecycle(r, now);
  /* The detail behind the toggle: whatever the spine extracted from a dict
     payload, else the rest of the prose. Never both — a card that showed the
     paragraph twice is how the old one earned "an infinite scroll".
     The CLAMPED TAIL leads it (D42): it is the rest of the sentence the
     headline started, so it must not sit after a later paragraph. */
  const rest = bodyWithTail(face.tail, display.detail ?? parts.rest);

  const decide = async (status: "accepted" | "rejected") => {
    setFeedback({ state: "sending" });
    try {
      await fundApiClient.decideRecommendation(r.run_id, r.rec_id,
                                               { status, actor: "ceo" });
      /* OPTIMISTIC **AND** REFETCHED, IN THAT ORDER, AND THE ORDER IS THE
         FIX. The refetch pulls seven endpoints and does not reliably finish
         inside a second; the CEO's stated acceptance criterion is that a
         successful click looks different within one. So the lamp changes on
         the response — which is the moment the spine actually recorded it —
         and the refetch then replaces the optimistic sentence with the folded
         truth. Neither alone is enough: optimism without the refetch is a
         page that believes itself, and a refetch without optimism is the
         silence he complained about. */
      setFeedback({ state: "landed", status,
                    at: new Date().toISOString() });
      await onDecide();
    } catch (e) {
      // A decision that failed must not look like a decision that landed.
      setFeedback({ state: "failed",
                    message: e instanceof Error ? e.message
                      : "the spine did not record it" });
    }
  };

  return (
    <div className={scale.container}>
      <div className="flex flex-wrap items-start gap-x-3 gap-y-2">
        {item.dueDate && <DueChip date={item.dueDate} />}
        <p className={`min-w-0 flex-1 ${scale.text}`}>{face.line}</p>
        <span className="flex shrink-0 items-center gap-2">
          {lamp.showButtons ? (
            <>
              <button type="button" disabled={feedback.state === "sending"}
                      onClick={() => decide("accepted")}
                      className={`${KT.btn} disabled:opacity-40`}>
                Accept
              </button>
              <button type="button" disabled={feedback.state === "sending"}
                      onClick={() => decide("rejected")}
                      className={`${KT.btnGhost} hover:border-[var(--kt-down)] hover:text-[var(--kt-down)] disabled:opacity-40`}>
                Reject
              </button>
            </>
          ) : null}
          {lamp.label && (
            /* THE ONE-SECOND ANSWER. Hierarchy from type and space, never
               colour — the only exception is a genuine failure, which is
               semantic. */
            <span className={`font-mono text-[10px] ${
              lamp.tone === "failed" ? KT.down : KT.muted}`}>
              {lamp.label}
            </span>
          )}
        </span>
      </div>

      {/* QUESTION 2: WHERE DOES IT STAND. The same rail the request card
          wears, from the same component — a second rendering of one idea is
          how two surfaces start disagreeing about it. The age rides the hot
          stage, so "filed · 20.7h" IS the sentence "nobody has looked at this
          since yesterday morning", which no line on this card said before. */}
      <StageRail
        items={rail.stages.map((s) => ({
          label: REC_STAGE_LABEL[s.stage] ?? s.stage, state: s.state,
        }))}
        ageHours={rail.ageHours}
      />

      {/* WHAT HE ALREADY DECIDED, AND WHEN. `decided_at` was in the store and
          not in the projection, so no surface could say it. This line is the
          difference between "your click landed" and silence. */}
      {adj && (
        <p className={`mt-1 text-[11px] ${KT.muted}`}>
          {adj.label}
          {adj.at ? ` · ${fmtAt(adj.at)}` : ""}
          {adj.instruction ? ` · “${adj.instruction}”` : ""}
        </p>
      )}

      {/* THE ROW IS BROKEN AND SAYS SO. A stored payload no fold could read
          renders as a warning, never as a tidy blank — the CEO seeing that a
          row is unreadable is strictly better than him seeing nothing. */}
      {looksUnreadable(r) && (
        <p className={`mt-1 text-[11px] ${KT.down}`}>
          This row was filed as a data payload with no readable headline. The
          text below is the record verbatim.
        </p>
      )}

      {/* WHAT REPLACED IT. Rendered only when the note NAMED its superseder:
          six of ten "superseded" mentions in the record are boilerplate about
          something else, and a wrong link looks exactly like a right one. */}
      {superseded && (
        <p className={`mt-1 text-[11px] ${KT.muted}`}>
          Superseded by <span className="font-mono">{superseded.ref}</span>
          {" — "}<span className="italic">{superseded.quote}</span>
        </p>
      )}

      {/* THE CASCADE, AS A REMINDER AND NOTHING ELSE. No control on this line
          executes anything; the chair validates each member against the
          record and then acts, exactly as the constitution says. */}
      {chip && (
        <p className={`mt-1 text-[11px] ${KT.muted}`}>{chip}</p>
      )}

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
          {/* WITHOUT THE TWO FACTS THIS CARD ALREADY RENDERS. The due date is
              in the chip at the top of the row and the wait is the rail's
              age — printing either again is the same paragraph twice, which
              is what the CEO called an infinite scroll. */}
          {rankReason(item, { due: true, waiting: true })}
        </span>
        {rest && (
          <button type="button" onClick={() => setOpen((v) => !v)}
                  className={`font-mono text-[10px] ${KT.accent} hover:underline`}>
            {open ? "− less" : "+ the rest"}
          </button>
        )}
        {/* THE CITATION, ONE CLICK AWAY (CEO, 2026-08-24: "I cant form a view
            of whats closed and adjudicated by you"). It rides the existing
            details toggle rather than adding a third one: a chair disposition
            and its reason are one thing to read, not two. */}
        {adj?.citation && (
          <button type="button" onClick={() => setOpen((v) => !v)}
                  className={`font-mono text-[10px] ${KT.accent} hover:underline`}>
            {open ? "− reason" : "+ the reason"}
          </button>
        )}
        {/* THE CHAIN, on the row that carries the click. Where a decision
            comes from is part of deciding it, and this desk previously made a
            reader leave the page to find out. */}
        <button type="button" onClick={() => setChain((v) => !v)}
                aria-expanded={chain}
                className={`font-mono text-[10px] ${KT.accent} hover:underline`}>
          {chain ? "− lineage" : "+ lineage"}
        </button>
      </div>

      {open && (rest || adj?.citation) && (
        <div className="mt-2 border-t border-[var(--kt-border)] pt-2">
          {rest && (
            <p className={`text-[12px] leading-relaxed ${KT.body}`}>{rest}</p>
          )}
          {adj?.citation && (
            <p className={`${rest ? "mt-2" : ""} text-[12px] leading-relaxed ${KT.muted}`}>
              <span className="font-mono text-[10px]">{adj.actor}: </span>
              {/* VERBATIM AND UNTRUNCATED. A chair that paraphrased its own
                  reason on the surface auditing that reason would be marking
                  its own homework. */}
              {adj.citation}
            </p>
          )}
        </div>
      )}
      {chain && (
        <LineageInline
          anchor={{ kind: "rec", runId: r.run_id, recId: r.rec_id }}
          sources={sources} />
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
function DailyMemoCard({ memo, read }: {
  memo: ArchiveMemo | null;
  /** The state of the `GET /fund/desk/archives/memo` read. It was a single
   *  `unreachable` boolean OR'd with `memo === null`, and that disjunction is
   *  ticket fccb9cf3 in miniature: `memo` is null before the first answer AND
   *  after a failure, so the card could only ever print "could not be read —
   *  UNKNOWN, not absent" for both.
   *
   *  HOW REACHABLE THAT WAS, measured rather than assumed, because the honest
   *  answer is "not, today": `load()` awaits ONE `Promise.allSettled`, so every
   *  read on this page flips out of `loading` in the same render — and the door
   *  this card lives behind is gated on `desk !== null`. Verified on the
   *  in-flight browser arm: the card does not mount there at all. So this is a
   *  contract the component was stating falsely, not a sentence the CEO saw.
   *  Fixed anyway: the gate above it is one edit from changing, and a
   *  component that cannot tell "not yet" from "not ever" is one wiring change
   *  away from saying so out loud. (It is NOT exported — a first draft of this
   *  note said it was, which the read-through caught.) */
  read: DeskRead;
}) {
  if (read === "loading") {
    return (
      <p className={`mb-2 text-sm ${KT.muted}`}>Reading her daily…</p>
    );
  }
  if (read === "unreadable") {
    return (
      <p className={`mb-2 text-sm ${KT.sev.warn}`}>
        Her memo could not be read — UNKNOWN, not absent. Anything she filed is
        still filed; this surface could not reach it.
      </p>
    );
  }
  if (memo === null) {
    /* Readable AND null. Not reachable through this page's `load()`, which
       only stores a fulfilled payload — kept because "the read succeeded and
       produced nothing" is a third fact, and a component whose type admits it
       should not answer it with one of the two sentences above. */
    return (
      <p className={`mb-2 text-sm ${KT.sev.warn}`}>
        The memo endpoint answered with no payload at all — that is a defect in
        the response, not a day without a daily.
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
function AskRow({ ask, onDecided, sources }: {
  ask: QueuedAsk;
  onDecided: () => Promise<void> | void;
  /** Optional: a declined ask in the reading section has a chain too, and the
   *  door that renders it has no sources to give. Absent = no toggle, rather
   *  than a toggle that opens onto an empty fold. */
  sources?: LineageSources;
}) {
  const [busy, setBusy] = useState<"approve" | "decline" | null>(null);
  const [declining, setDeclining] = useState(false);
  const [chain, setChain] = useState(false);
  const [incident, setIncident] = useState(false);
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
  /* THE BUTTONS FOLLOW THE LIFECYCLE, NOT THE ROUTING. `stage` decides where
     the ask is placed and whether it is counted as his; `approvable` decides
     whether the control exists at all. They were one flag until 2026-08-24,
     when routing an open request to the chair silently took the CEO's approve
     button off his own page — a removed control, found by looking. */
  const mine = ask.approvable;
  const emphasised = ask.stage === "awaiting_ceo";
  /* QUESTION 1: WHAT IS THIS — a NAME, not the first line of a dump.
     THE CLAMP IS THE D42 REPAIR AND IT IS THE RENDERER'S JOB BY THE SPINE'S
     OWN CONTRACT: `AskCard.headline`'s docstring says "for a prose ask this is
     the subject's first LINE, untouched — the renderer knows its own width and
     does the truncating", and the renderer was not truncating. EVERY request
     on the live desk is prose (116 of 116 at the time of writing, and the
     count only grows — the invariant is that none is structured), so this
     printed the whole subject as the card's name — seven rendered lines on
     the first ask of the day, which
     is the wall of prose the CEO rejected the card for. Nothing is lost: the
     tail goes behind "+ the incident", and `clampLine`'s test proves the
     rejoin is exact. */
  const face = clampLine(ask.card.headline || ask.subject,
                         emphasised ? ASK_HEADLINE_MAX : CARD_HEADLINE_MAX);

  return (
    <div className={`${KT.panel} ${emphasised ? "p-4" : "p-3"} ${
      ask.stage === "declined" ? "opacity-60" : ""}`}>
      <div className="flex flex-wrap items-start gap-x-3 gap-y-2">
        <p className={`min-w-0 flex-1 ${emphasised ? "text-[15px] font-medium leading-snug" : "text-[13px] leading-snug"}`}>
          {face.line || (
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
      {/* QUESTIONS 2, 3 AND 4 — where it stands, what is owed, whose move.
          The rail carries the age of the CURRENT stage, which is the sentence
          the old card buried: request 0c295ec7 was approved 22 minutes after
          filing and then sat idle 2.5 days. */}
      <RequestCardBody card={ask.card} subject={ask.subject}
                       headlineShown={face.line}
                       open={incident} onToggle={() => setIncident((v) => !v)}
                       trailing={sources ? (
                         <button type="button" onClick={() => setChain((v) => !v)}
                                 aria-expanded={chain}
                                 className={`font-mono text-[10px] ${KT.accent} hover:underline`}>
                           {chain ? "− lineage" : "+ lineage"}
                         </button>
                       ) : null} />
      {chain && sources && (
        <LineageInline anchor={{ kind: "request", requestId: ask.requestId }}
                       sources={sources} />
      )}
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
