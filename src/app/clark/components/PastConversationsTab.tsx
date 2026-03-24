"use client"

import React, { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { MessageSquare, Loader2, RefreshCw, Trash2, SquarePen, X } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import agentsApi from '@/lib/agents_api'
import type { ChatMessage } from '../types'

export type PastConversationsTabVariant = 'sidebar' | 'embedded' | 'mobileSheet'

interface PastConversationsTabProps {
  userId?: string
  variant?: PastConversationsTabVariant
  /** When variant is mobileSheet, shown as a close control in the header row. */
  onRequestClose?: () => void
  /** Bump to refetch list from API (e.g. after starting a new chat). */
  refreshTrigger?: number
  onLoadConversation?: (
    sessionId: string,
    messages: ChatMessage[],
    sessionCondensedMemory?: unknown[],
    sessionCondensedSummary?: string
  ) => void
  onOpenDevtools?: () => void
  /** Current session shown in the main feed — merged at top of the list when it has messages. */
  activeSessionId?: string
  activeMessages?: ChatMessage[]
  onNewChat?: () => void | Promise<void>
  /** Called when the row for the active session is deleted or after new chat clears it server-side. */
  onActiveSessionDeleted?: () => void
}

interface ConversationListItem {
  id: string
  sessionId: string
  preview: string
  messages: ChatMessage[]
  sessionCondensedMemory?: unknown[]
  sessionCondensedSummary?: string
}

export default function PastConversationsTab({
  userId,
  variant = 'sidebar',
  onRequestClose,
  refreshTrigger = 0,
  onLoadConversation,
  onOpenDevtools,
  activeSessionId,
  activeMessages,
  onNewChat,
  onActiveSessionDeleted,
}: PastConversationsTabProps) {
  const [conversations, setConversations] = useState<ConversationListItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const isEmbedded = variant === 'embedded'
  const isMobileSheet = variant === 'mobileSheet'

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

      const messages: ChatMessage[] = messagesRaw.map((msg) => {
        const timestamp = msg?.timestamp ? new Date(msg.timestamp) : new Date()
        return {
          ...(msg && typeof msg === 'object' ? msg : {}),
          id: String(msg?.id ?? ''),
          type: msg?.type === 'assistant' ? 'assistant' : 'user',
          content: msg?.content ?? '',
          timestamp,
        } as ChatMessage
      })

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
  }, [userId, refreshTrigger])

  const displayConversations = useMemo((): ConversationListItem[] => {
    const sid = activeSessionId?.trim()
    const live = activeMessages ?? []
    const withoutActive = sid
      ? conversations.filter((c) => c.sessionId !== sid)
      : conversations

    if (!sid || live.length === 0) {
      return withoutActive
    }

    const firstUser = live.find((m) => m.type === 'user')
    const preview =
      firstUser?.content?.trim() ||
      live[0]?.content?.trim() ||
      'Current conversation'

    const liveItem: ConversationListItem = {
      id: `live_${sid}`,
      sessionId: sid,
      preview,
      messages: live,
      sessionCondensedMemory: [],
      sessionCondensedSummary: undefined,
    }

    return [liveItem, ...withoutActive]
  }, [conversations, activeSessionId, activeMessages])

  const handleDelete = async (e: React.MouseEvent, conv: ConversationListItem) => {
    e.preventDefault()
    e.stopPropagation()
    if (!userId || !conv.sessionId) return

    const isActive = Boolean(activeSessionId && conv.sessionId === activeSessionId)
    setDeletingId(conv.id)

    try {
      await agentsApi.delete('/api/v1/agents/conversations', {
        params: { user_id: userId, session_id: conv.sessionId },
      })
    } catch (err) {
      console.warn('Delete conversation API:', err)
    }

    if (isActive) {
      onActiveSessionDeleted?.()
    }

    await fetchConversations()
    setDeletingId(null)
  }

  if (!userId) {
    return (
      <Card className="bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 border-white/15 backdrop-blur-xl shadow-[0_8px_24px_rgba(0,0,0,0.4)]">
        <CardContent className="p-8 text-center">
          <p className="text-white/60">User ID is required to view past conversations.</p>
        </CardContent>
      </Card>
    )
  }

  const actionRowClass =
    // "Ghost" style: no filled background/border by default, just subtle hover feedback.
    'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl border border-transparent bg-transparent text-left text-sm text-white/80 hover:bg-white/[0.04] hover:text-white hover:border-white/10 transition-colors'

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2 min-w-0">
        </div>
        
      </div>

      {!isEmbedded && (onNewChat || onOpenDevtools) && (
        <div className="flex flex-col gap-2 px-0">
          {onNewChat && (
            <button
              type="button"
              onClick={() => void onNewChat()}
              className={actionRowClass}
              title="New chat"
              aria-label="New chat"
            >
              <SquarePen className="h-4 w-4 text-teal-400/90 flex-shrink-0" />
              <span className="font-medium">New Chat</span>
            </button>
          )}
          {onOpenDevtools && (
            <button
              type="button"
              onClick={() => onOpenDevtools()}
              className={actionRowClass}
              title="Open devtools"
              aria-label="Open devtools"
            >
              <img src="/devtools.svg" alt="" className="h-4 w-4 opacity-80 flex-shrink-0" />
              <span className="font-medium">Dev Tools</span>
            </button>
          )}
        </div>
      )}

      <div className="flex flex-col gap-2 min-h-0">
        <div className="flex items-center justify-between gap-2 px-2">
          <h3 className="text-[11px] font-bold text-white/50 uppercase tracking-[0.15em]">
            Recents
          </h3>
          <button
            type="button"
            onClick={() => void fetchConversations()}
            disabled={isLoading}
            className="p-1.5 rounded-lg text-white/45 hover:text-teal-300 hover:bg-white/[0.06] transition-colors disabled:opacity-40 flex-shrink-0"
            title="Refresh list"
            aria-label="Refresh conversations"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>

      {error && (
        <div className="p-3 rounded-xl bg-red-900/20 border border-red-700/30 backdrop-blur-xl">
          <p className="text-red-300 text-xs">{error}</p>
        </div>
      )}

      {isLoading && !displayConversations.length && (
        <div className="p-8 text-center">
          <Loader2 className="h-6 w-6 text-teal-400 animate-spin mx-auto mb-3" />
          <p className="text-white/50 text-xs">Loading...</p>
        </div>
      )}

      {!isLoading && !error && displayConversations.length === 0 && (
        <div className="p-8 text-center rounded-xl bg-white/5 border border-white/5">
          <p className="text-white/40 text-xs leading-relaxed">No past conversations found.</p>
        </div>
      )}

      {displayConversations.length > 0 && (
        <div className="space-y-0.5">
          {displayConversations.map((conv, index) => {
            const isActiveRow = Boolean(activeSessionId && conv.sessionId === activeSessionId)
            return (
              <motion.div
                key={conv.id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.01 }}
                className="group flex items-stretch gap-0.5"
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
                  className={`flex-1 min-w-0 text-left px-2 rounded-xl border transition-all duration-200 ${
                    isActiveRow
                      ? 'bg-teal-500/10 border-teal-500/25'
                      : 'border-transparent hover:bg-white/[0.04] active:bg-white/[0.06]'
                  }`}
                >
                  <div className="px-3 py-2">
                    <div className="flex items-start gap-3">
                      <span
                        className={`text-[13px] leading-snug line-clamp-2 transition-colors ${
                          isActiveRow ? 'text-teal-100/90' : 'text-white/60 group-hover:text-white/90'
                        }`}
                      >
                        {conv.preview}
                      </span>
                    </div>
                  </div>
                </button>
                <button
                  type="button"
                  onClick={(e) => void handleDelete(e, conv)}
                  disabled={deletingId === conv.id}
                  className="flex-shrink-0 self-center p-2 rounded-lg text-white/30 hover:text-red-300 hover:bg-red-500/10 transition-colors disabled:opacity-40"
                  title="Delete conversation"
                  aria-label="Delete conversation"
                >
                  {deletingId === conv.id ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Trash2 className="h-3.5 w-3.5" />
                  )}
                </button>
              </motion.div>
            )
          })}
        </div>
      )}
      </div>
    </div>
  )
}
