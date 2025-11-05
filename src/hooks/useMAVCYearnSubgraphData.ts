import { useQuery } from '@tanstack/react-query';
import { gql, GraphQLClient } from 'graphql-request';

const QUERY = gql`
  query MAVCYearnVaultAnalytics {
    mavcyearnVaultMetric(id: "mavc-yearn-vault") {
      totalDeposits
      totalWithdrawals
      mintedShares
      burnedShares
      uniqueDepositors
      uniqueWithdrawers
      lastUpdated
    }
    deposits(first: 1000, orderBy: timestamp, orderDirection: desc) {
      id
      owner
      assets
      shares
      timestamp
    }
    withdrawals(first: 1000, orderBy: timestamp, orderDirection: desc) {
      id
      owner
      receiver
      assets
      shares
      timestamp
    }
  }
`;

type MetricResult = {
  mavcyearnVaultMetric: {
    totalDeposits: string;
    totalWithdrawals: string;
    mintedShares: string;
    burnedShares: string;
    uniqueDepositors: number;
    uniqueWithdrawers: number;
    lastUpdated: string;
  } | null;
  deposits: Array<{
    id: string;
    owner: string;
    assets: string;
    shares: string;
    timestamp: string;
  }>;
  withdrawals: Array<{
    id: string;
    owner: string;
    receiver: string;
    assets: string;
    shares: string;
    timestamp: string;
  }>;
};

const fetchSubgraph = async (subgraphUrl: string): Promise<MetricResult> => {
  try {
    const client = new GraphQLClient(subgraphUrl);
    const data = await client.request<MetricResult>(QUERY);
    
    const filteredDeposits = data.deposits.filter(d => d.id.includes('MAVC-YEARN'));
    const filteredWithdrawals = data.withdrawals.filter(w => w.id.includes('MAVC-YEARN'));
    
    return {
      ...data,
      deposits: filteredDeposits,
      withdrawals: filteredWithdrawals
    };
  } catch (error: any) {
    const errorMessage = error?.response?.errors?.[0]?.message || error?.message || 'Unknown error';
    throw new Error(`Subgraph query failed: ${errorMessage}`);
  }
};

export const useMAVCYearnSubgraphData = (subgraphUrl?: string) => {
  const enabled = Boolean(subgraphUrl);
  return useQuery<MetricResult, Error>({
    queryKey: ['subgraph', 'mavc-yearn-vault-analytics', subgraphUrl],
    queryFn: () => fetchSubgraph(subgraphUrl!),
    enabled,
    refetchInterval: enabled ? 5_000 : false,
    staleTime: 2_000,
    refetchOnWindowFocus: false,
    placeholderData: (previousData) => previousData,
  });
};

