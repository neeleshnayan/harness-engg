import { useQuery } from '@tanstack/react-query';
import { gql, GraphQLClient } from 'graphql-request';

const QUERY = gql`
  query VaultAnalytics {
    vaultMetric(id: "vault") {
      totalDeposits
      totalWithdrawals
      mintedShares
      burnedShares
      uniqueDepositors
      uniqueWithdrawers
      lastUpdated
    }
    deposits(first: 5, orderBy: timestamp, orderDirection: desc) {
      id
      owner
      assets
      shares
      timestamp
    }
    withdrawals(first: 5, orderBy: timestamp, orderDirection: desc) {
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
  vaultMetric: {
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
  return data;
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

