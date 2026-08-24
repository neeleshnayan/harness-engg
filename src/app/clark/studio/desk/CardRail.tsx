"use client";

/**
 * THE LIFECYCLE RAIL — one rendering, two card types.
 *
 * Spec: `docs/design/REQUEST_CARD_2026-08-24.md`, question 2 ("Where does it
 * stand?"). The rail is what made request `0c295ec7`'s real story legible in a
 * glance — approved 22 minutes after filing, then idle 2.5 days, which the old
 * card rendered as gray footer text.
 *
 * EXTRACTED, NOT COPIED (D42). The request card had this rail inline; the
 * recommendation card needed the SAME visual language, and this repo's own
 * `components.tsx` header carries the reason a second copy is not acceptable:
 * "two renderings of the same run that drift apart is how a reader ends up
 * trusting whichever one is prettier". One component, two mappers.
 *
 * FOUR STATES, and the fourth is the one this file exists to carry honestly.
 * `unrecorded` is a stage the record CANNOT speak to — a recommendation's
 * execution, which nothing on this desk logs. It is neither a tick (which
 * would claim an execution nobody recorded) nor a dim future stage (which
 * would claim one that happened never did), so it renders as its own thing and
 * says so on hover.
 */

import React from "react";

import { KT } from "../theme";
import { ageLabel } from "./cardState";
import type { RailState } from "./cardAnatomy";

export interface RailItem {
  label: string;
  state: RailState;
}

const TONE: Record<RailState, string> = {
  // The hot stage is the ONE colour on a card, and it is semantic — the
  // visual grammar's single exception, exactly as the spec writes it.
  current: "text-[var(--kt-warn)]",
  reached: KT.body,
  future: KT.muted,
  // Dim AND dashed-through: the eye must not read it as "not yet".
  unrecorded: `${KT.muted} italic`,
};

const TITLE: Partial<Record<RailState, string>> = {
  unrecorded: "Nothing on this desk records that a recommendation was carried "
    + "out — no field and no event this page reads. Unrecorded is not "
    + "“not done”.",
};

/**
 * The rail.
 *
 * `age` rides the CURRENT stage and only it. An age on every stage would be
 * five numbers where the reader needs one: how long has this been stuck HERE.
 * A null age renders as nothing — never as `0.0h`, which would be this fund's
 * oldest mistake on its newest surface — while a genuine zero renders, because
 * hiding that would be the same error pointed the other way.
 */
export function StageRail({ items, ageHours, suffix }: {
  items: RailItem[];
  ageHours: number | null;
  /** An extra terminal word, e.g. "declined". */
  suffix?: string | null;
}) {
  const age = ageLabel(ageHours);
  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1">
      {items.map((s, i) => (
        <React.Fragment key={`${s.label}-${i}`}>
          {i > 0 && (
            <span className={`font-mono text-[10px] ${KT.muted}`} aria-hidden>
              ›
            </span>
          )}
          <span className={`font-mono text-[10px] ${TONE[s.state]}`}
                title={TITLE[s.state]}>
            {s.label}
            {s.state === "current" && age ? ` · ${age}` : ""}
            {s.state === "unrecorded" ? " (unrecorded)" : ""}
          </span>
        </React.Fragment>
      ))}
      {suffix && (
        <span className={`font-mono text-[10px] ${KT.muted}`}>· {suffix}</span>
      )}
    </div>
  );
}
