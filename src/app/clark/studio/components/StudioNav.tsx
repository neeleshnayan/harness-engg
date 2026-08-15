"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, BookOpen, FlaskConical, Library, ShieldAlert, Sliders } from "lucide-react";

/**
 * Workflow-first navigation, ordered by how often it is used.
 *
 * **Monitor is the landing page.** The Studio used to open on Decide — the
 * approval queue and nothing else — which made the fund's rarest event the first
 * thing you saw, while halt state, breaches, fills and drift all sat one click
 * away. Approvals are now a panel at the top of Monitor, so the common case
 * ("anything wrong? anything waiting on me?") is answered without navigating and
 * the rare case still leads the page.
 *
 * Allocate owns sizing and per-strategy attribution: important, but not a thing
 * you check every day.
 *
 * Lab owns strategy backtesting and candidate verification.
 *
 * Risk owns structural portfolio risk: correlation, effective bets, tails, regime.
 *
 * Thesis owns automatic theme discovery, multi-source research intelligence,
 * and deterministic bull/bear thesis generation.
 */
const TABS = [
  { href: "/clark/studio", label: "Monitor", icon: Activity, exact: true,
    hint: "Approvals, breaches, NAV, fills and live signals — the five-minute check" },
  { href: "/clark/studio/allocate", label: "Allocate", icon: Sliders,
    hint: "Strategies, weights, composition and per-strategy attribution" },
  { href: "/clark/studio/lab", label: "Lab", icon: FlaskConical,
    hint: "Research an idea: backtest, templates, and what to promote" },
  { href: "/clark/studio/risk", label: "Risk", icon: ShieldAlert,
    hint: "Diversification, tail risk, market regime and survivability" },
  { href: "/clark/studio/thesis", label: "Thesis", icon: BookOpen,
    hint: "Automatic theme discovery & investment thesis generator" },
  { href: "/clark/studio/research", label: "Research", icon: Library,
    hint: "Theses, memos and postmortems — the recorded why behind the trades" },
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
