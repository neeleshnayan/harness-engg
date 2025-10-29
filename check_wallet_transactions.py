"""
Check transactions for a specific Circle wallet
"""
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv("KryptonPay_Backend/.env")

CIRCLE_API_KEY = os.getenv("CIRCLE_API_KEY")
WALLET_ID = "7c33b7f8-b403-586f-969b-3b99dcedc2aa"

print("="*80)
print(f"Checking Transactions for Wallet: {WALLET_ID}")
print("="*80)

# Try the wallet-specific transactions endpoint
url = f"https://api.circle.com/v1/w3s/wallets/{WALLET_ID}/transactions"
headers = {"Authorization": f"Bearer {CIRCLE_API_KEY}"}

try:
    response = requests.get(url, headers=headers, params={"pageSize": 20}, timeout=10)

    print(f"\nStatus Code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print("\nResponse:")
        print(json.dumps(data, indent=2))

        transactions = data.get("data", {}).get("transactions", [])
        print(f"\n{'='*80}")
        print(f"Found {len(transactions)} transactions")
        print("="*80)

        for i, tx in enumerate(transactions[:10], 1):
            print(f"\n{i}. Transaction ID: {tx.get('id')}")
            print(f"   State: {tx.get('state')}")
            print(f"   Operation: {tx.get('operation')}")
            print(f"   Blockchain: {tx.get('blockchain')}")

            if tx.get('txHash'):
                print(f"   TX Hash: {tx.get('txHash')}")
                print(f"   Etherscan: https://sepolia.etherscan.io/tx/{tx.get('txHash')}")

            if tx.get('errorReason'):
                print(f"   ❌ Error: {tx.get('errorReason')}")
                if tx.get('errorDetails'):
                    print(f"   ❌ Details: {tx.get('errorDetails')}")

            print(f"   Created: {tx.get('createDate')}")
            print(f"   Updated: {tx.get('updateDate')}")
    else:
        print("\nError Response:")
        print(json.dumps(response.json(), indent=2))

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
