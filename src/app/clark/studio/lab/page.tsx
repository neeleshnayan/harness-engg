"use client";

import React from "react";
import { StudioHeader } from "../components/StudioHeader";
import { LeanLab } from "../components/LeanLab";
import { BeltWorkspace } from "../components/BeltWorkspace";
import { BeltRuns } from "./BeltRuns";

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
 *
 * ONE surface, now (CEO direction, request c91d5c07, 2026-08-20). The research
 * map and the hunting ground were retired from this page: they answered "where
 * should we look", which is the MECHANISM seat's question, and that seat reads
 * the same endpoints (`/fund/research/map`, `/fund/universe/hunting-ground`)
 * directly through the API. A panel that exists so a human can do an agent's
 * first step is a panel that gets skimmed and trusted; the Lab is now only the
 * place where an idea is written and run.
 *
 * ONE VALIDATION EXPERIENCE (CEO direction, 2026-08-21): *"unify the experience
 * so I can validate agents runs same way i would mine ... importantly be able to
 * see the analytics behind the runs!"*. The page reads top to bottom as the same
 * loop at three scales:
 *
 *   1. LeanLab      — write it and run it. Your own run's analytics render
 *                     immediately, through LeanResults.
 *   2. BeltRuns     — what the FACTORY judged, each opening into the same
 *                     analytics in the same order, from the same engine output.
 *   3. BeltWorkspace— the raw sweep history and the source on disk, verbatim.
 *
 * The middle one is new. It could not exist before 2026-08-21 because the belt
 * discarded the evidence: the curve, the fills, the cost grid and the per-fold
 * rows were computed, handed to the gate, and dropped. The spine keeps them now
 * (ClarkHarness app/fund/runanalytics.py), and every candidate judged BEFORE
 * that renders as a named absence rather than as an empty panel.
 */

export default function LabPage() {
  return (
    <div className="bg-[var(--kt-bg)] text-[var(--kt-text)] min-h-screen">
      <StudioHeader subtitle="Write a strategy, run it on the engine of record — nothing here is registered or persisted" />
      <div className="mx-auto max-w-[1600px] px-6 pb-10">
        <LeanLab />
        {/* what the factory judged, and the evidence behind each verdict */}
        <BeltRuns />
        {/* what already ran: the quant's workspace, code + sweep history */}
        <BeltWorkspace />
      </div>
    </div>
  );
}
