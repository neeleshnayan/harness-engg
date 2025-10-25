import { useQuery } from '@tanstack/react-query';

interface MAVPConfig {
  contract_address?: string;
  subgraph_url?: string;
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

interface MAVPConfigResponse {
  status: string;
  config: MAVPConfig;
}

const fetchMAVPConfig = async (): Promise<MAVPConfig> => {
  const response = await fetch('/api/v1/config/mavp');
  if (!response.ok) {
    throw new Error('Failed to fetch MAVP configuration');
  }
  const data: MAVPConfigResponse = await response.json();
  return data.config;
};

export const useMAVPConfig = () => {
  return useQuery<MAVPConfig, Error>({
    queryKey: ['mavp-config'],
    queryFn: fetchMAVPConfig,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes (cacheTime is deprecated, use gcTime)
    refetchOnWindowFocus: false,
  });
};
