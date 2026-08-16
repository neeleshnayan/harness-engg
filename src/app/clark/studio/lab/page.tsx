"use client";

import React from "react";
import { StudioHeader } from "../components/StudioHeader";
import { LeanLab } from "../components/LeanLab";

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

export default function LabPage() {
  return (
    <div className="bg-[var(--kt-bg)] text-[var(--kt-text)] min-h-screen">
      <StudioHeader subtitle="Write a strategy, run it on the engine of record — nothing here is registered or persisted" />
      <div className="mx-auto max-w-[1600px] px-6 pb-10">
        <LeanLab />
      </div>
    </div>
  );
}
