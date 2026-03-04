"use client"

import React, { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { MessageSquare, Clock, Loader2, RefreshCw } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import agentsApi from '@/lib/agents_api'
import type { ChatMessage } from '../types'

interface PastConversationsTabProps {
  userId?: string
  onLoadConversation?: (sessionId: string, messages: ChatMessage[]) => void
}

interface ConversationListItem {
  id: string
  sessionId: string
  preview: string
  timestamp: string
  messageCount: number
  messages: ChatMessage[]
}

export default function PastConversationsTab({ userId, onLoadConversation }: PastConversationsTabProps) {
  const [conversations, setConversations] = useState<ConversationListItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const formatTimestamp = (timestamp?: string) => {
    if (!timestamp) return 'Unknown date'
    try {
      const date = new Date(timestamp)
      return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return timestamp
    }
  }

  const mapApiConversations = (rawConversations: any[]): ConversationListItem[] => {
    const items: ConversationListItem[] = []

    rawConversations.forEach((conv, index) => {
      if (!conv) return
      const sessionId: string = conv.session_id || ''
      const messagesRaw: any[] = Array.isArray(conv.messages) ? conv.messages : []

      const messages: ChatMessage[] = messagesRaw.map((msg) => ({
        id: String(msg?.id ?? ''),
        type: msg?.type === 'assistant' ? 'assistant' : 'user',
        content: msg?.content ?? '',
        timestamp: msg?.timestamp ? new Date(msg.timestamp) : new Date(),
      }))

      if (messages.length === 0) {
        return
      }

      const firstUserMessage = messages.find((m) => m.type === 'user')
      const preview = firstUserMessage?.content || messages[0].content || 'Conversation'
      const timestamp: string = conv.updated_at || conv.created_at || messages[messages.length - 1].timestamp.toISOString()

      items.push({
        id: String(conv.id ?? `${sessionId || 'conv'}_${index}`),
        sessionId,
        preview,
        timestamp,
        messageCount: messages.length,
        messages,
      })
    })

    return items.sort((a, b) => {
      const ta = new Date(a.timestamp).getTime()
      const tb = new Date(b.timestamp).getTime()
      return tb - ta
    })
  }

  const fetchConversations = async () => {
    if (!userId) {
      setError('User ID is required to fetch conversations')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const response = await agentsApi.get('/api/v1/agents/conversations', {
        params: { user_id: userId, limit: 20 },
      })

      if (response.data?.success) {
        const raw = Array.isArray(response.data.conversations) ? response.data.conversations : []
        setConversations(mapApiConversations(raw))
      } else {
        setError(response.data?.message || 'Failed to fetch conversations')
      }
    } catch (err: any) {
      console.error('Error fetching conversations:', err)
      setError(err.response?.data?.message || err.message || 'Failed to fetch conversations')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (userId) {
      fetchConversations()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId])

  if (!userId) {
    return (
      <Card className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/15 backdrop-blur-xl shadow-[0_8px_24px_rgba(0,0,0,0.4)]">
        <CardContent className="p-8 text-center">
          <p className="text-white/60">User ID is required to view past conversations.</p>
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
            <MessageSquare className="h-5 w-5 text-teal-400" />
            Past Conversations
          </h2>
          <p className="text-sm text-white/60 mt-1">Browse and continue your previous Clark chats.</p>
        </div>
        <button
          onClick={fetchConversations}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2 bg-teal-900/40 hover:bg-teal-800/50 backdrop-blur-sm border border-teal-700/30 text-white rounded-xl transition-colors disabled:opacity-50"
        >
          {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
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

      {isLoading && !conversations.length && (
        <Card className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/15 backdrop-blur-xl">
          <CardContent className="p-8 text-center">
            <Loader2 className="h-8 w-8 text-teal-400 animate-spin mx-auto mb-4" />
            <p className="text-white/60">Loading conversations...</p>
          </CardContent>
        </Card>
      )}

      {!isLoading && !error && conversations.length === 0 && (
        <Card className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/15 backdrop-blur-xl">
          <CardContent className="p-8 text-center">
            <p className="text-white/60">No past conversations found yet. Start chatting with Clark to build history.</p>
          </CardContent>
        </Card>
      )}

      {!isLoading && conversations.length > 0 && (
        <div className="space-y-4">
          {conversations.map((conv, index) => (
            <motion.div
              key={conv.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.03 }}
            >
              <Card className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/15 backdrop-blur-xl shadow-[0_8px_24px_rgba(0,0,0,0.4)]">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1.5">
                        <MessageSquare className="h-4 w-4 text-teal-400" />
                        <CardTitle className="text-sm text-white truncate">
                          {conv.preview.length > 80 ? `${conv.preview.slice(0, 80)}…` : conv.preview}
                        </CardTitle>
                      </div>
                      <CardDescription className="text-xs text-white/50">
                        {conv.messageCount} message{conv.messageCount !== 1 ? 's' : ''}{' '}
                        {conv.sessionId && (
                          <span className="ml-1 font-mono text-[10px] text-white/40">
                            · {conv.sessionId.substring(0, 18)}…
                          </span>
                        )}
                      </CardDescription>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      <div className="text-xs text-white/50 flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {formatTimestamp(conv.timestamp)}
                      </div>
                      {onLoadConversation && (
                        <button
                          type="button"
                          onClick={() => {
                            const safeSessionId =
                              conv.sessionId || `session_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`
                            onLoadConversation(safeSessionId, conv.messages)
                          }}
                          className="px-3 py-1.5 rounded-lg bg-white/15 hover:bg-white/25 text-xs font-medium text-white transition-colors border border-white/20"
                        >
                          Continue
                        </button>
                      )}
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="text-xs text-white/60">
                    Last message:{' '}
                    <span className="text-white/85">
                      {conv.messages[conv.messages.length - 1]?.content.length > 120
                        ? `${conv.messages[conv.messages.length - 1].content.slice(0, 120)}…`
                        : conv.messages[conv.messages.length - 1]?.content}
                    </span>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}

