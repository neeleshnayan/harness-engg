# Krypton Frontend

This is the Krypton web app, built with Next.js 15 (App Router) and TypeScript. It provides:

- **Login & onboarding** for business and customer users
- **Wallet experience** on top of Circle, with KYC, fiat on‑ramp, and real‑time balance updates
- **Clark**, an agentic DeFi copilot (full‑screen and embedded "mini" variant)
- **Growth experiences** (hedge‑fund / marketplace flows, liquidity pools, analytics)

The root layout (`src/app/layout.tsx`) wires up global styles, `Instrument Sans` fonts and the TanStack Query provider.

---

## Tech Stack

### Core Framework
- **Framework**: Next.js 15.5.9 (App Router, `src/app`)
- **Language**: TypeScript 5 / React 19.2.0
- **Styling**: TailwindCSS (`globals.css`, `tailwind.config.js`)
- **UI Components**: Shadcn‑style components under `src/components/ui`
- **Icons**: Lucide React, React Icons, FontAwesome

### State Management & Data
- **React Query** (`@tanstack/react-query` v5.90.2) via `QueryProvider`
  - Optimized caching (60s stale time, 5min GC time)
  - Disabled unnecessary refetching for better performance
- **Custom hooks** in `src/hooks`:
  - `useWebSocket` – WebSocket connection management
  - `useTransactionStatus`, `useYearnAUM`, `useStrategy*` – DeFi analytics and polling
  - `useTokenSymbol` – ERC-20 token symbol fetching
  - `use-toast` – Toast notifications

### Authentication & Payments
- **Auth**: Firebase Auth v11.10.0 (Google SSO) + backend `/api/v1/login`
- **Payments**: Circle integration via backend API
- **KYC**: Sumsub WebSDK (`@sumsub/websdk-react` v2.3.19)
- **Fiat On-ramp**: Transak integration

### Blockchain & DeFi
- **Ethereum**: Ethers.js v6.16.0
- **Alchemy SDK**: v3.6.3 for blockchain data
- **Coinbase OnchainKit**: v0.38.19 for wallet connections
- **GraphQL**: `graphql-request` v7.2.0 for subgraph queries

### Charts & Visualization
- **Recharts**: v2.15.4 (dynamically imported for code splitting)
- **Framer Motion**: v12.23.24 (dynamically imported for animations)

### Forms & Validation
- **React Hook Form**: v7.62.0
- **Zod**: v4.0.15 for schema validation
- **Hookform Resolvers**: v5.2.1

---

## Performance Optimizations

### Build Performance
- ✅ **Standalone Output**: Enabled for smaller Docker images and faster deployments
- ✅ **Package Import Optimization**: Tree-shaking for heavy libraries (recharts, framer-motion, lucide-react)
- ✅ **Image Optimization**: AVIF/WebP formats with caching

### Code Splitting
- ✅ **Dynamic Imports**: Heavy components loaded on-demand:
  - Modals: `SendUSDCModal`, `BuyUSDCModal`, `SumsubKYCModal`, `SendERC20Modal`
  - Charts: `PortfolioChart`, `TechnicalCharts`, `AllocationCharts`, `CandleChart`, `PriceHistoryChart`
  - Heavy components: `ResultsDisplay`, `DevtoolsOverlay`
- ✅ **Impact**: ~40-50% smaller initial bundle size

### Runtime Optimizations
- ✅ **React.memo**: Applied to frequently re-rendered components (`WalletHeader`, `UsernameCard`)
- ✅ **React Query**: Optimized caching and refetch strategies
- ✅ **Memory Management**: Proper cleanup in useEffect hooks, WebSocket cleanup

### Performance Metrics
- **Build Time**: ~2-3 minutes (down from ~10 minutes)
- **Initial Bundle**: ~221 kB shared JS (optimized)
- **First Load**: Most routes under 50 kB

For detailed optimization documentation, see:
- `OPTIMIZATION_SUMMARY.md` – Summary and future scope
- `PERFORMANCE_OPTIMIZATIONS.md` – Technical details

---

## High‑level Flows

### 1. Authentication & Entry

- **Route**: `/` → `src/app/page.tsx` → `LoginPage` (`src/components/LoginPage.tsx`)
- **Flow**:
  - User chooses **Business** or **Customer**.
  - Auth via **Google** (Firebase Auth).
  - Frontend calls `/api/v1/login` with the Firebase ID token.
  - Response (`userData`) is stored in `localStorage` and used across the app.
  - Users are redirected to:
    - **Business**: `/business`
    - **Customer**: `/customer`

