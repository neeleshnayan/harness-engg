# MAVC Integration with Circle Developer-Controlled Wallets

## Overview

This project uses **Circle Developer-Controlled Wallets** for MAVC (Multi-Asset Vault) deposits and withdrawals. The backend executes smart contract transactions on behalf of users via Circle's API.

## Architecture

```
User → Frontend → Backend API → Circle SDK → Smart Contract → Blockchain
```

### Why Circle Instead of MetaMask?

- ✅ **Seamless UX**: No wallet extension required
- ✅ **Backend Control**: Transactions executed server-side
- ✅ **Custodial**: Users don't need to manage private keys
- ✅ **Gas Management**: Backend pays gas fees
- ✅ **Consistent with existing infrastructure**: You already use Circle wallets

## Backend Implementation

### File: `KryptonPay_Backend/app/api/v1/mavc.py`

#### Endpoints

1. **POST `/api/v1/mavc/deposit`**
   - Deposits USDC to MAVC vault
   - Executes 2 transactions:
     1. `USDC.approve(vault, amount)`
     2. `vault.deposit(amount, user)`
   
   ```json
   Request:
   {
     "user_id": "string",
     "amount": 10.5
   }
   
   Response:
   {
     "status": "success",
     "message": "Deposited 10.5 USDC to MAVC vault",
     "approve_tx": "tx_id_1",
     "deposit_tx": "tx_id_2",
     "amount": 10.5
   }
   ```

2. **POST `/api/v1/mavc/withdraw`**
   - Withdraws (redeems) MAVC shares for USDC
   - Executes 1 transaction:
     1. `vault.redeem(shares, user, user)`
   
   ```json
   Request:
   {
     "user_id": "string",
     "amount": 5.0
   }
   
   Response:
   {
     "status": "success",
     "message": "Withdrew 5.0 MAVC shares",
     "redeem_tx": "tx_id",
     "amount": 5.0
   }
   ```

3. **GET `/api/v1/mavc/balance/{wallet_address}`**
   - Read-only endpoint to check MAVC balance
   - Returns balance in MAVC tokens (18 decimals)

### Key Functions

#### `execute_contract_call(wallet_id, contract_address, abi_function_signature, abi_parameters)`
- Executes smart contract interactions via Circle API
- Uses `CreateContractExecutionTransactionForDeveloperRequest`
- Returns transaction ID for tracking

#### `get_user_wallet_id(user_id)` & `get_user_wallet_address(user_id)`
- Fetches Circle wallet info from Firebase
- Maps user_id to wallet_id and wallet_address

## Environment Variables

### Backend (`.env` in `KryptonPay_Backend/`)

```bash
# Circle API
CIRCLE_API_KEY=your_circle_api_key
ENTITY_SECRET_CIPHERTEXT=your_entity_secret

# MAVC Contract
MAVC_VAULT_ADDRESS=0xYourVaultContractAddress
USDC_TOKEN_ADDRESS=0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238  # Sepolia USDC

# Ethereum RPC (for read operations in mavc_vault.py service)
ETHEREUM_RPC_URL=https://sepolia.infura.io/v3/YOUR_KEY
```

### Frontend (`.env.local`)

```bash
# Subgraph for analytics
NEXT_PUBLIC_SUBGRAPH_URL=https://api.studio.thegraph.com/query/121450/mavc/version/latest
```

## Frontend Implementation

### File: `src/components/wallet/MAVCCard.tsx`

- Removed MetaMask integration
- Calls backend API endpoints
- Passes `user_id` from localStorage
- Shows loading states and transaction results

### User Flow

1. User clicks "Deposit" button
2. Enters USDC amount in modal
3. Frontend calls `/api/v1/mavc/deposit` with `user_id` and `amount`
4. Backend:
   - Looks up user's Circle wallet
   - Executes USDC approval transaction
   - Executes vault deposit transaction
5. Returns success with transaction IDs
6. Frontend shows success message
7. Subgraph indexes the transactions (if configured)

## Smart Contract Details

**Vault**: `MultiAssetVaultUSDCWETH` (ERC-4626 compliant)  
**Strategy**: 50/50 USDC/WETH allocation  
**Network**: Ethereum Sepolia Testnet

### Contract Interactions

