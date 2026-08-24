/**
 * A RECORD ROW — a desk row nobody owes a move on.
 *
 * THE INCIDENT (CEO, 2026-08-24, on his own desk, verbatim): *"like WTF"* — an
 * already-executed chair action rendered with **Accept** and **Reject** beside
 * it. The row was `run-coo-triage8` rec 7, a `finding` filed for the record:
 * its status is `open`, its `next_actor_resolved` is `nobody`, and the spine
 * says so in three separate fields (`next_actor_basis: "explicit"`,
 * `next_actor_why`, `desk_stage: "owned_elsewhere"`). Every surface that
 * rendered it read exactly one of them — `status === "open"` — and offered a
 * decision on a thing that had no decision left in it.
 *
 * SEPARATE COUNTING FROM CONTROL EXISTENCE. That is the whole lesson of D39's
 * P-2, where one flag answered both "whose move is it" and "does this control
 * exist", and routing a request to the chair silently removed the CEO's own
 * approve button. Here the two answers point the other way and must still be
 * asked separately: a record row is not counted (the CEO desk's `stageOfItem`
 * already routes it to `owned_elsewhere`) AND its controls must not exist.
 * `desk/page.tsx` and `desk/[seat]/page.tsx` had the first half wrong too —
 * both counted it under "awaiting a decision".
 *
 * NOTHING HERE IS RE-DERIVED. `nobody` is the spine's own answer, published on
 * `next_actor_resolved` by `app/fund/desk.py::next_actor`. This module reads
 * it and never guesses one: a row that states no actor is NOT a record row,
 * because "the spine did not say" and "the spine said nobody" are different
 * facts and only the second one closes a row.
 */

/** The fields this module reads. Structural rather than the full
 *  `DeskRecommendation` so a test can build one without the other forty. */
export interface RoutedRec {
  status?: string | null;
  next_actor_resolved?: string | null;
  next_actor?: string | null;
  next_actor_why?: string | null;
}

/** The spine's word for "this row is finished; nobody's move is next". */
export const NOBODY = "nobody";

/** Whose move the spine says it is, or null when it did not say.
 *
 *  `next_actor_resolved` is the resolved answer and wins; `next_actor` is the
 *  raw declaration a seat filed and is the fallback for a payload that
 *  predates resolution. Empty strings are absence, not an actor. */
export function routedActor(r: RoutedRec | null | undefined): string | null {
  const v = r?.next_actor_resolved ?? r?.next_actor ?? null;
  if (typeof v !== "string") return null;
  const t = v.trim();
  return t ? t : null;
}

/**
 * Is this a row filed for the record — no decision owed, by the spine's word?
 *
 * DELIBERATELY INDEPENDENT OF STATUS. A record row's status is `open`, which
 * is exactly why every surface got it wrong: `open` means "not decided", and
 * this row will never be decided because there is nothing to decide. Reading
 * status here would re-create the bug in the guard meant to stop it.
 */
export function isRecordRow(r: RoutedRec | null | undefined): boolean {
  return routedActor(r) === NOBODY;
}

/**
 * The sentence a record row renders where its buttons used to be.
 *
 * The spine's own `next_actor_why` rides along when it sent one, because the
 * reason a row is closed belongs beside the claim that it is — but the leading
 * sentence is OURS and is fixed, so a spine that sends no reason still renders
 * a statement rather than a blank where two buttons were.
 */
export function recordRowNote(r: RoutedRec | null | undefined): string {
  const why = (r?.next_actor_why ?? "").trim();
  const head = "Filed for the record — no decision is owed";
  return why ? `${head} · ${why}` : head;
}

/**
 * Split a seat's or a day's recommendations into the three things they
 * actually are.
 *
 * `awaiting` is what a heading may call "awaiting a decision"; `record` is
 * open-but-closed; `decided` is everything the CEO already said yes to. The
 * three are exhaustive and disjoint, which a test asserts by cardinality —
 * a split that silently dropped a row would otherwise look like a tidier desk.
 */
export function splitRecordRows<T extends RoutedRec>(recs: readonly T[]): {
  awaiting: T[]; record: T[]; decided: T[];
} {
  const awaiting: T[] = [];
  const record: T[] = [];
  const decided: T[] = [];
  for (const r of recs) {
    if (r?.status !== "open") decided.push(r);
    else if (isRecordRow(r)) record.push(r);
    else awaiting.push(r);
  }
  return { awaiting, record, decided };
}
