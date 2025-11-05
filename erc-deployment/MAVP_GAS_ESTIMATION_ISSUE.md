# MAVP Gas Estimation Error - Root Cause Analysis

## Problem
Circle API returns `ESTIMATION_ERROR` when trying to deposit USDC into MAVP vault.

## Root Cause

The issue is caused by **nested external calls** that Circle's gas estimation cannot properly simulate:

1. **MAVP.sol line 117**: `this._swapUsdcIntoAsset()` - External call to self
2. **UniswapV4Integration.sol line 495**: `this.checkExistingPools()` - Another external call to self
3. **Loop over 5 assets**: Each deposit attempts 5 swaps, each with nested external calls

### Why This Fails

Circle's gas estimation tries to simulate the entire transaction including:
- 5 external calls `this._swapUsdcIntoAsset()`
- Each swap calls `swapDirectCustomPool` which internally calls `this.checkExistingPools()`
- Complex pool creation and liquidity addition logic

During gas estimation, Circle cannot properly simulate these nested external call patterns, causing `ESTIMATION_ERROR`.

## Solution

### Option 1: Modify UniswapV4Integration (Recommended)
Make `checkExistingPools` an internal function instead of external:

```solidity
// Change from:
(address poolLow, address poolMedium, address poolHigh) = this.checkExistingPools(tokenIn, tokenOut);

// To:
(address poolLow, address poolMedium, address poolHigh) = _checkExistingPools(tokenIn, tokenOut);

// And make the function internal:
function _checkExistingPools(
    address token0,
    address token1
) internal view returns (
    address poolLow,
    address poolMedium,
    address poolHigh
) {
    // ... existing implementation
}
```

### Option 2: Modify MAVP to Skip Swaps During Gas Estimation
This is not possible - gas estimation happens at the RPC level, not in the contract.

### Option 3: Simplify Swap Logic
Remove the external call to `checkExistingPools` and inline the logic, or make it view-only.

### Option 4: Batch Swaps
Instead of looping through 5 swaps, batch them into a single call. This reduces the number of external calls.

## Current Workaround

The current code already handles swap failures gracefully via try-catch, keeping failed swaps as USDC. However, Circle's gas estimation fails before the try-catch can execute.

## Recommendation

**Deploy a new version of UniswapV4Integration** with `checkExistingPools` as an internal function. This will eliminate one layer of external calls and should fix the gas estimation issue.

## Testing

After fixing, test with:
1. Single asset deposit (should work)
2. Full deposit with all 5 assets (should work)
3. Deposit when pools don't exist (should handle gracefully)

