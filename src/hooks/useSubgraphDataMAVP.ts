import { useQuery } from '@tanstack/react-query';
import { gql, GraphQLClient } from 'graphql-request';

const QUERY = gql`
  query MAVPVaultAnalytics {
    mavpvaultMetric(id: "mavp-vault") {
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
  mavpvaultMetric: {
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
  
  // Filter deposits and withdrawals to only include MAVP ones (ID contains "-MAVP-")
  const filteredDeposits = data.deposits.filter(d => d.id.includes('-MAVP-')).slice(0, 5);
  const filteredWithdrawals = data.withdrawals.filter(w => w.id.includes('-MAVP-')).slice(0, 5);
  
  return {
    ...data,
    deposits: filteredDeposits,
    withdrawals: filteredWithdrawals
  };
};

export const useSubgraphDataMAVP = (subgraphUrl?: string) => {
  const enabled = Boolean(subgraphUrl);
  return useQuery<MetricResult, Error>({
    queryKey: ['subgraph', 'mavp-vault-analytics', subgraphUrl],
    queryFn: () => fetchSubgraph(subgraphUrl!),
    enabled,
    refetchInterval: enabled ? 5_000 : false,
    staleTime: 2_000,
    refetchOnWindowFocus: false,
    placeholderData: (previousData) => previousData,
  });
};

