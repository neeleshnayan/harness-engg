// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";
import {console} from "forge-std/console.sol";
import {MAVCYearnStrategy} from "../src/MAVCYearnStrategy.sol";

/**
 * @title Deploy MAVC Yearn Strategy
 * @notice Deployment script for MAVC Yearn v3 tokenized strategy
 *
 * Usage:
 * forge script script/DeployMAVCYearn.s.sol:DeployMAVCYearn --rpc-url sepolia --broadcast --verify -vvvv
 */
contract DeployMAVCYearn is Script {
    // ============ Sepolia Testnet Addresses ============

    // USDC on Sepolia (Circle's testnet USDC)
    address constant USDC_SEPOLIA = 0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238;

    // WBTC on Sepolia (you may need to deploy a mock or use existing)
    address constant WBTC_SEPOLIA = 0x29f2D40B0605204364af54EC677bD022dA425d03; // Example address

    // Chainlink BTC/USD Price Feed on Sepolia
    address constant BTC_USD_FEED_SEPOLIA = 0x1b44F3514812d835EB1BDB0acB33d3fA3351Ee43;

    // Uniswap V3 SwapRouter on Sepolia
    address constant UNISWAP_V3_ROUTER_SEPOLIA = 0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E;

    // ============ Mainnet Addresses (for reference) ============

    address constant USDC_MAINNET = 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48;
    address constant WBTC_MAINNET = 0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599;
    address constant BTC_USD_FEED_MAINNET = 0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c;
    address constant UNISWAP_V3_ROUTER_MAINNET = 0xE592427A0AEce92De3Edee1F18E0157C05861564;

    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);

        console.log("===========================================");
        console.log("DEPLOYING MAVC YEARN STRATEGY");
        console.log("===========================================");
        console.log("Deployer address:", deployer);
        console.log("Deployer balance:", deployer.balance);
        console.log("");

        // Determine network and use appropriate addresses
        uint256 chainId = block.chainid;
        address usdc;
        address wbtc;
        address btcUsdFeed;
        address swapRouter;

        if (chainId == 1) {
            // Ethereum Mainnet
            console.log("Network: ETHEREUM MAINNET");
            usdc = USDC_MAINNET;
            wbtc = WBTC_MAINNET;
            btcUsdFeed = BTC_USD_FEED_MAINNET;
            swapRouter = UNISWAP_V3_ROUTER_MAINNET;
        } else if (chainId == 11155111) {
            // Sepolia Testnet
            console.log("Network: SEPOLIA TESTNET");
            usdc = USDC_SEPOLIA;
            wbtc = WBTC_SEPOLIA;
            btcUsdFeed = BTC_USD_FEED_SEPOLIA;
            swapRouter = UNISWAP_V3_ROUTER_SEPOLIA;
        } else {
            revert("Unsupported network");
        }

        console.log("");
        console.log("Contract Addresses:");
        console.log("- USDC:", usdc);
        console.log("- WBTC:", wbtc);
        console.log("- BTC/USD Feed:", btcUsdFeed);
        console.log("- Uniswap V3 Router:", swapRouter);
        console.log("");

        vm.startBroadcast(deployerPrivateKey);

        // Deploy MAVC Yearn Strategy
        MAVCYearnStrategy strategy = new MAVCYearnStrategy(
            usdc,                           // underlying asset (USDC)
            "MAVC Yearn Strategy",         // strategy name
            wbtc,                           // WBTC address
            btcUsdFeed,                     // Chainlink BTC/USD feed
            swapRouter                      // Uniswap V3 router
        );

        vm.stopBroadcast();

        console.log("===========================================");
        console.log("DEPLOYMENT SUCCESSFUL!");
        console.log("===========================================");
        console.log("MAVC Yearn Strategy:", address(strategy));
        console.log("");
        console.log("Next Steps:");
        console.log("1. Verify contract on Etherscan");
        console.log("2. Add vault address to Firestore:");
        console.log("   Collection: quant_strategies");
        console.log("   Document: MAVC_YEARN");
        console.log("   Field: VAULT_ADDRESS =", address(strategy));
        console.log("3. Fund the strategy with initial liquidity");
        console.log("4. Set up keeper for rebalancing (optional)");
        console.log("");
        console.log("Etherscan verification command:");
        console.log("forge verify-contract <ADDRESS>");
        console.log("  --chain-id", chainId);
        console.log("  src/MAVCYearnStrategy.sol:MAVCYearnStrategy");
        console.log("===========================================");
    }
}
