# MAVC Yearn - Quick Deployment Reference

## 🚀 Quick Start (5 Steps)

### 1. Install Dependencies
```bash
cd erc-deployment
forge install yearn/tokenized-strategy --no-commit
forge install Uniswap/v3-periphery --no-commit
forge install Uniswap/v3-core --no-commit
```

### 2. Configure Environment
```bash
# Create .env file
cat > .env << 'EOF'
PRIVATE_KEY=your_private_key_here
ALCHEMY_API_KEY=your_alchemy_key
ETHERSCAN_API_KEY=your_etherscan_key
EOF

source .env
```

### 3. Update foundry.toml
Add these remappings to `foundry.toml`:
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

### 4. Deploy to Sepolia
```bash
forge script script/DeployMAVCYearn.s.sol:DeployMAVCYearn \
  --rpc-url sepolia \
  --broadcast \
  --verify \
  -vvvv
```

### 5. Add to Firestore
```json
{
  "collection": "quant_strategies",
  "document": "MAVC_YEARN",
  "fields": {
    "VAULT_ADDRESS": "0xYourDeployedAddress"
  }
}
```

---

## 📋 Contract Addresses (Sepolia)

| Contract | Address |
|----------|---------|
| USDC | `0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238` |
| WBTC | `0x29f2D40B0605204364af54EC677bD022dA425d03` |
| BTC/USD Feed | `0x1b44F3514812d835EB1BDB0acB33d3fA3351Ee43` |
| Uniswap Router | `0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E` |

---

## 🧪 Quick Test Commands

```bash
# Test vault
cast call YOUR_VAULT "name()(string)" --rpc-url sepolia

# Check allocation
cast call YOUR_VAULT "getCurrentAllocation()(uint256,uint256)" --rpc-url sepolia

# Manual rebalance
cast send YOUR_VAULT "manualRebalance()" --rpc-url sepolia --private-key $PRIVATE_KEY

# Get vault info via API
curl http://localhost:8000/api/v1/mavc-yearn/vault-info
```

---

## 🔧 Backend Setup

1. **Update .env** in `KryptonPay_Backend/`:
```bash
ETHEREUM_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/${ALCHEMY_API_KEY}
CIRCLE_API_KEY=your_circle_key
ENTITY_SECRET=your_entity_secret
```

2. **Start backend:**
```bash
cd KryptonPay_Backend
uvicorn app.main:app --reload
```

3. **Test API:**
```bash
curl http://localhost:8000/docs
```

---

## 🎨 Frontend Access

1. Start dev server:
```bash
npm run dev
```

2. Navigate to:
```
http://localhost:3000/customer/grow/hedge-fund-v2
```

3. Look for **MAVC Yearn** card with purple "Yearn v3" badge

---

## ⚡ One-Line Deployment (After Setup)

```bash
forge script script/DeployMAVCYearn.s.sol:DeployMAVCYearn --rpc-url sepolia --broadcast --verify -vvvv && echo "✅ Deployed! Add address to Firestore."
```

---

## 🐛 Common Issues

| Issue | Solution |
|-------|----------|
| `forge: command not found` | Run `curl -L https://foundry.paradigm.xyz \| bash && foundryup` |
| Compilation error | Run `forge install` and check remappings |
| Out of gas | Fund wallet: `cast send --value 0.1ether YOUR_WALLET --rpc-url sepolia` |
| Verification failed | Wait 1 min, then verify manually |
| Frontend shows "Coming Soon" | Check Firestore VAULT_ADDRESS field |

---

## 📊 Monitoring Dashboard

```bash
# Real-time logs
cast logs --address YOUR_VAULT --follow --rpc-url sepolia

# Check balances
cast call 0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238 "balanceOf(address)(uint256)" YOUR_VAULT --rpc-url sepolia
```

---

## 🎯 Next Steps After Deployment

1. ✅ Deploy contract
2. ✅ Verify on Etherscan
3. ✅ Add to Firestore
4. ✅ Test deposit via frontend
5. ✅ Test withdrawal
6. ✅ Monitor rebalancing
7. ✅ Set up alerts

**Complete documentation:** See `YEARN_DEPLOYMENT_GUIDE.md`
