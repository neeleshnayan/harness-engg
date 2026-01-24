import requests
import json

# URL from the code fallback
url = 'https://api.studio.thegraph.com/query/1714038/krypton-liquidity-pools-sepolia/version/latest'

# Strategy Address from latest_strategies.json (GOLD Yearn)
strategy_address = '0x008E6716696D5625D5E95C106f4aa736435E57aa'.lower()
pool_address = '0xf99dEd500454129B5Fe249B8A54a8D464C45075c'.lower()

query = """
query CheckData($addr: Bytes!) {
  deposits(first: 5, where: { strategy: $addr }) {
    id
    timestamp
    assets
  }
  strategySnapshots(first: 5, where: { strategy: $addr }) {
     id
     timestamp
     aum
  }
}
"""

print(f"Checking Strategy Address: {strategy_address}")
try:
    r = requests.post(url, json={'query': query, 'variables': {'addr': strategy_address}})
    print("Response Strategy Address:", r.text)
except Exception as e:
    print(f"Error: {e}")

print(f"\nChecking Pool Address: {pool_address}")
try:
    r = requests.post(url, json={'query': query, 'variables': {'addr': pool_address}})
    print("Response Pool Address:", r.text)
except Exception as e:
    print(f"Error: {e}")
