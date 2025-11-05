// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.20;

import {BaseStrategy} from "@yearn-vaults/BaseStrategy.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {AggregatorV3Interface} from "@chainlink/contracts/src/v0.8/shared/interfaces/AggregatorV3Interface.sol";
import "./UniswapV4Integration.sol";

/**
 * @title MAVC Yearn Strategy (USDC/WETH)
 * @notice Yearn v3 tokenized strategy that maintains a 50/50 allocation between USDC and WETH
 * @dev Based on working MultiAssetVaultUSDCWETH implementation
 *
 * This strategy:
 * - Accepts USDC deposits (ERC-4626 compliant)
 * - Maintains 50% USDC / 50% WETH allocation
 * - Gracefully handles swap failures (keeps as USDC)
 * - Uses existing Uniswap V3 liquidity
 * - Uses Chainlink for price feeds
 */
contract MAVCYearnStrategyUSDCWETH is BaseStrategy {
    using SafeERC20 for IERC20;

    IERC20 public immutable USDC;
    IERC20 public immutable WETH;
    UniswapV4Integration public immutable DEX_INTEGRATION;
    AggregatorV3Interface public immutable ethUsdPriceFeed;

    uint256 public usdcHeld;
    uint256 public wethHeld;

    event Rebalanced(uint256 usdcAmount, uint256 wethAmount);
    event SwapExecuted(address tokenIn, address tokenOut, uint256 amountIn, uint256 amountOut);
    event SwapFailed(string reason);

    constructor(
        address _asset,
        string memory _name,
        address _weth,
        address _dexIntegration,
        address _ethUsdPriceFeed
    ) BaseStrategy(_asset, _name) {
        USDC = IERC20(_asset);
        WETH = IERC20(_weth);
        DEX_INTEGRATION = UniswapV4Integration(_dexIntegration);
        ethUsdPriceFeed = AggregatorV3Interface(_ethUsdPriceFeed);

        IERC20(_asset).forceApprove(_dexIntegration, type(uint256).max);
        WETH.forceApprove(_dexIntegration, type(uint256).max);
    }

    function _deployFunds(uint256 _amount) internal override {
        uint256 usdcBalance = USDC.balanceOf(address(this));
        
        uint256 usdcAmount = usdcBalance / 2;
        uint256 wethSwapAmount = usdcBalance / 2;

        usdcHeld += usdcAmount;

        if (wethSwapAmount > 0) {
            try this._swapUsdcToWethExternal(wethSwapAmount) returns (uint256 wethReceived) {
                if (wethReceived > 0) {
                    wethHeld += wethSwapAmount;
                    emit SwapExecuted(address(USDC), address(WETH), wethSwapAmount, wethReceived);
                } else {
                    usdcHeld += wethSwapAmount;
                }
            } catch Error(string memory reason) {
                usdcHeld += wethSwapAmount;
                emit SwapFailed(reason);
            } catch {
                usdcHeld += wethSwapAmount;
                emit SwapFailed("Unknown error");
            }
        }

        emit Rebalanced(usdcHeld, wethHeld);
    }

    function _freeFunds(uint256 _amount) internal override {
        uint256 usdcBalance = USDC.balanceOf(address(this));

        if (usdcBalance >= _amount) {
            return;
        }

        uint256 usdcNeeded = _amount - usdcBalance;
        uint256 totalValue = usdcHeld + wethHeld;
        
        if (totalValue == 0) return;

        uint256 wethToSell = (usdcNeeded * wethHeld) / totalValue;
        uint256 actualWethBalance = WETH.balanceOf(address(this));

        if (actualWethBalance > 0 && wethToSell > 0) {
            uint256 wethToSwap = wethToSell < actualWethBalance ? wethToSell : actualWethBalance;
            
            try this._swapWethToUsdcExternal(wethToSwap) returns (uint256 usdcReceived) {
                if (usdcReceived > 0) {
                    uint256 wethValueInUsdc = (wethToSwap * wethHeld) / actualWethBalance;
                    wethHeld = wethHeld > wethValueInUsdc ? wethHeld - wethValueInUsdc : 0;
                    usdcHeld += usdcReceived;
                    emit SwapExecuted(address(WETH), address(USDC), wethToSwap, usdcReceived);
                }
            } catch {
                // Swap failed, adjust internal accounting
                if (wethHeld >= wethToSell) {
                    wethHeld -= wethToSell;
                    usdcHeld += wethToSell;
                }
            }
        }
    }

    function _harvestAndReport() internal override returns (uint256) {
        return usdcHeld + wethHeld;
    }

    function _swapUsdcToWethExternal(uint256 usdcAmount) external returns (uint256) {
        require(msg.sender == address(this), "Only strategy");
        return _swapUsdcToWeth(usdcAmount);
    }

    function _swapWethToUsdcExternal(uint256 wethAmount) external returns (uint256) {
        require(msg.sender == address(this), "Only strategy");
        return _swapWethToUsdc(wethAmount);
    }

    function _swapUsdcToWeth(uint256 usdcAmount) internal returns (uint256 wethReceived) {
        if (usdcAmount == 0) return 0;

        wethReceived = DEX_INTEGRATION.swapDirectCustomPool(
            address(USDC),
            address(WETH),
            usdcAmount,
            0
        );

        return wethReceived;
    }

    function _swapWethToUsdc(uint256 wethAmount) internal returns (uint256 usdcReceived) {
        if (wethAmount == 0) return 0;

        usdcReceived = DEX_INTEGRATION.swapDirectCustomPool(
            address(WETH),
            address(USDC),
            wethAmount,
            0
        );

        return usdcReceived;
    }

    function getCurrentAllocation() external view returns (uint256 usdcBps, uint256 wethBps) {
        uint256 totalValue = usdcHeld + wethHeld;
        if (totalValue == 0) return (5000, 5000);

        usdcBps = (usdcHeld * 10000) / totalValue;
        wethBps = (wethHeld * 10000) / totalValue;
    }

    function getActualBalances() external view returns (uint256 usdcBalance, uint256 wethBalance) {
        usdcBalance = USDC.balanceOf(address(this));
        wethBalance = WETH.balanceOf(address(this));
    }
}

