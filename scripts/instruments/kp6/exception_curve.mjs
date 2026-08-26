/**
 * THE SEPARATION CURVES BEHIND `ticketExceptions.ts`'s LEVELS — reproducible.
 *
 * WHY IT SHIPS IN THE REPO. Six pixel figures in `studio/desk/**` cite probe
 * scripts that lived in a session temp directory and are uncheckable today. A
 * threshold's basis is worth more than a pixel's, so the two tables in
 * `ticketExceptions.ts` — the per-state age curve and the money curve — get an
 * instrument that regenerates them and a reader who doubts a level can run it.
 *
 * BEFORE CHOOSING A LEVEL, MEASURE WHETHER THE STATISTIC SEPARATES AT ALL. A
 * flat curve means the level is a tie-break wearing a measurement's clothes,
 * and the rule "pick the lowest that holds" then hands you the most permissive
 * value by default. This prints the curve so the flatness is visible.
 *
 * USAGE
 *   node scripts/instruments/kp6/exception_curve.mjs <tickets.json>
 *   node scripts/instruments/kp6/exception_curve.mjs --url http://127.0.0.1:8090
 *   node scripts/instruments/kp6/exception_curve.mjs --null
 *
 * `<tickets.json>` is a saved `GET /api/v1/fund/tickets?limit=5000` body.
 *
 * THE NULL MODE IS NOT DECORATION. `--null` runs every curve over an EMPTY
 * ticket list and asserts each one is zero at every level, and it PRINTS THE
 * DOMAIN SIZE IT COMPARED — a zero with no domain behind it is a vacuous pass,
 * and this repo has shipped two of those. It exits non-zero if any curve
 * returns a non-zero over nothing, or if the domain it walked was empty for a
 * reason other than the empty input.
 */

const AGE_LEVELS = [48, 72, 96, 120, 144, 168];
const MONEY_LEVELS = [0.01, 100, 250, 500, 750, 900, 1000, 2000];
const STATES = ["filed", "approved", "in_flight", "returned", "accepted"];

