/**
 * THIS MODULE IS A HOLLOWED-OUT STUB AND ITS ONE CALLER DOES NOT KNOW.
 *
 * Found 2026-08-27 while removing dead exports. `useStrategyPrice` below has
 * `enabled: false` and `queryFn: async () => null`, so
 * `StrategyCard.tsx:75` — a CUSTOMER-FACING card — destructures
 * `{ data, isLoading, error }` and receives `undefined`, `false` and `null`
 * FOREVER. A price that never loads and never errors renders as a quiet
 * nothing, which is absence wearing the shape of a measurement.
 *
 * NOT REPAIRED HERE: this is the wallet product's surface and a desk
 * dispatch is the wrong place to decide whether the subgraph query comes
 * back or the card stops asking. Reported so somebody chooses.
 *
 * What WAS done: five private helpers (`getStrategyPriceId`,
 * `createPriceQuery`, `createPriceHistoryQuery`, `fetchStrategyPrice`,
 * `fetchStrategyPriceHistory`) and the `graphql-request` import were removed.
 * All six were already unreferenced BEFORE this diff — verified against
 * HEAD — and every one of them returned `''`, `null` or `[]`.
 */
import { useQuery } from '@tanstack/react-query';
import { StrategyName } from './useStrategyConfig';

interface StrategyPriceCurrent {
  price: string;
  lastUpdate: string;
  updateCount?: number;
  strategy?: string;
}

export interface StrategyPriceUpdate {
  id: string;
  txHash: string;
  price: string;
  timestamp: string;
  strategy?: string;
}

export const useStrategyPrice = (strategyName: StrategyName, subgraphUrl?: string) => {
  return useQuery<StrategyPriceCurrent | null, Error>({
    queryKey: [`${strategyName.toLowerCase()}-price`, subgraphUrl],
    queryFn: async () => null,
    enabled: false,
    staleTime: Infinity,
  });
};

/* `useStrategyPriceHistory` and `MAVPPriceUpdate` removed 2026-08-27: no
   consumer anywhere in the repository. The hook was a STUB — `queryFn: async
   () => []` with `enabled: false` — so nothing was lost that ever ran, and
   the type was an alias explicitly labelled "backward compatibility" for a
   caller that no longer exists. */
