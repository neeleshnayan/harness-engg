# Manual Price Update Guide

## Overview

You can manually force a price update for MAVC or MAVP strategies, bypassing the 30-minute interval check. This is useful for:
- Testing price updates
- Emergency updates when needed
- Debugging price update issues

## API Endpoint

**POST** `/api/v1/admin/force-price-update/{strategy_name}`

### Parameters

- `strategy_name` (path parameter): Either `MAVC` or `MAVP`

### Example Requests

#### Force MAVC Price Update
```bash
curl -X POST http://localhost:8000/api/v1/admin/force-price-update/MAVC
```

#### Force MAVP Price Update
```bash
curl -X POST http://localhost:8000/api/v1/admin/force-price-update/MAVP
```

### Response

**Success (200):**
```json
{
  "status": "success",
  "message": "MAVC price update forced successfully",
  "strategy": "MAVC"
}
```

**Error (400/500):**
```json
{
  "detail": "Error message here"
}
```

## Important Notes

1. **Bypasses Interval Check**: This endpoint bypasses the 30-minute interval check, but the contract may still enforce it if it has been redeployed with the interval check.

2. **Contract Enforcement**: If the contract has been redeployed with the interval check, the transaction will still fail if less than 30 minutes have passed since the last update.

3. **Gas Costs**: Each update requires gas fees. Make sure `ADMIN_PRIVATE_KEY` wallet has sufficient ETH.

4. **Logs**: Check backend logs for detailed information about the update process.

## Testing

1. Start your backend server
2. Call the endpoint using curl or Postman
3. Check the response and backend logs
4. Verify the transaction on Etherscan (link will be in logs)
5. Check the subgraph to see if the price update was indexed

## Troubleshooting

- **Transaction fails**: Check if contract enforces interval (if redeployed)
- **No response**: Check backend logs for errors
- **Subgraph not updating**: Verify contract address matches subgraph configuration

