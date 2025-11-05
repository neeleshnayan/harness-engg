// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "forge-std/console.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

// Simplified version focusing on custom pool creation
interface IUniswapV3Factory {
    function createPool(address tokenA, address tokenB, uint24 fee) external returns (address pool);
    function getPool(address tokenA, address tokenB, uint24 fee) external view returns (address pool);
}

interface IUniswapV3Pool {
    function initialize(uint160 sqrtPriceX96) external;
}

/**
 * @title CustomPoolCreator
 * @dev Creates truly custom pools with different fee tiers to avoid existing pools
 */
contract CustomPoolCreator {
    using SafeERC20 for IERC20;

    address public constant UNISWAP_V3_FACTORY = 0x0227628f3F023bb0B980b67D528571c95c6DaC1c;

    // Fee tiers
    uint24 public constant FEE_LOW = 500;     // 0.05%
    uint24 public constant FEE_MEDIUM = 3000; // 0.3%
    uint24 public constant FEE_HIGH = 10000;  // 1%
    uint24 public constant FEE_CUSTOM = 2500; // 0.25% (custom)

    function createBrandNewPool(
        address tokenA,
        address tokenB
    ) external returns (address pool) {
        console.log("=== CREATING BRAND NEW CUSTOM POOL ===");
        console.log("TokenA: %s, TokenB: %s", tokenA, tokenB);

        // Try different fee tiers to find an unused one
        uint24[4] memory feeTiers = [FEE_LOW, FEE_CUSTOM, FEE_HIGH, 500];

        for (uint i = 0; i < feeTiers.length; i++) {
            address existingPool = IUniswapV3Factory(UNISWAP_V3_FACTORY).getPool(tokenA, tokenB, feeTiers[i]);

            if (existingPool == address(0)) {
                console.log("SUCCESS: Found unused fee tier %s bps", feeTiers[i]);

                // Create the new pool
                try IUniswapV3Factory(UNISWAP_V3_FACTORY).createPool(tokenA, tokenB, feeTiers[i]) returns (address newPool) {
                    pool = newPool;
                    console.log("SUCCESS: Created brand new pool at %s", pool);
                    console.log("Fee tier: %s bps", feeTiers[i]);

                    // Initialize with 1:1 ratio
                    uint160 sqrtPriceX96 = 79228162514264337593543950336;
                    IUniswapV3Pool(pool).initialize(sqrtPriceX96);
                    console.log("SUCCESS: Initialized new pool with 1:1 ratio");

                    return pool;

                } catch Error(string memory reason) {
                    console.log("ERROR: Pool creation failed: %s", reason);
                    continue;
                } catch {
                    console.log("ERROR: Pool creation failed with unknown error");
                    continue;
                }
            } else {
                console.log("Fee tier %s bps already used by pool %s", feeTiers[i], existingPool);
            }
        }

        console.log("ERROR: All fee tiers are taken - cannot create new pool");
        return address(0);
    }
}