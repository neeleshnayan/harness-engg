"use client"

import React, { useState, useRef, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, PieChart, Pie, Cell, BarChart, Bar } from 'recharts'
import { Badge } from '@/components/ui/badge'
import { TrendingUp, TrendingDown, DollarSign, BarChart3, PieChart as PieChartIcon, Send, Bot, User, CheckCircle, XCircle, Loader2, ArrowLeft } from 'lucide-react'
import agentsApi from '@/lib/agents_api'
import { useRouter } from 'next/navigation'

interface BacktestRequest {
  strategy: 'conservative' | 'aggressive'
  start_date: string
  end_date: string
  initial_capital: number
  rebalance_frequency: string
}

interface BacktestMetrics {
  total_return: number
  annualized_return: number
  volatility: number
  sharpe_ratio: number
  max_drawdown: number
  calmar_ratio: number
  win_rate: number
  best_month: number
  worst_month: number
}

interface BacktestAllocation {
  symbol: string
  allocation_percentage: number
  final_value: number
  total_return: number
}

interface TechnicalIndicators {
  sma_30?: number
  sma_100?: number
  sma_200?: number
  rsi?: number
  rsi_overbought: boolean
  rsi_oversold: boolean
  bb_upper?: number
  bb_middle?: number
  bb_lower?: number
  bb_upper_break: boolean
  bb_lower_break: boolean
}

interface BacktestDataPoint {
  date: string
  portfolio_value: number
  daily_return: number
  cumulative_return: number
  technical_indicators?: TechnicalIndicators
}

interface BacktestResult {
  success: boolean
  message: string
  strategy: string
  start_date: string
  end_date: string
  initial_capital: number
  final_capital: number
  total_days: number
  metrics: BacktestMetrics
  allocations: BacktestAllocation[]
  data_points: BacktestDataPoint[]
  include_technical_analysis: boolean
  technical_indicators_requested: string[]
  target_assets: string[]
  show_performance_stats: boolean
}

interface ChatMessage {
  id: string
  type: 'user' | 'assistant'
  content: string
  timestamp: Date
  parsedIntent?: any
  success?: boolean
  backtestResult?: BacktestResult
}

const chartConfig = {
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
}

