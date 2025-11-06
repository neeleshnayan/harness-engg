#!/bin/bash

# Script to update MAVP price on Sepolia testnet
# Usage: ./update-mavp-price.sh

VAULT_ADDRESS="0x26C3a3635431aB9FB447c63A64909433bF9Bd5C1"
RPC_URL="sepolia"

if [ -z "$PRIVATE_KEY" ]; then
  echo "❌ Error: PRIVATE_KEY environment variable not set"
  exit 1
fi

echo "🔄 Updating MAVP strategy price on vault: $VAULT_ADDRESS"
echo ""

# Call updateStrategyPrice() function
cast send $VAULT_ADDRESS \
  "updateStrategyPrice()" \
  --rpc-url $RPC_URL \
  --private-key $PRIVATE_KEY \
  --legacy

echo ""
echo "✅ Price update transaction sent!"
echo "🔍 The subgraph will automatically index the StrategyPriceUpdated event"
echo "📊 Check the subgraph in ~1 minute to see the updated price"
