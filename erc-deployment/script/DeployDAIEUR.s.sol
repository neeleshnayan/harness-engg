// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/MultiAssetVault.sol";
import "../src/ChainlinkPriceOracle.sol";
import "../src/UniswapV4Integration.sol";

contract DeployDAIEURScript is Script {
    // Real Sepolia testnet token addresses
    address constant DAI_ADDRESS = 0x68194a729C2450ad26072b3D33ADaCbcef39D574; // DAI on Sepolia
    address constant EUR_ADDRESS = 0x08210F9170F89Ab7658F0B5E3fF39b0E03C594D4; // EURC on Sepolia

    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);
        
        console.log("Deploying DAI/EUR vault with the account:", deployer);
        console.log("Account balance:", deployer.balance);
        
        vm.startBroadcast(deployerPrivateKey);
        
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
            DAI_ADDRESS,
            EUR_ADDRESS,
            address(priceOracle),
            address(dexIntegration),
            "Multi Asset Vault DAI/EUR",
            "MAV-DE"
        );
        
        console.log("MultiAssetVault deployed at:", address(vault));
        
        vm.stopBroadcast();
        
        console.log("Deployment completed successfully!");
        console.log("Vault address:", address(vault));
        console.log("Price Oracle address:", address(priceOracle));
        console.log("DAI Token address:", DAI_ADDRESS);
        console.log("EUR Token address:", EUR_ADDRESS);
    }
}

