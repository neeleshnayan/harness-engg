import { useQuery } from '@tanstack/react-query';
import { hedgeFundApi } from '@/lib/api';

export type StrategyName = 'YEARN_WETH';

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
  // Strategy description
  name?: string;
  description?: string;
}

interface StrategyConfigResponse {
  status: string;
  config: StrategyConfig;
}

const getConfigEndpoint = (strategyName: StrategyName): string => {
  switch (strategyName) {
    case 'YEARN_WETH':
      return '/api/v1/config/yearn-weth';
    default:
      throw new Error(`Unknown strategy: ${strategyName}`);
  }
};

const fetchStrategyConfig = async (strategyName: StrategyName): Promise<StrategyConfig> => {
  const endpoint = getConfigEndpoint(strategyName);
  const response = await hedgeFundApi.get<StrategyConfigResponse>(endpoint);
  return response.data.config;
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


