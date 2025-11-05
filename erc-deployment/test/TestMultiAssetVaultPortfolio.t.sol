// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/MAVP.sol";
import "../src/UniswapV4Integration.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract TestMultiAssetVaultPortfolio is Test {
    // Sepolia token addresses sourced from https://eth-sepolia.blockscout.com
    address constant USDC = 0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238; // 6 decimals
    address constant SOL = 0x824CB8fC742F8D3300d29f16cA8beE94471169f5; // 9 decimals (Wrapped SOL)
    address constant ADA = 0x944c886956e09014d88E9bB6B91641F1bEF2BBe8; // 18 decimals
    address constant WETH = 0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14; // 18 decimals
    address constant DOGE = 0x183209DA02C281709A5BcD40188AaFfA04A7fEfD; // 18 decimals
    address constant WBNB = 0x343c0D9Fe222109f223bC8Fd9ff9C48351E63B90; // 18 decimals

    address internal deployer;
    UniswapV4Integration internal dex;
    MultiAssetVaultPortfolio internal vault;

    address internal user;

    function setUp() public {
        uint256 forkId = vm.createFork(vm.rpcUrl("sepolia"));
        vm.selectFork(forkId);

        deployer = makeAddr("deployer");
        user = makeAddr("user");

        vm.startPrank(deployer);
        dex = new UniswapV4Integration(deployer);

        address[] memory assets = new address[](5);
        assets[0] = SOL;
        assets[1] = ADA;
        assets[2] = WETH;
        assets[3] = DOGE;
        assets[4] = WBNB;

        vault = new MultiAssetVaultPortfolio(USDC, assets, address(dex), "Multi Asset Vault USDC Basket", "MAVP");
        vm.stopPrank();

        // Provide liquidity to the DEX integration so custom pools can be created
        _prefundDex();

        // Fund user with USDC for deposits
        deal(USDC, user, 1_000_000 * 1e6); // 1M USDC
    }

    function testDepositAndRedeemFiveAssetBasket() public {
        uint256 depositAmount = 1_000 * 1e6; // 1,000 USDC

        vm.startPrank(user);
        IERC20(USDC).approve(address(vault), depositAmount);
        uint256 mintedShares = vault.deposit(depositAmount, user);
        vm.stopPrank();

        assertGt(mintedShares, 0, "Shares should be minted");
        assertApproxEqAbs(vault.totalAssets(), depositAmount, 5 * 1e6, "Total assets tracks deposit");

        // Ensure each target asset received liquidity
        for (uint256 i = 0; i < 5; ++i) {
            (address token,, uint256 tokenBalance, uint256 bookValue) = vault.getAssetInfo(i);
            assertTrue(token != address(0), "Token address not set");
            assertGt(tokenBalance, 0, "Token balance should grow");
            assertGt(bookValue, 0, "Book value recorded");
        }

        // Redeem half the shares and ensure user receives USDC
        uint256 halfShares = mintedShares / 2;
        vm.startPrank(user);
        uint256 usdcReceived = vault.redeem(halfShares, user, user);
        vm.stopPrank();

        assertGt(usdcReceived, 0, "User should receive USDC on redeem");
        assertApproxEqAbs(vault.totalAssets(), depositAmount - usdcReceived, 10 * 1e6, "Assets drop after redeem");
    }

    function _prefundDex() internal {
        uint256 usdcLiquidity = 500_000 * 1e6;
        uint256 solLiquidity = 50_000 * 1e9;
        uint256 adaLiquidity = 500_000 * 1e18;
        uint256 wethLiquidity = 1_000 * 1e18;
        uint256 dogeLiquidity = 5_000_000 * 1e18;
        uint256 wbnbLiquidity = 1_000 * 1e18;

        deal(USDC, address(dex), usdcLiquidity);
        deal(SOL, address(dex), solLiquidity);
        deal(ADA, address(dex), adaLiquidity);
        deal(WETH, address(dex), wethLiquidity);
        deal(DOGE, address(dex), dogeLiquidity);
        deal(WBNB, address(dex), wbnbLiquidity);
    }
}
