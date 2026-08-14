import { Category } from './types'

const CHART_PALETTE = {
  performance: '#2dd4bf',
  positive: '#4ade80',
  negative: '#f87171',
  warning: '#facc15',
  info: '#22d3ee',
  neutral: '#cbd5e1',
  secondary: '#67e8f9',
  tertiary: '#14b8a6',
} as const

export const chartUi = {
  card: 'w-full bg-teal-900/25 border-teal-700/40 backdrop-blur-sm',
  muted: 'text-teal-100/75',
  tooltip: 'bg-zinc-900/95 border border-teal-700/50 rounded-lg shadow-lg',
  empty: 'border border-dashed border-teal-600/40 bg-teal-900/10 text-teal-100/75',
} as const

export const chartConfig = {
  portfolio: {
    label: "Value",
    color: CHART_PALETTE.performance,
  },
  cumulative: {
    label: "Cumulative Return",
    color: CHART_PALETTE.positive,
  },
  daily: {
    label: "Daily Return",
    color: CHART_PALETTE.info,
  },
  sma_30: {
    label: "30-day SMA",
    color: CHART_PALETTE.warning,
  },
  sma_100: {
    label: "100-day SMA",
    color: CHART_PALETTE.secondary,
  },
  sma_200: {
    label: "200-day SMA",
    color: CHART_PALETTE.positive,
  },
  rsi: {
    label: "RSI",
    color: CHART_PALETTE.warning,
  },
  stochastic_rsi: {
    label: "Stochastic RSI",
    color: CHART_PALETTE.tertiary,
  },
  stochastic_rsi_k: {
    label: "Stoch RSI %K",
    color: CHART_PALETTE.performance,
  },
  stochastic_rsi_d: {
    label: "Stoch RSI %D",
    color: CHART_PALETTE.secondary,
  },
  bb_upper: {
    label: "Bollinger Upper",
    color: CHART_PALETTE.info,
  },
  bb_middle: {
    label: "Bollinger Middle",
    color: CHART_PALETTE.neutral,
  },
  bb_lower: {
    label: "Bollinger Lower",
    color: CHART_PALETTE.warning,
  },
  price: {
    label: "Price",
    color: CHART_PALETTE.warning,
  },
  super_trend: {
    label: "Super Trend",
    color: CHART_PALETTE.positive,
  },
  adx: {
    label: "ADX",
    color: CHART_PALETTE.secondary,
  },
  adx_plus_dmi: {
    label: "+DMI",
    color: CHART_PALETTE.positive,
  },
  adx_minus_dmi: {
    label: "-DMI",
    color: CHART_PALETTE.negative,
  },
}

export const allocationColors = [
  '#2dd4bf',
  '#4ade80',
  '#22d3ee',
  '#67e8f9',
  '#14b8a6',
  '#34d399',
  '#06b6d4',
  '#84cc16',
  '#facc15',
  '#f87171',
]

