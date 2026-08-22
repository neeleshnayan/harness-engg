/**
 * Faces — who is in the room, drawn.
 *
 * The CEO's ask (brief docs/briefs/HUMAN_OFFICE_2026-08-20.md): humanise the
 * bench. "A human type org where you have desks and you can see what each desk
 * is doing." A face is how a human indexes a colleague, so the ONE rule this
 * file exists to enforce is that a face is ASSIGNED and never generated:
 *
 *   1. **Deterministic.** `faceFor("pm")` returns the same spec forever. The
 *      renderer is a pure function of the spec, so the pm's face on a desk
 *      card, a memo card, a wire row and its seat header are the same drawing.
 *   2. **Unique.** No two actors share a (head, eyes, mouth, feature) tuple —
 *      two colleagues with the same face is a lie the eye believes instantly.
 *      A test asserts this over the whole registry.
 *   3. **Absent is absent.** An actor with no registered face gets NO face —
 *      not a hash-generated one. `faceFor` returns null and the component draws
 *      a dashed, featureless head that says "no face on file". Inventing a
 *      portrait for an unrecognised actor is the same class of error as
 *      rendering an unknown number as zero.
 *
 * Why the registry is hand-written and small: the event log's `actor` field is
 * free text and is already carrying things that are not identities at all (one
 * live row's actor is a 200-character sentence explaining a declined ticket).
 * A prefix match would happily give "cto-stale-guard: the GLD position…" the
 * CTO's face and quietly attribute a machine's note to a person. So matching is
 * exact, with two narrow, versioned exceptions below — both tested.
 *
 * Colour: none. Every path strokes `currentColor`, so a face takes the token
 * colour of whatever it sits in and cannot introduce a hue. Per theme.ts,
 * hierarchy comes from type and space.
 */

/** Silhouette. Humans are round or oval; machines are square. That is not
 *  decoration — it is the same distinction the Studio already draws in colour
 *  between a number the fund computed and a sentence a model wrote
 *  (studio-theme.css, "violet is the machine"). A reader must never mistake the
 *  auto-policy for a person. */
export type FaceHead = "round" | "oval" | "square";
export type FaceEyes = "dots" | "wide" | "lines";
export type FaceMouth = "smile" | "small" | "flat";

/** The one distinguishing mark. Line-drawn, in the same stroke as the head. */
export type FaceFeature =
  | "none"
  | "antenna"     // mechanism — the idea
  | "book"        // analyst — the corpus
  | "pen"         // pm — the memo
  | "curve"       // quant — the equity curve the belt judges
  | "magnifier"   // adversary — the thing that looks closer
  | "glasses"     // validator — reads the instruments
  | "shield"      // riskofficer — supervises the envelope
  | "hammer"      // builder — harness engineering
  | "tie"         // ceo
  | "headset"     // cto — the session at the console
  | "gear"        // worker — the background loop
  | "spark"       // clark — the assistant
  | "bolt";       // auto-policy — deterministic execution

/** What kind of thing acted. Rendered in the tooltip so the silhouette rule is
 *  legible and not merely felt. */
export type FaceKind = "seat" | "human" | "machine";

export interface FaceSpec {
  id: string;
  /** How the office refers to them. */
  label: string;
  /** One line: what they are. Becomes the face's accessible name. */
  role: string;
  kind: FaceKind;
  head: FaceHead;
  eyes: FaceEyes;
  mouth: FaceMouth;
  feature: FaceFeature;
}

/**
 * The registry. Seats first, in the order the constitution lists the bench,
 * then the humans and machines that appear as `actor` on desk events.
 *
 * Only actors VERIFIED on the live log or named in the constitution are here.
 * `GET /fund/events` on 2026-08-20 returns desk events with actor ∈ {ceo, cto}
 * only; the rest of the list (operator, worker, system, clark, auto-policy-v1)
 * comes from the wider log and is registered so those faces exist the day a
 * desk surface starts showing them. Anything else is deliberately faceless.
 */
