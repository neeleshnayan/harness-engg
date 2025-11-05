# Multi-Asset Vault (ERC-4626)


forge script script/DeployMAVP.s.sol:DeployMAVP --rpc-url https://sepolia.infura.io/v3/2f996d80c4664ac68e012f3052a31ee3 --broadcast   --verify   -vvvv --gas-limit 5000000


forge script test/TestMultiAssetVaultPortfolio.s.sol:TestMultiAssetVaultPortfolio --rpc-url https://eth-sepolia.g.alchemy.com/v2/M6S9rlQMfU-jEVs5scsDI --broadcast --verify


forge script test/TestMultiAssetVaultPortfolio.s.sol:TestMultiAssetVaultPortfolio --rpc-url https://sepolia.infura.io/v3/2f996d80c4664ac68e012f3052a31ee3 --broadcast --verify

forge script test/TestMultiAssetVaultPortfolio.s.sol:TestMultiAssetVaultPortfolio --rpc-url https://eth-sepolia.api.onfinality.io/rpc?apikey=507637d5-66a9-43a1-b97b-93c27b72f0dd --broadcast --verify



Complete smart-contract + frontend stack for a 50/50 USDC/WBTC ERC-4626 vault. The repo ships with Foundry contracts, a React control center, and an optional The Graph subgraph so you can redeploy and operate the vault from a clean machine in minutes.

## What's Inside
- `src/` - core solidity contracts (`MultiAssetVault.sol`, mocks, deployment helpers)
- `script/` - Foundry deployment scripts
- `test/` - unit, integration, and Chainlink-backed smoke tests
- `frontend/` - Vite + React dApp for interacting with the vault
- `subgraph/` - The Graph subgraph to surface historical vault metrics in the UI

---

## Redeploying On A Fresh Machine
The steps below assume a brand-new workstation (macOS, Linux, or Windows with WSL/Git Bash).

### 0. Prerequisites
Install the following once per machine:
- **Git** - clone the repository
- **Node.js 18+** (ships with `npm`)
- **Foundry** - Solidity build and scripting toolchain (`curl -L https://foundry.paradigm.xyz | bash` then `foundryup`)
- **Optional:** `@graphprotocol/graph-cli` (`npm install -g @graphprotocol/graph-cli`) if you plan to deploy the subgraph

### 1. Clone The Repository
```bash
git clone https://github.com/your-org/erc-deployment.git
cd erc-deployment
```

### 2. Configure Environment Variables
Create a root-level `.env` file (never commit real secrets):
```ini
PRIVATE_KEY=0xyour_private_key_without_0x
SEPOLIA_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/YOUR_KEY
MAINNET_RPC_URL=https://mainnet.infura.io/v3/YOUR_KEY
ETHERSCAN_API_KEY=YOUR_ETHERSCAN_KEY
# Optional convenience vars
WALLET_ADDRESS=0xYourEOA
DAI_USD_FEED=0x...
EUR_USD_FEED=0x...
GAS_PRICE=20000000000
GAS_LIMIT=8000000
```
Load the file before running scripts (`source .env` on macOS/Linux, `set -a; source .env` in Git Bash).

### 3. Install Solidity Dependencies
```bash
forge install
forge build
forge test -vv
```
If you need Alchemy or Infura keys for tests, ensure they are present in `.env` before running `forge test`.

### 4. Deploy The Vault
Pick a target network:
```bash
# Local (Anvil)
anvil # run in a separate terminal
forge script script/Deploy.s.sol --rpc-url http://localhost:8545 --broadcast

# Sepolia (Alchemy example)
forge script script/Deploy.s.sol \
  --rpc-url https://eth-sepolia.g.alchemy.com/v2/YOUR_KEY \
  --broadcast --verify

# Chainlink-backed integration script
forge script test/TestVaultWithChainlink.s.sol:TestVaultWithChainlink \
  --rpc-url $SEPOLIA_RPC_URL --broadcast
```
Record the deployed vault, USDC, and WBTC addresses; you will feed them to the frontend and subgraph.