function num(v) {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/** Rows the CEO is not already the next actor on: the population every
 *  escalation rule is judged over. Rule 1 owns the rest by construction. */
function escalationPopulation(tickets) {
  return tickets.filter(
    (t) => !t.terminal && t.next_actor !== "ceo" && t.next_actor !== "unknown");
}

export function ageCurve(tickets) {
  const pop = escalationPopulation(tickets);
  const out = {};
  for (const s of STATES) {
    const rows = pop.filter((t) => t.state === s);
    out[s] = {
      domain: rows.length,
      unknownAge: rows.filter((t) => num(t.age_in_state_hours) === null).length,
      at: Object.fromEntries(AGE_LEVELS.map((h) => [
        h, rows.filter((t) => (num(t.age_in_state_hours) ?? -1) >= h).length,
      ])),
    };
  }
  return out;
}

export function moneyCurve(tickets) {
  const pop = escalationPopulation(tickets);
  return {
    domain: pop.length,
    readable: pop.filter((t) => num(t.money_at_stake) !== null).length,
    unknown: pop.filter((t) => num(t.money_at_stake) === null).length,
    at: Object.fromEntries(MONEY_LEVELS.map((y) => [
      y, pop.filter((t) => (num(t.money_at_stake) ?? -Infinity) >= y).length,
    ])),
  };
}

/** The band inside which ANY per-state level discriminates. Outside it a level
 *  either admits the whole state or can never fire, and saying which is the
 *  point of publishing it. */
export function ageBand(tickets) {
  const ages = tickets
    .filter((t) => !t.terminal)
    .map((t) => num(t.age_in_state_hours))
    .filter((h) => h !== null);
  return ages.length
    ? { n: ages.length, min: Math.min(...ages), max: Math.max(...ages) }
    : { n: 0, min: null, max: null };
}

/** How much of the join rule's subject population is even readable. */
export function joinCoverage(tickets) {
  const accepted = tickets.filter((t) => !t.terminal && t.state === "accepted");
  const readable = accepted.filter(
    (t) => t.parent_basis !== "unlinkable_pre_highway");
  const parents = new Set(tickets.map((t) => t.parent_id).filter(Boolean));
  return {
    accepted: accepted.length,
    linkageReadable: readable.length,
    fenced: accepted.length - readable.length,
    acceptedThatAreSomeonesParent:
      accepted.filter((t) => parents.has(t.ticket_id)).length,
  };
}

function table(label, obj) {
  console.log(`\n${label}`);
  console.log(JSON.stringify(obj, null, 1));
}

async function load(argv) {
  const urlFlag = argv.indexOf("--url");
  if (urlFlag !== -1) {
    const base = argv[urlFlag + 1];
    const r = await fetch(`${base}/api/v1/fund/tickets?limit=5000`);
    if (!r.ok) throw new Error(`${base} answered ${r.status} for /fund/tickets`);
    return (await r.json()).tickets ?? [];
  }
  const file = argv.find((a) => !a.startsWith("--"));
  if (!file) {
    console.error("usage: exception_curve.mjs <tickets.json> | --url <base> | --null");
    process.exit(2);
  }
  const fs = await import("node:fs");
  const body = JSON.parse(fs.readFileSync(file, "utf8"));
  return Array.isArray(body) ? body : (body.tickets ?? []);
}

async function main() {
  const argv = process.argv.slice(2);

  if (argv.includes("--null")) {
    // THE DOMAIN IS STATED WITH THE ZERO. Over an empty population every curve
    // must be zero at every level AND must have walked the levels it claims to
    // — a curve that returned {} would also "be all zeroes".
    const empty = [];
    const a = ageCurve(empty), m = moneyCurve(empty), j = joinCoverage(empty);
    let compared = 0, bad = [];
    for (const s of STATES) {
      for (const h of AGE_LEVELS) {
        compared += 1;
        if (a[s].at[h] !== 0) bad.push(`age ${s}@${h}h = ${a[s].at[h]}`);
      }
    }
    for (const y of MONEY_LEVELS) {
      compared += 1;
      if (m.at[y] !== 0) bad.push(`money@$${y} = ${m.at[y]}`);
    }
    for (const [k, v] of Object.entries(j)) {
      compared += 1;
      if (v !== 0) bad.push(`join.${k} = ${v}`);
    }
    const expected = STATES.length * AGE_LEVELS.length + MONEY_LEVELS.length + 4;
    console.log(`NULL TEST: compared ${compared} cell(s) over an empty ticket `
      + `population (expected ${expected}); ${bad.length} non-zero.`);
    if (compared !== expected) {
      console.error(`REFUSING: walked ${compared} cells, not ${expected} — the `
        + "null test's own domain is wrong, so its zero means nothing.");
      process.exit(1);
    }
    if (bad.length) { console.error(bad.join("\n")); process.exit(1); }
    console.log("PASS — every curve is zero over nothing, and the domain is stated.");
    return;
  }

  const tickets = await load(argv);
  console.log(`tickets: ${tickets.length}; working: `
    + `${tickets.filter((t) => !t.terminal).length}; escalation population: `
    + `${escalationPopulation(tickets).length}`);
  table("AGE BAND (working rows, age_in_state_hours)", ageBand(tickets));
  table("AGE CURVE (rows at or past each level, escalation population)",
    ageCurve(tickets));
  table("MONEY CURVE (rows at or above each line, escalation population)",
    moneyCurve(tickets));
  table("JOIN COVERAGE (the missing-join rule's readable domain)",
    joinCoverage(tickets));
}

if (import.meta.url === `file://${process.argv[1].replace(/\\/g, "/")}`
    || process.argv[1].endsWith("exception_curve.mjs")) {
  main().catch((e) => { console.error(e); process.exit(1); });
}
