// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/MultiAssetVault.sol";
import "../src/MockUSDC.sol";
import "../src/MockWBTC.sol";
import "../src/ChainlinkPriceOracle.sol";
import "../src/UniswapV4Integration.sol";

contract DeployScript is Script {
    // Chainlink price feed addresses are configured in the ChainlinkPriceOracle contract

    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);
        
        console.log("Deploying contracts with the account:", deployer);
        console.log("Account balance:", deployer.balance);
        
        vm.startBroadcast(deployerPrivateKey);
        
        // Deploy mock tokens
        MockUSDC usdc = new MockUSDC();
        MockWBTC wbtc = new MockWBTC();
        
        console.log("MockUSDC deployed at:", address(usdc));
        console.log("MockWBTC deployed at:", address(wbtc));
        
        // Deploy Chainlink price oracle
        ChainlinkPriceOracle priceOracle = new ChainlinkPriceOracle(
            deployer
        );
        
        console.log("ChainlinkPriceOracle deployed at:", address(priceOracle));
        
        // Deploy DEX integration
        UniswapV4Integration dexIntegration = new UniswapV4Integration(
            deployer
        );
        
        console.log("DEXIntegration deployed at:", address(dexIntegration));
        
        // Deploy vault
        MultiAssetVault vault = new MultiAssetVault(
            address(usdc),
            address(wbtc),
            address(priceOracle),
            address(dexIntegration),
            "Multi Asset Vault Chainlink",
            "MAVC"
        );
        
        console.log("MultiAssetVault deployed at:", address(vault));
        
        vm.stopBroadcast();
        
        console.log("Deployment completed successfully!");
        console.log("Vault address:", address(vault));
        console.log("Price Oracle address:", address(priceOracle));
    }
}