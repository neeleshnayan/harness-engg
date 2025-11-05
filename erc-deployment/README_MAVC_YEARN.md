# MAVC Yearn V3 Deployment

Deploy a production-ready Yearn v3 tokenized strategy with 50/50 USDC/WBTC allocation.

## 🚀 Quick Start

### Windows
```cmd
cd erc-deployment
INSTALL_DEPENDENCIES.bat
```

### Linux/Mac
```bash
cd erc-deployment
bash INSTALL_DEPENDENCIES.sh
```

This will:
- ✅ Install Yearn v3 contracts
- ✅ Install Uniswap V3 dependencies
- ✅ Update foundry.toml remappings
- ✅ Create .env template
- ✅ Test compilation

---

## 📁 File Structure

```
erc-deployment/
├── src/
│   └── MAVCYearnStrategy.sol          # Main strategy contract
├── script/
│   └── DeployMAVCYearn.s.sol          # Deployment script
├── lib/                               # Dependencies (auto-installed)
│   ├── tokenized-strategy/            # Yearn v3 base
│   ├── v3-periphery/                  # Uniswap V3 periphery
│   └── v3-core/                       # Uniswap V3 core
├── foundry.toml                       # Foundry configuration
├── .env                               # Environment variables (create this!)
├── INSTALL_DEPENDENCIES.bat           # Windows installer
├── INSTALL_DEPENDENCIES.sh            # Linux/Mac installer
├── YEARN_DEPLOYMENT_GUIDE.md          # Complete deployment guide
├── QUICK_DEPLOY.md                    # Quick reference
└── README_MAVC_YEARN.md               # This file
```

---

## 📋 Prerequisites

### 1. Install Foundry

**Windows:**
```powershell
# Run PowerShell as Administrator
irm https://raw.githubusercontent.com/foundry-rs/foundry/master/foundryup/install.ps1 | iex
foundryup
```

**Linux/Mac:**
```bash
curl -L https://foundry.paradigm.xyz | bash
foundryup
```

Verify installation:
```bash
forge --version
```

### 2. Get API Keys

- **Alchemy:** https://alchemy.com (for RPC access)
- **Etherscan:** https://etherscan.io/myapikey (for verification)
- **Private Key:** Export from MetaMask/wallet

### 3. Fund Wallet

Get Sepolia ETH for gas:
- https://sepoliafaucet.com
- https://www.alchemy.com/faucets/ethereum-sepolia

---

## ⚡ Deploy in 3 Steps

### Step 1: Install Dependencies
```bash
# Windows
INSTALL_DEPENDENCIES.bat

# Linux/Mac
bash INSTALL_DEPENDENCIES.sh
```

### Step 2: Configure Environment
Edit `.env` file:
```bash
PRIVATE_KEY=your_private_key_without_0x
ALCHEMY_API_KEY=your_alchemy_key
ETHERSCAN_API_KEY=your_etherscan_key
```

### Step 3: Deploy
```bash
forge script script/DeployMAVCYearn.s.sol:DeployMAVCYearn \
  --rpc-url sepolia \
  --broadcast \
  --verify \
  -vvvv
```

**Save the vault address from the output!**

---

## 🔧 Post-Deployment

### 1. Add to Firestore

Firebase Console → Firestore → `quant_strategies` → Create document:

```json
{
  "id": "MAVC_YEARN",
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
  "risk_grade": "B"
}
```

### 2. Test Backend

```bash
cd ../KryptonPay_Backend
uvicorn app.main:app --reload

# Test API
curl http://localhost:8000/api/v1/mavc-yearn/vault-info
```

### 3. Test Frontend

```bash
cd ..
npm run dev

# Open browser
http://localhost:3000/customer/grow/hedge-fund-v2
```

Look for the **MAVC Yearn** card with purple "Yearn v3" badge!

---

## 📊 Contract Features

### ERC-4626 Standard
- `deposit(uint256 assets, address receiver)` - Deposit USDC, get shares
- `redeem(uint256 shares, address receiver, address owner)` - Burn shares, get USDC
- `totalAssets()` - Total value of USDC + WBTC
- `totalSupply()` - Total vault shares
- `convertToAssets(uint256 shares)` - Calculate USDC value of shares

### MAVC Strategy
- 50% USDC allocation
- 50% WBTC allocation
- Auto-rebalancing when drift > 5%
- Chainlink BTC/USD price feeds
- Uniswap V3 swaps (0.3% fee tier)
- 1% max slippage protection

### Management
- `manualRebalance()` - Trigger rebalance manually
- `getCurrentAllocation()` - View current USDC/WBTC split
- `setManagement(address)` - Transfer management role
- `setKeeper(address)` - Set keeper for automation

---

## 🧪 Testing Commands

### Check Vault Status
```bash
# Get vault name
cast call YOUR_VAULT "name()(string)" --rpc-url sepolia

# Get total assets
cast call YOUR_VAULT "totalAssets()(uint256)" --rpc-url sepolia

# Get allocation
cast call YOUR_VAULT "getCurrentAllocation()(uint256,uint256)" --rpc-url sepolia
```

