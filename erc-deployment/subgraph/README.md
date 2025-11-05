# MAVC Vault Subgraph

Tracks deposits and withdrawals for the `MultiAssetVaultUSDCWETH` contract on Sepolia, exposing MAVC share analytics.

## Getting Started

1. Install dependencies inside `subgraph/`:
   ```bash
   cd subgraph
   npm install
   ```
2. Update `subgraph.yaml`:
   - `source.address`: deployed vault contract
   - `source.startBlock`: block where the vault was created
3. Generate AssemblyScript types:
   ```bash
   npm run codegen
   npm run build
   ```
4. Deploy to The Graph (Hosted Service or Subgraph Studio):
   ```bash
   npm run deploy -- --access-token YOUR_TOKEN
   ```
   Replace the `deploy` script target with your actual subgraph slug when using Studio/Hosted service.

## Query Examples

```graphql
{
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
}
```

Use the resulting HTTPS endpoint in `frontend/.env` as `VITE_SUBGRAPH_URL` so the UI can surface live MAVC analytics.
