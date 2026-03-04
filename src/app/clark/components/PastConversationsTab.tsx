"use client"

import React, { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { MessageSquare, Loader2, RefreshCw } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
  messages: ChatMessage[]
}

export default function PastConversationsTab({ userId, onLoadConversation }: PastConversationsTabProps) {
  const [conversations, setConversations] = useState<ConversationListItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

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

      items.push({
        id: String(conv.id ?? `${sessionId || 'conv'}_${index}`),
        sessionId,
        preview,
        messages,
      })
    })

    return items
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
        {/* <button
          onClick={fetchConversations}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2 bg-teal-900/40 hover:bg-teal-800/50 backdrop-blur-sm border border-teal-700/30 text-white rounded-xl transition-colors disabled:opacity-50"
        >
          {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          Refresh
        </button> */}
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
        <div className="space-y-2">
          {conversations.map((conv, index) => (
            <motion.div
              key={conv.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.02 }}
            >
              <button
                type="button"
                onClick={() => {
                  if (!onLoadConversation) return
                  const safeSessionId =
                    conv.sessionId || `session_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`
                  onLoadConversation(safeSessionId, conv.messages)
                }}
                className="w-full text-left"
              >
                <Card className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/10 hover:border-white/25 backdrop-blur-xl shadow-[0_8px_24px_rgba(0,0,0,0.4)] transition-colors">
                  <CardHeader className="py-3">
                    <div className="flex items-center gap-2">
                      <MessageSquare className="h-4 w-4 text-teal-400 flex-shrink-0" />
                      <CardTitle className="text-sm text-white truncate">
                        {conv.preview.length > 80 ? `${conv.preview.slice(0, 80)}…` : conv.preview}
                      </CardTitle>
                    </div>
                  </CardHeader>
                </Card>
              </button>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}

