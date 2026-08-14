"use client";

import React from "react";
import Link from "next/link";
import { MessageSquare, TrendingUp } from "lucide-react";
import { StudioNav } from "./StudioNav";
import { KT } from "../theme";
import { ThemeToggle } from "../ThemeToggle";
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
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-3 px-6 py-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-[var(--kt-accent-border)] bg-[var(--kt-accent-bg)]">
            <TrendingUp size={15} className="text-[var(--kt-accent)]" />
          </div>
          <div className="leading-tight">
            <div className={KT.title}>Krypton Fund · Strategy Studio</div>
            {status ? (
              <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-[var(--kt-text-muted)]">
                {status}
              </div>
            ) : (
              subtitle && <div className={`mt-0.5 ${KT.label}`}>{subtitle}</div>
            )}
          </div>
        </div>
        <div className="ml-4 hidden sm:block">
          <StudioNav />
        </div>
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
          <Link
            href="/clark"
            className={`hidden h-8 items-center gap-1.5 lg:flex ${KT.btn}`}
            title="Clark's full workspace"
          >
            <MessageSquare size={13} /> Full
          </Link>
        </div>
      </div>
      <div className="mx-auto max-w-[1600px] px-6 pb-2 sm:hidden">
        <StudioNav />
      </div>
      {/* Risk applies to every surface, so it follows the user rather than
          living on a page they must remember to visit. */}
      <RiskBar />
      {/* what we actually own, live — not a market index reel */}
      <PositionTicker />
    </div>
  );
}
