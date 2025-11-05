// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/MAVP.sol";
import "../src/UniswapV4Integration.sol";
import "../src/MAVPPriceOracle.sol";
import "../src/MockUNIPriceFeed.sol";
import "../src/MockUSDTPriceFeed.sol";

/// @notice Deploys the complete MAVP system: Price Oracle + Vault
contract DeployMAVP is Script {
    // Sepolia canonical token addresses (Blockscout)
    address constant USDC = 0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238; // 6 decimals
    address constant SOL = 0x824CB8fC742F8D3300d29f16cA8beE94471169f5; // 9 decimals
    address constant ADA = 0x944c886956e09014d88E9bB6B91641F1bEF2BBe8; // 18 decimals
    address constant WETH = 0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14; // 18 decimals
    address constant DOGE = 0x183209DA02C281709A5BcD40188AaFfA04A7fEfD; // 18 decimals
    address constant WBNB = 0x343c0D9Fe222109f223bC8Fd9ff9C48351E63B90; // 18 decimals

    // Sepolia Chainlink Price Feed Addresses
    address constant ETH_USD_FEED = 0x694AA1769357215DE4FAC081bf1f309aDC325306;
    address constant BTC_USD_FEED = 0x1b44F3514812d835EB1BDB0acB33d3fA3351Ee43;
    address constant LINK_USD_FEED = 0xc59E3633BAAC79493d908e63626716e204A45EdF;

    function run() external {
        uint256 privateKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(privateKey);

        console2.log("=== Deploying MAVP System ===");
        console2.log("Deployer:", deployer);

        vm.startBroadcast(privateKey);

        // Step 1: Deploy mock price feeds
        console2.log("\n--- Deploying Mock Price Feeds ---");
        MockUSDTPriceFeed usdtFeed = new MockUSDTPriceFeed();
        console2.log("MockUSDTPriceFeed:", address(usdtFeed));

        MockUNIPriceFeed uniFeed = new MockUNIPriceFeed();
        console2.log("MockUNIPriceFeed:", address(uniFeed));

        // Step 2: Deploy MAVP Price Oracle
        console2.log("\n--- Deploying MAVP Price Oracle ---");
        MAVPPriceOracle priceOracle = new MAVPPriceOracle(
            ETH_USD_FEED,      // Real Chainlink ETH/USD feed
            BTC_USD_FEED,      // Real Chainlink BTC/USD feed
            address(usdtFeed), // Mock USDT/USD feed
            address(uniFeed),  // Mock UNI/USD feed
            LINK_USD_FEED      // Real Chainlink LINK/USD feed
        );
        console2.log("MAVPPriceOracle:", address(priceOracle));

        // Step 3: Deploy or reuse DEX Integration
        address dexOverride = vm.envOr("DEX_INTEGRATION", address(0));
        UniswapV4Integration dex =
            dexOverride == address(0) ? new UniswapV4Integration(deployer) : UniswapV4Integration(dexOverride);
        console2.log("DEX Integration:", address(dex));

        // Step 4: Deploy MAVP Vault with oracle
        console2.log("\n--- Deploying MAVP Vault ---");
        address[] memory assets = new address[](5);
        assets[0] = SOL;
        assets[1] = ADA;
        assets[2] = WETH;
        assets[3] = DOGE;
        assets[4] = WBNB;

        MultiAssetVaultPortfolio vault = new MultiAssetVaultPortfolio(
            USDC,
            assets,
            address(dex),
            address(priceOracle),  // Pass oracle to constructor
            "Multi Asset Vault Portfolio",
            "MAVP"
        );
        console2.log("MAVP Vault:", address(vault));

        vm.stopBroadcast();

        // Summary
        console2.log("\n=== Deployment Complete ===");
        console2.log("Deployer:", deployer);
        console2.log("MAVP Price Oracle:", address(priceOracle));
        console2.log("MAVP Vault:", address(vault));
        console2.log("DEX Integration:", address(dex));
        console2.log("\n=== Update these addresses in: ===");
        console2.log("1. Firebase: quant_strategies/MAVP/vault_address");
        console2.log("2. Subgraph: subgraph.yaml MAVP address");
    }
}
