/**
 * THE CEO'S EXCEPTIONS FILTER — which tickets reach him, and WHY each one did.
 *
 * THE INCIDENT THIS EXISTS FOR (CEO, 2026-08-24 and again 2026-08-26): his
 * desk carried 57 rows; 25 of them stated neither a date nor a dollar figure,
 * so the payload's own note said their order was "arrival order and not a
 * ranking"; it rendered 50 of the 57 and truncated seven away with no sentence
 * on screen; and an item he had filed **at $915** sat at position 19 of 50 and
 * he could not find it. Measured on the live spine 2026-08-26 —
 * `decisions: {shown: 50, total: 57, truncated: true, ranked_on_nothing: 25}`.
 *
 * THE SPEC is `docs/design/TICKET_HIGHWAY_V1_2026-08-24.md` Part 3: a ticket
 * reaches the CEO iff `next_actor` resolves to `ceo`; OR it aged past its
 * state's threshold; OR it is blocked on a missing join; OR `money_at_stake`
 * is at or above a line; OR it is a `challenge` against a terminal. Everything
 * else lives on a board he visits by choice.
 *
 * WHAT THE MEASUREMENT CHANGED IN THAT SPEC, AND IT IS THE HEADLINE. Folded
 * over the live record (713 tickets, 338 working, 2026-08-26) rule 1 alone
 * selects **54 rows, and 54 + 3 unreadable-actor rows is exactly the 57 his
 * desk shows today**. The exceptions filter therefore does not shrink his desk
 * by itself — his desk was ALREADY exceptions-only under rule 1, and rules
 * 2–5 can only ADD. The reduction comes from somewhere the spec did not name:
 *
 *   **21 of those 54 are `accepted` — he already decided them and owes the
 *   EXECUTION. 33 are undecided and owe a DECISION.** Two different acts wearing
 *   one list. Splitting them is what takes his decision list from 57 to 33,
 *   and it is a split the fold can make because `decided` survives the move
 *   out of `filed` (`tickets.py` §1.5, "one decision, one row").
 *
 * So rules 2–5 are built, wired and counted — but they land in an ESCALATIONS
 * block at the foot, not among his decisions: nobody is asking him to act on
 * them, they are things stuck in the machine that crossed a line. Named
 * disclosure, never concealment: the count is on screen before the block is
 * opened, and this module's split is exhaustive and disjoint by cardinality
 * (a test asserts it), so a row cannot go missing by being tidied.
 *
 * EVERY ROW STATES THE RULE THAT SURFACED IT. The brief's words: "a row he
 * cannot explain the presence of is the defect you are fixing."
 *
 * A RULE THAT CANNOT FIRE SAYS SO, WITH ITS DOMAIN. Two of the five are inert
 * on today's record and reporting them as "0 blocked" would be absence-as-zero
 * on the surface built to end it:
 *
 *   - `missing_join` needs a downstream link from an `accepted` ticket to the
 *     dispatch that serves it. **154 of the 191 working `accepted` tickets sit
 *     inside the fenced pre-highway cohort where the record cannot support a
 *     link at all, and none of the 191 is any other ticket's parent.** So the
 *     rule reports `evaluable: 37, unknown: 154` out of a domain of 191 —
 *     never "nothing is blocked".
 *   - `challenge` needs a ticket of type `challenge`. There are **0 of 713**;
 *     the type has existed for two days and nothing has filed one. Domain
 *     stated beside the zero, always.
 *
 * WHAT THIS MODULE DOES NOT DO. It does not decide whether a row is
 * approvable (`deskEngine.blockedRecs` and the server's refusal own that); it
 * does not re-derive whose move a ticket is (`next_actor` is the spine's own
 * answer, and a client that re-derived it once read 11 where the spine read
 * 6); and it never prices a ticket from its prose.
 */

import type { Ticket, TicketState } from "@/lib/fund_api";

/* -------------------------------------------------------- the constants --- */

/**
 * The version string every surface prints beside a count taken through here.
 *
 * A LEVEL MOVES ONLY WITH A WRITTEN REASON, IN EITHER DIRECTION. These are
 * display thresholds — they decide what reaches a human's first screen, not
 * what reaches money — but the direction rule is the firm's and it is cheaper
 * to obey it here than to argue the boundary later.
 */
export const CEO_EXCEPTIONS_VERSION =
  "ceo exceptions v1 (2026-08-26) — the five rules of TICKET_HIGHWAY_V1 Part 3; " +
  "levels below are the BUILDER'S PROPOSAL and await the CEO's ratification";

