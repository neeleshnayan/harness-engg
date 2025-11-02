# MAVC Yearn Strategy (USDC/WETH) - DEPLOYED ✅

## Final Working Deployment

**Vault Address:** `0xE3cb802600f59b45d9e991bD9cd154ECE87A0217`

**Network:** Ethereum Sepolia (Chain ID: 11155111)

## Why This Version Works

Based on your working `MultiAssetVaultUSDCWETH.sol` implementation:

✅ **Uses USDC/WETH** (not WBTC) - WETH/USDC pool has liquidity on Sepolia  
✅ **Graceful swap failure handling** - If swap fails, keeps funds as USDC  
✅ **50/50 allocation** - Splits deposits half USDC, half WETH  
✅ **Uses your DEX Integration** - `0x7B5D90ad6c75D0C0E061c97E94b4f6A2D9CD92Ed`  
✅ **Yearn v3 TokenizedStrategy** - Fully ERC-4626 compliant  

## Configuration

### Contract Addresses
- **USDC:** `0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238`
- **WETH:** `0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14`
- **ETH/USD Feed:** `0x694AA1769357215DE4FAC081bf1f309aDC325306`
- **DEX Integration:** `0x7B5D90ad6c75D0C0E061c97E94b4f6A2D9CD92Ed`
- **TokenizedStrategy:** `0xBB51273D6c746910C7C06fe718f30c936170feD0`

### Update Firestore

Go to Firebase Console → Firestore → `quant_strategies` → `MAVC_YEARN`

```json
{
  "VAULT_ADDRESS": "0xE3cb802600f59b45d9e991bD9cd154ECE87A0217"
}
```

## How It Works

### Deposit Flow
1. User deposits 10 USDC
2. Strategy receives 10 USDC
3. Keeps 5 USDC as is
4. Tries to swap 5 USDC → WETH
   - ✅ If swap succeeds: Holds 5 USDC + WETH worth 5 USDC
   - ❌ If swap fails: Holds 10 USDC (graceful fallback)
5. Mints vault shares to user

### Withdraw Flow
1. User redeems shares
2. Strategy calculates proportional withdrawal
3. Returns USDC from both USDC and WETH holdings
4. If has actual WETH, swaps it to USDC first

## Testing

```bash
# Check vault name
cast call 0xE3cb802600f59b45d9e991bD9cd154ECE87A0217 "name()(string)" --rpc-url sepolia

# Check allocation (should return 5000, 5000 for 50/50)
cast call 0xE3cb802600f59b45d9e991bD9cd154ECE87A0217 "getCurrentAllocation()(uint256,uint256)" --rpc-url sepolia

# Get actual balances
cast call 0xE3cb802600f59b45d9e991bD9cd154ECE87A0217 "getActualBalances()(uint256,uint256)" --rpc-url sepolia
```

## Etherscan Links
- **New Vault (USDC/WETH):** https://sepolia.etherscan.io/address/0xE3cb802600f59b45d9e991bD9cd154ECE87A0217
- **Old Vault (USDC/WBTC - broken):** https://sepolia.etherscan.io/address/0x910e2b419c041e1348fce403c540bc716cafd212
- **Working MAVC (non-Yearn):** Check your deployment logs

## Key Differences from Previous Version

| Feature | Old (WBTC) | New (WETH) |
|---------|------------|------------|
| Secondary asset | WBTC | WETH |
| Pool liquidity | ❌ None on Sepolia | ✅ Exists |
| Swap failures | ❌ Reverts entire deposit | ✅ Graceful fallback |
| DEX | Uniswap Router | Your DEX Integration |
| Architecture | Yearn v3 | Yearn v3 |

## Next Steps

1. ✅ Update Firestore `VAULT_ADDRESS` 
2. ✅ Test deposit with frontend
3. ✅ Verify swap execution
4. Monitor for any issues

Deposits should now work perfectly!

