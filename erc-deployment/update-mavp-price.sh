#!/bin/bash

# Script to update MAVP price on Sepolia testnet
# Usage: ./update-mavp-price.sh

VAULT_ADDRESS="0x23FD6333F573D6D1ac5A5bF587CCEadA24D1008d"
RPC_URL="https://eth-sepolia.api.onfinality.io/rpc?apikey=507637d5-66a9-43a1-b97b-93c27b72f0dd"

echo "🔄 Updating MAVP price on vault: $VAULT_ADDRESS"
echo ""

# Call updateMAVPPrice() function
cast send $VAULT_ADDRESS \
  "updateMAVPPrice()" \
  --rpc-url $RPC_URL \
  --private-key $PRIVATE_KEY \
  --legacy

echo ""
echo "✅ Price update transaction sent!"
echo "🔍 The subgraph will automatically index the MAVPPriceUpdated event"
echo "📊 Check the frontend in ~1 minute to see the updated price"