### 2. Wallet (Business & Customer)

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
    - `SendUSDCModal` for simple USDC transfers (business).
    - `SendERC20Modal` for ERC‑20 flows (customer, supports swaps).
  - Render `BalanceCard`, `TransactionHistory`, and action buttons:
    - **Pay** (open send modal)
    - **Grow** (navigate to `grow` routes)
    - Optional extra buttons (e.g. **Manage Business**).
  - Integrate **Transak** via `BuyUSDCModal` for fiat on‑ramp.
  - Embed **Mini Clark** chat component for quick DeFi interactions.

### 3. Real‑time Wallet Updates

- **WebSocket**: `useWebSocket` (`src/hooks/useWebSocket.ts`) connects to the backend WS endpoint (`/api/v1/ws`).
- **Events**:
  - `transaction_confirmed` and `transaction_update` messages (inbound/outbound transfers, wallet create/update).
  - On relevant events, `WalletPageBase`:
    - Debounces a **background balance refresh** (15s delay for Circle finality).
    - Optionally reloads transaction history.
    - Shows a transient **webhook notification** (business pages can surface this).
    - Prevents duplicate processing with event ID tracking.

---

## Clark – DeFi Copilot

### Full Clark Experience

- **Route**: `/clark` → `src/app/clark/page.tsx`
- **Devtools Route**: `/clark/devtools` → `src/app/clark/devtools/page.tsx`
- **Components** (under `src/app/clark/components`):
  - `ChatInterface` (input bar)
  - `ResultsDisplay` (renders markdown plus structured results such as backtests, price history charts) – **dynamically imported**
  - `CategoryTiles` (prebuilt prompts by category)
  - `DevtoolsOverlay` (inspecting agent messages, costs, flows) – **dynamically imported**
  - `InterruptModal` (approval / denial for agent interrupts)
  - `MemoriesTab` (user memory management)
  - `TransactionConfirmationCard`, `TransactionStatus` and charts
  - **Chart Components** (under `src/app/clark/components/charts`) – **all dynamically imported**:
    - `PriceHistoryChart` – Interactive line chart for Krypton Pay token price history
    - `PortfolioChart` – Portfolio value over time
    - `TechnicalCharts` – Technical indicators visualization
    - `AllocationCharts` – Asset allocation pie and bar charts
    - `CandleChart` – OHLCV candlestick charts
- **Flow**:
  - Session/user context is restored from `localStorage` (`userData`, previous mini‑Clark messages if expanded).
  - User prompts are sent to `agentsApi.post('/api/v1/agents/query')` with `user_id`, `username`, `session_id`.
  - The response is normalized into a `ChatMessage` with:
    - `backtestResult` (for backtest queries)
    - `priceHistoryResult` (for price history queries with chart data)
    - `economicResult` (for economic data queries)
    - `screenerResult` (for token screening queries)
    - optional `agent_flow` graph
    - cost information (`session_cost`, `overall_cost`), persisted to `localStorage`.
  - Clark detects **Krypton Pay** operations using:
    - `parsed_intent.agent_ids` and `parsed_intent.operation`
    - `agent_flow` nodes and transaction‑like payloads
    - message/markdown content heuristics
  - For **Krypton Pay price history** flows:
    - `ResultsDisplay` detects `priceHistoryResult` in the message
    - Renders `PriceHistoryChart` component with interactive line chart
    - Shows current price, price change percentage, and date range
    - No interrupt or transaction card needed (read-only operation)
  - For **Krypton Pay swap/transfer** flows:
    - **Swap-only queries** (e.g., "Swap 2 USD for AED"): Execute immediately, show transaction status card with swap details
    - **Transfer queries** (e.g., "Send 1 USD to @Foodl3"): 
      - An inline Clark confirmation bubble surfaces in the chat (derived from the interrupt payload), with **Confirm** / **Cancel** actions
      - On **Confirm** / **Cancel**, Clark appends a short status message and immediately resumes the normal agent flow
      - When the payment is executed, `ResultsDisplay` suppresses the long natural‑language payment bubble and renders a `TransactionStatus` card instead
      - `TransactionStatus`:
        - Is seeded from the agent `agent_flow` (inline transaction data) so it appears immediately
        - Continues polling `/circle/active-transactions/:username` to reflect live Circle states and final completion
  - UI shows:
    - **Cost chips** (session vs total)
    - Streaming‑style feed of messages and structured results
    - Modal prompts and devtools overlay.

### Clark memory and past conversations

Clark keeps **session memory** (summarized conversation for the current session) and **condensed persona** (cross-session user summary). Past conversations are stored in Firebase and can be loaded so their session memory is restored.

