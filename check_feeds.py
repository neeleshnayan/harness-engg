from web3 import Web3
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv("KryptonPay_Backend/.env")
w3 = Web3(Web3.HTTPProvider(os.getenv("ETHEREUM_RPC_URL")))

oracle_addr = "0x30c3DCa9195E4dAe39d33Fa051cADdB5E4c8d7cf"

oracle_abi = [
    {"inputs": [], "name": "ethUsdFeed", "outputs": [{"name": "", "type": "address"}], "type": "function"},
    {"inputs": [], "name": "btcUsdFeed", "outputs": [{"name": "", "type": "address"}], "type": "function"},
    {"inputs": [], "name": "usdtUsdFeed", "outputs": [{"name": "", "type": "address"}], "type": "function"},
    {"inputs": [], "name": "uniUsdFeed", "outputs": [{"name": "", "type": "address"}], "type": "function"},
    {"inputs": [], "name": "linkUsdFeed", "outputs": [{"name": "", "type": "address"}], "type": "function"},
]

oracle = w3.eth.contract(address=Web3.to_checksum_address(oracle_addr), abi=oracle_abi)

feeds = {
    "ETH/USD": {"address": oracle.functions.ethUsdFeed().call(), "heartbeat": 86400},
    "BTC/USD": {"address": oracle.functions.btcUsdFeed().call(), "heartbeat": 86400},
    "USDT/USD": {"address": oracle.functions.usdtUsdFeed().call(), "heartbeat": 86400},
    "UNI/USD": {"address": oracle.functions.uniUsdFeed().call(), "heartbeat": 172800},
    "LINK/USD": {"address": oracle.functions.linkUsdFeed().call(), "heartbeat": 172800},
}

chainlink_abi = [
    {
        "inputs": [],
        "name": "latestRoundData",
        "outputs": [
            {"name": "roundId", "type": "uint80"},
            {"name": "answer", "type": "int256"},
            {"name": "startedAt", "type": "uint256"},
            {"name": "updatedAt", "type": "uint256"},
            {"name": "answeredInRound", "type": "uint80"}
        ],
        "type": "function"
    }
]

current_time = w3.eth.get_block('latest')['timestamp']
print("="*80)
print(f"Current time: {datetime.fromtimestamp(current_time)}")
print("="*80)

stale_feeds = []

for name, config in feeds.items():
    print(f"\n📊 {name} - {config['address']}")
    
    try:
        feed = w3.eth.contract(address=Web3.to_checksum_address(config['address']), abi=chainlink_abi)
        round_data = feed.functions.latestRoundData().call()
        round_id, price, started_at, updated_at, answered_in_round = round_data
        
        age_seconds = current_time - updated_at
        age_hours = age_seconds / 3600
        heartbeat_hours = config['heartbeat'] / 3600
        is_stale = age_seconds > config['heartbeat']
        
        print(f"   Price: ${price / 1e8:.2f}")
        print(f"   Updated: {datetime.fromtimestamp(updated_at)}")
        print(f"   Age: {age_hours:.1f} hours (limit: {heartbeat_hours:.1f} hours)")
        
        if is_stale:
            excess = (age_seconds - config['heartbeat']) / 3600
            print(f"   ❌ STALE by {excess:.1f} hours!")
            stale_feeds.append(name)
        else:
            remaining = (config['heartbeat'] - age_seconds) / 3600
            print(f"   ✅ FRESH ({remaining:.1f}h remaining)")
            
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        stale_feeds.append(name)

print("\n" + "="*80)
if stale_feeds:
    print(f"🚨 STALE FEEDS: {', '.join(stale_feeds)}")
    print("\n💡 UPDATE COMMANDS:")
    for feed in stale_feeds:
        if "USDT" in feed:
            print(f"   cast send {feeds[feed]['address']} 'simulatePriceMovement()' --rpc-url sepolia --private-key $PRIVATE_KEY --legacy")
        elif "UNI" in feed:
            print(f"   cast send {feeds[feed]['address']} 'simulatePriceMovement()' --rpc-url sepolia --private-key $PRIVATE_KEY --legacy")
else:
    print("✅ All feeds fresh!")
print("="*80)

