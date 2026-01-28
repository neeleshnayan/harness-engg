"use client"

import React, { useState, useEffect, useRef } from 'react'
import dynamic from 'next/dynamic'
import { Menu } from 'lucide-react'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import agentsApi from '@/lib/agents_api'
import { useRouter } from 'next/navigation'
import { getAuth, signOut } from 'firebase/auth'
import { getFirebaseApp } from '@/lib/firebaseClient'
import HamburgerMenu from '@/components/wallet/HamburgerMenu'
import { ChatMessage } from './types'
import { categories } from './constants'
import CategoryTiles from './components/CategoryTiles'
import ChatInputBar from './components/ChatInterface'

// Dynamically import heavy components to reduce initial bundle size
const ResultsDisplay = dynamic(() => import('./components/ResultsDisplay'), {
  loading: () => <div className="flex items-center justify-center p-8"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div></div>,
  ssr: false,
});

const DevtoolsOverlay = dynamic(() => import('./components/DevtoolsOverlay'), {
  loading: () => null,
  ssr: false,
});



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
  const [userName, setUserName] = useState<string>('')
  const [sessionId, setSessionId] = useState<string>('')
  const [userData, setUserData] = useState<any>(null)
  
  // Cost tracking - session cost resets on new session, overall cost fetched from Firebase
  const [sessionCost, setSessionCost] = useState<number>(0)
  const [overallCost, setOverallCost] = useState<number>(0)
  const [isFetchingCosts, setIsFetchingCosts] = useState<boolean>(false)
  
  // Interrupt handling
  const [interrupts, setInterrupts] = useState<any[]>([])
  const [isInterruptModalOpen, setIsInterruptModalOpen] = useState(false)
  const [pendingInterruptResponse, setPendingInterruptResponse] = useState<{
    query: string
    userMessage: ChatMessage
  } | null>(null)
  
  

  // Initialize session and user IDs on component mount
  useEffect(() => {
    // Get user data from localStorage (set during login)
    const storedUserData = localStorage.getItem('userData')
    if (storedUserData) {
      try {
        const parsedData = JSON.parse(storedUserData)
        setUserData(parsedData)
        // Extract username if available
        if (parsedData.username) {
          setUserName(parsedData.username)
        }
        // Use actual user_id from userData, fallback to other unique identifiers
        // Try user_id first, then uid (Firebase), then email
        // These should all be unique per user and consistent across sessions
        const actualUserId = parsedData.user_id || 
                            parsedData.uid || 
                            parsedData.email
        if (actualUserId) {
          setUserId(actualUserId)
        } else {
          // If no unique identifier found, use default fallback
          console.warn('No user_id, uid, or email found in userData. Using default fallback ID.')
          setUserId('krypton_user')
        }
      } catch (error) {
        console.error('Error parsing user data:', error)
        // Fallback to default ID if parsing fails
        setUserId('krypton_user')
      }
    } else {
      // If no userData exists, use default fallback ID
      setUserId('krypton_user')
    }
    
    // Check for expanded messages from mini chat components
    try {
      const expandedMessages = localStorage.getItem('clark_expanded_messages')
      const expandedSessionId = localStorage.getItem('clark_expanded_session_id')
      
      if (expandedMessages && expandedSessionId) {
        // Load messages from expansion
        const parsedMessages = JSON.parse(expandedMessages).map((msg: any) => ({
          ...msg,
          timestamp: new Date(msg.timestamp) // Convert string back to Date
        })) as ChatMessage[]
        setMessages(parsedMessages)
        setSessionId(expandedSessionId)
        
        // Clear the stored data to avoid reloading on refresh
        localStorage.removeItem('clark_expanded_messages')
        localStorage.removeItem('clark_expanded_session_id')
      } else {
        // Generate new session ID if not expanding from mini chat
        const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
        setSessionId(newSessionId)
      }
    } catch (error) {
      console.error('Error loading expanded messages:', error)
      // Fallback to generating new session ID if loading fails
      const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
      setSessionId(newSessionId)
    }
    
    // Reset session cost for new session
    setSessionCost(0)
  }, [])

  // Fetch initial costs from Firebase via API when userId is available
  useEffect(() => {
    const fetchInitialCosts = async () => {
      if (!userId || isFetchingCosts) return
      
      setIsFetchingCosts(true)
      try {
        // Fetch overall cost from Firebase using dedicated endpoint (no query processing)
        const response = await agentsApi.get('/api/v1/agents/cost', {
          params: { user_id: userId }
        })

        const payload = response.data
        if (payload.success && payload.overall_cost !== undefined) {
          const newOverallCost = payload.overall_cost || 0
          setSessionCost(0) // Always 0 for new session
          setOverallCost(newOverallCost)
          // Persist overall cost to localStorage as backup
          localStorage.setItem('clark_overall_cost', newOverallCost.toString())
        }
      } catch (error) {
        console.error('Error fetching initial costs:', error)
        // Fallback to localStorage if API call fails
        if (typeof window !== 'undefined') {
          const stored = localStorage.getItem('clark_overall_cost')
          if (stored) {
            setOverallCost(parseFloat(stored))
          }
        }
      } finally {
        setIsFetchingCosts(false)
      }
    }

    // Fetch costs when userId is available
    if (userId) {
      fetchInitialCosts()
    }
  }, [userId])

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTo({ top: feedRef.current.scrollHeight, behavior: 'smooth' })
    }
  }, [messages])

  // Also scroll when a new interrupt (e.g. payment confirmation) arrives so the
  // inline confirmation bubble is visible at the bottom of the feed.
  useEffect(() => {
    if (feedRef.current && interrupts.length > 0) {
      feedRef.current.scrollTo({ top: feedRef.current.scrollHeight, behavior: 'smooth' })
    }
  }, [interrupts.length])

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

      router.push('/')
    } catch (err) {
      console.error('Error during logout:', err)
    }
  }

  const handleCopyAddress = async () => {
    if (userData?.wallet_address) {
      try {
        await navigator.clipboard.writeText(userData.wallet_address)
      } catch (err) {
        // Fallback for older browsers
        const textArea = document.createElement('textarea')
        textArea.value = userData.wallet_address
        document.body.appendChild(textArea)
        textArea.select()
        document.execCommand('copy')
        document.body.removeChild(textArea)
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

    // Extract price history result - check multiple possible locations
    // The agent returns: data: { price_history: {...}, token: "...", data_points: [...] }
    // Or: data: { price_history: { token, lookback_days, count, data: [...] } }
    const priceHistoryData = rawData?.price_history ?? rawData?.priceHistory
    // Try multiple paths to find data_points
    let dataPoints = rawData?.data_points
    if (!dataPoints && priceHistoryData) {
      dataPoints = priceHistoryData?.data_points ?? priceHistoryData?.data
    }
    // Also check if priceHistoryData itself is an array (unlikely but possible)
    if (!dataPoints && Array.isArray(priceHistoryData)) {
      dataPoints = priceHistoryData
    }
    
    // Debug logging
    if (payload?.parsed_intent?.operation === 'price_history' || priceHistoryData || dataPoints) {
      console.log('Price history extraction:', {
        hasPriceHistoryData: !!priceHistoryData,
        hasDataPoints: !!dataPoints,
        dataPointsType: Array.isArray(dataPoints) ? 'array' : typeof dataPoints,
        dataPointsLength: Array.isArray(dataPoints) ? dataPoints.length : 'N/A',
        rawDataKeys: rawData ? Object.keys(rawData) : [],
        priceHistoryDataKeys: priceHistoryData && typeof priceHistoryData === 'object' ? Object.keys(priceHistoryData) : [],
        parsedIntent: payload?.parsed_intent,
      })
    }
    
    const priceHistoryResult = (priceHistoryData || dataPoints) && Array.isArray(dataPoints) && dataPoints.length > 0
      ? {
          token: rawData?.token || priceHistoryData?.token || payload?.parsed_intent?.token_name || '',
          lookback_days: priceHistoryData?.lookback_days || payload?.parsed_intent?.lookback_days || 30,
          count: priceHistoryData?.count || dataPoints.length || 0,
          data_points: dataPoints,
        }
      : undefined
    
    if (priceHistoryResult) {
      console.log('Price history result created:', {
        token: priceHistoryResult.token,
        lookback_days: priceHistoryResult.lookback_days,
        count: priceHistoryResult.count,
        dataPointsLength: priceHistoryResult.data_points.length,
      })
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
      priceHistoryResult,
      // Remove all other result types - only keep backtest and price history
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
        username: userName,
        session_id: sessionId
      })

      const payload = response.data
      
      // Check for interrupts
      if (payload.stop_reason === 'interrupt' && payload.interrupts && payload.interrupts.length > 0) {
        setInterrupts(payload.interrupts)
        setIsInterruptModalOpen(true)
        setPendingInterruptResponse({
          query: routedPrompt,
          userMessage: userMessage
        })
        setIsLoading(false)
        return
      }
      
      // Clear interrupt state if no interrupts
      setInterrupts([])
      setIsInterruptModalOpen(false)
      setPendingInterruptResponse(null)
      
      // Update costs if available and persist overall cost to localStorage
      if (payload.costs) {
        const newSessionCost = payload.costs.session_cost || 0
        const newOverallCost = payload.costs.overall_cost || 0
        setSessionCost(newSessionCost)
        setOverallCost(newOverallCost)
        // Persist overall cost to localStorage (session cost resets on new session)
        localStorage.setItem('clark_overall_cost', newOverallCost.toString())
      }
      
      // Check if krypton_pay transaction was made
      // Check multiple possible locations for krypton_pay indication
      const agentIds = payload?.parsed_intent?.agent_ids || []
      const hasKryptonPayInIntent = agentIds.includes('krypton_pay')
      
      const agentFlowNodes = payload?.agent_flow?.nodes || []
      const hasKryptonPayInFlow = agentFlowNodes.some((node: any) => 
        node.tool_name === 'consult_krypton_pay' || 
        node.id === 'krypton_pay' ||
        (node.output?.data && (
          node.output.data.transaction_id || 
          node.output.data.status === 'SUBMITTED' ||
          node.output.data.operation
        ))
      )
      
      // Also check if response data contains transaction info
      const hasTransactionData = payload?.data?.transaction_id || 
        payload?.data?.status === 'SUBMITTED' ||
        payload?.data?.operation
      
      // Fallback: check message content for transaction keywords
      const message = payload?.message || ''
      const hasTransactionKeywords = /(sent|transfer|transaction|successfully)/i.test(message) && 
        /(USD|EUR|AED|to @)/i.test(message)
      
      const hasKryptonPay = hasKryptonPayInIntent || hasKryptonPayInFlow || hasTransactionData || hasTransactionKeywords
      
      const assistantMessage = createAssistantMessage(payload)

      // Append Clark's response so ResultsDisplay can render results/backtests/etc.
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

  const handleSendMessage = async (interruptResponses?: any[]) => {
    const queryText = interruptResponses ? (pendingInterruptResponse?.query || '') : inputValue
    
    if (!queryText.trim() || isLoading) return

    const userMessage: ChatMessage = interruptResponses 
      ? pendingInterruptResponse!.userMessage
      : {
          id: Date.now().toString(),
          type: 'user',
          content: inputValue,
          timestamp: new Date(),
        }

    if (!interruptResponses) {
      setMessages(prev => [...prev, userMessage])
      setInputValue('')
    }
    
    setIsLoading(true)
    
    try {
      const requestBody: any = {
        user_id: userId,
        username: userName,
        session_id: sessionId
      }

      // If we have interrupt responses, send them as content blocks
      // Otherwise, send the query
      if (interruptResponses && interruptResponses.length > 0) {
        // Strands expects interrupt responses as content blocks
        requestBody.content = interruptResponses
      } else {
        requestBody.query = queryText
      }

      const response = await agentsApi.post('/api/v1/agents/query', requestBody)

      const payload = response.data
      
      // Check for interrupts
      if (payload.stop_reason === 'interrupt' && payload.interrupts && payload.interrupts.length > 0) {
        setInterrupts(payload.interrupts)
        setIsInterruptModalOpen(true)
        setPendingInterruptResponse({
          query: queryText,
          userMessage: userMessage
        })
        setIsLoading(false)
        return
      }
      
      // Clear interrupt state if no interrupts
      setInterrupts([])
      setIsInterruptModalOpen(false)
      setPendingInterruptResponse(null)
      
      // Update costs if available and persist overall cost to localStorage
      if (payload.costs) {
        const newSessionCost = payload.costs.session_cost || 0
        const newOverallCost = payload.costs.overall_cost || 0
        setSessionCost(newSessionCost)
        setOverallCost(newOverallCost)
        // Persist overall cost to localStorage (session cost resets on new session)
        localStorage.setItem('clark_overall_cost', newOverallCost.toString())
      }
      
      // Check if krypton_pay transaction was made
      // Check multiple possible locations for krypton_pay indication
      const agentIds = payload?.parsed_intent?.agent_ids || []
      const hasKryptonPayInIntent = agentIds.includes('krypton_pay')
      
      const agentFlowNodes = payload?.agent_flow?.nodes || []
      const hasKryptonPayInFlow = agentFlowNodes.some((node: any) => 
        node.tool_name === 'consult_krypton_pay' || 
        node.id === 'krypton_pay' ||
        (node.output?.data && (
          node.output.data.transaction_id || 
          node.output.data.status === 'SUBMITTED' ||
          node.output.data.operation
        ))
      )
      
      // Also check if response data contains transaction info
      const hasTransactionData = payload?.data?.transaction_id || 
        payload?.data?.status === 'SUBMITTED' ||
        payload?.data?.operation
      
      // Fallback: check message content for transaction keywords
      const message = payload?.message || ''
      const hasTransactionKeywords = /(sent|transfer|transaction|successfully)/i.test(message) && 
        /(USD|EUR|AED|to @)/i.test(message)
      
      const hasKryptonPay = hasKryptonPayInIntent || hasKryptonPayInFlow || hasTransactionData || hasTransactionKeywords
      
      const assistantMessage = createAssistantMessage(payload)

      // Always append Clark's response; ResultsDisplay will decide what to show,
      // including any transaction status cards for krypton_pay flows.
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

  const handleInterruptApprove = async (interruptId: string) => {
    const interruptResponses = [{
      interruptResponse: {
        interruptId: interruptId,
        response: "yes"
      }
    }]

    // Optimistic Clark message in the conversation stream
    const confirmedMessage: ChatMessage = {
      id: (Date.now() + Math.random()).toString(),
      type: 'assistant',
      content: 'Transaction confirmed.',
      timestamp: new Date(),
      success: true,
    }

    setMessages(prev => [...prev, confirmedMessage])

    // Hide the inline confirmation bubble by clearing interrupts
    setIsInterruptModalOpen(false)
    setInterrupts([])

    await handleSendMessage(interruptResponses)
  }

  const handleInterruptReject = async (interruptId: string) => {
    const interruptResponses = [{
      interruptResponse: {
        interruptId: interruptId,
        response: "no"
      }
    }]

    // Optimistic Clark messages in the conversation stream
    const rejectedMessage: ChatMessage = {
      id: (Date.now() + Math.random()).toString(),
      type: 'assistant',
      content: 'Transaction rejected.',
      timestamp: new Date(),
      success: true,
    }

    const processingMessage: ChatMessage = {
      id: (Date.now() + Math.random()).toString(),
      type: 'assistant',
      content: 'Updating your request…',
      timestamp: new Date(),
      success: false,
    }

    setMessages(prev => [...prev, rejectedMessage, processingMessage])

    // Hide the inline confirmation bubble by clearing interrupts
    setIsInterruptModalOpen(false)
    setInterrupts([])

    await handleSendMessage(interruptResponses)
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  return (
    <div className="min-h-screen w-full bg-[#001C1B] overflow-x-hidden">
      {/* Navbar */}
      <header className="fixed top-0 left-0 right-0 z-50 backdrop-blur-md bg-[#001C1B]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-2 min-h-[4rem]">
            <div className="flex items-center">
              <img
                src="/Krypton Clark.svg"
                alt="Krypton Logo"
                className="h-15 w-auto drop-shadow-[0_2px_8px_rgba(16,255,180,0.18)]"
              />
            </div>
            <div className="flex items-center space-x-3">
              <button
                onClick={() => setIsDevtoolsOpen(true)}
                className="flex items-center text-white px-4 py-2 rounded-xl transition-colors font-medium"
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
                  className="flex items-center text-white px-4 py-2 rounded-xl transition-colors font-medium"
                  aria-label="Open menu"
                >
                  <img
                    src="/Burger.svg"
                    alt="Burger"
                    className="h-6 w-auto drop-shadow-[0_2px_8px_rgba(16,255,180,0.18)]"
                  />
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>
      {/* Spacer for fixed navbar height */}
      <div className="h-24" />

      {/* Main Content Area - continuous feed */}
      <div className={`container mx-auto px-4 py-10 max-w-6xl relative z-0`}>
        

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
          <div ref={feedRef} className="max-h-[calc(100vh-6rem-8rem)] overflow-y-auto">
            <div className="pb-40">
              <ResultsDisplay messages={messages} isLoading={isLoading} username={userName} />
              {/* Show payment confirmation inline at the end of the conversation */}
              {interrupts && interrupts.length > 0 && (() => {
                const paymentInterrupt = interrupts.find((i) => i.name === 'krypton-pay-approval')
                if (!paymentInterrupt) return null
                const { reason } = paymentInterrupt
                const operation =
                  reason.operation === 'swap_and_transfer' ? 'Swap & Transfer' : 'Transfer'
                const fromToken = reason.from_token || reason.to_token
                const toToken = reason.to_token || ''
                return (
                  <div className="mb-4 flex gap-2 justify-start items-start">
                    <div className="w-8 h-8 flex items-center justify-center flex-shrink-0">
                      <img src="/clark process.svg" alt="Clark" className="h-8 w-8" />
                    </div>
                    <div className="max-w-[85%] rounded-2xl p-4 bg-teal-900/40 border border-teal-700/50 text-white backdrop-blur-sm">
                      <div className="text-[10px] uppercase tracking-[0.2em] text-teal-300/80 mb-2">
                        Payment confirmation
                      </div>
                      <p className="text-sm text-teal-100/90 mb-3">
                        Please review and confirm the payment details below.
                      </p>
                      <div className="bg-teal-900/60 rounded-lg p-3 border border-teal-700/40 space-y-2 text-sm">
                        {reason.operation === 'swap_and_transfer' && reason.from_token && (
                          <div className="flex justify-between items-center">
                            <span className="text-teal-200/80">Swap From:</span>
                            <span className="text-teal-100 font-medium">
                              {reason.from_token}
                            </span>
                          </div>
                        )}
                        <div className="flex justify-between items-center">
                          <span className="text-teal-200/80">Send Amount:</span>
                          <span className="text-teal-100 font-semibold">
                            {reason.received_amount} {toToken}
                          </span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-teal-200/80">To:</span>
                          <span className="text-teal-100 font-medium">
                            @{reason.receiver_username}
                          </span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-teal-200/80">Operation:</span>
                          <span className="text-teal-100 font-medium">{operation}</span>
                        </div>
                      </div>
                      <div className="flex gap-3 pt-3 mt-2">
                        <button
                          onClick={() => handleInterruptReject(paymentInterrupt.id)}
                          className="flex-1 inline-flex items-center justify-center px-3 py-2 rounded-xl border border-red-700/60 bg-red-900/30 text-red-100 hover:bg-red-900/50 text-sm font-medium transition-colors"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => handleInterruptApprove(paymentInterrupt.id)}
                          className="flex-1 inline-flex items-center justify-center px-3 py-2 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-sm font-medium transition-colors"
                        >
                          Confirm
                        </button>
                      </div>
                    </div>
                  </div>
                )
              })()}
            </div>
          </div>
        </div>
        
        {/* Prompts modal opened by left icon */}
        <Dialog open={isPromptModalOpen} onOpenChange={setIsPromptModalOpen}>
          <DialogContent className="sm:max-w-2xl bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 backdrop-blur-xl border border-white/15 rounded-2xl shadow-[0_20px_60px_rgba(0,0,0,0.6)]">
            <div className="max-h-[70vh] overflow-y-auto px-2">
              {(!selectedCategory) && (
                <div className="w-full flex flex-col items-center">
                  <div className="w-full max-w-md space-y-3">
                    {categories.map((category) => (
                      <button
                        key={category.id}
                        onClick={() => setSelectedCategory(category.id)}
                        className="w-full text-left p-4 rounded-xl bg-white/10 hover:bg-white/15 backdrop-blur-sm border border-white/15 hover:border-white/20 transition-all duration-200"
                      >
                        <div className="flex items-center gap-3">
                          {category.icon.startsWith('/') ? (
                            <img src={category.icon} alt={category.title} className="h-5 w-5" />
                          ) : (
                            <span className="text-lg">{category.icon}</span>
                          )}
                          <div className="min-w-0">
                            <div className="text-white font-medium truncate">{category.title}</div>
                            <div className="text-xs text-white/60 truncate">{category.description}</div>
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
                      className="mb-3 text-xs text-white/70 hover:text-white transition-colors"
                    >
                      ← Back
                    </button>
                    <div className="space-y-3">
                      {categories.find(c => c.id === selectedCategory)?.prompts.map((prompt, idx) => (
                        <button
                          key={idx}
                          onClick={() => handlePromptClick(prompt)}
                          disabled={isLoading}
                          className="w-full text-left p-4 rounded-xl bg-white/10 hover:bg-white/15 active:bg-white/20 backdrop-blur-sm border border-white/15 hover:border-white/20 transition-all duration-200 text-white disabled:opacity-50"
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
        userId={userId}
        userName={userName}
        sessionId={sessionId}
        sessionCost={sessionCost}
        overallCost={overallCost}
      />
    </div>
  )
}
