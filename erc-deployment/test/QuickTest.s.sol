// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/MultiAssetVault.sol";
import "../src/MockUSDC.sol";

contract QuickTest is Script {
    address constant USDC_ADDRESS = 0x5FbDB2315678afecb367f032d93F642f64180aa3;
    address constant VAULT_ADDRESS = 0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0;
    address constant TEST_USER = 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266;
    uint256 constant PRIVATE_KEY = 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80;
    
    function run() external {
        console.log("=== Quick Vault Test ===");
        
        MockUSDC usdc = MockUSDC(USDC_ADDRESS);
        MultiAssetVault vault = MultiAssetVault(VAULT_ADDRESS);
        
        vm.startBroadcast(PRIVATE_KEY);
        
        // Quick deposit test
        uint256 depositAmount = 50000e6; // 50K USDC
        usdc.mint(TEST_USER, depositAmount);
        usdc.approve(address(vault), depositAmount);
        
        console.log("Depositing:", depositAmount);
        uint256 shares = vault.deposit(depositAmount, TEST_USER);
        console.log("Shares received:", shares);
        
        // Check state
        console.log("Total assets:", vault.totalAssets());
        console.log("User shares:", vault.balanceOf(TEST_USER));
        
        (uint256 usdcPercent, uint256 btcPercent) = vault.getCurrentAllocation();
        console.log("Allocation - USDC:", usdcPercent, "%");
        console.log("Allocation - BTC:", btcPercent, "%");
        
        vm.stopBroadcast();
    }
}