#### Data and APIs

| Concept | Where it lives | API / usage |
|--------|-----------------|-------------|
| **Past conversations list** | Firebase `conversation_history` (per user) | `GET /api/v1/agents/conversations?user_id=&limit=` – used by `PastConversationsTab` |
| **Session condensed memory** | Backend in-memory (per `user_id` + `session_id`); persisted on save | Stored with each conversation doc as `session_condensed_memory` (raw) and `session_condensed_summary` (LLM summary) |
| **Condensed memories (all sessions)** | Backend local + Firebase `clark/{user_id}.condensed_memories` | `GET /api/v1/agents/memories?user_id=&session_id=` – returns condensed persona and current-session summary |
| **Persist after each reply** | Frontend calls after assistant message | `POST /api/v1/agents/clark-chat` with `user_id`, `session_id`, `messages` – backend also saves session memory and LLM summary to Firebase |

#### Flow: saving (current session)

1. User sends messages; backend stores turns in memory and builds a **session condensed summary** (LLM).
2. After each assistant reply, the frontend calls **`POST /api/v1/agents/clark-chat`** with the full message list.
3. Backend:
   - Saves **last chat** and **conversation_history** (messages).
   - Reads current session memory from the memory manager, runs **LLM summarization** for this session, and stores:
     - **`session_condensed_memory`** (raw interaction entries) and  
     - **`session_condensed_summary`** (one paragraph)  
     on the conversation document in Firebase.

#### Flow: loading a past conversation

1. User opens **Past conversations** (sidebar or Devtools → History), backed by **`GET /api/v1/agents/conversations`**.
2. Each item has: `session_id`, `messages`, optional **`session_condensed_memory`**, optional **`session_condensed_summary`**.
3. On **“Load”** (click a conversation), the frontend calls **`POST /api/v1/agents/restore-session-memory`** with:
   - **`user_id`**, **`session_id`**
   - **`session_condensed_memory`** and **`session_condensed_summary`** when present (from the conversation doc).
   - **`messages`** when the doc has **no** stored session memory (e.g. older conversations): backend builds session entries from messages, runs the summarizer, and stores the summary for that session.
4. Backend restores:
   - Raw session entries into the memory manager for that `session_id`.
   - Session summary override (so the Memories tab can show it without another LLM call).
5. Frontend sets **`sessionId`** and **`messages`** so the feed shows that conversation; subsequent queries use the restored session context.

#### Flow: Devtools → Memories tab

1. **Memories** tab calls **`GET /api/v1/agents/memories?user_id=&session_id=`** (current page `session_id`, e.g. active or loaded conversation).
2. Response includes:
   - **Session condensed memory** – one LLM summary for the **current** session (from stored override after load, or from on-the-fly summarization of current-session turns).
   - **Condensed memories (all sessions)** – global condensed persona from backend (local storage + Firebase).
   - **Transient / persistent knowledge base** – backend KB entries.
3. **Refresh** re-fetches so that after loading a past conversation, the tab shows that conversation’s session summary.

#### Components involved

- **`src/app/clark/page.tsx`** – Keeps `sessionId`, calls `persistLastChat` (clark-chat) and `handleLoadConversationFromHistory` (restore-session-memory + set state).
- **`src/app/clark/components/PastConversationsTab.tsx`** – Fetches conversations, maps `session_condensed_memory` / `session_condensed_summary`, invokes **`onLoadConversation(sessionId, messages, sessionCondensedMemory?, sessionCondensedSummary?)`**.
- **`src/app/clark/components/MemoriesTab.tsx`** – Fetches **`GET /api/v1/agents/memories`** with **`userId`** and **`sessionId`**; displays session condensed memory, condensed memories, and KB sections.
- **`src/app/clark/components/DevtoolsOverlay.tsx`** – Hosts Agent Flow, Memories, and History (Past conversations); passes **`sessionId`** into **MemoriesTab** so the tab reflects the active or loaded conversation.

### Mini Clark (Embedded in Wallet)

- **Component**: `src/components/MiniClarkChat.tsx`
- **Usage**:
  - Passed into `WalletPageBase` via `config.renderChatComponent` from `/business` and `/customer`.
  - Supports a compact chat window plus an **"expand"** button that deep‑links to `/clark` and hydrates the main Clark view from `localStorage`.
- **Behaviour**:
  - Uses the same `agentsApi` backend and `ChatMessage` type as full Clark.
  - Can operate in **input‑only mode** (field + send button only) or full mini chat.
  - When the agent completes a `send_usdc` action with high confidence it triggers:
    - `onBalanceFlicker` (visual hint)
    - `onBalanceRefresh` (background fetch)
    - `onTransactionRefresh` (reload history)

