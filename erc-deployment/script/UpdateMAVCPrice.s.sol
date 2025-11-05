// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/MultiAssetVaultUSDCWETH.sol";

/**
 * @title UpdateMAVCPrice
 * @notice Script to initialize/update the MAVC price on the deployed vault
 * @dev Run with: forge script script/UpdateMAVCPrice.s.sol:UpdateMAVCPrice --rpc-url sepolia --broadcast --verify
 */
contract UpdateMAVCPrice is Script {
    // Deployed vault address on Sepolia (from subgraph.yaml)
    address constant VAULT_ADDRESS = 0x3329f1cb19AA1A58f4ff4Bbef7a7C94f07953118;

    function run() external {
        // Get private key from environment variable
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");

        // Start broadcasting transactions
        vm.startBroadcast(deployerPrivateKey);

        // Get vault instance
        MultiAssetVaultUSDCWETH vault = MultiAssetVaultUSDCWETH(VAULT_ADDRESS);

        // Call updateMAVCPrice to initialize/update the price
        console.log("Calling updateMAVCPrice() on vault at:", VAULT_ADDRESS);

        try vault.updateMAVCPrice() returns (uint256 newPrice) {
            console.log("Success! MAVC price updated to:", newPrice);
            console.log("Price in USD (8 decimals):", newPrice / 1e8);
        } catch Error(string memory reason) {
            console.log("Failed to update price. Reason:", reason);
            console.log("This might be due to the 30-minute update interval.");
        } catch (bytes memory) {
            console.log("Failed to update price with unknown error.");
        }

        vm.stopBroadcast();
    }
}
