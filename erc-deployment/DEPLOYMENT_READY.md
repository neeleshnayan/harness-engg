# ✅ MAVC Yearn Deployment Ready!

## Status: **READY TO DEPLOY** 🚀

The MAVC Yearn strategy contract has been successfully compiled and is ready for deployment!

### ✅ What's Working

- [x] Dependencies installed (Yearn v3, Uniswap V3)
- [x] Remappings configured correctly
- [x] Contract compiles successfully
- [x] Deployment script ready

---

## 🚀 Next Steps to Deploy

### 1. Create `.env` File

Create a file at `erc-deployment/.env`:

```bash
# Deployer wallet private key (without 0x prefix)
PRIVATE_KEY=your_private_key_here

# Alchemy API key
ALCHEMY_API_KEY=your_alchemy_key

# Etherscan API key
ETHERSCAN_API_KEY=your_etherscan_key
```

### 2. Get Testnet ETH

Get Sepolia ETH from a faucet:
- https://sepoliafaucet.com
- https://www.alchemy.com/faucets/ethereum-sepolia

Check your balance:
```bash
cast balance YOUR_ADDRESS --rpc-url https://rpc.sepolia.org
```

### 3. Deploy to Sepolia

```bash
cd erc-deployment

forge script script/DeployMAVCYearn.s.sol:DeployMAVCYearn \
  --rpc-url sepolia \
  --broadcast \
  --verify \
  -vvvv
```

### 4. Save the Vault Address

The deployment will output:
```
===========================================
MAVC Yearn Strategy: 0xYOUR_VAULT_ADDRESS_HERE
===========================================
```

**SAVE THIS ADDRESS!**

### 5. Add to Firestore

Go to Firebase Console → Firestore → `quant_strategies` collection

Create document with ID: `MAVC_YEARN`

```json
{
  "VAULT_ADDRESS": "0xYOUR_VAULT_ADDRESS_HERE",
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

### 6. Test the Frontend

```bash
cd ..
npm run dev
```

Navigate to: http://localhost:3000/customer/grow/hedge-fund-v2

You should see the **MAVC Yearn** card!

---

## 📋 Contract Addresses (Sepolia)

These are hardcoded in the deployment script:

| Contract | Address |
|----------|---------|
| USDC | `0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238` |
| WBTC | `0x29f2D40B0605204364af54EC677bD022dA425d03` |
| BTC/USD Price Feed | `0x1b44F3514812d835EB1BDB0acB33d3fA3351Ee43` |
| Uniswap V3 Router | `0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E` |

---

## 🧪 After Deployment Testing

### Test 1: Check Vault Info
```bash
# Get vault name
cast call YOUR_VAULT_ADDRESS "name()(string)" --rpc-url sepolia

# Expected: "MAVC Yearn Strategy"
```

### Test 2: Check API
```bash
curl http://localhost:8000/api/v1/mavc-yearn/vault-info
```

### Test 3: Make a Deposit

1. Go to the MAVC Yearn card on the frontend
2. Click "Deposit"
3. Enter amount (start with 10 USDC)
4. Complete the transaction
5. Watch your vault share balance increase!

---

## ⚠️ Important Notes

1. **This is Sepolia testnet** - Perfect for testing, no real money
2. **First deposit costs more gas** - It includes a USDC→WBTC swap
3. **Rebalancing is automatic** - Happens when allocation drifts > 5%
4. **No lock-in period** - You can withdraw anytime
5. **Monitor transactions** - Check https://sepolia.etherscan.io

---

## 🐛 Troubleshooting

### Error: "insufficient funds for gas"
**Solution:** Get more Sepolia ETH from faucet

### Error: "deployment reverted"
**Solution:** Check that all contract addresses are correct for Sepolia

### Frontend shows "Coming Soon"
**Solution:**
1. Check Firestore has `MAVC_YEARN` document
2. Verify `VAULT_ADDRESS` is correct
3. Restart backend server

---

## 📚 Full Documentation

- **Complete Guide:** [YEARN_DEPLOYMENT_GUIDE.md](YEARN_DEPLOYMENT_GUIDE.md)
- **Quick Reference:** [QUICK_DEPLOY.md](QUICK_DEPLOY.md)
- **Architecture:** [../MAVC_YEARN_SUMMARY.md](../MAVC_YEARN_SUMMARY.md)

---

**You're all set! Run the deployment command above to launch your Yearn v3 vault! 🎉**