---

## Grow, Marketplace, and Internal Tools

### Grow Pages

- **Routes**:
  - `/customer/grow` → `CustomerGrowPage` → `GrowPage userType="customer"`
  - `/business/grow` → `BusinessGrowPage` → `GrowPage userType="business"`
- **Component**: `GrowPage` (`src/components/grow/GrowPage.tsx`)
  - Orchestrates investment / growth experiences, delegating to subflows:
    - Hedge fund strategies
    - Marketplace placements
    - Tokenized yield products and analytics.

### Customer Growth Subroutes

Under `src/app/customer/grow`:

- `/customer/grow/hedge-fund` – Hedge‑fund specific UI with strategy management.
- `/customer/grow/marketplace` – Marketplace hub:
  - Dynamic category route: `/customer/grow/marketplace/[category]`.
  - Uses marketplace helpers in `src/lib/marketplace.ts` and UI in `src/components/marketplace/*`.
  - Features startup detail modals and token purchase flows.

### Business Management

- **Route**: `/business/manage` → `src/app/business/manage/page.tsx`
- Features business profile management, fundraising data, and analytics charts.

### Internal / Liquidity Pools

- **Route**: `/internal/liquidity-pools`
- **Page**: `src/app/internal/liquidity-pools/page.tsx`
- **Components** under `src/components/pools`:
  - `Dashboard`, `AddLiquidityForm`, `InitializePoolForm`
  - `MultiHopSwap`, `SwapForm`
  - `CLPoolMonitor`, `BalancesChart`, `PriceChart`, `PriceFeedCard`
- This suite powers internal netting / liquidity pool management and analytics, backed by:
  - `src/lib/nettingPoolsApi.ts`
  - Subgraph / strategy hooks under `src/hooks`.

---

## Shared Components & Utilities

### UI Primitives
- **Location**: `src/components/ui`
- **Components**: `button`, `input`, `dialog`, `card`, `form`, `toast`, `select`, `switch`, `separator`, `label`, `alert`, `badge`, `skeleton`, `chart`
- Built on Radix UI primitives with TailwindCSS styling.

### Wallet Components
- **Location**: `src/components/wallet`
- **Key Components**:
  - `WalletHeader` – Navigation and menu (memoized)
  - `BalanceCard` – Balance display with transaction history tabs
  - `TransactionHistory` – Historical transaction list
  - `ActiveTransactions` – Real-time transaction status
  - `SendUSDCModal`, `SendERC20Modal` – Payment modals (dynamically imported)
  - `BuyUSDCModal`, `SwapModal` – Fiat on-ramp and swap modals (dynamically imported)
  - `SumsubKYCModal` – KYC verification modal (dynamically imported)
  - `StrategyCard`, `StrategyModal` – Strategy management
  - `SubgraphAnalyticsGeneric`, `SubgraphAnalyticsYearnWETH` – Analytics views
  - `TokenBalances`, `KTTokenBalances` – Token balance displays
  - `TradingSignals` – Trading signal indicators
  - `CumulativeAUMChartNew` – AUM visualization
  - `TransactionStatusIndicator` – Transaction status UI

### Charts
- **Location**: `src/components/charts`
- **Components**: `TokenPriceChart`, `AssetAllocationChart`, `AumChart`, `PriceChart`
- Built with Recharts (dynamically imported where used).

### Hooks
- **Location**: `src/hooks`
- **Key Hooks**:
  - `useWebSocket` – Shared WebSocket connection logic
  - `useTransactionStatus` – Transaction status polling
  - `useYearnAUM` – Yearn strategy AUM data
  - `useStrategy*` – Strategy data and configuration hooks
  - `useTokenSymbol` – ERC-20 token symbol fetching
  - `useNettingPoolsAuth` – Netting pools authentication
  - `use-toast` – Toast notification provider

### Libraries
- **Location**: `src/lib`
- **Key Modules**:
  - `api.ts` – REST API client, including Krypton Pay API functions:
    - `getDailyPriceHistory()` – Fetch daily price history for tokens (kEUR, kGBP, kAED, kUSD)
    - `swap()` – Execute token swaps
    - `getUserInfo()`, `getTokenInfo()` – User and token data
  - `agents_api.ts` – Clark agent API client
  - `firebaseClient.ts` – Firebase initialization
  - `priceCache.ts` – Price caching utilities
  - `subgraphApi.ts` – Subgraph query helpers
  - `kTokens.ts` – Krypton token metadata and addresses
  - `circleStates.ts` – Circle status normalization
  - `marketplace.ts` – Marketplace API client
  - `nettingPoolsApi.ts` – Netting pools API client
  - `utils.ts` – Shared utility functions

