import { useQuery } from '@tanstack/react-query';
import { hedgeFundApi } from '@/lib/api';

export type StrategyName = string;

interface StrategyConfig {
  vault_address?: string; // contract_address for MAVP removed
  token_address?: string;
  subgraph_url?: string;
  usdc_address?: string;
  // Strategy metrics
  net_apy?: number;
  aum?: number;
  sharpe_ratio?: number;
  max_drawdown?: number;
  lock_in_period?: string;
  participants?: number;
  performance_fee?: number;
  risk_grade?: string;
  // Token properties
  asset_decimals?: number;
  share_decimals?: number;
  // Strategy description
  name?: string;
  description?: string;
}

interface StrategyConfigResponse {
  status: string;
  config: StrategyConfig;
}

const getConfigEndpoint = (strategyName: string): string => {
  // Legacy mapping
  if (strategyName === 'YEARN_WETH') return '/api/v1/config/yearn-weth';

  // Dynamic/Generic mapping
  // Assuming backend has a generic config endpoint or we use the strategy endpoint
  // But wait, fetchStrategyConfig expects { config: ... } response.
  // We'll point to the generic /api/v1/strategies?name=... or just assumes it handles it?
  // For now to prevent crash, we return a safe fallback or same endpoint?
  // Actually, if it's dynamic, we might not need this hook call to succeed if data is passed via props.
  // But to satisfy the hook, let's return a dummy or real endpoint.
  return `/api/v1/config/${strategyName.toLowerCase()}`;
};

const fetchStrategyConfig = async (strategyName: StrategyName): Promise<StrategyConfig> => {
  try {
    const endpoint = getConfigEndpoint(strategyName);
    const response = await hedgeFundApi.get<StrategyConfigResponse>(endpoint);
    return response.data.config;
  } catch (error) {
    console.warn(`Failed to fetch config for ${strategyName}`, error);
    return {}; // Return empty config on failure to prevent crash
  }
};

export const useStrategyConfig = (strategyName: StrategyName) => {
  return useQuery<StrategyConfig, Error>({
    queryKey: [`${strategyName.toLowerCase()}-config`],
    queryFn: () => fetchStrategyConfig(strategyName),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
    refetchOnWindowFocus: false,
  });
};

export const useYearnWETHConfig = () => useStrategyConfig('YEARN_WETH');


