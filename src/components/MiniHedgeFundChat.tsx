"use client"

import React, { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import agentsApi from '@/lib/agents_api'
import { parseErrorMessage } from '@/lib/parseError'
import { ChatMessage } from '@/app/clark/types'
import { categories } from '@/app/clark/constants'
import ResultsDisplay from '@/app/clark/components/ResultsDisplay'
import PromptGuideModal from '@/app/clark/components/PromptGuideModal'
import ChatInputBar from '@/app/clark/components/ChatInterface'
import CategoryTiles from '@/app/clark/components/CategoryTiles'
import { createAssistantMessage } from '@/app/clark/utils/createAssistantMessage'

interface MiniHedgeFundChatProps {
  userId?: string
  onBalanceRefresh?: () => void
  onBalanceFlicker?: () => void
  onTransactionRefresh?: () => void
}

export default function MiniHedgeFundChat({
  userId = '',
  onBalanceRefresh,
  onBalanceFlicker,
  onTransactionRefresh,
}: MiniHedgeFundChatProps) {
  const router = useRouter()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string>('')
  const [userName, setUserName] = useState<string>('')
  const [isPromptModalOpen, setIsPromptModalOpen] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const feedRef = useRef<HTMLDivElement>(null)
  // Check if we should show tiles (no user messages or results)
  const shouldShowTiles = !messages.some(m => m.type === 'user') &&
    !messages.some(m => m.backtestResult || m.screenerResult || m.economicResult)

  useEffect(() => {
    const newSessionId = `session_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`
    setSessionId(newSessionId)

    const storedUserData = localStorage.getItem('userData')
    if (storedUserData) {
      try {
        const parsedData = JSON.parse(storedUserData)
        if (parsedData.username) {
          setUserName(parsedData.username)
        }
      } catch (error) {
        console.error('Error parsing user data', error)
      }
    }
  }, [])

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTo({ top: feedRef.current.scrollHeight, behavior: 'smooth' })
    }
  }, [messages])

  const buildQueryForCategory = (prompt: string, categoryId?: string | null) => {
    if (!categoryId) return prompt
    if (categoryId === 'technical') return `Technical analysis request: ${prompt}`
    if (categoryId === 'strategy') return `Backtest request: ${prompt}`
    return prompt
  }

  const runQuery = async (query: string, userMessage?: ChatMessage) => {
    setIsLoading(true)
    try {
      const response = await agentsApi.post('/api/v1/agents/query', {
        query,
        user_id: userId,
        username: userName || 'krypton',
        session_id: sessionId,
      })
      const payload = response.data
      if (payload?.success && payload?.parsed_intent?.action === 'send_usdc' && (payload.parsed_intent.confidence ?? 0) > 0.7) {
        onBalanceFlicker?.()
        onBalanceRefresh?.()
        onTransactionRefresh?.()
      }
      const assistantMessage = createAssistantMessage(payload)
      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('Hedge Fund Chat API error:', error)
      const content = parseErrorMessage(error, 'Sorry, I encountered an error processing your request. Please try again.')
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content,
        timestamp: new Date(),
        success: false,
      }])
    } finally {
      setIsLoading(false)
    }
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
    await runQuery(query, userMessage)
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
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
    await runQuery(routedPrompt, userMessage)
  }

  const handleExpand = () => {
    if (messages.length > 0) {
      try {
        const messagesToStore = messages.map(msg => ({
          ...msg,
          timestamp: msg.timestamp.toISOString(),
        }))
        localStorage.setItem('clark_expanded_messages', JSON.stringify(messagesToStore))
        localStorage.setItem('clark_expanded_session_id', sessionId)
      } catch (error) {
        console.error('Error storing messages for expansion:', error)
      }
    }
    router.push('/clark')
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

  return (
    <>
      <div className="relative w-full min-w-0 flex flex-col rounded-2xl bg-[hsl(var(--brand-bg))] overflow-hidden shadow-xl max-h-[70vh]">
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
          <div className="dark flex-1 min-h-0 overflow-hidden">
            <div ref={feedRef} className="scrollbar-minimal h-full max-h-[50vh] overflow-x-hidden overflow-y-auto scroll-smooth px-4 py-3">
              <div className="pb-6">
                {shouldShowTiles ? (
                  <>
                    <div className="flex items-center justify-center mb-4 mt-2">
                      <img
                        src="/Krypton Clark.svg"
                        alt="Clark"
                        className="h-14 w-14 sm:h-16 sm:w-16 drop-shadow-[0_4px_16px_rgba(162,89,247,0.3)]"
                      />
                    </div>
                    <CategoryTiles
                      categories={categories}
                      selectedCategory={selectedCategory}
                      onCategorySelect={(categoryId) => setSelectedCategory(categoryId || null)}
                      onPromptClick={handlePromptClick}
                      isLoading={isLoading}
                    />
                  </>
                ) : (
                  <>
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
                  </>
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
