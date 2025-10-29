"""
List recent Circle transactions
"""
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv("KryptonPay_Backend/.env")

CIRCLE_API_KEY = os.getenv("CIRCLE_API_KEY")

print("="*80)
print("Listing Recent Circle Transactions")
print("="*80)

url = "https://api.circle.com/v1/w3s/developer/transactions"
headers = {"Authorization": f"Bearer {CIRCLE_API_KEY}"}

try:
    response = requests.get(url, headers=headers, params={"pageSize": 10}, timeout=10)

    print(f"\nStatus Code: {response.status_code}")
    print(f"\nResponse:")
    data = response.json()
    print(json.dumps(data, indent=2))

    if response.status_code == 200 and "data" in data:
        transactions = data.get("data", {}).get("transactions", [])
        print(f"\n Found {len(transactions)} recent transactions:")
        for tx in transactions[:5]:
            print(f"\n  ID: {tx.get('id')}")
            print(f"  State: {tx.get('state')}")
            print(f"  Type: {tx.get('transactionType')}")
            if tx.get('txHash'):
                print(f"  TX Hash: {tx.get('txHash')}")

except Exception as e:
    print(f"Error: {e}")
