# Fix MAVC Yearn Balance Display - URGENT

## Problem
✅ Deposits working  
✅ Shares minted  
✅ Token portfolio shows correctly  
❌ MAVC Yearn card shows 0 balance  

## Root Cause
**Firestore has old/wrong vault address**

The backend is correctly reading from Firestore, but Firestore has the wrong address.

## Solution - Update Firestore NOW

### Step 1: Go to Firebase Console
https://console.firebase.google.com/

### Step 2: Navigate to Firestore
1. Select your project
2. Click "Firestore Database" in left sidebar
3. Find collection: `quant_strategies`
4. Find document: `MAVC_YEARN`

### Step 3: Update VAULT_ADDRESS Field

**Change from (one of these old addresses):**
- `0x910e2b419c041e1348fce403c540bc716cafd212` ❌ (original broken)
- `0xe4993f3a226076C5cA73F583c5E1d8619A4FC423` ❌ (WBTC version)
- `0xF96ed58d8BCE872eA56c374358658a5F7c372488` ❌ (WBTC with try-catch)

**Change to (new working USDC/WETH):**
```
0xE3cb802600f59b45d9e991bD9cd154ECE87A0217
```

### Step 4: Verify the Change

**Test the balance endpoint:**
```bash
# Replace with your wallet address
curl "http://localhost:8000/api/v1/mavc-yearn/balance/0xe4745d11f15918f4b2c4d86c6e518d929ac8cd81"
```

**Should return:**
```json
{
  "status": "success",
  "balance": "9.xxx",
  "balance_wei": "9xxxxx...",
  "decimals": 18
}
```

### Step 5: Refresh Frontend
Hard refresh the MAVC Yearn card:
- Windows: `Ctrl + Shift + R`
- Mac: `Cmd + Shift + R`

## Verify on Blockchain

**Check your shares directly:**
```bash
# Your wallet
WALLET=0xe4745d11f15918f4b2c4d86c6e518d929ac8cd81

# New vault
VAULT=0xE3cb802600f59b45d9e991bD9cd154ECE87A0217

# Check balance
cast call $VAULT "balanceOf(address)(uint256)" $WALLET --rpc-url sepolia
```

## Why This Happened
1. Deployed 3 different versions of the vault
2. Last one (USDC/WETH) is the working version
3. Firestore wasn't updated to latest address
4. Backend correctly reads from Firestore
5. Firestore has old address → Backend returns 0

## The Correct Vault Details

**Address:** `0xE3cb802600f59b45d9e991bD9cd154ECE87A0217`  
**Name:** MAVC Yearn Strategy USDC/WETH  
**Allocation:** 50% USDC / 50% WETH  
**Network:** Ethereum Sepolia  
**Etherscan:** https://sepolia.etherscan.io/address/0xE3cb802600f59b45d9e991bD9cd154ECE87A0217

## Complete Firestore Document

Your `MAVC_YEARN` document should look like:
```json
{
  "VAULT_ADDRESS": "0xE3cb802600f59b45d9e991bD9cd154ECE87A0217",
  "name": "MAVC Yearn",
  "description": "Yearn v3 tokenized strategy with 50/50 USDC/WETH allocation",
  "net_apy": 45.2,
  "aum": 2.1,
  "sharpe_ratio": 1.12,
  "max_drawdown": 18.50,
  "lock_in_period": "None",
  "participants": 0,
  "performance_fee": 20.0,
  "risk_grade": "B"
}
```

## After Update
✅ Balance will show correctly  
✅ Card will display your shares  
✅ Status will update properly  
✅ Deposits/withdrawals will work  

**Just update that ONE field in Firestore and everything will work!**


