# Update Firestore Configuration

## CRITICAL: Update MAVC_YEARN Vault Address

The old vault was broken. New working vault deployed.

### Firebase Console Method

1. Go to: https://console.firebase.google.com/
2. Select your project
3. Navigate to: **Firestore Database** (left sidebar)
4. Find collection: `quant_strategies`
5. Find document: `MAVC_YEARN`
6. Click **Edit document**
7. Update field `VAULT_ADDRESS` from:
   - Old: `0x910e2b419c041e1348fce403c540bc716cafd212` ❌
   - New: `0xe4993f3a226076C5cA73F583c5E1d8619A4FC423` ✅
8. Click **Update**

### Verify Configuration

After updating, the document should look like:
```json
{
  "VAULT_ADDRESS": "0xe4993f3a226076C5cA73F583c5E1d8619A4FC423",
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

### Test Backend Connection

```bash
cd KryptonPay_Backend
curl http://localhost:8000/api/v1/mavc-yearn/vault-info
```

Expected response:
```json
{
  "status": "success",
  "vault_address": "0xe4993f3a226076C5cA73F583c5E1d8619A4FC423",
  "total_assets": "0",
  "total_supply": "0",
  "price_per_share": 1.0
}
```

## Done!

After updating Firestore, deposits should work correctly.

