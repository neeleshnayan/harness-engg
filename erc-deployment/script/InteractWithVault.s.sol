// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/MultiAssetVault.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract InteractWithVault is Script {
    // Your deployed contracts
    address constant VAULT_ADDRESS = 0x284Be3234de1B24F522afFeFB7906C151A42e924;
    address constant DAI_ADDRESS = 0x68194a729C2450ad26072b3D33ADaCbcef39D574;
    
    function run() external {
        uint256 privateKey = vm.envUint("PRIVATE_KEY");
        address user = vm.addr(privateKey);
        
        console.log("=== REAL VAULT INTERACTION ===");
        console.log("User:", user);
        console.log("Vault:", VAULT_ADDRESS);
        
        vm.startBroadcast(privateKey);
        
        // Check DAI balance
        uint256 daiBalance = IERC20(DAI_ADDRESS).balanceOf(user);
        console.log("User DAI balance:", daiBalance / 1e18, "DAI");
        
        if (daiBalance >= 1e18) { // If user has at least 1 DAI
            // Approve vault to spend DAI
            IERC20(DAI_ADDRESS).approve(VAULT_ADDRESS, 1e18);
            console.log("SUCCESS: Approved 1 DAI for vault");
            
            // Deposit 1 DAI
            MultiAssetVault vault = MultiAssetVault(VAULT_ADDRESS);
            uint256 shares = vault.deposit(1e18, user);
            console.log("SUCCESS: Deposited 1 DAI, received", shares / 1e18, "MAVC shares");
            
            console.log("Real transaction completed!");
            console.log("Check Etherscan for transaction history");
        } else {
            console.log("ERROR: Need at least 1 DAI to interact");
        }
        
        vm.stopBroadcast();
    }
}
