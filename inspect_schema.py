import requests
import json

url = 'https://api.studio.thegraph.com/query/1714038/krypton-liquidity-pools-sepolia/version/latest'

query = """
query {
  __schema {
    types {
      name
      fields {
        name
      }
    }
  }
}
"""

try:
    r = requests.post(url, json={'query': query})
    data = r.json()
    types = data.get('data', {}).get('__schema', {}).get('types', [])
    
    # Filter for interesting types
    print("Found Types:")
    for t in types:
        name = t.get('name', '')
        if not name.startswith('__') and not name in ['String', 'Boolean', 'Int', 'ID', 'Bytes', 'BigInt', 'BigDecimal']:
            print(f"- {name}")
            fields = t.get('fields')
            if fields:
               field_names = [f['name'] for f in fields[:5]]
               print(f"  Fields: {field_names}...")

except Exception as e:
    print(f"Error: {e}")
