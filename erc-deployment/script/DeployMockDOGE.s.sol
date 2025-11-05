// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/MockDOGE.sol";

contract DeployMockDOGE is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        
        vm.startBroadcast(deployerPrivateKey);
        
        MockDOGE doge = new MockDOGE{salt: bytes32(uint256(1))}();
        console.log("MockDOGE deployed at:", address(doge));
        console.log("Initial supply:", doge.totalSupply() / 1e8, "DOGE");
        console.log("Decimals:", doge.decimals());
        
        vm.stopBroadcast();
    }
}
