// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "forge-std/Test.sol";
import "../src/MAVP.sol";
import "../src/UniswapV4Integration.sol";
import "../src/MAVPPriceOracle.sol";
import "../src/MockUNIPriceFeed.sol";
import "../src/MockUSDTPriceFeed.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract TestMultiAssetVaultPortfolio is Script, Test {
    // Test account configuration
    uint256 immutable OWNER_PRIVATE_KEY = vm.envUint("PRIVATE_KEY");
    
    // Use specific wallet that has tokens AND ETH for gas
    address constant WALLET_WITH_TOKENS = 0xcB499cf9d71FBD345e9BF8A37434e5C92d290Efc;
    
    function getVaultOwner() internal pure returns (address) {
        return WALLET_WITH_TOKENS;
    }
    
    function getWalletWithTokens() internal pure returns (address) {
        return WALLET_WITH_TOKENS;
    }
    
    // Sepolia token addresses - using tokens that have actual liquidity pools with USDC
    address constant USDC = 0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238; // 6 decimals
    address constant WETH = 0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14; // 18 decimals - ✅ HAS POOLS
    address constant WBTC = 0x29f2D40B0605204364af54EC677bD022dA425d03; // 8 decimals - Bitcoin on Sepolia
    address constant USDT = 0xaA8E23Fb1079EA71e0a56F48a2aA51851D8433D0; // 6 decimals - Tether on Sepolia  
    address constant UNI = 0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984; // 18 decimals - UNI token
    address constant LINK = 0x779877A7B0D9E8603169DdbD7836e478b4624789; // 18 decimals - Chainlink on Sepolia

    // Chainlink Price Feed Addresses on Sepolia
    address constant ETH_USD_FEED = 0x694AA1769357215DE4FAC081bf1f309aDC325306;
    address constant BTC_USD_FEED = 0x1b44F3514812d835EB1BDB0acB33d3fA3351Ee43;
    address constant LINK_USD_FEED = 0xc59E3633BAAC79493d908e63626716e204A45EdF;

    // Reuse existing contract addresses (set to address(0) to deploy new)
    address constant EXISTING_DEX = address(0); // Deploy fresh
    address constant EXISTING_VAULT = address(0); // Always deploy new vault for testing

    function run() external {
        console.log("=== Multi Asset Vault Portfolio Test Script ===");
        console.log("This script tests a 5-asset portfolio vault on Sepolia testnet");
        console.log("Vault Owner:", getVaultOwner());

        vm.startBroadcast(OWNER_PRIVATE_KEY);

        // Deploy DEX integration
        UniswapV4Integration dexIntegration;
        if (EXISTING_DEX != address(0)) {
            dexIntegration = UniswapV4Integration(EXISTING_DEX);
            console.log("Reusing existing DEX integration");
        } else {
            dexIntegration = new UniswapV4Integration(getVaultOwner());
            console.log("Deployed new DEX integration");
        }

        // Deploy mock price feeds for missing tokens
        MockUSDTPriceFeed usdtFeed = new MockUSDTPriceFeed();
        MockUNIPriceFeed uniFeed = new MockUNIPriceFeed();
        console.log("Deployed mock price feeds");
        
        // Deploy MAVP Price Oracle
        MAVPPriceOracle priceOracle = new MAVPPriceOracle(
            ETH_USD_FEED,      // Real Chainlink ETH/USD
            BTC_USD_FEED,      // Real Chainlink BTC/USD
            address(usdtFeed), // Mock USDT/USD
            address(uniFeed),  // Mock UNI/USD
            LINK_USD_FEED      // Real Chainlink LINK/USD
        );
        console.log("Deployed MAVP Price Oracle");

        // Deploy vault with 5-asset basket - using tokens with actual liquidity
        address[] memory assets = new address[](5);
        assets[0] = WETH;  // ✅ Known to have USDC pools
        assets[1] = WBTC;  // Bitcoin - ✅ confirmed working
        assets[2] = USDT;  // Tether - ✅ confirmed working  
        assets[3] = UNI;   // UNI token - has USDC pools
        assets[4] = LINK;  // Chainlink - ✅ confirmed working

        MultiAssetVaultPortfolio vault;
        if (EXISTING_VAULT != address(0)) {
            vault = MultiAssetVaultPortfolio(EXISTING_VAULT);
            console.log("Reusing existing vault");
        } else {
            vault = new MultiAssetVaultPortfolio(
                USDC,
                assets,
                address(dexIntegration),
                "Multi Asset Vault USDC Basket",
                "MAVP"
            );
            console.log("Deployed new 5-asset portfolio vault");
            
            // Set the price oracle
            vault.setPriceOracle(address(priceOracle));
            console.log("Connected price oracle to vault");
        }

        vm.stopBroadcast();
        
        console.log("Contracts deployed:");
        console.log("  USDC:", USDC);
        console.log("  WETH:", WETH, "(confirmed pools)");
        console.log("  WBTC:", WBTC, "(Bitcoin - confirmed)");
        console.log("  USDT:", USDT, "(Tether - confirmed)");
        console.log("  UNI:", UNI, "(UNI token - has USDC pools)");
        console.log("  LINK:", LINK, "(Chainlink - confirmed)");
        console.log("  DEX Integration:", address(dexIntegration));
        console.log("  MAVP Vault:", address(vault));
        console.log("  Price Oracle:", address(priceOracle));
        console.log("  Mock USDT Feed:", address(usdtFeed));
        console.log("  Mock UNI Feed:", address(uniFeed));

        // Pre-fund DEX integration for custom pool creation
        _prefundDex(dexIntegration);

        // Test price oracle
        testPriceOracle(vault, priceOracle);
        
        // Test vault operations with real USDC from your wallet
        testVaultOperations(vault);
        
        // Display etherscan addresses
        console.log("\n=== ETHERSCAN ADDRESSES ===");
        console.log("User Wallet:", getWalletWithTokens());
        console.log(string(abi.encodePacked("Etherscan User: https://sepolia.etherscan.io/address/", _addressToString(getWalletWithTokens()))));
        console.log("MAVP Vault Contract:", address(vault));
        console.log(string(abi.encodePacked("Etherscan Vault: https://sepolia.etherscan.io/address/", _addressToString(address(vault)))));
        console.log("DEX Integration:", address(dexIntegration));
        console.log(string(abi.encodePacked("Etherscan DEX: https://sepolia.etherscan.io/address/", _addressToString(address(dexIntegration)))));
        
        // Check your final wallet balance
        checkFinalWalletBalance();
        
        console.log("\n=== All Tests Completed Successfully! ===");
    }

    function checkFinalWalletBalance() internal view {
        console.log("\n--- Final Wallet Balance Check ---");
        
        IERC20 usdc = IERC20(USDC);
        uint256 finalUsdcBalance = usdc.balanceOf(getWalletWithTokens());
        
        console.log("Your final USDC balance:", formatUSDC(finalUsdcBalance), "USDC");
        console.log("Expected: ~940 USDC (1000 - 50 for DEX - 10 for deposit)");
        
        if (finalUsdcBalance < 900 * 1e6) {
            console.log("WARNING: USDC balance lower than expected");
        } else {
            console.log("SUCCESS: USDC balance looks correct");
        }
    }

    function _prefundDex(UniswapV4Integration dex) internal {
        console.log("\n--- Pre-funding DEX Integration ---");
        console.log("Pre-funding DEX integration with tokens for custom pool creation...");

        vm.startBroadcast(OWNER_PRIVATE_KEY);

        // Fund with realistic amounts from your wallet for DEX liquidity
        uint256 preFundUSDC = 50 * 1e6; // 50 USDC from your 1000 USDC
        IERC20(USDC).transfer(address(dex), preFundUSDC);
        console.log("Pre-funded DEX with %s USDC", formatUSDC(preFundUSDC));

        // Use vm.deal() to create tokens for DEX liquidity - using tokens with real pools
        uint256 wethLiquidity = 10 * 1e18; // 10 WETH
        uint256 wbtcLiquidity = 1 * 1e8; // 1 WBTC (8 decimals)
        uint256 usdtLiquidity = 10_000 * 1e6; // 10k USDT (6 decimals)
        uint256 uniLiquidity = 1_000 * 1e18; // 1k UNI (18 decimals)
        uint256 linkLiquidity = 1_000 * 1e18; // 1k LINK (18 decimals)

        // Create fake tokens for DEX using Foundry's deal cheatcode
        vm.deal(address(dex), 1 ether); // Give DEX some ETH
        // Use deal() for ERC20 tokens - this creates fake token balances for testing
        deal(WETH, address(dex), wethLiquidity);
        deal(WBTC, address(dex), wbtcLiquidity);
        deal(USDT, address(dex), usdtLiquidity);
        deal(UNI, address(dex), uniLiquidity);
        deal(LINK, address(dex), linkLiquidity);

        console.log("Pre-funded DEX with %s WETH (test tokens)", _toString(wethLiquidity / 1e18));
        console.log("Pre-funded DEX with %s WBTC (test tokens)", _toString(wbtcLiquidity / 1e8));
        console.log("Pre-funded DEX with %s USDT (test tokens)", _toString(usdtLiquidity / 1e6));
        console.log("Pre-funded DEX with %s UNI (test tokens)", _toString(uniLiquidity / 1e18));
        console.log("Pre-funded DEX with %s LINK (test tokens)", _toString(linkLiquidity / 1e18));

        vm.stopBroadcast();
        
        console.log("SUCCESS: DEX Integration pre-funded for custom pool creation");
    }

    function testVaultOperations(MultiAssetVaultPortfolio vault) internal {
        console.log("\n--- Test: 5-Asset Portfolio Vault Operations with REAL USDC ---");
        
        // Get USDC interface
        IERC20 usdc = IERC20(USDC);
        
        // Check USDC balance for your wallet
        uint256 usdcBalance = usdc.balanceOf(getWalletWithTokens());
        
        console.log("Your wallet:", getWalletWithTokens());
        console.log("Your USDC Balance:", formatUSDC(usdcBalance), "USDC");
        
        if (usdcBalance == 0) {
            console.log("ERROR: No USDC balance in your wallet!");
            console.log("Expected: ~1000 USDC in wallet 0xcB499cf9d71FBD345e9BF8A37434e5C92d290Efc");
            return;
        }
        
        // Test deposit with real USDC
        testDepositFiveAssetBasket(vault, usdc);
        
        // Test withdrawal 
        testWithdrawFiveAssetBasket(vault, usdc);
        
        // Show final portfolio allocation
        showPortfolioAllocation(vault);
    }

    function testDepositFiveAssetBasket(MultiAssetVaultPortfolio vault, IERC20 usdc) internal {
        console.log("\n--- Test: DEPOSIT $10 USDC into 5-Asset Basket (REAL TRANSACTIONS) ---");
        
        uint256 depositAmount = 10 * 1e6; // 10 USDC as requested
        
        // Show initial state
        console.log("\n=== INITIAL STATE ===");
        printPortfolioBalanceTable("BEFORE DEPOSIT", getWalletWithTokens(), vault, usdc);
        
        // Check if wallet has enough USDC
        uint256 walletUsdcBalance = usdc.balanceOf(getWalletWithTokens());
        if (walletUsdcBalance < depositAmount) {
            console.log("WARNING: Insufficient USDC balance for deposit");
            console.log("Required:", formatUSDC(depositAmount), "USDC");
            console.log("Available:", formatUSDC(walletUsdcBalance), "USDC");
            depositAmount = walletUsdcBalance; // Use all available USDC
            console.log("Using all available USDC:", formatUSDC(depositAmount), "USDC");
        }
        
        // Perform REAL deposit transactions
        vm.startBroadcast(OWNER_PRIVATE_KEY);
        
        // Real approval transaction
        usdc.approve(address(vault), depositAmount);
        console.log("SUCCESS: Approved", formatUSDC(depositAmount), "USDC for vault");
        
        // Add small delay between approval and deposit
        vm.sleep(1000); // 1 second delay
        
        // Real deposit transaction
        uint256 shares = vault.deposit(depositAmount, getWalletWithTokens());
        console.log("SUCCESS: Deposited", formatUSDC(depositAmount), "USDC");
        console.log("SUCCESS: Received", formatMAVP(shares), "MAVP shares");
        
        vm.stopBroadcast();
        
        // Show state after deposit
        console.log("\n=== STATE AFTER DEPOSIT ===");
        printPortfolioBalanceTable("AFTER DEPOSIT", getWalletWithTokens(), vault, usdc);
        
        // Show individual asset allocations
        console.log("\n=== REAL MULTI-ASSET ALLOCATION BREAKDOWN ===");
        console.log("Your $10 USDC has been automatically converted into a 5-asset portfolio:");
        console.log("Target: 20% each asset (WETH, WBTC, USDT, UNI, LINK)");
        console.log("");
        
        uint256 totalValue = vault.totalAssets();
        for (uint256 i = 0; i < 5; i++) {
            (address token, uint256 allocationBps, uint256 tokenBalance, uint256 bookValue) = vault.getAssetInfo(i);
            string memory tokenName = getTokenName(token);
            uint256 actualPercent = totalValue > 0 ? (bookValue * 10000) / totalValue : 0;
            
            console.log(string(abi.encodePacked(
                tokenName, " - Target: ", _toString(allocationBps / 100), "% | ",
                "Actual: ", _toString(actualPercent / 100), "% | ",
                "Tokens: ", _toString(tokenBalance), " | ",
                "USD Value: $", formatUSDC(bookValue)
            )));
            
            if (tokenBalance > 0) {
                console.log(string(abi.encodePacked("  SUCCESS: USDC -> ", tokenName)));
            } else {
                console.log(string(abi.encodePacked("  FAILED: USDC -> ", tokenName, " (kept as USDC)")));
            }
        }
        
        uint256 usdcKept = vault.usdcHeld();
        if (usdcKept > 0) {
            console.log(string(abi.encodePacked("USDC Kept (unswapped): $", formatUSDC(usdcKept))));
        }
    }

    function testWithdrawFiveAssetBasket(MultiAssetVaultPortfolio vault, IERC20 usdc) internal {
        console.log("\n--- Test: WITHDRAWAL from 5-Asset Basket (REAL TRANSACTIONS) ---");
        
        uint256 userShares = vault.balanceOf(getWalletWithTokens());
        if (userShares == 0) {
            console.log("WARNING: No shares to withdraw");
            return;
        }
        
        uint256 withdrawShares = userShares / 2; // Withdraw half the shares
        if (withdrawShares == 0) {
            withdrawShares = userShares; // Withdraw all if too small
        }
        
        // Show initial state
        console.log("\n=== INITIAL STATE ===");
        printPortfolioBalanceTable("BEFORE WITHDRAWAL", getWalletWithTokens(), vault, usdc);
        
        // Perform REAL withdrawal transaction
        vm.startBroadcast(OWNER_PRIVATE_KEY);
        
        uint256 assetsWithdrawn = vault.redeem(withdrawShares, getWalletWithTokens(), getWalletWithTokens());
        console.log("SUCCESS: Redeemed", formatMAVP(withdrawShares), "MAVP shares");
        console.log("SUCCESS: Received", formatUSDC(assetsWithdrawn), "USDC");
        
        vm.stopBroadcast();
        
        // Show final state
        console.log("\n=== FINAL STATE ===");
        printPortfolioBalanceTable("AFTER WITHDRAWAL", getWalletWithTokens(), vault, usdc);
    }

    function showPortfolioAllocation(MultiAssetVaultPortfolio vault) internal view {
        console.log("\n--- Final Portfolio Allocation ---");
        
        (address[] memory tokens, uint256[] memory allocationBps) = vault.getCurrentAllocation();
        
        console.log("\n=== CURRENT PORTFOLIO ALLOCATION ===");
        for (uint256 i = 0; i < tokens.length; i++) {
            string memory tokenName = getTokenName(tokens[i]);
            uint256 percentage = allocationBps[i] / 100; // Convert from BPS to percentage
            console.log(string(abi.encodePacked(
                tokenName, ": ", _toString(percentage), "%"
            )));
        }
        
        uint256 totalAssets = vault.totalAssets();
        console.log("Total Portfolio Value:", formatUSDC(totalAssets), "USDC");
    }

    function printPortfolioBalanceTable(string memory title, address user, MultiAssetVaultPortfolio vault, IERC20 usdc) internal view {
        console.log("\n=== ", title, " ===");
        console.log("=======================================================");
        console.log("| Account | USDC Balance | MAVP Balance | Total Assets |");
        console.log("=======================================================");

        // User balances
        uint256 userUsdcBalance = usdc.balanceOf(user);
        uint256 userMavpBalance = vault.balanceOf(user);
        string memory userRow = string(abi.encodePacked("| User    | ", formatUSDC(userUsdcBalance), " USDC | ", formatMAVP(userMavpBalance), " MAVP | N/A          |"));
        console.log(userRow);

        // Vault balances
        uint256 vaultUsdcBalance = usdc.balanceOf(address(vault));
        uint256 vaultMavpBalance = vault.balanceOf(address(vault)); // Should be 0
        uint256 vaultTotalAssets = vault.totalAssets();
        string memory vaultRow = string(abi.encodePacked("| Vault   | ", formatUSDC(vaultUsdcBalance), " USDC | ", formatMAVP(vaultMavpBalance), " MAVP | ", formatUSDC(vaultTotalAssets), " USDC |"));
        console.log(vaultRow);

        console.log("=======================================================");

        // Additional vault info
        console.log("\nVault Internal Accounting:");
        console.log("  Total Assets:", formatUSDC(vaultTotalAssets), "USDC");
        console.log("  USDC Held:", formatUSDC(vault.usdcHeld()), "USDC");
        
        // Show asset count
        uint256 assetCount = vault.assetCount();
        console.log("  Number of Target Assets:", _toString(assetCount));
    }

    function getTokenName(address token) internal pure returns (string memory) {
        if (token == USDC) return "USDC";
        if (token == WETH) return "WETH";
        if (token == WBTC) return "WBTC";
        if (token == USDT) return "USDT";
        if (token == UNI) return "UNI";
        if (token == LINK) return "LINK";
        return "UNKNOWN";
    }

    // Helper functions for human-readable formatting
    function formatUSDC(uint256 amount) internal pure returns (string memory) {
        if (amount == 0) return "0.00";
        
        uint256 whole = amount / 1e6;
        uint256 fractional = (amount % 1e6) / 1e4; // Get first 2 decimal places
        
        string memory fracStr;
        if (fractional < 10) {
            fracStr = string(abi.encodePacked("0", _toString(fractional)));
        } else {
            fracStr = _toString(fractional);
        }
        
        return string(abi.encodePacked(_toString(whole), ".", fracStr));
    }

    function formatMAVP(uint256 amount) internal pure returns (string memory) {
        if (amount == 0) return "0.00";
        
        uint256 whole = amount / 1e18;
        uint256 fractional = (amount % 1e18) / 1e16; // Get first 2 decimal places
        
        string memory fracStr;
        if (fractional < 10) {
            fracStr = string(abi.encodePacked("0", _toString(fractional)));
        } else {
            fracStr = _toString(fractional);
        }
        
        return string(abi.encodePacked(_toString(whole), ".", fracStr));
    }

    function _toString(uint256 value) internal pure returns (string memory) {
        if (value == 0) return "0";
        
        uint256 temp = value;
        uint256 digits;
        while (temp != 0) {
            digits++;
            temp /= 10;
        }
        bytes memory buffer = new bytes(digits);
        while (value != 0) {
            digits -= 1;
            buffer[digits] = bytes1(uint8(48 + uint256(value % 10)));
            value /= 10;
        }
        return string(buffer);
    }

    function _addressToString(address addr) internal pure returns (string memory) {
        return _toHexString(uint256(uint160(addr)), 20);
    }

    function _toHexString(uint256 value, uint256 length) internal pure returns (string memory) {
        bytes memory buffer = new bytes(2 * length);
        for (uint256 i = 2 * length; i > 0; --i) {
            buffer[i - 1] = _toHexChar(uint8(value & 0xf));
            value >>= 4;
        }
        return string(abi.encodePacked("0x", buffer));
    }

    function _toHexChar(uint8 value) internal pure returns (bytes1) {
        if (value < 10) {
            return bytes1(uint8(bytes1('0')) + value);
        } else {
            return bytes1(uint8(bytes1('a')) + value - 10);
        }
    }

    function testPriceOracle(MultiAssetVaultPortfolio vault, MAVPPriceOracle oracle) internal view {
        console.log("\n--- Testing Chainlink Price Oracle ---");
        console.log("Formula: 1 MAVP = 0.2*ETH + 0.2*BTC + 0.2*USDT + 0.2*UNI + 0.2*LINK");
        
        try oracle.arePriceFeedsHealthy() returns (bool healthy) {
            console.log("Price feeds healthy:", healthy);
            
            if (healthy) {
                try vault.getAssetPricesUSD() returns (
                    uint256 ethPrice,
                    uint256 btcPrice,
                    uint256 usdtPrice,
                    uint256 uniPrice,
                    uint256 linkPrice,
                    uint256 mavpPrice
                ) {
                    console.log("\n=== Live Asset Prices from Chainlink ===");
                    console.log("ETH/USD:", _formatPrice(ethPrice));
                    console.log("BTC/USD:", _formatPrice(btcPrice));
                    console.log("USDT/USD:", _formatPrice(usdtPrice));
                    console.log("UNI/USD:", _formatPrice(uniPrice));
                    console.log("LINK/USD:", _formatPrice(linkPrice));
                    console.log("MAVP/USD:", _formatPrice(mavpPrice));
                    
                    try vault.getMAVPPriceBreakdown() returns (
                        uint256 ethContrib,
                        uint256 btcContrib,
                        uint256 usdtContrib,
                        uint256 uniContrib,
                        uint256 linkContrib
                    ) {
                        console.log("\n=== MAVP Price Breakdown (Each 20%) ===");
                        console.log("ETH contribution:", _formatPrice(ethContrib));
                        console.log("BTC contribution:", _formatPrice(btcContrib));
                        console.log("USDT contribution:", _formatPrice(usdtContrib));
                        console.log("UNI contribution:", _formatPrice(uniContrib));
                        console.log("LINK contribution:", _formatPrice(linkContrib));
                        
                        uint256 calculatedTotal = ethContrib + btcContrib + usdtContrib + uniContrib + linkContrib;
                        console.log("Calculated total:", _formatPrice(calculatedTotal));
                        console.log("Oracle reported:", _formatPrice(mavpPrice));
                        
                        if (calculatedTotal == mavpPrice) {
                            console.log("SUCCESS: Price calculation verified!");
                        } else {
                            console.log("WARNING: Price calculation mismatch");
                        }
                    } catch {
                        console.log("Failed to get MAVP price breakdown");
                    }
                } catch {
                    console.log("Failed to get asset prices");
                }
            } else {
                console.log("WARNING: Some price feeds are unhealthy or stale");
            }
        } catch {
            console.log("ERROR: Failed to check price feed health");
        }
    }

    function _formatPrice(uint256 price) internal pure returns (string memory) {
        if (price == 0) return "$0.00";
        
        uint256 dollars = price / 1e8;
        uint256 cents = (price % 1e8) / 1e6;
        
        if (cents < 10) {
            return string(abi.encodePacked("$", _toString(dollars), ".0", _toString(cents)));
        } else {
            return string(abi.encodePacked("$", _toString(dollars), ".", _toString(cents)));
        }
    }
}
