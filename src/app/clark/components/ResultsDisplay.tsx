"use client"

import React, { useState } from 'react'
import dynamic from 'next/dynamic'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { DollarSign, TrendingUp, BarChart3, TrendingDown, ChevronDown, ChevronUp } from 'lucide-react'
import { Loader2, Info, User } from 'lucide-react'
import { ChatMessage, BacktestResult, ScreenerResult, EconomicResult, NewsData, CalendarData, EconomicData, RegulationResult, AgentFlowGraph, AgentFlowStep, BalanceResult, BalanceEntry, DailyBalanceEntry, IntradayBalanceEntry } from '../types'
import { formatCurrency, formatPercentage, formatDate, formatNumber, formatTimestamp } from '../utils'
import TransactionStatus, { InlineTransactionData } from './TransactionStatus'

// Dynamically import heavy chart components to reduce initial bundle size
const PortfolioChart = dynamic(() => import('./charts/PortfolioChart'), {
  loading: () => <div className="flex items-center justify-center p-8"><Loader2 className="h-6 w-6 animate-spin" /></div>,
  ssr: false,
});

const TechnicalCharts = dynamic(() => import('./charts/TechnicalCharts'), {
  loading: () => <div className="flex items-center justify-center p-8"><Loader2 className="h-6 w-6 animate-spin" /></div>,
  ssr: false,
});

const AllocationCharts = dynamic(() => import('./charts/AllocationCharts'), {
  loading: () => <div className="flex items-center justify-center p-8"><Loader2 className="h-6 w-6 animate-spin" /></div>,
  ssr: false,
});

const CandleChart = dynamic(() => import('./charts/CandleChart'), {
  loading: () => <div className="flex items-center justify-center p-8"><Loader2 className="h-6 w-6 animate-spin" /></div>,
  ssr: false,
});

const PriceHistoryChart = dynamic(() => import('./charts/PriceHistoryChart'), {
  loading: () => <div className="flex items-center justify-center p-8"><Loader2 className="h-6 w-6 animate-spin" /></div>,
  ssr: false,
});

const BalanceHistoryChartLazy = dynamic(() => import('./charts/BalanceHistoryChart'), {
  loading: () => <div className="flex items-center justify-center p-8"><Loader2 className="h-6 w-6 animate-spin" /></div>,
  ssr: false,
});

interface ResultsDisplayProps {
  messages: ChatMessage[]
  isLoading?: boolean
  username?: string
}

