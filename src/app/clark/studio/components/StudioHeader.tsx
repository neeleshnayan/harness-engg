"use client";

import React from "react";
import Link from "next/link";
import { StudioNav } from "./StudioNav";
import { ThemeToggle } from "../ThemeToggle";
import { ModeBar } from "./ModeBar";
import { RiskBar } from "./RiskBar";
import { MarketClock } from "./MarketClock";
import { ClarkConsole } from "./ClarkConsole";
import { PositionTicker } from "./PositionTicker";

interface StudioHeaderProps {
  /** Static strapline, e.g. a page description. */
  subtitle?: string;
  /** Live status line (connection state, last sync) — replaces `subtitle` when given. */
  status?: React.ReactNode;
  /** Page-specific actions, rendered left of the theme toggle. */
  actions?: React.ReactNode;
}

/**
 * The ONE Studio top bar — used by every Studio page.
 *
 * The dashboard previously hand-rolled its own copy of this (with teal/sky
 * accents that drifted off the emerald palette). Page-specific controls now come
 * in through `actions` instead of forking the shell.
 */
export function StudioHeader({ subtitle, status, actions }: StudioHeaderProps) {
  return (
    <div className="sticky top-0 z-30 border-b border-[var(--kt-border)] bg-[var(--kt-bg)]/90 text-[var(--kt-text)] backdrop-blur-md">
      {/* Identity, then navigation underneath it — not competing for the same
          line. The strapline is gone: "Everything that needs you, in one
          screen" is a claim about the product made to someone already using
          it, and it took the same weight as the fund's own name. */}
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-3 px-6 pt-3 pb-2">
        <Link href="/clark/studio" className="flex items-center gap-2.5" title="Krypton">
          <img src="/Krypton Clark.svg" alt="" aria-hidden className="h-6 w-auto" />
          <span className="text-[15px] font-semibold tracking-tight text-[var(--kt-text-strong)]">
            Krypton Fund
          </span>
        </Link>
        {/* Subordinate to the name, on the same line rather than under it.
            Allocate, Lab and Risk each pass a genuinely descriptive subtitle
            and would lose something if this were dropped outright; the home
            page passes none, which is the case that prompted the change. */}
        {status ? (
          <div className="flex items-center gap-1.5 text-[11px] text-[var(--kt-text-muted)]">
            {status}
          </div>
        ) : (
          subtitle && (
            <div className="hidden text-[12px] text-[var(--kt-text-muted)] md:block">
              {subtitle}
            </div>
          )
        )}
        <div className="ml-auto flex items-center gap-3">
          {/* Almost everything on every surface is downstream of this: a flat
              chart and an empty signals table both read as faults until you
              know the venue is shut. */}
          <MarketClock />
          {actions}
          <ThemeToggle />
          {/* Opens OVER the cockpit rather than navigating to /clark. Asking
              about a screen you had to leave means restating its numbers from
              memory, and a question that begins "I think NAV was around two
              thousand" is one the answer cannot be checked against. */}
          <ClarkConsole />
        </div>
      </div>
      <div className="mx-auto max-w-[1600px] px-6 pb-2">
        <StudioNav />
      </div>
      {/* WHICH FUND IS THIS — above risk, because it decides how to read every
          other number on the page including the risk strip's own. A drawdown
          of 6.8% means something different in test mode, and an operator who
          learns the mode second has already read the numbers wrong once. */}
      <ModeBar />
      {/* Risk applies to every surface, so it follows the user rather than
          living on a page they must remember to visit. */}
      <RiskBar />
      {/* what we actually own, live — not a market index reel */}
      <PositionTicker />
    </div>
  );
}
