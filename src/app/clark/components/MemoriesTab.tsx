"use client"

import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Brain, Clock, MessageSquare, Database, Loader2, RefreshCw, User } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import agentsApi from '@/lib/agents_api'
import type { ChatMessage } from '../types'
import { stripReasoningFromMessage } from '../utils/createAssistantMessage'

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
    categories?: {
      personal_profile?: {
        summary?: string
        traits?: string[]
      }
      financial_preferences?: {
        summary?: string
        preferred_assets?: string[]
        risk_tolerance?: string
      }
      agent_experience?: {
        summary?: string
        agent_patterns?: string[]
      }
      knowledge_base?: {
        extracted_facts?: string[]
        significant_results?: string[]
      }
    }
    timestamp?: string
  }
  created_at?: string
}

interface MemoriesTabProps {
  userId?: string
  sessionId?: string
  messages?: ChatMessage[]
}

interface KnowledgeBaseEntry {
  type: 'fact' | 'result'
  content: string
  timestamp: string
}

export default function MemoriesTab({ userId, sessionId, messages = [] }: MemoriesTabProps) {
  const [condensedMemories, setCondensedMemories] = useState<Memory[]>([])
  const [recentMemories, setRecentMemories] = useState<Memory[]>([])
  const [transientKB, setTransientKB] = useState<KnowledgeBaseEntry[]>([])
  const [persistentKB, setPersistentKB] = useState<KnowledgeBaseEntry[]>([])
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
      const params: { user_id: string; session_id?: string } = { user_id: userId }
      if (sessionId) {
        params.session_id = sessionId
      }
      const response = await agentsApi.get('/api/v1/agents/memories', {
        params
      })

      if (response.data.success) {
        const condensed = response.data.condensed_memories || []
        const transient = response.data.transient_knowledge_base || []
        const persistent = response.data.persistent_knowledge_base || []
        
        // Ensure we have arrays (defensive)
        setCondensedMemories(Array.isArray(condensed) ? condensed : [])
        setTransientKB(Array.isArray(transient) ? transient : [])
        setPersistentKB(Array.isArray(persistent) ? persistent : [])
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

  // Build current session memories purely from UI chat messages (not persisted anywhere)
  useEffect(() => {
    if (!messages || messages.length === 0) {
      setRecentMemories([])
      return
    }

    const uiMemories: Memory[] = []

    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i]
      if (msg.type !== 'user') continue

      const next = messages[i + 1]
      const assistant = next && next.type === 'assistant' ? next : undefined

      const timestampIso = msg.timestamp instanceof Date ? msg.timestamp.toISOString() : new Date(msg.timestamp).toISOString()

      uiMemories.push({
        id: msg.id,
        message: `User: ${msg.content}${assistant ? ` | Assistant: ${assistant.content}` : ''}`,
        metadata: {
          type: 'user_interaction',
          session_id: sessionId,
          interaction: {
            user_query: msg.content,
            final_response: assistant
              ? {
                  message: assistant.content,
                  success: assistant.success,
                }
              : undefined,
          },
          timestamp: timestampIso,
        },
        created_at: timestampIso,
      })
    }

    setRecentMemories(uiMemories)
  }, [messages, sessionId])

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

    // Extract display message from memory object
    // Priority: message field (string) > text field > reasoningContent
    let displayMessage: string | undefined = undefined
    
    // First, try the message field
    if (memory.message) {
      if (typeof memory.message === 'string') {
        // If message is a JSON string, try to parse it
        if (memory.message.trim().startsWith('{')) {
          try {
            const parsed = JSON.parse(memory.message)
            if (parsed.message && typeof parsed.message === 'string') {
              displayMessage = parsed.message
              // Merge parsed metadata if available
              if (parsed.metadata && typeof parsed.metadata === 'object') {
                Object.assign(metadata, parsed.metadata)
              }
            } else {
              // If parsed JSON doesn't have a message field, use the original string
              displayMessage = memory.message
            }
          } catch {
            // Not valid JSON, use as-is
            displayMessage = memory.message
          }
        } else {
          // Plain string, use directly
          displayMessage = memory.message
        }
      } else {
        // message is not a string, convert to string safely
        displayMessage = String(memory.message)
      }
    }
    
    // Also check for text field (some Firebase structures use this)
    if (!displayMessage && (memory as any).text) {
      const textField = (memory as any).text
      if (typeof textField === 'string') {
        if (textField.trim().startsWith('{')) {
          try {
            const parsed = JSON.parse(textField)
            if (parsed.message && typeof parsed.message === 'string') {
              displayMessage = parsed.message
              if (parsed.metadata && typeof parsed.metadata === 'object') {
                Object.assign(metadata, parsed.metadata)
              }
            } else {
              displayMessage = textField
            }
          } catch {
            displayMessage = textField
          }
        } else {
          displayMessage = textField
        }
      }
    }
    
    // Fallback to reasoningContent structure (strip any nested reasoning before showing)
    if (!displayMessage && (memory as any).reasoningContent) {
      const reasoning = (memory as any).reasoningContent
      if (reasoning?.reasoningText?.text) {
        const reasoningText = reasoning.reasoningText.text
        if (typeof reasoningText === 'string') {
          let raw = ''
          if (reasoningText.trim().startsWith('{')) {
            try {
              const parsed = JSON.parse(reasoningText)
              if (parsed.message && typeof parsed.message === 'string') {
                raw = parsed.message
                if (parsed.metadata && typeof parsed.metadata === 'object') {
                  Object.assign(metadata, parsed.metadata)
                }
              } else {
                raw = reasoningText
              }
            } catch {
              raw = reasoningText
            }
          } else {
            raw = reasoningText
          }
          displayMessage = stripReasoningFromMessage(raw)
        }
      }
    }
    
    // Final safety: ensure displayMessage is a string, never an object
    if (displayMessage && typeof displayMessage !== 'string') {
      console.warn('displayMessage is not a string, converting:', typeof displayMessage)
      try {
        displayMessage = JSON.stringify(displayMessage)
      } catch {
        displayMessage = String(displayMessage)
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
                        <div className={`text-sm font-medium ${metadata.portfolio_data.metrics.total_return >= 0 ? 'text-green-400' : 'text-red-400'
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

            {(memoryType === 'condensed_persona' || memoryType === 'persona_memory') && (
              <div className="space-y-3">
                {displayMessage ? (
                  <div>
                    <div className="text-xs text-white/60 mb-1">Persona Summary:</div>
                    <div className="text-sm text-white/90 bg-white/5 p-3 rounded border border-white/10 leading-relaxed">
                      {displayMessage}
                    </div>
                  </div>
                ) : (
                  <div className="text-xs text-white/60 bg-white/5 p-3 rounded border border-white/10">
                    No persona summary available.
                  </div>
                )}
                {metadata.categories && (
                  <div className="space-y-3 mt-4">
                    {metadata.categories.personal_profile && (
                      <div className="bg-white/5 p-3 rounded border border-white/10">
                        <div className="text-xs text-teal-400 font-semibold mb-1 uppercase tracking-wider">Personal Profile</div>
                        <div className="text-sm text-white/80 mb-2">{metadata.categories.personal_profile.summary}</div>
                        {metadata.categories.personal_profile.traits && metadata.categories.personal_profile.traits.length > 0 && (
                          <div className="flex flex-wrap gap-1">
                            {metadata.categories.personal_profile.traits.map((trait, idx) => (
                              <span key={idx} className="px-2 py-0.5 bg-teal-900/30 text-teal-300 rounded text-[10px]">
                                {trait}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {metadata.categories.financial_preferences && (
                      <div className="bg-white/5 p-3 rounded border border-white/10">
                        <div className="text-xs text-cyan-400 font-semibold mb-1 uppercase tracking-wider">Financial Preferences</div>
                        <div className="text-sm text-white/80 mb-2">{metadata.categories.financial_preferences.summary}</div>
                        <div className="flex flex-wrap gap-2 items-center">
                          {metadata.categories.financial_preferences.risk_tolerance && (
                            <span className="text-[10px] text-white/60">
                              Risk: <span className="text-cyan-300">{metadata.categories.financial_preferences.risk_tolerance}</span>
                            </span>
                          )}
                          {metadata.categories.financial_preferences.preferred_assets && metadata.categories.financial_preferences.preferred_assets.length > 0 && (
                            <div className="flex flex-wrap gap-1">
                              {metadata.categories.financial_preferences.preferred_assets.map((asset, idx) => (
                                <span key={idx} className="px-2 py-0.5 bg-cyan-900/30 text-cyan-300 rounded text-[10px]">
                                  {asset}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {metadata.categories.agent_experience && (
                      <div className="bg-white/5 p-3 rounded border border-white/10">
                        <div className="text-xs text-blue-400 font-semibold mb-1 uppercase tracking-wider">Agent Experience</div>
                        <div className="text-sm text-white/80 mb-2">{metadata.categories.agent_experience.summary}</div>
                        {metadata.categories.agent_experience.agent_patterns && metadata.categories.agent_experience.agent_patterns.length > 0 && (
                          <div className="flex flex-wrap gap-1">
                            {metadata.categories.agent_experience.agent_patterns.map((pattern, idx) => (
                              <span key={idx} className="px-2 py-0.5 bg-blue-900/30 text-blue-300 rounded text-[10px]">
                                {pattern}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {metadata.categories.knowledge_base && (
                      <div className="bg-white/5 p-3 rounded border border-white/10">
                        <div className="text-xs text-amber-400 font-semibold mb-1 uppercase tracking-wider">Knowledge Base (Concrete Data)</div>

                        {metadata.categories.knowledge_base.extracted_facts && metadata.categories.knowledge_base.extracted_facts.length > 0 && (
                          <div className="mb-3">
                            <div className="text-[10px] text-white/50 mb-1">Extracted Facts:</div>
                            <div className="flex flex-wrap gap-1">
                              {metadata.categories.knowledge_base.extracted_facts.map((fact, idx) => (
                                <span key={idx} className="px-2 py-0.5 bg-amber-900/30 text-amber-300 rounded text-[10px] border border-amber-700/20">
                                  {fact}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {metadata.categories.knowledge_base.significant_results && metadata.categories.knowledge_base.significant_results.length > 0 && (
                          <div>
                            <div className="text-[10px] text-white/50 mb-1">Significant Results:</div>
                            <div className="flex flex-wrap gap-1">
                              {metadata.categories.knowledge_base.significant_results.map((result, idx) => (
                                <span key={idx} className="px-2 py-0.5 bg-indigo-900/30 text-indigo-300 rounded text-[10px] border border-indigo-700/20">
                                  {result}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {metadata.persona_summary && !metadata.categories && (
                  <div className="grid grid-cols-1 gap-2 text-xs mt-2">
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

            {/* Fallback for other memory types */}
            {displayMessage && memoryType !== 'user_interaction' && memoryType !== 'portfolio_state' && memoryType !== 'condensed_persona' && memoryType !== 'persona_memory' && (
              <div className="text-sm text-white/80 bg-white/5 p-2 rounded border border-white/10">
                {displayMessage}
              </div>
            )}
            
            {/* Safety: Never render raw object as JSON */}
            {!displayMessage && memoryType !== 'user_interaction' && memoryType !== 'portfolio_state' && memoryType !== 'condensed_persona' && memoryType !== 'persona_memory' && (
              <div className="text-xs text-white/60 bg-white/5 p-2 rounded border border-white/10">
                Memory content not available for display.
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
          {/* Current Session Memories */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <Brain className="h-5 w-5 text-teal-400" />
              <h3 className="text-lg font-semibold text-white">
                Current Session Memories
              </h3>
              <span className="px-2 py-1 bg-teal-900/40 text-teal-300 text-xs rounded-xl border border-teal-700/30">
                {recentMemories.length}
              </span>
            </div>
            {recentMemories.length === 0 ? (
              <Card className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/15 backdrop-blur-xl">
                <CardContent className="p-8 text-center">
                  <p className="text-white/60">
                    No current session memories found.
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

          {/* Knowledge Base Sections */}
          <>
            {/* Persistent Knowledge Base */}
            <div>
              <div className="flex items-center gap-2 mb-4">
                <Database className="h-5 w-5 text-indigo-400" />
                <h3 className="text-lg font-semibold text-white">
                  Persistent Knowledge Base (Last 5)
                </h3>
                <span className="px-2 py-1 bg-indigo-900/40 text-indigo-300 text-xs rounded-xl border border-indigo-700/30">
                  {persistentKB.length}
                </span>
              </div>
              {persistentKB.length === 0 ? (
                <Card className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/15 backdrop-blur-xl">
                  <CardContent className="p-8 text-center">
                    <p className="text-white/60">
                      No persistent knowledge base entries found.
                    </p>
                  </CardContent>
                </Card>
              ) : (
                <div className="space-y-2">
                  {persistentKB.map((entry, index) => (
                    <motion.div
                      key={index}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.05 }}
                    >
                      <Card className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/15 backdrop-blur-xl">
                        <CardContent className="p-3">
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                                  entry.type === 'fact' 
                                    ? 'bg-amber-900/40 text-amber-300 border border-amber-700/30' 
                                    : 'bg-indigo-900/40 text-indigo-300 border border-indigo-700/30'
                                }`}>
                                  {entry.type === 'fact' ? 'Fact' : 'Result'}
                                </span>
                                <span className="text-xs text-white/50">
                                  {formatTimestamp(entry.timestamp)}
                                </span>
                              </div>
                              <div className="text-sm text-white/90 mt-1">
                                {entry.content}
                              </div>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    </motion.div>
                  ))}
                </div>
              )}
            </div>

            {/* Transient Knowledge Base */}
            <div>
              <div className="flex items-center gap-2 mb-4">
                <Brain className="h-5 w-5 text-amber-400" />
                <h3 className="text-lg font-semibold text-white">
                  Transient Knowledge Base (Last 5)
                </h3>
                <span className="px-2 py-1 bg-amber-900/40 text-amber-300 text-xs rounded-xl border border-amber-700/30">
                  {transientKB.length}
                </span>
              </div>
              {transientKB.length === 0 ? (
                <Card className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/15 backdrop-blur-xl">
                  <CardContent className="p-8 text-center">
                    <p className="text-white/60">
                      No transient knowledge base entries found.
                    </p>
                  </CardContent>
                </Card>
              ) : (
                <div className="space-y-2">
                  {transientKB.map((entry, index) => (
                    <motion.div
                      key={index}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.05 }}
                    >
                      <Card className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/15 backdrop-blur-xl">
                        <CardContent className="p-3">
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                                  entry.type === 'fact' 
                                    ? 'bg-amber-900/40 text-amber-300 border border-amber-700/30' 
                                    : 'bg-indigo-900/40 text-indigo-300 border border-indigo-700/30'
                                }`}>
                                  {entry.type === 'fact' ? 'Fact' : 'Result'}
                                </span>
                                <span className="text-xs text-white/50">
                                  {formatTimestamp(entry.timestamp)}
                                </span>
                              </div>
                              <div className="text-sm text-white/90 mt-1">
                                {entry.content}
                              </div>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    </motion.div>
                  ))}
                </div>
              )}
            </div>
          </>
        </>
      )}
    </div>
  )
}

