# Transaction Status Indicators - Implementation Guide

## Overview

This implementation adds MetaMask-style transaction status indicators to KryptonPay's MAVC withdraw/deposit functionality. Users now see real-time likelihood estimates and detailed risk analysis before and during transaction processing.

---

## Features Implemented

### 1. **Transaction Likelihood Estimation** (Frontend)
**File:** `src/services/transactionLikelihood.ts`

Provides real-time validation and risk assessment:
- **5 Likelihood Levels:**
  - 🟢 Very Likely (90-100% success rate)
  - 🟢 Likely (70-90%)
  - 🟡 Uncertain (40-70%)
  - 🟠 Unlikely (10-40%)
  - 🔴 Very Unlikely (0-10%)

- **Risk Factors Analyzed:**
  - Insufficient balance check
  - Balance margin calculation
  - Network congestion level
  - Gas availability
  - Contract reachability
  - Wallet connection status

### 2. **Visual Status Indicator Component**
**File:** `src/components/wallet/TransactionStatusIndicator.tsx`

Beautiful, animated component showing:
- **Progress bar** with color-coded stages
- **Real-time status messages** (validating → broadcasting → confirming → confirmed)
- **Likelihood badge** with confidence score
- **Warning messages** for detected issues
- **Transaction hash** link (once available)
- **Collapsible risk factors** details

### 3. **Enhanced MAVC Modal**
**File:** `src/components/wallet/MAVCModal.tsx`

Updated to include:
- Automatic likelihood estimation when amount changes
- Live transaction status during processing
- Stage progression (validating → broadcasting → confirming → confirmed)
- Visual feedback for success/failure states

### 4. **Backend Validation API**
**File:** `KryptonPay_Backend/app/api/v1/transaction_validation.py`

Three new endpoints:

#### `POST /validate-transaction`
Comprehensive transaction validation:
```json
{
  "wallet_address": "0x...",
  "token_address": "0x...",
  "amount": "100.50",
  "transaction_type": "withdraw",
  "vault_address": "0x..."
}
```

Response:
```json
{
  "likelihood": "very_likely",
  "confidence": 95,
  "estimated_success_rate": 95,
  "warnings": [],
  "risk_factors": {
    "insufficient_balance": false,
    "balance_margin": 45.2,
    "network_congestion": "low",
    "estimated_gas_cost": "0.0024",
    "has_enough_for_gas": true,
    "contract_reachable": true,
    "wallet_connected": true,
    "current_gas_price": "12.5"
  },
  "estimated_gas_fee_usd": 4.80,
  "estimated_time_minutes": 1
}
```

#### `GET /network-status`
Current blockchain network status:
```json
{
  "status": "connected",
  "gas_price_gwei": 12.5,
  "network_congestion": "low",
  "latest_block": 12345678,
  "estimated_block_time": 12
}
```

#### `POST /estimate-gas`
Detailed gas estimates for slow/standard/fast options:
```json
{
  "estimated_gas_units": 180000,
  "current_gas_price_gwei": 12.5,
  "estimates": {
    "slow": {
      "gas_price_gwei": 12.5,
      "cost_eth": 0.00225,
      "estimated_time_minutes": 5
    },
    "standard": {
      "gas_price_gwei": 15.0,
      "cost_eth": 0.0027,
      "estimated_time_minutes": 2
    },
    "fast": {
      "gas_price_gwei": 18.75,
      "cost_eth": 0.003375,
      "estimated_time_minutes": 1
    }
  }
}
```

---

## Integration Steps

### Step 1: Register Backend Routes

Add to your FastAPI application (e.g., `main.py` or `app.py`):

```python
from app.api.v1 import transaction_validation

# Add to your router includes
app.include_router(
    transaction_validation.router,
    prefix="/api/v1/transaction",
    tags=["transaction-validation"]
)
```

### Step 2: Update MAVCStrategyCard Component

Pass wallet and token addresses to the modal:

**File:** `src/components/wallet/MAVCStrategyCard.tsx`

```tsx
// Around line 420+
<MAVCModal
  visible={modalVisible}
  onClose={() => setModalVisible(false)}
  action={modalAction}
  mavcBalance={mavcBalance}
  usdcBalance={usdcBalance}
  onDeposit={handleDeposit}
  onWithdraw={handleWithdraw}
  loading={transactionLoading}
  error={transactionError}
  success={transactionSuccess}
  mavcPrice={mavcPriceData?.price}
  walletAddress={address}  // ADD THIS
  tokenAddress={strategyData?.token_address}  // ADD THIS
/>
```

