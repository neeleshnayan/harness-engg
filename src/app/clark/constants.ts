import { Category } from './types'

export const chartConfig = {
  portfolio: {
    label: "Portfolio Value",
    color: "hsl(var(--chart-1))",
  },
  cumulative: {
    label: "Cumulative Return",
    color: "hsl(var(--chart-2))",
  },
  daily: {
    label: "Daily Return",
    color: "hsl(var(--chart-3))",
  },
  sma_30: {
    label: "30-day SMA",
    color: "hsl(var(--chart-4))",
  },
  sma_100: {
    label: "100-day SMA",
    color: "hsl(var(--chart-5))",
  },
  sma_200: {
    label: "200-day SMA",
    color: "hsl(var(--chart-6))",
  },
  rsi: {
    label: "RSI",
    color: "hsl(var(--chart-7))",
  },
  bb_upper: {
    label: "Bollinger Upper",
    color: "hsl(var(--chart-8))",
  },
  bb_middle: {
    label: "Bollinger Middle",
    color: "hsl(var(--chart-9))",
  },
  bb_lower: {
    label: "Bollinger Lower",
    color: "hsl(var(--chart-10))",
  },
  price: {
    label: "Price",
    color: "#fbbf24",
  },
}

export const allocationColors = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
  "hsl(var(--chart-5))",
  "hsl(var(--chart-6))",
  "hsl(var(--chart-7))",
  "hsl(var(--chart-8))",
  "hsl(var(--chart-9))",
  "hsl(var(--chart-10))",
]

export const categories: Category[] = [
  {
    id: 'strategy',
    title: 'Strategy & Backtesting',
    icon: '/backtesting.svg',
    description: 'Test portfolio strategies',
    prompts: [
      'Backtest Bitcoin & Ethereum with 50% each from 01/01/2025 to 09/09/2025 with 1000 USD',
      'Backtest BTC & ETH 50/50 with monthly rebalancing from 01/01/2025 to 09/09/2025 with 1000 USD',
      'Run trading strategy where Buy when RSI < 30 & Sell when RSI > 70 with 1000 USD from 01/01/2025 to 09/09/2025',
      'Run strategy where Buy when EMA(9) crosses above EMA(21) and RSI(14) > 50 & Sell when EMA(9) crosses below EMA(21) or RSI(14) < 45 with 1000 USD from 01/01/2025 to 09/09/2025',
      'Run strategy where Buy when Close < BB_lower(20,2) and RSI(14) < 30 & Sell when Close >= SMA(20) or +4% profit with 1000 USD from 01/01/2025 to 09/09/2025',
      'Run strategy where Buy when MACD(12,26,9) cross up and ADX(14) > 20 & Sell when MACD cross down or ADX < 18 with 1000 USD from 01/01/2025 to 09/09/2025'
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
      'Show RSI analysis for ETH and ADA'
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
      'Show me GDP data for top 10 countries',
      'What are the inflation rates for major economies?',
      'Display unemployment rates',
      'Show interest rates for countries',
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
      'What are the tax implications of crypto trading?',
      'How do I report crypto gains and losses?',
      'What are the tax regulations for DeFi transactions?',
      'How to calculate capital gains tax on crypto?',
      'What are the tax requirements for crypto mining?',
      'How to handle crypto tax reporting for businesses?',
      'What are the tax implications of staking rewards?',
      'How to optimize crypto tax strategy?'
    ]
  }
]
