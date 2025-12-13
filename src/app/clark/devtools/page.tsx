"use client"

import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowLeft, Clock, Zap, TrendingUp, Activity, BarChart3, Filter } from 'lucide-react'
import { ChatMessage, AgentFlowGraph, AgentFlowStep } from '../types'
import AgentFlow from '../components/AgentFlow'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'

export default function DevtoolsPage() {
  const router = useRouter()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [selectedQueryIndex, setSelectedQueryIndex] = useState<number | null>(null)
  const [filterType, setFilterType] = useState<'all' | 'single' | 'sequential' | 'parallel'>('all')

  useEffect(() => {
    // Load messages from localStorage
    try {
      const storedMessages = localStorage.getItem('clark_messages')
      if (storedMessages) {
        const parsedMessages = JSON.parse(storedMessages).map((msg: any) => ({
          ...msg,
          timestamp: new Date(msg.timestamp) // Convert string back to Date
        })) as ChatMessage[]
        setMessages(parsedMessages)
      }
    } catch (error) {
      console.error('Error loading messages:', error)
    }
  }, [])

  // Get all queries (user messages) with their corresponding agent flows
  const queriesWithFlows = messages
    .map((message, index) => {
      if (message.type === 'user') {
        // Find the next assistant message that has an agent flow
        const nextAssistant = messages.slice(index + 1).find(m => 
          m.type === 'assistant' && m.agentFlow
        )
        return {
          query: message.content,
          timestamp: message.timestamp,
          messageIndex: index,
          agentFlow: nextAssistant?.agentFlow
        }
      }
      return null
    })
    .filter((item): item is NonNullable<typeof item> => item !== null && item.agentFlow !== undefined)
    .reverse() // Reverse to show latest queries first

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
    <div className="min-h-screen w-full bg-gradient-to-br from-black via-zinc-900 to-neutral-900 overflow-x-hidden">
      {/* Navbar */}
      <header className="fixed top-0 left-0 right-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-2 min-h-[4rem]">
            <div className="flex items-center gap-4">
              <button
                onClick={() => router.push('/clark')}
                className="flex items-center gap-2 text-white hover:text-zinc-300 transition-colors"
              >
                <ArrowLeft className="h-4 w-4" />
                <span>Back to Clark</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Spacer for fixed navbar height */}
      <div className="h-24" />

      {/* Main Content */}
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-white mb-2">Agent Flow</h1>
          
          {/* Statistics Cards */}
          {queriesWithFlows.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
              >
                <Card className="bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-xs text-zinc-400 mb-1">Total Queries</p>
                        <p className="text-2xl font-bold text-white">{stats.totalQueries}</p>
                      </div>
                      <Activity className="h-8 w-8 text-blue-400" />
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
              
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
              >
                <Card className="bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-xs text-zinc-400 mb-1">Total Latency</p>
                        <p className="text-2xl font-bold text-white">
                          {stats.avgLatency < 1000 
                            ? `${stats.avgLatency.toFixed(0)}ms` 
                            : `${(stats.avgLatency / 1000).toFixed(2)}s`}
                        </p>
                      </div>
                      <Zap className="h-8 w-8 text-yellow-400" />
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
              
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
              >
                <Card className="bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-xs text-zinc-400 mb-1">Parallel Flows</p>
                        <p className="text-2xl font-bold text-white">{stats.flowTypeCounts.parallel}</p>
                      </div>
                      <BarChart3 className="h-8 w-8 text-purple-400" />
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
              
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
              >
                <Card className="bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-xs text-zinc-400 mb-1">Sequential Flows</p>
                        <p className="text-2xl font-bold text-white">{stats.flowTypeCounts.sequential}</p>
                      </div>
                      <TrendingUp className="h-8 w-8 text-green-400" />
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            </div>
          )}

          {/* Filter Buttons */}
          {queriesWithFlows.length > 0 && (
            <div className="flex items-center gap-2 mb-4">
              <Filter className="h-4 w-4 text-zinc-400" />
              <span className="text-sm text-zinc-400">Filter:</span>
              {(['all', 'single', 'sequential', 'parallel'] as const).map((type) => (
                <button
                  key={type}
                  onClick={() => setFilterType(type)}
                  className={`px-3 py-1 rounded-lg text-sm transition-colors ${
                    filterType === type
                      ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                      : 'bg-zinc-700/50 text-zinc-400 hover:bg-zinc-700/70'
                  }`}
                >
                  {type.charAt(0).toUpperCase() + type.slice(1)}
                </button>
              ))}
            </div>
          )}
        </div>

        {queriesWithFlows.length === 0 ? (
          <Card className="bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm">
            <CardContent className="p-8 text-center">
              <p className="text-zinc-400">
                No agent flow data available. Send some queries in the main Clark interface to see flow graphs here.
              </p>
            </CardContent>
          </Card>
        ) : filteredQueries.length === 0 ? (
          <Card className="bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm">
            <CardContent className="p-8 text-center">
              <p className="text-zinc-400">
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
                    className="bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm hover:border-zinc-600/50 transition-colors"
                  >
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <CardTitle className="text-lg text-white">
                            Query #{originalIndex + 1}
                          </CardTitle>
                          {flowType !== 'single' && (
                            <span className="px-2 py-1 bg-purple-500/20 text-purple-300 text-xs rounded border border-purple-500/30">
                              {flowType === 'parallel' ? 'Parallel' : 'Sequential'}
                            </span>
                          )}
                        </div>
                        <CardDescription className="text-zinc-300 mb-3">
                          {queryData.query}
                        </CardDescription>
                        <div className="flex items-center gap-4 flex-wrap">
                          <div className="text-xs text-zinc-500 flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {queryData.timestamp.toLocaleString()}
                          </div>
                          {agentCount > 0 && (
                            <div className="text-xs text-zinc-400 flex items-center gap-1">
                              <TrendingUp className="h-3 w-3" />
                              {agentCount} agent{agentCount !== 1 ? 's' : ''}
                            </div>
                          )}
                          {totalLatency !== null && (
                            <div className="text-xs text-yellow-400 flex items-center gap-1">
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
                        className="ml-4 px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg transition-colors text-sm"
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
      </div>
    </div>
  )
}
