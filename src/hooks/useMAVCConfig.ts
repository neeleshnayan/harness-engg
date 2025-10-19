import { useQuery } from '@tanstack/react-query';

interface MAVCConfig {
  vault_address?: string;
  subgraph_url?: string;
  usdc_address?: string;
}

interface MAVCConfigResponse {
  status: string;
  config: MAVCConfig;
}

const fetchMAVCConfig = async (): Promise<MAVCConfig> => {
  const response = await fetch('/api/v1/config/mavc');
  if (!response.ok) {
    throw new Error('Failed to fetch MAVC configuration');
  }
  const data: MAVCConfigResponse = await response.json();
  return data.config;
};

export const useMAVCConfig = () => {
  return useQuery<MAVCConfig, Error>({
    queryKey: ['mavc-config'],
    queryFn: fetchMAVCConfig,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes (cacheTime is deprecated, use gcTime)
    refetchOnWindowFocus: false,
  });
};