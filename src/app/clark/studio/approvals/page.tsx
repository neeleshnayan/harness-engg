"use client";

import React, { useState } from "react";
import { StudioHeader } from "../components/StudioHeader";
import { ApprovalsPanel } from "../components/ApprovalsPanel";
import { ClarkActionBar } from "../components/ClarkActionBar";

export default function ApprovalsPage() {
  const [tick, setTick] = useState(0);
  return (
    <div className="min-h-screen bg-[var(--kt-bg)] text-[var(--kt-text)]">
      <StudioHeader subtitle="Approval desk — human-gated order flow" />
      <div className="mx-auto max-w-[900px] space-y-4 px-4 py-4">
        <ClarkActionBar
          placeholder="Ask Clark about the queue… e.g. 'what's pending?' or 'buy 10 AAPL thesis <id>'"
          suggestions={["what's pending?", "how's the fund", "show the risk"]}
          onDone={() => setTick((v) => v + 1)}
        />
        <ApprovalsPanel key={tick} onChanged={() => setTick((v) => v + 1)} />
        <p className="text-center text-[11px] text-[var(--kt-text-muted)]">
          Orders are proposed by Clark or the desk and always settle behind this human gate.
        </p>
      </div>
    </div>
  );
}
