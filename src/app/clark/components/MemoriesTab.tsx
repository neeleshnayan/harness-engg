"use client"

import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Brain, Clock, MessageSquare, Database, Loader2, RefreshCw, User } from 'lucide-react'
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
    persona_summary?: {
      interests?: string[]
      preferences?: string
      behavior_patterns?: string
      knowledge_level?: string
      goals?: string[]
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
  const [recentMemories, setRecentMemories] = useState<Memory[]>([])
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
        const condensed = response.data.condensed_memories || []
        const recent = response.data.recent_memories || []
        
        console.log('Fetched memories:', { 
          condensed_count: condensed.length, 
          recent_count: recent.length,
          condensed: condensed,
          recent: recent
        })
        setCondensedMemories(condensed)
        setRecentMemories(recent)
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
    
    // Handle reasoningContent structure (fallback for prod data)
    let displayMessage: string | undefined = memory.message
    if (!displayMessage && (memory as any).reasoningContent) {
      const reasoning = (memory as any).reasoningContent
      if (reasoning?.reasoningText?.text) {
        displayMessage = reasoning.reasoningText.text
        // Try to extract JSON from the text if it's a JSON string
        if (displayMessage) {
          try {
            const parsed = JSON.parse(displayMessage)
            if (parsed.message) {
              displayMessage = parsed.message
              // Merge parsed metadata if available
              if (parsed.metadata) {
                Object.assign(metadata, parsed.metadata)
              }
            }
          } catch {
            // Not JSON, use as-is
          }
        }
      }
    }

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
                  {(memoryType === 'condensed_persona' || memoryType === 'persona_memory') && (
                    <User className="h-4 w-4 text-teal-400" />
                  )}
                  <CardTitle className="text-sm text-white capitalize">
                    {memoryType === 'condensed_persona' ? 'Condensed Persona' : memoryType === 'persona_memory' ? 'Persona Memory' : memoryType.replace('_', ' ')}
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

            {(memoryType === 'condensed_persona' || memoryType === 'persona_memory') && displayMessage && (
              <div className="space-y-3">
                <div>
                  <div className="text-xs text-white/60 mb-1">Persona Summary:</div>
                  <div className="text-sm text-white/90 bg-white/5 p-3 rounded border border-white/10 leading-relaxed">
                    {displayMessage}
                  </div>
                </div>
                {metadata.persona_summary && (
                  <div className="grid grid-cols-1 gap-2 text-xs">
                    {metadata.persona_summary.interests && Array.isArray(metadata.persona_summary.interests) && metadata.persona_summary.interests.length > 0 && (
                      <div className="bg-white/5 p-2 rounded border border-white/10">
                        <div className="text-white/60 mb-1">Interests:</div>
                        <div className="text-white/80 flex flex-wrap gap-1">
                          {metadata.persona_summary.interests.map((interest: string, idx: number) => (
                            <span key={idx} className="px-2 py-0.5 bg-teal-900/30 text-teal-300 rounded text-xs">
                              {interest}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {metadata.persona_summary.preferences && (
                      <div className="bg-white/5 p-2 rounded border border-white/10">
                        <div className="text-white/60 mb-1">Preferences:</div>
                        <div className="text-white/80">{metadata.persona_summary.preferences}</div>
                      </div>
                    )}
                    {metadata.persona_summary.knowledge_level && (
                      <div className="bg-white/5 p-2 rounded border border-white/10">
                        <div className="text-white/60 mb-1">Knowledge Level:</div>
                        <div className="text-white/80">{metadata.persona_summary.knowledge_level}</div>
                      </div>
                    )}
                    {metadata.persona_summary.goals && Array.isArray(metadata.persona_summary.goals) && metadata.persona_summary.goals.length > 0 && (
                      <div className="bg-white/5 p-2 rounded border border-white/10">
                        <div className="text-white/60 mb-1">Goals:</div>
                        <div className="text-white/80 flex flex-wrap gap-1">
                          {metadata.persona_summary.goals.map((goal: string, idx: number) => (
                            <span key={idx} className="px-2 py-0.5 bg-cyan-900/30 text-cyan-300 rounded text-xs">
                              {goal}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
            
            {displayMessage && memoryType !== 'user_interaction' && memoryType !== 'portfolio_state' && memoryType !== 'condensed_persona' && memoryType !== 'persona_memory' && (
              <div className="text-sm text-white/80 bg-white/5 p-2 rounded border border-white/10">
                {displayMessage}
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
            Explore memories
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
          {/* Recent Memories (Last 10) */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <Brain className="h-5 w-5 text-teal-400" />
              <h3 className="text-lg font-semibold text-white">
                Recent Memories (Last 10)
              </h3>
              <span className="px-2 py-1 bg-teal-900/40 text-teal-300 text-xs rounded-xl border border-teal-700/30">
                {recentMemories.length}
              </span>
            </div>
            {recentMemories.length === 0 ? (
              <Card className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/15 backdrop-blur-xl">
                <CardContent className="p-8 text-center">
                  <p className="text-white/60">
                    No recent memories found.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-4">
                {recentMemories.map((memory, index) => renderMemory(memory, index))}
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

