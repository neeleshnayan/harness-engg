# MAVP and MAVC Separation - Subgraph Update

## Changes Made

The subgraph has been updated to properly separate MAVC and MAVP vault metrics, deposits, and withdrawals. Previously, both vaults were writing to the same `VaultMetric` entity, causing data conflicts.

### Schema Changes

Added two new entities:
- `MAVCVaultMetric` - Tracks MAVC-specific metrics
- `MAVPVaultMetric` - Tracks MAVP-specific metrics

Both have the same structure as the original `VaultMetric` but are tracked independently.

### Mapping Changes

1. **Separate Metric IDs**:
   - MAVC: `mavc-vault`
   - MAVP: `mavp-vault`

2. **Handler Updates**:
   - `handleDeposit()` → Uses `getMAVCMetric()` and tags deposits with `-MAVC-`
   - `handleWithdraw()` → Uses `getMAVCMetric()` and tags withdrawals with `-MAVC-`
   - `handleMAVPDeposit()` → Uses `getMAVPMetric()` and tags deposits with `-MAVP-`
   - `handleMAVPWithdraw()` → Uses `getMAVPMetric()` and tags withdrawals with `-MAVP-`

3. **Participant Tracking**:
   - Updated to include vault identifier to prevent cross-contamination

### Frontend Changes

1. **New Hook**: `useSubgraphDataMAVP.ts`
   - Queries `mavpvaultMetric(id: "mavp-vault")`
   - Client-side filters deposits/withdrawals containing `-MAVP-` in ID

2. **Updated Hook**: `useSubgraphData.ts`
   - Now queries `mavcvaultMetric(id: "mavc-vault")`
   - Client-side filters deposits/withdrawals containing `-MAVC-` in ID

3. **Updated Hook**: `useMAVPSubgraphData.ts`
   - Queries `mavpvaultMetric(id: "mavp-vault")` for strategy card
   - Client-side filters deposits/withdrawals containing `-MAVP-` in ID

4. **Component Updates**:
   - `SubgraphAnalytics.tsx` → Uses `mavcvaultMetric`
   - `SubgraphAnalyticsMAVP.tsx` → Uses `mavpvaultMetric` and `useSubgraphDataMAVP`
   - `MAVPStrategyCard.tsx` → Fixed to use `mavpvaultMetric` field

**Note**: GraphQL subgraphs don't support `id_contains` filter, so we fetch more records and filter client-side.

## Deployment Steps

### 1. Regenerate Subgraph Code

```bash
cd erc-deployment/subgraph
graph codegen
graph build
```

### 2. Deploy to The Graph Studio

```bash
graph deploy --studio mavp
```

Or if using separate subgraphs:

```bash
# For MAVC
graph deploy --studio mavc

# For MAVP  
graph deploy --studio mavp
```

### 3. Wait for Syncing

The subgraph will need to re-index from the start blocks:
- MAVC: Block 9477000
- MAVP: Block 9535705

### 4. Verify Data Separation

Query both metrics independently:

```graphql
# MAVC Query
{
  mavcvaultMetric(id: "mavc-vault") {
    totalDeposits
    totalWithdrawals
    mintedShares
    burnedShares
  }
}

# MAVP Query
{
  mavpvaultMetric(id: "mavp-vault") {
    totalDeposits
    totalWithdrawals
    mintedShares
    burnedShares
  }
}
```

## Breaking Changes

**Frontend queries must be updated** to use the new entity names:
- ❌ `vaultMetric` → ✅ `mavcvaultMetric` or `mavpvaultMetric`

The frontend has already been updated in this commit to handle these changes.

## Files Modified

### Subgraph
- `schema.graphql` - Added `MAVCVaultMetric` and `MAVPVaultMetric`
- `subgraph.yaml` - Updated entity references
- `src/mapping.ts` - Separated handlers and metrics

### Frontend
- `src/hooks/useSubgraphData.ts` - Query `mavcvaultMetric` with client-side filtering
- `src/hooks/useSubgraphDataMAVP.ts` - NEW: Query `mavpvaultMetric` with client-side filtering
- `src/hooks/useMAVPSubgraphData.ts` - Updated to query `mavpvaultMetric` with client-side filtering
- `src/components/wallet/SubgraphAnalytics.tsx` - Use `mavcvaultMetric`
- `src/components/wallet/SubgraphAnalyticsMAVP.tsx` - Use `mavpvaultMetric` and new hook
- `src/components/wallet/MAVPStrategyCard.tsx` - Fixed to use `mavpvaultMetric` field
- `src/app/customer/grow/hedge-fund-v2/mavp/page.tsx` - Use `SubgraphAnalyticsMAVP`

## Testing

After deployment:

1. Navigate to `http://localhost:3000/customer/grow/hedge-fund-v2/mavc`
   - Should show MAVC-specific data only

2. Navigate to `http://localhost:3000/customer/grow/hedge-fund-v2/mavp`
   - Should show MAVP-specific data only

3. Verify that deposits/withdrawals are not duplicated between vaults

