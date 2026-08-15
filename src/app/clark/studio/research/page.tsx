"use client";

import React from "react";
import { StudioHeader } from "../components/StudioHeader";
import { ThesisDesk } from "./ThesisDesk";
import { KT } from "../theme";

/**
 * Research — theses, memos and postmortems on their own page.
 *
 * Started life mounted under Lab; moved out because the thesis workflow is
 * Abhishek's surface and Lab is the backtest bench. This page is deliberately
 * a thin shell around ThesisDesk so his work replaces one component, not a
 * layout.
 */
export default function ResearchPage() {
  return (
    <div className={KT.page}>
      <StudioHeader subtitle="Theses, memos and postmortems — why the fund holds what it holds" />
      <div className="mx-auto max-w-[1100px] px-6 py-6">
        <ThesisDesk />
      </div>
    </div>
  );
}
