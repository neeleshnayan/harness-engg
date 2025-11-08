# Contract Address Alignment Verification

## Issue
Price updates are not appearing in the subgraph. This document helps verify that backend and subgraph are listening to the same contract addresses.

## Expected Addresses

### MAVC (MultiAssetVaultUSDCWETH)
- **Subgraph expects**: `0xeBbca96f25F6198C37b7d439e8724a50f9b266DD`
- **Backend reads from**: Firestore `quant_strategies/MAVC/VAULT_ADDRESS`
- **Location**: `erc-deployment/subgraph/subgraph.yaml` line 9

### MAVP (MultiAssetVaultPortfolio)
- **Subgraph expects**: `0x5Eed3b9354b6Dd40b9839E5d8159ECDBaFD5D527`
- **Backend reads from**: Firestore `quant_strategies/MAVP/vault_address`
- **Location**: `erc-deployment/subgraph/subgraph.yaml` line 39

## Verification Steps

1. **Check Firestore Configuration**
   - Go to Firebase Console → Firestore → `quant_strategies`
   - Verify `MAVC` document has `VAULT_ADDRESS` matching subgraph address
   - Verify `MAVP` document has `vault_address` matching subgraph address

2. **Check Backend Logs**
   - Backend now logs the vault address it reads from Firestore
   - Look for: `"MAVC vault address from Firestore: <address>"`
   - Look for: `"MAVP vault address from Firestore: <address>"`

3. **If Addresses Don't Match**
   - Option A: Update Firestore to match subgraph addresses (if subgraph is correct)
   - Option B: Update subgraph.yaml and redeploy subgraph (if Firestore is correct)

## Contract Changes Made

Both contracts now enforce the 30-minute interval check:
- `MultiAssetVaultUSDCWETH.sol`: Added require statement in `_updateStrategyPrice()`
- `MAVP.sol`: Added require statement in `_updateStrategyPrice()`

The require statement allows the first update (when `lastPriceUpdate == 0`) and then enforces the 30-minute cooldown.

## Testing

After deploying updated contracts:
1. Verify backend can call `updateStrategyPrice()` successfully
2. Check that `StrategyPriceUpdated` events are emitted on-chain
3. Verify subgraph indexes the events
4. Confirm price data appears in frontend queries

