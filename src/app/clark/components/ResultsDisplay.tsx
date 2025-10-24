"use client"

import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { DollarSign, TrendingUp, BarChart3, TrendingDown } from 'lucide-react'
import { ChatMessage, BacktestResult, ScreenerResult, EconomicResult, NewsData, CalendarData, EconomicData } from '../types'
import { formatCurrency, formatPercentage, formatDate, formatNumber } from '../utils'
import PortfolioChart from './charts/PortfolioChart'
import TechnicalCharts from './charts/TechnicalCharts'
import AllocationCharts from './charts/AllocationCharts'

interface ResultsDisplayProps {
  messages: ChatMessage[]
}

export default function ResultsDisplay({ messages }: ResultsDisplayProps) {
  const hasResults = messages.some(m => m.backtestResult || m.screenerResult || m.economicResult)
  const hasUserMessages = messages.some(m => m.type === 'user')

  // If no results and no user messages, don't render anything (logo and tiles are handled in main page)
  if (!hasResults && !hasUserMessages) {
    return null
  }

  return (
    <div className="space-y-4">
      {/* Economic Results */}
      {messages.some(m => m.economicResult) && (
        <div className="space-y-4 mb-6">
          {messages
            .filter(m => m.economicResult)
            .map((message) => {
              const economicResult = message.economicResult!
              const isNews = economicResult.indicator === 'news'
              const isCalendar = economicResult.indicator === 'calendar'
              
              return (
                <Card key={message.id} className="w-full bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm">
                  <CardHeader className="pb-4">
                    <CardTitle className="text-lg text-white">{economicResult.indicator_name}</CardTitle>
                    <CardDescription className="text-zinc-400">
                      {isNews ? `${economicResult.total_found} latest news articles` : 
                       isCalendar ? `${economicResult.total_found} upcoming economic events` :
                       `Economic indicators for ${economicResult.total_found} countries`}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-x-auto">
                      {isNews ? (
                        <div className="space-y-4">
                          {(economicResult.results as NewsData[]).map((news, index) => (
                            <div key={news.id || index} className="border-b border-zinc-800 pb-4 hover:bg-zinc-900/50 transition-colors p-4 rounded-lg">
                              <div className="flex items-start justify-between">
                                <div className="flex-1">
                                  <h3 className="text-lg font-semibold text-white mb-2">{news.title}</h3>
                                  {news.description && (
                                    <p className="text-sm text-zinc-400 mb-2">{news.description}</p>
                                  )}
                                  <div className="flex items-center gap-4 text-xs text-zinc-500">
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
                                    className="ml-4 text-blue-400 hover:text-blue-300 text-sm"
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
                            <tr className="border-b border-zinc-700">
                              <th className="text-left py-3 px-4 text-sm font-semibold text-zinc-400">Date</th>
                              <th className="text-left py-3 px-4 text-sm font-semibold text-zinc-400">Country</th>
                              <th className="text-left py-3 px-4 text-sm font-semibold text-zinc-400">Event</th>
                              <th className="text-right py-3 px-4 text-sm font-semibold text-zinc-400">Actual</th>
                              <th className="text-right py-3 px-4 text-sm font-semibold text-zinc-400">Forecast</th>
                              <th className="text-right py-3 px-4 text-sm font-semibold text-zinc-400">Previous</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(economicResult.results as CalendarData[]).map((event, index) => (
                              <tr key={event.event_id || index} className="border-b border-zinc-800 hover:bg-zinc-900/50 transition-colors">
                                <td className="py-3 px-4 text-sm text-zinc-300">
                                  {new Date(event.date).toLocaleDateString()}
                                </td>
                                <td className="py-3 px-4 text-sm font-medium text-white">{event.country}</td>
                                <td className="py-3 px-4 text-sm text-zinc-300">
                                  <div>
                                    <div className="font-medium text-white">{event.event}</div>
                                    {event.category && <div className="text-xs text-zinc-500">{event.category}</div>}
                                  </div>
                                </td>
                                <td className="py-3 px-4 text-sm text-right text-white font-medium">
                                  {event.actual !== null && event.actual !== undefined ? event.actual : '-'}
                                </td>
                                <td className="py-3 px-4 text-sm text-right text-zinc-300">
                                  {event.forecast !== null && event.forecast !== undefined ? event.forecast : '-'}
                                </td>
                                <td className="py-3 px-4 text-sm text-right text-zinc-300">
                                  {event.previous !== null && event.previous !== undefined ? event.previous : '-'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      ) : (
                        <table className="w-full">
                          <thead>
                            <tr className="border-b border-zinc-700">
                              <th className="text-left py-3 px-4 text-sm font-semibold text-zinc-400">Rank</th>
                              <th className="text-left py-3 px-4 text-sm font-semibold text-zinc-400">Country</th>
                              <th className="text-right py-3 px-4 text-sm font-semibold text-zinc-400">Current Value</th>
                              <th className="text-right py-3 px-4 text-sm font-semibold text-zinc-400">Previous Value</th>
                              <th className="text-right py-3 px-4 text-sm font-semibold text-zinc-400">Change</th>
                              <th className="text-left py-3 px-4 text-sm font-semibold text-zinc-400">Unit</th>
                              <th className="text-left py-3 px-4 text-sm font-semibold text-zinc-400">Last Updated</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(economicResult.results as EconomicData[]).map((data, index) => {
                            const change = data.value !== null && data.previous_value !== null && data.previous_value !== undefined
                              ? data.value - data.previous_value 
                              : null
                            const changePercent = data.value !== null && data.previous_value !== null && data.previous_value !== undefined && data.previous_value !== 0
                              ? ((data.value - data.previous_value) / data.previous_value) * 100
                              : null
                            
                            return (
                              <tr key={data.country} className="border-b border-zinc-800 hover:bg-zinc-900/50 transition-colors">
                                <td className="py-3 px-4 text-sm text-zinc-300">{index + 1}</td>
                                <td className="py-3 px-4 text-sm font-medium text-white">{data.country}</td>
                                <td className="py-3 px-4 text-sm text-right text-white font-medium">
                                  {data.value !== null ? data.value.toLocaleString() : 'N/A'}
                                </td>
                                <td className="py-3 px-4 text-sm text-right text-zinc-300">
                                  {data.previous_value !== null && data.previous_value !== undefined ? data.previous_value.toLocaleString() : 'N/A'}
                                </td>
                                <td className={`py-3 px-4 text-sm text-right font-medium ${
                                  change !== null && change > 0 ? 'text-green-500' : 
                                  change !== null && change < 0 ? 'text-red-500' : 'text-zinc-300'
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
                                <td className="py-3 px-4 text-sm text-zinc-300">{data.unit || 'N/A'}</td>
                                <td className="py-3 px-4 text-sm text-zinc-300">
                                  {data.date ? new Date(data.date).toLocaleDateString() : 'N/A'}
                                </td>
                                </tr>
                              )
                            })}
                          </tbody>
                        </table>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )
            })}
        </div>
      )}

      {/* Screener Results */}
      {messages.some(m => m.screenerResult) && (
        <div className="space-y-4 mb-6">
          {messages
            .filter(m => m.screenerResult)
            .map((message) => {
              const screenerResult = message.screenerResult!
              return (
                <Card key={message.id} className="w-full bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm">
                  <CardHeader className="pb-4">
                    <CardTitle className="text-lg text-white">
                      {screenerResult.screener_type === 'price' && 'Price Screener Results'}
                      {screenerResult.screener_type === 'daily_change' && 'Daily Change Screener Results'}
                      {screenerResult.screener_type === 'market_cap' && 'Market Cap Screener Results'}
                      {screenerResult.screener_type === 'ema' && 'EMA Screener Results'}
                    </CardTitle>
                    <CardDescription className="text-zinc-400">
                      {screenerResult.range_description} • {screenerResult.total_found} cryptos found
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead>
                          <tr className="border-b border-zinc-700">
                            <th className="text-left py-3 px-4 text-sm font-semibold text-zinc-400">Rank</th>
                            <th className="text-left py-3 px-4 text-sm font-semibold text-zinc-400">Name</th>
                            <th className="text-left py-3 px-4 text-sm font-semibold text-zinc-400">Symbol</th>
                            <th className="text-right py-3 px-4 text-sm font-semibold text-zinc-400">Price</th>
                            <th className="text-right py-3 px-4 text-sm font-semibold text-zinc-400">24h Change</th>
                            {screenerResult.screener_type === '52w_high_low' && (
                              <th className="text-right py-3 px-4 text-sm font-semibold text-zinc-400">From High/Low</th>
                            )}
                            {screenerResult.screener_type === 'rsi' && (
                              <th className="text-right py-3 px-4 text-sm font-semibold text-zinc-400">RSI</th>
                            )}
                            {screenerResult.screener_type === 'technical_pattern' && (
                              <>
                                <th className="text-right py-3 px-4 text-sm font-semibold text-zinc-400">50 SMA</th>
                                <th className="text-right py-3 px-4 text-sm font-semibold text-zinc-400">200 SMA</th>
                              </>
                            )}
                            {screenerResult.screener_type === 'ema' && (
                              <>
                                <th className="text-right py-3 px-4 text-sm font-semibold text-zinc-400">5 EMA</th>
                                <th className="text-right py-3 px-4 text-sm font-semibold text-zinc-400">10 EMA</th>
                              </>
                            )}
                            <th className="text-right py-3 px-4 text-sm font-semibold text-zinc-400">Market Cap</th>
                            <th className="text-right py-3 px-4 text-sm font-semibold text-zinc-400">Volume (24h)</th>
                          </tr>
                        </thead>
                        <tbody>
                          {screenerResult.results.map((crypto, index) => (
                            <tr key={crypto.symbol} className="border-b border-zinc-800 hover:bg-zinc-900/50 transition-colors">
                              <td className="py-3 px-4 text-sm text-zinc-300">{crypto.rank || index + 1}</td>
                              <td className="py-3 px-4 text-sm font-medium text-white">{crypto.name}</td>
                              <td className="py-3 px-4 text-sm text-zinc-300">{crypto.symbol}</td>
                              <td className="py-3 px-4 text-sm text-right text-white">{formatCurrency(crypto.price)}</td>
                              <td className={`py-3 px-4 text-sm text-right font-medium ${
                                crypto.daily_change_percent >= 0 ? 'text-green-500' : 'text-red-500'
                              }`}>
                                {crypto.daily_change_percent >= 0 ? '+' : ''}{crypto.daily_change_percent.toFixed(2)}%
                              </td>
                              {screenerResult.screener_type === '52w_high_low' && (
                                <td className={`py-3 px-4 text-sm text-right font-medium ${
                                  crypto.percent_from_high !== undefined && crypto.percent_from_high >= -10 ? 'text-green-500' : 
                                  crypto.percent_from_low !== undefined && crypto.percent_from_low <= 10 ? 'text-red-500' : 'text-zinc-300'
                                }`}>
                                  {crypto.percent_from_high !== undefined ? `${crypto.percent_from_high.toFixed(1)}% from high` : 
                                   crypto.percent_from_low !== undefined ? `${crypto.percent_from_low.toFixed(1)}% from low` : 'N/A'}
                                </td>
                              )}
                              {screenerResult.screener_type === 'rsi' && (
                                <td className={`py-3 px-4 text-sm text-right font-medium ${
                                  crypto.rsi !== undefined && crypto.rsi <= 30 ? 'text-red-500' : 
                                  crypto.rsi !== undefined && crypto.rsi >= 70 ? 'text-green-500' : 'text-zinc-300'
                                }`}>
                                  {crypto.rsi !== undefined ? crypto.rsi.toFixed(1) : 'N/A'}
                                </td>
                              )}
                              {screenerResult.screener_type === 'technical_pattern' && (
                                <>
                                  <td className="py-3 px-4 text-sm text-right text-zinc-300">
                                    {crypto.sma_50 !== undefined ? formatCurrency(crypto.sma_50) : 'N/A'}
                                  </td>
                                  <td className="py-3 px-4 text-sm text-right text-zinc-300">
                                    {crypto.sma_200 !== undefined ? formatCurrency(crypto.sma_200) : 'N/A'}
                                  </td>
                                </>
                              )}
                              {screenerResult.screener_type === 'ema' && (
                                <>
                                  <td className="py-3 px-4 text-sm text-right text-zinc-300">
                                    {crypto.ema_5 !== undefined ? formatCurrency(crypto.ema_5) : 'N/A'}
                                  </td>
                                  <td className="py-3 px-4 text-sm text-right text-zinc-300">
                                    {crypto.ema_10 !== undefined ? formatCurrency(crypto.ema_10) : 'N/A'}
                                  </td>
                                </>
                              )}
                              <td className="py-3 px-4 text-sm text-right text-zinc-300">{formatNumber(crypto.market_cap)}</td>
                              <td className="py-3 px-4 text-sm text-right text-zinc-300">{formatNumber(crypto.volume_24h)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              )
            })}
        </div>
      )}

      {/* Backtest Results */}
      {messages.some(m => m.backtestResult) && (
        <div className="space-y-4">
          {messages
            .filter(m => m.backtestResult)
            .map((message) => {
              const backtestResult = message.backtestResult!
              return (
                <div key={message.id} className="space-y-4">
                  {/* Summary Cards - Only show if performance stats are enabled */}
                  {backtestResult.show_performance_stats && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 w-full">
                      <Card className="bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm">
                        <CardContent className="p-4">
                          <div className="flex items-center space-x-3">
                            <DollarSign className="h-5 w-5 text-green-400" />
                            <div>
                              <p className="text-xs font-medium text-zinc-400">Final Value</p>
                              <p className="text-xl font-bold text-white">{formatCurrency(backtestResult.final_capital)}</p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>

                      <Card className="bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm">
                        <CardContent className="p-4">
                          <div className="flex items-center space-x-3">
                            <TrendingUp className="h-5 w-5 text-blue-400" />
                            <div>
                              <p className="text-xs font-medium text-zinc-400">Total Return</p>
                              <p className={`text-xl font-bold ${
                                backtestResult.metrics.total_return >= 0 ? 'text-green-400' : 'text-red-400'
                              }`}>
                                {formatPercentage(backtestResult.metrics.total_return)}
                              </p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>

                      <Card className="bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm">
                        <CardContent className="p-4">
                          <div className="flex items-center space-x-3">
                            <BarChart3 className="h-5 w-5 text-purple-400" />
                            <div>
                              <p className="text-xs font-medium text-zinc-400">Sharpe Ratio</p>
                              <p className="text-xl font-bold text-white">{backtestResult.metrics.sharpe_ratio.toFixed(2)}</p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>

                      <Card className="bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm">
                        <CardContent className="p-4">
                          <div className="flex items-center space-x-3">
                            <TrendingDown className="h-5 w-5 text-red-400" />
                            <div>
                              <p className="text-xs font-medium text-zinc-400">Max Drawdown</p>
                              <p className="text-xl font-bold text-red-400">
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
                    <PortfolioChart 
                      dataPoints={backtestResult.data_points}
                      startDate={backtestResult.start_date}
                      endDate={backtestResult.end_date}
                    />
                  )}

                  {/* Technical Analysis Charts */}
                  {backtestResult.include_technical_analysis && (
                    <TechnicalCharts 
                      dataPoints={backtestResult.data_points}
                      technicalIndicatorsRequested={backtestResult.technical_indicators_requested}
                      targetAssets={backtestResult.target_assets}
                    />
                  )}

                  {/* Allocation Chart - Only show if performance stats are enabled */}
                  {backtestResult.show_performance_stats && (
                    <AllocationCharts allocations={backtestResult.allocations} />
                  )}
                </div>
              )
            })}
        </div>
      )}
    </div>
  )
}
