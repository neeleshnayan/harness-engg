// SPDX-License-Identifier: GPL-3.0
pragma solidity >=0.8.18;

import "forge-std/Script.sol";
import {TokenizedStrategy} from "@yearn-vaults/TokenizedStrategy.sol";

contract DeployTokenizedStrategy is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);

        console.log("===========================================");
        console.log("DEPLOYING TOKENIZED STRATEGY IMPLEMENTATION");
        console.log("===========================================");
        console.log("Deployer address:", deployer);
        console.log("Deployer balance:", deployer.balance);
        console.log("");

        vm.startBroadcast(deployerPrivateKey);

        address factory = address(0);

        TokenizedStrategy implementation = new TokenizedStrategy(factory);

        vm.stopBroadcast();

        console.log("===========================================");
        console.log("DEPLOYMENT SUCCESSFUL!");
        console.log("===========================================");
        console.log("TokenizedStrategy Implementation:", address(implementation));
        console.log("");
        console.log("IMPORTANT: Update BaseStrategy.sol tokenizedStrategyAddress");
        console.log("Change line 102 from:");
        console.log("  0x2e234DAe75C793f67A35089C9d99245E1C58470b");
        console.log("To:");
        console.log(" ", address(implementation));
        console.log("");
        console.log("Then rebuild and redeploy MAVCYearnStrategy");
        console.log("===========================================");
    }
}

