"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { CheckSquare, Layers, LayoutDashboard, ShieldAlert, Sliders, Target } from "lucide-react";
import { KT } from "../theme";

const TABS = [
  { href: "/clark/studio", label: "Overview", icon: LayoutDashboard, exact: true },
  { href: "/clark/studio/strategies", label: "Strategies", icon: Layers },
  { href: "/clark/studio/compose", label: "Composer", icon: Sliders },
  { href: "/clark/studio/approvals", label: "Approvals", icon: CheckSquare },
  { href: "/clark/studio/theses", label: "Theses", icon: Target },
  { href: "/clark/studio/risk", label: "Risk", icon: ShieldAlert },
];

/** Shared subpage nav for the Strategy Studio cockpit. */
export function StudioNav() {
  const path = usePathname();
  return (
    <div className="flex flex-wrap items-center gap-1">
      {TABS.map((t) => {
        const active = t.exact ? path === t.href : path.startsWith(t.href);
        const Icon = t.icon;
        return (
          <Link
            key={t.href}
            href={t.href}
            className={`flex h-8 items-center gap-1.5 rounded-lg px-3 text-xs font-medium transition-colors ${
              active
                ? "bg-emerald-500/15 text-[var(--kt-accent)] border border-emerald-500/30"
                : "border border-transparent text-[var(--kt-text-dim)] hover:bg-[var(--kt-inset)] hover:text-[var(--kt-text)]"
            }`}
          >
            <Icon size={14} /> {t.label}
          </Link>
        );
      })}
    </div>
  );
}