/**
 * How long a ticket may sit in each state before it escalates, in hours.
 *
 * THE BAND THESE HAD TO LAND IN WAS MEASURED FIRST, and it is narrow. Over the
 * live record on 2026-08-26 every working ticket's `age_in_state_hours` lies
 * between **43.1 and 146.8** — the record's newest ticket was filed
 * 2026-08-24 and its oldest 2026-08-19. **A level below 43 admits that state's
 * entire population and a level above 147 can never fire**, so a level chosen
 * outside 43–147 is a tie-break wearing a measurement's clothes, and this
 * comment exists so the next person to move one knows which they are doing.
 *
 * What each level catches today, non-CEO working rows, measured not estimated
 * (`node scripts/instruments/kp6/exception_curve.mjs`):
 *
 *   | state     | domain | 48h | 72h | 96h | 120h | 144h | LEVEL | fires |
 *   |-----------|-------:|----:|----:|----:|-----:|-----:|------:|------:|
 *   | filed     |     56 |  40 |  19 |   0 |    0 |    0 |   96  |     0 |
 *   | approved  |     47 |  47 |  27 |  20 |    1 |    0 |   96  |    20 |
 *   | in_flight |      9 |   7 |   0 |   0 |    0 |    0 |   72  |     0 |
 *   | accepted  |    169 | 169 | 110 | 103 |   44 |    4 |  144  |     4 |
 *   | returned  |      0 |   0 |   0 |   0 |    0 |    0 |   48  |     0 |
 *
 * The domain is the 281 working rows rule 1 did NOT already take (it takes
 * `ceo` AND unreadable-actor rows); 338 working minus 57.
 *
 * The reason per state, because a number with no reason is a magic number
 * with a name:
 *
 *   `filed`     — four days is two full working days past the batch cadence
 *                 the desk actually runs on; an ask nobody blessed in four
 *                 days is not queued, it is forgotten.
 *   `approved`  — the same four days, and this is failure 7 of the design's
 *                 falsifiability table: "approved-undispatched invisible
 *                 (56)". It is the one level that fires today, on 20 rows.
 *   `in_flight` — three days. The longest seat dispatch on this firm's record
 *                 is hours, so a ticket in flight for three days is a seat
 *                 that stopped, not a seat that is slow.
 *   `returned`  — two days. This is the chair's own review obligation and the
 *                 constitution's missing middle state; its domain is 0 today
 *                 because the state was born two days ago.
 *   `accepted`  — six days decided and unexecuted. Longer than the others on
 *                 purpose: execution genuinely queues behind other work, and
 *                 this state holds half the working population.
 *
 * TERMINAL STATES CARRY NO THRESHOLD AND THE MAP SAYS SO WITH `null` RATHER
 * THAN A LARGE NUMBER. Nothing ages after it is finished, and a sentinel like
 * `Infinity` would make "cannot age" indistinguishable from "ages very
 * slowly" at the one place a reader checks.
 */
export const AGE_THRESHOLD_HOURS: Readonly<Record<TicketState, number | null>> = {
  filed: 96,
  approved: 96,
  in_flight: 72,
  returned: 48,
  accepted: 144,
  done: null,
  declined: null,
  superseded: null,
  merged: null,
  expired: null,
};

/**
 * The dollar line above which a ticket reaches the CEO whoever's move it is.
 *
 * **$900, AND THE BASIS IS THE INCIDENT ITSELF.** The row he named as his miss
 * carries `money_at_stake: 915.0` — it is in the record, exactly that value —
 * so any line above $915 would fail to surface the very row that motivated the
 * rule. $900 is the round number immediately below it.
 *
 * SEPARATION MEASURED BEFORE THE LEVEL WAS CHOSEN, over the 281 working rows
 * that are NOT already the CEO's move (a flat curve would mean the line was a
 * tie-break, and this one is not flat — it drops 68 → 5 across the range):
 *
 *   | line | rows added |            | line  | rows added |
 *   |-----:|-----------:|            |------:|-----------:|
 *   | $  0 |         68 |            | $ 750 |         23 |
 *   | $100 |         66 |            | $ 900 |         18 |
 *   | $250 |         56 |            | $1000 |          5 |
 *   | $500 |         52 |            | $2000 |          0 |
 *
 * 177 of those 281 rows carry a readable figure at all; **the other 104 are
 * UNKNOWN and this rule cannot speak for them** — reported as `unknown` on the
 * rule's own report, never folded into the "below the line" count.
 */
