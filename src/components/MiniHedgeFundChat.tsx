"use client"

import React, { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import agentsApi from '@/lib/agents_api'
import { ChatMessage } from '@/app/clark/types'
import { categories } from '@/app/clark/constants'
import ResultsDisplay from '@/app/clark/components/ResultsDisplay'
import CategoryTiles from '@/app/clark/components/CategoryTiles'

interface MiniHedgeFundChatProps {
  userId?: string
}

export default function MiniHedgeFundChat({
  userId = '',
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
  
  // Max height for scrolling when content is too long
  const MAX_HEIGHT = 600 // Max height before scrolling kicks in

  // Initialize session ID and username
  useEffect(() => {
    const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
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

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTo({ top: feedRef.current.scrollHeight, behavior: 'smooth' })
    }
  }, [messages])

  // Check if we should show tiles (no user messages or results)
  const shouldShowTiles = !messages.some(m => m.type === 'user') && 
    !messages.some(m => m.backtestResult || m.screenerResult || m.economicResult)

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
    
    try {
      const response = await agentsApi.post('/api/v1/agents/query', {
        query: inputValue,
        user_id: userId,
        username: userName,
        session_id: sessionId
      })

      const payload = response.data
      const assistantMessage = createAssistantMessage(payload)
      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('Hedge Fund Chat API error:', error)
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: 'Sorry, I encountered an error processing your request. Please try again.',
        timestamp: new Date(),
        success: false,
      }

      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
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
    
    try {
      const response = await agentsApi.post('/api/v1/agents/query', {
        query: routedPrompt,
        user_id: userId,
        username: userName,
        session_id: sessionId
      })

      const payload = response.data
      const assistantMessage = createAssistantMessage(payload)
      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('Hedge Fund Chat API error:', error)
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: 'Sorry, I encountered an error processing your request. Please try again.',
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
        <img src="/maximize.svg" alt="Maximize" className="h-4 w-4" />
      </Button>
      
      {/* Messages area - grows naturally with content, scrollable when exceeding max height */}
      <div
        ref={feedRef}
        className="overflow-y-auto px-4 py-3 scrollbar-thin scrollbar-thumb-zinc-600 scrollbar-track-transparent"
        style={{
          maxHeight: `${MAX_HEIGHT}px`,
        }}
      >
        {shouldShowTiles ? (
          <div className="dark">
            {/* Clark Logo */}
            <div className="flex items-center justify-center mb-4 mt-2">
              <img 
                src="/clark.svg" 
                alt="Clark" 
                className="h-16 w-16 sm:h-20 sm:w-20 drop-shadow-[0_4px_16px_rgba(162,89,247,0.3)]" 
              />
            </div>
            {/* Category Tiles */}
            <CategoryTiles
              categories={categories}
              selectedCategory={selectedCategory}
              onCategorySelect={(categoryId) => setSelectedCategory(categoryId || null)}
              onPromptClick={handlePromptClick}
              isLoading={isLoading}
            />
          </div>
        ) : messages.length > 0 ? (
          <div className="dark">
            <div className="space-y-3">
              <ResultsDisplay messages={messages} isLoading={isLoading} />
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-zinc-400">
            <div className="text-center">
              <img src="/clark.svg" alt="Clark" className="h-14 w-14 mx-auto mb-2" />
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
          <Button
            onClick={() => router.push('/clark')}
            className="flex-1 px-4 py-2 bg-zinc-800/60 hover:bg-zinc-700/80 text-zinc-300 hover:text-white px-4 sm:px-6 py-2 rounded-xl border border-zinc-700/50 hover:border-zinc-600/50 transition-all duration-200 text-xs sm:text-sm w-full sm:w-auto justify-center flex items-center gap-2 h-10 text-sm"
          >
            <span>Ask Clark</span>
            <span>→</span>
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

