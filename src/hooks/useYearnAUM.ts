import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';

interface YearnVaultInfo {
  status: string;
  strategy: string;
  vault_address: string;
  total_assets: string;
  total_assets_formatted: number;
  total_supply: string;
  total_supply_formatted: number;
  decimals: number;
  price_per_share: number;
}

const fetchYearnAUM = async (strategyName: string): Promise<number> => {
  const response = await api.get<YearnVaultInfo>(`/api/v1/strategy/${strategyName}/vault-info`);
  return response.data.total_assets_formatted;
};

export const useYearnAUM = (strategyName: string) => {
  return useQuery<number, Error>({
    queryKey: [`${strategyName.toLowerCase()}-aum`],
    queryFn: () => fetchYearnAUM(strategyName),
    enabled: strategyName === 'MAVC_YEARN',
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
};

