"use client"

import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { AgentFlowStep, AgentFlowGraph, AgentFlowEdge, ScreenerResult, BacktestResult, EconomicResult, RegulationResult } from '../types'
import { stripReasoningFromMessage } from '../utils/createAssistantMessage'
import { ArrowRight, ArrowDown, CheckCircle2, Loader2, XCircle, GitBranch, GitMerge, ChevronDown, ChevronUp, Code, MessageSquare, Clock, Zap, Database, Sparkles, TrendingUp, TrendingDown, DollarSign, BarChart3, FileText, Globe } from 'lucide-react'

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

interface AgentFlowProps {
  flow: AgentFlowGraph | AgentFlowStep[]
}

// Type guard to check if flow is a graph structure
function isFlowGraph(flow: AgentFlowGraph | AgentFlowStep[]): flow is AgentFlowGraph {
  return flow && typeof flow === 'object' && 'nodes' in flow && 'edges' in flow
}


export default function AgentFlow({ flow }: AgentFlowProps) {
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set())
  const [expandedData, setExpandedData] = useState<Set<string>>(new Set())
  if (!flow) {
    return null
  }

  // Handle both old array format and new graph format
  let steps: AgentFlowStep[]
  let flowType: string = 'single'
  let edges: AgentFlowEdge[] = []

  if (isFlowGraph(flow)) {
    // New graph format - use steps array for display
    steps = flow.steps || flow.nodes.filter(n => n.type !== 'start' && n.type !== 'end')
    flowType = flow.flow_type || 'single'
    edges = flow.edges || []
  } else {
    // Old array format
    steps = flow
  }

  if (!steps || steps.length === 0) {
    return null
  }

  const toggleAgentExpansion = (agentId: string) => {
    setExpandedAgents(prev => {
      const newSet = new Set(prev)
      if (newSet.has(agentId)) {
        newSet.delete(agentId)
      } else {
        newSet.add(agentId)
      }
      return newSet
    })
  }

  const toggleDataExpansion = (agentId: string) => {
    setExpandedData(prev => {
      const newSet = new Set(prev)
      if (newSet.has(agentId)) {
        newSet.delete(agentId)
      } else {
        newSet.add(agentId)
      }
      return newSet
    })
  }

  const formatTimestamp = (timestamp?: string) => {
    if (!timestamp) return null
    try {
      const date = new Date(timestamp)
      return date.toLocaleTimeString('en-US', { 
        hour12: false, 
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit',
        fractionalSecondDigits: 3
      })
    } catch {
      return timestamp
    }
  }

  const formatLatency = (latencyMs?: number) => {
    if (latencyMs === undefined || latencyMs === null) return null
    if (latencyMs < 1000) {
      return `${latencyMs.toFixed(0)}ms`
    }
    return `${(latencyMs / 1000).toFixed(2)}s`
  }

  const formatCurrency = (value: number) => {
    if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`
    if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`
    if (value >= 1e3) return `$${(value / 1e3).toFixed(2)}K`
    return `$${value.toFixed(2)}`
  }

  const formatPercentage = (value: number) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
  }

  // Get data preview text
  const getDataPreview = (step: AgentFlowStep, data: any): string => {
    if (!data || typeof data !== 'object') return 'Click to view data'
    
    const agentId = step.id

    if (agentId === 'screener' && (data.screener || data.results)) {
      const screenerData = data.screener || data
      const count = screenerData.total_found || screenerData.results?.length || 0
      return `${count} result${count !== 1 ? 's' : ''} found`
    }

    if (agentId === 'backtest' && (data.backtest_result || data.backtestResult || data.metrics)) {
      const backtestData = data.backtest_result || data.backtestResult || data
      if (backtestData.metrics?.total_return !== undefined) {
        return `Total Return: ${formatPercentage(backtestData.metrics.total_return)}`
      }
      return 'Backtest results available'
    }

    if (agentId === 'economic' && (data.economic || data.markdown || data.raw_fmp)) {
      const economicData = data.economic || data
      if (economicData.markdown) return 'Markdown content available'
      const count = economicData.results?.length || 0
      return `${count} data point${count !== 1 ? 's' : ''}`
    }

    if (agentId === 'regulations' && (data.regulation_result || data.regulationResult || data.matches)) {
      const regData = data.regulation_result || data.regulationResult || data
      const count = regData.matches?.length || 0
      return `${count} regulation${count !== 1 ? 's' : ''} found`
    }

    if (agentId === 'data_fetcher' && data.assets) {
      const count = Object.keys(data.assets).length
      return `${count} asset${count !== 1 ? 's' : ''} fetched`
    }

    if (agentId === 'economic' && (data.raw_fmp || data.fmp_data || Array.isArray(data))) {
      const fmpData = data.raw_fmp || data.fmp_data || data
      const dataArray = Array.isArray(fmpData) ? fmpData : (fmpData.data || [])
      return `${dataArray.length} data point${dataArray.length !== 1 ? 's' : ''}`
    }

    if (agentId === 'search' && (data.search_context || data.search_results || data.results)) {
      const searchData = data.search_context || data.search_results || data
      const count = searchData.results?.length || 0
      if (count > 0) return `${count} search result${count !== 1 ? 's' : ''}`
      if (searchData.search_context || searchData.context) return 'Search context available'
      return 'Search data available'
    }

    if (step.output?.data_keys && step.output.data_keys.length > 0) {
      return `Keys: ${step.output.data_keys.slice(0, 3).join(', ')}${step.output.data_keys.length > 3 ? '...' : ''}`
    }

    return 'Click to view data'
  }

  // Render agent-specific data
  const renderAgentData = (step: AgentFlowStep, data: any) => {
    if (!data || typeof data !== 'object') {
      return (
        <pre className="text-xs text-[var(--kt-text-dim)] bg-[var(--kt-inset)] p-3 rounded border border-[var(--kt-border)] overflow-x-auto">
          {JSON.stringify(data, null, 2)}
        </pre>
      )
    }

    const agentId = step.id

    // Screener Agent Data
    if (agentId === 'screener' && (data.screener || data.results)) {
      const screenerData = data.screener || data
      const results = screenerData.results || []
      
      return (
        <div className="w-full max-w-full overflow-hidden space-y-3">
          {screenerData.total_found !== undefined && (
            <div className="text-xs text-[var(--kt-text-dim)]">
              Found {screenerData.total_found} result{screenerData.total_found !== 1 ? 's' : ''}
            </div>
          )}
          {results.length > 0 && (
            <div className="w-full max-w-full overflow-hidden">
              <div className="space-y-2 max-h-96 overflow-y-auto overflow-x-auto">
                {results.slice(0, 10).map((item: any, idx: number) => (
                  <div key={idx} className="bg-[var(--kt-inset)] rounded-lg p-3 border border-[var(--kt-border)] min-w-0">
                    <div className="flex items-start justify-between mb-2 gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="font-medium text-sm text-[var(--kt-text-strong)] break-words">{item.name || item.symbol}</div>
                        <div className="text-xs text-[var(--kt-text-dim)] break-words">{item.symbol}</div>
                      </div>
                      {item.price !== undefined && (
                        <div className="text-right flex-shrink-0">
                          <div className="font-semibold text-sm text-[var(--kt-text-strong)]">{formatCurrency(item.price)}</div>
                          {item.daily_change_percent !== undefined && (
                            <div className={`text-xs flex items-center gap-1 ${
                              item.daily_change_percent >= 0 ? 'text-[var(--kt-up)]' : 'text-[var(--kt-down)]'
                            }`}>
                              {item.daily_change_percent >= 0 ? (
                                <TrendingUp className="h-3 w-3" />
                              ) : (
                                <TrendingDown className="h-3 w-3" />
                              )}
                              {formatPercentage(item.daily_change_percent)}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      {item.market_cap !== undefined && (
                        <div className="break-words">
                          <span className="text-[var(--kt-text-muted)]">Market Cap: </span>
                          <span className="text-[var(--kt-text-dim)]">{formatCurrency(item.market_cap)}</span>
                        </div>
                      )}
                      {item.volume_24h !== undefined && (
                        <div className="break-words">
                          <span className="text-[var(--kt-text-muted)]">24h Volume: </span>
                          <span className="text-[var(--kt-text-dim)]">{formatCurrency(item.volume_24h)}</span>
                        </div>
                      )}
                      {item.rank !== undefined && (
                        <div>
                          <span className="text-[var(--kt-text-muted)]">Rank: </span>
                          <span className="text-[var(--kt-text-dim)]">#{item.rank}</span>
                        </div>
                      )}
                      {item.rsi !== undefined && (
                        <div>
                          <span className="text-[var(--kt-text-muted)]">RSI: </span>
                          <span className="text-[var(--kt-text-dim)]">{item.rsi.toFixed(2)}</span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {results.length > 10 && (
                  <div className="text-xs text-[var(--kt-text-muted)] text-center py-2">
                    ... and {results.length - 10} more results
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )
    }

    // Backtest Agent Data
    if (agentId === 'backtest' && (data.backtest_result || data.backtestResult || data.metrics)) {
      const backtestData = data.backtest_result || data.backtestResult || data
      const metrics = backtestData.metrics || {}
      const allocations = backtestData.allocations || []
      
      return (
        <div className="w-full max-w-full overflow-hidden space-y-4">
          {backtestData.strategy && (
            <div className="text-sm font-semibold text-[var(--kt-text-strong)] break-words">
              Strategy: <span className="text-[var(--kt-text-dim)] font-normal">{backtestData.strategy}</span>
            </div>
          )}
          {backtestData.start_date && backtestData.end_date && (
            <div className="text-xs text-[var(--kt-text-dim)]">
              Period: {new Date(backtestData.start_date).toLocaleDateString()} - {new Date(backtestData.end_date).toLocaleDateString()}
            </div>
          )}
          
          {Object.keys(metrics).length > 0 && (
            <div className="bg-[var(--kt-inset)] rounded-lg p-3 border border-[var(--kt-border)] min-w-0">
              <div className="text-xs font-semibold text-[var(--kt-agent)] mb-2 uppercase">Metrics</div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {metrics.total_return !== undefined && (
                  <div className="break-words">
                    <span className="text-[var(--kt-text-muted)]">Total Return: </span>
                    <span className={`font-medium ${
                      metrics.total_return >= 0 ? 'text-[var(--kt-up)]' : 'text-[var(--kt-down)]'
                    }`}>
                      {formatPercentage(metrics.total_return)}
                    </span>
                  </div>
                )}
                {metrics.sharpe_ratio !== undefined && (
                  <div>
                    <span className="text-[var(--kt-text-muted)]">Sharpe Ratio: </span>
                    <span className="text-[var(--kt-text-dim)] font-medium">{metrics.sharpe_ratio.toFixed(2)}</span>
                  </div>
                )}
                {metrics.max_drawdown !== undefined && (
                  <div className="break-words">
                    <span className="text-[var(--kt-text-muted)]">Max Drawdown: </span>
                    <span className="text-[var(--kt-down)] font-medium">{formatPercentage(metrics.max_drawdown)}</span>
                  </div>
                )}
                {metrics.volatility !== undefined && (
                  <div className="break-words">
                    <span className="text-[var(--kt-text-muted)]">Volatility: </span>
                    <span className="text-[var(--kt-text-dim)] font-medium">{formatPercentage(metrics.volatility)}</span>
                  </div>
                )}
                {backtestData.initial_capital !== undefined && (
                  <div className="break-words">
                    <span className="text-[var(--kt-text-muted)]">Initial Capital: </span>
                    <span className="text-[var(--kt-text-dim)] font-medium">{formatCurrency(backtestData.initial_capital)}</span>
                  </div>
                )}
                {backtestData.final_capital !== undefined && (
                  <div className="break-words">
                    <span className="text-[var(--kt-text-muted)]">Final Capital: </span>
                    <span className="text-[var(--kt-text-dim)] font-medium">{formatCurrency(backtestData.final_capital)}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {allocations.length > 0 && (
            <div className="bg-[var(--kt-inset)] rounded-lg p-3 border border-[var(--kt-border)] min-w-0">
              <div className="text-xs font-semibold text-[var(--kt-agent)] mb-2 uppercase">Allocations</div>
              <div className="w-full max-w-full overflow-hidden">
                <div className="space-y-2 max-h-96 overflow-y-auto overflow-x-auto">
                  {allocations.map((alloc: any, idx: number) => (
                    <div key={idx} className="flex items-center justify-between text-xs gap-2 min-w-0">
                      <span className="text-[var(--kt-text-dim)] break-words flex-1">{alloc.symbol}</span>
                      <div className="flex items-center gap-3 flex-shrink-0">
                        <span className="text-[var(--kt-text-muted)]">{alloc.allocation_percentage?.toFixed(1)}%</span>
                        {alloc.total_return !== undefined && (
                          <span className={`font-medium ${
                            alloc.total_return >= 0 ? 'text-[var(--kt-up)]' : 'text-[var(--kt-down)]'
                          }`}>
                            {formatPercentage(alloc.total_return)}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )
    }

    // Economic Agent Data
    if (agentId === 'economic' && (data.economic || data.markdown || data.raw_fmp)) {
      const economicData = data.economic || data
      
      if (economicData.markdown) {
        const safe = escapeHtml(stripReasoningFromMessage(economicData.markdown)).replace(/\n/g, '<br />')
        return (
          <div className="w-full max-w-full overflow-hidden">
            <div className="max-h-96 overflow-y-auto overflow-x-auto">
              <div 
                className="text-xs text-[var(--kt-text-dim)] break-words bg-[var(--kt-inset)] p-3 rounded border border-[var(--kt-border)] min-w-0"
                style={{ wordBreak: 'break-word', overflowWrap: 'break-word' }}
                dangerouslySetInnerHTML={{ __html: safe }}
              />
            </div>
          </div>
        )
      }

      const results = economicData.results || []
      if (results.length > 0) {
        return (
          <div className="w-full max-w-full overflow-hidden">
            <div className="space-y-2 max-h-96 overflow-y-auto overflow-x-auto">
              {results.slice(0, 10).map((item: any, idx: number) => (
                <div key={idx} className="bg-[var(--kt-inset)] rounded-lg p-3 border border-[var(--kt-border)] min-w-0">
                  <div className="flex items-start justify-between mb-1 gap-2">
                    <div className="font-medium text-sm text-[var(--kt-text-strong)] break-words min-w-0 flex-1">{item.indicator || item.title || item.event}</div>
                    {item.value !== undefined && item.value !== null && (
                      <div className="text-sm font-semibold text-[var(--kt-text-strong)] flex-shrink-0">{item.value}</div>
                    )}
                  </div>
                  <div className="text-xs text-[var(--kt-text-dim)] space-y-1">
                    {item.country && <div className="break-words">Country: {item.country}</div>}
                    {item.date && <div>Date: {new Date(item.date).toLocaleDateString()}</div>}
                    {item.category && <div className="break-words">Category: {item.category}</div>}
                    {item.previous_value !== undefined && item.previous_value !== null && (
                      <div>Previous: {item.previous_value}</div>
                    )}
                  </div>
                </div>
              ))}
              {results.length > 10 && (
                <div className="text-xs text-[var(--kt-text-muted)] text-center py-2">
                  ... and {results.length - 10} more results
                </div>
              )}
            </div>
          </div>
        )
      }
    }

    // Regulations Agent Data
    if (agentId === 'regulations' && (data.regulation_result || data.regulationResult || data.matches)) {
      const regData = data.regulation_result || data.regulationResult || data
      const matches = regData.matches || []
      
      return (
        <div className="w-full max-w-full overflow-hidden space-y-3">
          {regData.summary && (
            <div className="bg-[var(--kt-inset)] rounded-lg p-3 border border-[var(--kt-border)] min-w-0">
              <div className="text-xs font-semibold text-[var(--kt-warn)] mb-2 uppercase">Summary</div>
              <p className="text-xs text-[var(--kt-text-dim)] break-words">{regData.summary}</p>
            </div>
          )}
          {regData.topic && (
            <div className="text-xs text-[var(--kt-text-dim)] break-words">
              Topic: <span className="text-[var(--kt-text-dim)]">{regData.topic}</span>
            </div>
          )}
          {regData.jurisdiction && (
            <div className="text-xs text-[var(--kt-text-dim)] break-words">
              Jurisdiction: <span className="text-[var(--kt-text-dim)]">{regData.jurisdiction}</span>
            </div>
          )}
          {matches.length > 0 && (
            <div className="w-full max-w-full overflow-hidden">
              <div className="space-y-2 max-h-96 overflow-y-auto overflow-x-auto">
                {matches.map((match: any, idx: number) => (
                  <div key={idx} className="bg-[var(--kt-inset)] rounded-lg p-3 border border-[var(--kt-border)] min-w-0">
                    <div className="flex items-start justify-between mb-2 gap-2">
                      <div className="font-medium text-sm text-[var(--kt-text-strong)] flex-1 break-words min-w-0">{match.title}</div>
                      {match.score !== undefined && (
                        <div className="text-xs text-[var(--kt-text-muted)] flex-shrink-0">
                          {(match.score * 100).toFixed(0)}%
                        </div>
                      )}
                    </div>
                    {match.snippet && (
                      <p className="text-xs text-[var(--kt-text-dim)] mb-2 break-words">{match.snippet}</p>
                    )}
                    {match.jurisdiction && (
                      <div className="text-xs text-[var(--kt-text-muted)] break-words">Jurisdiction: {match.jurisdiction}</div>
                    )}
                    {match.url && (
                      <a 
                        href={match.url} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="text-xs text-[var(--kt-agent)] hover:text-[var(--kt-agent)] mt-1 inline-block break-all"
                      >
                        View source →
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )
    }

    // Data Fetcher Agent Data
    if (agentId === 'data_fetcher' && data.assets) {
      const assets = data.assets
      const assetEntries = Object.entries(assets)
      
      return (
        <div className="w-full max-w-full overflow-hidden space-y-3">
          <div className="text-xs text-[var(--kt-text-dim)]">
            Fetched data for {assetEntries.length} asset{assetEntries.length !== 1 ? 's' : ''}
          </div>
          <div className="w-full max-w-full overflow-hidden">
            <div className="space-y-2 max-h-96 overflow-y-auto overflow-x-auto">
              {assetEntries.map(([symbol, assetData]: [string, any]) => (
                <div key={symbol} className="bg-[var(--kt-inset)] rounded-lg p-3 border border-[var(--kt-border)] min-w-0">
                  <div className="font-medium text-sm text-[var(--kt-text-strong)] mb-2 break-words">{symbol}</div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {assetData.asset_type && (
                      <div className="break-words">
                        <span className="text-[var(--kt-text-muted)]">Type: </span>
                        <span className="text-[var(--kt-text-dim)]">{assetData.asset_type}</span>
                      </div>
                    )}
                    {assetData.total_points !== undefined && (
                      <div>
                        <span className="text-[var(--kt-text-muted)]">Data Points: </span>
                        <span className="text-[var(--kt-text-dim)]">{assetData.total_points}</span>
                      </div>
                    )}
                    {assetData.start_date && (
                      <div>
                        <span className="text-[var(--kt-text-muted)]">Start: </span>
                        <span className="text-[var(--kt-text-dim)]">{new Date(assetData.start_date).toLocaleDateString()}</span>
                      </div>
                    )}
                    {assetData.end_date && (
                      <div>
                        <span className="text-[var(--kt-text-muted)]">End: </span>
                        <span className="text-[var(--kt-text-dim)]">{new Date(assetData.end_date).toLocaleDateString()}</span>
                      </div>
                    )}
                    {assetData.price_change_pct !== undefined && (
                      <div className="break-words">
                        <span className="text-[var(--kt-text-muted)]">Price Change: </span>
                        <span className={`font-medium ${
                          assetData.price_change_pct >= 0 ? 'text-[var(--kt-up)]' : 'text-[var(--kt-down)]'
                        }`}>
                          {formatPercentage(assetData.price_change_pct)}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )
    }

    // Economic Agent Data (handles FMP functionality)
    if (agentId === 'economic' && (data.raw_fmp || data.fmp_data || Array.isArray(data))) {
      const fmpData = data.raw_fmp || data.fmp_data || data
      const dataArray = Array.isArray(fmpData) ? fmpData : (fmpData.data || [])
      
      if (dataArray.length > 0) {
        return (
          <div className="w-full max-w-full overflow-hidden">
            <div className="space-y-2 max-h-96 overflow-y-auto overflow-x-auto">
              <div className="text-xs text-[var(--kt-text-dim)]">
                {dataArray.length} data point{dataArray.length !== 1 ? 's' : ''}
              </div>
              {dataArray.slice(0, 10).map((item: any, idx: number) => (
                <div key={idx} className="bg-[var(--kt-inset)] rounded-lg p-3 border border-[var(--kt-border)] min-w-0">
                  <div className="text-xs text-[var(--kt-text-dim)]">
                    <pre className="whitespace-pre-wrap break-words overflow-x-auto">
                      {JSON.stringify(item, null, 2)}
                    </pre>
                  </div>
                </div>
              ))}
              {dataArray.length > 10 && (
                <div className="text-xs text-[var(--kt-text-muted)] text-center py-2">
                  ... and {dataArray.length - 10} more results
                </div>
              )}
            </div>
          </div>
        )
      }
    }

    // Search Agent Data
    if (agentId === 'search' && (data.search_context || data.search_results || data.results)) {
      const searchData = data.search_context || data.search_results || data
      const results = searchData.results || []
      const context = searchData.search_context || searchData.context || ''
      
      return (
        <div className="w-full max-w-full overflow-hidden space-y-3">
          {context && (
            <div className="bg-[var(--kt-inset)] rounded-lg p-3 border border-[var(--kt-border)] min-w-0">
              <div className="text-xs font-semibold text-[var(--kt-agent)] mb-2 uppercase">Search Context</div>
              <p className="text-xs text-[var(--kt-text-dim)] break-words whitespace-pre-wrap">{context}</p>
            </div>
          )}
          {results.length > 0 && (
            <div className="w-full max-w-full overflow-hidden">
              <div className="space-y-2 max-h-96 overflow-y-auto overflow-x-auto">
                {results.slice(0, 10).map((item: any, idx: number) => (
                  <div key={idx} className="bg-[var(--kt-inset)] rounded-lg p-3 border border-[var(--kt-border)] min-w-0">
                    {item.title && (
                      <div className="font-medium text-sm text-[var(--kt-text-strong)] mb-1 break-words">{item.title}</div>
                    )}
                    {item.url && (
                      <a 
                        href={item.url} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="text-xs text-[var(--kt-agent)] hover:text-[var(--kt-agent)] mb-2 inline-block break-all"
                      >
                        {item.url}
                      </a>
                    )}
                    {item.snippet && (
                      <p className="text-xs text-[var(--kt-text-dim)] break-words">{item.snippet}</p>
                    )}
                    {item.description && (
                      <p className="text-xs text-[var(--kt-text-dim)] break-words mt-1">{item.description}</p>
                    )}
                  </div>
                ))}
                {results.length > 10 && (
                  <div className="text-xs text-[var(--kt-text-muted)] text-center py-2">
                    ... and {results.length - 10} more results
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )
    }

    // Finalise Agent - might have combined data
    if (agentId === 'finalise') {
      // Check for nested agent data
      if (data.screener) return renderAgentData({ ...step, id: 'screener' }, data.screener)
      if (data.backtest_result || data.backtestResult) return renderAgentData({ ...step, id: 'backtest' }, data)
      if (data.economic || data.markdown) return renderAgentData({ ...step, id: 'economic' }, data)
      if (data.regulation_result || data.regulationResult) return renderAgentData({ ...step, id: 'regulations' }, data)
    }

    // Fallback: render as formatted JSON
    return (
      <div className="w-full max-w-full overflow-hidden">
        <pre className="text-xs text-[var(--kt-text-dim)] bg-[var(--kt-inset)] p-3 rounded border border-[var(--kt-border)] overflow-x-auto min-w-0 break-words whitespace-pre-wrap">
          {JSON.stringify(data, null, 2)}
        </pre>
      </div>
    )
  }

  const renderAgentNode = (step: AgentFlowStep, showExpandButton: boolean = true) => {
    const isExpanded = expandedAgents.has(step.id)
    const hasData = step.output && 'data' in step.output && step.output.data !== undefined
    const hasInputOutput = step.input || step.output || step.timestamp_start || step.latency_ms || hasData
    const canExpand = showExpandButton && hasInputOutput

    return (
      <div className="flex flex-col gap-2">
        <div
          className={`flex items-center gap-2 px-3 py-2 rounded-lg border transition-all ${canExpand ? 'cursor-pointer hover:opacity-80' : ''}`}
          onClick={canExpand ? () => toggleAgentExpansion(step.id) : undefined}
          style={{
            backgroundColor: `${getAgentColor(step)}20`,
            borderColor: `${getAgentColor(step)}60`,
          }}
        >
          {getStatusIcon(step.status)}
          <span
            className="text-sm font-medium"
            style={{ color: getAgentColor(step) }}
          >
            {step.name}
          </span>
          {/* Show latency badge if available */}
          {step.latency_ms !== undefined && step.latency_ms !== null && (
            <motion.div
              className="flex items-center gap-1 px-2 py-0.5 bg-[var(--kt-hover)] rounded text-xs text-[var(--kt-text-dim)]"
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.2 }}
            >
              <Zap className="h-3 w-3 text-[var(--kt-warn)]" />
              <span className="font-medium">{formatLatency(step.latency_ms)}</span>
            </motion.div>
          )}
          {/* Special badge for finalise agent */}
          {step.id === 'finalise' && (
            <motion.div
              className="flex items-center gap-1 px-2 py-0.5 bg-orange-500/20 rounded text-xs text-[var(--kt-warn)] border border-orange-500/30"
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.2 }}
            >
              <Sparkles className="h-3 w-3" />
              <span>Finalise</span>
            </motion.div>
          )}
          {canExpand && (
            isExpanded ? (
              <ChevronUp className="h-4 w-4 text-[var(--kt-text-dim)] ml-auto" />
            ) : (
              <ChevronDown className="h-4 w-4 text-[var(--kt-text-dim)] ml-auto" />
            )
          )}
        </div>
        
        {/* Expanded input/output details */}
        <AnimatePresence>
          {isExpanded && hasInputOutput && (
            <motion.div
              className="ml-4 space-y-2 border-l-2 border-[var(--kt-border)] pl-4"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
            >
            {/* Timing Information */}
            {(step.timestamp_start || step.timestamp_end || step.latency_ms !== undefined) && (
              <div className="bg-[var(--kt-inset)] rounded-lg p-3">
                <div className="flex items-center gap-2 mb-2">
                  <Clock className="h-3 w-3 text-[var(--kt-agent)]" />
                  <span className="text-xs font-semibold text-[var(--kt-agent)] uppercase">Execution Timing</span>
                </div>
                <div className="space-y-1 text-xs">
                  {step.timestamp_start && (
                    <div className="flex items-center gap-2">
                      <span className="text-[var(--kt-text-muted)]">Start:</span>
                      <span className="text-[var(--kt-text-dim)]">{formatTimestamp(step.timestamp_start)}</span>
                    </div>
                  )}
                  {step.timestamp_end && (
                    <div className="flex items-center gap-2">
                      <span className="text-[var(--kt-text-muted)]">End:</span>
                      <span className="text-[var(--kt-text-dim)]">{formatTimestamp(step.timestamp_end)}</span>
                    </div>
                  )}
                  {step.latency_ms !== undefined && step.latency_ms !== null && (
                    <div className="flex items-center gap-2">
                      <Zap className="h-3 w-3 text-[var(--kt-warn)]" />
                      <span className="text-[var(--kt-text-muted)]">Latency:</span>
                      <span className="text-[var(--kt-warn)] font-medium">{formatLatency(step.latency_ms)}</span>
                    </div>
                  )}
                </div>
              </div>
            )}
            {step.input && (
              <div className="bg-[var(--kt-inset)] rounded-lg p-3">
                <div className="flex items-center gap-2 mb-2">
                  <Code className="h-3 w-3 text-[var(--kt-agent)]" />
                  <span className="text-xs font-semibold text-[var(--kt-agent)] uppercase">Input</span>
                </div>
                <p className="text-xs text-[var(--kt-text-dim)] whitespace-pre-wrap break-words">{step.input}</p>
              </div>
            )}
            {step.output && (
              <div className="bg-[var(--kt-inset)] rounded-lg p-3">
                <div className="flex items-center gap-2 mb-2">
                  <MessageSquare className="h-3 w-3 text-[var(--kt-up)]" />
                  <span className="text-xs font-semibold text-[var(--kt-up)] uppercase">Output</span>
                  {step.output.success ? (
                    <CheckCircle2 className="h-3 w-3 text-[var(--kt-up)] ml-auto" />
                  ) : (
                    <XCircle className="h-3 w-3 text-[var(--kt-down)] ml-auto" />
                  )}
                </div>
                <div className="space-y-1">
                  {step.output.message && (
                    <p className="text-xs text-[var(--kt-text-dim)] whitespace-pre-wrap break-words">{step.output.message}</p>
                  )}
                  {step.output.data_keys && step.output.data_keys.length > 0 && (
                    <div className="mt-2">
                      <span className="text-xs text-[var(--kt-text-muted)]">Data keys: </span>
                      <span className="text-xs text-[var(--kt-text-dim)]">{step.output.data_keys.join(', ')}</span>
                    </div>
                  )}
                  {step.output.has_data && (
                    <span className="inline-block text-xs text-[var(--kt-up)] mt-1">✓ Has data</span>
                  )}
                </div>
              </div>
            )}
            {/* Full Data Display */}
            {step.output?.data && (
              <div className="bg-[var(--kt-inset)] rounded-lg p-3 max-w-full overflow-hidden">
                <div 
                  className="flex items-center gap-2 mb-2 cursor-pointer hover:opacity-80 transition-opacity"
                  onClick={() => toggleDataExpansion(step.id)}
                >
                  <Database className="h-3 w-3 text-[var(--kt-agent)] flex-shrink-0" />
                  <span className="text-xs font-semibold text-[var(--kt-agent)] uppercase">Data</span>
                  {expandedData.has(step.id) ? (
                    <ChevronUp className="h-3 w-3 text-[var(--kt-text-dim)] ml-auto flex-shrink-0" />
                  ) : (
                    <ChevronDown className="h-3 w-3 text-[var(--kt-text-dim)] ml-auto flex-shrink-0" />
                  )}
                </div>
                {/* Data Preview (when collapsed) */}
                {!expandedData.has(step.id) && (
                  <div className="text-xs text-[var(--kt-text-muted)] mt-1 break-words">
                    {getDataPreview(step, step.output.data)}
                  </div>
                )}
                <AnimatePresence>
                  {expandedData.has(step.id) && (
                    <motion.div
                      className="mt-2 w-full max-w-full overflow-hidden"
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.2 }}
                    >
                      {renderAgentData(step, step.output.data)}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    )
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-[var(--kt-up)]" />
      case 'pending':
        return <Loader2 className="h-4 w-4 text-[var(--kt-warn)] animate-spin" />
      case 'error':
      case 'failed':
        return <XCircle className="h-4 w-4 text-[var(--kt-down)]" />
      default:
        return <CheckCircle2 className="h-4 w-4 text-gray-400" />
    }
  }

  const getAgentColor = (step: AgentFlowStep) => {
    if (step.color) return step.color
    if (step.type === 'orchestrator') return '#4A90E2'
    return '#95A5A6'
  }

  const getFlowTypeIcon = () => {
    switch (flowType) {
      case 'parallel':
        return <GitBranch className="h-4 w-4 text-[var(--kt-agent)]" />
      case 'sequential':
        return <GitMerge className="h-4 w-4 text-[var(--kt-agent)]" />
      default:
        return null
    }
  }

  const getFlowTypeLabel = () => {
    switch (flowType) {
      case 'parallel':
        return 'Parallel Execution'
      case 'sequential':
        return 'Sequential Pipeline'
      default:
        return 'Agent Flow'
    }
  }

  // For parallel flows, group agents that have the same parent
  const renderParallelFlow = () => {
    // Find the orchestrator
    const orchestrator = steps.find(s => s.type === 'orchestrator')
    const specializedAgents = steps.filter(s => s.type === 'specialized' && s.id !== 'finalise')
    const finaliseAgent = steps.find(s => s.id === 'finalise')

    if (!orchestrator) {
      // Fallback to linear rendering
      return renderLinearFlow()
    }

    return (
      <div className="flex flex-col items-center gap-4">
        {/* Orchestrator */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          {renderAgentNode(orchestrator, false)}
        </motion.div>

        {/* Arrow down */}
        {specializedAgents.length > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
          >
            <ArrowDown className="h-4 w-4 text-[var(--kt-text-muted)]" />
          </motion.div>
        )}

        {/* Parallel agents */}
        {specializedAgents.length > 0 && (
          <motion.div
            className="flex items-start gap-4 flex-wrap justify-center"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
          >
            {specializedAgents.map((step, index) => (
              <motion.div
                key={step.id}
                className="flex flex-col items-center"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.4 + index * 0.1 }}
              >
                {renderAgentNode(step, true)}
              </motion.div>
            ))}
          </motion.div>
        )}

        {/* Finalise agent - always at the end */}
        {finaliseAgent && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 + specializedAgents.length * 0.1 }}
            >
              <ArrowDown className="h-4 w-4 text-[var(--kt-text-muted)]" />
            </motion.div>
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.6 + specializedAgents.length * 0.1 }}
            >
              {renderAgentNode(finaliseAgent, true)}
            </motion.div>
          </>
        )}
      </div>
    )
  }

  // For sequential flows, render in order
  const renderSequentialFlow = () => {
    return (
      <div className="flex flex-col items-center gap-3">
        {steps.map((step, index) => (
          <React.Fragment key={step.id}>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.15, duration: 0.3 }}
            >
              {renderAgentNode(step, true)}
            </motion.div>
            {index < steps.length - 1 && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: index * 0.15 + 0.1 }}
              >
                <ArrowDown className="h-4 w-4 text-[var(--kt-text-muted)]" />
              </motion.div>
            )}
          </React.Fragment>
        ))}
      </div>
    )
  }

  // Linear flow (default)
  const renderLinearFlow = () => {
    return (
      <div className="flex flex-col gap-3">
        {steps.map((step, index) => (
          <React.Fragment key={step.id}>
            <div className="flex items-start gap-3">
              <motion.div
                className="flex-1"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1, duration: 0.3 }}
              >
                {renderAgentNode(step, true)}
              </motion.div>
              {index < steps.length - 1 && (
                <motion.div
                  className="flex-shrink-0 mt-3"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: index * 0.1 + 0.15 }}
                >
                  <ArrowRight className="h-4 w-4 text-[var(--kt-text-muted)]" />
                </motion.div>
              )}
            </div>
          </React.Fragment>
        ))}
      </div>
    )
  }

  return (
    <Card className="w-full bg-[var(--kt-hover)] border-[var(--kt-border)] backdrop-blur-sm">
      <CardHeader className="pb-3 flex flex-row items-center justify-between">
        <CardTitle className="text-base text-[var(--kt-text-strong)] flex items-center gap-2">
          {getFlowTypeIcon()}
          <span>{getFlowTypeLabel()}</span>
          {flowType !== 'single' && (
            <span className="text-xs text-[var(--kt-text-dim)] font-normal ml-2">
              ({steps.length} agent{steps.length !== 1 ? 's' : ''})
            </span>
          )}
        </CardTitle>
      </CardHeader>
      {/* The terminal toggle that used to sit here is gone. It replayed a
          finished flow at an invented 120ms a row while calling itself live,
          and it duplicated the real event log — which now lives in Devtools →
          Terminal, accumulates across the whole session, and is written as the
          calls actually happen. This card does the one thing it is good at:
          the shape of the flow. */}
      <CardContent>
        {flowType === 'parallel' && renderParallelFlow()}
        {flowType === 'sequential' && renderSequentialFlow()}
        {flowType === 'single' && renderLinearFlow()}
      </CardContent>
    </Card>
  )
}
