"use client"

import React, { useState, useEffect, useRef } from 'react'
import { Menu } from 'lucide-react'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import agentsApi from '@/lib/agents_api'
import { useRouter } from 'next/navigation'
import { getAuth, signOut } from 'firebase/auth'
import { getFirebaseApp } from '@/lib/firebaseClient'
import HamburgerMenu from '@/components/wallet/HamburgerMenu'
import { clearUserContext, addBreadcrumb } from '@/lib/sentry'
import { ChatMessage } from './types'
import { categories } from './constants'
import CategoryTiles from './components/CategoryTiles'
import ChatInputBar from './components/ChatInterface'
import ResultsDisplay from './components/ResultsDisplay'
import DevtoolsOverlay from './components/DevtoolsOverlay'



export default function BacktestPage() {
  const router = useRouter()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [showMenu, setShowMenu] = useState(false)
  const [isPromptModalOpen, setIsPromptModalOpen] = useState(false)
  const [isDevtoolsOpen, setIsDevtoolsOpen] = useState(false)
  const feedRef = useRef<HTMLDivElement>(null)
  
  // Session management for mem0 integration
  const [userId, setUserId] = useState<string>('')
  const [sessionId, setSessionId] = useState<string>('')
  const [userData, setUserData] = useState<any>(null)
  
  // Cost tracking
  const [sessionCost, setSessionCost] = useState<number>(0)
  const [overallCost, setOverallCost] = useState<number>(0)
  

  // Initialize session and user IDs on component mount
  useEffect(() => {
    // Get user data from localStorage (set during login)
    const storedUserData = localStorage.getItem('userData')
    if (storedUserData) {
      try {
        const parsedData = JSON.parse(storedUserData)
        setUserData(parsedData)
        // Use actual user_id from userData, fallback to generated ID if not available
        const actualUserId = parsedData.user_id
        setUserId(actualUserId)
      } catch (error) {
        console.error('Error parsing user data:', error)
        // Fallback to generated ID if parsing fails
        const fallbackUserId = `user_krypton`
        setUserId(fallbackUserId)
      }
    } else {
      // If no userData exists, generate a temporary ID (for unauthenticated users)
      const defaultUserId = `user_krypton`
      setUserId(defaultUserId)
    }
    // Generate session ID (new for each browser session)
    const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    setSessionId(newSessionId)
  }, [])

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTo({ top: feedRef.current.scrollHeight, behavior: 'smooth' })
    }
  }, [messages])

  // Store messages in localStorage for devtools page access
  useEffect(() => {
    if (messages.length > 0) {
      try {
        const messagesToStore = messages.map(msg => ({
          ...msg,
          timestamp: msg.timestamp.toISOString() // Convert Date to string for storage
        }))
        localStorage.setItem('clark_messages', JSON.stringify(messagesToStore))
      } catch (error) {
        console.error('Error storing messages:', error)
      }
    }
  }, [messages])

  const handleLogout = async () => {
    try {
      const app = getFirebaseApp()
      if (app) {
        const auth = getAuth(app)
        await signOut(auth)
      }
      localStorage.removeItem('userData')
      setUserData(null)
      
      // Clear Sentry user context on logout
      clearUserContext()
      
      addBreadcrumb('User logged out', 'auth', { user_id: userData?.user_id })
      
      router.push('/')
    } catch (err) {
      console.error('Error during logout:', err)
    }
  }

  const handleCopyAddress = async () => {
    if (userData?.wallet_address) {
      try {
        await navigator.clipboard.writeText(userData.wallet_address)
        addBreadcrumb('Address copied to clipboard', 'wallet', { address: userData.wallet_address })
      } catch (err) {
        // Fallback for older browsers
        const textArea = document.createElement('textarea')
        textArea.value = userData.wallet_address
        document.body.appendChild(textArea)
        textArea.select()
        document.execCommand('copy')
        document.body.removeChild(textArea)
        addBreadcrumb('Address copied to clipboard (fallback)', 'wallet', { address: userData.wallet_address })
      }
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

  const createAssistantMessage = (payload: any): ChatMessage => {
    const messageId = (Date.now() + Math.random()).toString()
    // Build response message: prefer LLM combiner's message (includes all data), 
    // fallback to economic markdown, then default message
    let responseMessage: string =
      payload?.message ??  // LLM combiner's combined message (preferred - includes both screener and economic)
      (payload?.data?.markdown as string | undefined) ??  // Economic markdown if no combined message
      "Sorry, I'm unable to process your request at the moment."
    const rawData = payload?.data

    // Only keep backtest result, remove all other components
    const backtestResult = rawData?.backtest_result ?? rawData?.backtestResult

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
      // Remove all other result types - only keep backtest
      screenerResult: undefined,
      economicResult: undefined,
      regulationResult: undefined,
      source: payload?.source ?? rawData?.source,
      capabilitiesSummary: payload?.capabilities_summary ?? rawData?.capabilities_summary,
      parameterRequest,
      agentFlow: payload?.agent_flow, // Keep agent flow graph
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
    setIsLoading(true)
    
    try {
      const response = await agentsApi.post('/api/v1/agents/query', {
        query: routedPrompt,
        user_id: userId,
        session_id: sessionId
      })

      const payload = response.data
      // Update costs if available
      if (payload.costs) {
        setSessionCost(payload.costs.session_cost || 0)
        setOverallCost(payload.costs.overall_cost || 0)
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
        session_id: sessionId
      })

      const payload = response.data
      
      // Update costs if available
      if (payload.costs) {
        setSessionCost(payload.costs.session_cost || 0)
        setOverallCost(payload.costs.overall_cost || 0)
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

  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-black via-zinc-900 to-neutral-900 overflow-x-hidden">
      {/* Navbar */}
      <header className="fixed top-0 left-0 right-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-2 min-h-[4rem]">
            <div className="flex items-center">
              <img
                src="/krypton_logo.svg"
                alt="Krypton Logo"
                className="h-20 w-auto drop-shadow-[0_2px_8px_rgba(16,255,180,0.18)]"
              />
            </div>
            <div className="flex items-center space-x-3">
              {/* Cost Display */}
              {(sessionCost > 0 || overallCost > 0) && (
                <div className="flex items-center space-x-2 text-xs text-zinc-400">
                  <div className="px-2 py-1 bg-zinc-800/50 rounded-lg">
                    <span className="text-zinc-300">Session: </span>
                    <span className="text-green-400">${sessionCost.toFixed(6)}</span>
                  </div>
                  <div className="px-2 py-1 bg-zinc-800/50 rounded-lg">
                    <span className="text-zinc-300">Total: </span>
                    <span className="text-blue-400">${overallCost.toFixed(6)}</span>
                  </div>
                </div>
              )}
              <button
                onClick={() => setIsDevtoolsOpen(true)}
                className="flex items-center bg-zinc-800 hover:bg-zinc-700 text-white px-4 py-2 rounded-xl transition-colors font-medium"
                aria-label="Open devtools"
              >
                <img
                  src="/devtools.svg"
                  alt="Devtools"
                  className="h-4 w-4"
                />
              </button>
              <div className="relative">
                <button
                  onClick={() => setShowMenu(!showMenu)}
                  className="flex items-center bg-zinc-800 hover:bg-zinc-700 text-white px-4 py-2 rounded-xl transition-colors font-medium"
                  aria-label="Open menu"
                >
                  <Menu className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>
      {/* Spacer for fixed navbar height */}
      <div className="h-24" />

      {/* Main Content Area - continuous feed */}
      <div className={`container mx-auto px-4 py-2 max-w-6xl relative z-0`}>
        {/* Clark Logo - Show only when no user messages or results */}
        {!messages.some(m => m.type === 'user') && !messages.some(m => m.backtestResult) && (
          <div className="flex items-center justify-center mb-2 mt-20 sm:mt-0">
            <img src="/clark.svg" alt="Clark" className="h-[7.28rem] w-[7.28rem] sm:h-[9.1rem] sm:w-[9.1rem] drop-shadow-[0_4px_16px_rgba(162,89,247,0.3)]" />
          </div>
        )}

        {/* Category Tiles - Show only when no user messages or results */}
        {!messages.some(m => m.type === 'user') && !messages.some(m => m.backtestResult) && (
          <CategoryTiles
            categories={categories}
            selectedCategory={selectedCategory}
            onCategorySelect={(categoryId) => setSelectedCategory(categoryId || null)}
            onPromptClick={handlePromptClick}
            isLoading={isLoading}
          />
        )}

        {/* Continuous Feed: scrollable area bounded by navbar (top) and chat input (bottom) */}
        <div className="dark">
          <div ref={feedRef} className="max-h-[calc(100vh-6rem-6.5rem)] overflow-y-auto">
            <ResultsDisplay messages={messages} isLoading={isLoading} />
          </div>
        </div>
        
        {/* Prompts modal opened by left icon */}
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
                          onClick={() => handlePromptClick(prompt)}
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

      {/* Chat Input Bar - fixed at bottom */}
      <ChatInputBar
        inputValue={inputValue}
        setInputValue={setInputValue}
        isLoading={isLoading}
        onSendMessage={handleSendMessage}
        onKeyPress={handleKeyPress}
        onOpenPromptModal={() => setIsPromptModalOpen(true)}
      />

      {/* Hamburger Menu */}
      <HamburgerMenu
        visible={showMenu}
        onClose={() => setShowMenu(false)}
        onLogout={handleLogout}
        accountData={userData}
        onCopyAddress={handleCopyAddress}
      />

      {/* Devtools Overlay */}
      <DevtoolsOverlay
        isOpen={isDevtoolsOpen}
        onClose={() => setIsDevtoolsOpen(false)}
        messages={messages}
      />
    </div>
  )
}