export const categories: Category[] = [
  {
    id: 'fund',
    title: 'Fund Operations',
    icon: '/backtesting.svg',
    description: 'Run the fund with Clark',
    prompts: [
      // Clark reaches the spine through typed tools now, so it can chain
      // reads and reason about what it finds. These are the questions that
      // were impossible under the old regex router — none of them match a
      // pattern, and every one needs two or more lookups.
      'How are we doing today?',
      'Anything I should be worried about right now?',
      'Which position is over its concentration limit, and by how much?',
      'How much would I need to trim to clear that breach?',
      'How many day trades do I have left before the account gets restricted?',
      'Can I buy and sell the same name today, or would that cost a day trade?',
      'Are our trading costs running above what the backtests assume?',
      'Does our book agree with the broker right now?',
      'What did each strategy actually trade today?',
      'Do a pass over the fund and tell me anything that deserves attention.',
      'Is the market open, and how long until it closes?',
      'Backtest nvidia over the last 6 months with an SMA crossover',
      // --- kept for reference; these worked under the old router ---------
      "What's the fund at?",
      'Show me the strategies',
      'What positions do we hold?',
      "What's pending approval?",
      'Buy 2 AAPL for US Momentum',
      'Sell 1 MSFT',
      // 'Who are our LPs?',
      // 'Deploy the Mega-Cap Tech strategy',
    ],
  },
  {
    id: 'strategy',
    title: 'Strategy & Backtesting',
    icon: '/backtesting.svg',
    description: 'Test portfolio strategies (crypto/legacy)',
    prompts: [
      'Backtest a 100-day SMA filter on Gold; stay in cash when below SMA; from 2024-01-01 to 2024-09-30 with $12,000',
      'Backtest Gold from 01/01/2025 to 09/09/2025 with 1000 USD',
      'Backtest Bitcoin & Ethereum with 50% each from 01/01/2025 to 09/09/2025 with 1000 USD',
      'Backtest a 50/200 EMA crossover on BTC from 2024-01-01 to 2024-06-30 with $5,000',
      'Backtest RSI strategy on Bitcoin from 2024-01-01 to 2024-06-30 with $10,000',
      'Backtest portfolio with 60% Bitcoin, 30% Ethereum, 10% Solana using 10000 USD from 2024-01-01 to 2024-12-31',
      'Backtest monthly momentum on BTC, ETH, SOL (hold top 2 each rebalance) from 2023-01-01 to 2024-01-01 with $15,000',
      // 'Backtest Bollinger Bands (20,2) mean reversion on BTC from 2024-03-01 to 2024-07-31 with $7,500',
      // 'Backtest MACD (12,26,9) on ETH from 2024-02-01 to 2024-08-01 with $8,000',
      // 'Backtest Stochastic RSI (14,3,3,3) on SOL from 2024-01-15 to 2024-06-30 with $6,000',
      // 'Backtest BTC with a 2x ATR(14) trailing stop from 2024-01-01 to 2024-09-30 with $10,000',
      // 'Backtest BTC & ETH 50/50 with monthly rebalancing from 01/01/2025 to 09/09/2025 with 1000 USD',
      // 'Backtest a strategy where Buy when RSI < 30 & Sell when RSI > 70 with 1000 USD from 01/01/2025 to 09/09/2025',
      // 'Backtest a strategy where Buy when EMA(9) crosses above EMA(21) and RSI(14) > 50 & Sell when EMA(9) crosses below EMA(21) or RSI(14) < 45 with 1000 USD from 01/01/2025 to 09/09/2025',
      // 'Backtest a strategy where Buy when MACD(12,26,9) cross up and ADX(14) > 20 & Sell when MACD cross down or ADX < 18 with 1000 USD from 01/01/2025 to 09/09/2025',
      // 'Backtest a strategy where Buy when Stochastic RSI %K < 20 and RSI(14) > 50 & Sell when Stochastic RSI %K > 80 with 1500 USD from 01/01/2025 to 09/09/2025',
      // 'Backtest using Super Trend on Bitcoin from 2025-01-01 to 2025-09-09 with 1000 USD',
      // 'Backtest a strategy: Buy when ADX > 20 and +DMI > -DMI, Sell when ADX < 18 or -DMI > +DMI on Bitcoin from 2025-01-01 to 2025-09-09 with 1000 USD',
      // 'Please backtest a simple Bitcoin strategy where I buy BTC with $2,000 on 2024‑01‑01 and take profit if the price goes up 20% or sell if it falls 10%, checking this until 2024‑09‑30.',
      // 'Backtest a simple Super Trend strategy on Bitcoin that goes long when Super Trend turns green and exits when it turns red, from 2024‑01‑01 to 2024‑09‑30 with $4,000.',
      // 'Backtest a basic ADX trend strategy on Bitcoin where we only stay in trades when ADX shows a strong trend, from 2024‑01‑01 to 2024‑09‑30 with $3,000.',
      // 'Backtest a simple VWAP trend strategy on Bitcoin that stays in the trade when price is above the 30‑period VWAP and goes to cash when price is below it, from 2024‑02‑01 to 2024‑09‑30 with $4,000.',
      // 'Backtest a simple ATR trailing stop strategy on Bitcoin where I buy once at the start and then sell if price falls 2 times ATR(14) from the highest point, from 2024‑01‑01 to 2024‑09‑30 with $5,000.',
      // 'I want to try a very simple MACD strategy on Ethereum: buy when MACD goes above its signal line and sell when it goes back below, from 2024‑01‑01 to 2024‑09‑30 using $4,000.',
      // 'Backtest a simple Bollinger Bands strategy on Bitcoin that buys when the price closes below the lower band and sells when it closes above the upper band, from 2024‑01‑01 to 2024‑06‑30 with $2,500.'
      // 'Backtest a very simple RSI strategy on Bitcoin where it buys when the RSI falls below 30 and sells when RSI goes above 70, from 2024‑01‑01 to 2024‑06‑30 using $3,000.',
      // 'Please backtest a simple Bitcoin strategy that buys when the 50‑day EMA goes above the 200‑day EMA and sells when it goes back below, from 2024‑01‑01 to 2024‑12‑31 with $5,000.'
    ]
  },
  {
    id: 'technical',
    title: 'Technical Analysis',
    icon: '/technical.svg',
    description: 'Analyze price trends',
    prompts: [
      'Plot RSI and moving averages for Bitcoin from 2025-01-01 to 2025-09-09',
      'Show Bollinger Bands for Ethereum over the last 6 months',
      'Display technical indicators for Solana and Cardano',
      'Plot 30, 100, and 200-day moving averages for BTC',
      'Show RSI analysis for ETH and ADA',
      'Show me Super Trend analysis for Bitcoin from 2025-01-01 to 2025-09-09',
      'Plot technical analysis for Bitcoin with ADX from 01-01-2025 to 09-09-2025',
      'Plot ADX indicator for Ethereum from 01-01-2025 to 09-09-2025'
    ]
  },
  {
    id: 'screeners',
    title: 'Crypto Screeners',
    icon: '/screener.svg',
    description: 'Filter cryptos for specific criteria',
    prompts: [
      'Find top 5 cryptos with price above $5',
      'Show me cryptos priced between $10 and $1000',
      'Find cryptos with daily gain over 30%',
      'Find cryptos near 52-week high',
      'Find cryptos with RSI bearish (oversold)',
      'Find cryptos with RSI bullish (overbought)',
      'Find cryptos with golden cross pattern',
      'Find top 5 cryptos with current price above 10 Day EMA',
      'Find top 5 cryptos with current price above 5 Day EMA'
    ]
  },
  {
    id: 'research',
    title: 'Market Research',
    icon: '/research.svg',
    description: 'Access economic data',
    prompts: [
      'What is the GDP for the US?',
      'Give me a company profile on Apple',
      'Show me 10-year treasury yield',
      'Show interest rates for US',
      'Show me the latest economic news',
      'What\'s happening in the economy?',
      'Show economic calendar',
      'What are the upcoming economic events?'
    ]
  },
  {
    id: 'tax',
    title: 'Tax & Regulations',
    icon: '/tax.svg',
    description: 'Tax guidance and compliance',
    prompts: [
      'Summarize how crypto income is taxed in India, especially consulting fees or advisory revenue.',
      'What documentation should I prepare when responding to an Indian Section 142(1) crypto notice?',
      'Explain the TDS obligations for trades on foreign exchanges or DEXs from an Indian tax perspective.',
      'How does the Indian IT Department track offshore crypto wallets, and what risks trigger audits?',
      'Provide an overview of crypto tax obligations in Germany and any jurisdiction-specific nuances.'
    ]
  },
  {
    id: 'kryptonpay',
    title: 'Payments and Swaps',
    icon: '/kryptonpay.svg',
    description: 'Send payments and execute token swaps',
    prompts: [
      'Send 10 dollars to @krypton',
      'Swap 50 euros for GBP',
      'Swap 20 USD for EUR and send 10 EUR to @krypton',
      'Show price history for EUR',
      'Display GBP price chart for the last 90 days',
      'What are my balances?',
      'Show my daily balance history',
      'Show my intraday balance history'
    ]
  },
]
