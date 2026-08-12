"use client";

import React from "react";

export type StatusState = "live" | "syncing" | "offline";

interface StatusPulseProps {
  state: StatusState;
  label?: string;
  className?: string;
}

export function StatusPulse({ state, label, className = "" }: StatusPulseProps) {
  const getColors = () => {
    switch (state) {
      case "live":
        return {
          dot: "bg-emerald-500",
          animation: "animate-pulse-live",
          text: "text-[var(--kt-accent)]",
        };
      case "syncing":
        return {
          dot: "bg-amber-500",
          animation: "animate-blink-sync",
          text: "text-[var(--kt-warn)]",
        };
      case "offline":
      default:
        return {
          dot: "bg-rose-500",
          animation: "",
          text: "text-[var(--kt-down)]",
        };
    }
  };

  const colors = getColors();

  return (
    <div className={`flex items-center gap-1.5 ${className}`}>
      <div className="relative flex h-2 w-2 items-center justify-center">
        <span className={`absolute inline-flex h-full w-full rounded-full ${colors.dot} ${colors.animation}`} />
        <span className={`relative inline-flex h-1.5 w-1.5 rounded-full ${colors.dot}`} />
      </div>
      {label && <span className={`text-[11px] font-medium ${colors.text}`}>{label}</span>}
    </div>
  );
}
