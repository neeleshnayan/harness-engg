#!/bin/bash

# Script to update MAVC price on Sepolia testnet
# Usage: ./update-price.sh

VAULT_ADDRESS="0x3329f1cb19AA1A58f4ff4Bbef7a7C94f07953118"
RPC_URL="sepolia"

echo "🔄 Updating MAVC price on vault: $VAULT_ADDRESS"
echo ""

# Call updateMAVCPrice() function
cast send $VAULT_ADDRESS \
  "updateMAVCPrice()" \
  --rpc-url $RPC_URL \
  --private-key $PRIVATE_KEY \
  --legacy

echo ""
echo "✅ Price update transaction sent!"
echo "🔍 The subgraph will automatically index the MAVCPriceUpdated event"
echo "📊 Check the frontend in ~1 minute to see the updated price"
