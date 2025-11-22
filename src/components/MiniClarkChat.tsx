"use client"

import React, { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { Expand, Send, User, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import agentsApi from '@/lib/agents_api'
import { ChatMessage } from '@/app/clark/types'
import ResultsDisplay from '@/app/clark/components/ResultsDisplay'
import { categories } from '@/app/clark/constants'

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
  const [isPromptModalOpen, setIsPromptModalOpen] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const feedRef = useRef<HTMLDivElement>(null)
  const [hasSentMessage, setHasSentMessage] = useState(false)
  
  // Dynamic height management
  const [containerHeight, setContainerHeight] = useState<number>(350) // Initial height
  const MIN_HEIGHT = 100
  const MAX_HEIGHT = 300 // Fixed max height - becomes scrollable after this
  const HEIGHT_PER_MESSAGE = 100 // Approximate height per message (accounts for structured results)
  
  // Determine if we should show only input (when showInputOnly is true and no messages sent yet)
  const shouldShowInputOnly = showInputOnly && !hasSentMessage

  // Initialize session ID
  useEffect(() => {
    const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    setSessionId(newSessionId)
  }, [])

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTo({ top: feedRef.current.scrollHeight, behavior: 'smooth' })
    }
  }, [messages])

  // Calculate dynamic height based on message count
  // Height grows with messages but caps at MAX_HEIGHT, then becomes scrollable
  useEffect(() => {
    const messageCount = messages.length
    if (messageCount === 0) {
      setContainerHeight(MIN_HEIGHT)
    } else {
      // Calculate height based on message count, but cap at MAX_HEIGHT
      // After MAX_HEIGHT, the container becomes fixed and scrollable
      const calculatedHeight = Math.min(
        MIN_HEIGHT + (messageCount * HEIGHT_PER_MESSAGE),
        MAX_HEIGHT
      )
      setContainerHeight(calculatedHeight)
    }
  }, [messages.length])

  const createAssistantMessage = (payload: any): ChatMessage => {
    const messageId = (Date.now() + Math.random()).toString()
    let responseMessage: string =
      payload?.message ?? "Sorry, I'm unable to process your request at the moment."
    const rawData = payload?.data

    const backtestResult = rawData?.backtest_result ?? rawData?.backtestResult
    const screenerResult =
      rawData && rawData?.screener_type && rawData.screener_type !== 'economic'
        ? rawData
        : undefined
    const economicResult =
      rawData && rawData?.screener_type === 'economic' ? rawData : undefined
    const regulationResult = rawData?.regulation_result ?? rawData?.regulationResult
    if (regulationResult) {
      responseMessage = ''
    }

    const rawParameterRequest = payload?.parameter_request
    const parameterRequest = rawParameterRequest
      ? {
          service: rawParameterRequest.service,
          actionType: rawParameterRequest.action_type,
          prompt: rawParameterRequest.prompt,
          missingParameters: rawParameterRequest.missing_parameters ?? {},
          receivedParameters: rawParameterRequest.received_parameters ?? {},
          requiredParameters: rawParameterRequest.required_parameters ?? {},
          context: rawParameterRequest.context ?? {},
        }
      : undefined

    return {
      id: messageId,
      type: 'assistant',
      content: responseMessage,
      timestamp: new Date(),
      parsedIntent: payload?.parsed_intent,
      success: payload?.success ?? false,
      backtestResult,
      screenerResult,
      economicResult,
      regulationResult,
      source: payload?.source ?? rawData?.source,
      capabilitiesSummary: payload?.capabilities_summary ?? rawData?.capabilities_summary,
      parameterRequest,
    }
  }

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading) return

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: inputValue,
      timestamp: new Date(),
    }

    setMessages(prev => [...prev, userMessage])
    setInputValue('')
    setIsLoading(true)
    setHasSentMessage(true) // Mark that a message has been sent
    
    try {
      const response = await agentsApi.post('/api/v1/agents/query', {
        query: inputValue,
        user_id: userId,
        session_id: sessionId
      })

      const payload = response.data
      
      // Check if this was a successful USDC transaction and trigger callbacks
      if (payload.success && payload.parsed_intent) {
        const intent = payload.parsed_intent
        if (intent.action === 'send_usdc' && intent.confidence > 0.7) {
          if (onBalanceFlicker) onBalanceFlicker()
          if (onBalanceRefresh) onBalanceRefresh()
          if (onTransactionRefresh) onTransactionRefresh()
        }
      }
      
      const assistantMessage = createAssistantMessage(payload)
      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('LangChain API error:', error)
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: 'Sorry, I\'m unable to process your request at the moment.',
        timestamp: new Date(),
        success: false,
      }

      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const handleExpand = () => {
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
    setIsLoading(true)
    setHasSentMessage(true) // Mark that a message has been sent
    
    try {
      const response = await agentsApi.post('/api/v1/agents/query', {
        query: routedPrompt,
        user_id: userId,
        session_id: sessionId
      })

      const payload = response.data
      
      // Check if this was a successful USDC transaction and trigger callbacks
      if (payload.success && payload.parsed_intent) {
        const intent = payload.parsed_intent
        if (intent.action === 'send_usdc' && intent.confidence > 0.7) {
          if (onBalanceFlicker) onBalanceFlicker()
          if (onBalanceRefresh) onBalanceRefresh()
          if (onTransactionRefresh) onTransactionRefresh()
        }
      }
      
      const assistantMessage = createAssistantMessage(payload)
      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('LangChain API error:', error)
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: 'Sorry, I\'m unable to process your request at the moment.',
        timestamp: new Date(),
        success: false,
      }

      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  // When showing input only, render without container border
  if (shouldShowInputOnly) {
    return (
      <>
        <div className="flex items-center gap-2">
          <button
            type="button"
            aria-label="Open prompt library"
            onClick={() => setIsPromptModalOpen(true)}
            className="h-10 w-10 flex items-center justify-center rounded-xl bg-zinc-900/80 border border-zinc-700/60 shadow hover:bg-zinc-800/80 flex-shrink-0"
          >
            <img src="/clark process.svg" alt="Prompts" className="h-5 w-5" />
          </button>
          <Input
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask Clark..."
            disabled={isLoading}
            className="flex-1 bg-zinc-800/60 border-zinc-700/50 text-white placeholder:text-zinc-400 focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/20 rounded-xl h-10 text-sm"
          />
          <Button
            onClick={handleSendMessage}
            disabled={!inputValue.trim() || isLoading}
            size="icon"
            className="bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 border-0 rounded-xl shadow-lg h-10 w-10"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <img src="/send button.svg" alt="send" className="h-4 w-4" />
            )}
          </Button>
        </div>
        {/* Prompts modal */}
        <Dialog open={isPromptModalOpen} onOpenChange={setIsPromptModalOpen}>
          <DialogContent className="sm:max-w-2xl bg-zinc-900/95 border border-zinc-700/60 rounded-2xl">
            <div className="max-h-[70vh] overflow-y-auto px-2">
              {(!selectedCategory) && (
                <div className="w-full flex flex-col items-center">
                  <div className="w-full max-w-md space-y-3">
                    {categories.map((category) => (
                      <button
                        key={category.id}
                        onClick={() => setSelectedCategory(category.id)}
                        className="w-full text-left p-4 rounded-xl bg-zinc-800/40 hover:bg-zinc-700/60 border border-zinc-700/50 hover:border-purple-500/50 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          {category.icon.startsWith('/') ? (
                            <img src={category.icon} alt={category.title} className="h-5 w-5" />
                          ) : (
                            <span className="text-lg">{category.icon}</span>
                          )}
                          <div className="min-w-0">
                            <div className="text-white font-medium truncate">{category.title}</div>
                            <div className="text-xs text-zinc-400 truncate">{category.description}</div>
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {selectedCategory && (
                <div className="w-full flex flex-col items-center space-y-4">
                  <div className="w-full max-w-md">
                    <button
                      onClick={() => setSelectedCategory(null)}
                      className="mb-3 text-xs text-zinc-400 hover:text-white"
                    >
                      ← Back
                    </button>
                    <div className="space-y-3">
                      {categories.find(c => c.id === selectedCategory)?.prompts.map((prompt, idx) => (
                        <button
                          key={idx}
                          onClick={() => handlePromptClick(prompt, selectedCategory)}
                          disabled={isLoading}
                          className="w-full text-left p-4 rounded-xl bg-zinc-800/40 hover:bg-zinc-700/60 border border-zinc-700/50 hover:border-purple-500/50 transition-colors text-white disabled:opacity-50"
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </>
    )
  }

  return (
    <div className="relative w-full rounded-2xl border border-zinc-700/50 bg-zinc-900/60 backdrop-blur-sm overflow-hidden shadow-lg">
      {/* Expand button overlay - fixed at top-right corner, doesn't scroll */}
      <Button
        onClick={handleExpand}
        variant="ghost"
        size="sm"
        className="absolute top-2 right-2 z-10 h-8 w-8 p-0 text-zinc-400 hover:text-white hover:bg-zinc-700/50 bg-zinc-900/80 backdrop-blur-sm rounded-full"
        aria-label="Expand to full Clark view"
      >
        {/* <Expand className="h-4 w-4" /> */}
        <img src="/maximize.svg" alt="Maximize" className="h-4 w-4" />
      </Button>
      
      {/* Messages area - dynamic height that grows with messages, then becomes fixed and scrollable */}
      <div
        ref={feedRef}
        className="overflow-y-auto px-4 py-3 scrollbar-thin scrollbar-thumb-zinc-600 scrollbar-track-transparent"
        style={{
          height: `${containerHeight}px`,
          transition: 'height 0.3s ease-in-out',
          maxHeight: `${MAX_HEIGHT}px`,
        }}
      >
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-zinc-400">
            <div className="text-center">
              <img src="/clark.svg" alt="Clark" className="h-14 w-14 mx-auto mb-2" />
            </div>
          </div>
        ) : (
          <div className="dark">
            <div className="space-y-3">
              <ResultsDisplay messages={messages} isLoading={isLoading} />
            </div>
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="px-4 py-3 border-t border-zinc-700/50 bg-zinc-800/30">
        <div className="flex items-center gap-2">
          <button
            type="button"
            aria-label="Open prompt library"
            onClick={() => setIsPromptModalOpen(true)}
            className="h-10 w-10 flex items-center justify-center rounded-xl bg-zinc-900/80 border border-zinc-700/60 shadow hover:bg-zinc-800/80 flex-shrink-0"
          >
            <img src="/clark process.svg" alt="Prompts" className="h-5 w-5" />
          </button>
          <Input
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask Clark..."
            disabled={isLoading}
            className="flex-1 bg-zinc-800/60 border-zinc-700/50 text-white placeholder:text-zinc-400 focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/20 rounded-xl h-10 text-sm"
          />
          <Button
            onClick={handleSendMessage}
            disabled={!inputValue.trim() || isLoading}
            size="icon"
            className="bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 border-0 rounded-xl shadow-lg h-10 w-10"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <img src="/send button.svg" alt="send" className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>

      {/* Prompts modal */}
      <Dialog open={isPromptModalOpen} onOpenChange={setIsPromptModalOpen}>
        <DialogContent className="sm:max-w-2xl bg-zinc-900/95 border border-zinc-700/60 rounded-2xl">
          <div className="max-h-[70vh] overflow-y-auto px-2">
            {(!selectedCategory) && (
              <div className="w-full flex flex-col items-center">
                <div className="w-full max-w-md space-y-3">
                  {categories.map((category) => (
                    <button
                      key={category.id}
                      onClick={() => setSelectedCategory(category.id)}
                      className="w-full text-left p-4 rounded-xl bg-zinc-800/40 hover:bg-zinc-700/60 border border-zinc-700/50 hover:border-purple-500/50 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        {category.icon.startsWith('/') ? (
                          <img src={category.icon} alt={category.title} className="h-5 w-5" />
                        ) : (
                          <span className="text-lg">{category.icon}</span>
                        )}
                        <div className="min-w-0">
                          <div className="text-white font-medium truncate">{category.title}</div>
                          <div className="text-xs text-zinc-400 truncate">{category.description}</div>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
            {selectedCategory && (
              <div className="w-full flex flex-col items-center space-y-4">
                <div className="w-full max-w-md">
                  <button
                    onClick={() => setSelectedCategory(null)}
                    className="mb-3 text-xs text-zinc-400 hover:text-white"
                  >
                    ← Back
                  </button>
                  <div className="space-y-3">
                    {categories.find(c => c.id === selectedCategory)?.prompts.map((prompt, idx) => (
                      <button
                        key={idx}
                        onClick={() => handlePromptClick(prompt, selectedCategory)}
                        disabled={isLoading}
                        className="w-full text-left p-4 rounded-xl bg-zinc-800/40 hover:bg-zinc-700/60 border border-zinc-700/50 hover:border-purple-500/50 transition-colors text-white disabled:opacity-50"
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

