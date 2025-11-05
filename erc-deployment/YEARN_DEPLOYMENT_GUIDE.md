# MAVC Yearn V3 Vault Deployment Guide

Complete guide to deploy the MAVC Yearn v3 tokenized strategy to blockchain.

## 📋 Prerequisites

### 1. Install Dependencies

First, ensure you have Foundry installed:
```bash
# If not installed, run:
curl -L https://foundry.paradigm.xyz | bash
foundryup
```

### 2. Install Yearn V3 Contracts

```bash
cd erc-deployment

# Install Yearn v3 tokenized strategy base
forge install yearn/tokenized-strategy --no-commit

# Install Uniswap V3 (for swaps)
forge install Uniswap/v3-periphery --no-commit
forge install Uniswap/v3-core --no-commit
```

### 3. Update Remappings

Add to `foundry.toml` remappings:
```toml
remappings = [
    "@chainlink/contracts/=lib/chainlink/contracts/",
    "@openzeppelin/contracts/=lib/openzeppelin-contracts/contracts/",
    "chainlink-brownie-contracts/=lib/chainlink-brownie-contracts/",
    "@yearn-vaults/=lib/tokenized-strategy/src/",
    "@uniswap/v3-periphery/contracts/=lib/v3-periphery/contracts/",
    "@uniswap/v3-core/contracts/=lib/v3-core/contracts/"
]
```

### 4. Set Up Environment Variables

Create `.env` file in `erc-deployment/` directory:

```bash
# Deployment wallet private key (NEVER commit this!)
PRIVATE_KEY=your_private_key_here

# RPC URLs
ALCHEMY_API_KEY=your_alchemy_key
SEPOLIA_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/${ALCHEMY_API_KEY}
MAINNET_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}

# Etherscan API key for verification
ETHERSCAN_API_KEY=your_etherscan_key
```

Load environment:
```bash
source .env
```

---

## 🚀 Deployment Steps

### Step 1: Compile Contracts

```bash
cd erc-deployment
forge build
```

If successful, you should see:
```
[⠊] Compiling...
[⠒] Compiling 1 files with 0.8.20
[⠢] Solc 0.8.20 finished in X.XXs
Compiler run successful!
```

### Step 2: Test Deployment (Dry Run)

Test deployment without broadcasting:
```bash
forge script script/DeployMAVCYearn.s.sol:DeployMAVCYearn --rpc-url sepolia
```

### Step 3: Deploy to Sepolia Testnet

```bash
forge script script/DeployMAVCYearn.s.sol:DeployMAVCYearn \
  --rpc-url sepolia \
  --broadcast \
  --verify \
  -vvvv
```

**Expected Output:**
```
===========================================
DEPLOYING MAVC YEARN STRATEGY
===========================================
Deployer address: 0x...
Deployer balance: 0.5 ETH

Network: SEPOLIA TESTNET

Contract Addresses:
- USDC: 0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238
- WBTC: 0x29f2D40B0605204364af54EC677bD022dA425d03
- BTC/USD Feed: 0x1b44F3514812d835EB1BDB0acB33d3fA3351Ee43
- Uniswap V3 Router: 0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E

===========================================
DEPLOYMENT SUCCESSFUL!
===========================================
MAVC Yearn Strategy: 0xYourDeployedVaultAddress
```

**Save this vault address!** You'll need it for the next steps.

### Step 4: Verify Contract on Etherscan

If auto-verification fails, manually verify:

```bash
forge verify-contract YOUR_VAULT_ADDRESS \
  --chain-id 11155111 \
  --constructor-args $(cast abi-encode "constructor(address,string,address,address,address)" \
    0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238 \
    "MAVC Yearn Strategy" \
    0x29f2D40B0605204364af54EC677bD022dA425d03 \
    0x1b44F3514812d835EB1BDB0acB33d3fA3351Ee43 \
    0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E) \
  src/MAVCYearnStrategy.sol:MAVCYearnStrategy \
  --etherscan-api-key $ETHERSCAN_API_KEY
```

---

## 🔧 Backend Configuration

### Step 5: Update Firestore Database

Add the vault address to your Firestore database:

