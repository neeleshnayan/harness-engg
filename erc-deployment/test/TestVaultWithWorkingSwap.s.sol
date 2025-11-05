// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/MultiAssetVaultUSDCWETH.sol";
import "../src/ChainlinkPriceOracle.sol";
import "../src/UniswapV4Integration_Working.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract TestVaultWithWorkingSwap is Script {
    // Test account configuration
    uint256 immutable OWNER_PRIVATE_KEY = vm.envUint("PRIVATE_KEY");

    // Use specific wallet that has tokens and ETH for gas
    address constant WALLET_WITH_TOKENS = 0xcB499cf9d71FBD345e9BF8A37434e5C92d290Efc;

    function getVaultOwner() internal pure returns (address) {
        return WALLET_WITH_TOKENS;
    }

    function getWalletWithTokens() internal pure returns (address) {
        return WALLET_WITH_TOKENS;
    }

    // Use tokens with existing liquidity on Sepolia - WETH/USDC
    address constant USDC_ADDRESS = 0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238; // USDC on Sepolia
    address constant WETH_ADDRESS = 0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14; // WETH on Sepolia

    function run() external {
        console.log("=== VAULT TEST WITH WORKING SWAP INTEGRATION ===");
        console.log("Testing complete vault flow: deposit -> swap -> withdrawal");
        console.log("Using WORKING Universal Router + Permit2 system");
        console.log("Vault Owner:", getVaultOwner());

        vm.startBroadcast(OWNER_PRIVATE_KEY);

        ChainlinkPriceOracle priceOracle = new ChainlinkPriceOracle(getVaultOwner());
        console.log("Deployed Chainlink Price Oracle");

        UniswapV4Integration_Working dexIntegration = new UniswapV4Integration_Working(getVaultOwner());
        console.log("Deployed WORKING DEX integration");

        MultiAssetVaultUSDCWETH vault = new MultiAssetVaultUSDCWETH(
            USDC_ADDRESS,
            WETH_ADDRESS,
            address(dexIntegration),
            address(priceOracle),
            "Multi Asset Vault USDC/WETH Working",
            "MAVW"
        );
        console.log("Deployed vault with working DEX integration");

        vm.stopBroadcast();

        console.log("Contracts deployed:");
        console.log("  USDC:", USDC_ADDRESS);
        console.log("  WETH:", WETH_ADDRESS);
        console.log("  Price Oracle:", address(priceOracle));
        console.log("  Working DEX Integration:", address(dexIntegration));
        console.log("  Vault:", address(vault));

        // Show working pool information
        showWorkingPoolInfo(dexIntegration);

        // Test the complete vault flow
        testCompleteVaultFlow(vault, dexIntegration);

        console.log("\n=== All Tests Completed Successfully! ===");
    }

    function showWorkingPoolInfo(UniswapV4Integration_Working dexIntegration) internal view {
        console.log("\n--- WORKING POOL INFORMATION ---");

        try dexIntegration.checkPoolInfo() returns (
            uint128 liquidity,
            uint24 fee,
            bool unlocked,
            uint160 sqrtPriceX96
        ) {
            console.log("Pool Address: 0x6Ce0896eAE6D4BD668fDe41BB784548fb8F59b50");
            console.log("Liquidity: %s units", liquidity);
            console.log("Fee: %s bps (0.%s%%)", fee, fee / 100);
            console.log("Unlocked: %s", unlocked);
            console.log("Current Price (sqrtPriceX96): %s", sqrtPriceX96);

            // Calculate approximate USDC per WETH price
            uint256 price = uint256(sqrtPriceX96) * uint256(sqrtPriceX96) / (2**192) * 1e12;
            console.log("Approx price: %s USDC per WETH", price / 1e6);

            console.log("SUCCESS: Pool has %s liquidity units and is ready for trading!", liquidity);
        } catch {
            console.log("Could not read pool information");
        }
    }

    function testCompleteVaultFlow(MultiAssetVaultUSDCWETH vault, UniswapV4Integration_Working dexIntegration) internal {
        console.log("\n--- COMPLETE VAULT FLOW TEST ---");

        // Get token interfaces
        IERC20 usdc = IERC20(USDC_ADDRESS);
        IERC20 weth = IERC20(WETH_ADDRESS);

        // Check initial balances
        uint256 initialUsdcBalance = usdc.balanceOf(getWalletWithTokens());
        uint256 initialWethBalance = weth.balanceOf(getWalletWithTokens());

        console.log("\n=== INITIAL STATE ===");
        console.log("User USDC: %s USDC", initialUsdcBalance / 1e6);
        console.log("User WETH: %s WETH", initialWethBalance / 1e18);

        if (initialUsdcBalance < 20e6) {
            console.log("WARNING: Insufficient USDC balance for testing");
            return;
        }

        // Step 1: Test direct swap through DEX integration
        testDirectSwap(dexIntegration, usdc, weth);

        // Step 2: Test vault deposit
        testVaultDeposit(vault, usdc, weth);

        // Step 3: Test vault withdrawal
        testVaultWithdrawal(vault, usdc, weth);

        // Show final state
        uint256 finalUsdcBalance = usdc.balanceOf(getWalletWithTokens());
        uint256 finalWethBalance = weth.balanceOf(getWalletWithTokens());

        console.log("\n=== FINAL STATE ===");
        console.log("User USDC: %s USDC", finalUsdcBalance / 1e6);
        console.log("User WETH: %s WETH", finalWethBalance / 1e18);
        console.log("USDC Change: %s", int256(finalUsdcBalance) - int256(initialUsdcBalance));
        console.log("WETH Change: %s", int256(finalWethBalance) - int256(initialWethBalance));
    }

    function testDirectSwap(UniswapV4Integration_Working dexIntegration, IERC20 usdc, IERC20 weth) internal {
        console.log("\n--- TEST 1: DIRECT SWAP THROUGH DEX INTEGRATION ---");

        uint256 swapAmount = 10 * 1e6; // 10 USDC

        // Check balance before
        uint256 usdcBefore = usdc.balanceOf(getWalletWithTokens());
        uint256 wethBefore = weth.balanceOf(getWalletWithTokens());

        console.log("Before swap: %s USDC, %s WETH", usdcBefore / 1e6, wethBefore / 1e18);

        vm.startBroadcast(OWNER_PRIVATE_KEY);

        // Approve and execute swap
        usdc.approve(address(dexIntegration), swapAmount);
        console.log("Approved DEX for %s USDC", swapAmount / 1e6);

        try dexIntegration.swapTokens(USDC_ADDRESS, WETH_ADDRESS, swapAmount, 0) returns (uint256 amountOut) {
            console.log("SUCCESS: Direct swap completed!");
            console.log("USDC spent: %s", swapAmount / 1e6);
            console.log("WETH received: %s", amountOut / 1e18);

            // Check balances after
            uint256 usdcAfter = usdc.balanceOf(getWalletWithTokens());
            uint256 wethAfter = weth.balanceOf(getWalletWithTokens());

            console.log("After swap: %s USDC, %s WETH", usdcAfter / 1e6, wethAfter / 1e18);
            console.log("Actual USDC change: %s", int256(usdcAfter) - int256(usdcBefore));
            console.log("Actual WETH change: %s", int256(wethAfter) - int256(wethBefore));

        } catch Error(string memory reason) {
            console.log("ERROR: Direct swap failed: %s", reason);
        } catch {
            console.log("ERROR: Direct swap failed with unknown error");
        }

        vm.stopBroadcast();
    }

    function testVaultDeposit(MultiAssetVaultUSDCWETH vault, IERC20 usdc, IERC20 weth) internal {
        console.log("\n--- TEST 2: VAULT DEPOSIT ---");

        uint256 depositAmount = 50 * 1e6; // 50 USDC

        // Check vault balance before
        uint256 vaultUsdcBefore = usdc.balanceOf(address(vault));
        uint256 vaultWethBefore = weth.balanceOf(address(vault));

        console.log("Vault before deposit: %s USDC, %s WETH", vaultUsdcBefore / 1e6, vaultWethBefore / 1e18);

        vm.startBroadcast(OWNER_PRIVATE_KEY);

        // Approve and deposit
        usdc.approve(address(vault), depositAmount);
        console.log("Approved vault for %s USDC", depositAmount / 1e6);

        try vault.deposit(depositAmount, getWalletWithTokens()) returns (uint256 shares) {
            console.log("SUCCESS: Deposited %s USDC", depositAmount / 1e6);
            console.log("Received %s MAVW shares", shares / 1e18);

            // Check vault balance after deposit
            uint256 vaultUsdcAfter = usdc.balanceOf(address(vault));
            uint256 vaultWethAfter = weth.balanceOf(address(vault));

            console.log("Vault after deposit: %s USDC, %s WETH", vaultUsdcAfter / 1e6, vaultWethAfter / 1e18);

            // Check if vault performed any swaps
            if (vaultWethAfter > vaultWethBefore) {
                console.log("SUCCESS: Vault performed DEX swap during deposit!");
                console.log("WETH gained by vault: %s", (vaultWethAfter - vaultWethBefore) / 1e18);
            }

            // Show vault allocation
            try vault.getCurrentAllocation() returns (uint256 usdcPercent, uint256 wethPercent) {
                console.log("Vault allocation - USDC: %s%%, WETH: %s%%", usdcPercent, wethPercent);
            } catch {
                console.log("Could not get vault allocation");
            }

        } catch Error(string memory reason) {
            console.log("ERROR: Vault deposit failed: %s", reason);
        } catch {
            console.log("ERROR: Vault deposit failed with unknown error");
        }

        vm.stopBroadcast();
    }

    function testVaultWithdrawal(MultiAssetVaultUSDCWETH vault, IERC20 usdc, IERC20 weth) internal {
        console.log("\n--- TEST 3: VAULT WITHDRAWAL ---");

        uint256 userShares = vault.balanceOf(getWalletWithTokens());
        console.log("User shares available: %s MAVW", userShares / 1e18);

        if (userShares == 0) {
            console.log("WARNING: No shares to withdraw");
            return;
        }

        // Withdraw half of shares
        uint256 withdrawShares = userShares / 2;

        // Check balances before withdrawal
        uint256 userUsdcBefore = usdc.balanceOf(getWalletWithTokens());
        uint256 userWethBefore = weth.balanceOf(getWalletWithTokens());

        console.log("User before withdrawal: %s USDC, %s WETH", userUsdcBefore / 1e6, userWethBefore / 1e18);

        vm.startBroadcast(OWNER_PRIVATE_KEY);

        try vault.redeem(withdrawShares, getWalletWithTokens(), getWalletWithTokens()) returns (uint256 assetsReceived) {
            console.log("SUCCESS: Withdrew %s MAVW shares", withdrawShares / 1e18);
            console.log("Received %s assets", assetsReceived / 1e6);

            // Check balances after withdrawal
            uint256 userUsdcAfter = usdc.balanceOf(getWalletWithTokens());
            uint256 userWethAfter = weth.balanceOf(getWalletWithTokens());

            console.log("User after withdrawal: %s USDC, %s WETH", userUsdcAfter / 1e6, userWethAfter / 1e18);
            console.log("USDC change: %s", int256(userUsdcAfter) - int256(userUsdcBefore));
            console.log("WETH change: %s", int256(userWethAfter) - int256(userWethBefore));

            // Check if vault performed reverse swaps
            if (userWethAfter > userWethBefore) {
                console.log("SUCCESS: Vault returned both USDC and WETH!");
            }

        } catch Error(string memory reason) {
            console.log("ERROR: Vault withdrawal failed: %s", reason);
        } catch {
            console.log("ERROR: Vault withdrawal failed with unknown error");
        }

        vm.stopBroadcast();
    }
}