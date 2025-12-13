import { Category } from './types'

export const chartConfig = {
  portfolio: {
    label: " Value",
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
  stochastic_rsi: {
    label: "Stochastic RSI",
    color: "#34d399",
  },
  stochastic_rsi_k: {
    label: "Stoch RSI %K",
    color: "#34d399",
  },
  stochastic_rsi_d: {
    label: "Stoch RSI %D",
    color: "#60a5fa",
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
  super_trend: {
    label: "Super Trend",
    color: "#10b981",
  },
  adx: {
    label: "ADX",
    color: "#8b5cf6",
  },
  adx_plus_dmi: {
    label: "+DMI",
    color: "#10b981",
  },
  adx_minus_dmi: {
    label: "-DMI",
    color: "#ef4444",
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
      'Backtest a strategy where Buy when RSI < 30 & Sell when RSI > 70 with 1000 USD from 01/01/2025 to 09/09/2025',
      'Backtest a strategy where Buy when EMA(9) crosses above EMA(21) and RSI(14) > 50 & Sell when EMA(9) crosses below EMA(21) or RSI(14) < 45 with 1000 USD from 01/01/2025 to 09/09/2025',
      'Backtest a strategy where Buy when MACD(12,26,9) cross up and ADX(14) > 20 & Sell when MACD cross down or ADX < 18 with 1000 USD from 01/01/2025 to 09/09/2025',
      'Backtest a strategy where Buy when Stochastic RSI %K < 20 and RSI(14) > 50 & Sell when Stochastic RSI %K > 80 with 1500 USD from 01/01/2025 to 09/09/2025',
      'Backtest using Super Trend on Bitcoin from 2025-01-01 to 2025-09-09 with 1000 USD',
      'Backtest a strategy: Buy when ADX > 20 and +DMI > -DMI, Sell when ADX < 18 or -DMI > +DMI on Bitcoin from 2025-01-01 to 2025-09-09 with 1000 USD'
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
      'Overlay Stochastic RSI and RSI for BTC over the last quarter',
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
  }
]
