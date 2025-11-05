// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "chainlink-brownie-contracts/contracts/src/v0.8/shared/interfaces/AggregatorV3Interface.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title MAVPPriceOracle
 * @dev Calculates MAVP token price based on underlying asset prices from Chainlink oracles
 * Formula: 1 MAVP = 0.002*WETH + 0.002*WBTC + 0.002*USDT + 0.002*UNI + 0.002*LINK (in USD terms)
 */
contract MAVPPriceOracle is Ownable {
    
    // Chainlink Price Feed interfaces
    AggregatorV3Interface public immutable ethUsdFeed;
    AggregatorV3Interface public immutable btcUsdFeed;
    AggregatorV3Interface public immutable usdtUsdFeed;
    AggregatorV3Interface public immutable uniUsdFeed;
    AggregatorV3Interface public immutable linkUsdFeed;
    
    // Price feed staleness thresholds (in seconds)
    uint256 public constant ETH_HEARTBEAT = 3600;   // 1 hour
    uint256 public constant BTC_HEARTBEAT = 3600;   // 1 hour
    uint256 public constant USDT_HEARTBEAT = 86400; // 24 hours
    uint256 public constant UNI_HEARTBEAT = 86400;  // 24 hours (mock)
    uint256 public constant LINK_HEARTBEAT = 86400; // 24 hours
    
    // Portfolio weights (0.2% each = 20 basis points)
    uint256 public constant WEIGHT_BPS = 20; // 0.2% in basis points
    uint256 public constant TOTAL_BPS = 10000; // 100% in basis points
    
    // Events
    event PriceUpdated(uint256 mavpPriceUsd, uint256 timestamp);
    event PriceFeedStale(address feed, uint256 lastUpdate);
    
    constructor(
        address _ethUsdFeed,
        address _btcUsdFeed,
        address _usdtUsdFeed,
        address _uniUsdFeed,
        address _linkUsdFeed
    ) Ownable(msg.sender) {
        ethUsdFeed = AggregatorV3Interface(_ethUsdFeed);
        btcUsdFeed = AggregatorV3Interface(_btcUsdFeed);
        usdtUsdFeed = AggregatorV3Interface(_usdtUsdFeed);
        uniUsdFeed = AggregatorV3Interface(_uniUsdFeed);
        linkUsdFeed = AggregatorV3Interface(_linkUsdFeed);
    }
    
    /**
     * @dev Returns the latest MAVP price in USD (8 decimals)
     * Formula: 1 MAVP = 0.002*ETH_USD + 0.002*BTC_USD + 0.002*USDT_USD + 0.002*UNI_USD + 0.002*LINK_USD
     */
    function getMAVPPriceUSD() external view returns (uint256) {
        uint256 ethPrice = _getLatestPrice(ethUsdFeed, ETH_HEARTBEAT);
        uint256 btcPrice = _getLatestPrice(btcUsdFeed, BTC_HEARTBEAT);
        uint256 usdtPrice = _getLatestPrice(usdtUsdFeed, USDT_HEARTBEAT);
        uint256 uniPrice = _getLatestPrice(uniUsdFeed, UNI_HEARTBEAT);
        uint256 linkPrice = _getLatestPrice(linkUsdFeed, LINK_HEARTBEAT);
        
        // Calculate weighted average: (0.002 * price1 + 0.002 * price2 + ...)
        uint256 totalWeightedPrice = 
            (ethPrice * WEIGHT_BPS) +
            (btcPrice * WEIGHT_BPS) +
            (usdtPrice * WEIGHT_BPS) +
            (uniPrice * WEIGHT_BPS) +
            (linkPrice * WEIGHT_BPS);
            
        return totalWeightedPrice / TOTAL_BPS;
    }
    
    /**
     * @dev Returns individual asset prices and the calculated MAVP price
     */
    function getAssetPrices() external view returns (
        uint256 ethPrice,
        uint256 btcPrice,
        uint256 usdtPrice,
        uint256 uniPrice,
        uint256 linkPrice,
        uint256 mavpPrice
    ) {
        ethPrice = _getLatestPrice(ethUsdFeed, ETH_HEARTBEAT);
        btcPrice = _getLatestPrice(btcUsdFeed, BTC_HEARTBEAT);
        usdtPrice = _getLatestPrice(usdtUsdFeed, USDT_HEARTBEAT);
        uniPrice = _getLatestPrice(uniUsdFeed, UNI_HEARTBEAT);
        linkPrice = _getLatestPrice(linkUsdFeed, LINK_HEARTBEAT);
        
        uint256 totalWeightedPrice = 
            (ethPrice * WEIGHT_BPS) +
            (btcPrice * WEIGHT_BPS) +
            (usdtPrice * WEIGHT_BPS) +
            (uniPrice * WEIGHT_BPS) +
            (linkPrice * WEIGHT_BPS);
            
        mavpPrice = totalWeightedPrice / TOTAL_BPS;
    }
    
    /**
     * @dev Returns the breakdown of MAVP price by asset contribution
     */
    function getMAVPBreakdown() external view returns (
        uint256 ethContribution,
        uint256 btcContribution,
        uint256 usdtContribution,
        uint256 uniContribution,
        uint256 linkContribution
    ) {
        uint256 ethPrice = _getLatestPrice(ethUsdFeed, ETH_HEARTBEAT);
        uint256 btcPrice = _getLatestPrice(btcUsdFeed, BTC_HEARTBEAT);
        uint256 usdtPrice = _getLatestPrice(usdtUsdFeed, USDT_HEARTBEAT);
        uint256 uniPrice = _getLatestPrice(uniUsdFeed, UNI_HEARTBEAT);
        uint256 linkPrice = _getLatestPrice(linkUsdFeed, LINK_HEARTBEAT);
        
        // Each asset contributes 0.2% to the total MAVP price
        ethContribution = (ethPrice * WEIGHT_BPS) / TOTAL_BPS;
        btcContribution = (btcPrice * WEIGHT_BPS) / TOTAL_BPS;
        usdtContribution = (usdtPrice * WEIGHT_BPS) / TOTAL_BPS;
        uniContribution = (uniPrice * WEIGHT_BPS) / TOTAL_BPS;
        linkContribution = (linkPrice * WEIGHT_BPS) / TOTAL_BPS;
    }
    
    /**
     * @dev Internal function to get latest price from a Chainlink feed with staleness check
     */
    function _getLatestPrice(AggregatorV3Interface priceFeed, uint256 heartbeat) internal view returns (uint256) {
        try priceFeed.latestRoundData() returns (
            uint80 roundId,
            int256 price,
            uint256 startedAt,
            uint256 updatedAt,
            uint80 answeredInRound
        ) {
            require(price > 0, "Invalid price from oracle");
            require(updatedAt > 0, "Round not complete");
            
            // Check if price is stale
            if (block.timestamp - updatedAt > heartbeat) {
                revert("Price feed is stale");
            }
            
            return uint256(price);
        } catch {
            revert("Failed to get price from oracle");
        }
    }
    
    /**
     * @dev Check if all price feeds are healthy (not stale)
     */
    function arePriceFeedsHealthy() external view returns (bool) {
        try this._checkFeedHealth(ethUsdFeed, ETH_HEARTBEAT) {
            try this._checkFeedHealth(btcUsdFeed, BTC_HEARTBEAT) {
                try this._checkFeedHealth(usdtUsdFeed, USDT_HEARTBEAT) {
                    try this._checkFeedHealth(uniUsdFeed, UNI_HEARTBEAT) {
                        try this._checkFeedHealth(linkUsdFeed, LINK_HEARTBEAT) {
                            return true;
                        } catch { return false; }
                    } catch { return false; }
                } catch { return false; }
            } catch { return false; }
        } catch { return false; }
    }
    
    /**
     * @dev External function for feed health check (used internally)
     */
    function _checkFeedHealth(AggregatorV3Interface priceFeed, uint256 heartbeat) external view {
        _getLatestPrice(priceFeed, heartbeat);
    }
    
    /**
     * @dev Get the decimals used by this oracle (matches Chainlink standard)
     */
    function decimals() external pure returns (uint8) {
        return 8;
    }
    
    /**
     * @dev Get description of this oracle
     */
    function description() external pure returns (string memory) {
        return "MAVP/USD Price Feed - Multi Asset Vault Portfolio";
    }
}
