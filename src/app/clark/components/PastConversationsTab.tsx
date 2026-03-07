"use client"

import React, { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { MessageSquare, Loader2, RefreshCw } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import agentsApi from '@/lib/agents_api'
import type { ChatMessage } from '../types'

interface PastConversationsTabProps {
  userId?: string
  onLoadConversation?: (
    sessionId: string,
    messages: ChatMessage[],
    sessionCondensedMemory?: unknown[],
    sessionCondensedSummary?: string
  ) => void
}

interface ConversationListItem {
  id: string
  sessionId: string
  preview: string
  messages: ChatMessage[]
  sessionCondensedMemory?: unknown[]
  sessionCondensedSummary?: string
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
      const sessionCondensedMemory: unknown[] = Array.isArray(conv.session_condensed_memory)
        ? conv.session_condensed_memory
        : []
      const sessionCondensedSummary: string | undefined =
        typeof conv.session_condensed_summary === 'string' ? conv.session_condensed_summary : undefined

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
        sessionCondensedMemory,
        sessionCondensedSummary,
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
    <div className="space-y-5">
      {/* Header with icon and title */}
      <div className="flex items-center justify-between px-2">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-3.5 w-3.5 text-teal-400" />
          <h2 className="text-[11px] font-bold text-white/50 uppercase tracking-[0.15em]">History</h2>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-xl bg-red-900/20 border border-red-700/30 backdrop-blur-xl">
          <p className="text-red-300 text-xs">{error}</p>
        </div>
      )}

      {isLoading && !conversations.length && (
        <div className="p-8 text-center">
          <Loader2 className="h-6 w-6 text-teal-400 animate-spin mx-auto mb-3" />
          <p className="text-white/50 text-xs">Loading...</p>
        </div>
      )}

      {!isLoading && !error && conversations.length === 0 && (
        <div className="p-8 text-center rounded-xl bg-white/5 border border-white/5">
          <p className="text-white/40 text-xs leading-relaxed">No past conversations found.</p>
        </div>
      )}

      {!isLoading && conversations.length > 0 && (
        <div className="space-y-0.5">
          {conversations.map((conv, index) => (
            <motion.div
              key={conv.id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.01 }}
            >
              <button
                type="button"
                onClick={() => {
                  if (!onLoadConversation) return
                  const safeSessionId =
                    conv.sessionId || `session_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`
                  onLoadConversation(
                    safeSessionId,
                    conv.messages,
                    conv.sessionCondensedMemory,
                    conv.sessionCondensedSummary
                  )
                }}
                className="w-full text-left group px-2"
              >
                <div className="px-3 py-2 rounded-xl border border-transparent hover:bg-white/[0.04] active:bg-white/[0.06] transition-all duration-200">
                  <div className="flex items-start gap-3">
                    <span className="text-[13px] text-white/60 group-hover:text-white/90 leading-snug line-clamp-2 transition-colors">
                      {conv.preview}
                    </span>
                  </div>
                </div>
              </button>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}

