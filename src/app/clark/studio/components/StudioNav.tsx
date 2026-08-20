"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, BookOpen, FlaskConical, ShieldAlert, Sliders, Swords } from "lucide-react";

/**
 * Workflow-first navigation — FIVE tabs, down from seven (CEO direction,
 * request c91d5c07, 2026-08-20).
 *
 * **Monitor is the landing page.** The Studio used to open on Decide — the
 * approval queue and nothing else — which made the fund's rarest event the first
 * thing you saw, while halt state, breaches, fills and drift all sat one click
 * away. Approvals are now a panel at the top of Monitor, so the common case
 * ("anything wrong? anything waiting on me?") is answered without navigating and
 * the rare case still leads the page.
 *
 * Desk is second now, not last: it became the OFFICE — the firm day by day, one
 * page per seat, and the place work is asked for. It is where a manager starts.
 *
 * Allocate owns sizing and per-strategy attribution: important, but not a thing
 * you check every day.
 *
 * Lab owns strategy backtesting and candidate verification.
 *
 * Thesis owns automatic theme discovery, multi-source research intelligence,
 * and deterministic bull/bear thesis generation.
 *
 * What left the bar, and why it did not leave the product:
 *   * MECHANICS — retired as a tab. Its funnel, causes of death, gate lineage
 *     and cohort now render on the quant's seat page (the lane that submits to
 *     the belt); its story and ladder render on the Desk. The rule: a chart
 *     stays only if it informs a specific click or dispatch, and Mechanics was
 *     a tab you read rather than acted on. /clark/studio/mechanics redirects.
 *   * RISK — the builder removed it from the bar (2026-08-20); the CEO vetoed
 *     the removal the same morning ("risk page is entirely gone"). A page only
 *     reachable through a strip nobody thinks of as a door IS gone to its
 *     reader. Six tabs, restored by CEO decision.
 */
const TABS = [
  { href: "/clark/studio", label: "Monitor", icon: Activity, exact: true,
    hint: "Approvals, breaches, NAV, fills and live signals — the five-minute check" },
  { href: "/clark/studio/desk", label: "Desk", icon: Swords,
    hint: "The office: the firm day by day, one page per seat, request work, artifact chain and kills" },
  { href: "/clark/studio/allocate", label: "Allocate", icon: Sliders,
    hint: "Strategies, weights, composition and per-strategy attribution" },
  { href: "/clark/studio/lab", label: "Lab", icon: FlaskConical,
    hint: "Research an idea: write a strategy, run it on the engine of record" },
  { href: "/clark/studio/risk", label: "Risk", icon: ShieldAlert,
    hint: "Diversification, tail risk, market regime and survivability" },
  { href: "/clark/studio/thesis", label: "Thesis", icon: BookOpen,
    hint: "Automatic theme discovery & investment thesis generator" },
];

export function StudioNav() {
  const path = usePathname();
  return (
    <nav className="flex flex-wrap items-center gap-1">
      {TABS.map((t) => {
        const active = t.exact ? path === t.href : path.startsWith(t.href);
        const Icon = t.icon;
        return (
          <Link
            key={t.href}
            href={t.href}
            title={t.hint}
            aria-current={active ? "page" : undefined}
            className={`flex h-8 items-center gap-1.5 rounded-lg px-3 text-xs font-medium transition-colors ${
              active
                ? "border border-[var(--kt-accent-border)] bg-[var(--kt-accent-bg)] text-[var(--kt-accent)]"
                : "border border-transparent text-[var(--kt-text-dim)] hover:bg-[var(--kt-inset)] hover:text-[var(--kt-text)]"
            }`}
          >
            <Icon size={14} /> {t.label}
          </Link>
        );
      })}
    </nav>
  );
}
