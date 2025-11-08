// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/extensions/ERC4626.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";
import "./UniswapV4Integration.sol";
import "./MAVPPriceOracle.sol";

/**
 * @title MultiAssetVaultPortfolio
 * @dev ERC-4626 vault that converts USDC deposits into a fixed 5-token basket (20% each)
 */
contract MultiAssetVaultPortfolio is ERC4626, ReentrancyGuard, Pausable, Ownable {
    using SafeERC20 for IERC20;

    uint256 private constant BPS = 10_000;
    uint256 private constant TARGET_COUNT = 5;

    IERC20 public immutable USDC;
    UniswapV4Integration public immutable DEX_INTEGRATION;
    MAVPPriceOracle public immutable PRICE_ORACLE;

    struct TargetAsset {
        IERC20 token;
        uint256 allocationBps;
        uint256 tokenBalance;
        uint256 usdcBookValue;
    }

    TargetAsset[] private _assets;
    mapping(address => uint256) private _assetIndexPlusOne;

    uint256 public usdcHeld;

    uint256 public strategyPriceUSD;
    uint256 public lastPriceUpdate;
    uint256 public constant PRICE_UPDATE_INTERVAL = 30 minutes;

    event AssetSwapIn(address indexed token, uint256 usdcAmountIn, uint256 tokenAmountOut);
    event AssetSwapOut(address indexed token, uint256 tokenAmountIn, uint256 usdcAmountOut);
    event AllocationInitialized(address indexed token, uint256 allocationBps);
    event StrategyPriceUpdated(uint256 newPrice, uint256 timestamp);

    constructor(
        address _usdc,
        address[] memory targetTokens,
        address _dexIntegration,
        address _PRICE_ORACLE,
        string memory _name,
        string memory _symbol
    ) ERC4626(IERC20(_usdc)) ERC20(_name, _symbol) Ownable(msg.sender) {
        require(_usdc != address(0), "USDC address zero");
        require(_dexIntegration != address(0), "DEX address zero");
        require(_PRICE_ORACLE != address(0), "Oracle address zero");
        require(targetTokens.length == TARGET_COUNT, "Need five assets");

        USDC = IERC20(_usdc);
        DEX_INTEGRATION = UniswapV4Integration(_dexIntegration);
        PRICE_ORACLE = MAVPPriceOracle(_PRICE_ORACLE);

        uint256 perAssetBps = BPS / TARGET_COUNT;
        for (uint256 i = 0; i < TARGET_COUNT; i++) {
            address tokenAddress = targetTokens[i];
            require(tokenAddress != address(0), "Token zero");
            require(tokenAddress != _usdc, "Token cannot be USDC");
            require(_assetIndexPlusOne[tokenAddress] == 0, "Duplicate token");

            _assetIndexPlusOne[tokenAddress] = _assets.length + 1; // 1-based indexing
            _assets.push(
                TargetAsset({token: IERC20(tokenAddress), allocationBps: perAssetBps, tokenBalance: 0, usdcBookValue: 0})
            );

            emit AllocationInitialized(tokenAddress, perAssetBps);
        }

        _updateStrategyPrice();
    }

    /*//////////////////////////////////////////////////////////////
                                VAULT LOGIC
    //////////////////////////////////////////////////////////////*/

    function deposit(uint256 assets, address receiver) public override nonReentrant whenNotPaused returns (uint256) {
        require(assets > 0, "Amount must be > 0");

        USDC.safeTransferFrom(msg.sender, address(this), assets);

        // Calculate shares based on MAVP price formula (like MAVC)
        // Formula: shares = (assets * 1e8 * 1e18) / (mavpPrice * 1e6)
        // assets: 6 decimals (USDC)
        // shares: 18 decimals (MAVP token)
        uint256 shares = _calculateSharesFromPrice(assets);
        require(shares > 0, "Shares must be > 0");

        // GAS OPTIMIZATION: Skip swaps during deposit to reduce gas costs
        // All deposited USDC is held in the vault
        // Swaps will be performed via separate rebalance() function
        usdcHeld += assets;

        _mint(receiver, shares);
        emit Deposit(msg.sender, receiver, assets, shares);
        return shares;
    }

    function withdraw(uint256 assets, address receiver, address owner)
        public
        override
        nonReentrant
        whenNotPaused
        returns (uint256)
    {
        require(assets > 0, "Amount must be > 0");
        uint256 totalValue = totalAssets();
        require(totalValue > 0, "Vault empty");

        uint256 supply = totalSupply();
        uint256 shares = Math.mulDiv(assets, supply, totalValue, Math.Rounding.Ceil);
        uint256 assetsRedeemed = _processRedemption(shares, receiver, owner);
        require(assetsRedeemed >= assets, "Under-withdrawn assets");
        return shares;
    }

    function redeem(uint256 shares, address receiver, address owner)
        public
        override
        nonReentrant
        whenNotPaused
        returns (uint256)
    {
        require(shares > 0, "Shares must be > 0");

       
        uint256 assets = _calculateAssetsFromPrice(shares);
        require(assets > 0, "Assets must be > 0");

        return _processRedemption(shares, receiver, owner);
    }

    function totalAssets() public view override returns (uint256 totalValue) {
        totalValue = usdcHeld;
        for (uint256 i = 0; i < _assets.length; i++) {
            totalValue += _assets[i].usdcBookValue;
        }
    }

    function convertToShares(uint256 assets) public view override returns (uint256) {
        if (assets == 0) {
            return 0;
        }
        // Use MAVP price formula for conversion
        return _calculateSharesFromPrice(assets);
    }

    function convertToAssets(uint256 shares) public view override returns (uint256) {
        if (shares == 0) {
            return 0;
        }
        // Use MAVP price formula for conversion
        return _calculateAssetsFromPrice(shares);
    }

    function previewDeposit(uint256 assets) public view override returns (uint256) {
        // Use MAVP price formula
        return _calculateSharesFromPrice(assets);
    }

    function previewMint(uint256 shares) public view override returns (uint256) {
        if (shares == 0) {
            return 0;
        }
        // Use MAVP price formula (inverse)
        return _calculateAssetsFromPrice(shares);
    }

    function previewWithdraw(uint256 assets) public view override returns (uint256) {
        if (assets == 0) {
            return 0;
        }
        // Use MAVP price formula
        return _calculateSharesFromPrice(assets);
    }

    function previewRedeem(uint256 shares) public view override returns (uint256) {
        // Use MAVP price formula (inverse)
        return _calculateAssetsFromPrice(shares);
    }

    /*//////////////////////////////////////////////////////////////
                            INTERNAL HELPERS
    //////////////////////////////////////////////////////////////*/

    function _processRedemption(uint256 shares, address receiver, address owner)
        internal
        returns (uint256 assetsRedeemed)
    {
        uint256 supply = totalSupply();
        require(supply > 0, "No shares");
        require(shares <= supply, "Shares exceed supply");

        if (msg.sender != owner) {
            uint256 allowed = allowance(owner, msg.sender);
            if (allowed != type(uint256).max) {
                require(allowed >= shares, "Insufficient allowance");
                _approve(owner, msg.sender, allowed - shares);
            }
        }

        _burn(owner, shares);

        uint256 usdcPayout = 0;

        if (usdcHeld > 0) {
            uint256 usdcPortion = Math.mulDiv(usdcHeld, shares, supply);
            if (usdcPortion > usdcHeld) {
                usdcPortion = usdcHeld;
            }
            if (usdcPortion > 0) {
                usdcHeld -= usdcPortion;
                usdcPayout += usdcPortion;
            }
        }

        for (uint256 i = 0; i < _assets.length; i++) {
            TargetAsset storage asset = _assets[i];
            if (asset.tokenBalance == 0 && asset.usdcBookValue == 0) {
                continue;
            }

            uint256 tokenAmountPortion = Math.mulDiv(asset.tokenBalance, shares, supply);
            if (tokenAmountPortion > asset.tokenBalance) {
                tokenAmountPortion = asset.tokenBalance;
            }

            uint256 bookValuePortion = Math.mulDiv(asset.usdcBookValue, shares, supply);
            if (bookValuePortion > asset.usdcBookValue) {
                bookValuePortion = asset.usdcBookValue;
            }

            if (tokenAmountPortion > 0) {
                uint256 usdcFromSwap = _swapAssetIntoUsdcInternal(i, tokenAmountPortion);
                asset.tokenBalance -= tokenAmountPortion;
                if (bookValuePortion >= asset.usdcBookValue) {
                    asset.usdcBookValue = 0;
                } else {
                    asset.usdcBookValue -= bookValuePortion;
                }
                usdcPayout += usdcFromSwap;
                emit AssetSwapOut(address(asset.token), tokenAmountPortion, usdcFromSwap);
            } else if (bookValuePortion > 0) {
                asset.usdcBookValue -= bookValuePortion;
            }
        }

        if (usdcPayout > 0) {
            USDC.safeTransfer(receiver, usdcPayout);
        }

        emit Withdraw(msg.sender, receiver, owner, usdcPayout, shares);
        return usdcPayout;
    }

    function _swapUsdcIntoAssetInternal(uint256 index, uint256 usdcAmount) internal returns (uint256 tokensReceived) {
        if (usdcAmount == 0) {
            return 0;
        }

        TargetAsset storage asset = _assets[index];
        
        // Match MAVC pattern: use approve() directly instead of forceApprove()
        // Approve DEX integration to spend USDC tokens
        USDC.approve(address(DEX_INTEGRATION), usdcAmount);
        
        // Use existing pool for direct swap (same pattern as MAVC)
        tokensReceived = DEX_INTEGRATION.swapDirectCustomPool(
            address(USDC),
            address(asset.token),
            usdcAmount,
            0 // No minimum for testing
        );
    }

    function _swapUsdcIntoAsset(uint256 index, uint256 usdcAmount) public returns (uint256) {
        require(msg.sender == address(this), "Only vault");
        return _swapUsdcIntoAssetInternal(index, usdcAmount);
    }

    function _swapAssetIntoUsdcInternal(uint256 index, uint256 tokenAmount) internal returns (uint256 usdcReceived) {
        if (tokenAmount == 0) {
            return 0;
        }

        TargetAsset storage asset = _assets[index];
        // Use approve() instead of forceApprove() for consistency
        asset.token.approve(address(DEX_INTEGRATION), tokenAmount);
        usdcReceived = DEX_INTEGRATION.swapDirectCustomPool(address(asset.token), address(USDC), tokenAmount, 0);
    }

    /*//////////////////////////////////////////////////////////////
                                ADMIN
    //////////////////////////////////////////////////////////////*/

    /**
     * @dev Rebalance vault by swapping USDC into target assets
     * @notice Can be called by owner when gas prices are low
     * @param maxGasPerSwap Maximum gas to use per swap (prevents runaway gas costs)
     */
    function rebalance(uint256 maxGasPerSwap) external onlyOwner nonReentrant {
        require(usdcHeld > 0, "No USDC to rebalance");
        require(maxGasPerSwap > 0, "Invalid gas limit");

        uint256 totalToRebalance = usdcHeld;
        uint256 successfulSwaps = 0;

        for (uint256 i = 0; i < _assets.length; i++) {
            TargetAsset storage asset = _assets[i];
            uint256 usdcPortion = (totalToRebalance * asset.allocationBps) / BPS;

            if (usdcPortion == 0) {
                continue;
            }

            // Try to swap with gas limit
            try this._swapUsdcIntoAsset{gas: maxGasPerSwap}(i, usdcPortion) returns (uint256 tokensReceived) {
                if (tokensReceived > 0) {
                    asset.tokenBalance += tokensReceived;
                    asset.usdcBookValue += usdcPortion;
                    usdcHeld -= usdcPortion;
                    successfulSwaps++;
                    emit AssetSwapIn(address(asset.token), usdcPortion, tokensReceived);
                }
            } catch {
                // Swap failed, keep as USDC
                continue;
            }
        }

        require(successfulSwaps > 0, "All swaps failed");
    }

    /**
     * @dev Rebalance a single asset (for granular control)
     */
    function rebalanceSingleAsset(uint256 assetIndex, uint256 usdcAmount) external onlyOwner nonReentrant {
        require(assetIndex < _assets.length, "Invalid asset index");
        require(usdcAmount > 0 && usdcAmount <= usdcHeld, "Invalid amount");

        TargetAsset storage asset = _assets[assetIndex];

        try this._swapUsdcIntoAsset(assetIndex, usdcAmount) returns (uint256 tokensReceived) {
            if (tokensReceived > 0) {
                asset.tokenBalance += tokensReceived;
                asset.usdcBookValue += usdcAmount;
                usdcHeld -= usdcAmount;
                emit AssetSwapIn(address(asset.token), usdcAmount, tokensReceived);
            } else {
                revert("Swap returned zero tokens");
            }
        } catch Error(string memory reason) {
            revert(reason);
        }
    }

    function pause() external onlyOwner {
        _pause();
    }

    function unpause() external onlyOwner {
        _unpause();
    }

    function emergencyWithdraw(address recipient) external onlyOwner {
        address to = recipient == address(0) ? owner() : recipient;

        uint256 usdcBalance = USDC.balanceOf(address(this));
        if (usdcBalance > 0) {
            USDC.safeTransfer(to, usdcBalance);
            usdcHeld = 0;
        }

        for (uint256 i = 0; i < _assets.length; i++) {
            TargetAsset storage asset = _assets[i];
            uint256 tokenBalance = asset.token.balanceOf(address(this));
            if (tokenBalance > 0) {
                asset.token.safeTransfer(to, tokenBalance);
                asset.tokenBalance = 0;
                asset.usdcBookValue = 0;
            }
        }
    }

    /*//////////////////////////////////////////////////////////////
                                VIEWS
    //////////////////////////////////////////////////////////////*/

    function assetCount() external view returns (uint256) {
        return _assets.length;
    }

    function getAssetInfo(uint256 index)
        external
        view
        returns (address token, uint256 allocationBps, uint256 tokenBalance, uint256 usdcBookValue)
    {
        require(index < _assets.length, "Index out of bounds");
        TargetAsset storage asset = _assets[index];
        return (address(asset.token), asset.allocationBps, asset.tokenBalance, asset.usdcBookValue);
    }

    function getCurrentAllocation() external view returns (address[] memory tokens, uint256[] memory allocationBps) {
        uint256 len = _assets.length + 1;
        tokens = new address[](len);
        allocationBps = new uint256[](len);

        uint256 totalValue = totalAssets();

        tokens[0] = address(USDC);
        allocationBps[0] = totalValue == 0 ? 0 : (usdcHeld * BPS) / totalValue;

        for (uint256 i = 0; i < _assets.length; i++) {
            TargetAsset storage asset = _assets[i];
            tokens[i + 1] = address(asset.token);
            allocationBps[i + 1] = totalValue == 0 ? 0 : (asset.usdcBookValue * BPS) / totalValue;
        }
    }

    /*//////////////////////////////////////////////////////////////
                            PRICE ORACLE FUNCTIONS
    //////////////////////////////////////////////////////////////*/


    function getStrategyPrice() external view returns (uint256 price) {
        return PRICE_ORACLE.getMAVPPriceUSD();
    }

    function getAssetPrices() external view returns (
        uint256 ethPrice,
        uint256 btcPrice,
        uint256 usdtPrice,
        uint256 uniPrice,
        uint256 linkPrice,
        uint256 strategyPrice
    ) {
        return PRICE_ORACLE.getAssetPrices();
    }

    function getStrategyPriceBreakdown() external view returns (
        uint256 ethContribution,
        uint256 btcContribution,
        uint256 usdtContribution,
        uint256 uniContribution,
        uint256 linkContribution
    ) {
        return PRICE_ORACLE.getMAVPBreakdown();
    }

    function arePriceFeedsHealthy() external view returns (bool) {
        return PRICE_ORACLE.arePriceFeedsHealthy();
    }

    function getCachedStrategyPrice() external view returns (uint256 price, uint256 timestamp) {
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

        newPrice = PRICE_ORACLE.getMAVPPriceUSD();
        strategyPriceUSD = newPrice;
        lastPriceUpdate = block.timestamp;

        emit StrategyPriceUpdated(newPrice, block.timestamp);

        return newPrice;
    }

    /*//////////////////////////////////////////////////////////////
                        PRICE CALCULATION HELPERS
    //////////////////////////////////////////////////////////////*/

    /**
     * @dev Calculate shares based on MAVP price formula
     * @param assets Amount of USDC deposited (6 decimals)
     * @return shares Amount of MAVP shares (18 decimals)
     */
    function _calculateSharesFromPrice(uint256 assets) internal view returns (uint256 shares) {
        uint256 strategyPrice = PRICE_ORACLE.getMAVPPriceUSD();
        require(strategyPrice > 0, "Invalid strategy price");

        shares = (assets * 1e8 * 1e18) / (strategyPrice * 1e6);
    }

    function _calculateAssetsFromPrice(uint256 shares) internal view returns (uint256 assets) {
        uint256 strategyPrice = PRICE_ORACLE.getMAVPPriceUSD();
        require(strategyPrice > 0, "Invalid strategy price");

        assets = (shares * strategyPrice * 1e6) / (1e8 * 1e18);
    }
}