### 5. Set Up The Frontend
```bash
cd frontend
cp .env.example .env # edit with the addresses from step 4
npm install
```
Populate `frontend/.env` with:
```
VITE_CHAIN_ID=11155111               # or your target chain ID
VITE_RPC_URL=https://...
VITE_VAULT_ADDRESS=0xDeployedVault
VITE_USDC_ADDRESS=0xToken
VITE_WETH_ADDRESS=0xToken
VITE_MAVP_VAULT_ADDRESS=0xMAVPVault   # for the 5-token portfolio vault
VITE_ORACLE_ADDRESS=0xChainlinkOracle # optional, for enhanced price feeds
VITE_SUBGRAPH_URL=https://...        # optional, leave blank until deployed
VITE_WALLETCONNECT_PROJECT_ID=...
```
Run the dApp locally:
```bash
npm run dev
```
The UI is available at `http://localhost:5173` and blocks state-changing actions until all required addresses are present.

### 6. Build The Frontend (Generate `dist/`)
```bash
# still inside frontend/
npm run build
```
The production bundle is emitted to `frontend/dist`. Copy the folder to any static host (S3 + CloudFront, Netlify, Vercel static, nginx). To sanity-check before deploying:
```bash
npm run preview
```

### 7. (Optional) Deploy The Graph Subgraph
```bash
cd subgraph
npm install
# edit subgraph.yaml with the vault address and start block
npm run codegen
npm run build
npm run deploy -- --access-token YOUR_TOKEN
```
Use the resulting HTTPS endpoint as `VITE_SUBGRAPH_URL` in the frontend to unlock analytics.

---

## Common Operations
- **Re-run tests** after contract changes: `forge test -vv`
- **Manual flows on Anvil**: `chmod +x test_vault.sh && ./test_vault.sh`
- **Integration script**: `forge script test/TestVaultInteraction.s.sol --rpc-url http://localhost:8545 --broadcast`

## Contract Highlights
- ERC-4626 compliant vault with 50/50 USDC/WBTC allocation
- ReentrancyGuard, Pausable, and Ownable protections
- Mock price feeds for local testing with easy Chainlink swap-in
- Auto-rebalancing helpers with 5% tolerance

## Frontend Highlights
- **Dual Vault Interface** - Navigate between MAVC (50/50 USDC/WETH) and MAVP (5-token portfolio) vaults
- Wallet connections (MetaMask, Coinbase Wallet, WalletConnect)
- Real-time vault telemetry via wagmi and react-query
- **Chainlink Oracle Integration** - Live ETH/USD and USDC/USD price feeds for accurate vault share pricing
- Guided deposit and withdrawal with allowance management
- Optional subgraph dashboard for historical insights

## Chainlink Integration
The frontend now includes live Chainlink price feeds for accurate vault share pricing:

### Formula
Vault share price calculation follows: `1 MAV = (0.5×USDC) + (0.5×WETH/USDC_value)`

### Price Feeds Used (Sepolia Testnet)
- **ETH/USD**: `0x694AA1769357215DE4FAC081bf1f309aDC325306`
- **USDC/USD**: `0xA2F78ab2355fe2f984D808B5CeE7FD0A93D5270E`

### Features
- Real-time price fetching from Chainlink oracles
- Automatic fallback to basic calculation if oracle data unavailable
- Visual indicator showing oracle health status (green = Chainlink active, amber = fallback)
- Live ETH and USDC prices displayed in the vault overview

### Implementation
- `useChainlinkPrices` hook fetches live prices and calculates WETH/USDC conversion
- `VaultOverview` component displays enhanced share price with oracle status
- Graceful degradation ensures the app works even without oracle access

## Subgraph Overview
Located in `subgraph/`, the mapping indexes deposit and withdraw events and aggregates TVL, share supply, and participant counts. Adjust `subgraph.yaml` for your new deployment, redeploy with the Graph CLI, and update the frontend environment variable to stream analytics into the UI.

## Troubleshooting
- **Missing `dist/`**: run `npm run build` inside `frontend/` after installing dependencies.
- **RPC or auth errors**: double-check `.env` values and ensure keys are funded and valid.
- **Contract verification fails**: confirm `ETHERSCAN_API_KEY` and target chain match.
- **Wallet actions disabled in UI**: confirm vault and USDC addresses exist in `frontend/.env` and the wallet is on the same network.

Happy vaulting!
