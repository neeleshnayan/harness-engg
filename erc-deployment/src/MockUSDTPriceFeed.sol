// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "chainlink-brownie-contracts/contracts/src/v0.8/shared/interfaces/AggregatorV3Interface.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title MockUSDTPriceFeed
 * @dev Mock Chainlink price feed for USDT/USD for testing on Sepolia testnet
 * USDT is pegged to USD so price should stay around $1.00
 */
contract MockUSDTPriceFeed is AggregatorV3Interface, Ownable {
    
    struct RoundData {
        uint80 roundId;
        int256 answer;
        uint256 startedAt;
        uint256 updatedAt;
        uint80 answeredInRound;
    }
    
    uint8 public constant override decimals = 8;
    string public constant override description = "USDT/USD Mock Price Feed";
    uint256 public constant override version = 1;
    
    uint80 private currentRoundId;
    mapping(uint80 => RoundData) private rounds;
    
    // USDT price around $1.00 USD (8 decimals = 100000000)
    int256 private constant INITIAL_PRICE = 100000000; // $1.00
    
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
     * @param newPrice New price in 8 decimals (e.g., 100000000 = $1.00)
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
     * @dev Simulate small price movements for USDT (stays close to $1.00)
     */
    function simulatePriceMovement() external onlyOwner {
        RoundData memory lastRound = rounds[currentRoundId];
        
        // Simulate very small ±0.5% price movement (USDT is stable)
        uint256 randomSeed = uint256(keccak256(abi.encodePacked(block.timestamp, block.prevrandao, currentRoundId)));
        bool isPositive = (randomSeed % 2) == 0;
        uint256 changePercent = (randomSeed % 50) + 1; // 0.01-0.5%
        
        int256 change = (lastRound.answer * int256(changePercent)) / 10000;
        int256 newPrice = isPositive ? lastRound.answer + change : lastRound.answer - change;
        
        // Keep USDT price within tight bounds ($0.98-$1.02)
        if (newPrice < 98000000) newPrice = 98000000;   // Min $0.98
        if (newPrice > 102000000) newPrice = 102000000; // Max $1.02
        
        updatePrice(newPrice);
    }
}