export const FACES: Readonly<Record<string, FaceSpec>> = Object.freeze({
  mechanism: {
    id: "mechanism", label: "mechanism", kind: "seat",
    role: "proposes edges with a named counterparty",
    head: "round", eyes: "dots", mouth: "small", feature: "antenna",
  },
  analyst: {
    id: "analyst", label: "analyst", kind: "seat",
    role: "builds evidence-grounded theses from the corpus",
    head: "oval", eyes: "dots", mouth: "smile", feature: "book",
  },
  pm: {
    id: "pm", label: "pm", kind: "seat",
    role: "owns the book analytically; writes the decision memo",
    head: "round", eyes: "dots", mouth: "smile", feature: "pen",
  },
  quant: {
    id: "quant", label: "quant", kind: "seat",
    role: "translates approved ideas into algorithms and runs the belt",
    head: "oval", eyes: "dots", mouth: "flat", feature: "curve",
  },
  adversary: {
    id: "adversary", label: "adversary", kind: "seat",
    role: "tries to kill any artifact, blind to its author",
    head: "round", eyes: "wide", mouth: "flat", feature: "magnifier",
  },
  validator: {
    id: "validator", label: "validator", kind: "seat",
    role: "audits the fund's own instruments",
    head: "oval", eyes: "wide", mouth: "small", feature: "glasses",
  },
  riskofficer: {
    id: "riskofficer", label: "riskofficer", kind: "seat",
    role: "supervises the auto-approval policy after the fact",
    head: "round", eyes: "wide", mouth: "small", feature: "shield",
  },
  builder: {
    id: "builder", label: "builder", kind: "seat",
    role: "harness engineering, in an isolated worktree",
    head: "oval", eyes: "dots", mouth: "small", feature: "hammer",
  },
  coo: {
    // The market veteran who triages the CEO's desk (seated 2026-08-20).
    // Named VISHESH by CEO decision the same day ("so he doesn't feel left
    // out") — the seat carries a colleague's name the way the CTO carries its
    // model's. Wears the tie like the ceo — same room, same suits — but the
    // oval head, line eyes and flat mouth are the veteran's: seen every
    // cycle, moved by none of them. Tuple unique; the registry test enforces.
    id: "coo", label: "Vishesh", kind: "seat",
    role: "COO — triages the desk into batch decisions; endorses, never decides",
    head: "oval", eyes: "lines", mouth: "flat", feature: "tie",
  },

  secretary: {
    // Seated 2026-08-20 (CEO decision) and named DONNA the same day, the way
    // the COO seat carries Vishesh. Given a face 2026-08-21 with her floor desk
    // and seat page — before this she rendered FACELESS on the CEO's desk, and
    // an unattributed note is a note nobody can place.
    //
    // The `book` feature is the corpus; hers is the RECORD, which is the same
    // gesture — a bound thing that is read, not decided. Tuple stays unique via
    // the round head + line eyes + small mouth combination; the registry test
    // enforces it.
    id: "secretary", label: "Donna", kind: "seat",
    role: "documents each day from the record; never decides",
    head: "round", eyes: "lines", mouth: "small", feature: "book",
  },

  cfo: {
    // Seated 2026-08-22 (CEO decision) and named GRACE the same day, for
    // Hopper. Given a desk in the EXECUTIVE ROW rather than on the bench: the
    // constitution's executive table seats her and the COO as peers who advise
    // the CEO on the same decisions from different axes.
    //
    // THE FEATURE IS SHARED WITH THE QUANT AND THAT IS A COMPROMISE, NAMED.
    // The mark this seat wants is Hopper's nanosecond — 11.8 inches of wire, a
    // short straight segment — and adding a `wire` glyph means a new case in
    // SeatFace.tsx, which is outside this dispatch's file boundary. `curve` is
    // the nearest true meaning available (her memo's central artifact is a
    // meter and a critical path, both curves) and the TUPLE is what the
    // registry's uniqueness rule actually enforces: oval/lines/small/curve is
    // held by nobody. Replace it with `wire` the first time SeatFace.tsx is
    // legitimately open.
    id: "cfo", label: "Grace", kind: "seat",
    role: "what each seat costs and what it bought; judges work by whether it moves the date",
    head: "oval", eyes: "lines", mouth: "small", feature: "curve",
  },

  ceo: {
    id: "ceo", label: "Neelesh", kind: "human",
    role: "CEO — risk appetite, identity, and every approval click",
    head: "round", eyes: "dots", mouth: "smile", feature: "tie",
  },
  cto: {
    id: "cto", label: "Fable", kind: "human",
    role: "CTO — architecture, dispatch, and verification of every agent claim",
    head: "oval", eyes: "dots", mouth: "flat", feature: "headset",
  },
  operator: {
    id: "operator", label: "operator", kind: "human",
    role: "a human acting at the console",
    head: "round", eyes: "dots", mouth: "flat", feature: "none",
  },

  worker: {
    id: "worker", label: "worker", kind: "machine",
    role: "the background loop — exits, reconciliation, the clock",
    head: "square", eyes: "lines", mouth: "flat", feature: "gear",
  },
  system: {
    id: "system", label: "system", kind: "machine",
    role: "the spine itself, writing to its own log",
    head: "square", eyes: "lines", mouth: "small", feature: "none",
  },
  clark: {
    id: "clark", label: "clark", kind: "machine",
    role: "the assistant surface",
    head: "square", eyes: "lines", mouth: "smile", feature: "spark",
  },
  "auto-policy": {
    id: "auto-policy", label: "auto-policy", kind: "machine",
    role: "the deterministic, versioned auto-approval envelope",
    head: "square", eyes: "wide", mouth: "flat", feature: "bolt",
  },
});

