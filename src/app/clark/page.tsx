"use client"

import React, { useState, useEffect, useRef } from 'react'
import dynamic from 'next/dynamic'
import { Menu } from 'lucide-react'
import PromptGuideModal from './components/PromptGuideModal'
import agentsApi from '@/lib/agents_api'
import { useRouter } from 'next/navigation'
import { getAuth, signOut } from 'firebase/auth'
import { getFirebaseApp } from '@/lib/firebaseClient'
import HamburgerMenu from '@/components/wallet/HamburgerMenu'
import { ChatMessage } from './types'
import { categories } from './constants'
import CategoryTiles from './components/CategoryTiles'
import ChatInputBar from './components/ChatInterface'
import { createAssistantMessage } from './utils/createAssistantMessage'
import { parseErrorMessage } from '@/lib/parseError'

// Dynamically import heavy components to reduce initial bundle size
const ResultsDisplay = dynamic(() => import('./components/ResultsDisplay'), {
  loading: () => <div className="flex items-center justify-center p-8"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div></div>,
  ssr: false,
});

const DevtoolsOverlay = dynamic(() => import('./components/DevtoolsOverlay'), {
  loading: () => null,
  ssr: false,
});

/** Shape of an interrupt from the agents/query API (id may be empty) */
type InterruptFromApi = { id?: string; name?: string; reason?: Record<string, unknown> }

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
  const submittingInterruptRef = useRef(false)
  const shownInterruptIdsRef = useRef<Set<string>>(new Set())
  const queryQueueRef = useRef<Array<{ query: string }>>([])
  const [queueLength, setQueueLength] = useState(0)
  const [queueQueries, setQueueQueries] = useState<string[]>([])


  // Initialize session and user IDs on component mount
  useEffect(() => {
    // Get user data from localStorage (set during login)
    const storedUserData = localStorage.getItem('userData')
    if (storedUserData) {
      try {
        const parsedData = JSON.parse(storedUserData)
        setUserData(parsedData)
        // Extract username if available; use "krypton" for balance/history queries when not set
        if (parsedData.username) {
          setUserName(parsedData.username)
        } else {
          setUserName('krypton')
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
      // If no userData exists, use default fallback ID and username for balance queries
      setUserId('krypton_user')
      setUserName('krypton')
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
        const newSessionId = `session_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`
        setSessionId(newSessionId)
      }
    } catch (error) {
      console.error('Error loading expanded messages:', error)
      // Fallback to generating new session ID if loading fails
      const newSessionId = `session_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`
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
        username: userName || 'krypton',
        session_id: sessionId
      })

      const payload = response.data

      // Debug: log API response shape (dev only)
      if (typeof process !== 'undefined' && process.env.NODE_ENV === 'development') {
        const rd = payload?.data
        const bt = rd?.backtest_result ?? rd?.backtestResult ?? rd?.technical?.backtest_result ?? rd?.backtest?.backtest_result
        console.log('[Clark] agents/query response (prompt click):', {
          hasData: Boolean(rd),
          dataKeys: rd && typeof rd === 'object' ? Object.keys(rd) : [],
          hasBacktestResult: Boolean(bt),
        })
      }

      // Check for interrupts (dedupe by id so same HITL never shows twice)
      if (payload.stop_reason === 'interrupt' && payload.interrupts && payload.interrupts.length > 0) {
        const seen = shownInterruptIdsRef.current
        const newInterrupts = (payload.interrupts as InterruptFromApi[]).filter((i) => {
          const id = i?.id != null ? String(i.id) : ''
          if (id && seen.has(id)) return false
          if (id) seen.add(id)
          return true
        })
        if (newInterrupts.length > 0) {
          setInterrupts(newInterrupts)
          setIsInterruptModalOpen(true)
          setPendingInterruptResponse({
            query: routedPrompt,
            userMessage: userMessage
          })
        }
        setIsLoading(false)
        return
      }
      
      // Clear interrupt state if no interrupts
      shownInterruptIdsRef.current.clear()
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
      console.error('Clark API error:', error)
      const content = parseErrorMessage(error, "Sorry, I'm unable to process your request at the moment.")
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

  const handleSendMessage = async (interruptResponses?: any[], overrideQuery?: string) => {
    const queryText = overrideQuery ?? (interruptResponses ? (pendingInterruptResponse?.query || '') : inputValue)

    // For normal send: queue if already loading; otherwise need non-empty query. For HITL: only need not loading and pending context.
    if (interruptResponses?.length) {
      if (isLoading || !pendingInterruptResponse) return
      if (submittingInterruptRef.current) return
      submittingInterruptRef.current = true
    } else {
      // Normal send without override: if loading and user typed something, queue it and return
      if (!overrideQuery && isLoading && inputValue.trim()) {
        const q = inputValue.trim()
        queryQueueRef.current.push({ query: q })
        setQueueLength(prev => prev + 1)
        setQueueQueries(prev => [...prev, q])
        setInputValue('')
        return
      }
      if (!queryText.trim() || isLoading) return
    }

    const userMessage: ChatMessage = interruptResponses && pendingInterruptResponse
      ? pendingInterruptResponse.userMessage
      : {
          id: Date.now().toString(),
          type: 'user',
          content: queryText,
          timestamp: new Date(),
        }

    if (!interruptResponses) {
      setMessages(prev => [...prev, userMessage])
      if (!overrideQuery) setInputValue('')
    }
    
    setIsLoading(true)
    
    try {
      const requestBody: any = {
        user_id: userId,
        username: userName || 'krypton',
        session_id: sessionId
      }

      // If we have interrupt responses, send them as content blocks (and still send query for agent flow display)
      // Otherwise, send the query
      if (interruptResponses && interruptResponses.length > 0) {
        requestBody.content = interruptResponses
        if (queryText.trim()) requestBody.query = queryText
      } else {
        requestBody.query = queryText
      }

      const response = await agentsApi.post('/api/v1/agents/query', requestBody)

      const payload = response.data

      // Debug: log API response shape for backtest/technical (dev only)
      if (typeof process !== 'undefined' && process.env.NODE_ENV === 'development') {
        const rd = payload?.data
        const bt = rd?.backtest_result ?? rd?.backtestResult ?? rd?.technical?.backtest_result ?? rd?.backtest?.backtest_result
        console.log('[Clark] agents/query response:', {
          hasData: Boolean(rd),
          dataKeys: rd && typeof rd === 'object' ? Object.keys(rd) : [],
          hasBacktestResult: Boolean(bt),
          backtestShape: bt ? {
            data_points_len: Array.isArray(bt.data_points) ? bt.data_points.length : 'not-array',
            include_technical_analysis: bt.include_technical_analysis,
            technical_indicators_requested: bt.technical_indicators_requested,
            first_dp_indicators: Array.isArray(bt.data_points) && bt.data_points[0] ? Boolean((bt.data_points[0] as any).technical_indicators) : null,
          } : null,
        })
      }

      // Check for interrupts (dedupe by id so same HITL never shows twice)
      if (payload.stop_reason === 'interrupt' && payload.interrupts && payload.interrupts.length > 0) {
        const seen = shownInterruptIdsRef.current
        const newInterrupts = (payload.interrupts as InterruptFromApi[]).filter((i) => {
          const id = i?.id != null ? String(i.id) : ''
          if (id && seen.has(id)) return false
          if (id) seen.add(id)
          return true
        })
        if (newInterrupts.length > 0) {
          setInterrupts(newInterrupts)
          setIsInterruptModalOpen(true)
          setPendingInterruptResponse({
            query: queryText,
            userMessage: userMessage
          })
        }
        setIsLoading(false)
        return
      }
      
      // Clear interrupt state if no interrupts
      shownInterruptIdsRef.current.clear()
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
      console.error('Clark API error:', error)
      const content = parseErrorMessage(error, "Sorry, I'm unable to process your request at the moment.")
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content,
        timestamp: new Date(),
        success: false,
      }])
    } finally {
      if (interruptResponses?.length) submittingInterruptRef.current = false
      setIsLoading(false)
      // Process next from queue after state settles
      if (queryQueueRef.current.length > 0) {
        const next = queryQueueRef.current.shift()!
        setQueueLength(prev => Math.max(0, prev - 1))
        setQueueQueries(prev => prev.slice(1))
        setTimeout(() => handleSendMessage(undefined, next.query), 0)
      }
    }
  }

  const removeQueueItem = (index: number) => {
    if (index < 0 || index >= queryQueueRef.current.length) return
    queryQueueRef.current = queryQueueRef.current.filter((_, i) => i !== index)
    setQueueQueries(prev => prev.filter((_, i) => i !== index))
    setQueueLength(prev => Math.max(0, prev - 1))
  }

  const editQueueItem = (index: number, newQuery: string) => {
    const trimmed = newQuery.trim()
    if (index < 0 || index >= queryQueueRef.current.length || !trimmed) return
    queryQueueRef.current = queryQueueRef.current.map((item, i) =>
      i === index ? { query: trimmed } : item
    )
    setQueueQueries(prev => prev.map((q, i) => (i === index ? trimmed : q)))
  }

  const moveQueueItem = (index: number, direction: 'up' | 'down') => {
    const len = queryQueueRef.current.length
    if (len < 2 || index < 0 || index >= len) return
    const next = direction === 'up' ? index - 1 : index + 1
    if (next < 0 || next >= len) return
    const arr = [...queryQueueRef.current]
    ;[arr[index], arr[next]] = [arr[next], arr[index]]
    queryQueueRef.current = arr
    setQueueQueries(prev => {
      const copy = [...prev]
      ;[copy[index], copy[next]] = [copy[next], copy[index]]
      return copy
    })
  }

  const handleInterruptApprove = async (interruptId: string) => {
    const interruptResponses = [{
      interruptResponse: {
        interruptId: interruptId,
        response: "yes"
      }
    }]

    // Don't add optimistic "Transaction confirmed." here — the API response will add a single
    // assistant message with the real transaction card. Adding one here caused double render
    // and could show another user's transaction when the poll merged in other users' tx.

    // Hide the inline confirmation bubble by clearing interrupts
    shownInterruptIdsRef.current.clear()
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
    shownInterruptIdsRef.current.clear()
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

  const showCategoryTiles =
    !messages.some((m) => m.type === 'user') &&
    !messages.some((m) => m.backtestResult) &&
    !isPromptModalOpen

  return (
    <div className="min-h-screen w-full bg-[#001C1B] overflow-x-hidden">
      {/* Navbar */}
      <header className="fixed top-0 left-0 right-0 z-50 backdrop-blur-md bg-[#001C1B]">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between py-2 min-h-[4rem]">
            <div className="flex justify-start">
              <button
                onClick={() => setIsDevtoolsOpen(true)}
                className="flex items-center text-white px-4 py-2 rounded-xl transition-colors font-medium"
                aria-label="Open devtools"
              >
                <img
                  src="/devtools.svg"
                  alt="Devtools"
                  className="h-6 w-6"
                />
              </button>
            </div>
            <div className="flex justify-center flex-1">
              <img
                src="/Krypton Clark.svg"
                alt="Krypton Logo"
                className="h-12 sm:h-16 md:h-20 w-auto drop-shadow-[0_2px_8px_rgba(16,255,180,0.18)]"
              />
            </div>
            <div className="flex justify-end">
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
      </header>
      {/* Spacer for fixed navbar height */}
      <div className="h-24" />

      {/* Main Content Area - continuous feed */}
      <div className="container mx-auto px-4 py-10 max-w-6xl relative z-0">
        {/* Category Tiles - hidden when prompt modal is open so a single card click doesn't fire both modal and tiles */}
        {showCategoryTiles && (
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
          <div ref={feedRef} className="scrollbar-minimal min-h-[200px] max-h-[calc(100vh-6rem-8rem)] overflow-y-auto scroll-smooth">
            <div className="pb-40">
              {/* Loading with no messages yet: show "Thinking…"; once messages exist, ResultsDisplay shows "Processing your request..." */}
              {isLoading && messages.length === 0 && (
                <div className="flex gap-2 justify-start items-center py-4">
                  <div className="w-8 h-8 flex items-center justify-center flex-shrink-0">
                    <img src="/clark process.svg" alt="Clark" className="h-8 w-8 animate-pulse" />
                  </div>
                  <div className="rounded-2xl px-4 py-3 bg-zinc-900/30 border border-zinc-700/40 text-white/80 text-sm">
                    Thinking…
                  </div>
                </div>
              )}
              <ResultsDisplay messages={messages} isLoading={isLoading} username={userName} />
              {/* When messages exist, loading state is shown inside ResultsDisplay as "Processing your request..." */}
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
                    <div className="max-w-[85%] rounded-2xl p-4 bg-zinc-900/40 border border-zinc-700/50 text-white backdrop-blur-sm">
                      <div className="text-[10px] uppercase tracking-[0.2em] text-white/80 mb-2">
                        Payment confirmation
                      </div>
                      <p className="text-sm text-white/90 mb-3">
                        Please review and confirm the payment details below.
                      </p>
                      <div className="bg-zinc-900/60 rounded-lg p-3 border border-zinc-700/40 space-y-2 text-sm">
                        {reason.operation === 'swap_and_transfer' && reason.from_token && (
                          <div className="flex justify-between items-center">
                            <span className="text-white/80">Swap From:</span>
                            <span className="text-white font-medium">
                              {reason.from_token}
                            </span>
                          </div>
                        )}
                        <div className="flex justify-between items-center">
                          <span className="text-white/80">Send Amount:</span>
                          <span className="text-white font-semibold">
                            {reason.received_amount} {toToken}
                          </span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-white/80">To:</span>
                          <span className="text-white font-medium">
                            @{reason.receiver_username}
                          </span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-white/80">Operation:</span>
                          <span className="text-white font-medium">{operation}</span>
                        </div>
                      </div>
                      <div className="flex gap-3 pt-3 mt-2">
                        <button
                          type="button"
                          onClick={() => handleInterruptReject(paymentInterrupt.id)}
                          className="flex-1 inline-flex items-center justify-center px-3 py-2 rounded-xl border border-red-700/60 bg-red-900/30 text-red-100 hover:bg-red-900/50 text-sm font-medium transition-colors"
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          onClick={() => handleInterruptApprove(paymentInterrupt.id)}
                          className="flex-1 inline-flex items-center justify-center px-3 py-2 rounded-xl bg-white/20 hover:bg-white/30 text-white text-sm font-medium transition-colors border border-white/20"
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
        
      {/* Prompts modal opened by left icon - shared with MiniClark */}
      <PromptGuideModal
        open={isPromptModalOpen}
        onOpenChange={setIsPromptModalOpen}
        categories={categories}
        selectedCategory={selectedCategory}
        onSelectCategory={setSelectedCategory}
        onPromptClick={handlePromptClick}
        isLoading={isLoading}
      />
      </div>

      {/* Chat Input Bar - fixed at bottom */}
      <ChatInputBar
        inputValue={inputValue}
        setInputValue={setInputValue}
        isLoading={isLoading}
        onSendMessage={() => handleSendMessage()}
        onKeyPress={handleKeyPress}
        onOpenPromptModal={() => {
          setSelectedCategory(null)
          setIsPromptModalOpen(true)
        }}
        queueLength={queueLength}
        queueQueries={queueQueries}
        onRemoveQueueItem={removeQueueItem}
        onEditQueueItem={editQueueItem}
        onMoveQueueItem={moveQueueItem}
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
