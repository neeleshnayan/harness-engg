"use client"

import React, { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import agentsApi from '@/lib/agents_api'
import { parseErrorMessage } from '@/lib/parseError'
import { ChatMessage } from '@/app/clark/types'
import ResultsDisplay from '@/app/clark/components/ResultsDisplay'
import PromptGuideModal from '@/app/clark/components/PromptGuideModal'
import ChatInputBar from '@/app/clark/components/ChatInterface'
import CategoryTiles from '@/app/clark/components/CategoryTiles'
import { categories } from '@/app/clark/constants'
import { createAssistantMessage } from '@/app/clark/utils/createAssistantMessage'

type InterruptFromApi = { id?: string; name?: string; reason?: Record<string, unknown> }

interface MiniClarkChatProps {
  userId?: string
  onBalanceRefresh?: () => void
  onBalanceFlicker?: () => void
  onTransactionRefresh?: () => void
  showInputOnly?: boolean
}

export default function MiniClarkChat({
  userId = '',
  onBalanceRefresh,
  onBalanceFlicker,
  onTransactionRefresh,
  showInputOnly = false,
}: MiniClarkChatProps) {
  const router = useRouter()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string>('')
  const [userName, setUserName] = useState<string>('')
  const [isPromptModalOpen, setIsPromptModalOpen] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const feedRef = useRef<HTMLDivElement>(null)
  const [hasSentMessage, setHasSentMessage] = useState(false)
  const [interrupts, setInterrupts] = useState<InterruptFromApi[]>([])
  const [pendingInterruptResponse, setPendingInterruptResponse] = useState<{ query: string; userMessage: ChatMessage } | null>(null)
  const shownInterruptIdsRef = useRef<Set<string>>(new Set())

  const shouldShowInputOnly = showInputOnly && !hasSentMessage

  // Initialize session ID and username
  useEffect(() => {
    const newSessionId = `session_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`
    setSessionId(newSessionId)

    // Extract username from localStorage
    const storedUserData = localStorage.getItem('userData')
    if (storedUserData) {
      try {
        const parsedData = JSON.parse(storedUserData)
        if (parsedData.username) {
          setUserName(parsedData.username)
        }
      } catch (error) {
        console.error('Error parsing user data:', error)
      }
    }
  }, [])

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTo({ top: feedRef.current.scrollHeight, behavior: 'smooth' })
    }
  }, [messages])

  useEffect(() => {
    if (feedRef.current && interrupts.length > 0) {
      feedRef.current.scrollTo({ top: feedRef.current.scrollHeight, behavior: 'smooth' })
    }
  }, [interrupts.length])

  /** Single path for API call, callbacks, and response handling. */
  const runQuery = async (query: string, userMessage?: ChatMessage, interruptResponses?: unknown[]) => {
    setIsLoading(true)
    try {
      const body: Record<string, unknown> = {
        user_id: userId,
        username: userName || 'krypton',
        session_id: sessionId,
      }
      if (interruptResponses?.length) {
        body.content = interruptResponses
        if (query.trim()) body.query = query
      } else {
        body.query = query
      }
      const response = await agentsApi.post('/api/v1/agents/query', body)
      const payload = response.data

      // Payment / interrupt: show confirmation dialog instead of appending a message
      if (payload?.stop_reason === 'interrupt' && payload?.interrupts?.length) {
        const newInterrupts = (payload.interrupts as InterruptFromApi[]).filter((i) => {
          const id = i?.id != null ? String(i.id) : ''
          if (id && shownInterruptIdsRef.current.has(id)) return false
          if (id) shownInterruptIdsRef.current.add(id)
          return true
        })
        if (newInterrupts.length > 0) {
          setInterrupts(newInterrupts)
          setPendingInterruptResponse({
            query,
            userMessage: userMessage ?? {
              id: Date.now().toString(),
              type: 'user',
              content: query,
              timestamp: new Date(),
            },
          })
        }
        setIsLoading(false)
        return
      }

      setInterrupts([])
      setPendingInterruptResponse(null)
      shownInterruptIdsRef.current.clear()

      if (payload?.success && payload?.parsed_intent?.action === 'send_usdc' && payload.parsed_intent.confidence > 0.7) {
        onBalanceFlicker?.()
        onBalanceRefresh?.()
        onTransactionRefresh?.()
      }
      const assistantMessage = createAssistantMessage(payload)
      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('LangChain API error:', error)
      setMessages(prev => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          type: 'assistant' as const,
          content: parseErrorMessage(error, "Sorry, I'm unable to process your request at the moment."),
          timestamp: new Date(),
          success: false,
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handleInterruptApprove = async (interruptId: string) => {
    const pending = pendingInterruptResponse
    if (!pending) return
    setInterrupts([])
    setPendingInterruptResponse(null)
    const interruptResponses = [{ interruptResponse: { interruptId, response: 'yes' } }]
    await runQuery(pending.query, pending.userMessage, interruptResponses)
    onBalanceRefresh?.()
    onTransactionRefresh?.()
  }

  const handleInterruptReject = async (interruptId: string) => {
    const pending = pendingInterruptResponse
    if (!pending) return
    setInterrupts([])
    setPendingInterruptResponse(null)
    setMessages(prev => [...prev, {
      id: (Date.now() + 1).toString(),
      type: 'assistant',
      content: 'Transaction rejected.',
      timestamp: new Date(),
      success: true,
    }])
    const interruptResponses = [{ interruptResponse: { interruptId, response: 'no' } }]
    await runQuery(pending.query, pending.userMessage, interruptResponses)
  }

  const handleSendMessage = async () => {
    const query = inputValue.trim()
    if (!query || isLoading) return
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: query,
      timestamp: new Date(),
    }
    setMessages(prev => [...prev, userMessage])
    setInputValue('')
    setHasSentMessage(true)
    await runQuery(query, userMessage)
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const handleExpand = () => {
    // Store messages and sessionId before navigating
    if (messages.length > 0) {
      try {
        const messagesToStore = messages.map(msg => ({
          ...msg,
          timestamp: msg.timestamp.toISOString() // Convert Date to string for storage
        }))
        localStorage.setItem('clark_expanded_messages', JSON.stringify(messagesToStore))
        localStorage.setItem('clark_expanded_session_id', sessionId)
      } catch (error) {
        console.error('Error storing messages for expansion:', error)
      }
    }
    router.push('/clark')
  }

  const buildQueryForCategory = (prompt: string, categoryId?: string | null) => {
    if (!categoryId) return prompt
    if (categoryId === 'technical') {
      return `Technical analysis request: ${prompt}`
    }
    if (categoryId === 'strategy') {
      return `Backtest request: ${prompt}`
    }
    return prompt
  }

  const handlePromptClick = async (prompt: string, categoryId?: string | null) => {
    const routedPrompt = buildQueryForCategory(prompt, categoryId ?? null)
    setSelectedCategory(null)
    setIsPromptModalOpen(false)
    setInputValue('')
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: prompt,
      timestamp: new Date(),
    }
    setMessages(prev => [...prev, userMessage])
    setHasSentMessage(true)
    await runQuery(routedPrompt, userMessage)
  }

  const promptsModal = (
    <PromptGuideModal
      open={isPromptModalOpen}
      onOpenChange={setIsPromptModalOpen}
      categories={categories}
      selectedCategory={selectedCategory}
      onSelectCategory={setSelectedCategory}
      onPromptClick={(prompt, categoryId) => handlePromptClick(prompt, categoryId)}
      isLoading={isLoading}
    />
  )

  // Same inline payment confirmation as /clark
  const paymentInterrupt = interrupts.find((i) => i.name === 'krypton-pay-approval')
  const reason = paymentInterrupt?.reason as { operation?: string; from_token?: string; to_token?: string; received_amount?: number; receiver_username?: string } | undefined

  if (shouldShowInputOnly) {
    return (
      <>
        <div className="miniclark-bar w-full outline-none ring-0 border-0 [&_*]:outline-none [&_*]:border-0">
          <ChatInputBar
            inputValue={inputValue}
            setInputValue={setInputValue}
            isLoading={isLoading}
            onSendMessage={handleSendMessage}
            onKeyPress={handleKeyPress}
            onOpenPromptModal={() => { setSelectedCategory(null); setIsPromptModalOpen(true) }}
            embedded
          />
        </div>
        {promptsModal}
      </>
    )
  }

  return (
    <>
      <div className="relative w-full flex flex-col rounded-2xl bg-[hsl(var(--brand-bg))] overflow-hidden shadow-xl max-h-[70vh]">
        <Button
          onClick={handleExpand}
          variant="ghost"
          size="sm"
          className="absolute top-2 right-2 z-10 h-8 w-8 p-0 text-teal-200/80 hover:text-white hover:bg-teal-700/40 rounded-full border border-teal-600/50 transition-colors"
          aria-label="Expand to full Clark view"
        >
          <img src="/maximize.svg" alt="Maximize" className="h-4 w-4" />
        </Button>
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
          {/* Feed: same structure as /clark */}
          <div className="dark flex-1 min-h-0 overflow-hidden">
            <div ref={feedRef} className="scrollbar-minimal h-full max-h-[50vh] overflow-y-auto scroll-smooth px-3 py-3">
              <div className="pb-6">
                {!messages.some((m) => m.type === 'user') && (
                  <CategoryTiles
                    categories={categories}
                    selectedCategory={selectedCategory}
                    onCategorySelect={(categoryId) => setSelectedCategory(categoryId || null)}
                    onPromptClick={handlePromptClick}
                    isLoading={isLoading}
                  />
                )}
                {isLoading && messages.length === 0 && (
                  <div className="flex gap-2 justify-start items-center py-4">
                    <div className="w-8 h-8 flex items-center justify-center flex-shrink-0">
                      <img src="/clark process.svg" alt="Clark" className="h-8 w-8 animate-pulse" />
                    </div>
                    <div className="rounded-2xl px-4 py-3 bg-teal-900/30 border border-teal-700/40 text-white/80 text-sm">
                      Thinking…
                    </div>
                  </div>
                )}
                <ResultsDisplay messages={messages} isLoading={isLoading} username={userName} />
                {interrupts.length > 0 && paymentInterrupt && reason && (
                  <div className="mb-4 flex gap-2 justify-start items-start">
                    <div className="w-8 h-8 flex items-center justify-center flex-shrink-0">
                      <img src="/clark process.svg" alt="Clark" className="h-8 w-8" />
                    </div>
                    <div className="max-w-[85%] rounded-2xl p-4 bg-teal-900/40 border border-teal-700/50 text-white backdrop-blur-sm">
                      <div className="text-[10px] uppercase tracking-[0.2em] text-teal-200/90 mb-2">
                        Payment confirmation
                      </div>
                      <p className="text-sm text-white/90 mb-3">
                        Please review and confirm the payment details below.
                      </p>
                      <div className="bg-teal-900/60 rounded-lg p-3 border border-teal-700/40 space-y-2 text-sm">
                        {reason.operation === 'swap_and_transfer' && reason.from_token && (
                          <div className="flex justify-between items-center">
                            <span className="text-white/80">Swap From:</span>
                            <span className="text-white font-medium">{reason.from_token}</span>
                          </div>
                        )}
                        <div className="flex justify-between items-center">
                          <span className="text-white/80">Send Amount:</span>
                          <span className="text-white font-semibold">
                            {reason.received_amount} {reason.to_token ?? ''}
                          </span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-white/80">To:</span>
                          <span className="text-white font-medium">@{reason.receiver_username}</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-white/80">Operation:</span>
                          <span className="text-white font-medium">
                            {reason.operation === 'swap_and_transfer' ? 'Swap & Transfer' : 'Transfer'}
                          </span>
                        </div>
                      </div>
                      <div className="flex gap-3 pt-3 mt-2">
                        <button
                          type="button"
                          onClick={() => handleInterruptReject(String(paymentInterrupt.id ?? ''))}
                          className="flex-1 inline-flex items-center justify-center px-3 py-2 rounded-xl border border-red-700/60 bg-red-900/30 text-red-100 hover:bg-red-900/50 text-sm font-medium transition-colors"
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          onClick={() => handleInterruptApprove(String(paymentInterrupt.id ?? ''))}
                          className="flex-1 inline-flex items-center justify-center px-3 py-2 rounded-xl bg-white/20 hover:bg-white/30 text-white text-sm font-medium border border-white/20"
                        >
                          Confirm
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
          <ChatInputBar
            inputValue={inputValue}
            setInputValue={setInputValue}
            isLoading={isLoading}
            onSendMessage={handleSendMessage}
            onKeyPress={handleKeyPress}
            onOpenPromptModal={() => { setSelectedCategory(null); setIsPromptModalOpen(true) }}
            embedded
          />
        </div>
      </div>
      {promptsModal}
    </>
  )
}

