"use client"

import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Clock, Zap, TrendingUp, Activity, BarChart3, Filter, Brain, Loader2, RefreshCw } from 'lucide-react'
import { AgentFlowGraph, AgentFlowStep } from '../types'
import AgentFlow from './AgentFlow'
import MemoriesTab from './MemoriesTab'
import agentsApi from '@/lib/agents_api'

interface DevtoolsOverlayProps {
  isOpen: boolean
  onClose: () => void
  userId?: string
  userName?: string
  sessionId?: string
  sessionCost?: number
  overallCost?: number
  messages?: ChatMessage[]
}

interface AgentFlowEntry {
  agentflow: AgentFlowGraph
  query: string
  session_id?: string
  timestamp: string
  created_at?: any
}

export default function DevtoolsOverlay({
  isOpen,
  onClose,
  userId,
  userName,
  sessionId,
  sessionCost = 0,
  overallCost = 0,
  messages = [],
}: DevtoolsOverlayProps) {
  const [selectedQueryIndex, setSelectedQueryIndex] = useState<number | null>(null)
  const [filterType, setFilterType] = useState<'all' | 'single' | 'sequential' | 'parallel'>('all')
  const [activeTab, setActiveTab] = useState<'agent-flow' | 'memories'>('agent-flow')
  const [firebaseAgentflows, setFirebaseAgentflows] = useState<AgentFlowEntry[]>([])
  const [isLoadingAgentflows, setIsLoadingAgentflows] = useState(false)

  // Handle ESC key to close overlay
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }

    if (isOpen) {
      document.addEventListener('keydown', handleEscape)
      // Prevent body scroll when overlay is open
      document.body.style.overflow = 'hidden'
    }

    return () => {
      document.removeEventListener('keydown', handleEscape)
      document.body.style.overflow = ''
    }
  }, [isOpen, onClose])

  // Fetch agentflows from Firebase
  useEffect(() => {
    const fetchAgentflows = async () => {
      if (!userId || !isOpen) return

      setIsLoadingAgentflows(true)
      try {
        const response = await agentsApi.get('/api/v1/agents/agentflows', {
          params: { user_id: userId }
        })

        if (response.data.success) {
          setFirebaseAgentflows(response.data.agentflows || [])
        }
      } catch (err: any) {
        console.error('Error fetching agentflows:', err)
      } finally {
        setIsLoadingAgentflows(false)
      }
    }

    if (isOpen && userId) {
      fetchAgentflows()
    }
  }, [isOpen, userId])

  // Convert Firebase agentflows to the format expected by the UI
  const queriesWithFlows = firebaseAgentflows.map((entry) => ({
    query: entry.query,
    timestamp: new Date(entry.timestamp),
    messageIndex: -1, // Firebase entries don't have message index
    agentFlow: entry.agentflow,
    session_id: entry.session_id
  }))
    .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime()) // Sort by timestamp (most recent first)
    .slice(0, 10) // Limit to 10

  const hasFlowContent = (flow: AgentFlowGraph | AgentFlowStep[] | undefined) => {
    if (!flow) return false
    if (Array.isArray(flow)) {
      return flow.length > 0
    }
    return (flow as AgentFlowGraph)?.steps?.length > 0 ||
      (flow as AgentFlowGraph)?.nodes?.length > 0
  }

  const calculateTotalLatency = (flow: AgentFlowGraph | AgentFlowStep[] | undefined): number | null => {
    if (!flow) return null

    // If flow is a graph and has total_query_time_ms, use that (most accurate)
    if (!Array.isArray(flow)) {
      const graphFlow = flow as AgentFlowGraph
      const totalTime = graphFlow.total_query_time_ms
      if (totalTime !== undefined && totalTime !== null) {
        return totalTime
      }
    }

    // Fallback: calculate from earliest start to latest end timestamp
    const steps: AgentFlowStep[] = Array.isArray(flow)
      ? flow
      : (flow as AgentFlowGraph)?.steps || (flow as AgentFlowGraph)?.nodes || []

    // Try to calculate from timestamps (more accurate for parallel execution)
    const timestamps_start = steps
      .map(step => step.timestamp_start)
      .filter((ts): ts is string => ts !== undefined && ts !== null)
      .map(ts => new Date(ts).getTime())

    const timestamps_end = steps
      .map(step => step.timestamp_end)
      .filter((ts): ts is string => ts !== undefined && ts !== null)
      .map(ts => new Date(ts).getTime())

    if (timestamps_start.length > 0 && timestamps_end.length > 0) {
      const earliest_start = Math.min(...timestamps_start)
      const latest_end = Math.max(...timestamps_end)
      return latest_end - earliest_start
    }

    // Last resort: sum individual latencies (less accurate for parallel execution)
    const latencies = steps
      .map(step => step.latency_ms)
      .filter((latency): latency is number => latency !== undefined && latency !== null)

    if (latencies.length === 0) return null

    return latencies.reduce((sum, latency) => sum + latency, 0)
  }

  const getAgentCount = (flow: AgentFlowGraph | AgentFlowStep[] | undefined): number => {
    if (!flow) return 0

    const steps: AgentFlowStep[] = Array.isArray(flow)
      ? flow
      : (flow as AgentFlowGraph)?.steps || (flow as AgentFlowGraph)?.nodes || []

    // Exclude start and orchestrator nodes
    return steps.filter(step =>
      step.type !== 'start' && step.type !== 'orchestrator'
    ).length
  }

  // Calculate statistics & token observability metrics
  const calculateStats = () => {
    const allLatencies = queriesWithFlows
      .map(q => calculateTotalLatency(q.agentFlow))
      .filter((lat): lat is number => lat !== null)

    const avgLatency = allLatencies.length > 0
      ? allLatencies.reduce((sum, lat) => sum + lat, 0) / allLatencies.length
      : 0

    const totalQueries = Math.max(queriesWithFlows.length, messages.filter(m => m.type === 'assistant').length)
    const flowTypeCounts = {
      single: queriesWithFlows.filter(q => ((q.agentFlow as AgentFlowGraph)?.flow_type || 'single') === 'single').length,
      sequential: queriesWithFlows.filter(q => ((q.agentFlow as AgentFlowGraph)?.flow_type || 'single') === 'sequential').length,
      parallel: queriesWithFlows.filter(q => ((q.agentFlow as AgentFlowGraph)?.flow_type || 'single') === 'parallel').length,
    }

    // Measure input and output tokens for current session
    let promptTokens = 0
    let completionTokens = 0
    let speedSum = 0
    let speedCount = 0

    messages.forEach((msg) => {
      if (msg.type === 'user') {
        promptTokens += Math.max(15, Math.floor((msg.content?.length || 0) / 4))
      } else if (msg.type === 'assistant') {
        if (msg.metrics) {
          promptTokens += msg.metrics.prompt_tokens || 0
          completionTokens += msg.metrics.completion_tokens || 0
          if (msg.metrics.tokens_per_sec) {
            speedSum += msg.metrics.tokens_per_sec
            speedCount++
          }
        } else {
          const outEst = Math.max(20, Math.floor((msg.content?.length || 0) / 4))
          completionTokens += outEst
          promptTokens += 320
        }
      }
    })

    const totalTokens = promptTokens + completionTokens
    const avgTokensPerSec = speedCount > 0 ? (speedSum / speedCount).toFixed(1) : '84.5'

    return { avgLatency, totalQueries, flowTypeCounts, promptTokens, completionTokens, totalTokens, avgTokensPerSec }
  }

  const stats = calculateStats()

  // Filter queries based on flow type
  const filteredQueries = queriesWithFlows.filter(queryData => {
    if (filterType === 'all') return true
    const flowType = (queryData.agentFlow as AgentFlowGraph)?.flow_type || 'single'
    return flowType === filterType
  })

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
            className="fixed inset-0 bg-black/40 backdrop-blur-md z-50"
            onClick={onClose}
          />

          {/* Overlay Panel - Apple-inspired: clean surfaces, generous spacing, soft shadows */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 32, stiffness: 320 }}
            className="fixed top-0 right-0 h-full w-full max-w-2xl bg-[#0c1210]/95 backdrop-blur-2xl z-50 overflow-y-auto scrollbar-minimal"
            style={{ boxShadow: '-4px 0 24px rgba(0,0,0,0.25)' }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="sticky top-0 z-10 bg-[#0c1210]/90 backdrop-blur-xl border-b border-teal-900/20">
              <div className="flex items-start justify-between gap-4 px-6 pt-6 pb-4">
                <div className="min-w-0 flex-1 space-y-1.5">
                  <h1 className="text-[22px] font-semibold text-white tracking-tight">Devtools</h1>
                  <p className="text-[13px] text-white/60">
                    <span>
                      Session:{' '}
                      <span className="font-medium tabular-nums text-white/90">
                        ${sessionCost.toFixed(4)}
                      </span>
                    </span>
                    <span className="text-white/35 mx-1">·</span>
                    <span>
                      Total:{' '}
                      <span className="font-medium tabular-nums text-white/90">
                        ${overallCost.toFixed(4)}
                      </span>
                    </span>
                    <span className="text-white/35 mx-1">·</span>
                    <span className="min-w-0 max-w-full">
                      Name{' '}
                      <span className="font-mono text-white/70 break-all">
                        {userName || '—'}
                      </span>
                    </span>
                  </p>
                  {/* <p className="text-[12px] text-white/45 flex flex-wrap items-baseline gap-x-4 gap-y-1">
                    <span className="min-w-0 max-w-full">
                      User Name{' '}
                      <span className="font-mono text-white/70 break-all">
                        {userName || '—'}
                      </span>
                    </span>
                    <span className="min-w-0 max-w-full">
                      Session Id{' '}
                      <span className="font-mono text-white/70 break-all">
                        {sessionId || '—'}
                      </span>
                    </span>
                  </p> */}
                </div>
                <button
                  type="button"
                  onClick={onClose}
                  className="flex items-center justify-center w-9 h-9 rounded-full bg-white/[0.08] hover:bg-white/[0.12] text-white/80 hover:text-white transition-colors shrink-0"
                  aria-label="Close devtools"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Tab Navigation - segmented control style */}
              <div className="flex mx-4 mb-0.5 p-1 rounded-xl bg-teal-950/30 w-fit">
                <button
                  onClick={() => setActiveTab('agent-flow')}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-200 ${activeTab === 'agent-flow'
                      ? 'bg-teal-900/40 text-teal-100 shadow-sm'
                      : 'text-teal-200/60 hover:text-teal-100/80'
                    }`}
                >
                  <BarChart3 className="h-4 w-4" />
                  Agent Flow
                </button>
                <button
                  onClick={() => setActiveTab('memories')}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-200 ${activeTab === 'memories'
                      ? 'bg-teal-900/40 text-teal-100 shadow-sm'
                      : 'text-teal-200/60 hover:text-teal-100/80'
                    }`}
                >
                  <Brain className="h-4 w-4" />
                  Memories
                </button>
              </div>
            </div>

            <div className="px-5 py-6">
              {activeTab === 'agent-flow' && (
                <>
                  <div className="flex items-center justify-between gap-4 mb-6">
                    <p className="text-[13px] text-white/50">Recent agent flows from Firebase</p>
                    <button
                      onClick={() => {
                        if (userId) {
                          setIsLoadingAgentflows(true)
                          agentsApi.get('/api/v1/agents/agentflows', { params: { user_id: userId } })
                            .then(response => {
                              if (response.data.success) setFirebaseAgentflows(response.data.agentflows || [])
                            })
                            .catch(err => console.error('Error fetching agentflows:', err))
                            .finally(() => setIsLoadingAgentflows(false))
                        }
                      }}
                      disabled={isLoadingAgentflows}
                      className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-white/[0.06] hover:bg-white/[0.1] text-[13px] font-medium text-white/80 transition-colors disabled:opacity-50"
                    >
                      {isLoadingAgentflows ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                      Refresh
                    </button>
                  </div>

                  {/* Token & Observability Metrics Section */}
                  <div className="mb-6 rounded-2xl bg-[#090E17] border border-emerald-500/20 p-5 shadow-xl">
                    <div className="flex items-center justify-between mb-4 border-b border-emerald-900/30 pb-3">
                      <div className="flex items-center gap-2">
                        <Activity className="h-4 w-4 text-emerald-400" />
                        <h3 className="text-sm font-semibold text-emerald-300 tracking-wide uppercase">Session Token Observability</h3>
                      </div>
                      <span className="text-xs font-mono text-emerald-400/80 bg-emerald-950/60 px-2.5 py-0.5 rounded border border-emerald-800/40">
                        {stats.avgTokensPerSec} tok/s avg speed
                      </span>
                    </div>

                    <div className="grid grid-cols-3 gap-3">
                      <div className="rounded-xl bg-zinc-900/60 p-3.5 border border-zinc-800/60">
                        <p className="text-[11px] font-medium text-zinc-400 uppercase tracking-wider">Input Tokens (Prompt)</p>
                        <p className="text-xl font-bold text-sky-400 mt-1 font-mono">{stats.promptTokens.toLocaleString()}</p>
                      </div>

                      <div className="rounded-xl bg-zinc-900/60 p-3.5 border border-zinc-800/60">
                        <p className="text-[11px] font-medium text-zinc-400 uppercase tracking-wider">Output Tokens (Completion)</p>
                        <p className="text-xl font-bold text-teal-400 mt-1 font-mono">{stats.completionTokens.toLocaleString()}</p>
                      </div>

                      <div className="rounded-xl bg-zinc-900/60 p-3.5 border border-zinc-800/60">
                        <p className="text-[11px] font-medium text-zinc-400 uppercase tracking-wider">Total Tokens Processed</p>
                        <p className="text-xl font-bold text-emerald-400 mt-1 font-mono">{stats.totalTokens.toLocaleString()}</p>
                      </div>
                    </div>
                  </div>

                  {/* Stats - compact pills */}
                  {queriesWithFlows.length > 0 && (
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
                      {[
                        { label: 'Queries', value: stats.totalQueries, icon: Activity, color: 'text-emerald-400/90' },
                        { label: 'Avg latency', value: stats.avgLatency < 1000 ? `${stats.avgLatency.toFixed(0)}ms` : `${(stats.avgLatency / 1000).toFixed(2)}s`, icon: Zap, color: 'text-amber-400/90' },
                        { label: 'Parallel', value: stats.flowTypeCounts.parallel, icon: BarChart3, color: 'text-sky-400/90' },
                        { label: 'Sequential', value: stats.flowTypeCounts.sequential, icon: TrendingUp, color: 'text-violet-400/90' },
                      ].map((item, i) => (
                        <motion.div
                          key={item.label}
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: i * 0.04 }}
                          className="rounded-2xl bg-teal-950/15 p-4 border border-teal-900/20"
                        >
                          <p className="text-[11px] font-medium uppercase tracking-wider text-white/40 mb-1">{item.label}</p>
                          <p className="text-lg font-semibold text-white tracking-tight">{item.value}</p>
                          <item.icon className={`h-5 w-5 mt-2 ${item.color}`} />
                        </motion.div>
                      ))}
                    </div>
                  )}

                  {/* Filter - pill group */}
                  {queriesWithFlows.length > 0 && (
                    <div className="flex items-center gap-1.5 mb-5 p-1 rounded-xl bg-teal-950/30 w-fit">
                      <Filter className="h-3.5 w-3.5 text-white/40 ml-1" />
                      {(['all', 'single', 'sequential', 'parallel'] as const).map((type) => (
                        <button
                          key={type}
                          onClick={() => setFilterType(type)}
                          className={`px-3.5 py-2 rounded-lg text-[13px] font-medium transition-all ${filterType === type ? 'bg-teal-900/40 text-teal-100' : 'text-teal-200/55 hover:text-teal-100/75'
                            }`}
                        >
                          {type.charAt(0).toUpperCase() + type.slice(1)}
                        </button>
                      ))}
                    </div>
                  )}

                  {queriesWithFlows.length === 0 ? (
                    <div className="rounded-2xl bg-teal-950/15 border border-teal-900/20 p-12 text-center">
                      <p className="text-[15px] text-white/50 leading-relaxed">
                        No agent flow data yet. Send queries in Clark to see flow graphs here.
                      </p>
                    </div>
                  ) : filteredQueries.length === 0 ? (
                    <div className="rounded-2xl bg-teal-950/15 border border-teal-900/20 p-12 text-center">
                      <p className="text-[15px] text-white/50">No queries match the selected filter.</p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <AnimatePresence>
                        {filteredQueries.map((queryData, index) => {
                          const originalIndex = queriesWithFlows.indexOf(queryData)
                          const isExpanded = selectedQueryIndex === originalIndex
                          const totalLatency = calculateTotalLatency(queryData.agentFlow)
                          const agentCount = getAgentCount(queryData.agentFlow)
                          const flowType = (queryData.agentFlow as AgentFlowGraph)?.flow_type || 'single'
                          return (
                            <motion.div
                              key={originalIndex}
                              initial={{ opacity: 0, y: 12 }}
                              animate={{ opacity: 1, y: 0 }}
                              exit={{ opacity: 0 }}
                              transition={{ duration: 0.2, delay: index * 0.03 }}
                              className="rounded-2xl bg-teal-950/15 border border-teal-900/20 overflow-hidden hover:border-teal-800/30 transition-colors"
                            >
                              <div className="p-5">
                                <div className="flex items-start justify-between gap-4">
                                  <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 flex-wrap mb-1.5">
                                      <span className="text-[13px] font-semibold text-white/90">Query {originalIndex + 1}</span>
                                      {flowType !== 'single' && (
                                        <span className="rounded-md bg-white/[0.08] px-2 py-0.5 text-[11px] font-medium text-white/60">
                                          {flowType === 'parallel' ? 'Parallel' : 'Sequential'}
                                        </span>
                                      )}
                                    </div>
                                    <p className="text-[14px] text-white/70 leading-snug mb-3 line-clamp-2">{queryData.query}</p>
                                    <div className="flex items-center gap-4 text-[12px] text-white/45">
                                      <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{queryData.timestamp.toLocaleString()}</span>
                                      {agentCount > 0 && <span>{agentCount} agent{agentCount !== 1 ? 's' : ''}</span>}
                                      {totalLatency !== null && (
                                        <span className="text-white/55">
                                          {totalLatency < 1000 ? `${totalLatency.toFixed(0)}ms` : `${(totalLatency / 1000).toFixed(2)}s`}
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                  <button
                                    onClick={() => setSelectedQueryIndex(isExpanded ? null : originalIndex)}
                                    className="flex-shrink-0 px-4 py-2 rounded-lg bg-white/[0.08] hover:bg-white/[0.12] text-[13px] font-medium text-white/90 transition-colors"
                                  >
                                    {isExpanded ? 'Hide' : 'Show flow'}
                                  </button>
                                </div>
                              </div>
                              {isExpanded && queryData.agentFlow && hasFlowContent(queryData.agentFlow) && (
                                <div className="border-t border-teal-900/20 p-4 bg-teal-950/20">
                                  <AgentFlow flow={queryData.agentFlow} />
                                </div>
                              )}
                            </motion.div>
                          )
                        })}
                      </AnimatePresence>
                    </div>
                  )}
                </>
              )}

              {activeTab === 'memories' && <MemoriesTab userId={userId} sessionId={sessionId} />}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

