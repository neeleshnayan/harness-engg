/**
 * THE EXCEPTIONS FILTER, RUN AGAINST A REAL FOLD — the live-corpus check.
 *
 * WHY THIS IS AN INSTRUMENT AND NOT A CHECKED-IN FIXTURE. The ticket
 * population MOVES: it grew 695 -> 696 inside forty minutes during the fold's
 * first dispatch, and every count below is a traffic reading, not a constant.
 * A 1.3 MB corpus checked into the suite would pin a number that is false by
 * the next hour and would tell a future reader that a moving figure is a
 * fixed one. So the unit tests pin the INVARIANTS on hand-built rows, and this
 * runs the same code over whatever the spine actually holds.
 *
 * USAGE
 *   node --experimental-strip-types scripts/instruments/kp6/verify_exceptions.mts <tickets.json>
 *   node --experimental-strip-types scripts/instruments/kp6/verify_exceptions.mts --url http://127.0.0.1:8091
 *
 * WHAT IT ASSERTS (exit 1 on any failure — it is a check, not a printout):
 *   1. the split is exhaustive and disjoint over the real population;
 *   2. `decisionOwed + executionOwed` equals the fold's own count of tickets
 *      whose next actor is the CEO or unreadable — the two derivations of
 *      "his rows" must agree, and this is the reconciliation the highway's
 *      first slice made the standard;
 *   3. no terminal ticket appears in any awaiting bucket;
 *   4. every surfaced row carries a rule and a non-empty reason.
 */

import {
  ceoExceptions, exceptionsNote,
} from "../../../src/app/clark/studio/desk/ticketExceptions.ts";

type AnyTicket = Parameters<typeof ceoExceptions>[0] extends
  readonly (infer T)[] | null | undefined ? T : never;

async function load(argv: string[]): Promise<{ tickets: AnyTicket[];
                                               counts: Record<string, any> }> {
  const i = argv.indexOf("--url");
  if (i !== -1) {
    const r = await fetch(`${argv[i + 1]}/api/v1/fund/tickets?limit=5000`);
    if (!r.ok) throw new Error(`answered ${r.status} for /fund/tickets`);
    const body = await r.json();
    return { tickets: body.tickets ?? [], counts: body.counts ?? {} };
  }
  const file = argv.find((a) => !a.startsWith("--"));
  if (!file) {
    console.error("usage: verify_exceptions.mts <tickets.json> | --url <base>");
    process.exit(2);
  }
  const fs = await import("node:fs");
  const body = JSON.parse(fs.readFileSync(file, "utf8"));
  return { tickets: body.tickets ?? [], counts: body.counts ?? {} };
}

const { tickets, counts } = await load(process.argv.slice(2));
const now = new Date().toISOString();
const x = ceoExceptions(tickets, now)!;
const fail: string[] = [];

// 1 — the partition.
const sum = x.totals.decisionOwed + x.totals.executionOwed + x.totals.escalated
  + x.totals.board + x.totals.record;
if (sum !== tickets.length) {
  fail.push(`partition: buckets sum to ${sum}, population is ${tickets.length}`);
}
const ids = [
  ...x.decisionOwed.map((r) => r.ticket.ticket_id),
  ...x.executionOwed.map((r) => r.ticket.ticket_id),
  ...x.escalated.map((r) => r.ticket.ticket_id),
  ...x.board.map((t) => t.ticket_id),
  ...x.record.map((t) => t.ticket_id),
];
if (new Set(ids).size !== tickets.length) {
  fail.push(`disjointness: ${ids.length} placements over `
    + `${new Set(ids).size} distinct ids`);
}

// 2 — reconciliation against the fold's OWN actor census, which is computed by
//     different code on the other side of the wire.
const foldsCeo = (counts.by_next_actor?.ceo ?? 0)
  + (counts.by_next_actor?.unknown ?? 0);
const foldsTerminalCeo = x.record.filter(
  (t) => t.next_actor === "ceo" || t.next_actor === "unknown").length;
const mine = x.totals.decisionOwed + x.totals.executionOwed;
if (mine !== foldsCeo - foldsTerminalCeo) {
  fail.push(`reconciliation: I place ${mine} row(s) on his desk; the fold's own `
    + `census says ${foldsCeo} minus ${foldsTerminalCeo} terminal = `
    + `${foldsCeo - foldsTerminalCeo}`);
}

// 3 — terminal is terminal.
for (const bucket of [x.decisionOwed, x.executionOwed, x.escalated]) {
  for (const r of bucket) {
    if (r.ticket.terminal) {
      fail.push(`terminal ticket ${r.ticket.ticket_id} is in an awaiting bucket`);
    }
  }
}
for (const t of x.board) {
  if (t.terminal) fail.push(`terminal ticket ${t.ticket_id} is on the board`);
}

// 4 — every surfaced row explains itself.
for (const r of [...x.decisionOwed, ...x.executionOwed, ...x.escalated]) {
  if (!r.rules.length) fail.push(`${r.ticket.ticket_id} surfaced with no rule`);
  if (!r.why.trim()) fail.push(`${r.ticket.ticket_id} surfaced with no reason`);
}

console.log(`population ${tickets.length}: decisions ${x.totals.decisionOwed}, `
  + `executions ${x.totals.executionOwed}, escalations ${x.totals.escalated}, `
  + `board ${x.totals.board}, record ${x.totals.record}`);
console.log(`note: ${exceptionsNote(x)}`);
console.log("rule reports:");
for (const r of x.reports) {
  console.log(`  ${r.rule.padEnd(13)} caught ${String(r.caught).padStart(4)}  `
    + `evaluable ${String(r.evaluable).padStart(4)}  `
    + `unknown ${String(r.unknown).padStart(4)}  `
    + `domain ${String(r.domain).padStart(4)}`);
}
if (fail.length) {
  console.error(`\nFAIL (${fail.length}):`);
  for (const f of fail) console.error(`  - ${f}`);
  process.exit(1);
}
console.log(`\nPASS — ${4} invariant(s) checked over ${tickets.length} real `
  + "ticket(s).");
