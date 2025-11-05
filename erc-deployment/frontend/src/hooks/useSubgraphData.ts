import { gql, GraphQLClient } from 'graphql-request';
import { useQuery } from '@tanstack/react-query';
import { env } from '@/config/env';

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
    mavcPriceCurrent(id: "current") {
      price
      lastUpdate
      updateCount
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
  mavcPriceCurrent: {
    price: string;
    lastUpdate: string;
    updateCount: number;
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

const fetchSubgraph = async (): Promise<MetricResult> => {
  if (!env.subgraphUrl) {
    throw new Error('Subgraph URL not configured');
  }
  const client = new GraphQLClient(env.subgraphUrl);
  const data = await client.request<MetricResult>(QUERY);
  return data;
};

export const useSubgraphData = () => {
  const enabled = Boolean(env.subgraphUrl);
  return useQuery({
    queryKey: ['subgraph', 'vault-analytics'],
    queryFn: fetchSubgraph,
    enabled,
    refetchInterval: enabled ? 60_000 : false,
  });
};
