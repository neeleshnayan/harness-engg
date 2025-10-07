# MAVC Backend API Endpoints

✅ **COMPLETED** - The following endpoints have been implemented in your KryptonPay backend:

## Required Endpoints

### 1. Get MAVC Balance
```
GET /api/v1/mavc/balance/{wallet_address}
```

**Response:**
```json
{
  "status": "success",
  "balance": "1250.456789"
}
```

### 2. Deposit USDC for MAVC
```
POST /api/v1/mavc/deposit
```

**Request Body:**
```json
{
  "amount": "100.00",
  "wallet_address": "0x...",
  "user_id": "user123"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Deposit successful",
  "mavc_balance": "1350.456789",
  "usdc_balance": "4900.00",
  "transaction_hash": "0x..."
}
```

### 3. Withdraw MAVC for USDC
```
POST /api/v1/mavc/withdraw
```

**Request Body:**
```json
{
  "amount": "50.00",
  "wallet_address": "0x...",
  "user_id": "user123"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Withdrawal successful",
  "mavc_balance": "1300.456789",
  "usdc_balance": "4950.00",
  "transaction_hash": "0x..."
}
```

## Error Responses

```json
{
  "status": "error",
  "detail": "Insufficient MAVC balance",
  "error_code": "INSUFFICIENT_BALANCE"
}
```

## Implementation Notes

1. **Balance Calculation**: MAVC balance should be calculated based on user's vault shares
2. **USDC Integration**: Use existing USDC balance endpoint
3. **Transaction Logging**: Log all deposits/withdrawals for audit
4. **Validation**: Validate amounts, wallet addresses, and user permissions
5. **Smart Contract Integration**: Connect to your deployed MAVC vault contract

## Example FastAPI Implementation

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class DepositRequest(BaseModel):
    amount: str
    wallet_address: str
    user_id: str

class WithdrawRequest(BaseModel):
    amount: str
    wallet_address: str
    user_id: str

@router.get("/api/v1/mavc/balance/{wallet_address}")
async def get_mavc_balance(wallet_address: str):
    # Implement balance fetching logic
    balance = await get_user_mavc_balance(wallet_address)
    return {"status": "success", "balance": str(balance)}

@router.post("/api/v1/mavc/deposit")
async def deposit_mavc(request: DepositRequest):
    # Implement deposit logic
    # 1. Validate user and wallet
    # 2. Check USDC balance
    # 3. Execute deposit transaction
    # 4. Update balances
    # 5. Return success response
    
    try:
        result = await execute_deposit(
            request.amount,
            request.wallet_address,
            request.user_id
        )
        return {
            "status": "success",
            "message": "Deposit successful",
            "mavc_balance": result["mavc_balance"],
            "usdc_balance": result["usdc_balance"],
            "transaction_hash": result["tx_hash"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/api/v1/mavc/withdraw")
async def withdraw_mavc(request: WithdrawRequest):
    # Implement withdrawal logic
    # 1. Validate user and wallet
    # 2. Check MAVC balance
    # 3. Execute withdrawal transaction
    # 4. Update balances
    # 5. Return success response
    
    try:
        result = await execute_withdrawal(
            request.amount,
            request.wallet_address,
            request.user_id
        )
        return {
            "status": "success",
            "message": "Withdrawal successful",
            "mavc_balance": result["mavc_balance"],
            "usdc_balance": result["usdc_balance"],
            "transaction_hash": result["tx_hash"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

## ✅ Frontend Integration Complete

The frontend is now configured to:
- Use `http://127.0.0.1:8000` as the API base URL
- Send proper request payloads with user data
- Handle success and error responses
- Update balances after transactions
- Show loading states during API calls

## 🚀 Testing

1. **Backend is running** on `http://127.0.0.1:8000`
2. **Frontend** connects to `http://localhost:3001/customer/grow/hedge-fund-v2`
3. **API endpoints tested** and working:
   - ✅ `GET /api/v1/mavc/balance/{wallet_address}` - Returns mock balance
   - ✅ `POST /api/v1/mavc/deposit` - Validates user and processes deposit
   - ✅ `POST /api/v1/mavc/withdraw` - Validates user and processes withdrawal

## 📝 Next Steps

1. **Replace mock data** with real MAVC vault smart contract integration
2. **Add real USDC transfers** using Circle API
3. **Implement vault share calculations** for MAVC balance
4. **Add transaction logging** to Firestore
5. **Deploy to production** when ready

