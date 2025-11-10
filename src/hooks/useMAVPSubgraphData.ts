import { useQuery } from '@tanstack/react-query';
import { gql, GraphQLClient } from 'graphql-request';

const QUERY_WITH_OWNER = gql`
  query MAVPVaultAnalytics($owner: String!) {
    mavpvaultMetric(id: "mavp-vault") {
      totalDeposits
      totalWithdrawals
      mintedShares
      burnedShares
      uniqueDepositors
      uniqueWithdrawers
      lastUpdated
    }
    deposits(
      first: 1000
      where: { owner: $owner }
      orderBy: timestamp
      orderDirection: desc
    ) {
      id
      owner
      assets
      shares
      timestamp
    }
    withdrawals(
      first: 1000
      where: { owner: $owner }
      orderBy: timestamp
      orderDirection: desc
    ) {
      id
      owner
      receiver
      assets
      shares
      timestamp
    }
  }
`;

const QUERY_WITHOUT_OWNER = gql`
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

const fetchSubgraph = async (subgraphUrl: string, walletAddress?: string): Promise<MetricResult> => {
  const client = new GraphQLClient(subgraphUrl);
  const query = walletAddress ? QUERY_WITH_OWNER : QUERY_WITHOUT_OWNER;
  const variables = walletAddress ? { owner: walletAddress.toLowerCase() } : {};
  const data = await client.request<MetricResult>(query, variables);
  
  const filteredDeposits = data.deposits.filter(d => d.id.includes('-MAVP-'));
  const filteredWithdrawals = data.withdrawals.filter(w => w.id.includes('-MAVP-'));
  
  return {
    ...data,
    deposits: filteredDeposits,
    withdrawals: filteredWithdrawals
  };
};

export const useMAVPSubgraphData = (subgraphUrl?: string, walletAddress?: string) => {
  const enabled = Boolean(subgraphUrl);
  return useQuery<MetricResult, Error>({
    queryKey: ['mavp-subgraph', 'vault-analytics', subgraphUrl, walletAddress],
    queryFn: () => fetchSubgraph(subgraphUrl!, walletAddress),
    enabled,
    refetchInterval: enabled ? 5_000 : false,
    staleTime: 2_000,
    refetchOnWindowFocus: false,
    placeholderData: (previousData) => previousData, // keepPreviousData is deprecated, use placeholderData
  });
};
