import { useQuery } from '@tanstack/react-query';

interface MAVCYearnConfig {
  vault_address?: string;
  token_address?: string;
  subgraph_url?: string;
  usdc_address?: string;
  net_apy?: number;
  aum?: number;
  sharpe_ratio?: number;
  max_drawdown?: number;
  lock_in_period?: string;
  participants?: number;
  performance_fee?: number;
  risk_grade?: string;
  name?: string;
  description?: string;
}

interface MAVCYearnConfigResponse {
  status: string;
  config: MAVCYearnConfig;
}

const fetchMAVCYearnConfig = async (): Promise<MAVCYearnConfig> => {
  const response = await fetch('/api/v1/config/mavc-yearn');
  if (!response.ok) {
    throw new Error('Failed to fetch MAVC Yearn configuration');
  }
  const data: MAVCYearnConfigResponse = await response.json();
  return data.config;
};

export const useMAVCYearnConfig = () => {
  return useQuery<MAVCYearnConfig, Error>({
    queryKey: ['mavc-yearn-config'],
    queryFn: fetchMAVCYearnConfig,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
};

