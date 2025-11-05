# MAVC Vault Control Center

A polished React + Vite front-end for interacting with the MultiAssetVaultUSDCWETH contract. Connect MetaMask, view vault analytics, execute USDC deposits and withdrawals, and monitor MAVC share activity pulled from a custom The Graph subgraph.

## Highlights
- Glassmorphism-inspired UI with responsive layout and subtle gradients
- Multi-wallet support (MetaMask, Coinbase Wallet, WalletConnect) with network guard for the configured chain
- Live vault telemetry (TVL, share price, allocation, internal accounting, on-chain balances)
- User dashboard with MAVC share balance, USDC wallet funds, and allowance status
- Guided deposit & withdrawal flows with approval handling and transaction feedback
- Optional subgraph insights for MAVC mint/burn trends and recent vault activity

## 1. Configure Environment
1. Duplicate the template:
   ```bash
   cp .env.example .env
   ```
2. Populate `.env` with real values:
   - `VITE_CHAIN_ID` – e.g. `11155111` for Sepolia
   - `VITE_RPC_URL` – HTTPS RPC for the same chain (Infura, Alchemy, etc.)
   - `VITE_VAULT_ADDRESS` – deployed `MultiAssetVaultUSDCWETH` address
   - `VITE_USDC_ADDRESS` – ERC20 USDC token used for deposits
   - `VITE_WETH_ADDRESS` – WETH token used by the vault (informational)
   - `VITE_SUBGRAPH_URL` – **optional** GraphQL endpoint once you deploy the subgraph (see `/subgraph`)

> The dApp blocks writes until the vault & token addresses are present. Subgraph analytics stay hidden until `VITE_SUBGRAPH_URL` is provided.

## 2. Install & Run
```bash
npm install
npm run dev
```
The development server defaults to `http://localhost:5173`.

## 3. User Flow
1. Connect MetaMask (browser prompts if no wallet is detected)
2. Review vault analytics and your MAVC position
3. Enter a USDC amount and click **Approve** if prompted (one-time per allowance)
4. Submit the **Deposit** to transfer USDC and mint MAVC
5. Use the withdrawal panel to burn MAVC for USDC when exiting
6. (Optional) Explore the **On-Chain Analytics via The Graph** section once your subgraph is live

Each transaction shows real-time status updates and the UI refreshes balances once receipts confirm on-chain.

## Subgraph Integration
- The UI queries `VITE_SUBGRAPH_URL` every minute to fetch aggregate vault metrics plus recent deposit/withdrawal history.
- A ready-to-customize subgraph lives in `/subgraph`. Update the address/start block, deploy to the Hosted Service or Subgraph Studio, then drop the query endpoint into `.env`.

## Tech Stack
- React 19 + TypeScript + Vite 7
- Tailwind CSS with custom theme tokens
- wagmi v2 + viem + ethers v6 for wallet and contract interactions
- @tanstack/react-query + graphql-request for data fetching

Happy vaulting!