1. Go to Firebase Console → Firestore Database
2. Navigate to collection: `quant_strategies`
3. Create new document with ID: `MAVC_YEARN`
4. Add fields:

```json
{
  "VAULT_ADDRESS": "0xYourDeployedVaultAddress",
  "name": "MAVC Yearn",
  "description": "Yearn v3 tokenized strategy with 50/50 USDC/BTC allocation",
  "net_apy": 45.2,
  "aum": 2.1,
  "sharpe_ratio": 1.12,
  "max_drawdown": 18.50,
  "lock_in_period": "None",
  "participants": 0,
  "performance_fee": 20.0,
  "risk_grade": "B",
  "subgraph_url": null
}
```

### Step 6: Update Frontend Configuration

The frontend will automatically use the Firestore config, but you can verify by checking:

**File:** `src/components/wallet/MAVCYearnStrategyCard.tsx`

The card fetches vault address from Firestore in the `fetchBalances()` function.

---

## 🧪 Testing the Deployment

### Test 1: Check Vault Details

```bash
# Get vault name
cast call YOUR_VAULT_ADDRESS "name()(string)" --rpc-url sepolia

# Get vault symbol
cast call YOUR_VAULT_ADDRESS "symbol()(string)" --rpc-url sepolia

# Get underlying asset (should be USDC)
cast call YOUR_VAULT_ADDRESS "asset()(address)" --rpc-url sepolia

# Get decimals
cast call YOUR_VAULT_ADDRESS "decimals()(uint8)" --rpc-url sepolia
```

### Test 2: Check Integrations

```bash
# Check WBTC address
cast call YOUR_VAULT_ADDRESS "WBTC()(address)" --rpc-url sepolia

# Check BTC price feed
cast call YOUR_VAULT_ADDRESS "btcUsdPriceFeed()(address)" --rpc-url sepolia

# Get current BTC price
cast call 0x1b44F3514812d835EB1BDB0acB33d3fA3351Ee43 "latestRoundData()(uint80,int256,uint256,uint256,uint80)" --rpc-url sepolia
```

### Test 3: Frontend Integration Test

1. Start your backend:
```bash
cd ../KryptonPay_Backend
uvicorn app.main:app --reload
```

2. Start your frontend:
```bash
cd ../
npm run dev
```

3. Navigate to: `http://localhost:3000/customer/grow/hedge-fund-v2`

4. You should see the **MAVC Yearn** card with:
   - Yearn v3 badge
   - 50/50 allocation display
   - Deposit/Withdraw buttons

### Test 4: API Endpoints Test

```bash
# Test vault info endpoint
curl http://localhost:8000/api/v1/mavc-yearn/vault-info

# Expected response:
{
  "status": "success",
  "vault_address": "0x...",
  "total_assets": "0",
  "total_supply": "0",
  "price_per_share": 1.0
}
```

---

## 💰 Fund the Vault (Initial Liquidity)

### Option 1: Circle Wallet Deposit (Recommended)

Use your existing Circle wallet integration:

1. Go to the MAVC Yearn card on the frontend
2. Click "Deposit"
3. Enter amount (e.g., 100 USDC)
4. Follow the approval + deposit flow

### Option 2: Manual Deposit via Cast

```bash
# 1. Approve USDC
cast send 0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238 \
  "approve(address,uint256)" \
  YOUR_VAULT_ADDRESS \
  1000000000 \
  --rpc-url sepolia \
  --private-key $PRIVATE_KEY

# 2. Deposit USDC
cast send YOUR_VAULT_ADDRESS \
  "deposit(uint256,address)" \
  1000000000 \
  YOUR_WALLET_ADDRESS \
  --rpc-url sepolia \
  --private-key $PRIVATE_KEY
```

---

## 🔄 Rebalancing

The vault automatically rebalances when:
- New deposits occur (`_deployFunds()`)
- Allocation drifts beyond 5% threshold

### Manual Rebalance

```bash
# Trigger manual rebalance (management only)
cast send YOUR_VAULT_ADDRESS \
  "manualRebalance()" \
  --rpc-url sepolia \
  --private-key $PRIVATE_KEY
```

### Check Current Allocation

```bash
cast call YOUR_VAULT_ADDRESS \
  "getCurrentAllocation()(uint256,uint256)" \
  --rpc-url sepolia
```

