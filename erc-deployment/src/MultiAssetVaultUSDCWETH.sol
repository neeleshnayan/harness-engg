// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/extensions/ERC4626.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "./ChainlinkPriceOracle.sol";
import "./UniswapV4Integration.sol";
import "forge-std/console.sol";

/**
 * @title MultiAssetVaultUSDCWETH
 * @dev ERC-4626 compliant vault for 50/50 USDC/WETH allocation
 * @notice Uses existing Uniswap V3 liquidity for real swaps
 */
contract MultiAssetVaultUSDCWETH is ERC4626, ReentrancyGuard, Pausable, Ownable {
    using SafeERC20 for IERC20;
    
    IERC20 public immutable USDC;
    IERC20 public immutable WETH;
    
    UniswapV4Integration public immutable DEX_INTEGRATION;
    ChainlinkPriceOracle public immutable PRICE_ORACLE;
    
    uint256 public usdcHeld;
    uint256 public wethHeld;

    uint256 public strategyPriceUSD;
    uint256 public lastPriceUpdate;
    uint256 public constant PRICE_UPDATE_INTERVAL = 30 minutes;

    event Rebalance(uint256 usdcAmount, uint256 wethAmount);
    event AllocationUpdate(uint256 usdcPercent, uint256 wethPercent);
    event StrategyPriceUpdated(uint256 newPrice, uint256 timestamp);
    
    constructor(
        address _usdc,
        address _weth,
        address _dexIntegration,
        address _priceOracle,
        string memory _name,
        string memory _symbol
    ) ERC4626(IERC20(_usdc)) ERC20(_name, _symbol) Ownable(msg.sender) {
        USDC = IERC20(_usdc);
        WETH = IERC20(_weth);
        DEX_INTEGRATION = UniswapV4Integration(_dexIntegration);
        PRICE_ORACLE = ChainlinkPriceOracle(_priceOracle);

        _updateStrategyPrice();
    }
    
    /**
     * @dev Calculate shares based on formula: 1 MAVC = 0.005*USDC_price + 0.005*WETH_price
     * @param assets Amount of USDC deposited (6 decimals)
     * @return shares Amount of MAVC shares (18 decimals)
     */
    function _calculateShares(uint256 assets) internal view returns (uint256 shares) {
        uint256 usdcPriceUSD = PRICE_ORACLE.getUsdcPrice();
        uint256 ethPriceUSD = PRICE_ORACLE.getEthPrice();
        
        uint256 mavcPriceUSD = (5 * usdcPriceUSD / 1000) + (5 * ethPriceUSD / 1000);
        
        shares = (assets * 1e8 * 1e18) / (mavcPriceUSD * 1e6);
        
        return shares;
    }
    
    /**
     * @dev Calculate assets based on shares using inverse formula
     * @param shares Amount of MAVC shares (18 decimals)
     * @return assets Amount of USDC (6 decimals)
     */
    function _calculateAssets(uint256 shares) internal view returns (uint256 assets) {
        uint256 usdcPriceUSD = PRICE_ORACLE.getUsdcPrice();
        uint256 ethPriceUSD = PRICE_ORACLE.getEthPrice();
        
        uint256 mavcPriceUSD = (5 * usdcPriceUSD / 1000) + (5 * ethPriceUSD / 1000);
        
        assets = (shares * mavcPriceUSD * 1e6) / (1e8 * 1e18);
        
        return assets;
    }
    
    /**
     * @dev Deposit USDC and split 50/50 into USDC/WETH allocation
     */
    function deposit(uint256 assets, address receiver) 
        public 
        override 
        nonReentrant 
        whenNotPaused 
        returns (uint256) 
    {
        require(assets > 0, "Amount must be > 0");
        
        USDC.safeTransferFrom(msg.sender, address(this), assets);
        
        uint256 shares = _calculateShares(assets);
        require(shares > 0, "Shares must be > 0");
        
        // Split 50/50 - half stays as USDC, half gets swapped to WETH
        uint256 usdcAmount = assets / 2; // 50% stays as USDC
        uint256 wethSwapAmount = assets / 2; // 50% to be swapped to WETH
        
        // Update USDC holdings
        usdcHeld += usdcAmount;
        
        // Try to swap half to WETH using existing liquidity pool
        if (wethSwapAmount > 0) {
            console.log("Attempting to swap %s USDC to WETH", wethSwapAmount / 1e6);
            try this._swapUsdcToWethExternal(wethSwapAmount) returns (uint256 wethReceived) {
                if (wethReceived > 0) {
                    // Track the WETH swap amount in USDC terms for internal accounting
                    wethHeld += wethSwapAmount; // Track the USDC value that was converted to WETH
                // Format WETH properly for display
                if (wethReceived < 1e15) { // Less than 0.001 WETH
                    console.log("SUCCESS: Swapped %s USDC to %s wei WETH", wethSwapAmount / 1e6, wethReceived);
                } else {
                    uint256 wholePart = wethReceived / 1e18;
                    uint256 decimalPart = (wethReceived % 1e18) / 1e12; // Get 6 decimal places
                    console.log("SUCCESS: Swapped %s USDC to %s.%s WETH", wethSwapAmount / 1e6, wholePart, decimalPart);
                }
                } else {
                    // Swap returned zero output - treat as failure and keep funds as USDC
                    usdcHeld += wethSwapAmount;
                    console.log("SWAP SKIPPED: Received 0 WETH, retained %s USDC", wethSwapAmount / 1e6);
                }
            } catch Error(string memory reason) {
                console.log("SWAP FAILED: %s", reason);
                // Keep as USDC when swap fails
                usdcHeld += wethSwapAmount;
            } catch {
                console.log("SWAP FAILED: Unknown error");
                // Keep as USDC when swap fails
                usdcHeld += wethSwapAmount;
            }
        }
        
        // Mint shares to receiver
        _mint(receiver, shares);
        
        console.log("Share calculation: %s USDC -> %s shares", assets / 1e6, shares / 1e18);
        console.log("Total supply after mint: %s shares", totalSupply() / 1e18);
        console.log("Total assets in vault: %s USDC", totalAssets() / 1e6);
        
        emit Deposit(msg.sender, receiver, assets, shares);
        return shares;
    }
    
    /**
     * @dev Withdraw proportionally from both USDC and WETH holdings  
     */
    function withdraw(uint256 assets, address receiver, address owner) 
        public 
        override 
        nonReentrant 
        whenNotPaused 
        returns (uint256) 
    {
        require(assets > 0, "Amount must be > 0");
        
        uint256 shares = _calculateShares(assets);
        require(shares > 0, "Shares must be > 0");
        
        if (msg.sender != owner) {
            uint256 allowed = allowance(owner, msg.sender);
            if (allowed != type(uint256).max) {
                require(allowed >= shares, "Insufficient allowance");
                _approve(owner, msg.sender, allowed - shares);
            }
        }
        
        _burn(owner, shares);
        
        // Calculate proportional withdrawal
        uint256 totalValue = totalAssets();
        require(totalValue > 0, "No assets to withdraw");
        require(assets <= totalValue, "Insufficient assets");
        
        // Calculate proportional withdrawal from internal accounting
        uint256 usdcToWithdraw = (assets * usdcHeld) / totalValue;
        uint256 wethToWithdraw = (assets * wethHeld) / totalValue;
        
        // Ensure we don't withdraw more than we have
        require(usdcToWithdraw <= usdcHeld, "Insufficient USDC holdings");
        require(wethToWithdraw <= wethHeld, "Insufficient WETH holdings");
        
        // Update internal accounting BEFORE transfer
        usdcHeld = usdcHeld - usdcToWithdraw;
        wethHeld = wethHeld - wethToWithdraw;
        
        // Withdraw USDC portion
        if (usdcToWithdraw > 0) {
            USDC.safeTransfer(receiver, usdcToWithdraw);
        }
        
        // Withdraw WETH portion (convert to USDC first if we have actual WETH)
        if (wethToWithdraw > 0) {
            uint256 actualWethBalance = WETH.balanceOf(address(this));
            if (actualWethBalance > 0) {
                // Try to swap WETH back to USDC
                try this._swapWethToUsdcExternal(actualWethBalance) returns (uint256 usdcFromWeth) {
                    USDC.safeTransfer(receiver, usdcFromWeth);
                } catch {
                    // If swap fails, just give equivalent USDC value
                    USDC.safeTransfer(receiver, wethToWithdraw);
                }
            } else {
                // No actual WETH, just give USDC equivalent
                USDC.safeTransfer(receiver, wethToWithdraw);
            }
        }
        
        emit Withdraw(msg.sender, receiver, owner, assets, shares);
        return shares;
    }
    
    /**
     * @dev Total assets in USDC terms
     */
    function totalAssets() public view override returns (uint256) {
        return usdcHeld + wethHeld;
    }
    
    /**
     * @dev Override redeem to handle share to asset conversion properly
     */
    function redeem(uint256 shares, address receiver, address owner)
        public
        override
        nonReentrant
        whenNotPaused
        returns (uint256)
    {
        require(shares > 0, "Shares must be > 0");
        
        uint256 assets = _calculateAssets(shares);
        require(assets > 0, "Assets must be > 0");
        
        if (msg.sender != owner) {
            uint256 allowed = allowance(owner, msg.sender);
            if (allowed != type(uint256).max) {
                require(allowed >= shares, "Insufficient allowance");
                _approve(owner, msg.sender, allowed - shares);
            }
        }
        
        // Burn shares first
        _burn(owner, shares);
        
        // Calculate proportional withdrawal
        uint256 totalValue = totalAssets();
        if (totalValue == 0 || assets == 0) {
            return assets; // Nothing to withdraw
        }
        
        // Calculate proportional withdrawal from internal accounting
        uint256 usdcToWithdraw = (assets * usdcHeld) / totalValue;
        uint256 wethToWithdraw = (assets * wethHeld) / totalValue;
        
        // Update internal accounting BEFORE transfer
        if (usdcToWithdraw > 0) {
            usdcHeld = usdcHeld - usdcToWithdraw;
            USDC.safeTransfer(receiver, usdcToWithdraw);
        }
        
        if (wethToWithdraw > 0) {
            wethHeld = wethHeld - wethToWithdraw;
            
            uint256 actualWethBalance = WETH.balanceOf(address(this));
            if (actualWethBalance > 0) {
                // Try to swap WETH back to USDC
                try this._swapWethToUsdcExternal(actualWethBalance) returns (uint256 usdcFromWeth) {
                    USDC.safeTransfer(receiver, usdcFromWeth);
                } catch {
                    // If swap fails, just give equivalent USDC value
                    USDC.safeTransfer(receiver, wethToWithdraw);
                }
            } else {
                // No actual WETH, just give USDC equivalent
                USDC.safeTransfer(receiver, wethToWithdraw);
            }
        }
        
        emit Withdraw(msg.sender, receiver, owner, assets, shares);
        return assets;
    }
    
    function getStrategyPrice() public view returns (uint256 strategyPrice) {
        uint256 usdcPriceUSD = PRICE_ORACLE.getUsdcPrice();
        uint256 ethPriceUSD = PRICE_ORACLE.getEthPrice();

        strategyPrice = (5 * usdcPriceUSD / 1000) + (5 * ethPriceUSD / 1000);

        return strategyPrice;
    }

    function getCachedStrategyPrice() external view returns (uint256 price, uint256 lastUpdate) {
        return (strategyPriceUSD, lastPriceUpdate);
    }

    function updateStrategyPrice() external returns (uint256 newPrice) {
        return _updateStrategyPrice();
    }

    function _updateStrategyPrice() internal returns (uint256 newPrice) {
        require(
            lastPriceUpdate == 0 || block.timestamp >= lastPriceUpdate + PRICE_UPDATE_INTERVAL,
            "Price update too soon"
        );

        uint256 usdcPriceUSD = PRICE_ORACLE.getUsdcPrice();
        uint256 ethPriceUSD = PRICE_ORACLE.getEthPrice();

        newPrice = (5 * usdcPriceUSD / 1000) + (5 * ethPriceUSD / 1000);

        strategyPriceUSD = newPrice;
        lastPriceUpdate = block.timestamp;

        emit StrategyPriceUpdated(newPrice, block.timestamp);

        return newPrice;
    }
    
    /**
     * @dev Get current allocation percentages
     */
    function getCurrentAllocation() public view returns (uint256 usdcBps, uint256 wethBps) {
        uint256 total = totalAssets();
        if (total == 0) return (5000, 5000);
        
        usdcBps = (usdcHeld * 10000) / total;
        wethBps = (wethHeld * 10000) / total;
    }
    
    /**
     * @dev External wrapper for USDC to WETH swap
     */
    function _swapUsdcToWethExternal(uint256 usdcAmount) external returns (uint256 wethReceived) {
        require(msg.sender == address(this), "Only vault can call");
        return _swapUsdcToWeth(usdcAmount);
    }
    
    /**
     * @dev External wrapper for WETH to USDC swap
     */
    function _swapWethToUsdcExternal(uint256 wethAmount) external returns (uint256 usdcReceived) {
        require(msg.sender == address(this), "Only vault can call");
        return _swapWethToUsdc(wethAmount);
    }
    
    /**
     * @dev Internal function to swap USDC to WETH using existing liquidity
     */
    function _swapUsdcToWeth(uint256 usdcAmount) internal returns (uint256 wethReceived) {
        if (usdcAmount == 0) return 0;
        
        console.log("Vault: Starting USDC to WETH swap for %s USDC", usdcAmount / 1e6);
        
        // Approve DEX integration to spend USDC tokens
        USDC.approve(address(DEX_INTEGRATION), usdcAmount);
        console.log("Vault: Approved DEX integration to spend %s USDC", usdcAmount / 1e6);
        
        // Use existing WETH/USDC pool for direct swap
        console.log("Vault: Calling DEX integration direct swap using existing pool...");
        wethReceived = DEX_INTEGRATION.swapDirectCustomPool(
            address(USDC),
            address(WETH),
            usdcAmount,
            0 // No minimum for testing
        );
        // Format WETH properly - show in wei if less than 0.001 WETH
        if (wethReceived < 1e15) { // Less than 0.001 WETH
            console.log("Vault: DEX integration returned %s wei WETH", wethReceived);
        } else {
            // Show with 6 decimal places for better precision
            uint256 wholePart = wethReceived / 1e18;
            uint256 decimalPart = (wethReceived % 1e18) / 1e12; // Get 6 decimal places
            console.log("Vault: DEX integration returned %s.%s WETH", wholePart, decimalPart);
        }
        
        return wethReceived;
    }
    
    /**
     * @dev Internal function to swap WETH to USDC using existing liquidity
     */
    function _swapWethToUsdc(uint256 wethAmount) internal returns (uint256 usdcReceived) {
        if (wethAmount == 0) return 0;
        
        console.log("Vault: Starting WETH to USDC swap for %s WETH", wethAmount / 1e18);
        
        // Approve DEX integration to spend WETH tokens
        WETH.approve(address(DEX_INTEGRATION), wethAmount);
        
        // Use existing WETH/USDC pool for direct swap
        usdcReceived = DEX_INTEGRATION.swapDirectCustomPool(
            address(WETH),
            address(USDC),
            wethAmount,
            0 // No minimum for testing
        );
        
        return usdcReceived;
    }
    
    /**
     * @dev Get actual token balances in the vault
     */
    function getActualBalances() external view returns (uint256 usdcBalance, uint256 wethBalance) {
        usdcBalance = USDC.balanceOf(address(this));
        wethBalance = WETH.balanceOf(address(this));
    }
    
    /**
     * @dev Emergency function to recover tokens
     */
    function emergencyWithdraw() external onlyOwner {
        uint256 usdcBalance = USDC.balanceOf(address(this));
        uint256 wethBalance = WETH.balanceOf(address(this));
        
        if (usdcBalance > 0) {
            USDC.safeTransfer(owner(), usdcBalance);
        }
        if (wethBalance > 0) {
            WETH.safeTransfer(owner(), wethBalance);
        }
    }
}
