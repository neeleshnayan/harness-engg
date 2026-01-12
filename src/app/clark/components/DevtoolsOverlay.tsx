"use client"

import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Clock, Zap, TrendingUp, Activity, BarChart3, Filter, Brain, Loader2, RefreshCw } from 'lucide-react'
import { ChatMessage, AgentFlowGraph, AgentFlowStep } from '../types'
import AgentFlow from './AgentFlow'
import MemoriesTab from './MemoriesTab'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import agentsApi from '@/lib/agents_api'

interface DevtoolsOverlayProps {
  isOpen: boolean
  onClose: () => void
  messages: ChatMessage[]
  userId?: string
}

interface AgentFlowEntry {
  agentflow: AgentFlowGraph
  query: string
  session_id?: string
  timestamp: string
  created_at?: any
}

export default function DevtoolsOverlay({ isOpen, onClose, messages, userId }: DevtoolsOverlayProps) {
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
    
    const steps: AgentFlowStep[] = Array.isArray(flow) 
      ? flow 
      : (flow as AgentFlowGraph)?.steps || (flow as AgentFlowGraph)?.nodes || []
    
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
            transition={{ duration: 0.3 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50"
            onClick={onClose}
          />
          
          {/* Overlay Panel */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 30, stiffness: 300 }}
            className="fixed top-0 right-0 h-full w-3/4 bg-gradient-to-b from-[#1c2f2f]/95 to-[#0b1515]/95 backdrop-blur-xl border-l border-white/15 z-50 shadow-[0_20px_60px_rgba(0,0,0,0.6)] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sticky top-0 bg-gradient-to-b from-[#1c2f2f]/95 to-[#0b1515]/95 backdrop-blur-xl border-b border-white/15 z-10">
              <div className="flex items-center justify-between p-4">
                <h1 className="text-2xl font-bold text-white">Devtools</h1>
                <button
                  onClick={onClose}
                  className="flex items-center justify-center w-10 h-10 rounded-xl bg-white/10 hover:bg-white/15 border border-white/20 text-white transition-colors"
                  aria-label="Close devtools"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              
              {/* Tab Navigation */}
              <div className="flex items-center gap-2 px-4 pb-4">
                <button
                  onClick={() => setActiveTab('agent-flow')}
                  className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm transition-colors border ${
                    activeTab === 'agent-flow'
                      ? 'bg-teal-900/40 text-teal-300 border-teal-700/30 hover:bg-teal-800/50'
                      : 'bg-white/10 text-white/60 border-white/15 hover:bg-white/15'
                  }`}
                >
                  <BarChart3 className="h-4 w-4" />
                  Agent Flow
                </button>
                <button
                  onClick={() => setActiveTab('memories')}
                  className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm transition-colors border ${
                    activeTab === 'memories'
                      ? 'bg-teal-900/40 text-teal-300 border-teal-700/30 hover:bg-teal-800/50'
                      : 'bg-white/10 text-white/60 border-white/15 hover:bg-white/15'
                  }`}
                >
                  <Brain className="h-4 w-4" />
                  Memories
                </button>
              </div>
            </div>

            <div className="p-4 sm:p-6 lg:p-8">
              {/* Tab Content */}
              {activeTab === 'agent-flow' && (
                <>
              {/* Header with refresh button */}
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-xl font-bold text-white flex items-center gap-2">
                    <BarChart3 className="h-5 w-5 text-teal-400" />
                    Agent Flows (Last 10)
                  </h2>
                  <p className="text-sm text-white/60 mt-1">
                    View the last 10 agentflows
                  </p>
                </div>
                <button
                  onClick={() => {
                    if (userId) {
                      setIsLoadingAgentflows(true)
                      agentsApi.get('/api/v1/agents/agentflows', {
                        params: { user_id: userId }
                      })
                      .then(response => {
                        if (response.data.success) {
                          setFirebaseAgentflows(response.data.agentflows || [])
                        }
                      })
                      .catch(err => console.error('Error fetching agentflows:', err))
                      .finally(() => setIsLoadingAgentflows(false))
                    }
                  }}
                  disabled={isLoadingAgentflows}
                  className="flex items-center gap-2 px-4 py-2 bg-teal-900/40 hover:bg-teal-800/50 backdrop-blur-sm border border-teal-700/30 text-white rounded-xl transition-colors disabled:opacity-50"
                >
                  {isLoadingAgentflows ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="h-4 w-4" />
                  )}
                  Refresh
                </button>
              </div>

              {/* Statistics Cards */}
              {queriesWithFlows.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                  >
                    <Card className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/15 backdrop-blur-xl shadow-[0_8px_24px_rgba(0,0,0,0.4)]">
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-xs text-white/60 mb-1">Total Queries</p>
                            <p className="text-2xl font-bold text-white">{stats.totalQueries}</p>
                          </div>
                          <Activity className="h-8 w-8 text-teal-400" />
                        </div>
                      </CardContent>
                    </Card>
                  </motion.div>
                  
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                  >
                    <Card className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/15 backdrop-blur-xl shadow-[0_8px_24px_rgba(0,0,0,0.4)]">
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-xs text-white/60 mb-1">Avg Latency</p>
                            <p className="text-2xl font-bold text-white">
                              {stats.avgLatency < 1000 
                                ? `${stats.avgLatency.toFixed(0)}ms` 
                                : `${(stats.avgLatency / 1000).toFixed(2)}s`}
                            </p>
                          </div>
                          <Zap className="h-8 w-8 text-cyan-400" />
                        </div>
                      </CardContent>
                    </Card>
                  </motion.div>
                  
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                  >
                    <Card className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/15 backdrop-blur-xl shadow-[0_8px_24px_rgba(0,0,0,0.4)]">
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-xs text-white/60 mb-1">Parallel Flows</p>
                            <p className="text-2xl font-bold text-white">{stats.flowTypeCounts.parallel}</p>
                          </div>
                          <BarChart3 className="h-8 w-8 text-teal-300" />
                        </div>
                      </CardContent>
                    </Card>
                  </motion.div>
                  
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.4 }}
                  >
                    <Card className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/15 backdrop-blur-xl shadow-[0_8px_24px_rgba(0,0,0,0.4)]">
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-xs text-white/60 mb-1">Sequential Flows</p>
                            <p className="text-2xl font-bold text-white">{stats.flowTypeCounts.sequential}</p>
                          </div>
                          <TrendingUp className="h-8 w-8 text-cyan-300" />
                        </div>
                      </CardContent>
                    </Card>
                  </motion.div>
                </div>
              )}

              {/* Filter Buttons */}
              {queriesWithFlows.length > 0 && (
                <div className="flex items-center gap-2 mb-6">
                  <Filter className="h-4 w-4 text-white/60" />
                  <span className="text-sm text-white/60">Filter:</span>
                  {(['all', 'single', 'sequential', 'parallel'] as const).map((type) => (
                    <button
                      key={type}
                      onClick={() => setFilterType(type)}
                      className={`px-3 py-1 rounded-xl text-sm transition-colors border ${
                        filterType === type
                          ? 'bg-teal-900/40 text-teal-300 border-teal-700/30 hover:bg-teal-800/50'
                          : 'bg-white/10 text-white/60 border-white/15 hover:bg-white/15'
                      }`}
                    >
                      {type.charAt(0).toUpperCase() + type.slice(1)}
                    </button>
                  ))}
                </div>
              )}

              {queriesWithFlows.length === 0 ? (
                <Card className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/15 backdrop-blur-xl shadow-[0_8px_24px_rgba(0,0,0,0.4)]">
                  <CardContent className="p-8 text-center">
                    <p className="text-white/60">
                      No agent flow data available. Send some queries in the main Clark interface to see flow graphs here.
                    </p>
                  </CardContent>
                </Card>
              ) : filteredQueries.length === 0 ? (
                <Card className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/15 backdrop-blur-xl shadow-[0_8px_24px_rgba(0,0,0,0.4)]">
                  <CardContent className="p-8 text-center">
                    <p className="text-white/60">
                      No queries match the selected filter.
                    </p>
                  </CardContent>
                </Card>
              ) : (
                <div className="space-y-6">
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
                          initial={{ opacity: 0, y: 20 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -20 }}
                          transition={{ duration: 0.3, delay: index * 0.05 }}
                        >
                          <Card 
                            className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/15 backdrop-blur-xl shadow-[0_8px_24px_rgba(0,0,0,0.4)] hover:border-white/25 transition-colors"
                          >
                            <CardHeader>
                              <div className="flex items-start justify-between">
                                <div className="flex-1">
                                  <div className="flex items-center gap-3 mb-2">
                                    <CardTitle className="text-lg text-white">
                                      Query #{originalIndex + 1}
                                    </CardTitle>
                                    {flowType !== 'single' && (
                                      <span className="px-2 py-1 bg-teal-900/40 text-teal-300 text-xs rounded-xl border border-teal-700/30">
                                        {flowType === 'parallel' ? 'Parallel' : 'Sequential'}
                                      </span>
                                    )}
                                  </div>
                                  <CardDescription className="text-white/70 mb-3">
                                    {queryData.query}
                                  </CardDescription>
                                  <div className="flex items-center gap-4 flex-wrap">
                                    <div className="text-xs text-white/50 flex items-center gap-1">
                                      <Clock className="h-3 w-3" />
                                      {queryData.timestamp.toLocaleString()}
                                    </div>
                                    {agentCount > 0 && (
                                      <div className="text-xs text-white/60 flex items-center gap-1">
                                        <TrendingUp className="h-3 w-3" />
                                        {agentCount} agent{agentCount !== 1 ? 's' : ''}
                                      </div>
                                    )}
                                    {totalLatency !== null && (
                                      <div className="text-xs text-cyan-300 flex items-center gap-1">
                                        <Zap className="h-3 w-3" />
                                        Total: {totalLatency < 1000 
                                          ? `${totalLatency.toFixed(0)}ms` 
                                          : `${(totalLatency / 1000).toFixed(2)}s`}
                                      </div>
                                    )}
                                  </div>
                                </div>
                                <button
                                  onClick={() => setSelectedQueryIndex(isExpanded ? null : originalIndex)}
                                  className="ml-4 px-4 py-2 bg-white/10 hover:bg-white/15 border border-white/20 text-white rounded-xl transition-colors text-sm"
                                >
                                  {isExpanded ? 'Hide Flow' : 'Show Flow'}
                                </button>
                              </div>
                            </CardHeader>
                            {isExpanded && queryData.agentFlow && hasFlowContent(queryData.agentFlow) && (
                              <CardContent className="pt-4">
                                <AgentFlow flow={queryData.agentFlow} />
                              </CardContent>
                            )}
                          </Card>
                        </motion.div>
                      )
                    })}
                  </AnimatePresence>
                </div>
              )}
                </>
              )}
              
              {activeTab === 'memories' && (
                <MemoriesTab userId={userId} />
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