export default function ResultsDisplay({ messages, isLoading, username }: ResultsDisplayProps) {
  const [revealedAssistantIds, setRevealedAssistantIds] = useState<Set<string>>(new Set())
  const [expandedTradeTables, setExpandedTradeTables] = useState<Set<string>>(new Set())
  const hasAnyContent = messages.length > 0
  if (!hasAnyContent) return null

  const hasStructuredResults = (message?: ChatMessage | null) =>
    Boolean(
      message && message.backtestResult
    )

  const formatSourceLabel = (source?: string) => {
    if (!source) return null
    if (source === 'llm_fallback') {
      return 'LLM fallback response'
    }
    return source.replace(/_/g, ' ')
  }

  /** Format balances for display: backend may send array [{ token, balance }] or object { token: balance } */
  const formatBalancesCell = (balances: unknown): string => {
    if (balances == null) return '—'
    if (Array.isArray(balances)) {
      return balances
        .map((e: { token?: string; balance?: unknown }) => {
          const t = e?.token ?? ''
          const b = e?.balance != null ? String(e.balance) : ''
          return t ? `${t}: ${b}` : ''
        })
        .filter(Boolean)
        .join(', ') || '—'
    }
    if (typeof balances === 'object' && !Array.isArray(balances)) {
      return Object.entries(balances as Record<string, unknown>)
        .map(([t, b]) => `${t}: ${b != null ? String(b) : ''}`)
        .join(', ') || '—'
    }
    return '—'
  }

  const renderEconomic = (message: ChatMessage) => {
    if (!message.economicResult) return null
    const economicResult = message.economicResult
    
    // If we only have markdown (from economic agent), render it as markdown
    if (economicResult.markdown && !economicResult.results) {
      return (
        <Card key={`econ-${message.id}`} className="w-full bg-teal-800/20 border-teal-700/30 backdrop-blur-sm">
          <CardHeader className="pb-4">
            <CardTitle className="text-lg text-white">Economic Data</CardTitle>
          </CardHeader>
          <CardContent>
            <div
              className="text-sm leading-relaxed prose prose-invert max-w-none"
              dangerouslySetInnerHTML={{ __html: markdownToHtml(economicResult.markdown) }}
            />
          </CardContent>
        </Card>
      )
    }
    
    // Otherwise, render structured data
    const isNews = economicResult.indicator === 'news'
    const isCalendar = economicResult.indicator === 'calendar'
    return (
      <Card key={`econ-${message.id}`} className="w-full bg-teal-800/20 border-teal-700/30 backdrop-blur-sm">
        <CardHeader className="pb-4">
          <CardTitle className="text-lg text-white">{economicResult.indicator_name || 'Economic Data'}</CardTitle>
          <CardDescription className="text-teal-200/70">
            {isNews ? `${economicResult.total_found || 0} latest news articles` :
             isCalendar ? `${economicResult.total_found || 0} upcoming economic events` :
             `Economic indicators for ${economicResult.total_found || 0} countries`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            {isNews ? (
              <div className="space-y-4">
                {(economicResult.results as NewsData[]).map((news, index) => (
                  <div key={news.id || index} className="border-b border-teal-800/30 pb-4 hover:bg-teal-900/30 transition-colors p-4 rounded-lg">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h3 className="text-lg font-semibold text-white mb-2">{news.title}</h3>
                        {news.description && (
                          <p className="text-sm text-teal-200/70 mb-2">{news.description}</p>
                        )}
                        <div className="flex items-center gap-4 text-xs text-teal-300/60">
                          <span>{new Date(news.date).toLocaleDateString()}</span>
                          {news.country && <span>• {news.country}</span>}
                          {news.category && <span>• {news.category}</span>}
                        </div>
                      </div>
                      {news.url && (
                        <a
                          href={news.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="ml-4 text-cyan-400 hover:text-cyan-300 text-sm"
                        >
                          Read more →
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : isCalendar ? (
              <table className="w-full">
                <thead>
                  <tr className="border-b border-teal-700/30">
                    <th className="text-left py-3 px-4 text-sm font-semibold text-teal-200/70">Date</th>
                    <th className="text-left py-3 px-4 text-sm font-semibold text-teal-200/70">Country</th>
                    <th className="text-left py-3 px-4 text-sm font-semibold text-teal-200/70">Event</th>
                    <th className="text-right py-3 px-4 text-sm font-semibold text-teal-200/70">Actual</th>
                    <th className="text-right py-3 px-4 text-sm font-semibold text-teal-200/70">Forecast</th>
                    <th className="text-right py-3 px-4 text-sm font-semibold text-teal-200/70">Previous</th>
                  </tr>
                </thead>
                <tbody>
                  {(economicResult.results as CalendarData[]).map((event, index) => (
                    <tr key={event.event_id || index} className="border-b border-teal-800/30 hover:bg-teal-900/30 transition-colors">
                      <td className="py-3 px-4 text-sm text-white/90">
                        {new Date(event.date).toLocaleDateString()}
                      </td>
                      <td className="py-3 px-4 text-sm font-medium text-white">{event.country}</td>
                      <td className="py-3 px-4 text-sm text-white/90">
                        <div>
                          <div className="font-medium text-white">{event.event}</div>
                          {event.category && <div className="text-xs text-teal-300/60">{event.category}</div>}
                        </div>
                      </td>
                      <td className="py-3 px-4 text-sm text-right text-white font-medium">
                        {event.actual !== null && event.actual !== undefined ? event.actual : '-'}
                      </td>
                      <td className="py-3 px-4 text-sm text-right text-white/90">
                        {event.forecast !== null && event.forecast !== undefined ? event.forecast : '-'}
                      </td>
                      <td className="py-3 px-4 text-sm text-right text-white/90">
                        {event.previous !== null && event.previous !== undefined ? event.previous : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : economicResult.results && Array.isArray(economicResult.results) && economicResult.results.length > 0 ? (
              <table className="w-full">
                <thead>
                  <tr className="border-b border-teal-700/30">
                    <th className="text-left py-3 px-4 text-sm font-semibold text-teal-200/70">Rank</th>
                    <th className="text-left py-3 px-4 text-sm font-semibold text-teal-200/70">Country</th>
                    <th className="text-right py-3 px-4 text-sm font-semibold text-teal-200/70">Current Value</th>
                    <th className="text-right py-3 px-4 text-sm font-semibold text-teal-200/70">Previous Value</th>
                    <th className="text-right py-3 px-4 text-sm font-semibold text-teal-200/70">Change</th>
                    <th className="text-left py-3 px-4 text-sm font-semibold text-teal-200/70">Unit</th>
                    <th className="text-left py-3 px-4 text-sm font-semibold text-teal-200/70">Last Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {(economicResult.results as EconomicData[]).map((data, index) => {
                    const hasValue = data.value !== null && data.value !== undefined && typeof data.value === 'number'
                    const hasPreviousValue = data.previous_value !== null && data.previous_value !== undefined && typeof data.previous_value === 'number'
                    const change = hasValue && hasPreviousValue
                      ? (data.value as number) - (data.previous_value as number)
                      : null
                    const changePercent = hasValue && hasPreviousValue && (data.previous_value as number) !== 0
                      ? (((data.value as number) - (data.previous_value as number)) / (data.previous_value as number)) * 100
                      : null
                    return (
                      <tr key={data.country || index} className="border-b border-teal-800/30 hover:bg-teal-900/30 transition-colors">
                        <td className="py-3 px-4 text-sm text-white/90">{index + 1}</td>
                        <td className="py-3 px-4 text-sm font-medium text-white">{data.country || 'N/A'}</td>
                        <td className="py-3 px-4 text-sm text-right text-white font-medium">
                          {hasValue && typeof data.value === 'number' ? data.value.toLocaleString() : 'N/A'}
                        </td>
                        <td className="py-3 px-4 text-sm text-right text-white/90">
                          {hasPreviousValue && typeof data.previous_value === 'number' ? data.previous_value.toLocaleString() : 'N/A'}
                        </td>
                        <td className={`py-3 px-4 text-sm text-right font-medium ${
                          change !== null && change > 0 ? 'text-green-500' :
                          change !== null && change < 0 ? 'text-red-500' : 'text-white/90'
                        }`}>
                          {change !== null ? (
                            <>
                              {change > 0 ? '+' : ''}{change.toFixed(2)}
                              {changePercent !== null && (
                                <span className="ml-1 text-xs">({changePercent > 0 ? '+' : ''}{changePercent.toFixed(1)}%)</span>
                              )}
                            </>
                          ) : 'N/A'}
                        </td>
                        <td className="py-3 px-4 text-sm text-white/90">{data.unit || 'N/A'}</td>
                        <td className="py-3 px-4 text-sm text-white/90">
                          {data.date ? new Date(data.date).toLocaleDateString() : 'N/A'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            ) : (
              // Fallback: show markdown if available, or a message
              <div className="text-sm text-teal-200/70">
                {economicResult.markdown ? (
                  <div
                    className="text-sm leading-relaxed prose prose-invert max-w-none"
                    dangerouslySetInnerHTML={{ __html: markdownToHtml(economicResult.markdown) }}
                  />
                ) : (
                  'No economic data available'
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    )
  }

  const renderRegulation = (message: ChatMessage) => {
    if (!message.regulationResult) return null
    const regulationResult = message.regulationResult as RegulationResult
    const summary = regulationResult.summary || message.content
    const summaryHtml = summary ? markdownToHtml(summary) : ''
    return (
      <Card key={`reg-${message.id}`} className="w-full bg-teal-800/20 border-teal-700/30 backdrop-blur-sm">
        <CardHeader className="pb-4">
          <CardTitle className="text-lg text-white">Regulation Guidance</CardTitle>
          {/* <CardDescription className="text-teal-200/70">
            {regulationResult.jurisdiction
              ? `Focus: ${regulationResult.jurisdiction}`
              : 'Jurisdiction not specified'}
          </CardDescription> */}
        </CardHeader>
        <CardContent className="space-y-4">
          {summary && (
            <div
              className="bg-zinc-900/40 border border-teal-700/30/40 rounded-xl p-4 text-sm text-white leading-relaxed"
              dangerouslySetInnerHTML={{ __html: summaryHtml }}
            />
          )}
          <div className="space-y-3">
            {regulationResult.matches.map((match, index) => (
              <div key={`${match.title}-${index}`} className="rounded-lg border border-teal-800/30 bg-teal-900/20 p-4 hover:border-teal-400/50 transition-colors">
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-semibold text-white">{match.title}</h3>
                    <div className="text-xs text-teal-200/70">
                      {match.jurisdiction && <span>{match.jurisdiction}</span>}
                      {match.source_title && (
                        <span className={match.jurisdiction ? 'ml-2' : ''}>{match.source_title}</span>
                      )}
                    </div>
                  </div>
                  {match.url && (
                    <a
                      href={match.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-cyan-400 hover:text-cyan-300"
                    >
                      View source →
                    </a>
                  )}
                </div>
                {match.description && (
                  <p className="mt-2 text-xs text-teal-200/70">{match.description}</p>
                )}
                <p className="mt-2 text-sm text-white/90 whitespace-pre-wrap leading-relaxed">
                  {match.snippet}
                </p>
                <div className="mt-2 text-xs text-teal-300/60">Relevance score: {match.score.toFixed(2)}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  const renderScreener = (message: ChatMessage) => {
    if (!message.screenerResult) return null
    const screenerResult = message.screenerResult
    
    // Handle stock/crypto/forex quotes and profiles
    const isStockQuote = screenerResult.screener_type === 'stock_quote'
    const isStockScreener = screenerResult.screener_type === 'stock_screener'
    const isStockProfile = screenerResult.screener_type === 'stock_profile'
    const isCryptoQuote = screenerResult.screener_type === 'crypto_quote'
    const isForexQuote = screenerResult.screener_type === 'forex_quote'
    
    if (isStockQuote || isStockProfile) {
      // Single stock display
      if (!screenerResult.results || screenerResult.results.length === 0) {
        return (
          <Card key={`stock-${message.id}`} className="w-full bg-teal-800/20 border-teal-700/30 backdrop-blur-sm">
            <CardHeader className="pb-4">
              <CardTitle className="text-lg text-white">No Data Available</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-teal-200/70">No stock data found for this query.</p>
            </CardContent>
          </Card>
        )
      }
      const stock = screenerResult.results[0]
      return (
        <Card key={`stock-${message.id}`} className="w-full bg-teal-800/20 border-teal-700/30 backdrop-blur-sm">
          <CardHeader className="pb-4">
            <CardTitle className="text-lg text-white">
              {isStockProfile ? 'Company Profile' : 'Stock Quote'} - {stock.name || stock.symbol}
            </CardTitle>
            <CardDescription className="text-teal-200/70">
              {stock.symbol} {stock.exchange && `• ${stock.exchange}`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <div className="text-xs text-teal-200/70 mb-1">Price</div>
                  <div className="text-xl font-bold text-white">{formatCurrency(stock.price)}</div>
                </div>
                {stock.daily_change_percent !== undefined && (
                  <div>
                    <div className="text-xs text-teal-200/70 mb-1">24h Change</div>
                    <div className={`text-xl font-bold ${stock.daily_change_percent >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      {stock.daily_change_percent >= 0 ? '+' : ''}{stock.daily_change_percent.toFixed(2)}%
                    </div>
                  </div>
                )}
                {stock.market_cap && (
                  <div>
                    <div className="text-xs text-teal-200/70 mb-1">Market Cap</div>
                    <div className="text-xl font-bold text-white">{formatNumber(stock.market_cap)}</div>
                  </div>
                )}
                {stock.volume_24h && (
                  <div>
                    <div className="text-xs text-teal-200/70 mb-1">Volume</div>
                    <div className="text-xl font-bold text-white">{formatNumber(stock.volume_24h)}</div>
                  </div>
                )}
              </div>
              {isStockProfile && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-teal-700/30">
                  {stock.sector && (
                    <div>
                      <div className="text-xs text-teal-200/70 mb-1">Sector</div>
                      <div className="text-sm text-white">{stock.sector}</div>
                    </div>
                  )}
                  {stock.industry && (
                    <div>
                      <div className="text-xs text-teal-200/70 mb-1">Industry</div>
                      <div className="text-sm text-white">{stock.industry}</div>
                    </div>
                  )}
                  {stock.ceo && (
                    <div>
                      <div className="text-xs text-teal-200/70 mb-1">CEO</div>
                      <div className="text-sm text-white">{stock.ceo}</div>
                    </div>
                  )}
                  {stock.website && (
                    <div>
                      <div className="text-xs text-teal-200/70 mb-1">Website</div>
                      <a href={stock.website} target="_blank" rel="noopener noreferrer" className="text-sm text-cyan-400 hover:text-cyan-300">
                        {stock.website}
                      </a>
                    </div>
                  )}
                  {stock.description && (
                    <div className="md:col-span-2">
                      <div className="text-xs text-teal-200/70 mb-1">Description</div>
                      <div className="text-sm text-white/90">{stock.description}</div>
                    </div>
                  )}
                </div>
              )}
              {(stock.day_low || stock.day_high || stock.year_low || stock.year_high) && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-teal-700/30">
                  {stock.day_low && (
                    <div>
                      <div className="text-xs text-teal-200/70 mb-1">Day Low</div>
                      <div className="text-sm text-white">{formatCurrency(stock.day_low)}</div>
                    </div>
                  )}
                  {stock.day_high && (
                    <div>
                      <div className="text-xs text-teal-200/70 mb-1">Day High</div>
                      <div className="text-sm text-white">{formatCurrency(stock.day_high)}</div>
                    </div>
                  )}
                  {stock.year_low && (
                    <div>
                      <div className="text-xs text-teal-200/70 mb-1">52W Low</div>
                      <div className="text-sm text-white">{formatCurrency(stock.year_low)}</div>
                    </div>
                  )}
                  {stock.year_high && (
                    <div>
                      <div className="text-xs text-teal-200/70 mb-1">52W High</div>
                      <div className="text-sm text-white">{formatCurrency(stock.year_high)}</div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )
    }
    
    return (
      <Card key={`scr-${message.id}`} className="w-full bg-teal-800/20 border-teal-700/30 backdrop-blur-sm">
        <CardHeader className="pb-4">
          <CardTitle className="text-lg text-white">
            {screenerResult.screener_type === 'price' && 'Price Screener Results'}
            {screenerResult.screener_type === 'daily_change' && 'Daily Change Screener Results'}
            {screenerResult.screener_type === 'market_cap' && 'Market Cap Screener Results'}
            {screenerResult.screener_type === 'ema' && 'EMA Screener Results'}
            {isStockScreener && 'Stock Screener Results'}
            {isCryptoQuote && 'Cryptocurrency Quotes'}
            {isForexQuote && 'Forex Quotes'}
          </CardTitle>
          <CardDescription className="text-teal-200/70">
            {screenerResult.range_description} • {screenerResult.total_found} {isStockScreener ? 'stocks' : isCryptoQuote ? 'cryptocurrencies' : isForexQuote ? 'forex pairs' : 'cryptos'} found
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-teal-700/30">
                  <th className="text-left py-3 px-4 text-sm font-semibold text-teal-200/70">Rank</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-teal-200/70">Name</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-teal-200/70">Symbol</th>
                  <th className="text-right py-3 px-4 text-sm font-semibold text-teal-200/70">Price</th>
                  <th className="text-right py-3 px-4 text-sm font-semibold text-teal-200/70">24h Change</th>
                  {screenerResult.screener_type === '52w_high_low' && (
                    <th className="text-right py-3 px-4 text-sm font-semibold text-teal-200/70">From High/Low</th>
                  )}
                  {screenerResult.screener_type === 'rsi' && (
                    <th className="text-right py-3 px-4 text-sm font-semibold text-teal-200/70">RSI</th>
                  )}
                  {screenerResult.screener_type === 'technical_pattern' && (
                    <>
                      <th className="text-right py-3 px-4 text-sm font-semibold text-teal-200/70">50 SMA</th>
                      <th className="text-right py-3 px-4 text-sm font-semibold text-teal-200/70">200 SMA</th>
                    </>
                  )}
                  {screenerResult.screener_type === 'ema' && (
                    <>
                      <th className="text-right py-3 px-4 text-sm font-semibold text-teal-200/70">5 EMA</th>
                      <th className="text-right py-3 px-4 text-sm font-semibold text-teal-200/70">10 EMA</th>
                    </>
                  )}
                  {isStockScreener && (
                    <>
                      <th className="text-left py-3 px-4 text-sm font-semibold text-teal-200/70">Sector</th>
                      <th className="text-left py-3 px-4 text-sm font-semibold text-teal-200/70">Exchange</th>
                    </>
                  )}
                  {!isForexQuote && (
                    <>
                      <th className="text-right py-3 px-4 text-sm font-semibold text-teal-200/70">Market Cap</th>
                      <th className="text-right py-3 px-4 text-sm font-semibold text-teal-200/70">Volume (24h)</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {screenerResult.results.map((item: any, index) => (
                  <tr key={item.symbol || index} className="border-b border-teal-800/30 hover:bg-teal-900/30 transition-colors">
                    <td className="py-3 px-4 text-sm text-white/90">{item.rank || index + 1}</td>
                    <td className="py-3 px-4 text-sm font-medium text-white">{item.name || item.symbol}</td>
                    <td className="py-3 px-4 text-sm text-white/90">{item.symbol}</td>
                    <td className="py-3 px-4 text-sm text-right text-white">{formatCurrency(item.price)}</td>
                    <td className={`py-3 px-4 text-sm text-right font-medium ${
                      (item.daily_change_percent || 0) >= 0 ? 'text-green-500' : 'text-red-500'
                    }`}>
                      {(item.daily_change_percent || 0) >= 0 ? '+' : ''}{(item.daily_change_percent || 0).toFixed(2)}%
                    </td>
                    {screenerResult.screener_type === '52w_high_low' && (
                      <td className={`py-3 px-4 text-sm text-right font-medium ${
                        item.percent_from_high !== undefined && item.percent_from_high >= -10 ? 'text-green-500' :
                        item.percent_from_low !== undefined && item.percent_from_low <= 10 ? 'text-red-500' : 'text-white/90'
                      }`}>
                        {item.percent_from_high !== undefined ? `${item.percent_from_high.toFixed(1)}% from high` :
                         item.percent_from_low !== undefined ? `${item.percent_from_low.toFixed(1)}% from low` : 'N/A'}
                      </td>
                    )}
                    {screenerResult.screener_type === 'rsi' && (
                      <td className={`py-3 px-4 text-sm text-right font-medium ${
                        item.rsi !== undefined && item.rsi <= 30 ? 'text-red-500' :
                        item.rsi !== undefined && item.rsi >= 70 ? 'text-green-500' : 'text-white/90'
                      }`}>
                        {item.rsi !== undefined ? item.rsi.toFixed(1) : 'N/A'}
                      </td>
                    )}
                    {screenerResult.screener_type === 'technical_pattern' && (
                      <>
                        <td className="py-3 px-4 text-sm text-right text-white/90">
                          {item.sma_50 !== undefined ? formatCurrency(item.sma_50) : 'N/A'}
                        </td>
                        <td className="py-3 px-4 text-sm text-right text-white/90">
                          {item.sma_200 !== undefined ? formatCurrency(item.sma_200) : 'N/A'}
                        </td>
                      </>
                    )}
                    {screenerResult.screener_type === 'ema' && (
                      <>
                        <td className="py-3 px-4 text-sm text-right text-white/90">
                          {item.ema_5 !== undefined ? formatCurrency(item.ema_5) : 'N/A'}
                        </td>
                        <td className="py-3 px-4 text-sm text-right text-white/90">
                          {item.ema_10 !== undefined ? formatCurrency(item.ema_10) : 'N/A'}
                        </td>
                      </>
                    )}
                    {isStockScreener && (
                      <>
                        <td className="py-3 px-4 text-sm text-white/90">{item.sector || 'N/A'}</td>
                        <td className="py-3 px-4 text-sm text-white/90">{item.exchange || 'N/A'}</td>
                      </>
                    )}
                    {screenerResult.screener_type !== 'forex_quote' && (
                      <>
                        <td className="py-3 px-4 text-sm text-right text-white/90">{formatNumber(item.market_cap || 0)}</td>
                        <td className="py-3 px-4 text-sm text-right text-white/90">{formatNumber(item.volume_24h || 0)}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    )
  }

  const renderBacktest = (message: ChatMessage) => {
    if (!message.backtestResult) return null
    const backtestResult = message.backtestResult
    const isTechnicalAnalysisOnly = backtestResult.include_technical_analysis && !backtestResult.show_performance_stats
    return (
      <div key={`bt-${message.id}`} className="space-y-4">
        {backtestResult.show_performance_stats && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 w-full">
            <Card className="bg-teal-800/20 border-teal-700/30 backdrop-blur-sm">
              <CardContent className="p-4">
                <div className="flex items-center space-x-3">
                  <DollarSign className="h-5 w-5 text-green-400" />
                  <div>
                    <p className="text-xs font-medium text-teal-200/70">Final Value</p>
                    <p className="text-xl font-bold text-white">{formatCurrency(backtestResult.final_capital)}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-teal-800/20 border-teal-700/30 backdrop-blur-sm">
              <CardContent className="p-4">
                <div className="flex items-center space-x-3">
                  <TrendingUp className="h-5 w-5 text-cyan-400" />
                  <div>
                    <p className="text-xs font-medium text-teal-200/70">Total Return</p>
                    <p className={`text-xl font-bold ${
                      backtestResult.metrics.total_return >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {formatPercentage(backtestResult.metrics.total_return)}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-teal-800/20 border-teal-700/30 backdrop-blur-sm">
              <CardContent className="p-4">
                <div className="flex items-center space-x-3">
                  <BarChart3 className="h-5 w-5 text-teal-400" />
                  <div>
                    <p className="text-xs font-medium text-teal-200/70">Sharpe Ratio</p>
                    <p className="text-xl font-bold text-white">{backtestResult.metrics.sharpe_ratio.toFixed(2)}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-teal-800/20 border-teal-700/30 backdrop-blur-sm">
              <CardContent className="p-4">
                <div className="flex items-center space-x-3">
                  <TrendingDown className="h-5 w-5 text-red-400" />
                  <div>
                    <p className="text-xs font-medium text-teal-200/70">Max Drawdown</p>
                    <p className="text-xl font-bold text-red-400">
                      {formatPercentage(Math.abs(backtestResult.metrics.max_drawdown))}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Trades Table - Show if trades exist */}
        {!isTechnicalAnalysisOnly && backtestResult.trades && backtestResult.trades.length > 0 && (() => {
          const tableId = `trades-${message.id}`
          const isExpanded = expandedTradeTables.has(tableId)
          return (
            <Card className="bg-teal-800/20 border-teal-700/30 backdrop-blur-sm">
              <CardHeader className="pb-4">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-lg text-white">Trade History</CardTitle>
                    <CardDescription className="text-teal-200/70">
                      {backtestResult.trades.length} {backtestResult.trades.length === 1 ? 'trade' : 'trades'} executed during backtest
                    </CardDescription>
                  </div>
                  <button
                    onClick={() => {
                      setExpandedTradeTables(prev => {
                        const next = new Set(prev)
                        if (isExpanded) {
                          next.delete(tableId)
                        } else {
                          next.add(tableId)
                        }
                        return next
                      })
                    }}
                    className="flex items-center gap-2 px-3 py-2 text-sm text-teal-200/70 hover:text-white transition-colors rounded-lg hover:bg-teal-700/30"
                    aria-label={isExpanded ? 'Collapse trades table' : 'Expand trades table'}
                  >
                    <span>{isExpanded ? 'Hide' : 'Show'} Details</span>
                    {isExpanded ? (
                      <ChevronUp className="h-4 w-4" />
                    ) : (
                      <ChevronDown className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </CardHeader>
              {isExpanded && (
                <CardContent>
                  {backtestResult.metrics.total_trades !== null && backtestResult.metrics.total_trades !== undefined && backtestResult.metrics.total_trades > 0 && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 w-full mb-4">
                      <Card className="bg-teal-900/30 border-teal-700/50">
                        <CardContent className="p-4">
                          <div className="flex items-center space-x-3">
                            <BarChart3 className="h-5 w-5 text-cyan-400" />
                            <div>
                              <p className="text-xs font-medium text-teal-200/70">Total Trades</p>
                              <p className="text-xl font-bold text-white">{backtestResult.metrics.total_trades}</p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>

                      <Card className="bg-teal-900/30 border-teal-700/50">
                        <CardContent className="p-4">
                          <div className="flex items-center space-x-3">
                            <TrendingUp className="h-5 w-5 text-green-400" />
                            <div>
                              <p className="text-xs font-medium text-teal-200/70">Winning Trades</p>
                              <p className="text-xl font-bold text-green-400">
                                {backtestResult.metrics.winning_trades ?? 0}
                              </p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>

                      <Card className="bg-teal-900/30 border-teal-700/50">
                        <CardContent className="p-4">
                          <div className="flex items-center space-x-3">
                            <TrendingDown className="h-5 w-5 text-red-400" />
                            <div>
                              <p className="text-xs font-medium text-teal-200/70">Losing Trades</p>
                              <p className="text-xl font-bold text-red-400">
                                {backtestResult.metrics.losing_trades ?? 0}
                              </p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>

                      <Card className="bg-teal-900/30 border-teal-700/50">
                        <CardContent className="p-4">
                          <div className="flex items-center space-x-3">
                            <DollarSign className="h-5 w-5 text-teal-400" />
                            <div>
                              <p className="text-xs font-medium text-teal-200/70">Avg Trade Return</p>
                              <p className={`text-xl font-bold ${
                                (backtestResult.metrics.avg_trade_return ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'
                              }`}>
                                {backtestResult.metrics.avg_trade_return !== null && backtestResult.metrics.avg_trade_return !== undefined
                                  ? formatCurrency(backtestResult.metrics.avg_trade_return)
                                  : 'N/A'}
                              </p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    </div>
                  )}
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-teal-700/30">
                          <th className="text-left py-3 px-4 text-sm font-semibold text-teal-200/70">#</th>
                          <th className="text-left py-3 px-4 text-sm font-semibold text-teal-200/70">Entry Date</th>
                          <th className="text-left py-3 px-4 text-sm font-semibold text-teal-200/70">Exit Date</th>
                          <th className="text-right py-3 px-4 text-sm font-semibold text-teal-200/70">Entry Price</th>
                          <th className="text-right py-3 px-4 text-sm font-semibold text-teal-200/70">Exit Price</th>
                          <th className="text-right py-3 px-4 text-sm font-semibold text-teal-200/70">Size</th>
                          <th className="text-right py-3 px-4 text-sm font-semibold text-teal-200/70">P&L</th>
                          <th className="text-right py-3 px-4 text-sm font-semibold text-teal-200/70">Return %</th>
                          <th className="text-right py-3 px-4 text-sm font-semibold text-teal-200/70">Duration</th>
                        </tr>
                      </thead>
                      <tbody>
                        {backtestResult.trades.map((trade) => (
                          <tr key={trade.trade_number} className="border-b border-teal-800/30 hover:bg-teal-900/30 transition-colors">
                            <td className="py-3 px-4 text-sm text-white/90">{trade.trade_number}</td>
                            <td className="py-3 px-4 text-sm text-white/90">{formatDate(trade.entry_date)}</td>
                            <td className="py-3 px-4 text-sm text-white/90">{formatDate(trade.exit_date)}</td>
                            <td className="py-3 px-4 text-sm text-right text-white">{formatCurrency(trade.entry_price)}</td>
                            <td className="py-3 px-4 text-sm text-right text-white">{formatCurrency(trade.exit_price)}</td>
                            <td className="py-3 px-4 text-sm text-right text-white/90">{formatNumber(trade.size)}</td>
                            <td className={`py-3 px-4 text-sm text-right font-medium ${
                              trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'
                            }`}>
                              {trade.pnl >= 0 ? '+' : ''}{formatCurrency(trade.pnl)}
                            </td>
                            <td className={`py-3 px-4 text-sm text-right font-medium ${
                              trade.return_pct >= 0 ? 'text-green-400' : 'text-red-400'
                            }`}>
                              {trade.return_pct >= 0 ? '+' : ''}{formatPercentage(trade.return_pct)}
                            </td>
                            <td className="py-3 px-4 text-sm text-right text-white/90">{trade.duration_days} {trade.duration_days === 1 ? 'day' : 'days'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              )}
            </Card>
          )
        })()}
        
        {/* Candle Charts - Show for each asset with candle data */}
        {backtestResult.candle_data && backtestResult.candle_data.length > 0 && (
          <div className="space-y-4">
            {backtestResult.candle_data.map((candleData, index) => (
              <CandleChart
                key={`candle-${index}-${candleData.symbol}`}
                candleData={candleData}
              />
            ))}
          </div>
        )}

        {backtestResult.show_performance_stats && (
          <PortfolioChart 
            dataPoints={backtestResult.data_points}
            startDate={backtestResult.start_date}
            endDate={backtestResult.end_date}
            trades={backtestResult.trades}
          />
        )}

        {backtestResult.include_technical_analysis && (
          <TechnicalCharts 
            dataPoints={backtestResult.data_points}
            technicalIndicatorsRequested={backtestResult.technical_indicators_requested}
            targetAssets={backtestResult.target_assets}
          />
        )}

        {backtestResult.show_performance_stats && (
          <AllocationCharts allocations={backtestResult.allocations} />
        )}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {messages.map((message, index) => (
        <div key={message.id} className="space-y-3">
          {message.type === 'user' && (
            <div className="flex justify-end w-full">
              <div className="w-full max-w-[85%] flex flex-col items-end">
                <div className="flex gap-2 justify-end items-center">
                  <span className="text-xs font-medium text-white/70">
                    You
                  </span>
                  <div className="w-8 h-8 flex items-center justify-center flex-shrink-0">
                    <User className="h-5 w-5 text-white/70" />
                  </div>
                </div>
                <div
                  className="mt-1 w-fit max-w-full rounded-2xl p-3 sm:p-4 text-white"
                  style={{
                    background:
                      'linear-gradient(180deg, rgba(255, 255, 255, 0.36) 0%, rgba(161, 207, 211, 0.06) 100%)',
                  }}
                >
                  <div className="text-sm leading-relaxed">
                    <span className="whitespace-pre-wrap">{message.content}</span>
                    <div className="flex items-center gap-2 mt-1.5">
                      <span className="text-xs text-white/70">
                        {formatTimestamp(message.timestamp)}
                      </span>
                      {(() => {
                        const nextAssistant = messages.slice(index + 1).find(m => m.type === 'assistant')
                        const shouldShowInfo =
                          nextAssistant &&
                          nextAssistant.success === true &&
                          hasStructuredResults(nextAssistant)
                        if (!shouldShowInfo) return null
                        const revealed = revealedAssistantIds.has(nextAssistant!.id)
                        return (
                          <button
                            type="button"
                            onClick={() => {
                              setRevealedAssistantIds(prev => {
                                const next = new Set(prev)
                                if (revealed) {
                                  next.delete(nextAssistant!.id)
                                } else {
                                  next.add(nextAssistant!.id)
                                }
                                return next
                              })
                            }}
                            className={`inline-flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 transition-colors h-5 w-5 sm:h-6 sm:w-6 flex-shrink-0 ${
                              revealed ? 'opacity-60' : ''
                            }`}
                            title={revealed ? "Hide Clark's response" : "Show Clark's response"}
                            aria-label={revealed ? "Hide Clark's response" : "Show Clark's response"}
                          >
                            <Info className="h-3 w-3 sm:h-3.5 sm:w-3.5 text-white" />
                          </button>
                        )
                      })()}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Secondary text reveal under the user message when success=true and info clicked */}
          {message.type === 'user' && (() => {
            const nextAssistant = messages.slice(index + 1).find(m => m.type === 'assistant')
            if (!nextAssistant || nextAssistant.success !== true || !hasStructuredResults(nextAssistant)) return null
            if (!revealedAssistantIds.has(nextAssistant.id)) return null
            return (
              <div className="flex justify-end">
                <div className="max-w-[85%] rounded-xl px-4 py-3 bg-zinc-800/60 border border-teal-700/30/50 text-white">
                  <div className="text-xs uppercase tracking-wide text-teal-200/70 mb-1">Clark’s response</div>
                  <div className="text-sm whitespace-pre-wrap leading-relaxed">{nextAssistant.content}</div>
                </div>
              </div>
            )
          })()}

          {message.type === 'assistant' && (() => {
            // Check if this is a price history query first (exclude from transaction detection)
            const isPriceHistoryQuery = message.priceHistoryResult && 
              message.priceHistoryResult.data_points && 
              message.priceHistoryResult.data_points.length > 0
            const parsedIntentOperation = message.parsedIntent?.operation
            const isPriceHistoryOperation = parsedIntentOperation === 'price_history'
            
            // Detect krypton_pay-style payment / transfer responses so we can
            // suppress Clark's natural language bubble and rely purely on the
            // structured transaction status UI.
            // BUT exclude price history queries - they should show charts, not transaction cards
            const agentIds = message.parsedIntent?.agent_ids || []
            const hasKryptonPayInIntent = agentIds.includes('krypton_pay')

            const agentFlowNodes = message.agentFlow && 'nodes' in message.agentFlow 
              ? message.agentFlow.nodes 
              : Array.isArray(message.agentFlow) 
                ? message.agentFlow 
                : []

            const hasKryptonPayInFlow = agentFlowNodes.some((node: any) => 
              node.tool_name === 'consult_krypton_pay' || 
              node.id === 'krypton_pay' ||
              (node.output?.data && (
                node.output.data.transaction_id || 
                node.output.data.status === 'SUBMITTED' ||
                node.output.data.operation
              ))
            )

            const messageContent = message.content || ''
            const hasTransactionKeywords = /(sent|transfer|transaction|successfully|swapped|swap completed)/i.test(messageContent) && 
              /(USD|EUR|AED|to @|transaction id)/i.test(messageContent)

            // Only treat as krypton_pay transaction if we have actual payment/swap (not balance-only read).
            // Exclude balance queries: operation "balances" | "balances_daily" | "balances_intraday" = read-only, no transaction UI.
            const hasTransactionData = agentFlowNodes.some((node: any) => {
              const data = node.output?.data
              if (!data) return false
              const op = data.operation
              if (op === 'balances' || op === 'balances_daily' || op === 'balances_intraday') return false
              return !!(data.transaction_id || data.status === 'SUBMITTED' || data.estimated_output || data.route)
            })
            
            const isBalanceOnlyQuery = message.balanceResult && ['balances', 'balances_daily', 'balances_intraday'].includes(message.balanceResult.operation)
            const isKryptonPay = !isPriceHistoryQuery && !isPriceHistoryOperation && !isBalanceOnlyQuery &&
              (hasKryptonPayInIntent || hasKryptonPayInFlow) && 
              (hasTransactionData || hasTransactionKeywords)

            // Try to derive minimal transaction details from the krypton_pay agent node
            // Only extract if this is actually a transaction (not price history)
            let inlineTxData: InlineTransactionData | undefined
            if (isKryptonPay) {
              // First try to extract from agent flow nodes
              if (agentFlowNodes.length > 0) {
                const kryptonNode = agentFlowNodes.find((node: any) =>
                  node.tool_name === 'consult_krypton_pay' ||
                  node.id === 'krypton_pay' ||
                  node.name?.toLowerCase().includes('krypton')
                )
                const data = kryptonNode?.output?.data
                
                // Only create inlineTxData if we have transaction indicators
                if (data && (data.transaction_id || data.status || data.operation || data.estimated_output)) {
                  // For swaps, extract from the swap response structure
                  if (data.estimated_output || data.route) {
                    // This is a swap response
                    const parsedIntent = message.parsedIntent
                    inlineTxData = {
                      transaction_id: data.transaction_id || data.data?.id,
                      status: data.status || 'SUBMITTED',
                      operation: 'swap',
                      token: parsedIntent?.to_token || data.to_token || data.route?.split('->')[1]?.trim() || 'USD',
                      amount: data.estimated_output || parsedIntent?.amount,
                      from_address: data.user_address,
                      to_address: data.user_address, // Swaps are to same wallet
                      tx_hash: data.tx_hash,
                      created_at: data.created_at,
                    }
                  } else if (data.transaction_id || data.status) {
                    // This is a transfer/swap+transfer response
                    inlineTxData = {
                      transaction_id: data.transaction_id,
                      status: data.status,
                      operation: data.operation,
                      token: data.token,
                      amount: data.amount || data.received_amount,
                      from_address: data.from_address,
                      to_address: data.to_address,
                      tx_hash: data.tx_hash,
                      created_at: data.created_at,
                    }
                  }
                }
              }
              
              // Fallback: if no data from agent flow nodes, try to extract from parsedIntent for swaps
              if (!inlineTxData && message.parsedIntent?.operation === 'swap') {
                const parsedIntent = message.parsedIntent
                if (parsedIntent.to_token && parsedIntent.amount) {
                  inlineTxData = {
                    transaction_id: undefined,
                    status: 'SUBMITTED',
                    operation: 'swap',
                    token: parsedIntent.to_token,
                    amount: parsedIntent.amount,
                    from_address: undefined,
                    to_address: undefined,
                    tx_hash: undefined,
                    created_at: Math.floor(Date.now() / 1000),
                  }
                }
              }
            }

            return (
            <>
              {/* For krypton_pay flows, hide Clark's natural language bubble entirely.
                  We'll show only the structured TransactionStatus card below. */}
              {!isKryptonPay && message.content && (message.success === false || !hasStructuredResults(message)) && (
                <>
                  <div className="flex gap-2 justify-start items-center">
                    <div className="w-8 h-8 flex items-center justify-center flex-shrink-0">
                      <img src="/clark process.svg" alt="Clark" className="h-8 w-8" />
                    </div>
                    <span className="text-xs font-medium" style={{ color: '#90E7EE' }}>
                      Clark
                    </span>
                  </div>
                  <div className="mt-1 ml-10 max-w-[85%] text-sm leading-relaxed text-white">
                    {/* Render optional source label, but hide noisy internal tags */}
                    {(() => {
                      const sourceLabel = formatSourceLabel(message.source)
                      if (!sourceLabel) return null
                      return (
                        <div className="text-[10px] uppercase tracking-[0.2em] text-teal-300/80 mb-2">
                          {sourceLabel}
                        </div>
                      )
                    })()}
                    {/* Render assistant message content as markdown-formatted HTML */}
                    <div
                      className="prose prose-invert max-w-none"
                      dangerouslySetInnerHTML={{ __html: markdownToHtml(message.content) }}
                    />
                    {message.capabilitiesSummary && (
                      <div className="mt-3 text-xs text-white/90 whitespace-pre-wrap leading-relaxed">
                        {message.capabilitiesSummary}
                      </div>
                    )}
                  </div>
                </>
              )}

              {/* When success === true, show the last line of Clark's response alongside plots,
                  except for krypton_pay flows where we rely solely on TransactionStatus. */}
              {!isKryptonPay && message.success === true && hasStructuredResults(message) && message.content && (() => {
                const lines = message.content.split('\n').map(l => l.trim()).filter(Boolean)
                const lastLine = lines.length > 0 ? lines[lines.length - 1] : ''
                if (!lastLine) return null
                return (
                  <>
                    <div className="flex gap-2 justify-start items-center">
                      <div className="w-8 h-8 flex items-center justify-center flex-shrink-0">
                        <img src="/clark process.svg" alt="Clark" className="h-8 w-8" />
                      </div>
                      <span className="text-xs font-medium" style={{ color: '#90E7EE' }}>
                        Clark
                      </span>
                    </div>
                    <div className="mt-1 ml-10 max-w-[85%] text-sm leading-relaxed text-white">
                      {lastLine}
                    </div>
                  </>
                )
              })()}

              {/* Render only backtest results */}
              {renderBacktest(message)}
              
              {/* Render price history chart */}
              {(() => {
                // Check if we have price history data
                const priceHistoryResult = message.priceHistoryResult
                const hasPriceHistory = priceHistoryResult && 
                  priceHistoryResult.data_points && 
                  Array.isArray(priceHistoryResult.data_points) &&
                  priceHistoryResult.data_points.length > 0
                
                if (!hasPriceHistory || !priceHistoryResult) return null
                
                // Debug logging
                console.log('Rendering price history chart:', {
                  token: priceHistoryResult.token,
                  dataPointsLength: priceHistoryResult.data_points.length,
                  lookbackDays: priceHistoryResult.lookback_days,
                })
                
                return (
                  <div className="flex gap-2 justify-start items-start mt-2">
                    <div className="w-8 h-8 flex items-center justify-center flex-shrink-0">
                      <img src="/clark process.svg" alt="Clark" className="h-8 w-8" />
                    </div>
                    <div className="max-w-[85%] w-full">
                      <PriceHistoryChart
                        token={priceHistoryResult.token}
                        dataPoints={priceHistoryResult.data_points}
                        lookbackDays={priceHistoryResult.lookback_days}
                      />
                    </div>
                  </div>
                )
              })()}

              {/* Render balance result (current, daily, or intraday) */}
              {(() => {
                const balanceResult = message.balanceResult
                if (!balanceResult) return null
                const { username_or_address, operation, balances, dailyBalances, intradayBalances } = balanceResult
                const hasCurrent = Array.isArray(balances) && balances.length > 0
                const hasDaily = Array.isArray(dailyBalances) && dailyBalances.length > 0
                const hasIntraday = Array.isArray(intradayBalances) && intradayBalances.length > 0
                const hasAnyData = hasCurrent || hasDaily || hasIntraday

                const title = operation === 'balances_daily'
                  ? `Daily balance history · ${username_or_address || 'User'}`
                  : operation === 'balances_intraday'
                    ? `Intraday balance history · ${username_or_address || 'User'}`
                    : `Balances · ${username_or_address || 'User'}`

                return (
                  <div className="flex gap-2 justify-start items-start mt-2">
                    <div className="max-w-[85%] w-full rounded-2xl p-4 bg-teal-900/40 border border-teal-700/50 backdrop-blur-sm">
                      <div className="text-[10px] uppercase tracking-[0.2em] text-teal-300/80 mb-3">{title}</div>
                      {!hasAnyData && (
                        <p className="text-sm text-teal-200/80">No balance data recorded yet for this period.</p>
                      )}
                      {hasCurrent && (
                        <div className="space-y-2">
                          {(balances as BalanceEntry[]).map((entry, idx) => {
                            const e = entry as unknown as Record<string, unknown>
                            const tokenLabel = e.token ?? e.symbol ?? e.tokenSymbol ?? e.token_name ?? e.name ?? '—'
                            const balanceVal = entry.balance != null ? (typeof entry.balance === 'string' ? entry.balance : String(entry.balance)) : '—'
                            return (
                              <div key={`${String(tokenLabel)}-${idx}`} className="flex justify-between items-center py-2 px-3 rounded-lg bg-teal-800/30 border border-teal-700/30">
                                <span className="text-white font-medium">{String(tokenLabel)}</span>
                                <span className="text-teal-100 tabular-nums">{balanceVal}</span>
                              </div>
                            )
                          })}
                        </div>
                      )}
                      {hasDaily && (
                        <BalanceHistoryChartLazy
                          title={title}
                          mode="daily"
                          dailyBalances={dailyBalances as DailyBalanceEntry[]}
                          username_or_address={username_or_address}
                        />
                      )}
                      {hasIntraday && (
                        <BalanceHistoryChartLazy
                          title={title}
                          mode="intraday"
                          intradayBalances={intradayBalances as IntradayBalanceEntry[]}
                          username_or_address={username_or_address}
                        />
                      )}
                    </div>
                  </div>
                )
              })()}
              
              {/* Show transaction status card when we detect a krypton_pay transaction */}
              {isKryptonPay && username && (
                <div className="flex gap-2 justify-start items-start mt-2">
                  <div className="w-8 h-8 flex items-center justify-center flex-shrink-0">
                    <img src="/clark process.svg" alt="Clark" className="h-8 w-8" />
                  </div>
                  <div className="max-w-[85%]">
                    <TransactionStatus username={username} initialData={inlineTxData} />
                  </div>
                </div>
              )}
            </>
            )
          })()}
        </div>
      ))}
      {isLoading && (
        <div className="flex gap-3 justify-start">
          <div className="bg-zinc-800/60 border border-teal-700/30/50 rounded-2xl p-4 backdrop-blur-sm">
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-teal-400" />
              <span className="text-sm text-white">Processing your request...</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const markdownToHtml = (markdown: string): string => {
  if (!markdown) return ''

  const escapeHtml = (text: string) =>
    text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')

  const applyInline = (text: string) => {
    const escaped = escapeHtml(text)
    return escaped
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/__(.+?)__/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/_(.+?)_/g, '<em>$1</em>')
  }

  const lines = markdown.split(/\n+/)
  const htmlParts: string[] = []
  let inList = false

  lines.forEach((line) => {
    const trimmed = line.trim()
    if (!trimmed) {
      if (inList) {
        htmlParts.push('</ul>')
        inList = false
      }
      return
    }

    if (trimmed.startsWith('- ')) {
      if (!inList) {
        htmlParts.push('<ul class="list-disc pl-5 space-y-1">')
        inList = true
      }
      htmlParts.push(`<li>${applyInline(trimmed.slice(2).trim())}</li>`)
    } else {
      if (inList) {
        htmlParts.push('</ul>')
        inList = false
      }
      htmlParts.push(`<p>${applyInline(trimmed)}</p>`)
    }
  })

  if (inList) {
    htmlParts.push('</ul>')
  }

  return htmlParts.join('')
}
