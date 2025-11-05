# MAVC Price Oracle & Subgraph Integration Documentation

## Overview

The Multi-Asset Vault Coin (MAVC) implements a sophisticated price tracking mechanism using Chainlink oracles. The vault contract calculates MAVC price based on its underlying assets (USDC and WETH) and emits price update events that are indexed by The Graph subgraph for easy querying.

## Table of Contents

1. [Price Calculation Formula](#price-calculation-formula)
2. [Smart Contract Integration](#smart-contract-integration)
3. [Subgraph Schema](#subgraph-schema)
4. [Querying MAVC Price](#querying-mavc-price)
5. [Integration Examples](#integration-examples)
6. [Frontend Integration](#frontend-integration)

---

## Price Calculation Formula

The MAVC token price is calculated using the following formula:

```
1 MAVC = 0.005 × USDC_Price + 0.005 × WETH_Price
```

### Details:
- **Price Source**: Chainlink Price Oracles (USDC/USD and ETH/USD feeds)
- **Price Precision**: 8 decimals (same as Chainlink standard)
- **Asset Allocation**: 50/50 split between USDC and WETH
- **Update Interval**: Minimum 30 minutes between updates

### Example Calculation:

```
Given:
- USDC Price: $1.00 (100000000 in 8 decimals)
- ETH Price: $2,500.00 (250000000000 in 8 decimals)

MAVC Price = (0.005 × 100000000) + (0.005 × 250000000000)
           = 500000 + 12500000000
           = 12500500000 (in 8 decimals)
           = $125.00500000
```

---

## Smart Contract Integration

### Contract: MultiAssetVaultUSDCWETH.sol

The vault contract provides three main functions for price management:

#### 1. Real-Time Price Calculation (View Function)

```solidity
function getMAVCPrice() public view returns (uint256 mavcPrice)
```

**Purpose**: Get the current MAVC price calculated in real-time from Chainlink oracles.

**Returns**: Price in USD with 8 decimals

**Usage**:
```solidity
// Get live price (no gas cost - view function)
uint256 currentPrice = vault.getMAVCPrice();
// Example: 12500500000 = $125.00500000
```

**Details**:
- Pure view function (no state changes)
- Calls Chainlink oracles directly
- No update restrictions
- Suitable for display/calculations

---

#### 2. Cached Price Retrieval (View Function)

```solidity
function getCachedMAVCPrice() external view returns (uint256 price, uint256 lastUpdate)
```

**Purpose**: Get the last cached/stored MAVC price and its update timestamp.

**Returns**:
- `price`: Last updated price (8 decimals)
- `lastUpdate`: Unix timestamp of last update

**Usage**:
```solidity
(uint256 price, uint256 timestamp) = vault.getCachedMAVCPrice();

// Check if price is stale
bool isStale = block.timestamp > timestamp + 30 minutes;
```

**Details**:
- Returns stored state variables
- Gas efficient for reading
- Updated only when updateMAVCPrice() is called

---

#### 3. Manual Price Update (State-Changing Function)

```solidity
function updateMAVCPrice() external returns (uint256 newPrice)
```

**Purpose**: Update the cached MAVC price and emit event for subgraph indexing.

**Returns**: The newly updated price

**Restrictions**:
- Can only be called once every 30 minutes
- Reverts if called too soon: `"Price update interval not reached"`

**Usage**:
```solidity
// Update price (requires 30 min since last update)
try vault.updateMAVCPrice() returns (uint256 newPrice) {
    console.log("Price updated to:", newPrice);
} catch Error(string memory reason) {
    console.log("Update failed:", reason);
}
```

**Event Emitted**:
```solidity
event MAVCPriceUpdated(uint256 newPrice, uint256 timestamp);
```

**Who Should Call This**:
- External automation services (Chainlink Keepers, Gelato)
- Subgraph indexers
- Backend services
- Manual calls during low activity periods

---

### Price Update Workflow

```
┌─────────────────────┐
│  External Caller    │
│  (Keeper/Service)   │
└──────────┬──────────┘
           │
           │ Calls updateMAVCPrice()
           │ (max once per 30 min)
           ▼
┌─────────────────────────────┐
│   Vault Contract            │
│                             │
│  1. Check time interval     │
│  2. Fetch USDC price        │◄──── Chainlink Oracle
│  3. Fetch WETH price        │◄──── Chainlink Oracle
│  4. Calculate MAVC price    │
│  5. Store in mavcPriceUSD   │
│  6. Emit MAVCPriceUpdated   │
└──────────┬──────────────────┘
           │
           │ Event: MAVCPriceUpdated
           ▼
┌─────────────────────────────┐
│   The Graph Subgraph        │
│                             │
│  1. Listen for events       │
│  2. Index price update      │
│  3. Store in GraphQL DB     │
│  4. Update MAVCPriceCurrent │
└──────────┬──────────────────┘
           │
           │ GraphQL Query
           ▼
┌─────────────────────────────┐
│   External Applications     │
│   (Frontend, Analytics,     │
│    Trading Bots, etc.)      │
└─────────────────────────────┘
```

---

## Subgraph Schema

The Graph subgraph indexes all price updates with two entity types:

### 1. MAVCPriceUpdate (Immutable Historical Records)

```graphql
type MAVCPriceUpdate @entity(immutable: true) {
  id: ID!              # Transaction hash + log index
  txHash: Bytes!       # Transaction that triggered update
  price: BigDecimal!   # MAVC price in USD (8 decimals converted to decimal)
  timestamp: BigInt!   # Block timestamp
}
```

**Purpose**: Store complete historical record of all price updates.

**Immutability**: Never modified after creation.

**Query Examples**:
```graphql
# Get last 10 price updates
{
  mavcPriceUpdates(first: 10, orderBy: timestamp, orderDirection: desc) {
    id
    price
    timestamp
    txHash
  }
}

# Get price updates within time range
{
  mavcPriceUpdates(
    where: {
      timestamp_gte: "1704067200"  # Jan 1, 2024
      timestamp_lte: "1735689600"  # Jan 1, 2025
    }
    orderBy: timestamp
    orderDirection: asc
  ) {
    price
    timestamp
  }
}
```

---

### 2. MAVCPriceCurrent (Latest Price - Mutable)

```graphql
type MAVCPriceCurrent @entity(immutable: false) {
  id: ID!              # Always "current"
  price: BigDecimal!   # Latest MAVC price in USD
  lastUpdate: BigInt!  # Timestamp of last update
  updateCount: Int!    # Total number of updates
}
```

**Purpose**: Quick access to the latest price without sorting.

**ID**: Always `"current"` (singleton entity).

**Query Example**:
```graphql
# Get current MAVC price
{
  mavcPriceCurrent(id: "current") {
    price
    lastUpdate
    updateCount
  }
}
```

**Response Example**:
```json
{
  "data": {
    "mavcPriceCurrent": {
      "price": "125.00500000",
      "lastUpdate": "1704123456",
      "updateCount": 142
    }
  }
}
```

---

## Querying MAVC Price

### Basic Queries

#### 1. Get Current Price

```graphql
query GetCurrentMAVCPrice {
  mavcPriceCurrent(id: "current") {
    price
    lastUpdate
    updateCount
  }
}
```

#### 2. Get Price History

```graphql
query GetPriceHistory($first: Int!, $skip: Int!) {
  mavcPriceUpdates(
    first: $first
    skip: $skip
    orderBy: timestamp
    orderDirection: desc
  ) {
    id
    price
    timestamp
    txHash
  }
}
```

#### 3. Get Price Changes Over Time

```graphql
query GetPriceChanges($startTime: BigInt!, $endTime: BigInt!) {
  mavcPriceUpdates(
    where: {
      timestamp_gte: $startTime
      timestamp_lte: $endTime
    }
    orderBy: timestamp
    orderDirection: asc
  ) {
    price
    timestamp
  }
}
```

#### 4. Combined Vault Analytics with Price

```graphql
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
  mavcPriceUpdates(first: 5, orderBy: timestamp, orderDirection: desc) {
    price
    timestamp
  }
}
```

---

## Integration Examples

### JavaScript/TypeScript (Using graphql-request)

```typescript
import { GraphQLClient, gql } from 'graphql-request';

const SUBGRAPH_URL = 'https://api.studio.thegraph.com/query/<your-id>/<subgraph-name>/version/latest';

const client = new GraphQLClient(SUBGRAPH_URL);

// Get current MAVC price
async function getCurrentPrice() {
  const query = gql`
    query {
      mavcPriceCurrent(id: "current") {
        price
        lastUpdate
        updateCount
      }
    }
  `;

  const data = await client.request(query);
  return data.mavcPriceCurrent;
}

// Usage
const priceData = await getCurrentPrice();
console.log(`Current MAVC Price: $${priceData.price}`);
console.log(`Last Updated: ${new Date(Number(priceData.lastUpdate) * 1000).toLocaleString()}`);
console.log(`Total Updates: ${priceData.updateCount}`);
```

### React Hook (Using @tanstack/react-query)

```typescript
import { useQuery } from '@tanstack/react-query';
import { GraphQLClient, gql } from 'graphql-request';

const SUBGRAPH_URL = process.env.NEXT_PUBLIC_SUBGRAPH_URL!;

const PRICE_QUERY = gql`
  query {
    mavcPriceCurrent(id: "current") {
      price
      lastUpdate
      updateCount
    }
  }
`;

export function useMAVCPrice() {
  return useQuery({
    queryKey: ['mavc-price'],
    queryFn: async () => {
      const client = new GraphQLClient(SUBGRAPH_URL);
      const data = await client.request(PRICE_QUERY);
      return data.mavcPriceCurrent;
    },
    refetchInterval: 60_000, // Refresh every 60 seconds
    staleTime: 30_000,        // Data fresh for 30 seconds
  });
}

// Component usage
function PriceDisplay() {
  const { data, isLoading, error } = useMAVCPrice();

  if (isLoading) return <div>Loading price...</div>;
  if (error) return <div>Error loading price</div>;

  return (
    <div>
      <h2>MAVC Price: ${data?.price}</h2>
      <p>Last Updated: {new Date(Number(data?.lastUpdate) * 1000).toLocaleString()}</p>
    </div>
  );
}
```

### Python (Using gql)

```python
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport

SUBGRAPH_URL = 'https://api.studio.thegraph.com/query/<your-id>/<subgraph-name>/version/latest'

transport = RequestsHTTPTransport(url=SUBGRAPH_URL)
client = Client(transport=transport, fetch_schema_from_transport=True)

# Get current price
query = gql('''
    query {
        mavcPriceCurrent(id: "current") {
            price
            lastUpdate
            updateCount
        }
    }
''')

result = client.execute(query)
price_data = result['mavcPriceCurrent']

print(f"Current MAVC Price: ${price_data['price']}")
print(f"Last Update: {price_data['lastUpdate']}")
print(f"Total Updates: {price_data['updateCount']}")
```

### cURL (Raw HTTP Request)

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "query": "{ mavcPriceCurrent(id: \"current\") { price lastUpdate updateCount } }"
  }' \
  https://api.studio.thegraph.com/query/<your-id>/<subgraph-name>/version/latest
```

---

## Frontend Integration

### Complete Example with Error Handling

```typescript
// hooks/useMAVCPrice.ts
import { gql, GraphQLClient } from 'graphql-request';
import { useQuery } from '@tanstack/react-query';

const QUERY = gql`
  query MAVCPriceData {
    mavcPriceCurrent(id: "current") {
      price
      lastUpdate
      updateCount
    }
    mavcPriceUpdates(first: 24, orderBy: timestamp, orderDirection: desc) {
      price
      timestamp
    }
  }
`;

type PriceData = {
  mavcPriceCurrent: {
    price: string;
    lastUpdate: string;
    updateCount: number;
  } | null;
  mavcPriceUpdates: Array<{
    price: string;
    timestamp: string;
  }>;
};

const fetchPriceData = async (): Promise<PriceData> => {
  const client = new GraphQLClient(process.env.NEXT_PUBLIC_SUBGRAPH_URL!);
  return await client.request<PriceData>(QUERY);
};

export const useMAVCPrice = () => {
  return useQuery({
    queryKey: ['mavc-price-data'],
    queryFn: fetchPriceData,
    refetchInterval: 60_000, // Poll every minute
    staleTime: 30_000,
  });
};
```

```typescript
// components/MAVCPriceCard.tsx
import React from 'react';
import { useMAVCPrice } from '@/hooks/useMAVCPrice';

export function MAVCPriceCard() {
  const { data, isLoading, error, isError } = useMAVCPrice();

  if (isLoading) {
    return (
      <div className="price-card loading">
        <div className="spinner" />
        <p>Loading MAVC price...</p>
      </div>
    );
  }

  if (isError || !data?.mavcPriceCurrent) {
    return (
      <div className="price-card error">
        <p>Unable to load price data</p>
        <p className="error-msg">{error?.message}</p>
      </div>
    );
  }

  const { price, lastUpdate, updateCount } = data.mavcPriceCurrent;
  const lastUpdateDate = new Date(Number(lastUpdate) * 1000);
  const timeSinceUpdate = Date.now() - lastUpdateDate.getTime();
  const minutesSinceUpdate = Math.floor(timeSinceUpdate / 60000);

  // Calculate 24h price change
  const priceHistory = data.mavcPriceUpdates;
  const priceChange24h = priceHistory.length >= 2
    ? ((Number(price) - Number(priceHistory[priceHistory.length - 1].price)) / Number(priceHistory[priceHistory.length - 1].price) * 100)
    : 0;

  return (
    <div className="price-card">
      <div className="price-header">
        <h2>MAVC Token Price</h2>
        <span className="update-badge">
          Updated {minutesSinceUpdate}m ago
        </span>
      </div>

      <div className="price-value">
        <span className="currency">$</span>
        <span className="amount">{Number(price).toFixed(8)}</span>
      </div>

      <div className="price-change">
        <span className={priceChange24h >= 0 ? 'positive' : 'negative'}>
          {priceChange24h >= 0 ? '↑' : '↓'} {Math.abs(priceChange24h).toFixed(2)}%
        </span>
        <span className="period">24h</span>
      </div>

      <div className="price-metadata">
        <div className="metadata-item">
          <span className="label">Total Updates</span>
          <span className="value">{updateCount}</span>
        </div>
        <div className="metadata-item">
          <span className="label">Last Update</span>
          <span className="value">{lastUpdateDate.toLocaleTimeString()}</span>
        </div>
      </div>

      <div className="price-chart">
        {/* Mini chart of recent price history */}
        {priceHistory.map((update, idx) => (
          <div
            key={idx}
            className="chart-bar"
            style={{
              height: `${(Number(update.price) / Number(price)) * 100}%`
            }}
          />
        ))}
      </div>
    </div>
  );
}
```

---

## Advanced Use Cases

### 1. Price Alerts

```typescript
import { useEffect } from 'react';
import { useMAVCPrice } from '@/hooks/useMAVCPrice';

function usePriceAlert(targetPrice: number, onAlert: () => void) {
  const { data } = useMAVCPrice();

  useEffect(() => {
    if (data?.mavcPriceCurrent) {
      const currentPrice = Number(data.mavcPriceCurrent.price);
      if (currentPrice >= targetPrice) {
        onAlert();
      }
    }
  }, [data, targetPrice, onAlert]);
}
```

### 2. Historical Price Analysis

```typescript
async function analyzePriceTrend(days: number) {
  const client = new GraphQLClient(SUBGRAPH_URL);

  const startTime = Math.floor(Date.now() / 1000) - (days * 24 * 60 * 60);

  const query = gql`
    query ($startTime: BigInt!) {
      mavcPriceUpdates(
        where: { timestamp_gte: $startTime }
        orderBy: timestamp
        orderDirection: asc
      ) {
        price
        timestamp
      }
    }
  `;

  const data = await client.request(query, { startTime: startTime.toString() });

  const prices = data.mavcPriceUpdates.map(u => Number(u.price));
  const avg = prices.reduce((a, b) => a + b, 0) / prices.length;
  const min = Math.min(...prices);
  const max = Math.max(...prices);

  return { avg, min, max, count: prices.length };
}
```

### 3. Real-time Price Websocket (GraphQL Subscriptions)

```typescript
import { createClient } from 'graphql-ws';

const wsClient = createClient({
  url: 'wss://api.studio.thegraph.com/query/<your-id>/<subgraph-name>/version/latest'
});

const subscription = `
  subscription {
    mavcPriceUpdates(orderBy: timestamp, orderDirection: desc, first: 1) {
      price
      timestamp
    }
  }
`;

wsClient.subscribe(
  { query: subscription },
  {
    next: (data) => {
      console.log('New price update:', data);
    },
    error: (err) => {
      console.error('Subscription error:', err);
    },
    complete: () => {
      console.log('Subscription completed');
    }
  }
);
```

---

## Best Practices

### 1. Caching Strategy
- Use `getCachedMAVCPrice()` for on-chain reads to save gas
- Use `getMAVCPrice()` when you need absolute latest price
- Cache subgraph responses for 30-60 seconds

### 2. Update Frequency
- Set up automated calls to `updateMAVCPrice()` every 30 minutes
- Use Chainlink Keepers or similar service for reliability
- Monitor for failed updates and alert on staleness

### 3. Error Handling
- Always check if `mavcPriceCurrent` exists before using
- Handle network failures gracefully
- Display last known price with staleness indicator

### 4. Performance
- Use pagination for historical queries
- Limit `first` parameter to reasonable values (< 1000)
- Implement client-side caching with React Query or SWR

### 5. Security
- Never trust price data for critical operations without validation
- Implement circuit breakers for extreme price movements
- Use time-weighted averages for sensitive calculations

---

## Troubleshooting

### Subgraph Not Returning Data

1. **Check deployment status**: Ensure subgraph is fully synced
2. **Verify contract events**: Check that `updateMAVCPrice()` has been called
3. **Test direct contract call**: Call `getCachedMAVCPrice()` to verify on-chain data

### Stale Price Data

```typescript
function isPriceStale(lastUpdate: string): boolean {
  const updateTime = Number(lastUpdate) * 1000;
  const stalePeriod = 45 * 60 * 1000; // 45 minutes
  return Date.now() - updateTime > stalePeriod;
}
```

### Rate Limiting

If hitting subgraph rate limits:
- Increase polling interval
- Implement exponential backoff
- Use query batching
- Consider running your own Graph node

---

## Contract Addresses

**Sepolia Testnet**:
- Vault: `<YOUR_VAULT_ADDRESS>`
- Chainlink USDC/USD: `<ORACLE_ADDRESS>`
- Chainlink ETH/USD: `<ORACLE_ADDRESS>`

**Subgraph Endpoints**:
- Development: `https://api.studio.thegraph.com/query/<id>/<name>/<version>`
- Production: `https://gateway.thegraph.com/api/<key>/subgraphs/id/<subgraph-id>`

---

## Support & Resources

- **The Graph Docs**: https://thegraph.com/docs/
- **Chainlink Price Feeds**: https://docs.chain.link/data-feeds/price-feeds
- **ERC-4626 Standard**: https://eips.ethereum.org/EIPS/eip-4626

---

*Last Updated: 2025-10-23*
