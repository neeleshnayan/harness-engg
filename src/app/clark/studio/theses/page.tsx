"use client";

import React, { useState } from "react";
import { StudioHeader } from "../components/StudioHeader";
import { ThesisPanel } from "../components/ThesisPanel";
import { ClarkActionBar } from "../components/ClarkActionBar";

export default function ThesesPage() {
  const [tick, setTick] = useState(0);
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <StudioHeader subtitle="Thesis workbench — the falsifiable idea behind every trade" />
      <div className="mx-auto max-w-[900px] space-y-4 px-4 py-4">
        <ClarkActionBar
          placeholder="Ask Clark… e.g. 'create thesis Long NVDA on datacenter demand' or 'draft a memo for thesis <id>'"
          suggestions={["list theses", "create thesis Long NVDA on datacenter demand"]}
          onDone={() => setTick((v) => v + 1)}
        />
        <ThesisPanel refreshKey={tick} onChanged={() => setTick((v) => v + 1)} />
        <p className="text-center text-[11px] text-zinc-600">
          Clark can draft theses and memos; the human owns activation and the trade decision.
        </p>
      </div>
    </div>
  );
}
