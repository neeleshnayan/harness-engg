// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/MultiAssetVaultUSDCWETH.sol";
import "../src/ChainlinkPriceOracle.sol";
import "../src/UniswapV4Integration.sol";
import "../src/MockUSDC.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract MAVCPricingTest is Test {
    MultiAssetVaultUSDCWETH vault;
    ChainlinkPriceOracle oracle;
    UniswapV4Integration dex;
    MockUSDC usdc;
    IERC20 weth;
    
    address user = address(0x1234);
    
    function setUp() public {
        usdc = new MockUSDC();
        
        weth = IERC20(address(0x5678));
        
        oracle = new ChainlinkPriceOracle(address(this));
        
        dex = new UniswapV4Integration(address(this));
        
        vault = new MultiAssetVaultUSDCWETH(
            address(usdc),
            address(weth),
            address(dex),
            address(oracle),
            "Multi Asset Vault",
            "MAVC"
        );
        
        usdc.mint(user, 1000 * 1e6);
    }
    
    function testMAVCPriceCalculation() public view {
        uint256 mavcPrice = vault.getMAVCPrice();
        
        uint256 usdcPrice = oracle.getUsdcPrice();
        uint256 ethPrice = oracle.getEthPrice();
        
        uint256 expectedPrice = (5 * usdcPrice / 1000) + (5 * ethPrice / 1000);
        
        assertEq(mavcPrice, expectedPrice, "MAVC price calculation incorrect");
        
        console.log("USDC Price (USD):", usdcPrice);
        console.log("ETH Price (USD):", ethPrice);
        console.log("MAVC Price (USD):", mavcPrice);
        console.log("Formula: 0.005 * USDC + 0.005 * ETH");
    }
    
    function testShareCalculation() public {
        uint256 depositAmount = 100 * 1e6;
        
        vm.startPrank(user);
        usdc.approve(address(vault), depositAmount);
        
        uint256 sharesBefore = vault.balanceOf(user);
        assertEq(sharesBefore, 0, "User should have no shares initially");
        
        uint256 mavcPrice = vault.getMAVCPrice();
        console.log("MAVC Price:", mavcPrice);
        console.log("Deposit Amount:", depositAmount);
        
        uint256 expectedShares = (depositAmount * 1e8 * 1e18) / (mavcPrice * 1e6);
        console.log("Expected Shares:", expectedShares);
        
        vault.deposit(depositAmount, user);
        
        uint256 sharesAfter = vault.balanceOf(user);
        console.log("Actual Shares:", sharesAfter);
        
        assertGt(sharesAfter, 0, "User should have shares after deposit");
        vm.stopPrank();
    }
    
    function testInverseCalculation() public view {
        uint256 testShares = 10 * 1e18;
        
        uint256 mavcPrice = vault.getMAVCPrice();
        
        uint256 expectedAssets = (testShares * mavcPrice * 1e6) / (1e8 * 1e18);
        
        console.log("Test Shares:", testShares / 1e18);
        console.log("MAVC Price:", mavcPrice);
        console.log("Expected Assets (USDC):", expectedAssets / 1e6);
        
        uint256 calculatedShares = (expectedAssets * 1e8 * 1e18) / (mavcPrice * 1e6);
        
        assertApproxEqAbs(calculatedShares, testShares, 1e10, "Round trip calculation should match");
    }
}

