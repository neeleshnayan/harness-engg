"use client";

/**
 * The request card — the four questions, in order, without scrolling.
 *
 * Spec: `docs/design/REQUEST_CARD_2026-08-24.md`, CEO-ratified, written after
 * request `0c295ec7` rendered as a wall of prose: *"it could have been
 * designed in a far more intuitive and cleaner way"*.
 *
 *   1. WHAT IS THIS — a headline, not the first line of a dump.
 *   2. WHERE DOES IT STAND — the lifecycle rail, current stage hot, carrying
 *      its AGE. `0c295ec7`'s real story is "approved 22 minutes after filing,
 *      then idle 2.5 days"; the old card rendered that as gray footer text.
 *   3. WHAT IS OWED — `wanted` as a tracked checklist. Partial progress must
 *      be visible; a card is not binary.
 *   4. WHOSE MOVE IS IT — actor AND act. The old "CEO-APPROVED — TRIGGER IT"
 *      chip named an owner and left the obligation to be guessed, and it named
 *      the wrong owner.
 *
 * VISUAL GRAMMAR (theme.ts's ILLUMINATION PRINCIPLE): calm surfaces, hierarchy
 * from type and space, never colour. The ONLY colour here is semantic — the
 * hot lifecycle stage. Kind chips stay neutral, sentence case, mono for ids.
 *
 * PROSE-ONLY IS NOT A DEGRADED MODE. All 109 requests filed before the schema
 * existed render through the fallback and always will; there is no migration
 * and rewriting an old subject to look structured would invent a headline the
 * filer never wrote.
 */

import type React from "react";

import type { AskCard, AskLifecycle } from "./execDesk";
import { KT } from "../theme";
/* `ageLabel` and the stage labels live in `cardState.ts`, not here, and the
   reason is mechanical rather than aesthetic: this repo's test runner is
   node's own type stripper, which REFUSES a `.tsx` file. A pure function in a
   component file is a pure function no test can reach — which is how an
   untested branch gets written by accident. */
import { STAGE_LABEL } from "./cardState";
import { StageRail } from "./CardRail";

/* The rail's PIXELS moved to `CardRail.tsx` in D42 so the recommendation card
   wears the same ones; what stays here is the ask-specific MAPPING, which is
   the only part that is about requests. The age and the declined suffix are
   passed straight through — nothing about the rendering changed. */
function Rail({ lifecycle }: { lifecycle: AskLifecycle }) {
  return (
    <StageRail
      items={lifecycle.stages.map((s) => ({
        label: STAGE_LABEL[s.stage] ?? s.stage,
        state: s.current ? "current" : s.reached ? "reached" : "future",
      }))}
      ageHours={lifecycle.ageHours}
      suffix={lifecycle.declined ? "declined" : null}
    />
  );
}

function Wanted({ items }: { items: AskCard["wanted"] }) {
  return (
    <ul className="mt-2 space-y-1">
      {items.map((w, i) => (
        <li key={i} className="flex items-baseline gap-2 text-[12px]">
          {/* A TICK, A HALF, OR AN EMPTY BOX — three states, because partial
              progress is the entire reason this is a checklist and not a
              sentence. Glyphs rather than colour: the design language says
              hierarchy comes from type and space. */}
          <span className={`font-mono text-[10px] ${
            w.state === "done" ? KT.accent : KT.muted}`}>
            {w.state === "done" ? "✓" : w.state === "in_progress" ? "◐" : "○"}
          </span>
          <span className={`min-w-0 flex-1 ${
            w.state === "done" ? KT.muted : KT.body}`}>
            {w.text}
            {w.note ? (
              <span className={`${KT.muted}`}> — {w.note}</span>
            ) : null}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function RequestCardBody({ card, subject, open, onToggle,
                                  headlineShown, trailing }: {
  card: AskCard;
  /** The raw subject, for the prose fallback and the details section. */
  subject: string;
  open: boolean;
  onToggle: () => void;
  /** What the CARD FACE actually printed, when the caller clamped it.
   *
   *  D42, and it is not a cosmetic parameter. The face used to print
   *  `card.headline` whole; every request on the live desk is prose (116 of
   *  116, and the count only grows — the invariant is that none is
   *  structured), so that string IS the entire subject, `hasMore` compared a
   *  value with itself,
   *  came out false, and the card offered no "+ the incident" toggle while
   *  rendering seven lines of narrative as its own name. Passing the clamped
   *  line makes the comparison mean what it says: is there anything the face
   *  is NOT showing? */
  headlineShown?: string | null;
  /** The caller's own toggles, rendered INSIDE this card's toggle row. */
  trailing?: React.ReactNode;
}) {
  const detail = card.incident ?? (card.structured ? null : subject);
  /* The details toggle is offered only when the collapsed body says something
     the card face does not. For a prose ask whose whole subject IS the
     headline, a toggle onto a repeat of the headline is a control that lies
     about having content. */
  const face = (headlineShown ?? card.headline ?? "").replace(/…$/, "").trim();
  const hasMore = !!detail && detail.trim() !== face;

  return (
    <>
      {card.summary && (
        <p className={`mt-1 text-[12px] leading-relaxed ${KT.muted}`}>
          {card.summary}
        </p>
      )}

      {card.lifecycle && <Rail lifecycle={card.lifecycle} />}

      {card.wanted.length > 0 && <Wanted items={card.wanted} />}

      {card.nextMove && (
        /* BOTH THE ACTOR AND THE ACT. The spine refuses a half-named move, so
           if this renders at all it names an obligation. */
        <p className={`mt-2 text-[12px] ${KT.body}`}>
          <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
            next move ·{" "}
          </span>
          {card.nextMove.actor} {card.nextMove.act}
        </p>
      )}

      {/* THE TOGGLE ROW. A ROW, not a bare button, and D42 paid for the
          difference: the incident toggle and the caller's own lineage toggle
          are inline elements from two different components, so with no flex
          parent they rendered welded together as "+ the incident+ lineage".
          The recommendation card has always put its toggles in exactly this
          container with exactly this gap; the request card now wears the same
          one, and a caller's extra toggle goes in `trailing` so it cannot
          land outside the row again. */}
      {(hasMore || trailing) && (
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
          {hasMore && (
            <button type="button" onClick={onToggle} aria-expanded={open}
                    className={`font-mono text-[10px] ${KT.accent} hover:underline`}>
              {open ? "− the incident" : "+ the incident"}
            </button>
          )}
          {trailing}
        </div>
      )}
      {open && hasMore && (
        <p className={`mt-2 whitespace-pre-wrap border-t border-[var(--kt-border)] pt-2 text-[12px] leading-relaxed ${KT.body}`}>
          {detail}
        </p>
      )}
    </>
  );
}
