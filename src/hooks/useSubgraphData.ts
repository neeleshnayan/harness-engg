import { useQuery } from '@tanstack/react-query';
import { gql, GraphQLClient } from 'graphql-request';

const QUERY = gql`
  query VaultAnalytics {
    mavcvaultMetric(id: "mavc-vault") {
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
  mavcvaultMetric: {
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
  const client = new GraphQLClient(subgraphUrl);
  const data = await client.request<MetricResult>(QUERY);
  
  const filteredDeposits = data.deposits.filter(d => d.id.includes('-MAVC-'));
  const filteredWithdrawals = data.withdrawals.filter(w => w.id.includes('-MAVC-'));
  
  return {
    ...data,
    deposits: filteredDeposits,
    withdrawals: filteredWithdrawals
  };
};

export const useSubgraphData = (subgraphUrl?: string) => {
  const enabled = Boolean(subgraphUrl);
  return useQuery<MetricResult, Error>({
    queryKey: ['subgraph', 'vault-analytics', subgraphUrl],
    queryFn: () => fetchSubgraph(subgraphUrl!),
    enabled,
    refetchInterval: enabled ? 5_000 : false,
    staleTime: 2_000,
    refetchOnWindowFocus: false,
    placeholderData: (previousData) => previousData, // keepPreviousData is deprecated, use placeholderData
  });
};

