"use client";

import React from "react";
import Link from "next/link";
import { MessageSquare, TrendingUp } from "lucide-react";
import { StudioNav } from "./StudioNav";

/** Shared top bar + tab nav for Studio subpages. */
export function StudioHeader({ subtitle }: { subtitle?: string }) {
  return (
    <div className="sticky top-0 z-10 border-b border-zinc-800/80 bg-zinc-950/90 backdrop-blur">
      <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-3 px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded bg-gradient-to-br from-teal-500 to-sky-600">
            <TrendingUp size={15} className="text-white" />
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold">Krypton Fund · Strategy Studio</div>
            {subtitle && <div className="text-[11px] text-zinc-500">{subtitle}</div>}
          </div>
        </div>
        <div className="ml-2 hidden sm:block">
          <StudioNav />
        </div>
        <Link
          href="/clark"
          className="ml-auto flex h-8 items-center gap-1.5 rounded-md border border-zinc-700 px-3 text-sm text-zinc-200 hover:bg-zinc-800"
        >
          <MessageSquare size={14} /> Clark
        </Link>
      </div>
      <div className="mx-auto max-w-[1400px] px-4 pb-2 sm:hidden">
        <StudioNav />
      </div>
    </div>
  );
}
