"use client";

import React from "react";

/** Shared tooltip container styling matching app aesthetics */
const TOOLTIP_CLASS =
  "rounded-xl border border-teal-700/50 bg-zinc-900/95 backdrop-blur-md px-4 py-3 shadow-xl min-w-[140px]";

interface TooltipRow {
  label: string;
  value: string;
  color?: string;
}

export interface StrategyChartTooltipProps {
  active?: boolean;
  /** Compatible with recharts Tooltip payload (dataKey can be string | number) */
  payload?: Array<{ name?: unknown; value?: unknown; color?: string; dataKey?: string | number | undefined }>;
  label?: string;
  /** Override label display (e.g. formatted date) */
  labelFormatted?: string;
  /** Custom rows: label + value pairs */
  rows?: TooltipRow[];
  /** Formatter for single value (AUM, Price charts) */
  valueFormatter?: (value: number) => string;
}

export function StrategyChartTooltip({
  active,
  payload,
  label,
  labelFormatted,
  rows,
  valueFormatter,
}: StrategyChartTooltipProps) {
  if (!active || !payload?.length) return null;

  const displayLabel = labelFormatted ?? label;

  return (
    <div className={TOOLTIP_CLASS}>
      {displayLabel && (
        <p className="text-xs text-teal-300/90 font-medium mb-2.5">{displayLabel}</p>
      )}
      <div className="space-y-1.5">
        {rows
          ? rows.map((row, i) => (
              <div
                key={i}
                className="flex items-center justify-between gap-4"
              >
                <div className="flex items-center gap-2">
                  {row.color && (
                    <div
                      className="h-2 w-2 rounded-full shrink-0"
                      style={{ backgroundColor: row.color }}
                    />
                  )}
                  <span className="text-zinc-400 text-sm">{row.label}</span>
                </div>
                <span className="text-white font-semibold tabular-nums text-sm">
                  {row.value}
                </span>
              </div>
            ))
          : payload.map((item, i) => {
              const val = item.value;
              if (val === undefined) return null;
              const formatted = valueFormatter
                ? valueFormatter(Number(val))
                : String(val);
              return (
                <div
                  key={i}
                  className="flex items-center justify-between gap-4"
                >
                  <div className="flex items-center gap-2">
                    {item.color && (
                      <div
                        className="h-2 w-2 rounded-full shrink-0"
                        style={{ backgroundColor: item.color }}
                      />
                    )}
                    <span className="text-zinc-400 text-sm">
                      {String(item.name ?? "Value")}
                    </span>
                  </div>
                  <span className="text-white font-semibold tabular-nums text-sm">
                    {formatted}
                  </span>
                </div>
              );
            })}
      </div>
    </div>
  );
}
