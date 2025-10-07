# Subgraph Analytics Setup

This project includes comprehensive subgraph analytics for the MAVC (Multi Asset Vault) token, similar to the erc-deployment frontend implementation.

## Features

- **Real-time Vault Metrics**: Total deposits, withdrawals, MAVC minted/burned
- **Interactive Charts**: USD flow and MAVC mint/burn trends over time
- **Transaction History**: Recent deposits and withdrawals with user addresses
- **Auto-refresh**: Data updates every minute when subgraph is configured

## Setup

### 1. Environment Configuration

Add the following to your `.env.local` file:

```bash
# Subgraph Configuration
NEXT_PUBLIC_SUBGRAPH_URL=https://api.thegraph.com/subgraphs/name/your-username/your-subgraph-name
```

### 2. Subgraph Deployment

The analytics expect a subgraph with the following schema (based on erc-deployment):

```graphql
type VaultMetric @entity {
  id: ID!
  totalDeposits: BigDecimal!
  totalWithdrawals: BigDecimal!
  mintedShares: BigDecimal!
  burnedShares: BigDecimal!
  uniqueDepositors: Int!
  uniqueWithdrawers: Int!
  lastUpdated: BigInt!
}

type Deposit @entity {
  id: ID!
  txHash: Bytes!
  sender: Bytes!
  owner: Bytes!
  assets: BigDecimal!
  shares: BigDecimal!
  timestamp: BigInt!
}

type Withdrawal @entity {
  id: ID!
  txHash: Bytes!
  sender: Bytes!
  owner: Bytes!
  receiver: Bytes!
  assets: BigDecimal!
  shares: BigDecimal!
  timestamp: BigInt!
}
```

### 3. GraphQL Query

The analytics use this query to fetch data:

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
```

## Usage

Once configured, the analytics will automatically appear below the MAVC card in the Hedge Fund V2 page (`/customer/grow/hedge-fund-v2`).

### Without Subgraph

If no subgraph URL is configured, a helpful message will be displayed explaining how to set it up.

### With Subgraph

When properly configured, you'll see:
- **Metrics Cards**: Total deposits, withdrawals, MAVC minted, and net supply
- **Charts**: Interactive line and area charts showing trends over time
- **Transaction Lists**: Recent deposits and withdrawals with timestamps and addresses

## Components

- `useSubgraphData.ts` - React Query hook for fetching subgraph data
- `SubgraphAnalytics.tsx` - Main analytics component with charts and metrics
- `MAVCCard.tsx` - Updated to include analytics section

## Dependencies

The following packages are required for the analytics:

```bash
npm install recharts graphql-request @tanstack/react-query
```

## Styling

The analytics use a dark theme consistent with the rest of the application, with:
- Zinc color palette for backgrounds and borders
- Gradient charts with purple and pink accents
- Responsive grid layouts
- Smooth animations and transitions

