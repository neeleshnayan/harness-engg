# 🏦 MultiAssetVault Interaction Guide

## 📍 **Your Deployed Contracts**

- **Vault**: `0x284Be3234de1B24F522afFeFB7906C151A42e924`
- **Oracle**: `0xe2429E2B75b88918a8dD78066045EA645AB533BD`  
- **DEX**: `0x8eAD64b651505842Db8912AEcA5C7Fd547f66Ef0`

## 💰 **Required Tokens**

- **DAI**: `0x68194a729C2450ad26072b3D33ADaCbcef39D574`
- **EUR**: `0x08210F9170F89Ab7658F0B5E3fF39b0E03C594D4`

## 🚀 **How to Interact**

### **Option 1: Using Etherscan (Easiest)**

1. Go to: https://sepolia.etherscan.io/address/0x284Be3234de1B24F522afFeFB7906C151A42e924#writeContract
2. Connect your wallet
3. Use the `deposit` function:
   - `assets`: Amount in DAI (e.g., 1000000000000000000 for 1 DAI)
   - `receiver`: Your wallet address

### **Option 2: Using Forge Script**

```bash
# Deposit 10 DAI into the vault
forge script script/InteractWithVault.s.sol --rpc-url sepolia --broadcast
```

### **Option 3: Using Cast Commands**

```bash
# Approve DAI spending
cast send 0x68194a729C2450ad26072b3D33ADaCbcef39D574 "approve(address,uint256)" 0x284Be3234de1B24F522afFeFB7906C151A42e924 1000000000000000000000 --rpc-url sepolia --private-key $PRIVATE_KEY

# Deposit 10 DAI
cast send 0x284Be3234de1B24F522afFeFB7906C151A42e924 "deposit(uint256,address)" 10000000000000000000 YOUR_ADDRESS --rpc-url sepolia --private-key $PRIVATE_KEY
```

## 📊 **Check Balances**

```bash
# Check your vault shares
cast call 0x284Be3234de1B24F522afFeFB7906C151A42e924 "balanceOf(address)" YOUR_ADDRESS --rpc-url sepolia

# Check vault's DAI balance
cast call 0x68194a729C2450ad26072b3D33ADaCbcef39D574 "balanceOf(address)" 0x284Be3234de1B24F522afFeFB7906C151A42e924 --rpc-url sepolia
```

## 🎯 **Expected Results**

After depositing, you'll see:
- ✅ Transaction appears on Etherscan
- ✅ You receive MAVC tokens
- ✅ Vault holds your DAI
- ✅ Real blockchain interaction!