Output: `(5000, 5000)` = 50% USDC, 50% WBTC

---

## 📊 Monitoring

### View Events

```bash
# Watch for rebalance events
cast logs --address YOUR_VAULT_ADDRESS \
  --event "Rebalanced(uint256,uint256,uint256)" \
  --rpc-url sepolia

# Watch for swap events
cast logs --address YOUR_VAULT_ADDRESS \
  --event "SwapExecuted(address,address,uint256,uint256)" \
  --rpc-url sepolia
```

### Check Balances

```bash
# USDC balance in vault
cast call 0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238 \
  "balanceOf(address)(uint256)" \
  YOUR_VAULT_ADDRESS \
  --rpc-url sepolia

# WBTC balance in vault
cast call 0x29f2D40B0605204364af54EC677bD022dA425d03 \
  "balanceOf(address)(uint256)" \
  YOUR_VAULT_ADDRESS \
  --rpc-url sepolia
```

---

## 🔐 Security Considerations

### Before Mainnet Deployment:

1. **Audit the contract** - Get professional security audit
2. **Test thoroughly** - Run extensive tests on testnet
3. **Verify all addresses** - Double-check all contract addresses
4. **Set proper permissions** - Configure management/keeper roles
5. **Test emergency procedures** - Ensure you can pause/shutdown if needed
6. **Monitor gas costs** - Uniswap swaps can be expensive
7. **Check price feeds** - Ensure Chainlink feeds are active
8. **Test slippage** - Verify MAX_SLIPPAGE_BPS is appropriate

### Role Management

```bash
# Set management address (can call manualRebalance)
cast send YOUR_VAULT_ADDRESS \
  "setManagement(address)" \
  NEW_MANAGEMENT_ADDRESS \
  --rpc-url sepolia \
  --private-key $PRIVATE_KEY

# Set keeper address (can call tend/report)
cast send YOUR_VAULT_ADDRESS \
  "setKeeper(address)" \
  KEEPER_ADDRESS \
  --rpc-url sepolia \
  --private-key $PRIVATE_KEY
```

---

## 🐛 Troubleshooting

### Error: "Failed to connect to Ethereum RPC"
**Solution:** Check your RPC URL and API key in `.env`

### Error: "Insufficient funds for gas"
**Solution:** Fund your deployer wallet with ETH for gas

### Error: "Contract verification failed"
**Solution:** Manually verify using the command in Step 4

### Error: "Approval failed"
**Solution:** Check USDC token address and wallet has USDC balance

### Error: "Uniswap swap failed"
**Solution:** Ensure:
- USDC/WBTC pool exists on Uniswap V3
- Pool has sufficient liquidity
- Slippage tolerance is appropriate

### Frontend shows "Coming Soon"
**Solution:**
1. Check Firestore has `MAVC_YEARN` document
2. Verify `VAULT_ADDRESS` field is correct
3. Restart backend server

---

## 📚 Additional Resources

- **Yearn v3 Docs:** https://docs.yearn.fi/developers/v3/overview
- **ERC-4626 Standard:** https://eips.ethereum.org/EIPS/eip-4626
- **Foundry Book:** https://book.getfoundry.sh/
- **Uniswap V3 Docs:** https://docs.uniswap.org/contracts/v3/overview
- **Chainlink Price Feeds:** https://docs.chain.link/data-feeds/price-feeds/addresses

---

## 🚀 Mainnet Deployment Checklist

Before deploying to mainnet:

- [ ] All tests pass
- [ ] Contract audited by professionals
- [ ] Testnet deployment successful
- [ ] All deposits/withdrawals tested
- [ ] Rebalancing tested
- [ ] Emergency procedures tested
- [ ] Gas costs analyzed
- [ ] Liquidity sufficient in Uniswap pools
- [ ] Monitoring/alerting set up
- [ ] Documentation complete
- [ ] Team trained on operations

---

## 📞 Support

If you encounter issues:
1. Check logs in `erc-deployment/broadcast/` folder
2. Review transaction on Etherscan
3. Check backend logs: `tail -f logs/app.log`
4. Test with smaller amounts first

**Contract deployed! Ready to revolutionize DeFi with MAVC Yearn! 🎉**
