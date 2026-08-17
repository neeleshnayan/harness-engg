"use client";

import React, { useRef, useState } from "react";
import { StudioHeader } from "../components/StudioHeader";
import { LeanLab } from "../components/LeanLab";
import { HuntingGround } from "../components/HuntingGround";
import { ResearchMap } from "../components/ResearchMap";

/**
 * LAB — the strategy desk.
 *
 * Research, not fund state: nothing here is registered or persisted, and it
 * touches no event log, so the loop keeps working when the ledger does not.
 *
 * ONE engine, deliberately. The Lab used to carry two backtesters — a fast
 * in-process one driven by a template dropdown, and LEAN driven by code — each
 * with its own analytics and its own idea of what a Sharpe ratio looks like.
 * Two answers to the same question in two visual languages is worse than
 * either alone: before reading a number you first had to remember which tester
 * produced it, and the two could disagree with nothing to adjudicate them.
 *
 * The template lab could not survive contact with a real strategy anyway — its
 * vocabulary was fixed at eight shapes, and a strategy that is not one of them
 * had nowhere to go. Code has no such ceiling, and it is the same code that
 * runs in the engine of record. So: write it (or have Clark write it), run it,
 * read the analytics.
 */

/** What the reader carried down from the map. Held here rather than inside
 *  either component, because it is the handoff BETWEEN them — and the
 *  observation ids are what let a candidate started from a filing be traced
 *  back to the sentence that prompted it. */
interface Brief {
  ticker: string;
  observationIds: string[];
}

export default function LabPage() {
  const [brief, setBrief] = useState<Brief | null>(null);
  const labRef = useRef<HTMLDivElement | null>(null);

  const takeToLab = (ticker: string, observationIds?: string[]) => {
    setBrief({ ticker, observationIds: observationIds ?? [] });
    // Move the reader to the desk. Setting state without scrolling leaves the
    // handoff invisible below the fold, which reads as the button doing nothing.
    labRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="bg-[var(--kt-bg)] text-[var(--kt-text)] min-h-screen">
      <StudioHeader subtitle="Write a strategy, run it on the engine of record — nothing here is registered or persisted" />
      <div className="mx-auto max-w-[1600px] px-6 pb-10">
        {/* The map first, deliberately. A lazy reader trusts whatever is at
            the top, so the top must be the view that shows what is MISSING —
            not the one that ranks what happens to be present. */}
        <ResearchMap onPick={takeToLab} />
        {/* Where to look, before what to test. The fund's whole book sits
            outside this list, which is the argument for putting it first. */}
        <HuntingGround onPick={(symbol) => takeToLab(symbol)} />
        <div ref={labRef}>
          <LeanLab brief={brief} onClearBrief={() => setBrief(null)} />
        </div>
      </div>
    </div>
  );
}