### Check Balances
```bash
# USDC in vault
cast call 0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238 \
  "balanceOf(address)(uint256)" YOUR_VAULT --rpc-url sepolia

# WBTC in vault
cast call 0x29f2D40B0605204364af54EC677bD022dA425d03 \
  "balanceOf(address)(uint256)" YOUR_VAULT --rpc-url sepolia
```

### Monitor Events
```bash
# Watch rebalance events
cast logs --address YOUR_VAULT \
  --event "Rebalanced(uint256,uint256,uint256)" \
  --rpc-url sepolia --follow
```

---

## 🐛 Troubleshooting

### Issue: `forge: command not found`
**Solution:** Install Foundry (see Prerequisites)

### Issue: Compilation errors with Yearn/Uniswap
**Solution:**
```bash
# Reinstall dependencies
rm -rf lib/tokenized-strategy lib/v3-periphery lib/v3-core
forge install yearn/tokenized-strategy Uniswap/v3-periphery Uniswap/v3-core --no-commit
forge build
```

### Issue: Deployment fails with "insufficient funds"
**Solution:** Fund wallet with Sepolia ETH from faucet

### Issue: Contract verification fails
**Solution:** Wait 1 minute, then verify manually:
```bash
forge verify-contract YOUR_VAULT \
  --chain-id 11155111 \
  src/MAVCYearnStrategy.sol:MAVCYearnStrategy \
  --etherscan-api-key $ETHERSCAN_API_KEY
```

### Issue: Frontend shows "Coming Soon"
**Solution:**
1. Check Firestore has MAVC_YEARN document
2. Verify VAULT_ADDRESS field is correct
3. Restart backend: `uvicorn app.main:app --reload`

---

## 📚 Documentation

| File | Description |
|------|-------------|
| **YEARN_DEPLOYMENT_GUIDE.md** | Complete step-by-step deployment guide with testing |
| **QUICK_DEPLOY.md** | Quick reference cheat sheet with common commands |
| **MAVC_YEARN_SUMMARY.md** | High-level overview and architecture documentation |
| **README_MAVC_YEARN.md** | This file - getting started guide |

---

## 🔐 Security

### Before Mainnet:
- [ ] Get professional security audit
- [ ] Test all functions thoroughly
- [ ] Verify all contract addresses
- [ ] Test emergency procedures
- [ ] Set up monitoring/alerts
- [ ] Review gas costs
- [ ] Check Chainlink feed status
- [ ] Verify Uniswap pool liquidity

### Access Control:
- **Management:** Can trigger rebalancing, set parameters
- **Keeper:** Can call report/tend functions
- **Emergency Admin:** Can pause deposits

---

## 📈 Expected Behavior

### After Deployment:
1. Vault has 0 total assets
2. Total supply is 0 shares
3. Price per share is 1.0
4. Allocation is 0/0 (no assets yet)

### After First Deposit:
1. User deposits 100 USDC
2. Receives ~100 vault shares (1:1 ratio initially)
3. Vault rebalances to 50 USDC / 50 USDC worth of WBTC
4. Allocation shows ~50%/50%

### After Price Movement:
1. BTC price changes
2. Allocation drifts (e.g., 48%/52%)
3. Next deposit triggers rebalance if drift > 5%
4. Allocation returns to 50%/50%

---

## 🎯 Key Metrics

| Metric | Target | Notes |
|--------|--------|-------|
| **Gas Cost (Deploy)** | ~2-3M gas | ~$50-100 on mainnet |
| **Gas Cost (Deposit)** | ~200-300k | First deposit higher (USDC→WBTC swap) |
| **Gas Cost (Withdraw)** | ~150-250k | May include WBTC→USDC swap |
| **Gas Cost (Rebalance)** | ~150-200k | Only when drift > 5% |
| **Slippage** | 1% max | Adjustable in contract |
| **Rebalance Threshold** | 5% | Adjustable in contract |

---

## 🚀 Production Checklist

- [ ] Deploy to Sepolia testnet
- [ ] Test deposits (5+ transactions)
- [ ] Test withdrawals (5+ transactions)
- [ ] Test rebalancing (verify 50/50 maintained)
- [ ] Monitor for 1-2 weeks
- [ ] Get smart contract audit
- [ ] Review gas optimization
- [ ] Set up monitoring/alerts
- [ ] Create runbook for operations
- [ ] Train team on emergency procedures
- [ ] Deploy to mainnet
- [ ] Announce to users

---

## 💡 Tips

1. **Start Small:** Test with small amounts (1-10 USDC) first
2. **Monitor Events:** Watch for Rebalanced and SwapExecuted events
3. **Check Allocation:** Should stay close to 50%/50%
4. **Gas Costs:** First deposit costs more (includes swap)
5. **Price Feeds:** Chainlink updates every 1 hour max
6. **Slippage:** Increase if swaps fail (but not > 5%)

---

## 📞 Need Help?

1. **Check logs:** Review Foundry output carefully
2. **Check Etherscan:** View transaction details
3. **Test on Sepolia:** Always test before mainnet
4. **Read docs:** See YEARN_DEPLOYMENT_GUIDE.md for detailed help

---

**Ready to deploy? Run `INSTALL_DEPENDENCIES.bat` (Windows) or `bash INSTALL_DEPENDENCIES.sh` (Linux/Mac) to get started! 🚀**