const allocationColors = [
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

export default function BacktestPage() {
  const router = useRouter()
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      type: 'assistant',
      content: `Hello! I can help you backtest crypto portfolio strategies and analyze technical indicators for specific assets. Try these examples:

Basic Backtesting:
• Backtest conservative strategy from 10/01/2024 to 09/09/2025 with 1000 USD
• Test aggressive strategy from 2024-01-01 to 2024-12-31 with 5000 USD

Custom Portfolio Allocation:
• Backtest the following strategy Bitcoin (BTC) 35%, Ethereum (ETH) 25%, BNB (BNB) 10%, Solana (SOL) 7%, Cardano (ADA) 5%, XRP (Ripple) 5%, TRON (TRX) 4%, Dogecoin (DOGE) 3%, Polkadot (DOT) 3%, Stablecoin (USDT/USDC) 3%. from 10/01/2024 to 09/09/2025 with 1000 USD

Asset-Specific Technical Analysis:
• Plot RSI and moving averages for Bitcoin from 2024-01-01 to 2024-12-31
• Show Bollinger Bands for Ethereum over the last 6 months
• Display technical indicators for Solana and Cardano
• Plot 30, 100, and 200-day moving averages for BTC
• Show RSI analysis for ETH and ADA`,
      timestamp: new Date(),
    }
  ])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading) return

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: inputValue,
      timestamp: new Date(),
    }

    setMessages(prev => [...prev, userMessage])
    setInputValue('')
    setIsLoading(true)
    
    try {
      // Make API call to LangChain service
      const response = await agentsApi.post('/api/v1/agents/query', {
        query: inputValue,
        user_id: 'backtest_user'
      })

      const data = response.data
      
      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: data.message,
        timestamp: new Date(),
        parsedIntent: data.parsed_intent,
        success: data.success,
        backtestResult: data.data?.backtest_result
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('LangChain API error:', error)
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: 'Sorry, I encountered an error processing your request. Please try again.',
        timestamp: new Date(),
        success: false,
      }

      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value)
  }

  const formatPercentage = (value: number) => {
    return `${value.toFixed(2)}%`
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString()
  }

  const formatTimestamp = (timestamp: Date) => {
    return timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  const renderIntentBadge = (intent: any) => {
    if (!intent) return null

    return (
      <div className="mt-2 space-y-1">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant={intent.confidence > 0.7 ? 'default' : 'secondary'}>
            {intent.action} ({Math.round(intent.confidence * 100)}%)
          </Badge>
          {intent.strategy && (
            <Badge variant="outline" className="bg-green-100 text-green-800">
              {intent.strategy === 'custom' ? 'Custom Portfolio' : intent.strategy}
            </Badge>
          )}
          {intent.start_date && (
            <Badge variant="outline" className="bg-blue-100 text-blue-800">
              {intent.start_date}
            </Badge>
          )}
          {intent.end_date && (
            <Badge variant="outline" className="bg-blue-100 text-blue-800">
              {intent.end_date}
            </Badge>
          )}
          {intent.initial_capital && (
            <Badge variant="outline" className="bg-purple-100 text-purple-800">
              ${intent.initial_capital}
            </Badge>
          )}
          {intent.rebalance_frequency && (
            <Badge variant="outline" className="bg-orange-100 text-orange-800">
              {intent.rebalance_frequency}
            </Badge>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-black via-zinc-900 to-neutral-900 dark overflow-x-hidden">
      {/* Main Content Area */}
      <div className="container mx-auto px-4 py-8 max-w-7xl pb-80">
        {/* Header with Back Button */}
        <div className="flex items-center justify-between mb-8">
          <Button
            onClick={() => router.push('/customer/grow/hedge-fund')}
            variant="ghost"
            className="flex items-center gap-2 text-zinc-400 hover:text-white hover:bg-zinc-800/50 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Hedge Fund
          </Button>
          <div className="text-center space-y-2">
            <h1 className="text-3xl font-bold text-white mb-4">Clark</h1>
            <p className="text-zinc-400">
              AI Portfolio Manager
            </p>
          </div>
          <div className="w-24"></div> {/* Spacer for centering */}
        </div>

      {/* Show Krypton logo when no results are available */}
      {!messages.some(m => m.backtestResult) && (
        <div className="flex flex-col items-center justify-center py-20">
          <img
            src="/krypton_logo.svg"
            alt="Krypton Logo"
            className="h-32 w-auto drop-shadow-[0_2px_8px_rgba(16,255,180,0.18)] mb-8"
          />
          <h2 className="text-2xl font-bold text-white mb-4">Ready to Analyze</h2>
          <p className="text-zinc-400 text-center max-w-md">
            Start a conversation to backtest portfolio strategies and analyze technical indicators.
          </p>
        </div>
      )}

      {/* Display backtest results if available */}
      {messages.some(m => m.backtestResult) && (
        <div className="space-y-6">
          {messages
            .filter(m => m.backtestResult)
            .map((message) => {
              const backtestResult = message.backtestResult!
              return (
                <div key={message.id} className="space-y-6">
                  {/* Summary Cards - Only show if performance stats are enabled */}
                  {backtestResult.show_performance_stats && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 w-full">
                      <Card>
                        <CardContent className="p-6">
                          <div className="flex items-center space-x-2">
                            <DollarSign className="h-4 w-4 text-muted-foreground" />
                            <div>
                              <p className="text-sm font-medium text-muted-foreground">Final Value</p>
                              <p className="text-2xl font-bold">{formatCurrency(backtestResult.final_capital)}</p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>

                      <Card>
                        <CardContent className="p-6">
                          <div className="flex items-center space-x-2">
                            <TrendingUp className="h-4 w-4 text-muted-foreground" />
                            <div>
                              <p className="text-sm font-medium text-muted-foreground">Total Return</p>
                              <p className={`text-2xl font-bold ${
                                backtestResult.metrics.total_return >= 0 ? 'text-green-600' : 'text-red-600'
                              }`}>
                                {formatPercentage(backtestResult.metrics.total_return)}
                              </p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>

                      <Card>
                        <CardContent className="p-6">
                          <div className="flex items-center space-x-2">
                            <BarChart3 className="h-4 w-4 text-muted-foreground" />
                            <div>
                              <p className="text-sm font-medium text-muted-foreground">Sharpe Ratio</p>
                              <p className="text-2xl font-bold">{backtestResult.metrics.sharpe_ratio.toFixed(2)}</p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>

                      <Card>
                        <CardContent className="p-6">
                          <div className="flex items-center space-x-2">
                            <TrendingDown className="h-4 w-4 text-muted-foreground" />
                            <div>
                              <p className="text-sm font-medium text-muted-foreground">Max Drawdown</p>
                              <p className="text-2xl font-bold text-red-600">
                                {formatPercentage(Math.abs(backtestResult.metrics.max_drawdown))}
                              </p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    </div>
                  )}

                  {/* Performance Chart - Only show if performance stats are enabled */}
                  {backtestResult.show_performance_stats && (
                    <Card className="w-full">
                      <CardHeader>
                        <CardTitle>Portfolio Performance</CardTitle>
                        <CardDescription>
                          Portfolio value over time from {formatDate(backtestResult.start_date)} to {formatDate(backtestResult.end_date)}
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <ChartContainer config={chartConfig} className="h-[400px] w-full">
                          <LineChart data={backtestResult.data_points}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis 
                              dataKey="date" 
                              tickFormatter={(value) => formatDate(value)}
                              tick={{ fontSize: 12 }}
                            />
                            <YAxis 
                              tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
                              tick={{ fontSize: 12 }}
                            />
                            <ChartTooltip content={<ChartTooltipContent />} />
                            <Line
                              type="monotone"
                              dataKey="portfolio_value"
                              stroke="var(--color-portfolio)"
                              strokeWidth={2}
                              dot={false}
                            />
                          </LineChart>
                        </ChartContainer>
                      </CardContent>
                    </Card>
                  )}

                  {/* Technical Analysis Charts */}
                  {backtestResult.include_technical_analysis && (
                    <div className="space-y-6">
                      {/* Moving Averages Chart */}
                      {(backtestResult.technical_indicators_requested.includes('dma_30') || 
                        backtestResult.technical_indicators_requested.includes('dma_100') || 
                        backtestResult.technical_indicators_requested.includes('dma_200')) && (
                        <Card className="w-full">
                          <CardHeader>
                            <CardTitle>Moving Averages Analysis</CardTitle>
                            <CardDescription>
                              Simple Moving Averages (SMA) for {backtestResult.target_assets.length > 0 ? backtestResult.target_assets.join(', ') : 'selected assets'}
                            </CardDescription>
                          </CardHeader>
                          <CardContent>
                            <ChartContainer config={chartConfig} className="h-[400px] w-full">
                              <LineChart data={backtestResult.data_points.filter(dp => 
                                dp.technical_indicators?.sma_30 !== null && dp.technical_indicators?.sma_30 !== undefined
                              ).map(dp => ({
                                ...dp,
                                sma_30: dp.technical_indicators?.sma_30,
                                sma_100: dp.technical_indicators?.sma_100,
                                sma_200: dp.technical_indicators?.sma_200
                              }))}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis 
                                  dataKey="date" 
                                  tickFormatter={(value) => formatDate(value)}
                                  tick={{ fontSize: 12 }}
                                />
                                <YAxis 
                                  tickFormatter={(value) => `$${value.toFixed(0)}`}
                                  tick={{ fontSize: 12 }}
                                />
                                <ChartTooltip content={<ChartTooltipContent />} />
                                {backtestResult.technical_indicators_requested.includes('dma_30') && (
                                  <Line
                                    type="monotone"
                                    dataKey="sma_30"
                                    stroke="var(--color-sma_30)"
                                    strokeWidth={2}
                                    dot={false}
                                    name="30-day SMA"
                                  />
                                )}
                                {backtestResult.technical_indicators_requested.includes('dma_100') && (
                                  <Line
                                    type="monotone"
                                    dataKey="sma_100"
                                    stroke="var(--color-sma_100)"
                                    strokeWidth={2}
                                    dot={false}
                                    name="100-day SMA"
                                  />
                                )}
                                {backtestResult.technical_indicators_requested.includes('dma_200') && (
                                  <Line
                                    type="monotone"
                                    dataKey="sma_200"
                                    stroke="var(--color-sma_200)"
                                    strokeWidth={2}
                                    dot={false}
                                    name="200-day SMA"
                                  />
                                )}
                              </LineChart>
                            </ChartContainer>
                          </CardContent>
                        </Card>
                      )}

                      {/* RSI Chart */}
                      {backtestResult.technical_indicators_requested.includes('rsi') && (
                        <Card className="w-full">
                          <CardHeader>
                            <CardTitle>Relative Strength Index (RSI)</CardTitle>
                            <CardDescription>
                              RSI with overbought (70) and oversold (30) levels for {backtestResult.target_assets.length > 0 ? backtestResult.target_assets.join(', ') : 'selected assets'}
                            </CardDescription>
                          </CardHeader>
                          <CardContent>
                            <ChartContainer config={chartConfig} className="h-[300px] w-full">
                              <LineChart data={backtestResult.data_points.filter(dp => 
                                dp.technical_indicators?.rsi !== null && dp.technical_indicators?.rsi !== undefined
                              ).map(dp => ({
                                ...dp,
                                rsi: Number(dp.technical_indicators?.rsi)
                              })).sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis 
                                  dataKey="date" 
                                  tickFormatter={(value) => formatDate(value)}
                                  tick={{ fontSize: 12 }}
                                />
                                <YAxis 
                                  domain={[0, 100]}
                                  tick={{ fontSize: 12 }}
                                />
                                <ChartTooltip content={<ChartTooltipContent />} />
                                <Line
                                  type="monotone"
                                  dataKey="rsi"
                                  stroke="#8884d8"
                                  strokeWidth={2}
                                  dot={false}
                                  name="RSI"
                                  connectNulls={false}
                                  isAnimationActive={true}
                                />
                                {/* Reference lines for overbought/oversold */}
                                <Line
                                  type="monotone"
                                  dataKey={() => 70}
                                  stroke="#ef4444"
                                  strokeWidth={1}
                                  strokeDasharray="3 3"
                                  dot={false}
                                  name="Overbought (70)"
                                />
                                <Line
                                  type="monotone"
                                  dataKey={() => 30}
                                  stroke="#ef4444"
                                  strokeWidth={1}
                                  strokeDasharray="3 3"
                                  dot={false}
                                  name="Oversold (30)"
                                />
                              </LineChart>
                            </ChartContainer>
                          </CardContent>
                        </Card>
                      )}

                      {/* Bollinger Bands Chart */}
                      {backtestResult.technical_indicators_requested.includes('bollinger_bands') && (
                        <Card className="w-full">
                          <CardHeader>
                            <CardTitle>Bollinger Bands Analysis</CardTitle>
                            <CardDescription>
                              Bollinger Bands (20-period, 2 standard deviations) for volatility analysis of {backtestResult.target_assets.length > 0 ? backtestResult.target_assets.join(', ') : 'selected assets'}
                            </CardDescription>
                          </CardHeader>
                          <CardContent>
                            <ChartContainer config={chartConfig} className="h-[400px] w-full">
                              <LineChart data={(() => {
                                const filteredData = backtestResult.data_points.filter(dp => 
                                  dp.technical_indicators?.bb_upper !== null && dp.technical_indicators?.bb_upper !== undefined
                                ).map(dp => ({
                                  ...dp,
                                  bb_upper: Number(dp.technical_indicators?.bb_upper),
                                  bb_middle: Number(dp.technical_indicators?.bb_middle),
                                  bb_lower: Number(dp.technical_indicators?.bb_lower)
                                })).sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
                                console.log('Bollinger Bands Chart Data:', filteredData.slice(0, 3));
                                return filteredData;
                              })()}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis 
                                  dataKey="date" 
                                  tickFormatter={(value) => formatDate(value)}
                                  tick={{ fontSize: 12 }}
                                />
                                <YAxis 
                                  tickFormatter={(value) => `$${value.toFixed(0)}`}
                                  tick={{ fontSize: 12 }}
                                />
                                <ChartTooltip content={<ChartTooltipContent />} />
                                <Line
                                  type="monotone"
                                  dataKey="bb_upper"
                                  stroke="#8884d8"
                                  strokeWidth={2}
                                  dot={false}
                                  name="Upper Band"
                                  connectNulls={false}
                                  isAnimationActive={true}
                                />
                                <Line
                                  type="monotone"
                                  dataKey="bb_middle"
                                  stroke="#82ca9d"
                                  strokeWidth={2}
                                  dot={false}
                                  name="Middle Band (SMA)"
                                  connectNulls={false}
                                  isAnimationActive={true}
                                />
                                <Line
                                  type="monotone"
                                  dataKey="bb_lower"
                                  stroke="#ffc658"
                                  strokeWidth={2}
                                  dot={false}
                                  name="Lower Band"
                                  connectNulls={false}
                                  isAnimationActive={true}
                                />
                              </LineChart>
                            </ChartContainer>
                          </CardContent>
                        </Card>
                      )}
                    </div>
                  )}

                  {/* Allocation Chart - Only show if performance stats are enabled */}
                  {backtestResult.show_performance_stats && (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 w-full">
                      <Card className="w-full">
                        <CardHeader>
                          <CardTitle className="flex items-center gap-2">
                            <PieChartIcon className="h-5 w-5" />
                            Portfolio Allocation
                          </CardTitle>
                          <CardDescription>
                            Final allocation percentages by asset
                          </CardDescription>
                        </CardHeader>
                        <CardContent>
                          <ChartContainer config={chartConfig} className="h-[300px] w-full">
                            <PieChart>
                              <Pie
                                data={backtestResult.allocations}
                                dataKey="allocation_percentage"
                                nameKey="symbol"
                                cx="50%"
                                cy="50%"
                                outerRadius={100}
                                label={({ symbol, allocation_percentage }) => 
                                  `${symbol}: ${allocation_percentage.toFixed(1)}%`
                                }
                              >
                                {backtestResult.allocations.map((_, index) => (
                                  <Cell key={`cell-${index}`} fill={allocationColors[index % allocationColors.length]} />
                                ))}
                              </Pie>
                              <ChartTooltip content={<ChartTooltipContent />} />
                            </PieChart>
                          </ChartContainer>
                        </CardContent>
                      </Card>

                      <Card className="w-full">
                        <CardHeader>
                          <CardTitle>Asset Performance</CardTitle>
                          <CardDescription>
                            Individual asset returns during backtest period
                          </CardDescription>
                        </CardHeader>
                        <CardContent>
                          <ChartContainer config={chartConfig} className="h-[300px] w-full">
                            <BarChart data={backtestResult.allocations}>
                              <CartesianGrid strokeDasharray="3 3" />
                              <XAxis 
                                dataKey="symbol" 
                                tick={{ fontSize: 12 }}
                                angle={-45}
                                textAnchor="end"
                                height={80}
                              />
                              <YAxis 
                                tickFormatter={(value) => `${value.toFixed(1)}%`}
                                tick={{ fontSize: 12 }}
                              />
                              <ChartTooltip content={<ChartTooltipContent />} />
                              <Bar dataKey="total_return" fill="#10b981">
                                {backtestResult.allocations.map((entry, index) => (
                                  <Cell key={`cell-${index}`} fill={entry.total_return >= 0 ? '#10b981' : '#ef4444'} />
                                ))}
                              </Bar>
                            </BarChart>
                          </ChartContainer>
                        </CardContent>
                      </Card>
                    </div>
                  )}
                </div>
              )
            })}
        </div>
      )}
      </div>

      {/* Fixed Chat Interface at Bottom */}
      <div className="fixed bottom-0 left-0 right-0 bg-gradient-to-br from-black via-zinc-900 to-neutral-900 shadow-lg px-4 py-2">
        <div className="max-w-7xl mx-auto">
          <Card className="rounded-lg border shadow-sm bg-zinc-800/50 backdrop-blur-sm border-zinc-700">
            <CardHeader className="pb-2">
              
            </CardHeader>
            <CardContent className="pt-0">
            {/* Chat Messages */}
            <div className="h-48 overflow-y-auto border rounded-lg p-3 mb-3 bg-zinc-900/50 border-zinc-700">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex gap-3 mb-4 ${
                    message.type === 'user' ? 'justify-end' : 'justify-start'
                  }`}
                >
                {message.type === 'assistant' && (
                  <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center">
                    <Bot className="h-4 w-4 text-purple-400" />
                  </div>
                )}
                
                <div
                  className={`max-w-[80%] rounded-lg p-3 ${
                    message.type === 'user'
                      ? 'bg-gradient-to-r from-blue-500 to-purple-600 text-white'
                      : 'bg-zinc-800 border border-zinc-700 text-white'
                  }`}
                >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-white">
                        {message.type === 'user' ? 'You' : 'Assistant'}
                      </span>
                      <span className="text-xs text-zinc-400">
                        {formatTimestamp(message.timestamp)}
                      </span>
                      {message.success !== undefined && (
                        message.success ? (
                          <CheckCircle className="h-4 w-4 text-green-500" />
                        ) : (
                          <XCircle className="h-4 w-4 text-red-500" />
                        )
                      )}
                    </div>
                    
                    <div className="text-sm whitespace-pre-wrap">{message.content}</div>
                    
                    {message.parsedIntent && renderIntentBadge(message.parsedIntent)}
                    
                    {message.parsedIntent?.custom_allocations && (
                      <div className="mt-3 p-3 bg-blue-50 rounded-lg border border-blue-200">
                        <h4 className="text-sm font-semibold text-blue-800 mb-2">Custom Portfolio Allocation:</h4>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          {Object.entries(message.parsedIntent.custom_allocations).map(([asset, percentage]) => (
                            <div key={asset} className="flex justify-between">
                              <span className="text-blue-700">{asset.replace('/USDT', '')}:</span>
                              <span className="font-medium text-blue-800">{percentage as number}%</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                  
                  {message.type === 'user' && (
                    <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center">
                      <User className="h-4 w-4 text-blue-400" />
                    </div>
                  )}
                </div>
              ))}
              
              {isLoading && (
                <div className="flex gap-3 mb-4 justify-start">
                  <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center">
                    <Bot className="h-4 w-4 text-purple-400" />
                  </div>
                  <div className="bg-zinc-800 border border-zinc-700 rounded-lg p-3">
                    <div className="flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin text-purple-400" />
                      <span className="text-sm text-white">Processing your request...</span>
                    </div>
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="flex gap-2">
              <Input
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Try: 'Plot RSI for Bitcoin' or 'Show moving averages for ETH and ADA' or 'Backtest conservative strategy with technical analysis'"
                disabled={isLoading}
                className="flex-1 bg-zinc-800 border-zinc-700 text-white placeholder:text-zinc-400 focus:border-purple-500"
              />
              <Button
                onClick={handleSendMessage}
                disabled={!inputValue.trim() || isLoading}
                size="icon"
                className="bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 border-0"
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
        </div>
      </div>
    </div>
  )
}