export const MONEY_LINE_USD = 900;

/**
 * How long an `accepted` ticket may wait for the dispatch that executes it
 * before it counts as blocked on a missing join.
 *
 * FIVE DAYS, and today the rule is nearly unfireable for a reason that is
 * itself the finding: of the 191 working `accepted` tickets, **154 sit in the
 * `unlinkable_pre_highway` fence** where the record cannot support a link at
 * all, and **not one of the 191 is any other ticket's parent** — so no
 * accepted ticket has a servable dispatch the fold can see. The rule is wired anyway, because the highway's own tickets will carry
 * the link and this is the metric that says whether they do; what must never
 * happen is the rule reporting "0 blocked" from a domain it cannot read.
 */
export const MISSING_JOIN_HOURS = 120;

/** The fenced cohort's marker, published by `tickets.py` on every legacy row
 *  whose parent the record cannot support. Read, never re-spelled. */
export const PRE_HIGHWAY_FENCE = "unlinkable_pre_highway";

/* ------------------------------------------------------------- the rules --- */

export type ExceptionRule =
  | "your_move" | "aged" | "missing_join" | "money" | "challenge";

/** Precedence when several rules fire on one ticket. `your_move` first
 *  because it is the only one that asks him to DO something; the rest are
 *  escalations and their order is the design doc's own. */
export const RULE_ORDER: readonly ExceptionRule[] =
  ["your_move", "money", "aged", "missing_join", "challenge"];

export const RULE_LABEL: Readonly<Record<ExceptionRule, string>> = {
  your_move: "your move",
  aged: "aged past its state's threshold",
  missing_join: "blocked on a missing join",
  money: `at or above the $${MONEY_LINE_USD} line`,
  challenge: "a challenge against a closed ticket",
};

/** Whether a rule puts a row on his DECISION list or in the escalations
 *  block. Only one rule asks him to act. */
export function isDecisionRule(rule: ExceptionRule): boolean {
  return rule === "your_move";
}

/* ------------------------------------------------------------- the rows --- */

/** What a row was ordered on — so the page can say when it was ordered on
 *  nothing instead of implying a ranking it does not have. */
export type RankedOn = "due_date" | "money" | "nothing";

export interface ExceptionRow {
  ticket: Ticket;
  /** Every rule that fired, in `RULE_ORDER`. Never empty. */
  rules: ExceptionRule[];
  /** The first of them. What the row's chip says. */
  primary: ExceptionRule;
  /** The sentence under the chip: WHY this rule fired on THIS row, with the
   *  number that made it fire. "aged" alone is not an explanation. */
  why: string;
  rankedOn: RankedOn;
  /** True when he has already decided it and owes the execution. Split out of
   *  `your_move` because a decision owed and an execution owed are different
   *  acts and putting them in one list is what made the list 57 long. */
  executionOwed: boolean;
}

/* ------------------------------------------------------- the rule checks --- */

function moneyOf(t: Ticket): number | null {
  const m = t.money_at_stake;
  return typeof m === "number" && Number.isFinite(m) ? m : null;
}

function dueOf(t: Ticket): string | null {
  const d = t.due_date;
  return typeof d === "string" && d.trim() ? d.trim() : null;
}

/** Hours in the current state, or null when the fold could not read the
 *  instants. Null is UNKNOWN and never satisfies a threshold — a rule that
 *  fired on an unreadable age would be inventing the measurement it needs. */
function stateAgeOf(t: Ticket): number | null {
  const h = t.age_in_state_hours;
  return typeof h === "number" && Number.isFinite(h) ? h : null;
}

/** Is this ticket's downstream linkage READABLE at all?
 *
 *  The fence is a property of the row the fold publishes; a row inside it has
 *  no parent the record can support, so no conclusion about its joins is
 *  available in either direction. */
export function linkageReadable(t: Ticket): boolean {
  return t.parent_basis !== PRE_HIGHWAY_FENCE;
}

/* ------------------------------------------------------------ the result --- */

/** One rule's own report: what it caught, out of what it could see, out of
 *  what exists. THREE numbers, because "0 caught" means nothing without the
 *  other two — this is the null-test discipline applied to a filter. */
