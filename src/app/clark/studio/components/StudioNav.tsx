"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, ClipboardCheck, FlaskConical, Sliders } from "lucide-react";

/**
 * Workflow-first navigation (see docs/STUDIO_IA_SPEC.md).
 *
 * The Studio used to be organised by system component — Overview / Strategies /
 * Composer / Approvals / Theses / Risk — which mirrored the code rather than the
 * job, and left things like per-strategy drawdown with an equal claim on two
 * tabs. These four match what the fund actually does, in order:
 *
 *     decide what to own -> research it -> size it -> watch it
 *
 * Lab sits between Decide and Allocate: authoring and testing a strategy is a
 * distinct job from sizing the book, but it is NOT a place capital moves.
 *
 * Review was retired rather than kept as a thin tab: attribution belongs with
 * the strategy it describes (Allocate), and the NAV record and audit trail
 * answer "what has happened to the fund", which is Monitor's question. A
 * reporting surface earns its own tab once there is history worth reporting.
 *
 * Risk is deliberately absent: it applies to all four, so it lives in the
 * always-visible RiskBar instead of being a place you have to visit.
 */
const TABS = [
  { href: "/clark/studio", label: "Decide", icon: ClipboardCheck, exact: true,
    hint: "Theses, memos and approvals awaiting a human" },
  { href: "/clark/studio/allocate", label: "Allocate", icon: Sliders,
    hint: "Strategies, weights and composition" },
  { href: "/clark/studio/lab", label: "Lab", icon: FlaskConical,
    hint: "Backtest, optimise and stress a strategy before it carries capital" },
  { href: "/clark/studio/monitor", label: "Monitor", icon: Activity,
    hint: "Live NAV, positions, breaches and the kill-switch" },
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
