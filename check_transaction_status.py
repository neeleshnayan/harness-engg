"""
Check the status of a Circle transaction
"""
import requests
import sys
import json

BACKEND_URL = "http://localhost:8000"
TRANSACTION_ID = "74680539-725a-549c-b6b6-f7ee0dd1005b"  # Latest withdrawal

if len(sys.argv) > 1:
    TRANSACTION_ID = sys.argv[1]

print("="*80)
print(f"Checking Circle Transaction Status")
print(f"Transaction ID: {TRANSACTION_ID}")
print("="*80)

try:
    response = requests.get(
        f"{BACKEND_URL}/api/v1/mavc/transaction/{TRANSACTION_ID}/status",
        timeout=10
    )

    print(f"\nStatus Code: {response.status_code}")
    print(f"\nResponse:")
    print(json.dumps(response.json(), indent=2))

    if response.status_code == 200:
        data = response.json()
        tx = data.get("transaction", {})
        state = tx.get("state")
        tx_hash = tx.get("txHash")
        error_reason = tx.get("errorReason")

        print("\n" + "="*80)
        print("Summary:")
        print(f"  State: {state}")
        if tx_hash:
            print(f"  TX Hash: {tx_hash}")
            print(f"  Etherscan: https://sepolia.etherscan.io/tx/{tx_hash}")
        if error_reason:
            print(f"  ❌ Error: {error_reason}")
        print("="*80)

except Exception as e:
    print(f"Error: {e}")
