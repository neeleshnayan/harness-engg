export const RISK_OPTIONS = [
  { value: "all", label: "All risk" },
  { value: "A", label: "Risk A" },
  { value: "A-", label: "Risk A-" },
  { value: "B+", label: "Risk B+" },
  { value: "B", label: "Risk B" },
  { value: "C", label: "Risk C" },
  { value: "D", label: "Risk D" },
] as const;

export const APY_OPTIONS = [
  { value: "all", label: "All APY" },
  { value: "0", label: "≥ 0%" },
  { value: "5", label: "≥ 5%" },
  { value: "10", label: "≥ 10%" },
  { value: "20", label: "≥ 20%" },
] as const;