```solidity
// Deposit Flow
1. USDC.approve(vault, amount)
2. vault.deposit(uint256 assets, address receiver) returns (uint256 shares)

// Withdraw Flow
1. vault.redeem(uint256 shares, address receiver, address owner) returns (uint256 assets)

// Read-Only
vault.balanceOf(address account) returns (uint256)
vault.totalAssets() returns (uint256)
```

## Deployment Steps

### 1. Deploy MAVC Vault

```bash
cd erc-deployment
forge script test/TestVaultWithChainlink.s.sol --rpc-url $SEPOLIA_RPC_URL --broadcast
```

Copy the vault address from output.

### 2. Configure Backend

Add to `KryptonPay_Backend/.env`:
```bash
MAVC_VAULT_ADDRESS=<vault_address_from_step_1>
```

### 3. Fund DEX Integration (if needed)

The vault uses DEX integration for USDC→WETH swaps. Ensure it has liquidity.

### 4. Test Backend

```bash
cd KryptonPay_Backend
uvicorn app.main:app --reload
```

Visit: `http://localhost:8000/docs` to test endpoints

### 5. Test Frontend

```bash
npm run dev
```

Navigate to `/customer/grow/hedge-fund-v2`

## Circle API Requirements

### Contract Execution Support

Circle's Developer-Controlled Wallets SDK must support:
- `CreateContractExecutionTransactionForDeveloperRequest`
- `create_developer_transaction_contract_execution()`

**Note**: If Circle doesn't support contract execution, you'll see HTTP 501 errors. In that case, you'd need to:
1. Use Circle's raw transaction API, or
2. Switch to MetaMask integration (see deleted files history)

## Troubleshooting

### "Circle wallet contract execution not implemented"
- Circle SDK version doesn't support contract calls
- Check Circle documentation for contract interaction support
- May need to upgrade SDK or use raw transaction API

### "MAVC vault address not configured"
- Set `MAVC_VAULT_ADDRESS` in backend `.env`
- Restart backend server

### "User wallet not found"
- User hasn't logged in / wallet not created
- Check Firebase `wallets` collection
- Ensure user has Circle wallet from login flow

### "Insufficient USDC balance"
- User doesn't have enough USDC
- Use Circle's faucet or testnet faucets

### "Deposit failed: insufficient allowance"
- Approval transaction didn't complete
- Backend should handle this automatically
- Check Circle transaction status

## Monitoring

### Transaction Tracking

All Circle transactions return a `transaction_id`. Track them at:
- Circle Dashboard: https://console.circle.com/
- Sepolia Etherscan: https://sepolia.etherscan.io/

### Subgraph Analytics

Once configured, the subgraph tracks:
- Total deposits/withdrawals
- MAVC minted/burned
- User transaction history
- Vault allocation percentages

Visit subgraph playground:
https://api.studio.thegraph.com/query/121450/mavc/version/latest

## Testing Checklist

- [ ] Backend starts without errors
- [ ] `/api/v1/mavc/balance/{address}` returns balance
- [ ] User can deposit USDC (test with small amount like 10 USDC)
- [ ] Approval transaction appears in Circle dashboard
- [ ] Deposit transaction appears in Circle dashboard
- [ ] User receives MAVC shares
- [ ] User can withdraw MAVC shares
- [ ] Withdraw transaction appears in Circle dashboard  
- [ ] User receives USDC back
- [ ] Subgraph indexes transactions (if configured)

## API Documentation

Full API docs available at: `http://localhost:8000/docs` when backend is running

Look for the "mavc" tag for all MAVC-related endpoints.

## Security Considerations

1. **Backend Controls Wallets**: Backend has full control via Circle API
2. **Gas Fees**: Backend pays for all transactions
3. **Rate Limiting**: Consider implementing rate limits on deposit/withdraw
4. **Amount Validation**: Validate amounts server-side
5. **User Authentication**: Ensure proper authentication before operations
6. **Transaction Monitoring**: Monitor for failed transactions
7. **Circle API Keys**: Keep secure, never expose to frontend

## Future Enhancements

- [ ] Add transaction status polling
- [ ] Implement withdrawal limits/cooldown
- [ ] Add APY calculation endpoints
- [ ] Real-time balance updates via WebSocket
- [ ] Transaction history endpoint
- [ ] Email notifications for large transactions
- [ ] Multi-signature for large withdrawals



