import { useQuery } from '@tanstack/react-query';

export type StrategyName = 'MAVC' | 'MAVP' | 'MAVC_YEARN';

interface StrategyConfig {
  vault_address?: string;
  contract_address?: string; // MAVP uses this
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
    case 'MAVC':
      return '/api/v1/config/mavc';
    case 'MAVP':
      return '/api/v1/config/mavp';
    case 'MAVC_YEARN':
      return '/api/v1/config/mavc-yearn';
    default:
      throw new Error(`Unknown strategy: ${strategyName}`);
  }
};

const fetchStrategyConfig = async (strategyName: StrategyName): Promise<StrategyConfig> => {
  const endpoint = getConfigEndpoint(strategyName);
  const response = await fetch(endpoint);
  if (!response.ok) {
    throw new Error(`Failed to fetch ${strategyName} configuration`);
  }
  const data: StrategyConfigResponse = await response.json();
  return data.config;
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

// Backward compatibility exports
export const useMAVCConfig = () => useStrategyConfig('MAVC');
export const useMAVPConfig = () => useStrategyConfig('MAVP');
export const useMAVCYearnConfig = () => useStrategyConfig('MAVC_YEARN');

