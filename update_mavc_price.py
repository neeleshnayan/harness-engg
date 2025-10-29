"""
Update MAVC Price on the new contract
"""
import os
from web3 import Web3
from dotenv import load_dotenv

load_dotenv("KryptonPay_Backend/.env")

RPC_URL = os.getenv("ETHEREUM_RPC_URL", "https://eth-sepolia.g.alchemy.com/v2/M6S9rlQMfU-jEVs5scsDI")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
VAULT_ADDRESS = "0x09C2bB00E70e31Ec9bB1066BE63D0c58865476C5"  # NEW VAULT

w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Minimal ABI for updateMAVCPrice and getMAVCPrice
VAULT_ABI = [
    {"inputs": [], "name": "updateMAVCPrice", "outputs": [{"type": "uint256"}], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [], "name": "getMAVCPrice", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
]

vault = w3.eth.contract(address=Web3.to_checksum_address(VAULT_ADDRESS), abi=VAULT_ABI)

print("="*80)
print("Updating MAVC Price")
print("="*80)
print(f"Vault Address: {VAULT_ADDRESS}")
print(f"Network: Sepolia")

# Get account from private key
account = w3.eth.account.from_key(PRIVATE_KEY)
print(f"Calling from: {account.address}")

try:
    # Read current price first
    print("\n1. Reading current price...")
    current_price = vault.functions.getMAVCPrice().call()
    print(f"   Current MAVC Price: {current_price} ({current_price / 1e8:.4f} USD)")

    # Update price
    print("\n2. Calling updateMAVCPrice()...")
    tx = vault.functions.updateMAVCPrice().build_transaction({
        'from': account.address,
        'nonce': w3.eth.get_transaction_count(account.address),
        'gas': 200000,
        'gasPrice': w3.eth.gas_price,
    })

    # Sign and send transaction
    signed_tx = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    print(f"   Transaction sent: {tx_hash.hex()}")
    print(f"   Etherscan: https://sepolia.etherscan.io/tx/{tx_hash.hex()}")

    # Wait for receipt
    print("   Waiting for confirmation...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    if receipt['status'] == 1:
        print("   ✅ Transaction confirmed!")

        # Read new price
        new_price = vault.functions.getMAVCPrice().call()
        print(f"\n3. New MAVC Price: {new_price} ({new_price / 1e8:.4f} USD)")
        print("="*80)
        print("✅ SUCCESS! MAVC price has been updated!")
        print("="*80)
    else:
        print("   ❌ Transaction failed!")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
