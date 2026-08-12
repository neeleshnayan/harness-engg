"use client";

import React from "react";
import Link from "next/link";
import { MessageSquare, TrendingUp } from "lucide-react";
import { StudioNav } from "./StudioNav";
import { KT } from "../theme";

interface StudioHeaderProps {
  subtitle?: string;
}

/** Shared top bar + tab nav for Studio subpages. Dark-only (see theme.ts). */
export function StudioHeader({ subtitle }: StudioHeaderProps) {
  return (
    <div className="sticky top-0 z-30 border-b border-zinc-800/70 bg-[#0A0A0B]/90 text-zinc-100 backdrop-blur-md">
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-3 px-6 py-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-emerald-500/25 bg-emerald-500/15">
            <TrendingUp size={15} className="text-emerald-400" />
          </div>
          <div className="leading-tight">
            <div className={KT.title}>Krypton Fund · Strategy Studio</div>
            {subtitle && <div className={`mt-0.5 ${KT.label}`}>{subtitle}</div>}
          </div>
        </div>
        <div className="ml-4 hidden sm:block">
          <StudioNav />
        </div>
        <Link href="/clark" className={`ml-auto flex h-8 items-center gap-1.5 ${KT.btn}`}>
          <MessageSquare size={13} /> Clark Copilot
        </Link>
      </div>
      <div className="mx-auto max-w-[1600px] px-6 pb-2 sm:hidden">
        <StudioNav />
      </div>
    </div>
  );
}
