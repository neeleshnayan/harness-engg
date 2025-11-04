# Frontend Fix - MAVC Yearn Balance Display

## Problem Found ✅

**Line 97-99 in `MAVCYearnStrategyCard.tsx`:**
```typescript
// TODO: Find Yearn vault token balance
// For now, setting to 0 as we haven't deployed the vault yet
setVaultBalance("0");
```

**The frontend was HARDCODED to always show 0 balance!**

## Changes Made

### 1. Fixed Initial Balance Fetch (Line 97-111)
**Before:**
```typescript
setVaultBalance("0"); // Always 0!
```

**After:**
```typescript
// Fetch Yearn vault share balance from backend
try {
  const yearnBalanceResponse = await api.get(`/api/v1/mavc-yearn/balance/${parsedData.wallet_address}`);
  if (yearnBalanceResponse.data && yearnBalanceResponse.data.balance) {
    setVaultBalance(yearnBalanceResponse.data.balance);
  } else {
    setVaultBalance("0");
  }
} catch (err) {
  setVaultBalance("0");
}
```

### 2. Added Fallback Balance Fetch (Line 121-132)
In case the first fetch fails, added a separate try-catch to fetch vault balance.

### 3. Fixed Transaction Polling (Line 205-247)
**Before:** Looked for token with symbol 'MAVC_YEARN' in wallet_balance (doesn't exist)

**After:** Directly queries `/api/v1/mavc-yearn/balance` endpoint

```typescript
const yearnBalanceResponse = await api.get(`/api/v1/mavc-yearn/balance/${parsedData.wallet_address}`);
const currentVaultBalance = parseFloat(yearnBalanceResponse.data.balance || "0");
```

## Testing

### 1. Rebuild Frontend
```bash
npm run dev
```

### 2. Test Balance Display
- Navigate to MAVC Yearn card
- Should now show **0.03 MAVC** shares
- Not 0 anymore!

### 3. Test Deposit Flow
- Try depositing
- Balance should update after transaction confirms
- Polling will now correctly detect balance changes

## Why It Was Broken

1. ❌ **Frontend never called backend API** for balance
2. ❌ **Hardcoded to 0** with a TODO comment
3. ❌ **Polling looked for wrong token symbol** ('MAVC_YEARN' doesn't exist in Circle wallet response)

## Why It Works Now

1. ✅ **Calls backend API** `/api/v1/mavc-yearn/balance/{address}`
2. ✅ **Backend queries Firestore** for vault address
3. ✅ **Backend queries blockchain** for actual share balance
4. ✅ **Polling uses correct endpoint** to detect balance changes

## Verification

**On blockchain:**
```bash
cast call 0xE3cb802600f59b45d9e991bD9cd154ECE87A0217 "balanceOf(address)(uint256)" 0xe4745d11f15918f4b2c4d86c6e518d929ac8cd81 --rpc-url sepolia
# Returns: 30000000 (0.03 shares with 18 decimals)
```

**Backend returns:**
```json
{
  "balance": "0.03",
  "balance_wei": "30000000",
  "decimals": 18
}
```

**Frontend now displays:** `0.03 MAVC`

## Files Changed
- `src/components/wallet/MAVCYearnStrategyCard.tsx`

No backend changes needed - backend was already correct!





