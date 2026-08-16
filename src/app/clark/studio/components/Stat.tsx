"use client";

import React from "react";
import { KT } from "../theme";

/**
 * One measured number, with the comparison that makes it mean something.
 *
 * Shared deliberately: the Lab runs two engines — the fast in-process
 * backtester and LEAN — and a Sharpe from one must LOOK like a Sharpe from
 * the other. Two stat vocabularies on one page invite the reader to believe
 * the numbers are different KINDS of fact. They are not; only the engine
 * differs, and that is said in words, not in styling.
 */
export function Stat({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: string;
}) {
  return (
    <div className={KT.card}>
      <div className={KT.label}>{label}</div>
      <div className={`mt-1 font-mono tabular-nums text-xl font-light ${tone || "text-[var(--kt-text-strong)]"}`}>
        {value}
      </div>
      {sub && <div className={`mt-1 text-[10px] ${KT.muted}`}>{sub}</div>}
    </div>
  );
}
