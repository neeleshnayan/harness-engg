"""
Quick script to test withdrawal endpoint and see all debug info
Run this while your backend is running to see the detailed address logs
"""

import requests
import json

# Configuration
BACKEND_URL = "http://localhost:8000"  # Adjust if your backend runs on a different port
USER_ID = "YOUR_USER_ID_HERE"  # Replace with actual user ID
WALLET_ADDRESS = "YOUR_WALLET_ADDRESS_HERE"  # Replace with actual wallet address
AMOUNT = "0.01"  # Small test amount

def test_withdrawal():
    """Test the withdrawal endpoint and display response"""

    print("=" * 80)
    print("🧪 Testing MAVC Withdrawal Endpoint")
    print("=" * 80)

    payload = {
        "amount": AMOUNT,
        "wallet_address": WALLET_ADDRESS,
        "user_id": USER_ID
    }

    print("\n📤 Request Payload:")
    print(json.dumps(payload, indent=2))

    try:
        print("\n🌐 Sending request to backend...")
        response = requests.post(
            f"{BACKEND_URL}/api/v1/mavc/withdraw",
            json=payload,
            timeout=30
        )

        print(f"\n📨 Response Status Code: {response.status_code}")
        print("\n📨 Response Body:")
        print(json.dumps(response.json(), indent=2))

        if response.status_code == 200:
            print("\n✅ Withdrawal request successful!")
            print("\n🔍 Check your backend terminal for detailed logs showing:")
            print("   - Destination wallet address")
            print("   - Circle wallet address")
            print("   - Transaction parameters")
            print("   - Circle API response")
        else:
            print("\n❌ Withdrawal request failed!")

    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to backend!")
        print("   Make sure backend is running:")
        print("   cd KryptonPay_Backend")
        print("   uvicorn app.main:app --reload")
    except Exception as e:
        print(f"\n❌ Error: {e}")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    # Check if user has configured the script
    if USER_ID == "YOUR_USER_ID_HERE" or WALLET_ADDRESS == "YOUR_WALLET_ADDRESS_HERE":
        print("⚠️  Please edit this script and set:")
        print("   - USER_ID: Your user ID from localStorage")
        print("   - WALLET_ADDRESS: Your wallet address")
        print("   - AMOUNT: Test amount (keep it small!)")
        print("\nYou can find these in browser console:")
        print("   JSON.parse(localStorage.getItem('userData'))")
    else:
        test_withdrawal()
