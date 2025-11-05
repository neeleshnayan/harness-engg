// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.20;

import {Script, console} from "forge-std/Script.sol";
import {MAVCYearnStrategyUSDCWETH} from "../src/MAVCYearnStrategyUSDCWETH.sol";

contract DeployMAVCYearnUSDCWETH is Script {
    address constant USDC_SEPOLIA = 0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238;
    address constant WETH_SEPOLIA = 0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14;
    address constant ETH_USD_FEED_SEPOLIA = 0x694AA1769357215DE4FAC081bf1f309aDC325306;

    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);

        console.log("===========================================");
        console.log("DEPLOYING MAVC YEARN STRATEGY (USDC/WETH)");
        console.log("===========================================");
        console.log("Deployer address:", deployer);
        console.log("Deployer balance:", deployer.balance);
        console.log("");

        uint256 chainId = block.chainid;
        address usdc;
        address weth;
        address ethUsdFeed;
        address dexIntegration;

        if (chainId == 11155111) {
            console.log("Network: SEPOLIA TESTNET");
            usdc = USDC_SEPOLIA;
            weth = WETH_SEPOLIA;
            ethUsdFeed = ETH_USD_FEED_SEPOLIA;
            
            console.log("Enter DEX Integration address:");
            dexIntegration = vm.envAddress("DEX_INTEGRATION_ADDRESS");
        } else {
            revert("Unsupported network");
        }

        console.log("");
        console.log("Contract Addresses:");
        console.log("- USDC:", usdc);
        console.log("- WETH:", weth);
        console.log("- ETH/USD Feed:", ethUsdFeed);
        console.log("- DEX Integration:", dexIntegration);
        console.log("");

        vm.startBroadcast(deployerPrivateKey);

        MAVCYearnStrategyUSDCWETH strategy = new MAVCYearnStrategyUSDCWETH(
            usdc,
            "MAVC Yearn Strategy USDC/WETH",
            weth,
            dexIntegration,
            ethUsdFeed
        );

        vm.stopBroadcast();

        console.log("===========================================");
        console.log("DEPLOYMENT SUCCESSFUL!");
        console.log("===========================================");
        console.log("MAVC Yearn Strategy:", address(strategy));
        console.log("");
        console.log("UPDATE FIRESTORE:");
        console.log("  VAULT_ADDRESS:", address(strategy));
        console.log("===========================================");
    }
}