### Step 3: Install Required Dependencies (if not already installed)

```bash
npm install framer-motion
```

The component uses `framer-motion` for smooth animations.

---

## User Experience Flow

### Before Transaction (Pre-validation)

1. User opens withdraw/deposit modal
2. User enters amount
3. **Instant feedback appears:**
   - Green badge: "Very likely to succeed (95%)"
   - Risk factors automatically checked
   - Warnings shown if issues detected

### During Transaction

1. User clicks "Withdraw MAVC" or "Deposit MAVC"
2. **Status indicator shows:**
   - Progress bar: 25% → Broadcasting to network...
   - Spinning icon
   - Likelihood: "Likely to succeed"

3. **Status updates:**
   - Progress bar: 75% → Waiting for blockchain confirmation...
   - Transaction hash link appears

4. **Completion:**
   - Progress bar: 100% → Transaction confirmed!
   - Success checkmark animation
   - Green color scheme

### Error Handling

If transaction fails:
- Red progress bar
- Error icon (✗)
- Error message displayed
- Likelihood updated to "Very unlikely"

---

## Configuration

### Frontend Configuration

The frontend service is fully client-side and requires no additional configuration. It works offline with basic validations.

For enhanced accuracy, you can integrate the backend API:

**File:** `src/services/transactionLikelihood.ts`

Add at the top:
```typescript
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Update estimateTransactionLikelihood to call backend
export async function estimateTransactionLikelihood(params) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/transaction/validate-transaction`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        wallet_address: params.walletAddress,
        token_address: params.tokenAddress,
        amount: params.amount,
        transaction_type: params.type,
      }),
    });

    if (response.ok) {
      return await response.json();
    }
  } catch (error) {
    console.warn('Backend validation unavailable, using client-side estimation');
  }

  // Fallback to client-side logic
  // ... existing code ...
}
```

### Backend Configuration

Required environment variables:

```bash
# .env file
ETHEREUM_RPC_URL=https://sepolia.infura.io/v3/YOUR_PROJECT_ID
# or
ETHEREUM_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/YOUR_API_KEY
```

---

## Visual Examples

### Likelihood Indicators

```
🟢 Very likely to succeed (95%)
   Balance margin: 45.2%
   Network congestion: Low
   Gas available: Yes
   Contract status: Reachable
```

```
🟡 Uncertain (65%)
   ⚠ Balance is very close to required amount
   ⚠ Moderate network congestion
```

```
🔴 Very unlikely to succeed (15%)
   ⚠ Insufficient balance for transaction
   ⚠ May not have enough ETH for gas fees
   ⚠ High network congestion may delay transaction
```

### Transaction Stages

```
[=====>                    ] 25%
⟳ Broadcasting to network...
🟢 Likely to succeed (85%)
```

```
[================>         ] 75%
⟳ Waiting for blockchain confirmation...
🟢 Likely to succeed (80%)

Transaction: 0x1234abcd...5678ef90
View on Etherscan ↗
```

```
[=========================] 100%
✓ Transaction confirmed!
🟢 Very likely to succeed (100%)
```

---

## Customization

### Changing Likelihood Thresholds

**File:** `src/services/transactionLikelihood.ts`

```typescript
function calculateLikelihood(score: number): TransactionLikelihood {
  if (score >= 90) return 'very_likely';    // Change threshold
  if (score >= 70) return 'likely';
  if (score >= 40) return 'uncertain';
  if (score >= 10) return 'unlikely';
  return 'very_unlikely';
}
```

### Adjusting Risk Scoring

**File:** `src/services/transactionLikelihood.ts`

```typescript
// Insufficient balance
if (insufficientBalance) {
  score -= 80;  // Adjust penalty
}

