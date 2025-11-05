// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.20;

import {BaseStrategy} from "@yearn-vaults/BaseStrategy.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {AggregatorV3Interface} from "@chainlink/contracts/src/v0.8/shared/interfaces/AggregatorV3Interface.sol";
import {ISwapRouter} from "@uniswap/v3-periphery/contracts/interfaces/ISwapRouter.sol";

/**
 * @title MAVC Yearn Strategy
 * @notice Yearn v3 tokenized strategy that maintains a 50/50 allocation between USDC and WBTC
 * @dev Implements vanilla MAVC (Multi-Asset Vault Composite) without RSI-based trading
 *
 * This strategy:
 * - Accepts USDC deposits (ERC-4626 compliant)
 * - Maintains 50% USDC / 50% WBTC allocation
 * - Rebalances when allocation drifts beyond threshold
 * - Uses Chainlink for BTC/USD price feeds
 * - Uses Uniswap V3 for USDC/WBTC swaps
 */
contract MAVCYearnStrategy is BaseStrategy {
    using SafeERC20 for IERC20;

    // ============ Constants ============

    /// @notice USDC token (6 decimals)
    IERC20 public immutable USDC;

    /// @notice Wrapped Bitcoin token (8 decimals)
    IERC20 public immutable WBTC;

    /// @notice Chainlink BTC/USD price feed (8 decimals)
    AggregatorV3Interface public immutable btcUsdPriceFeed;

    /// @notice Uniswap V3 Router
    ISwapRouter public immutable swapRouter;

    /// @notice Target allocation for USDC (in basis points, e.g., 5000 = 50%)
    uint256 public constant TARGET_USDC_BPS = 5000;

    /// @notice Target allocation for WBTC (in basis points, e.g., 5000 = 50%)
    uint256 public constant TARGET_WBTC_BPS = 5000;

    /// @notice Rebalance threshold (in basis points, e.g., 500 = 5% drift triggers rebalance)
    uint256 public constant REBALANCE_THRESHOLD_BPS = 500;

    /// @notice Uniswap V3 pool fee (0.3% = 3000)
    uint24 public constant POOL_FEE = 3000;

    /// @notice Maximum slippage for swaps (in basis points, e.g., 100 = 1%)
    uint256 public constant MAX_SLIPPAGE_BPS = 100;

    /// @notice Basis points denominator
    uint256 private constant BPS = 10000;

    // ============ Events ============

    event Rebalanced(uint256 usdcBalance, uint256 wbtcBalance, uint256 timestamp);
    event SwapExecuted(address tokenIn, address tokenOut, uint256 amountIn, uint256 amountOut);

    // ============ Constructor ============

    /**
     * @notice Initialize the MAVC Yearn Strategy
     * @param _asset The underlying asset (USDC)
     * @param _name The name of the strategy token
     * @param _wbtc The WBTC token address
     * @param _btcUsdPriceFeed Chainlink BTC/USD price feed
     * @param _swapRouter Uniswap V3 swap router
     */
    constructor(
        address _asset,
        string memory _name,
        address _wbtc,
        address _btcUsdPriceFeed,
        address _swapRouter
    ) BaseStrategy(_asset, _name) {
        USDC = IERC20(_asset);
        WBTC = IERC20(_wbtc);
        btcUsdPriceFeed = AggregatorV3Interface(_btcUsdPriceFeed);
        swapRouter = ISwapRouter(_swapRouter);

        // Approve Uniswap router to spend USDC and WBTC
        IERC20(_asset).forceApprove(_swapRouter, type(uint256).max);
        WBTC.forceApprove(_swapRouter, type(uint256).max);
    }

    // ============ BaseTokenizedStrategy Required Functions ============

    /**
     * @notice Deploy funds after a deposit or mint
     * @dev Called automatically after deposit/mint
     * @param _amount Amount of USDC to deploy
     */
    function _deployFunds(uint256 _amount) internal override {
        // After deposit, we have new USDC to deploy
        // Rebalance to maintain 50/50 allocation
        _rebalance();
    }

    /**
     * @notice Free funds for a withdrawal or redeem
     * @dev Called automatically during withdraw/redeem
     * @param _amount Amount of USDC needed
     */
    function _freeFunds(uint256 _amount) internal override {
        uint256 usdcBalance = USDC.balanceOf(address(this));

        // If we don't have enough USDC, sell WBTC to get it
        if (usdcBalance < _amount) {
            uint256 usdcNeeded = _amount - usdcBalance;
            _sellWBTCForUSDC(usdcNeeded);
        }
    }

    /**
     * @notice Harvest and report total assets
     * @dev Called during report() to calculate PnL
     * @return Total value of all assets in USDC terms
     */
    function _harvestAndReport() internal override returns (uint256) {
        // Calculate total value of USDC + WBTC (in USDC terms)
        return _totalAssetValue();
    }

    // ============ Internal Strategy Logic ============

    /**
     * @notice Calculate total asset value in USDC
     * @return Total value in USDC (6 decimals)
     */
    function _totalAssetValue() internal view returns (uint256) {
        uint256 usdcBalance = USDC.balanceOf(address(this));
        uint256 wbtcBalance = WBTC.balanceOf(address(this));

        // Convert WBTC to USD value
        uint256 wbtcValueInUsd = _wbtcToUsd(wbtcBalance);

        return usdcBalance + wbtcValueInUsd;
    }

    /**
     * @notice Get current BTC price from Chainlink
     * @return BTC price in USD (8 decimals)
     */
    function _getBtcPrice() internal view returns (uint256) {
        (, int256 price, , uint256 updatedAt, ) = btcUsdPriceFeed.latestRoundData();

        require(price > 0, "Invalid BTC price");
        require(block.timestamp - updatedAt < 1 hours, "Stale price data");

        return uint256(price);
    }

    /**
     * @notice Convert WBTC amount to USD value
     * @param wbtcAmount Amount of WBTC (8 decimals)
     * @return USD value (6 decimals, matching USDC)
     */
    function _wbtcToUsd(uint256 wbtcAmount) internal view returns (uint256) {
        if (wbtcAmount == 0) return 0;

        uint256 btcPrice = _getBtcPrice(); // 8 decimals

        // wbtcAmount (8 decimals) * btcPrice (8 decimals) / 1e8 / 1e2
        // = USDC amount (6 decimals)
        return (wbtcAmount * btcPrice) / 1e8 / 1e2;
    }

    /**
     * @notice Convert USD value to WBTC amount
     * @param usdAmount Amount in USD (6 decimals)
     * @return WBTC amount (8 decimals)
     */
    function _usdToWbtc(uint256 usdAmount) internal view returns (uint256) {
        if (usdAmount == 0) return 0;

        uint256 btcPrice = _getBtcPrice(); // 8 decimals

        // usdAmount (6 decimals) * 1e8 * 1e2 / btcPrice (8 decimals)
        // = WBTC amount (8 decimals)
        return (usdAmount * 1e8 * 1e2) / btcPrice;
    }

    /**
     * @notice Rebalance portfolio to 50/50 USDC/WBTC
     * @dev Only rebalances if drift exceeds threshold
     */
    function _rebalance() internal {
        uint256 totalValue = _totalAssetValue();
        if (totalValue == 0) return;

        uint256 usdcBalance = USDC.balanceOf(address(this));
        uint256 wbtcValueInUsd = _wbtcToUsd(WBTC.balanceOf(address(this)));

        // Calculate current allocations (in basis points)
        uint256 currentUsdcBps = (usdcBalance * BPS) / totalValue;
        uint256 currentWbtcBps = (wbtcValueInUsd * BPS) / totalValue;

        // Check if rebalancing is needed
        uint256 usdcDrift = currentUsdcBps > TARGET_USDC_BPS
            ? currentUsdcBps - TARGET_USDC_BPS
            : TARGET_USDC_BPS - currentUsdcBps;

        if (usdcDrift < REBALANCE_THRESHOLD_BPS) {
            return; // No rebalancing needed
        }

        // Calculate target balances
        uint256 targetUsdcValue = (totalValue * TARGET_USDC_BPS) / BPS;
        uint256 targetWbtcValue = (totalValue * TARGET_WBTC_BPS) / BPS;

        // Execute rebalance
        if (usdcBalance > targetUsdcValue) {
            // Too much USDC, buy WBTC
            uint256 usdcToSwap = usdcBalance - targetUsdcValue;
            _buyWBTCWithUSDC(usdcToSwap);
        } else {
            // Too much WBTC, sell for USDC
            uint256 wbtcValueToSwap = wbtcValueInUsd - targetWbtcValue;
            _sellWBTCForUSDC(wbtcValueToSwap);
        }

        emit Rebalanced(
            USDC.balanceOf(address(this)),
            WBTC.balanceOf(address(this)),
            block.timestamp
        );
    }

    /**
     * @notice Buy WBTC with USDC via Uniswap V3
     * @param usdcAmount Amount of USDC to spend (6 decimals)
     */
    function _buyWBTCWithUSDC(uint256 usdcAmount) internal {
        if (usdcAmount == 0) return;

        // Calculate minimum amount out with slippage protection
        uint256 expectedWbtc = _usdToWbtc(usdcAmount);
        uint256 minAmountOut = (expectedWbtc * (BPS - MAX_SLIPPAGE_BPS)) / BPS;

        ISwapRouter.ExactInputSingleParams memory params = ISwapRouter.ExactInputSingleParams({
            tokenIn: address(USDC),
            tokenOut: address(WBTC),
            fee: POOL_FEE,
            recipient: address(this),
            deadline: block.timestamp,
            amountIn: usdcAmount,
            amountOutMinimum: minAmountOut,
            sqrtPriceLimitX96: 0
        });

        try swapRouter.exactInputSingle(params) returns (uint256 amountOut) {
            emit SwapExecuted(address(USDC), address(WBTC), usdcAmount, amountOut);
        } catch {
            // Swap failed (likely no liquidity), continue without rebalancing
        }
    }

    /**
     * @notice Sell WBTC for USDC via Uniswap V3
     * @param usdcNeeded Amount of USDC needed (6 decimals)
     */
    function _sellWBTCForUSDC(uint256 usdcNeeded) internal {
        if (usdcNeeded == 0) return;

        // Calculate WBTC amount to sell
        uint256 wbtcToSell = _usdToWbtc(usdcNeeded);
        uint256 wbtcBalance = WBTC.balanceOf(address(this));

        if (wbtcToSell > wbtcBalance) {
            wbtcToSell = wbtcBalance;
        }

        if (wbtcToSell == 0) return;

        // Calculate minimum amount out with slippage protection
        uint256 minAmountOut = (usdcNeeded * (BPS - MAX_SLIPPAGE_BPS)) / BPS;

        ISwapRouter.ExactInputSingleParams memory params = ISwapRouter.ExactInputSingleParams({
            tokenIn: address(WBTC),
            tokenOut: address(USDC),
            fee: POOL_FEE,
            recipient: address(this),
            deadline: block.timestamp,
            amountIn: wbtcToSell,
            amountOutMinimum: minAmountOut,
            sqrtPriceLimitX96: 0
        });

        try swapRouter.exactInputSingle(params) returns (uint256 amountOut) {
            emit SwapExecuted(address(WBTC), address(USDC), wbtcToSell, amountOut);
        } catch {
            // Swap failed (likely no liquidity), continue without rebalancing
        }
    }

    // ============ Management Functions ============

    /**
     * @notice Manually trigger rebalance
     * @dev Only callable by management
     */
    function manualRebalance() external onlyManagement {
        _rebalance();
    }

    /**
     * @notice Get current portfolio allocation
     * @return usdcBps USDC allocation in basis points
     * @return wbtcBps WBTC allocation in basis points
     */
    function getCurrentAllocation() external view returns (uint256 usdcBps, uint256 wbtcBps) {
        uint256 totalValue = _totalAssetValue();
        if (totalValue == 0) return (0, 0);

        uint256 usdcBalance = USDC.balanceOf(address(this));
        uint256 wbtcValueInUsd = _wbtcToUsd(WBTC.balanceOf(address(this)));

        usdcBps = (usdcBalance * BPS) / totalValue;
        wbtcBps = (wbtcValueInUsd * BPS) / totalValue;
    }
}
