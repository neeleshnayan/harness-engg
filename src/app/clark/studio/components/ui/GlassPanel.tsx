"use client";

import React, { ReactNode } from "react";
import { Loader2 } from "lucide-react";

interface GlassPanelProps {
  children: ReactNode;
  title?: string;
  subtitle?: string;
  icon?: ReactNode;
  headerRight?: ReactNode;
  loading?: boolean;
  interactive?: boolean;
  className?: string;
  onClick?: () => void;
}

export function GlassPanel({
  children,
  title,
  subtitle,
  icon,
  headerRight,
  loading = false,
  interactive = false,
  className = "",
  onClick,
}: GlassPanelProps) {
  return (
    <div
      className={`glass-panel overflow-hidden ${interactive ? "glass-panel-interactive" : ""} ${className}`}
      onClick={onClick}
    >
      {(title || icon || headerRight) && (
        <div className="flex items-center justify-between border-b border-white/5 px-4 py-2.5">
          <div className="flex items-center gap-2">
            {icon && <span className="text-zinc-400">{icon}</span>}
            {title && <span className="text-sm font-semibold text-zinc-100">{title}</span>}
            {subtitle && <span className="text-[11px] text-zinc-500">{subtitle}</span>}
          </div>
          {headerRight && <div className="ml-auto">{headerRight}</div>}
        </div>
      )}
      
      <div className="relative">
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-zinc-950/40 backdrop-blur-sm">
            <Loader2 className="animate-spin text-teal-500" size={20} />
          </div>
        )}
        <div className={title ? "p-4" : ""}>
          {children}
        </div>
      </div>
    </div>
  );
}
