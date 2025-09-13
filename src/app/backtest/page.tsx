"use client"

import React, { useState, useRef, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ChartContainer, ChartTooltip, ChartTooltipContent, ChartLegend, ChartLegendContent } from '@/components/ui/chart'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer, PieChart, Pie, Cell, BarChart, Bar } from 'recharts'
import { Badge } from '@/components/ui/badge'
import { TrendingUp, TrendingDown, DollarSign, BarChart3, PieChart as PieChartIcon, Send, Bot, User, CheckCircle, XCircle, Loader2 } from 'lucide-react'
import agentsApi from '@/lib/agents_api'

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

interface BacktestDataPoint {
  date: string
  portfolio_value: number
  daily_return: number
  cumulative_return: number
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

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

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
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      type: 'assistant',
      content: 'Hello! I can help you backtest crypto portfolio strategies. Try saying "Backtest conservative strategy from 10/01/2024 to 10/09/2025 with an initial capital of 1000 USD with monthly rebalancing" or "Test aggressive strategy from 2024-01-01 to 2024-12-31 with 5000 USD".',
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
      const response = await agentsApi.post('/api/v1/query', {
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
              {intent.strategy}
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
    <div className="container mx-auto p-6 space-y-6">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-bold">Portfolio Backtesting</h1>
        <p className="text-muted-foreground">
          Test crypto portfolio strategies with natural language commands
        </p>
      </div>

      {/* Chat Interface */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            Backtest Chat
          </CardTitle>
          <CardDescription>
            Describe your backtest requirements in natural language
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Chat Messages */}
          <div className="h-96 overflow-y-auto border rounded-lg p-4 mb-4 bg-muted/20">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex gap-3 mb-4 ${
                  message.type === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                {message.type === 'assistant' && (
                  <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                    <Bot className="h-4 w-4 text-primary" />
                  </div>
                )}
                
                <div
                  className={`max-w-[80%] rounded-lg p-3 ${
                    message.type === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-background border'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium">
                      {message.type === 'user' ? 'You' : 'Assistant'}
                    </span>
                    <span className="text-xs text-muted-foreground">
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
                </div>
                
                {message.type === 'user' && (
                  <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                    <User className="h-4 w-4 text-primary" />
                  </div>
                )}
              </div>
            ))}
            
            {isLoading && (
              <div className="flex gap-3 mb-4 justify-start">
                <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
                <div className="bg-background border rounded-lg p-3">
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="text-sm">Processing your request...</span>
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
              placeholder="Try: 'Backtest conservative strategy from 10/01/2024 to 09/09/2025 with 1000 USD'"
              disabled={isLoading}
              className="flex-1"
            />
            <Button
              onClick={handleSendMessage}
              disabled={!inputValue.trim() || isLoading}
              size="icon"
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Display backtest results if available */}
      {messages.some(m => m.backtestResult) && (
        <div className="space-y-6">
          {messages
            .filter(m => m.backtestResult)
            .map((message) => {
              const backtestResult = message.backtestResult!
              return (
                <div key={message.id} className="space-y-6">
                  {/* Summary Cards */}
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
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
                            <p className="text-2xl font-bold text-green-600">
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
                              {formatPercentage(backtestResult.metrics.max_drawdown)}
                            </p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </div>

                  {/* Performance Chart */}
                  <Card>
                    <CardHeader>
                      <CardTitle>Portfolio Performance</CardTitle>
                      <CardDescription>
                        Portfolio value over time from {formatDate(backtestResult.start_date)} to {formatDate(backtestResult.end_date)}
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <ChartContainer config={chartConfig} className="h-[400px]">
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

                  {/* Allocation Chart */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <Card>
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
                        <ChartContainer config={chartConfig} className="h-[300px]">
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

                    <Card>
                      <CardHeader>
                        <CardTitle>Asset Performance</CardTitle>
                        <CardDescription>
                          Individual asset returns during backtest period
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <ChartContainer config={chartConfig} className="h-[300px]">
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
                            <Bar dataKey="total_return" fill="var(--color-portfolio)" />
                          </BarChart>
                        </ChartContainer>
                      </CardContent>
                    </Card>
                  </div>
                </div>
              )
            })}
        </div>
      )}
    </div>
  )
}
