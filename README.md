
## Krypton Frontend

This is the Krypton web app, built with Next.js (App Router) and TypeScript. It provides:

- **Login & onboarding** for business and customer users
- **Wallet experience** on top of Circle, with KYC, fiat on‑ramp, and real‑time balance updates
- **Clark**, an agentic DeFi copilot (full‑screen and embedded “mini” variant)
- **Growth experiences** (hedge‑fund / marketplace flows, liquidity pools, analytics)

The root layout (`src/app/layout.tsx`) wires up global styles, `Geist` fonts and the TanStack Query provider.

---

## Tech stack

- **Framework**: Next.js (App Router, `src/app`)
- **Language**: TypeScript / React
- **Styling**: TailwindCSS (`globals.css`, `tailwind.config.js`)
- **UI kit**: Shadcn‑style components under `src/components/ui`
- **Data / state**:
  - React Query via `QueryProvider`
  - Custom hooks in `src/hooks` (websocket, subgraphs, strategy data, toasts, etc.)
- **Auth**: Firebase Auth (Google SSO) + backend `/api/v1/login`
- **Observability**: Sentry (`instrumentation*.ts`, `src/lib/sentry.ts`)

---

## High‑level flows

### 1. Authentication & entry

- **Route**: `/` → `src/app/page.tsx` → `LoginPage` (`src/components/LoginPage.tsx`)
- **Flow**:
  - User chooses **Business** or **Customer**.
  - Auth via **Google** (Firebase Auth).
  - Frontend calls `/api/v1/login` with the Firebase ID token.
  - Response (`userData`) is stored in `localStorage` and used across the app.
  - Users are redirected to:
    - **Business**: `/business`
    - **Customer**: `/customer`

### 2. Wallet (business & customer)

- **Routes**:
  - Business wallet: `/business` → `src/app/business/page.tsx`
  - Customer wallet: `/customer` → `src/app/customer/page.tsx`
- Both pages are thin wrappers around `WalletPageBase` (`src/components/wallet/WalletPageBase.tsx`) with different `WalletPageConfig`.
- **Key responsibilities of `WalletPageBase`**:
  - Load `userData` from `localStorage` and refresh from `/api/v1/user/:userId`.
  - Maintain **KYC state** and drive the Sumsub flow:
    - Trigger applicant creation and access token
    - Poll KYC status and persist to `localStorage`.
  - Fetch **wallet balance** from `/api/v1/wallet_balance/:address`.
  - Handle **payments**:
    - `SendUSDCModal` for simple USDC transfers.
    - `SendERC20Modal` for ERC‑20 flows (configurable per page).
  - Render `BalanceCard`, `TransactionHistory`, and action buttons:
    - **Pay** (open send modal)
    - **Grow** (navigate to `grow` routes)
    - Optional extra buttons (e.g. **Manage Business**).
  - Integrate **Transak** via `BuyUSDCModal` for fiat on‑ramp.

### 3. Real‑time wallet updates

- **WebSocket**: `useWebSocket` (`src/hooks/useWebSocket.ts`) connects to the backend WS endpoint (`/api/v1/ws`).
- **Events**:
  - `circle_webhook` messages (inbound/outbound transfers, wallet create/update).
  - On relevant events, `WalletPageBase`:
    - Debounces a **background balance refresh** (configurable delay for Circle finality).
    - Optionally reloads transaction history.
    - Shows a transient **webhook notification** (business pages can surface this).

---

## Clark – DeFi copilot

### Full Clark experience

- **Route**: `/clark` → `src/app/clark/page.tsx`
- **Components** (under `src/app/clark/components`):
  - `ChatInterface` (input bar)
  - `ResultsDisplay` (renders markdown plus structured results such as backtests)
  - `CategoryTiles` (prebuilt prompts by category)
  - `DevtoolsOverlay` (inspecting agent messages, costs, flows)
  - `InterruptModal` (approval / denial for agent interrupts)
  - `TransactionConfirmationCard`, `TransactionStatus` and charts (allocation, technicals, portfolio, etc.)
