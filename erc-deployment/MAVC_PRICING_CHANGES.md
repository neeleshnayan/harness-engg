# MAVC Token Pricing Implementation

## Overview
Modified `MultiAssetVaultUSDCWETH.sol` to implement Chainlink oracle-based pricing for MAVC token minting and redemption.

## Formula
**1 MAVC = 0.005 × USDC_price + 0.005 × WETH_price**

Where:
- USDC_price: Chainlink USDC/USD price feed (8 decimals)
- WETH_price: Chainlink ETH/USD price feed (8 decimals)
- Result: MAVC price in USD (8 decimals)

## Changes Made

### 1. ChainlinkPriceOracle.sol
- Added USDC price feed: `0xA2F78ab2355fe2f984D808B5CeE7FD0A93D5270E`
- Added ETH price feed: `0x694AA1769357215DE4FAC081bf1f309aDC325306`
- Added convenience methods: `getUsdcPrice()` and `getEthPrice()`

### 2. MultiAssetVaultUSDCWETH.sol
- Added `PRICE_ORACLE` immutable reference
- Updated constructor to accept `_priceOracle` parameter
- Implemented `_calculateShares(uint256 assets)` - converts USDC to MAVC shares using oracle prices
- Implemented `_calculateAssets(uint256 shares)` - converts MAVC shares to USDC using oracle prices
- Added `getMAVCPrice()` - public function to query current MAVC price in USD
- Modified `deposit()` to use `_calculateShares()`
- Modified `withdraw()` to use `_calculateShares()` and `_calculateAssets()`
- Modified `redeem()` to use `_calculateAssets()`

### 3. Test Scripts Updated
- `test/TestVaultWithChainlink.s.sol` - Updated to pass price oracle to vault constructor
- `test/TestVaultWithWorkingSwap.s.sol` - Updated to deploy and pass price oracle
- Added `testMAVCPrice()` function to display MAVC pricing in tests

## Math Breakdown

### Share Calculation (Deposit)
```solidity
// Get prices from Chainlink (8 decimals)
usdcPriceUSD = PRICE_ORACLE.getUsdcPrice()  // e.g., 100000000 ($1.00)
ethPriceUSD = PRICE_ORACLE.getEthPrice()    // e.g., 200000000000 ($2000.00)

// Calculate MAVC price: 0.005 * USDC + 0.005 * ETH
mavcPriceUSD = (5 * usdcPriceUSD / 1000) + (5 * ethPriceUSD / 1000)
// = (5 * 100000000 / 1000) + (5 * 200000000000 / 1000)
// = 500000 + 1000000000
// = 1000500000 (8 decimals) = $10.005

// Convert assets (6 decimals) to shares (18 decimals)
shares = (assets * 1e8 * 1e18) / (mavcPriceUSD * 1e6)

// Example: 100 USDC deposit
// shares = (100000000 * 1e8 * 1e18) / (1000500000 * 1e6)
// shares = 9.995... * 1e18 MAVC tokens
```

### Asset Calculation (Redeem)
```solidity
// Inverse calculation
assets = (shares * mavcPriceUSD * 1e6) / (1e8 * 1e18)

// Example: Redeem 10 MAVC
// assets = (10e18 * 1000500000 * 1e6) / (1e8 * 1e18)
// assets = 100.05 * 1e6 = 100.05 USDC
```

## Key Features
- Real-time oracle pricing for fair share valuation
- Decimal handling: USDC (6), WETH (18), MAVC (18), Prices (8)
- Price staleness checks via Chainlink oracle
- Transparent pricing via `getMAVCPrice()` public function

## Testing
Run the test script to see MAVC pricing in action:
```bash
forge script test/TestVaultWithChainlink.s.sol --rpc-url sepolia --broadcast
```

The test will display:
- Real-time USDC and ETH prices from Chainlink
- Calculated MAVC price
- Share amounts minted for deposits
- Asset amounts returned for redemptions

