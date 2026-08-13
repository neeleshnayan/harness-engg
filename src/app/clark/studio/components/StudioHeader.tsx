"use client";

import React from "react";
import Link from "next/link";
import { MessageSquare, TrendingUp } from "lucide-react";
import { StudioNav } from "./StudioNav";
import { KT } from "../theme";
import { ThemeToggle } from "../ThemeToggle";
import { RiskBar } from "./RiskBar";
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
        <div className="ml-auto flex items-center gap-2">
          {actions}
          <ThemeToggle />
          <Link href="/clark" className={`flex h-8 items-center gap-1.5 ${KT.btn}`}>
            <MessageSquare size={13} /> Clark Copilot
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