export interface RuleReport {
  rule: ExceptionRule;
  /** Rows this rule surfaced (before precedence — a row several rules caught
   *  is counted by each of them here). */
  caught: number;
  /** Rows this rule was ABLE to judge. */
  evaluable: number;
  /** Rows in the rule's subject population it could NOT judge, because the
   *  input it needs is absent. Never folded into "did not fire". */
  unknown: number;
  /** The whole population the rule looks at. `evaluable + unknown`. */
  domain: number;
  /** The sentence the page prints under the rule's count. */
  note: string;
}

export interface CeoExceptions {
  /** His decisions — undecided, his move. The first screen. */
  decisionOwed: ExceptionRow[];
  /** He decided; the execution is his. Shown, separately, never counted as a
   *  decision. */
  executionOwed: ExceptionRow[];
  /** Rules 2–5: nobody is asking him to act, but these crossed a line. */
  escalated: ExceptionRow[];
  /** Working tickets no rule surfaced. The board he visits by choice. */
  board: Ticket[];
  /** Terminal tickets. Never awaiting anyone, never counted, never controlled. */
  record: Ticket[];
  reports: RuleReport[];
  /** How many rows on his decision list carry neither a date nor a figure, so
   *  their order is arrival order and not a ranking. The number his own
   *  payload printed and nothing acted on. */
  rankedOnNothing: number;
  /** Every working ticket is in exactly one of `decisionOwed` /
   *  `executionOwed` / `escalated` / `board`; every terminal one is in
   *  `record`. Published so a caller can assert it rather than trust it. */
  totals: {
    all: number; working: number; terminal: number;
    decisionOwed: number; executionOwed: number; escalated: number;
    board: number; record: number;
  };
  version: string;
}

/* --------------------------------------------------------------- the fold --- */

function ruleWhy(rule: ExceptionRule, t: Ticket, nowIso: string): string {
  switch (rule) {
    case "your_move":
      return t.next_actor_why || "the spine routes this ticket to the CEO";
    case "money": {
      const m = moneyOf(t);
      return m === null
        ? `at or above the $${MONEY_LINE_USD} line`
        : `$${m.toLocaleString("en-US", { maximumFractionDigits: 2 })} at stake, `
          + `at or above the $${MONEY_LINE_USD} line`;
    }
    case "aged": {
      const h = stateAgeOf(t);
      const lvl = AGE_THRESHOLD_HOURS[t.state];
      return h === null || lvl === null
        ? `has aged past the threshold for ${t.state}`
        : `${h.toFixed(0)}h in ${t.state} — past the ${lvl}h threshold for `
          + `that state`;
    }
    case "missing_join":
      return `accepted more than ${MISSING_JOIN_HOURS}h ago and the record `
        + "carries no dispatch that serves it";
    case "challenge": {
      const target = t.parent_id ? ` (targets ${t.parent_id})` : "";
      return `a challenge filed against a closed ticket${target}`;
    }
  }
  // Unreachable for the closed union above; a default that invented a
  // sentence would hide a new rule that forgot to add one.
  void nowIso;
  return "";
}

function rankedOnOf(t: Ticket): RankedOn {
  if (dueOf(t)) return "due_date";
  if (moneyOf(t) !== null) return "money";
  return "nothing";
}

/**
 * Order within a block: dated first (soonest first), then by money (largest
 * first), then arrival order (oldest first).
 *
 * A ROUNDED FIELD IS NOT A SORT KEY and neither is a partial one: rows that
 * tie on every key above fall back to `filed_at` and then to `ticket_id`, so
 * the order is TOTAL. A stable sort over a partial key hands the order to
 * whatever the fold happened to produce, which is how a "longest ignored"
 * board once led with its newest row.
 */
function compareRows(a: ExceptionRow, b: ExceptionRow): number {
  const ad = dueOf(a.ticket), bd = dueOf(b.ticket);
  if (ad !== bd) {
    if (ad === null) return 1;
    if (bd === null) return -1;
    if (ad !== bd) return ad < bd ? -1 : 1;
  }
  const am = moneyOf(a.ticket), bm = moneyOf(b.ticket);
  if (am !== bm) {
    if (am === null) return 1;
    if (bm === null) return -1;
    return bm - am;
  }
  const af = a.ticket.filed_at ?? "", bf = b.ticket.filed_at ?? "";
  if (af !== bf) return af < bf ? -1 : 1;
  return a.ticket.ticket_id < b.ticket.ticket_id ? -1 : 1;
}

/**
 * Apply the five rules to one folded ticket population.
 *
 * @param tickets the fold's rows, or null when the read has not returned or
 *   failed. Null in, null out: a filter over an unread population would
 *   report an empty desk, which is the one answer that must never be
 *   fabricated.
 * @param nowIso the instant to age against. Passed in rather than read from
 *   the clock so a test can pin it — and so the page ages against the fold's
 *   own `at`, not against the browser's clock, when the two disagree.
 */
