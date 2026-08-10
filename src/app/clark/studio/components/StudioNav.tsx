"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { CheckSquare, Layers, LayoutDashboard, ShieldAlert, Target } from "lucide-react";

const TABS = [
  { href: "/clark/studio", label: "Overview", icon: LayoutDashboard, exact: true },
  { href: "/clark/studio/strategies", label: "Strategies", icon: Layers },
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
            className={`flex h-8 items-center gap-1.5 rounded-md px-3 text-sm transition-colors ${
              active
                ? "bg-teal-600/20 text-teal-300 border border-teal-600/40"
                : "border border-transparent text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200"
            }`}
          >
            <Icon size={14} /> {t.label}
          </Link>
        );
      })}
    </div>
  );
}