/**
 * The two narrow aliases, written as anchored patterns rather than prefixes.
 *
 * `auto-policy-v1` is one identity across versions (the version is rendered
 * separately wherever it matters), and the assistant writes under
 * `claude:<something>`. Both are anchored so that an actor which merely BEGINS
 * with a known name — the live log carries `cto-stale-guard: the GLD position
 * this ticket closes was already sold…` — matches nothing and stays faceless.
 */
const ALIASES: ReadonlyArray<{ re: RegExp; id: string }> = [
  { re: /^auto-policy-v\d+$/, id: "auto-policy" },
  { re: /^claude:[a-z0-9_-]+$/i, id: "clark" },
  { re: /^claude$/i, id: "clark" },
  // The CEO's retired operator handle (approval events before 2026-08-20
  // carry actor `rushi`; guard v1.1 retired the name — history keeps it).
  // Same person as `ceo`, so the SAME spec object — aliasing one human to
  // their own face is truthful; a second face would be the lie the
  // uniqueness rule exists to prevent.
  { re: /^rushi$/, id: "ceo" },
  { re: /^neelesh$/, id: "ceo" },
  // A via-cto approval is the CTO's hand carrying the CEO's quoted
  // instruction (guard v1); the approver string carries the quote in
  // brackets. The face shown is the hand that clicked.
  //
  // `-via-co-cto` (guard v1.2, CEO decision 2026-08-21) is the SAME rule with a
  // second chair: an Opus session occupying the CTO chair operationally while
  // Fable's tokens are out. It carries a distinct identity precisely so the
  // record shows which chair staged what — but the FACE is the CTO's, because a
  // face answers "whose hand clicked", and both chairs are that one chair.
  // A distinct co-cto face is deliberately NOT in scope: it would need its own
  // unique tuple, and inventing a colleague is exactly what the uniqueness rule
  // exists to prevent. Anchored with `\b` like its sibling, so an actor that
  // merely BEGINS with the string (the log carries 200-character sentences in
  // `actor`) still matches nothing.
  { re: /^(neelesh|rushi)-via-(co-)?cto\b/, id: "cto" },
  { re: /^fable$/, id: "cto" },
  { re: /^vishesh$/, id: "coo" },
  { re: /^donna$/, id: "secretary" },
  { re: /^grace$/, id: "cfo" },
];

/**
 * The face for an actor id, or null when none is on file.
 *
 * Null is the load-bearing return: the component renders a stated absence for
 * it. Never fall back to "some face" — an invented portrait attributes work to
 * someone who never did it.
 */
export function faceFor(actor: string | null | undefined): FaceSpec | null {
  if (!actor) return null;
  const id = actor.trim().toLowerCase();
  if (!id) return null;
  if (Object.prototype.hasOwnProperty.call(FACES, id)) return FACES[id];
  for (const a of ALIASES) if (a.re.test(id)) return FACES[a.id];
  return null;
}

/** The tuple that must be unique across the registry — two colleagues who look
 *  identical are worse than no faces at all. Exported so the test asserts on
 *  the same key the eye actually reads. */
export function faceKey(f: FaceSpec): string {
  return `${f.head}/${f.eyes}/${f.mouth}/${f.feature}`;
}
