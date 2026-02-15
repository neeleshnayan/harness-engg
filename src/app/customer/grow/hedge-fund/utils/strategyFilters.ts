import { calculateRiskGrade } from "../components/StrategyCard";

/**
 * Get risk grade for a strategy. Mirrors StrategyCard logic:
 * Uses sharpe + max_drawdown when available, else risk_grade from API.
 */
export function getStrategyRiskGrade(s: any): string {
  const sharpe =
    typeof s.sharpe_ratio === "number"
      ? s.sharpe_ratio
      : typeof s.sharpeRatio === "number"
        ? s.sharpeRatio
        : parseFloat(String(s.sharpe_ratio ?? s.sharpeRatio ?? 0)) || 0;
  const maxDd =
    typeof s.max_drawdown === "number"
      ? s.max_drawdown
      : typeof s.maxDrawdown === "number"
        ? s.maxDrawdown
        : parseFloat(String(s.max_drawdown ?? s.maxDrawdown ?? 0)) || 0;
  if (Number.isFinite(sharpe) && Number.isFinite(maxDd)) {
    return calculateRiskGrade(sharpe, Math.abs(maxDd));
  }
  const stored = s.risk_grade ?? s.riskGrade ?? "B";
  return stored != null ? String(stored).trim() : "B";
}

/**
 * Get net APY for a strategy. Mirrors StrategyCard (config.net_apy).
 */
export function getStrategyNetApy(s: any): number {
  const raw = s.net_apy ?? s.netApy ?? 0;
  return typeof raw === "number" && Number.isFinite(raw)
    ? raw
    : parseFloat(String(raw)) || 0;
}

export function filterStrategies(
  strategies: any[],
  riskFilter: string,
  apyFilter: string
): any[] {
  let list = strategies;
  if (riskFilter !== "all") {
    const risk = riskFilter.trim();
    list = list.filter((s) => getStrategyRiskGrade(s) === risk);
  }
  if (apyFilter !== "all") {
    const minApy = parseFloat(apyFilter);
    if (Number.isFinite(minApy)) {
      list = list.filter((s) => getStrategyNetApy(s) >= minApy);
    }
  }
  return list;
}
