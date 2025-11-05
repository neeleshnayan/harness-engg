// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/MAVPPriceOracle.sol";
import "../src/MockUNIPriceFeed.sol";
import "../src/MockUSDTPriceFeed.sol";

contract DeployMAVPOracle is Script {
    // Sepolia Chainlink Price Feed Addresses
    address constant ETH_USD_FEED = 0x694AA1769357215DE4FAC081bf1f309aDC325306;
    address constant BTC_USD_FEED = 0x1b44F3514812d835EB1BDB0acB33d3fA3351Ee43;
    address constant LINK_USD_FEED = 0xc59E3633BAAC79493d908e63626716e204A45EdF;
    
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);
        
        console.log("=== Deploying MAVP Price Oracle System ===");
        console.log("Deployer:", deployer);
        
        vm.startBroadcast(deployerPrivateKey);
        
        // Deploy mock price feeds for missing tokens
        console.log("\n--- Deploying Mock Price Feeds ---");
        
        MockUSDTPriceFeed usdtFeed = new MockUSDTPriceFeed();
        console.log("MockUSDTPriceFeed deployed at:", address(usdtFeed));
        
        MockUNIPriceFeed uniFeed = new MockUNIPriceFeed();
        console.log("MockUNIPriceFeed deployed at:", address(uniFeed));
        
        // Deploy the main MAVP Price Oracle
        console.log("\n--- Deploying MAVP Price Oracle ---");
        
        MAVPPriceOracle priceOracle = new MAVPPriceOracle(
            ETH_USD_FEED,      // Real Chainlink ETH/USD feed
            BTC_USD_FEED,      // Real Chainlink BTC/USD feed
            address(usdtFeed), // Mock USDT/USD feed
            address(uniFeed),  // Mock UNI/USD feed
            LINK_USD_FEED      // Real Chainlink LINK/USD feed
        );
        
        console.log("MAVPPriceOracle deployed at:", address(priceOracle));
        
        vm.stopBroadcast();
        
        // Display oracle information
        console.log("\n=== Price Oracle Configuration ===");
        console.log("ETH/USD Feed (Real):", ETH_USD_FEED);
        console.log("BTC/USD Feed (Real):", BTC_USD_FEED);
        console.log("USDT/USD Feed (Mock):", address(usdtFeed));
        console.log("UNI/USD Feed (Mock):", address(uniFeed));
        console.log("LINK/USD Feed (Real):", LINK_USD_FEED);
        
        // Test the oracle
        testPriceOracle(priceOracle);
        
        console.log("\n=== Deployment Complete ===");
        console.log("Next steps:");
        console.log("1. Call MAVP.setPriceOracle(", address(priceOracle), ")");
        console.log("2. Update frontend with oracle address");
        console.log("3. Test price feeds in UI");
    }
    
    function testPriceOracle(MAVPPriceOracle oracle) internal view {
        console.log("\n--- Testing Price Oracle ---");
        
        try oracle.arePriceFeedsHealthy() returns (bool healthy) {
            console.log("Price feeds healthy:", healthy);
            
            if (healthy) {
                try oracle.getAssetPrices() returns (
                    uint256 ethPrice,
                    uint256 btcPrice,
                    uint256 usdtPrice,
                    uint256 uniPrice,
                    uint256 linkPrice,
                    uint256 mavpPrice
                ) {
                    console.log("\n=== Current Asset Prices (USD) ===");
                    console.log("ETH:", _formatPrice(ethPrice));
                    console.log("BTC:", _formatPrice(btcPrice));
                    console.log("USDT:", _formatPrice(usdtPrice));
                    console.log("UNI:", _formatPrice(uniPrice));
                    console.log("LINK:", _formatPrice(linkPrice));
                    console.log("MAVP:", _formatPrice(mavpPrice));
                    
                    // Show breakdown
                    try oracle.getMAVPBreakdown() returns (
                        uint256 ethContrib,
                        uint256 btcContrib,
                        uint256 usdtContrib,
                        uint256 uniContrib,
                        uint256 linkContrib
                    ) {
                        console.log("\n=== MAVP Price Breakdown (20% each) ===");
                        console.log("ETH contribution:", _formatPrice(ethContrib));
                        console.log("BTC contribution:", _formatPrice(btcContrib));
                        console.log("USDT contribution:", _formatPrice(usdtContrib));
                        console.log("UNI contribution:", _formatPrice(uniContrib));
                        console.log("LINK contribution:", _formatPrice(linkContrib));
                        
                        uint256 total = ethContrib + btcContrib + usdtContrib + uniContrib + linkContrib;
                        console.log("Total MAVP price:", _formatPrice(total));
                    } catch {
                        console.log("Failed to get MAVP breakdown");
                    }
                } catch {
                    console.log("Failed to get asset prices");
                }
            }
        } catch {
            console.log("Failed to check price feed health");
        }
    }
    
    function _formatPrice(uint256 price) internal pure returns (string memory) {
        // Convert 8-decimal price to human readable format
        uint256 dollars = price / 1e8;
        uint256 cents = (price % 1e8) / 1e6; // Get 2 decimal places
        
        if (cents < 10) {
            return string(abi.encodePacked("$", _toString(dollars), ".0", _toString(cents)));
        } else {
            return string(abi.encodePacked("$", _toString(dollars), ".", _toString(cents)));
        }
    }
    
    function _toString(uint256 value) internal pure returns (string memory) {
        if (value == 0) return "0";
        
        uint256 temp = value;
        uint256 digits;
        while (temp != 0) {
            digits++;
            temp /= 10;
        }
        bytes memory buffer = new bytes(digits);
        while (value != 0) {
            digits -= 1;
            buffer[digits] = bytes1(uint8(48 + uint256(value % 10)));
            value /= 10;
        }
        return string(buffer);
    }
}
