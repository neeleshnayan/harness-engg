"use client"

import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Brain, Clock, MessageSquare, Database, Loader2, RefreshCw } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import agentsApi from '@/lib/agents_api'

interface Memory {
  id?: string
  message?: string
  metadata?: {
    type?: string
    session_id?: string
    interaction?: {
      user_query?: string
      final_response?: {
        message?: string
        success?: boolean
      }
    }
    portfolio_data?: {
      type?: string
      query?: string
      metrics?: {
        total_return?: number
        sharpe_ratio?: number
        max_drawdown?: number
      }
    }
    timestamp?: string
  }
  created_at?: string
}

interface MemoriesTabProps {
  userId?: string
}

export default function MemoriesTab({ userId }: MemoriesTabProps) {
  const [condensedMemories, setCondensedMemories] = useState<Memory[]>([])
  const [currentSessionMemories, setCurrentSessionMemories] = useState<Memory[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchMemories = async () => {
    if (!userId) {
      setError("User ID is required to fetch memories")
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const response = await agentsApi.get('/api/v1/agents/memories', {
        params: { user_id: userId }
      })

      if (response.data.success) {
        setCondensedMemories(response.data.condensed_memories || [])
        setCurrentSessionMemories(response.data.current_session_memories || [])
        setCurrentSessionId(response.data.current_session_id || null)
      } else {
        setError(response.data.message || "Failed to fetch memories")
      }
    } catch (err: any) {
      console.error('Error fetching memories:', err)
      setError(err.response?.data?.message || err.message || "Failed to fetch memories")
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (userId) {
      fetchMemories()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId])

  const formatTimestamp = (timestamp?: string) => {
    if (!timestamp) return "Unknown date"
    try {
      const date = new Date(timestamp)
      return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    } catch {
      return timestamp
    }
  }

  const renderMemory = (memory: Memory, index: number) => {
    const metadata = memory.metadata || {}
    const memoryType = metadata.type || 'unknown'
    const sessionId = metadata.session_id

    return (
      <motion.div
        key={memory.id || index}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: index * 0.05 }}
      >
        <Card className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/15 backdrop-blur-xl shadow-[0_8px_24px_rgba(0,0,0,0.4)]">
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  {memoryType === 'user_interaction' && (
                    <MessageSquare className="h-4 w-4 text-blue-400" />
                  )}
                  {memoryType === 'portfolio_state' && (
                    <Database className="h-4 w-4 text-purple-400" />
                  )}
                  <CardTitle className="text-sm text-white capitalize">
                    {memoryType.replace('_', ' ')}
                  </CardTitle>
                </div>
                {sessionId && (
                  <CardDescription className="text-xs text-white/50">
                    Session: {sessionId.substring(0, 20)}...
                  </CardDescription>
                )}
              </div>
              <div className="text-xs text-white/50 flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {formatTimestamp(metadata.timestamp || memory.created_at)}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {memoryType === 'user_interaction' && (
              <div className="space-y-3">
                {metadata.interaction?.user_query && (
                  <div>
                    <div className="text-xs text-white/60 mb-1">User Query:</div>
                    <div className="text-sm text-white bg-white/5 p-2 rounded border border-white/10">
                      {metadata.interaction.user_query}
                    </div>
                  </div>
                )}
                {metadata.interaction?.final_response?.message && (
                  <div>
                    <div className="text-xs text-white/60 mb-1">Assistant Response:</div>
                    <div className="text-sm text-white/80 bg-white/5 p-2 rounded border border-white/10">
                      {metadata.interaction.final_response.message}
                    </div>
                  </div>
                )}
              </div>
            )}
            
            {memoryType === 'portfolio_state' && metadata.portfolio_data && (
              <div className="space-y-3">
                {metadata.portfolio_data.query && (
                  <div>
                    <div className="text-xs text-white/60 mb-1">Query:</div>
                    <div className="text-sm text-white bg-white/5 p-2 rounded border border-white/10">
                      {metadata.portfolio_data.query}
                    </div>
                  </div>
                )}
                {metadata.portfolio_data.metrics && (
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {metadata.portfolio_data.metrics.total_return !== undefined && (
                      <div className="bg-white/5 p-2 rounded border border-white/10">
                        <div className="text-white/60">Total Return</div>
                        <div className={`text-sm font-medium ${
                          metadata.portfolio_data.metrics.total_return >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}>
                          {metadata.portfolio_data.metrics.total_return >= 0 ? '+' : ''}
                          {metadata.portfolio_data.metrics.total_return.toFixed(2)}%
                        </div>
                      </div>
                    )}
                    {metadata.portfolio_data.metrics.sharpe_ratio !== undefined && (
                      <div className="bg-white/5 p-2 rounded border border-white/10">
                        <div className="text-white/60">Sharpe Ratio</div>
                        <div className="text-sm font-medium text-white">
                          {metadata.portfolio_data.metrics.sharpe_ratio.toFixed(2)}
                        </div>
                      </div>
                    )}
                    {metadata.portfolio_data.metrics.max_drawdown !== undefined && (
                      <div className="bg-white/5 p-2 rounded border border-white/10">
                        <div className="text-white/60">Max Drawdown</div>
                        <div className="text-sm font-medium text-red-400">
                          {metadata.portfolio_data.metrics.max_drawdown.toFixed(2)}%
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {memory.message && memoryType !== 'user_interaction' && memoryType !== 'portfolio_state' && (
              <div className="text-sm text-white/80 bg-white/5 p-2 rounded border border-white/10">
                {memory.message}
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>
    )
  }

  if (!userId) {
    return (
      <Card className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/15 backdrop-blur-xl shadow-[0_8px_24px_rgba(0,0,0,0.4)]">
        <CardContent className="p-8 text-center">
          <p className="text-white/60">
            User ID is required to view memories.
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header with refresh button */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Brain className="h-5 w-5 text-teal-400" />
            Memories
          </h2>
          <p className="text-sm text-white/60 mt-1">
            View condensed memories across sessions and current session memories
          </p>
        </div>
        <button
          onClick={fetchMemories}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2 bg-teal-900/40 hover:bg-teal-800/50 backdrop-blur-sm border border-teal-700/30 text-white rounded-xl transition-colors disabled:opacity-50"
        >
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          Refresh
        </button>
      </div>

      {error && (
        <Card className="bg-red-900/20 border-red-700/30 backdrop-blur-xl">
          <CardContent className="p-4">
            <p className="text-red-300 text-sm">{error}</p>
          </CardContent>
        </Card>
      )}

      {isLoading && (
        <Card className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/15 backdrop-blur-xl">
          <CardContent className="p-8 text-center">
            <Loader2 className="h-8 w-8 text-teal-400 animate-spin mx-auto mb-4" />
            <p className="text-white/60">Loading memories...</p>
          </CardContent>
        </Card>
      )}

      {!isLoading && !error && (
        <>
          {/* Current Session Memories */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <MessageSquare className="h-5 w-5 text-cyan-400" />
              <h3 className="text-lg font-semibold text-white">
                Current Session Memories
              </h3>
              <span className="px-2 py-1 bg-cyan-900/40 text-cyan-300 text-xs rounded-xl border border-cyan-700/30">
                {currentSessionMemories.length}
              </span>
            </div>
            {currentSessionId && (
              <p className="text-xs text-white/50 mb-4">
                Session ID: {currentSessionId}
              </p>
            )}
            {currentSessionMemories.length === 0 ? (
              <Card className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/15 backdrop-blur-xl">
                <CardContent className="p-8 text-center">
                  <p className="text-white/60">
                    No memories found for the current session.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-4">
                {currentSessionMemories.map((memory, index) => renderMemory(memory, index))}
              </div>
            )}
          </div>

          {/* Condensed Memories (All Sessions) */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <Database className="h-5 w-5 text-purple-400" />
              <h3 className="text-lg font-semibold text-white">
                Condensed Memories (All Sessions)
              </h3>
              <span className="px-2 py-1 bg-purple-900/40 text-purple-300 text-xs rounded-xl border border-purple-700/30">
                {condensedMemories.length}
              </span>
            </div>
            {condensedMemories.length === 0 ? (
              <Card className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/15 backdrop-blur-xl">
                <CardContent className="p-8 text-center">
                  <p className="text-white/60">
                    No condensed memories found.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-4">
                {condensedMemories.map((memory, index) => renderMemory(memory, index))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