---

## Local Development

### Prerequisites
- Node.js >= 20.18.0 (currently using v20.9.0)
- npm >= 10.1.0

### Setup

1. **Install dependencies**:
```bash
npm install
```

2. **Environment Variables**:
   - Create `.env.local` with required variables:
     - `NEXT_PUBLIC_API_URL` – Backend API URL
     - `NEXT_PUBLIC_RPC_URL` – Ethereum RPC URL (optional)

3. **Run dev server**:
```bash
npm run dev
```

Then visit `http://localhost:3000`.

### Development Workflow

You can start from the login page (`/`), sign in as **Business** or **Customer**, and then:

- Explore wallet + mini‑Clark at `/business` or `/customer`
- Explore Grow flows at `/business/grow` and `/customer/grow`
- Explore the full Clark experience at `/clark`
- Access Clark devtools at `/clark/devtools`
- (If permitted) open internal tools at `/internal/liquidity-pools`

### Available Scripts

- `npm run dev` – Start development server
- `npm run build` – Build for production
- `npm run start` – Start production server
- `npm run lint` – Run ESLint
- `npm run analyze` – Analyze bundle size (requires `ANALYZE=true`)

---

## Build & Deployment

### Build Configuration

- **Output**: Standalone mode for Docker deployments
- **Compression**: Enabled (gzip)
- **Image Optimization**: AVIF/WebP formats
### Build Performance

- **Build Time**: ~2-3 minutes (optimized from ~10 minutes)
- **Bundle Size**: ~221 kB shared JS, routes typically < 50 kB first load
- **Code Splitting**: Heavy components loaded dynamically

### Deployment

The app is configured for Railway deployment with:
- Standalone output for smaller Docker images
- Health check endpoint at `/`
- Automatic restarts on failure

See `railway.toml` for deployment configuration.

---

## Performance Monitoring

### Metrics to Track

- **Build Time**: Should stay under 3 minutes
- **Bundle Size**: Monitor with `npm run analyze`
- **Memory Usage**: Monitor in production for leaks
- **Core Web Vitals**: Track Lighthouse scores

### Optimization Resources

- `OPTIMIZATION_SUMMARY.md` – Summary of optimizations and future scope
- `PERFORMANCE_OPTIMIZATIONS.md` – Detailed technical documentation

---

## Project Structure

```
frontend/
├── src/
│   ├── app/                    # Next.js App Router pages
│   │   ├── business/          # Business routes
│   │   ├── customer/          # Customer routes
│   │   ├── clark/             # Clark DeFi copilot
│   │   ├── internal/          # Internal tools
│   │   └── layout.tsx         # Root layout
│   ├── components/            # React components
│   │   ├── ui/               # Shadcn UI primitives
│   │   ├── wallet/           # Wallet components
│   │   ├── charts/           # Chart components
│   │   ├── grow/             # Growth experience components
│   │   ├── marketplace/      # Marketplace components
│   │   └── pools/            # Liquidity pool components
│   ├── hooks/                # Custom React hooks
│   ├── lib/                  # Utility libraries
│   └── providers/           # React context providers
├── public/                   # Static assets
├── next.config.ts           # Next.js configuration
├── tailwind.config.js       # TailwindCSS configuration
├── tsconfig.json            # TypeScript configuration
└── package.json             # Dependencies and scripts
```

---

## Troubleshooting

### Build Issues

- **Module not found**: Run `npm install` to ensure all dependencies are installed
- **TypeScript errors**: Check `tsconfig.json` and ensure types are installed
### Runtime Issues

- **WebSocket connection**: Check backend WebSocket endpoint availability
- **Firebase auth**: Verify Firebase configuration in `src/lib/firebaseClient.ts`
- **API errors**: Check `NEXT_PUBLIC_API_URL` environment variable

### Performance Issues

- Run `npm run analyze` to identify large dependencies
- Check `OPTIMIZATION_SUMMARY.md` for optimization opportunities
- Monitor memory usage in production

---

## Contributing

When adding new features:

1. **Code Splitting**: Use dynamic imports for heavy components (>500 lines or heavy dependencies)
2. **Performance**: Add `React.memo` for frequently re-rendered components
3. **Caching**: Leverage React Query for API calls
4. **Bundle Size**: Monitor with `npm run analyze` before merging

---

**Last Updated**: March 6, 2026  
**Next.js Version**: 15.5.9  
**React Version**: 19.2.0  
**Build Status**: ✅ Optimized