- **Flow**:
  - Session/user context is restored from `localStorage` (`userData`, previous mini‑Clark messages if expanded).
  - User prompts are sent to `agentsApi.post('/api/v1/agents/query')` with `user_id`, `username`, `session_id`.
  - The response is normalized into a `ChatMessage` with:
    - `backtestResult`
    - optional `agent_flow` graph
    - cost information (`session_cost`, `overall_cost`), persisted to `localStorage`.
  - Clark detects **Krypton Pay** operations using:
    - `parsed_intent.agent_ids`
    - `agent_flow` nodes and transaction‑like payloads
    - message/markdown content heuristics
  - For Krypton Pay flows:
    - `InterruptModal` surfaces a confirmation step (e.g. “Send 1 USD to Foodl3”)
    - On **Confirm**, Clark executes the payment and returns a payment‑specific assistant message
    - `ResultsDisplay` suppresses Clark’s natural‑language payment bubble and renders a `TransactionStatus` card instead
    - `TransactionStatus`:
      - Is seeded from the agent `agent_flow` (inline transaction data) so it appears even if `/circle/active-transactions/:username` briefly returns no active transfers
      - Continues polling `/circle/active-transactions/:username` to reflect live Circle states and final completion
  - UI shows:
    - **Cost chips** (session vs total)
    - Streaming‑style feed of messages and structured results
    - Modal prompts and devtools.

### Mini Clark (embedded in wallet)

- **Component**: `src/components/MiniClarkChat.tsx`
- **Usage**:
  - Passed into `WalletPageBase` via `config.renderChatComponent` from `/business` and `/customer`.
  - Supports a compact chat window plus an **“expand”** button that deep‑links to `/clark` and hydrates the main Clark view from `localStorage`.
- **Behaviour**:
  - Uses the same `agentsApi` backend and `ChatMessage` type as full Clark.
  - Can operate in **input‑only mode** (field + send button only) or full mini chat.
  - When the agent completes a `send_usdc` action with high confidence it triggers:
    - `onBalanceFlicker` (visual hint)
    - `onBalanceRefresh` (background fetch)
    - `onTransactionRefresh` (reload history)

---

## Grow, marketplace, and internal tools

### Grow pages

- **Routes**:
  - `/customer/grow` → `CustomerGrowPage` → `GrowPage userType="customer"`
  - `/business/grow` → `BusinessGrowPage` → `GrowPage userType="business"`
- **Component**: `GrowPage` (`src/components/grow/GrowPage.tsx`)
  - Orchestrates investment / growth experiences, likely delegating to subflows:
    - Hedge fund strategies
    - Marketplace placements
    - Tokenized yield products and analytics.

### Customer growth subroutes

Under `src/app/customer/grow`:

- `/customer/grow/hedge-fund` – hedge‑fund specific UI.
- `/customer/grow/marketplace` – marketplace hub:
  - Dynamic category route: `/customer/grow/marketplace/[category]`.
  - Uses marketplace helpers in `src/lib/marketplace.ts` and UI in `src/components/marketplace/*`.

### Internal / liquidity pools

- **Route**: `/internal/liquidity-pools`
- **Page**: `src/app/internal/liquidity-pools/page.tsx`
- **Components** under `src/components/pools`:
  - `Dashboard`, `AddLiquidityForm`, `InitializePoolForm`
  - `MultiHopSwap`, `SwapForm`
  - `CLPoolMonitor`, `BalancesChart`, `PriceChart`, `PriceFeedCard`
- This suite powers internal netting / liquidity pool management and analytics, backed by:
  - `src/lib/nettingPoolsApi.ts`
  - subgraph / strategy hooks under `src/hooks`.

---

## Shared components & utilities (tour)

- **UI primitives**: `src/components/ui`
  - `button`, `input`, `dialog`, `card`, `form`, `toast`, etc.
- **Wallet**: `src/components/wallet`
  - `WalletHeader`, `BalanceCard`, `TransactionHistory`, `ActiveTransactions`
  - `StrategyCard`, `StrategyModal`, analytics charts and price history views
- **Charts**: `src/components/charts`
  - `TokenPriceChart`, `AssetAllocationChart`, `AumChart`, etc.
- **Hooks**: `src/hooks`
  - `useWebSocket` – shared WS connection logic.
  - `useTransactionStatus`, `useYearnAUM`, `useStrategy*` – DeFi analytics and polling.
  - `use-toast` – toast provider wiring.
- **Libs**: `src/lib`
  - `api.ts` – REST API client.
  - `agents_api.ts` – Clark agent API client.
  - `firebaseClient.ts` – Firebase initialization.
  - `priceCache.ts`, `subgraphApi.ts`, `kTokens.ts`, `circleStates.ts` – domain utilities for pricing, subgraphs, token metadata, Circle status normalization.

---

## Local development

- **Install dependencies**:

```bash
npm install
```

- **Run dev server**:

```bash
npm run dev
```

Then visit `http://localhost:3000`.

You can start from the login page (`/`), sign in as **Business** or **Customer**, and then:

- Explore wallet + mini‑Clark at `/business` or `/customer`
- Explore Grow flows at `/business/grow` and `/customer/grow`
- Explore the full Clark experience at `/clark`
- (If permitted) open internal tools at `/internal/liquidity-pools`.