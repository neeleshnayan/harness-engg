// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract MockWBTC is ERC20 {
    constructor() ERC20("Mock Wrapped Bitcoin", "WBTC") {
        _mint(msg.sender, 1000 * 10**8); // 1000 WBTC with 8 decimals
    }
    
    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
}
