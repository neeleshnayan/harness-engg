"use client";

import React from "react";
import Link from "next/link";
import { MessageSquare, TrendingUp } from "lucide-react";
import { StudioNav } from "./StudioNav";

interface StudioHeaderProps {
  subtitle?: string;
  theme?: "dark" | "light";
}

/** Shared top bar + tab nav for Studio subpages. */
export function StudioHeader({ subtitle, theme = "dark" }: StudioHeaderProps) {
  const isLight = theme === "light";

  return (
    <div className={`sticky top-0 z-30 border-b backdrop-blur-md transition-all ${
      isLight
        ? "bg-[#FAF8F5]/90 border-[#EAE5D9] text-[#1E1E1E]"
        : "bg-[#040812]/90 border-orange-500/20 text-zinc-100"
    }`}>
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-3 px-6 py-3 font-mono">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-[#D97757] to-[#CC6B49] shadow-sm">
            <TrendingUp size={15} className="text-white" />
          </div>
          <div className="leading-tight">
            <div className={`text-sm font-extrabold tracking-tight ${isLight ? "text-[#1E1E1E]" : "text-white"}`}>
              Krypton Fund · Strategy Studio
            </div>
            {subtitle && (
              <div className={`text-[11px] ${isLight ? "text-[#78716C]" : "text-zinc-400"}`}>
                {subtitle}
              </div>
            )}
          </div>
        </div>
        <div className="ml-4 hidden sm:block">
          <StudioNav />
        </div>
        <Link
          href="/clark"
          className={`ml-auto flex h-8 items-center gap-1.5 rounded-lg border px-3 text-xs font-bold transition ${
            isLight
              ? "border-[#D9D2C5] bg-[#F0EBE1] text-[#D97757] hover:bg-[#E2DDD2]"
              : "border-orange-500/40 bg-orange-950/40 text-orange-300 hover:bg-orange-900/60"
          }`}
        >
          <MessageSquare size={13} /> Clark Copilot
        </Link>
      </div>
      <div className="mx-auto max-w-[1600px] px-6 pb-2 sm:hidden">
        <StudioNav />
      </div>
    </div>
  );
}
