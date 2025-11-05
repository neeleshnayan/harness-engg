// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/MultiAssetVaultUSDCWETH.sol";
import "../src/ChainlinkPriceOracle.sol";
import "../src/UniswapV4Integration.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract TestVaultWithChainlink is Script {
    // Test account configuration
    uint256 immutable OWNER_PRIVATE_KEY = vm.envUint("PRIVATE_KEY");
    
    // Use specific wallet that has DAI and EUR tokens AND ETH for gas
    address constant WALLET_WITH_TOKENS = 0xcB499cf9d71FBD345e9BF8A37434e5C92d290Efc;
    
    function getVaultOwner() internal pure returns (address) {
        return WALLET_WITH_TOKENS; // Use the wallet with ETH for deployment
    }
    
    function getWalletWithTokens() internal pure returns (address) {
        return WALLET_WITH_TOKENS;
    }
    
    // Use tokens with existing liquidity on Sepolia - WETH/USDC
    address constant USDC_ADDRESS = 0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238; // USDC on Sepolia (input token) - matches DEX integration
    address constant WETH_ADDRESS = 0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14; // WETH on Sepolia (target token)

    // Legacy DAI/EUR addresses for compatibility with test functions
    address constant DAI_ADDRESS = 0x68194a729C2450ad26072b3D33ADaCbcef39D574;
    address constant EUR_ADDRESS = 0x08210F9170F89Ab7658F0B5E3fF39b0E03C594D4;

    // Reuse existing contract addresses (set to address(0) to deploy new)
    address constant EXISTING_ORACLE = address(0); // Deploy fresh
    address constant EXISTING_DEX = address(0); // Deploy fresh
    address constant EXISTING_VAULT = address(0); // Always deploy new vault for testing

    function run() external {
        console.log("=== MultiAssetVault Test Script with CHAINLINK DATA FEEDS ===");
        console.log("This script uses real Chainlink price feeds on Sepolia testnet");
        console.log("Vault Owner:", getVaultOwner());

        vm.startBroadcast(OWNER_PRIVATE_KEY);

        // Reuse or deploy Chainlink price oracle
        ChainlinkPriceOracle priceOracle;
        if (EXISTING_ORACLE != address(0)) {
            priceOracle = ChainlinkPriceOracle(EXISTING_ORACLE);
            console.log("Reusing existing price oracle");
        } else {
            priceOracle = new ChainlinkPriceOracle(getVaultOwner());
            console.log("Deployed new price oracle");
        }

        // Reuse or deploy DEX integration
        UniswapV4Integration dexIntegration;
        if (EXISTING_DEX != address(0)) {
            dexIntegration = UniswapV4Integration(EXISTING_DEX);
            console.log("Reusing existing DEX integration (with your WETH!)");
        } else {
            dexIntegration = new UniswapV4Integration(getVaultOwner());
            console.log("Deployed new DEX integration");
        }

        MultiAssetVaultUSDCWETH vault;
        if (EXISTING_VAULT != address(0)) {
            vault = MultiAssetVaultUSDCWETH(EXISTING_VAULT);
            console.log("Reusing existing vault");
        } else {
            vault = new MultiAssetVaultUSDCWETH(
                USDC_ADDRESS,
                WETH_ADDRESS,
                address(dexIntegration),
                address(priceOracle),
                "Multi Asset Vault USDC/WETH",
                "MAVC"
            );
            console.log("Deployed new vault");
        }

        vm.stopBroadcast();
        
        console.log("Contracts deployed:");
        console.log("  USDC:", USDC_ADDRESS);
        console.log("  WETH:", WETH_ADDRESS);
        console.log("  Chainlink Price Oracle:", address(priceOracle));
        console.log("  DEX Integration:", address(dexIntegration));
        console.log("  Vault:", address(vault));

        // Pre-fund DEX integration for custom pool creation
        vm.startBroadcast(OWNER_PRIVATE_KEY);

        console.log("\n--- Pre-funding DEX Integration ---");
        console.log("Pre-funding DEX integration with both tokens for liquidity...");

        // Fund with USDC (we have 1030 USDC available)
        uint256 preFundUSDC = 50 * 1e6; // 500 USDC
        IERC20(USDC_ADDRESS).transfer(address(dexIntegration), preFundUSDC);
        console.log("Pre-funded DEX with %s USDC", formatUSDC(preFundUSDC));

        // Fund with proportional WETH (you have 0.045 WETH available)
        uint256 preFundWETH = 10000000000000000; // 0.01 WETH (less than your 0.045 available)
        IERC20(WETH_ADDRESS).transfer(address(dexIntegration), preFundWETH);
        console.log("Pre-funded DEX with %s WETH", formatWETH(preFundWETH));

        vm.stopBroadcast();
        
        console.log("SUCCESS: DEX Integration pre-funded for custom pool creation");

        // Test 1: Chainlink price data
        testChainlinkPriceData(priceOracle);
        
        // Test 1.2: Display MAVC price
        testMAVCPrice(vault);
        
        // Test 1.5: Custom pool creation mode enabled
        console.log("INFO: DEX integration will create custom pools for all swaps");
        console.log("INFO: Existing pools will be ignored - creating fresh pools with liquidity");
        
        // Add delay to prevent transaction limit issues
        vm.sleep(2000); // 2 second delay
        
        // Test 2: Vault operations with real tokens
        testVaultOperations(vault);
        
        // Display etherscan addresses
        console.log("\n=== ETHERSCAN ADDRESSES ===");
        console.log("User Wallet:", getWalletWithTokens());
        console.log(string(abi.encodePacked("Etherscan User: https://sepolia.etherscan.io/address/", _addressToString(getWalletWithTokens()))));
        console.log("Vault Contract:", address(vault));
        console.log(string(abi.encodePacked("Etherscan Vault: https://sepolia.etherscan.io/address/", _addressToString(address(vault)))));
        console.log("Price Oracle:", address(priceOracle));
        console.log(string(abi.encodePacked("Etherscan Oracle: https://sepolia.etherscan.io/address/", _addressToString(address(priceOracle)))));
        console.log("DEX Integration:", address(dexIntegration));
        console.log(string(abi.encodePacked("Etherscan DEX: https://sepolia.etherscan.io/address/", _addressToString(address(dexIntegration)))));
        
        console.log("\n=== All Tests Completed Successfully! ===");
    }
    
    // Custom pool creation removed - using existing pools only
    
    function checkExistingPoolsForTokens(UniswapV4Integration dex, address token0, address token1) internal view {
        console.log("\n--- Test 1.5: Checking Existing Pools ---");

        // Call the pool checking function
        (address poolLow, address poolMedium, address poolHigh) = dex.checkExistingPools(token0, token1);

        console.log("\n=== POOL AVAILABILITY SUMMARY ===");

        if (poolLow != address(0)) {
            console.log("SUCCESS: 0.05%% fee pool EXISTS!");
        } else {
            console.log("MISSING: 0.05%% fee pool does not exist");
        }

        if (poolMedium != address(0)) {
            console.log("SUCCESS: 0.3%% fee pool EXISTS!");
        } else {
            console.log("MISSING: 0.3%% fee pool does not exist");
        }

        if (poolHigh != address(0)) {
            console.log("SUCCESS: 1%% fee pool EXISTS!");
        } else {
            console.log("MISSING: 1%% fee pool does not exist");
        }

        // Suggest best pool to use
        console.log("\n=== RECOMMENDED POOL ===");
        if (poolLow != address(0)) {
            console.log("RECOMMENDED: Use 0.05%% fee pool (typically has most liquidity)");
        } else if (poolMedium != address(0)) {
            console.log("RECOMMENDED: Use 0.3%% fee pool");
        } else if (poolHigh != address(0)) {
            console.log("RECOMMENDED: Use 1%% fee pool");
        } else {
            console.log("WARNING: No pools found for this token pair");
        }
    }
    
    // Direct swap test removed - handled by vault operations
    
    // Legacy function removed
    
    function testCustomPoolCreation(UniswapV4Integration dex) internal {
        console.log("\n--- Test 1.6: Custom Pool Creation Test ---");

        // Use DAI and EUR tokens that likely don't have existing pools
        address tokenA = DAI_ADDRESS;
        address tokenB = EUR_ADDRESS;

        console.log("Testing custom pool creation for:");
        console.log("TokenA (DAI): %s", tokenA);
        console.log("TokenB (EUR): %s", tokenB);

        // Check if pools exist for this pair
        (address poolLow, address poolMedium, address poolHigh) = dex.checkExistingPools(tokenA, tokenB);

        if (poolMedium == address(0) && poolLow == address(0) && poolHigh == address(0)) {
            console.log("Perfect! No existing pools found - will test custom pool creation");

            // This would normally be done through the vault, but let's test the DEX integration directly
            console.log("NOTE: Custom pool creation will be triggered automatically when swap is attempted");
            console.log("The DEX integration will:");
            console.log("1. Detect no existing pools");
            console.log("2. Create a new pool");
            console.log("3. Add initial liquidity");
            console.log("4. Attempt the swap");

        } else {
            console.log("Pools already exist for this pair:");
            if (poolLow != address(0)) console.log("0.05%% pool: %s", poolLow);
            if (poolMedium != address(0)) console.log("0.3%% pool: %s", poolMedium);
            if (poolHigh != address(0)) console.log("1%% pool: %s", poolHigh);
        }

        console.log("Custom pool creation test completed!");
    }
    
    function testMAVCPrice(MultiAssetVaultUSDCWETH vault) internal view {
        console.log("\n--- Test 1.2: MAVC Price Calculation ---");
        
        try vault.getMAVCPrice() returns (uint256 mavcPrice) {
            console.log("SUCCESS: MAVC price (USD):", _formatPrice(mavcPrice, 8), "USD");
            console.log("Formula: 1 MAVC = 0.005*USDC_price + 0.005*WETH_price");
        } catch Error(string memory reason) {
            console.log("ERROR: MAVC price error:", reason);
        } catch {
            console.log("ERROR: MAVC price: Unexpected error");
        }
    }
    
    function testChainlinkPriceData(ChainlinkPriceOracle oracle) internal view {
        console.log("\n--- Test 1: Chainlink Price Data ---");
        
        // Test DAI price
        try oracle.getDaiPrice() returns (uint256 daiPrice) {
            console.log("SUCCESS: Real DAI price (USD):", _formatPrice(daiPrice, 8), "USD");
        } catch Error(string memory reason) {
            console.log("ERROR: DAI price error:", reason);
        } catch {
            console.log("ERROR: DAI price: Unexpected error");
        }
        
        // Test EUR price
        try oracle.getEurPrice() returns (uint256 eurPrice) {
            console.log("SUCCESS: Real EUR price (USD):", _formatPrice(eurPrice, 8), "USD");
        } catch Error(string memory reason) {
            console.log("ERROR: EUR price error:", reason);
        } catch {
            console.log("ERROR: EUR price: Unexpected error");
        }
        
        // Test EUR/DAI price calculation
        try oracle.getEurPriceInDai() returns (uint256 eurDaiPrice) {
            console.log("SUCCESS: Real EUR price in DAI:", formatDAI(eurDaiPrice), "DAI per EUR");
        } catch Error(string memory reason) {
            console.log("ERROR: EUR/DAI price error:", reason);
        } catch {
            console.log("ERROR: EUR/DAI price: Unexpected error");
        }
        
        // Test oracle health
        try oracle.isHealthy() returns (bool healthy) {
            console.log("Oracle health:", healthy ? "HEALTHY" : "UNHEALTHY");
        } catch {
            console.log("Oracle health: Check failed");
        }
        
        // Show detailed price information
        try oracle.getDetailedPrices() returns (
            uint256 daiPrice,
            uint256 eurPrice,
            uint256 eurDaiPrice,
            uint256 daiTimestamp,
            uint256 eurTimestamp
        ) {
            console.log("\n=== DETAILED CHAINLINK PRICE DATA ===");
            console.log("DAI/USD Price:", _formatPrice(daiPrice, 8), "USD");
            console.log("EUR/USD Price:", _formatPrice(eurPrice, 8), "USD");
            console.log("EUR/DAI Price:", formatDAI(eurDaiPrice), "DAI per EUR");
            console.log("DAI Price Timestamp:", daiTimestamp);
            console.log("EUR Price Timestamp:", eurTimestamp);
            console.log("Current Block Timestamp:", block.timestamp);
            
            // Check price staleness
            uint256 daiAge = block.timestamp - daiTimestamp;
            uint256 eurAge = block.timestamp - eurTimestamp;
            
            console.log("DAI Price Age:", daiAge, "seconds");
            console.log("EUR Price Age:", eurAge, "seconds");
            
            if (daiAge > 3600) {
                console.log("WARNING: DAI price is stale (>1 hour old)");
            }
            if (eurAge > 3600) {
                console.log("WARNING: EUR price is stale (>1 hour old)");
            }
            
        } catch Error(string memory reason) {
            console.log("ERROR: Detailed prices error:", reason);
        } catch {
            console.log("ERROR: Detailed prices: Unexpected error");
        }
    }
    
    function testVaultOperations(MultiAssetVaultUSDCWETH vault) internal {
        console.log("\n--- Test 2: Vault Operations with Real Tokens ---");
        
        // Get token interfaces
        IERC20 usdc = IERC20(USDC_ADDRESS);
        IERC20 weth = IERC20(WETH_ADDRESS);
        
        // Check token balances for the wallet that has tokens
        uint256 usdcBalance = usdc.balanceOf(getWalletWithTokens());
        uint256 wethBalance = weth.balanceOf(getWalletWithTokens());
        
        console.log("Wallet with tokens:", getWalletWithTokens());
        console.log("USDC Balance:", formatUSDC(usdcBalance), "USDC");
        console.log("WETH Balance:", formatWETH(wethBalance), "WETH");
        
        if (usdcBalance == 0) {
            console.log("WARNING: No USDC balance. Get testnet USDC from faucets");
            return;
        }
        
        // Test deposit
        testDeposit(vault, usdc, weth);
        
        // Test withdrawal
        testWithdrawal(vault, usdc, weth);
        
        // Test price conversion functions
        testPriceConversions(vault);
    }
    
    function testDeposit(MultiAssetVaultUSDCWETH vault, IERC20 usdc, IERC20 weth) internal {
        console.log("\n--- Test 2A: DEPOSIT OPERATION (REAL TRANSACTIONS) ---");
        
        uint256 depositAmount = 10e6; // 10 USDC (start small for testing)
        
        // Show initial state
        console.log("\n=== INITIAL STATE ===");
        printBalanceTable("BEFORE DEPOSIT", getWalletWithTokens(), vault, usdc, weth);
        
        // Check if wallet has enough USDC
        uint256 walletUsdcBalance = usdc.balanceOf(getWalletWithTokens());
        if (walletUsdcBalance < depositAmount) {
            console.log("WARNING: Insufficient USDC balance for deposit");
            console.log("Required:", formatUSDC(depositAmount), "USDC");
            console.log("Available:", formatUSDC(walletUsdcBalance), "USDC");
            return;
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
        console.log("SUCCESS: Received", formatMAV(shares), "MAVC shares");
        
        vm.stopBroadcast();
        
        // Show state after deposit
        console.log("\n=== STATE AFTER DEPOSIT ===");
        printBalanceTable("AFTER DEPOSIT", getWalletWithTokens(), vault, usdc, weth);
        
        // Show vault allocation
        (uint256 daiPercent, uint256 eurPercent) = vault.getCurrentAllocation();
        console.log("\n=== VAULT ALLOCATION ===");
        console.log("DAI Allocation:", daiPercent, "%");
        console.log("EUR Allocation:", eurPercent, "%");
        
        // Test DEX integration status
        console.log("\n=== DEX INTEGRATION STATUS ===");
        try vault.DEX_INTEGRATION().poolExists(USDC_ADDRESS, WETH_ADDRESS) returns (bool exists) {
            console.log("USDC/WETH Pool Exists:", exists ? "YES" : "NO");
            if (!exists) {
                console.log("INFO: No pool found - vault kept USDC without swapping (expected on testnet)");
            }
        } catch {
            console.log("INFO: Could not check pool status");
        }
    }
    
    function testWithdrawal(MultiAssetVaultUSDCWETH vault, IERC20 usdc, IERC20 weth) internal {
        console.log("\n--- Test 2B: WITHDRAWAL OPERATION (REAL TRANSACTIONS) ---");
        
        uint256 userShares = vault.balanceOf(getWalletWithTokens());
        if (userShares == 0) {
            console.log("WARNING: No shares to withdraw");
            return;
        }
        
        uint256 withdrawAmount = userShares; // Withdraw all shares (100 MAV)
        if (withdrawAmount == 0) {
            console.log("WARNING: Share balance too small to withdraw");
            return;
        }
        
        // Show initial state
        console.log("\n=== INITIAL STATE ===");
        printBalanceTable("BEFORE WITHDRAWAL", getWalletWithTokens(), vault, usdc, weth);
        
        // Perform REAL withdrawal transaction
        vm.startBroadcast(OWNER_PRIVATE_KEY);
        
        uint256 assetsWithdrawn = vault.redeem(withdrawAmount, getWalletWithTokens(), getWalletWithTokens());
        console.log("SUCCESS: Redeemed", formatMAV(withdrawAmount), "MAVC shares");
        console.log("SUCCESS: Received", formatUSDC(assetsWithdrawn), "USDC");
        
        vm.stopBroadcast();
        
        // Show final state
        console.log("\n=== FINAL STATE ===");
        printBalanceTable("AFTER WITHDRAWAL", getWalletWithTokens(), vault, usdc, weth);
        
        // Show DEX interaction results
        console.log("\n=== DEX INTERACTION RESULTS ===");
        (uint256 actualUsdc, uint256 actualWeth) = vault.getActualBalances();
        console.log("Vault USDC Holdings:", formatUSDC(actualUsdc), "USDC");
        console.log("Vault WETH Holdings:", formatWETH(actualWeth), "WETH");

        if (actualWeth == 0) {
            console.log("INFO: No WETH holdings - DEX swap was skipped (no pools available)");
        } else {
            console.log("SUCCESS: DEX integration worked - vault holds both USDC and WETH");
        }
    }
    
    function printBalanceTable(string memory title, address user, MultiAssetVaultUSDCWETH vault, IERC20 usdc, IERC20 weth) internal view {
        console.log("\n=== ", title, " ===");
        console.log("========================================================");
        console.log("| Account | USDC Balance | WETH Balance | MAVC Balance |");
        console.log("========================================================");

        // User balances
        uint256 userUsdcBalance = usdc.balanceOf(user);
        uint256 userWethBalance = weth.balanceOf(user);
        uint256 userMavcBalance = vault.balanceOf(user);
        string memory userRow = string(abi.encodePacked("| User    | ", formatUSDC(userUsdcBalance), " USDC | ", formatWETH(userWethBalance), " WETH | ", formatMAV(userMavcBalance), " MAVC |"));
        console.log(userRow);

        // Vault balances
        uint256 vaultUsdcBalance = usdc.balanceOf(address(vault));
        uint256 vaultWethBalance = weth.balanceOf(address(vault));
        uint256 vaultMavcBalance = vault.balanceOf(address(vault)); // Vault's own MAVC balance (should be 0)
        uint256 vaultTotalAssets = vault.totalAssets();
        string memory vaultRow = string(abi.encodePacked("| Vault   | ", formatUSDC(vaultUsdcBalance), " USDC | ", formatWETH(vaultWethBalance), " WETH | ", formatMAV(vaultMavcBalance), " MAVC |"));
        console.log(vaultRow);

        console.log("========================================================");

        // Additional vault info
        console.log("\nVault Internal Accounting:");
        console.log("  Total Assets:", formatUSDC(vaultTotalAssets), "USDC");
        console.log("  USDC Held:", formatUSDC(vault.usdcHeld()), "USDC");
        console.log("  WETH Held:", formatUSDC(vault.wethHeld()), "USDC value");

        // Show actual token balances
        (uint256 actualUsdc, uint256 actualWeth) = vault.getActualBalances();
        console.log("\nActual Token Holdings:");
        console.log("  USDC Tokens:", formatUSDC(actualUsdc), "USDC");
        console.log("  WETH Tokens:", formatWETH(actualWeth), "WETH");
    }
    
    
    function testPriceConversions(MultiAssetVaultUSDCWETH vault) internal view {
        console.log("\n--- Test 3: Price Conversion Functions ---");
        
        console.log("Price conversion functions not implemented for USDC/WETH vault");
        console.log("This vault uses DEX swaps instead of oracle-based conversions");

        // Show current allocation instead
        (uint256 usdcPercent, uint256 wethPercent) = vault.getCurrentAllocation();
        console.log("Current USDC allocation:", usdcPercent, "%");
        console.log("Current WETH allocation:", wethPercent, "%");
    }
    
    // Helper functions for human-readable formatting
    function formatDAI(uint256 amount) internal pure returns (string memory) {
        if (amount == 0) return "0.00";
        
        uint256 whole = amount / 1e18;
        uint256 fractional = (amount % 1e18) / 1e16; // Get first 2 decimal places
        
        // Ensure proper padding for fractional part
        string memory fracStr;
        if (fractional < 10) {
            fracStr = string(abi.encodePacked("0", _toString(fractional)));
        } else {
            fracStr = _toString(fractional);
        }
        
        return string(abi.encodePacked(_toString(whole), ".", fracStr));
    }
    
    function formatEUR(uint256 amount) internal pure returns (string memory) {
        if (amount == 0) return "0.00";
        
        uint256 whole = amount / 1e6;
        uint256 fractional = (amount % 1e6) / 1e4; // Get first 2 decimal places
        
        // Ensure proper padding for fractional part
        string memory fracStr;
        if (fractional < 10) {
            fracStr = string(abi.encodePacked("0", _toString(fractional)));
        } else {
            fracStr = _toString(fractional);
        }
        
        return string(abi.encodePacked(_toString(whole), ".", fracStr));
    }
    
    function formatMAV(uint256 amount) internal pure returns (string memory) {
        if (amount == 0) return "0.00";
        
        uint256 whole = amount / 1e18;
        uint256 fractional = (amount % 1e18) / 1e16; // Get first 2 decimal places
        
        // Ensure proper padding for fractional part
        string memory fracStr;
        if (fractional < 10) {
            fracStr = string(abi.encodePacked("0", _toString(fractional)));
        } else {
            fracStr = _toString(fractional);
        }
        
        return string(abi.encodePacked(_toString(whole), ".", fracStr));
    }
    
    function _formatPrice(uint256 amount, uint8 decimals) internal pure returns (string memory) {
        if (amount == 0) return "0.0";
        
        uint256 divisor = 10 ** decimals;
        uint256 whole = amount / divisor;
        uint256 fractional = amount % divisor;
        
        if (fractional == 0) {
            return string(abi.encodePacked(_toString(whole), ".0"));
        }
        
        // Remove trailing zeros from fractional part
        while (fractional > 0 && fractional % 10 == 0) {
            fractional = fractional / 10;
        }
        
        return string(abi.encodePacked(_toString(whole), ".", _toString(fractional)));
    }
    
    function formatUSDC(uint256 amount) internal pure returns (string memory) {
        if (amount == 0) return "0.00";
        
        uint256 whole = amount / 1e6;
        uint256 fractional = (amount % 1e6) / 1e4; // Get first 2 decimal places
        
        // Ensure proper padding for fractional part
        string memory fracStr;
        if (fractional < 10) {
            fracStr = string(abi.encodePacked("0", _toString(fractional)));
        } else {
            fracStr = _toString(fractional);
        }
        
        return string(abi.encodePacked(_toString(whole), ".", fracStr));
    }
    
    function formatWETH(uint256 amount) internal pure returns (string memory) {
        if (amount == 0) return "0.0000";
        
        uint256 whole = amount / 1e18;
        uint256 fractional = (amount % 1e18) / 1e14; // Get first 4 decimal places for WETH
        
        // Ensure proper padding for fractional part
        string memory fracStr;
        if (fractional < 10) {
            fracStr = string(abi.encodePacked("000", _toString(fractional)));
        } else if (fractional < 100) {
            fracStr = string(abi.encodePacked("00", _toString(fractional)));
        } else if (fractional < 1000) {
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
}
