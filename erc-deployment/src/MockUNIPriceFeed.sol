// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "chainlink-brownie-contracts/contracts/src/v0.8/shared/interfaces/AggregatorV3Interface.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title MockUNIPriceFeed
 * @dev Mock Chainlink price feed for UNI/USD for testing on Sepolia testnet
 * Simulates realistic UNI price movements around $7-10 USD
 */
contract MockUNIPriceFeed is AggregatorV3Interface, Ownable {
    
    struct RoundData {
        uint80 roundId;
        int256 answer;
        uint256 startedAt;
        uint256 updatedAt;
        uint80 answeredInRound;
    }
    
    uint8 public constant override decimals = 8;
    string public constant override description = "UNI/USD Mock Price Feed";
    uint256 public constant override version = 1;
    
    uint80 private currentRoundId;
    mapping(uint80 => RoundData) private rounds;
    
    // Mock UNI price around $8.50 USD (8 decimals = 850000000)
    int256 private constant INITIAL_PRICE = 850000000; // $8.50
    
    event AnswerUpdated(int256 indexed current, uint256 indexed roundId, uint256 updatedAt);
    event NewRound(uint256 indexed roundId, address indexed startedBy, uint256 startedAt);
    
    constructor() Ownable(msg.sender) {
        currentRoundId = 1;
        
        // Initialize with current price
        rounds[currentRoundId] = RoundData({
            roundId: currentRoundId,
            answer: INITIAL_PRICE,
            startedAt: block.timestamp,
            updatedAt: block.timestamp,
            answeredInRound: currentRoundId
        });
        
        emit NewRound(currentRoundId, msg.sender, block.timestamp);
        emit AnswerUpdated(INITIAL_PRICE, currentRoundId, block.timestamp);
    }
    
    function latestRoundData() external view override returns (
        uint80 roundId,
        int256 answer,
        uint256 startedAt,
        uint256 updatedAt,
        uint80 answeredInRound
    ) {
        RoundData memory round = rounds[currentRoundId];
        return (
            round.roundId,
            round.answer,
            round.startedAt,
            round.updatedAt,
            round.answeredInRound
        );
    }
    
    function getRoundData(uint80 _roundId) external view override returns (
        uint80 roundId,
        int256 answer,
        uint256 startedAt,
        uint256 updatedAt,
        uint80 answeredInRound
    ) {
        require(_roundId <= currentRoundId && _roundId > 0, "No data present");
        RoundData memory round = rounds[_roundId];
        return (
            round.roundId,
            round.answer,
            round.startedAt,
            round.updatedAt,
            round.answeredInRound
        );
    }
    
    /**
     * @dev Update the mock price (only owner)
     * @param newPrice New price in 8 decimals (e.g., 850000000 = $8.50)
     */
    function updatePrice(int256 newPrice) public onlyOwner {
        require(newPrice > 0, "Price must be positive");
        
        currentRoundId++;
        
        rounds[currentRoundId] = RoundData({
            roundId: currentRoundId,
            answer: newPrice,
            startedAt: block.timestamp,
            updatedAt: block.timestamp,
            answeredInRound: currentRoundId
        });
        
        emit NewRound(currentRoundId, msg.sender, block.timestamp);
        emit AnswerUpdated(newPrice, currentRoundId, block.timestamp);
    }
    
    /**
     * @dev Simulate price movement with some randomness (for testing)
     */
    function simulatePriceMovement() external onlyOwner {
        RoundData memory lastRound = rounds[currentRoundId];
        
        // Simulate ±5% price movement
        uint256 randomSeed = uint256(keccak256(abi.encodePacked(block.timestamp, block.prevrandao, currentRoundId)));
        bool isPositive = (randomSeed % 2) == 0;
        uint256 changePercent = (randomSeed % 5) + 1; // 1-5%
        
        int256 change = (lastRound.answer * int256(changePercent)) / 100;
        int256 newPrice = isPositive ? lastRound.answer + change : lastRound.answer - change;
        
        // Keep price within reasonable bounds ($5-$15)
        if (newPrice < 500000000) newPrice = 500000000; // Min $5.00
        if (newPrice > 1500000000) newPrice = 1500000000; // Max $15.00
        
        updatePrice(newPrice);
    }
}
