"use client"

import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Clock, Zap, TrendingUp, Activity, BarChart3, Filter, Brain, Loader2, RefreshCw } from 'lucide-react'
import { ChatMessage, AgentFlowGraph, AgentFlowStep } from '../types'
import AgentFlow from './AgentFlow'
import MemoriesTab from './MemoriesTab'
import agentsApi from '@/lib/agents_api'

interface DevtoolsOverlayProps {
  isOpen: boolean
  onClose: () => void
  messages: ChatMessage[]
  userId?: string
  userName?: string
  sessionId?: string
  sessionCost?: number
  overallCost?: number
}

interface AgentFlowEntry {
  agentflow: AgentFlowGraph
  query: string
  session_id?: string
  timestamp: string
  created_at?: any
}

export default function DevtoolsOverlay({ isOpen, onClose, messages, userId, userName, sessionId, sessionCost = 0, overallCost = 0 }: DevtoolsOverlayProps) {
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

  // Calculate statistics
  const calculateStats = () => {
    const allLatencies = queriesWithFlows
      .map(q => calculateTotalLatency(q.agentFlow))
      .filter((lat): lat is number => lat !== null)
    
    const avgLatency = allLatencies.length > 0
      ? allLatencies.reduce((sum, lat) => sum + lat, 0) / allLatencies.length
      : 0
    
    const totalQueries = queriesWithFlows.length
    const flowTypeCounts = {
      single: queriesWithFlows.filter(q => ((q.agentFlow as AgentFlowGraph)?.flow_type || 'single') === 'single').length,
      sequential: queriesWithFlows.filter(q => ((q.agentFlow as AgentFlowGraph)?.flow_type || 'single') === 'sequential').length,
      parallel: queriesWithFlows.filter(q => ((q.agentFlow as AgentFlowGraph)?.flow_type || 'single') === 'parallel').length,
    }
    
    return { avgLatency, totalQueries, flowTypeCounts }
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
            className="fixed top-0 right-0 h-full w-full max-w-2xl bg-[#0d0d0d]/95 backdrop-blur-2xl z-50 overflow-y-auto"
            style={{ boxShadow: '-4px 0 24px rgba(0,0,0,0.25)' }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="sticky top-0 z-10 bg-[#0d0d0d]/90 backdrop-blur-xl border-b border-white/[0.06]">
              <div className="flex items-start justify-between gap-4 px-6 pt-6 pb-4">
                <div className="min-w-0">
                  <h1 className="text-[22px] font-semibold text-white tracking-tight">Devtools</h1>
                  {(userId || userName) && (
                    <p className="mt-1.5 text-[13px] text-white/50 truncate">
                      {userName && <span>{userName}</span>}
                      {userId && userName && <span className="text-white/40"> · </span>}
                      {userId && <span className="text-white/40 font-mono">{userId.slice(0, 12)}…</span>}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-white/[0.06] px-3 py-1.5 text-[13px] text-white/70">
                      Session <span className="font-medium text-white/90">${sessionCost.toFixed(4)}</span>
                    </span>
                    <span className="rounded-full bg-white/[0.06] px-3 py-1.5 text-[13px] text-white/70">
                      Total <span className="font-medium text-white/90">${overallCost.toFixed(4)}</span>
                    </span>
                  </div>
                  <button
                    onClick={onClose}
                    className="flex items-center justify-center w-9 h-9 rounded-full bg-white/[0.08] hover:bg-white/[0.12] text-white/80 hover:text-white transition-colors"
                    aria-label="Close devtools"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>
              
              {/* Tab Navigation - segmented control style */}
              <div className="flex mx-4 mb-0.5 p-1 rounded-xl bg-white/[0.06] w-fit">
                <button
                  onClick={() => setActiveTab('agent-flow')}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-200 ${
                    activeTab === 'agent-flow'
                      ? 'bg-white/10 text-white shadow-sm'
                      : 'text-white/50 hover:text-white/70'
                  }`}
                >
                  <BarChart3 className="h-4 w-4" />
                  Agent Flow
                </button>
                <button
                  onClick={() => setActiveTab('memories')}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-200 ${
                    activeTab === 'memories'
                      ? 'bg-white/10 text-white shadow-sm'
                      : 'text-white/50 hover:text-white/70'
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
                      className="rounded-2xl bg-white/[0.04] p-4 border border-white/[0.06]"
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
                <div className="flex items-center gap-1.5 mb-5 p-1 rounded-xl bg-white/[0.04] w-fit">
                  <Filter className="h-3.5 w-3.5 text-white/40 ml-1" />
                  {(['all', 'single', 'sequential', 'parallel'] as const).map((type) => (
                    <button
                      key={type}
                      onClick={() => setFilterType(type)}
                      className={`px-3.5 py-2 rounded-lg text-[13px] font-medium transition-all ${
                        filterType === type ? 'bg-white/10 text-white' : 'text-white/45 hover:text-white/65'
                      }`}
                    >
                      {type.charAt(0).toUpperCase() + type.slice(1)}
                    </button>
                  ))}
                </div>
              )}

              {queriesWithFlows.length === 0 ? (
                <div className="rounded-2xl bg-white/[0.04] border border-white/[0.06] p-12 text-center">
                  <p className="text-[15px] text-white/50 leading-relaxed">
                    No agent flow data yet. Send queries in Clark to see flow graphs here.
                  </p>
                </div>
              ) : filteredQueries.length === 0 ? (
                <div className="rounded-2xl bg-white/[0.04] border border-white/[0.06] p-12 text-center">
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
                          className="rounded-2xl bg-white/[0.04] border border-white/[0.06] overflow-hidden hover:border-white/[0.08] transition-colors"
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
                            <div className="border-t border-white/[0.06] p-4 bg-black/20">
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
              
              {activeTab === 'memories' && (
                <MemoriesTab userId={userId} sessionId={sessionId} messages={messages} />
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