// Low balance margin
else if (balanceMargin < 5) {
  score -= 15;  // Adjust penalty
}
```

### Styling

The component uses inline styles with CSS-in-JS. Colors can be customized:

**File:** `src/components/wallet/TransactionStatusIndicator.tsx`

```typescript
const displays = {
  very_likely: {
    label: 'Very likely to succeed',
    color: '#10B981',  // Change color
    icon: '✓',
  },
  // ... other levels
};
```

---

## Testing

### Test Scenarios

1. **Sufficient Balance:**
   - Enter amount less than current balance
   - Should show green "Very likely" indicator

2. **Insufficient Balance:**
   - Enter amount greater than balance
   - Should show red "Very unlikely" with warning

3. **Low Balance Margin:**
   - Enter amount very close to total balance (within 1-5%)
   - Should show yellow "Uncertain" with warning

4. **Network Congestion:**
   - Backend checks gas prices
   - High gas → warnings about delays/costs

5. **Transaction Processing:**
   - Submit transaction
   - Status should progress: validating → broadcasting → confirming → confirmed

### Manual Testing Commands

Test backend endpoints:

```bash
# Test network status
curl http://localhost:8000/api/v1/transaction/network-status

# Test validation
curl -X POST http://localhost:8000/api/v1/transaction/validate-transaction \
  -H "Content-Type: application/json" \
  -d '{
    "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
    "token_address": "0x...",
    "amount": "100",
    "transaction_type": "withdraw"
  }'

# Test gas estimation
curl -X POST http://localhost:8000/api/v1/transaction/estimate-gas \
  -H "Content-Type: application/json" \
  -d '{
    "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
    "token_address": "0x...",
    "amount": "100",
    "transaction_type": "withdraw"
  }'
```

---

## Troubleshooting

### Issue: Likelihood not updating

**Solution:** Check that `walletAddress` and `tokenAddress` props are passed to `MAVCModal`

### Issue: Backend validation fails

**Solution:**
1. Check `ETHEREUM_RPC_URL` is set correctly
2. Verify RPC provider is accessible
3. Check Infura/Alchemy API credits

### Issue: Always shows "Unable to connect"

**Solution:**
1. Backend: Verify Web3 initialization in `transaction_validation.py`
2. Frontend: Check API endpoint URL configuration

### Issue: Animations not working

**Solution:** Ensure `framer-motion` is installed:
```bash
npm install framer-motion
```

---

## Future Enhancements

Potential improvements:

1. **Real-time Gas Price Updates:** WebSocket connection for live gas price feeds
2. **Historical Success Rates:** Track actual transaction outcomes to improve predictions
3. **Slippage Warnings:** For swap operations (when implemented)
4. **Multi-step Transaction Preview:** Show all required approvals and calls
5. **Gas Price Customization:** Let users choose slow/standard/fast
6. **Transaction Simulation:** Use Tenderly or similar to simulate before execution
7. **MEV Protection Indicators:** Warn about front-running risks
8. **Cross-chain Compatibility:** Support multiple networks with different risk factors

---

## API Reference

### Frontend Service Functions

```typescript
// Estimate transaction likelihood
estimateTransactionLikelihood(params: {
  walletAddress: string;
  tokenAddress: string;
  amount: string;
  type: 'deposit' | 'withdraw';
  currentBalance: string;
  mavcPrice?: string;
}): Promise<TransactionLikelihoodResult>

// Get likelihood display properties
getLikelihoodDisplay(
  likelihood: TransactionLikelihood
): { label: string; color: string; icon: string; emoji: string; }

// Get transaction stage message
getTransactionStageMessage(
  stage: 'validating' | 'signing' | 'broadcasting' | 'confirming' | 'confirmed' | 'failed'
): string
```

### Backend API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/transaction/validate-transaction` | POST | Validate transaction and get likelihood |
| `/api/v1/transaction/network-status` | GET | Get current network status |
| `/api/v1/transaction/estimate-gas` | POST | Estimate gas costs |

---

## Support

For issues or questions:
1. Check the console for error messages
2. Verify all environment variables are set
3. Test backend endpoints individually
4. Check browser network tab for API call failures

---

## Conclusion

This implementation provides users with confidence-inspiring feedback similar to MetaMask, reducing failed transactions and improving overall UX. The modular design allows easy integration into other transaction flows beyond MAVC withdrawals.

**Key Benefits:**
- ✅ Reduces failed transactions
- ✅ Builds user confidence
- ✅ Transparent risk communication
- ✅ Professional, polished UX
- ✅ Extensible to other features

Happy coding! 🚀
