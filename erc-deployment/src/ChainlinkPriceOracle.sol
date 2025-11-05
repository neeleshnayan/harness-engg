// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "chainlink-brownie-contracts/contracts/src/v0.8/shared/interfaces/AggregatorV3Interface.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";

/**
 * @title ChainlinkPriceOracle
 * @dev Chainlink-based price oracle for multiple cryptocurrencies
 * @notice Provides real-time price data with staleness checks
 */
contract ChainlinkPriceOracle is Ownable, Pausable {
    // Price validation parameters  
    uint256 public constant MAX_STALENESS = 86400; // 24 hours in seconds (increased for testnet)
    uint256 public constant PRICE_PRECISION = 1e8; // Chainlink feeds use 8 decimals
    
    // Price feed contracts
    mapping(string => AggregatorV3Interface) public priceFeeds;
    mapping(string => uint8) public feedDecimals;
    
    // Events
    event PriceUpdated(string symbol, uint256 price, uint256 timestamp);
    event PriceFeedUpdated(string symbol, address feedAddress);
    
    // Errors
    error StalePrice(string symbol, uint256 timestamp, uint256 currentTime);
    error InvalidPrice(string symbol, int256 price);
    error PriceFeedNotSet(string symbol);
    error InvalidRoundData(string symbol);
    
    constructor(address _owner) Ownable(_owner) {
        _initializePriceFeeds();
    }
    
    /**
     * @dev Initialize price feeds for supported cryptocurrencies on Sepolia
     */
    function _initializePriceFeeds() internal {
        priceFeeds["DAI"] = AggregatorV3Interface(0x14866185B1962B63C3Ea9E03Bc1da838bab34C19);
        priceFeeds["EUR"] = AggregatorV3Interface(0x1a81afB8146aeFfCFc5E50e8479e826E7D55b910);
        priceFeeds["USDC"] = AggregatorV3Interface(0xA2F78ab2355fe2f984D808B5CeE7FD0A93D5270E);
        priceFeeds["ETH"] = AggregatorV3Interface(0x694AA1769357215DE4FAC081bf1f309aDC325306);
        
        feedDecimals["DAI"] = 8;
        feedDecimals["EUR"] = 8;
        feedDecimals["USDC"] = 8;
        feedDecimals["ETH"] = 8;
    }
    
    /**
     * @dev Get latest price for a cryptocurrency
     * @param symbol Token symbol (e.g., "BTC", "ETH", "USDC")
     * @return price Price in USD with 8 decimals
     */
    function getPrice(string memory symbol) public view virtual returns (uint256 price) {
        AggregatorV3Interface priceFeed = priceFeeds[symbol];
        if (address(priceFeed) == address(0)) {
            revert PriceFeedNotSet(symbol);
        }
        
        (
            uint80 roundId,
            int256 answer,
            uint256 startedAt,
            uint256 updatedAt,
            uint80 answeredInRound
        ) = priceFeed.latestRoundData();
        
        // Validate round data
        if (roundId == 0 || updatedAt == 0 || answeredInRound < roundId) {
            revert InvalidRoundData(symbol);
        }
        
        // Check if price is valid
        if (answer <= 0) {
            revert InvalidPrice(symbol, answer);
        }
        
        // Check for staleness
        if (block.timestamp - updatedAt > MAX_STALENESS) {
            revert StalePrice(symbol, updatedAt, block.timestamp);
        }
        
        // Convert to uint256 and normalize to 8 decimals
        uint8 decimals = feedDecimals[symbol];
        if (decimals == 8) {
            return uint256(answer);
        } else if (decimals < 8) {
            return uint256(answer) * (10 ** (8 - decimals));
        } else {
            return uint256(answer) / (10 ** (decimals - 8));
        }
    }
    
    /**
     * @dev Get DAI price in USD
     */
    function getDaiPrice() public view virtual returns (uint256 price) {
        return getPrice("DAI");
    }
    
    /**
     * @dev Get EUR price in USD
     */
    function getEurPrice() public view virtual returns (uint256 price) {
        return getPrice("EUR");
    }
    
    /**
     * @dev Get USDC price in USD
     */
    function getUsdcPrice() public view virtual returns (uint256 price) {
        return getPrice("USDC");
    }
    
    /**
     * @dev Get ETH price in USD
     */
    function getEthPrice() public view virtual returns (uint256 price) {
        return getPrice("ETH");
    }
    
    /**
     * @dev Get EUR price in DAI terms (18 decimals for DAI compatibility)
     */
    function getEurPriceInDai() public view virtual returns (uint256 price) {
        uint256 eurUsd = getEurPrice();
        uint256 daiUsd = getDaiPrice();
        
        // Convert EUR/USD to EUR/DAI
        // EUR/DAI = (EUR/USD) / (DAI/USD)
        // Adjust for decimals: both have 8 decimals, but DAI token has 18 decimals
        return (eurUsd * 1e18) / daiUsd;
    }
    
    /**
     * @dev Get detailed price information for multiple tokens
     */
    function getDetailedPrices() 
        public 
        view 
        virtual
        returns (
            uint256 daiPrice,
            uint256 eurPrice,
            uint256 eurDaiPrice,
            uint256 daiTimestamp,
            uint256 eurTimestamp
        ) 
    {
        daiPrice = getDaiPrice();
        eurPrice = getEurPrice();
        eurDaiPrice = getEurPriceInDai();
        
        // Get timestamps
        AggregatorV3Interface daiFeed = priceFeeds["DAI"];
        AggregatorV3Interface eurFeed = priceFeeds["EUR"];
        
        if (address(daiFeed) != address(0)) {
            (, , , uint256 updatedAt, ) = daiFeed.latestRoundData();
            daiTimestamp = updatedAt;
        }
        
        if (address(eurFeed) != address(0)) {
            (, , , uint256 updatedAt, ) = eurFeed.latestRoundData();
            eurTimestamp = updatedAt;
        }
    }
    
    /**
     * @dev Check if oracle is healthy
     */
    function isHealthy() external view virtual returns (bool healthy) {
        try this.getDaiPrice() returns (uint256) {
            try this.getEurPrice() returns (uint256) {
                return true;
            } catch {
                return false;
            }
        } catch {
            return false;
        }
    }
    
    /**
     * @dev Update price feed address for a symbol
     */
    function updatePriceFeed(string memory symbol, address feedAddress, uint8 decimals) external onlyOwner {
        priceFeeds[symbol] = AggregatorV3Interface(feedAddress);
        feedDecimals[symbol] = decimals;
        emit PriceFeedUpdated(symbol, feedAddress);
    }
    
    /**
     * @dev Get price feed address for a symbol
     */
    function getPriceFeed(string memory symbol) external view returns (address) {
        return address(priceFeeds[symbol]);
    }
    
    /**
     * @dev Get price feed decimals for a symbol
     */
    function getFeedDecimals(string memory symbol) external view returns (uint8) {
        return feedDecimals[symbol];
    }
    
    /**
     * @dev Emergency pause function
     */
    function pause() external onlyOwner {
        _pause();
    }
    
    /**
     * @dev Unpause function
     */
    function unpause() external onlyOwner {
        _unpause();
    }
}
