"use client";

import React from "react";
import { Shield, Percent } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RISK_OPTIONS, APY_OPTIONS } from "../constants";

interface StrategyFiltersProps {
  riskFilter: string;
  apyFilter: string;
  onRiskChange: (value: string) => void;
  onApyChange: (value: string) => void;
}

export function StrategyFilters({
  riskFilter,
  apyFilter,
  onRiskChange,
  onApyChange,
}: StrategyFiltersProps) {
  return (
    <div className="flex flex-wrap gap-2">
      <Select value={riskFilter} onValueChange={onRiskChange}>
        <SelectTrigger
          className="h-9 w-full sm:w-[120px] rounded-lg border border-white/10 bg-white/5 text-white text-sm hover:bg-white/10 hover:border-white/20 transition-colors"
        >
          <Shield className="w-3.5 h-3.5 mr-2 opacity-70 flex-shrink-0" />
          <SelectValue placeholder="Risk" />
        </SelectTrigger>
        <SelectContent className="rounded-lg border border-white/10 bg-[#0a1414]">
          {RISK_OPTIONS.map((opt) => (
            <SelectItem
              key={opt.value}
              value={opt.value}
              className="text-white focus:bg-white/10 rounded-md"
            >
              {opt.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select value={apyFilter} onValueChange={onApyChange}>
        <SelectTrigger
          className="h-9 w-full sm:w-[130px] rounded-lg border border-white/10 bg-white/5 text-white text-sm hover:bg-white/10 hover:border-white/20 transition-colors"
        >
          <Percent className="w-3.5 h-3.5 mr-2 opacity-70 flex-shrink-0" />
          <SelectValue placeholder="APY" />
        </SelectTrigger>
        <SelectContent className="rounded-lg border border-white/10 bg-[#0a1414]">
          {APY_OPTIONS.map((opt) => (
            <SelectItem
              key={opt.value}
              value={opt.value}
              className="text-white focus:bg-white/10 rounded-md"
            >
              {opt.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
