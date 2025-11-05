// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/MultiAssetVault.sol";
import "../src/MockUSDC.sol";
import "../src/MockWBTC.sol";
import "../src/ChainlinkPriceOracle.sol";
import "../src/UniswapV4Integration.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";

contract MultiAssetVaultTest is Test {
    MultiAssetVault public vault;
    MockUSDC public usdc;
    MockWBTC public wbtc;
    
    address public owner = address(0x1);
    address public user1 = address(0x2);
    address public user2 = address(0x3);
    
    uint256 public constant INITIAL_USDC = 500000e6; // 500K USDC per user
    uint256 public constant INITIAL_BTC = 100e8; // 100 BTC
    
    // Mock oracle and DEX for testing
    ChainlinkPriceOracle public mockOracle;
    UniswapV4Integration public mockDex;
    
    function setUp() public {
        // Deploy mock tokens
        usdc = new MockUSDC();
        wbtc = new MockWBTC();
        
        // Deploy mock Chainlink oracle
        vm.prank(owner);
        mockOracle = new ChainlinkPriceOracle(owner);
        
        // Deploy mock DEX integration
        vm.prank(owner);
        mockDex = new UniswapV4Integration(owner);
        
        // Deploy vault with Chainlink oracle and DEX
        vm.prank(owner);
        vault = new MultiAssetVault(
            address(usdc),
            address(wbtc),
            address(mockOracle),
            address(mockDex),
            "Multi Asset Vault",
            "MAV"
        );
        
        // Distribute tokens to users
        bool success1 = usdc.transfer(user1, INITIAL_USDC);
        bool success2 = usdc.transfer(user2, INITIAL_USDC);
        require(success1 && success2, "USDC transfer failed");
        wbtc.mint(user1, INITIAL_BTC);
        wbtc.mint(user2, INITIAL_BTC);
        
        // Approve vault to spend tokens
        vm.prank(user1);
        usdc.approve(address(vault), type(uint256).max);
        
        vm.prank(user2);
        usdc.approve(address(vault), type(uint256).max);
    }
    
    function testInitialState() public view {
        assertEq(vault.owner(), owner);
        assertEq(address(vault.asset()), address(usdc));
        assertEq(vault.totalAssets(), 0);
    }
    
    function testDeposit() public {
        uint256 depositAmount = 1000e6; // 1000 USDC
        
        vm.prank(user1);
        uint256 shares = vault.deposit(depositAmount, user1);
        
        assertEq(shares, depositAmount); // 1:1 ratio initially
        assertEq(vault.balanceOf(user1), shares);
        assertEq(vault.totalAssets(), depositAmount);
        assertEq(usdc.balanceOf(address(vault)), depositAmount);
    }
    
    function testWithdraw() public {
        uint256 depositAmount = 1000e6; // 1000 USDC
        
        // Deposit first
        vm.prank(user1);
        vault.deposit(depositAmount, user1);
        
        uint256 initialBalance = usdc.balanceOf(user1);
        
        // Withdraw half
        vm.prank(user1);
        vault.withdraw(depositAmount / 2, user1, user1);
        
        assertEq(vault.balanceOf(user1), 500e6);
        assertEq(vault.totalAssets(), 500e6);
        assertEq(usdc.balanceOf(user1), initialBalance + 500e6);
    }
    
    function testPauseUnpause() public {
        vm.prank(owner);
        vault.pause();
        assertTrue(vault.paused());
        
        vm.prank(owner);
        vault.unpause();
        assertFalse(vault.paused());
    }
    
    function testAccessControl() public {
        vm.prank(user1);
        vm.expectRevert(abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, user1));
        vault.pause();
    }
}