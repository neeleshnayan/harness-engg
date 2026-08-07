"use client";

import React, { useState } from "react";
import { StudioHeader } from "../components/StudioHeader";
import { RiskPanel } from "../components/RiskPanel";
import { ClarkActionBar } from "../components/ClarkActionBar";

export default function RiskPage() {
  const [tick, setTick] = useState(0);
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <StudioHeader subtitle="Risk cockpit — concentration and scenario stress" />
      <div className="mx-auto max-w-[900px] space-y-4 px-4 py-4">
        <ClarkActionBar
          placeholder="Ask Clark… e.g. 'show the risk' or 'what if AAPL drops 20%'"
          suggestions={["show the risk", "what if AAPL drops 20%", "what if NVDA drops 30%"]}
          onDone={() => setTick((v) => v + 1)}
        />
        <RiskPanel refreshKey={tick} />
        <p className="text-center text-[11px] text-zinc-600">
          Read-only situational awareness. The deterministic pre-trade risk gate enforces limits at approval.
        </p>
      </div>
    </div>
  );
}