export function ceoExceptions(
  tickets: readonly Ticket[] | null | undefined,
  nowIso: string,
): CeoExceptions | null {
  if (!tickets) return null;

  const working = tickets.filter((t) => !t.terminal);
  const record = tickets.filter((t) => t.terminal);

  // --- rule 1: whose move is it. The spine's answer, read not re-derived.
  //     An UNREADABLE actor counts toward him: this desk's oldest rule, and
  //     three rows are in that state today (a seat name the spine's actor
  //     vocabulary does not contain).
  const yourMove = (t: Ticket) =>
    t.next_actor === "ceo" || t.next_actor === "unknown";

  // --- rule 4: money.
  const moneyKnown = working.filter((t) => moneyOf(t) !== null);
  const overLine = (t: Ticket) => {
    const m = moneyOf(t);
    return m !== null && m >= MONEY_LINE_USD;
  };

  // --- rule 2: aged past its state's threshold.
  const ageEvaluable = working.filter(
    (t) => stateAgeOf(t) !== null && AGE_THRESHOLD_HOURS[t.state] !== null);
  const aged = (t: Ticket) => {
    const h = stateAgeOf(t);
    const lvl = AGE_THRESHOLD_HOURS[t.state];
    return h !== null && lvl !== null && h >= lvl;
  };

  // --- rule 3: blocked on a missing join.
  //     THE SUBJECT POPULATION IS `accepted` TICKETS, and the rule can only
  //     speak about one whose linkage the record supports. Everything else is
  //     UNKNOWN — not "not blocked".
  const acceptedRows = working.filter((t) => t.state === "accepted");
  const joinEvaluable = acceptedRows.filter(linkageReadable);
  const servedIds = new Set<string>();
  for (const t of tickets) {
    if (t.parent_id) servedIds.add(t.parent_id);
  }
  const missingJoin = (t: Ticket) => {
    if (t.state !== "accepted" || !linkageReadable(t)) return false;
    const h = stateAgeOf(t);
    if (h === null || h < MISSING_JOIN_HOURS) return false;
    return !servedIds.has(t.ticket_id);
  };

  // --- rule 5: a challenge against a terminal.
  const challengeRows = working.filter((t) => t.type === "challenge");
  const terminalIds = new Set(record.map((t) => t.ticket_id));
  const challengeAgainstTerminal = (t: Ticket) =>
    t.type === "challenge" && !!t.parent_id && terminalIds.has(t.parent_id);

  const CHECKS: Readonly<Record<ExceptionRule, (t: Ticket) => boolean>> = {
    your_move: yourMove,
    money: overLine,
    aged,
    missing_join: missingJoin,
    challenge: challengeAgainstTerminal,
  };

  // How many accepted tickets are served by SOMETHING. Zero means the rule
  // above is reading a missing mechanism, and its note says so.
  const servedAccepted = acceptedRows.filter(
    (t) => servedIds.has(t.ticket_id)).length;

  const decisionOwed: ExceptionRow[] = [];
  const executionOwed: ExceptionRow[] = [];
  const escalated: ExceptionRow[] = [];
  const board: Ticket[] = [];
  const caught: Record<ExceptionRule, number> = {
    your_move: 0, money: 0, aged: 0, missing_join: 0, challenge: 0,
  };

  for (const t of working) {
    const rules = RULE_ORDER.filter((r) => CHECKS[r](t));
    for (const r of rules) caught[r] += 1;
    if (rules.length === 0) { board.push(t); continue; }
    const primary = rules[0];
    const row: ExceptionRow = {
      ticket: t,
      rules,
      primary,
      why: ruleWhy(primary, t, nowIso),
      rankedOn: rankedOnOf(t),
      // `decided` survives the move out of `filed`, so this is "he has said
      // yes and the doing is his", not "the row's state happens to be
      // accepted". A row he decided and the CHAIR must execute is not here at
      // all — rule 1 never selected it.
      executionOwed: t.decided,
    };
    if (!isDecisionRule(primary)) escalated.push(row);
    else if (row.executionOwed) executionOwed.push(row);
    else decisionOwed.push(row);
  }

  decisionOwed.sort(compareRows);
  executionOwed.sort(compareRows);
  escalated.sort(compareRows);

  const reports: RuleReport[] = [
    {
      rule: "your_move",
      caught: caught.your_move,
      evaluable: working.length,
      unknown: 0,
      domain: working.length,
      note: "the spine resolved the next actor on every working ticket; rows "
        + "whose actor could not be read count toward him, not away from him",
    },
    {
      rule: "money",
      caught: caught.money,
      evaluable: moneyKnown.length,
      unknown: working.length - moneyKnown.length,
      domain: working.length,
      note: `${working.length - moneyKnown.length} working ticket(s) carry no `
        + "readable figure, so this rule cannot speak for them — they are "
        + "UNKNOWN, not below the line",
    },
    {
      rule: "aged",
      caught: caught.aged,
      evaluable: ageEvaluable.length,
      unknown: working.length - ageEvaluable.length,
      domain: working.length,
      note: `levels: ${(Object.keys(AGE_THRESHOLD_HOURS) as TicketState[])
        .filter((s) => AGE_THRESHOLD_HOURS[s] !== null)
        .map((s) => `${s} ${AGE_THRESHOLD_HOURS[s]}h`).join(", ")}`,
    },
    {
      rule: "missing_join",
      caught: caught.missing_join,
      evaluable: joinEvaluable.length,
      unknown: acceptedRows.length - joinEvaluable.length,
      domain: acceptedRows.length,
      note: joinEvaluable.length === 0
        ? `no accepted ticket carries linkage the record supports — all `
          + `${acceptedRows.length} are inside the pre-highway fence, so this `
          + "rule reports UNKNOWN and never 'nothing is blocked'"
        : `${joinEvaluable.length} of ${acceptedRows.length} accepted `
          + "ticket(s) carry linkage the record supports; the rest are fenced"
          // WHAT THE RULE IS ACTUALLY MEASURING, WHEN THE MECHANISM ITSELF IS
          // MISSING. If NOT ONE accepted ticket anywhere is served by a
          // downstream ticket, then "no dispatch serves this one" is a fact
          // about the highway not yet writing that link — not a fact about
          // this row being stuck. Both readings are true and only one is
          // actionable, so the surface must not present the first as the
          // second. Measured 2026-08-26: 0 of 191.
          + (servedAccepted === 0
            ? ` — but NO accepted ticket in the whole record is served by a `
              + `downstream ticket (0 of ${acceptedRows.length}), so this `
              + "count measures a link the highway does not write yet as much "
              + "as it measures stuck work"
            : ``),
    },
    {
      rule: "challenge",
      caught: caught.challenge,
      evaluable: challengeRows.length,
      unknown: 0,
      domain: challengeRows.length,
      note: challengeRows.length === 0
        ? "no ticket of type `challenge` exists yet, so this rule has an "
          + "empty domain — a zero from an empty domain is not a finding"
        : `${challengeRows.length} challenge ticket(s) exist`,
    },
  ];

  return {
    decisionOwed,
    executionOwed,
    escalated,
    board,
    record,
    reports,
    rankedOnNothing: decisionOwed.filter((r) => r.rankedOn === "nothing").length,
    totals: {
      all: tickets.length,
      working: working.length,
      terminal: record.length,
      decisionOwed: decisionOwed.length,
      executionOwed: executionOwed.length,
      escalated: escalated.length,
      board: board.length,
      record: record.length,
    },
    version: CEO_EXCEPTIONS_VERSION,
  };
}

/**
 * The sentence the page prints under his decision count.
 *
 * IT NEVER SAYS "0 rows" WHEN THE READ HAS NOT HAPPENED — the caller passes
 * `null` for an unread population and gets a null back, and the page then
 * renders its read-state sentence instead of a number.
 */
export function exceptionsNote(x: CeoExceptions | null): string | null {
  if (!x) return null;
  const parts: string[] = [];
  parts.push(`${x.totals.decisionOwed} decision(s) await you`);
  if (x.totals.executionOwed) {
    parts.push(`${x.totals.executionOwed} you decided and owe the execution on`);
  }
  if (x.rankedOnNothing) {
    parts.push(`${x.rankedOnNothing} of the decisions state neither a date nor `
      + "a figure, so their order is arrival order and not a ranking");
  }
  if (x.totals.escalated) {
    parts.push(`${x.totals.escalated} escalation(s) crossed a line without `
      + "being anyone's ask of you");
  }
  parts.push(`${x.totals.board} working ticket(s) are on the board and `
    + `${x.totals.record} are closed`);
  return parts.join("; ") + ".";
}
