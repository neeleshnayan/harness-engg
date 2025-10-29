"""
Check MAVC vault state to diagnose withdrawal issue
"""
import os
from web3 import Web3
from dotenv import load_dotenv
import json

load_dotenv("KryptonPay_Backend/.env")

RPC_URL = os.getenv("ETHEREUM_RPC_URL", "https://rpc.ankr.com/eth_sepolia")
VAULT_ADDRESS = "0xb3975b4294ed871013d2B47ADe5da9015Df5C54a"
WALLET_ADDRESS = "0xe4745d11f15918f4b2c4d86c6e518d929ac8cd81"

w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Minimal ABI for the functions we need
VAULT_ABI = [
    {"inputs": [], "name": "totalSupply", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "totalAssets", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
]

vault = w3.eth.contract(address=Web3.to_checksum_address(VAULT_ADDRESS), abi=VAULT_ABI)

print("="*80)
print("MAVC Vault State Diagnosis")
print("="*80)
print(f"Vault Address: {VAULT_ADDRESS}")
print(f"Wallet Address: {WALLET_ADDRESS}")
print(f"Network: Sepolia")
print("="*80)

try:
    total_supply = vault.functions.totalSupply().call()
    total_assets = vault.functions.totalAssets().call()
    wallet_balance = vault.functions.balanceOf(Web3.to_checksum_address(WALLET_ADDRESS)).call()

    print(f"\nVault Totals:")
    print(f"  Total Supply: {total_supply} ({total_supply / 1e6:.6f} MAVC)")
    print(f"  Total Assets: {total_assets} ({total_assets / 1e6:.6f} USDC)")

    print(f"\nWallet Balance:")
    print(f"  MAVC Balance: {wallet_balance} ({wallet_balance / 1e6:.6f} MAVC)")

    print(f"\nCalculation Test:")
    shares_to_redeem = 1370000  # 1.37 MAVC
    print(f"  Trying to redeem: {shares_to_redeem} ({shares_to_redeem / 1e6:.6f} MAVC)")

    if total_supply > 0:
        calculated_assets = (shares_to_redeem * total_assets) // total_supply
        print(f"  Would receive: {calculated_assets} ({calculated_assets / 1e6:.6f} USDC)")

        if calculated_assets == 0:
            print(f"\n❌ PROBLEM: Calculation returns 0!")
            print(f"   shares_to_redeem * total_assets = {shares_to_redeem * total_assets}")
            print(f"   divided by total_supply = {total_supply}")
            print(f"   Result: {shares_to_redeem * total_assets / total_supply}")

            # Calculate minimum shares needed
            if total_assets > 0:
                min_shares = (total_supply + total_assets - 1) // total_assets
                print(f"\n   Minimum shares needed for non-zero withdrawal: {min_shares} ({min_shares / 1e6:.6f} MAVC)")
        else:
            print(f"  ✅ Calculation would succeed!")
    else:
        print(f"  ❌ Total supply is 0!")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
