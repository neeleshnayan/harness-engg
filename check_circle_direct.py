"""
Check Circle transaction status directly from Circle API
"""
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv("KryptonPay_Backend/.env")

import sys

CIRCLE_API_KEY = os.getenv("CIRCLE_API_KEY")
TRANSACTION_ID = sys.argv[1] if len(sys.argv) > 1 else "74680539-725a-549c-b6b6-f7ee0dd1005b"

print("="*80)
print(f"Checking Circle Transaction DIRECTLY from Circle API")
print(f"Transaction ID: {TRANSACTION_ID}")
print("="*80)

url = f"https://api.circle.com/v1/w3s/developer/transactions/{TRANSACTION_ID}"
headers = {"Authorization": f"Bearer {CIRCLE_API_KEY}"}

try:
    response = requests.get(url, headers=headers, timeout=10)

    print(f"\nStatus Code: {response.status_code}")
    print(f"\nResponse:")
    print(json.dumps(response.json(), indent=2))

    if response.status_code == 200:
        data = response.json()
        tx = data.get("data", {})
        state = tx.get("state")
        tx_hash = tx.get("txHash")
        error_reason = tx.get("errorReason")
        error_details = tx.get("errorDetails")

        print("\n" + "="*80)
        print("Summary:")
        print(f"  State: {state}")
        if tx_hash:
            print(f"  TX Hash: {tx_hash}")
            print(f"  Etherscan: https://sepolia.etherscan.io/tx/{tx_hash}")
        if error_reason:
            print(f"  ❌ Error Reason: {error_reason}")
        if error_details:
            print(f"  ❌ Error Details: {error_details}")
        print("="*80)

except Exception as e:
    print(f"Error: {e}")
