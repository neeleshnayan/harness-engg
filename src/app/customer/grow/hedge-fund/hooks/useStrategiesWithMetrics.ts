"use client";

import { useQueries } from "@tanstack/react-query";
import { fetchSubgraph } from "@/hooks/useStrategySubgraphData";
import { calculateRiskGrade } from "../components/StrategyCard";

const DEFAULT_SUBGRAPH_URL = process.env.NEXT_PUBLIC_SUBGRAPH_URL;

/**
 * Enriches strategies with subgraph-computed metrics (sharpe_ratio, max_drawdown, net_apy, risk_grade)
 * so the risk/APY filters work. The API strategy list typically lacks these; they come from the subgraph.
 */
export function useStrategiesWithMetrics(strategies: any[]) {
  const queries = useQueries({
    queries: strategies.map((s) => {
      const address = s.address || s.vault_address || s.contract_address;
      const subgraphUrl = s.subgraph_url || s.SUBGRAPH_URL || DEFAULT_SUBGRAPH_URL;
      const strategyName = s.symbol || s.id || "GENERIC";

      return {
        queryKey: ["strategy-metrics-for-filter", s.id || s.address, address, subgraphUrl],
        queryFn: () => fetchSubgraph(subgraphUrl, strategyName as any, address),
        enabled: Boolean(address && subgraphUrl),
        staleTime: 60_000,
      };
    }),
  });

  const enriched = strategies.map((s, i) => {
    const result = queries[i];
    const computed = result?.data?.computedMetrics;

    if (!computed || !result?.data) {
      return { ...s };
    }

    const sharpe = computed.sharpeRatio;
    const maxDd = computed.maxDrawdown;
    const riskGrade =
      Number.isFinite(sharpe) && Number.isFinite(maxDd)
        ? calculateRiskGrade(sharpe, Math.abs(maxDd))
        : s.risk_grade ?? s.riskGrade ?? "B";

    return {
      ...s,
      sharpe_ratio: sharpe,
      max_drawdown: maxDd,
      net_apy: computed.netApy,
      risk_grade: riskGrade,
    };
  });

  const isLoading = queries.some((q) => q.isLoading);

  return { strategiesWithMetrics: enriched, metricsLoading: isLoading };
}
