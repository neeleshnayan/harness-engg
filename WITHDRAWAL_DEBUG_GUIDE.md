# MAVC Withdrawal Debug Guide

## Debug Logging Added

I've added comprehensive debug logging to both the **backend** and **frontend** to help diagnose withdrawal issues.

## What You'll See in the Logs

### Backend Logs (Python/FastAPI)

When you run the backend with `uvicorn app.main:app --reload`, you'll see detailed logs like:

```
================================================================================
🔄 MAVC WITHDRAWAL REQUEST STARTED
================================================================================
📋 Request Details:
   - User ID: <user_id>
   - Amount (human): 10 MAVC
   - Destination Wallet: 0x123...abc
   - Vault Contract: 0x1456Dafd60faDbDa71f58C1F8530CEEe1E7b37D7
✅ User verified: <user_id>
✅ Circle Wallet ID: <wallet_id>
📍 Circle Wallet Blockchain Address: 0x456...def
🔍 Processing withdrawal from MAVC vault...
💰 Amount Conversion:
   - Human readable: 10.0 MAVC
   - Wei (6 decimals): 10000000
📤 Preparing redeem transaction:
   - Function: redeem(uint256,address,address)
   - Param 1 (shares): 10000000
   - Param 2 (receiver): 0x123...abc
   - Param 3 (owner): 0x123...abc
   - Contract: 0x1456Dafd60faDbDa71f58C1F8530CEEe1E7b37D7
   - Executing wallet: <wallet_id> (0x456...def)
🚀 Sending transaction to Circle API...
🌐 Circle API Contract Execution Request:
   - URL: https://api.circle.com/v1/w3s/developer/transactions/contractExecution
   - Wallet ID: <wallet_id>
   - Contract: 0x1456Dafd60faDbDa71f58C1F8530CEEe1E7b37D7
   - Function: redeem(uint256,address,address)
   - Parameters: ['10000000', '0x123...abc', '0x123...abc']
   - Fee Level: MEDIUM
📡 Circle API Response Status: 201
✅ Circle API call successful!
   - Response: {...full Circle response...}
📨 Circle API Response:
   - Full response: {...}
✅ Withdrawal transaction created successfully!
   - Transaction ID: <tx_id>
   - State: INITIATED / PENDING_RISK_SCREENING / CONFIRMED / etc.
   - TX Hash: 0x789...xyz (or Pending...)
================================================================================
```

### Frontend Logs (Browser Console)

Open browser DevTools console (F12) and you'll see:

```
================================================================================
🚀 MAVC WITHDRAWAL STARTED
================================================================================
📋 Withdrawal amount requested: 10
✅ User data loaded: {user_id: "...", wallet_address: "0x123...abc"}
📤 Sending MAVC Withdraw Request to Backend:
   - Amount: 10 MAVC
   - Destination Wallet: 0x123...abc
   - User ID: <user_id>
   - API Endpoint: /api/v1/mavc/withdraw
💰 Initial Balances (before withdrawal):
   - MAVC Balance: 100
   - USDC Balance: 50
🌐 Making API call...
📨 Backend Response Received:
   - Status Code: 200
   - Response Data: {
       "status": "success",
       "message": "Withdrew 10 MAVC shares",
       "redeem_tx": "...",
       "tx_state": "INITIATED",
       "tx_hash": null,
       "amount": "10"
     }
✅ Withdrawal transaction created successfully!
   - Transaction ID: <tx_id>
   - Transaction State: INITIATED
   - TX Hash: Pending...
⏳ Starting balance polling (max 2 minutes)...
🔍 Balance Check Attempt 1/60...
   - Fetched wallet data for: 0x123...abc
   - Current MAVC: 100 (initial: 100) [NO CHANGE]
   - Current USDC: 50 (initial: 50) [NO CHANGE]
🔍 Balance Check Attempt 2/60...
   - Fetched wallet data for: 0x123...abc
   - Current MAVC: 90 (initial: 100) [DECREASED ✓]
   - Current USDC: 50 (initial: 50) [NO CHANGE]
✅ BALANCE CHANGED DETECTED!
   - MAVC: 100 -> 90
   - USDC: 50 -> 50
================================================================================
✅ WITHDRAWAL COMPLETED SUCCESSFULLY!
================================================================================
```

## Key Information to Look For

### 1. **Address Verification**
- **Circle Wallet Address**: The wallet executing the transaction (from Circle's custodial wallet)
- **Destination Wallet**: Where the withdrawn assets should be sent (user's wallet)
- **Vault Contract**: The MAVC contract address

### 2. **Transaction Parameters**
- **Amount in Wei**: Should be human amount × 1,000,000 (MAVC has 6 decimals)
- **Function**: `redeem(uint256,address,address)`
- **Parameters**: `[shares, receiver, owner]`

### 3. **Circle API Response**
- **Transaction ID**: Unique identifier for tracking
- **State**: Current transaction state (INITIATED, PENDING_RISK_SCREENING, CONFIRMED, COMPLETED, FAILED)
- **TX Hash**: Blockchain transaction hash (once broadcast)

### 4. **Common Issues to Diagnose**

#### Issue 1: Transaction Stuck at "INITIATED" or "PENDING_RISK_SCREENING"
**What to check:**
- Circle API response state
- Circle dashboard for pending approvals
- Risk screening policies

#### Issue 2: Transaction "FAILED" in Circle
**What to check:**
- Error message in Circle response
- Insufficient gas
- Smart contract revert (check error message)
- Wallet balance (does Circle wallet have enough MAVC?)

#### Issue 3: Balance Not Updating
**What to check:**
- Transaction state (is it COMPLETED?)
- TX Hash (check on Etherscan/block explorer)
- Balance polling logs (is the API returning correct data?)
- Token addresses match (MAVC token address vs what's being queried)

#### Issue 4: Wrong Address
**What to check:**
- Destination Wallet in logs matches user's expected wallet
- Circle Wallet Blockchain Address is the one holding MAVC tokens
- Contract address is correct MAVC vault

## How to Test

1. **Start Backend with logs visible:**
   ```bash
   cd KryptonPay_Backend
   uvicorn app.main:app --reload
   ```

2. **Open Frontend with DevTools:**
   - Open browser
   - Press F12 to open DevTools
   - Go to Console tab
   - Attempt a withdrawal

3. **Compare logs:**
   - Check backend terminal for detailed Circle API calls
   - Check browser console for frontend polling behavior
   - Look for any ❌ error messages

## Troubleshooting Steps

1. **If withdrawal request fails immediately:**
   - Check backend logs for the exact error from Circle API
   - Verify Circle API credentials are valid
   - Ensure wallet has sufficient MAVC balance

2. **If withdrawal gets stuck:**
   - Note the Transaction ID from logs
   - Check Circle dashboard: https://console.circle.com/
   - Check transaction state in Circle
   - Check blockchain explorer if TX Hash is available

3. **If balance never updates:**
   - Verify transaction completed on Circle dashboard
   - Check if TX Hash shows on block explorer
   - Manually refresh wallet balance endpoint
   - Check if USDC balance increased (withdrawal returns USDC/WETH)

## Additional Monitoring

You can also monitor the transaction status via the backend API:

```bash
GET /api/v1/mavc/transaction/{transaction_id}/status
```

This will return the current Circle transaction state.
