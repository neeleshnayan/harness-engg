"use client"

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import dynamic from 'next/dynamic'
import { PanelLeft, PanelRight } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import PromptGuideModal from './components/PromptGuideModal'
import agentsApi from '@/lib/agents_api'
import { kryptonWeb3Api } from '@/lib/api'
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
import { useWebSocket } from '@/hooks/useWebSocket'
import PastConversationsTab from './components/PastConversationsTab'
import { streamAgentQuery, type LogLine, type TraceStep } from '@/lib/agents_stream'
import LiveTurn from './components/LiveTurn'
import { ThemeToggle } from './studio/ThemeToggle'

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

/** Desktop history sidebar. Declared once because three things need to agree
 *  on it: the aside's own width, its animation target, and the left offset of
 *  the docked composer. */
const SIDEBAR_WIDTH = 260

/** Session log ceiling. Roughly forty turns of a busy conversation; past that
 *  the oldest lines are the ones least likely to be wanted. */
const SESSION_LOG_MAX = 800

/** Where the under-the-hood log lives between reloads. Per-tab (sessionStorage),
 *  one fixed key — see the restore effect for why it is not per-session-id. */
const TERMINAL_LOG_KEY = 'clark-terminal-log'

export default function BacktestPage() {
  const router = useRouter()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isHistoryLoading, setIsHistoryLoading] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [showMenu, setShowMenu] = useState(false)
  const [isPromptModalOpen, setIsPromptModalOpen] = useState(false)
  const [isDevtoolsOpen, setIsDevtoolsOpen] = useState(false)
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0)
  const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false)
  const feedRef = useRef<HTMLDivElement>(null)

  // Session management for mem0 integration
  const [userId, setUserId] = useState<string>('')
  const [userName, setUserName] = useState<string>('')
  /** Set on the client only. The server has no idea what time it is where the
   *  operator is, so rendering a time-of-day greeting during SSR guarantees a
   *  hydration mismatch; empty until mounted, and the greeting reads as a bare
   *  "Good ." for one frame otherwise. */
  const [hourBand, setHourBand] = useState<'' | 'morning' | 'afternoon' | 'evening'>('')
  const [isWideViewport, setIsWideViewport] = useState(false)
  /** What Clark is doing right now — cleared the moment the turn commits. */
  const [liveTrace, setLiveTrace] = useState<TraceStep[]>([])
  /** The same trace, in a ref, because the commit reads it from inside an async
   *  handler. `handleSendMessage` closes over `liveTrace` at the render it was
   *  created in, so by the time the stream finishes that variable still holds
   *  the empty array the turn started with — the live gutter filled in and the
   *  committed message got no citations at all. State drives the render; the
   *  ref is what the handler is allowed to read. */
  const liveTraceRef = useRef<TraceStep[]>([])
  const [liveText, setLiveText] = useState('')
  /** Every event of the session, oldest first, across every turn — not one
   *  turn's worth. It lives here rather than in the message flow so it keeps
   *  filling as the conversation goes back and forth, and so closing the
   *  devtools panel does not throw the history away.
   *
   *  Capped: a long session would otherwise grow this without bound and the
   *  oldest lines are the ones least likely to be wanted. */
  const [sessionLog, setSessionLog] = useState<LogLine[]>([])
  const sessionLogRef = useRef<LogLine[]>([])
  /** Just the turn in flight; folded into the session log when it ends. */
  const turnLogRef = useRef<LogLine[]>([])
  const [sessionId, setSessionId] = useState<string>('')

  // The log survives a reload but not a new conversation. The key is fixed and
  // per-tab, NOT per-session-id: every page load mints a fresh sessionId (see
  // the init effect below), so a session-keyed entry could never be found
  // again — the first version of this was keyed that way and restored nothing.
  // Instead F5 keeps the log because sessionStorage is per-tab, and "New Chat"
  // clears it explicitly in resetClarkSessionState, which is the one moment
  // the operator has said "this is a different conversation now".
  //
  // Deliberately NOT localStorage — a fund operator's tool-call history, with
  // argument values, should not outlive the tab that produced it.
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(TERMINAL_LOG_KEY)
      if (raw) {
        const lines = JSON.parse(raw) as LogLine[]
        if (Array.isArray(lines) && lines.length > 0) {
          sessionLogRef.current = lines
          setSessionLog(lines)
        }
      }
    } catch { /* a corrupt entry costs the history, never the page */ }
  }, [])

  useEffect(() => {
    if (sessionLog.length === 0) return
    try {
      sessionStorage.setItem(TERMINAL_LOG_KEY, JSON.stringify(sessionLog))
    } catch { /* quota exceeded: keep running, drop persistence */ }
  }, [sessionLog])
  const [userData, setUserData] = useState<any>(null)
  const [walletAddress, setWalletAddress] = useState<string>('')

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

  // Track whether we already initialized from a mini-chat expansion so we
  // don't override that state with Firebase last-chat data.
  const initializedFromExpansionRef = useRef(false)

  /** Fold one turn's log into the session's, renumbering so React keys stay
   *  unique across turns — the stream restarts `seq` at 0 every time. */
  const appendTurnLog = useCallback((lines: LogLine[], base: LogLine[]) => {
    const merged = [...base, ...lines.map((l, i) => ({ ...l, seq: base.length + i }))]
    return merged.length > SESSION_LOG_MAX ? merged.slice(-SESSION_LOG_MAX) : merged
  }, [])

  /** Turn the finished trace into marks that travel with the message.
   *  Only completed steps: a tool still in flight has no duration to cite, and
   *  a mark that says "pending" forever is worse than no mark. */
  const provenanceFrom = useCallback((steps: TraceStep[]) =>
    steps
      .filter((s) => s.endedAt != null)
      .map((s) => ({
        id: s.id,
        tool: s.name,
        input: s.input,
        ok: s.ok !== false,
        ms: s.endedAt != null ? s.endedAt - s.startedAt : undefined,
      })), [])

  const persistLastChat = React.useCallback(
    async (allMessages: ChatMessage[]) => {
      if (!userId) return

      try {
        const payload = {
          user_id: userId,
          session_id: sessionId,
          // Persist full message shape (including structured results for plots/charts).
          // Backend will sanitize for Firestore compatibility.
          messages: allMessages.map((msg) => ({
            id: msg.id,
            type: msg.type,
            content: msg.content,
            timestamp: msg.timestamp instanceof Date ? msg.timestamp.toISOString() : msg.timestamp,
            success: msg.success,
            source: msg.source,
            capabilitiesSummary: msg.capabilitiesSummary,
            parsedIntent: msg.parsedIntent,
            parameterRequest: msg.parameterRequest,
            agentFlow: msg.agentFlow,
            backtestResult: msg.backtestResult,
            screenerResult: msg.screenerResult,
            economicResult: msg.economicResult,
            regulationResult: msg.regulationResult,
            priceHistoryResult: msg.priceHistoryResult,
            balanceResult: msg.balanceResult,
            // Persisted so a reloaded conversation keeps its citations. An
            // answer whose provenance vanishes on refresh is an answer you
            // cannot check tomorrow, which is most of the point.
            provenance: msg.provenance,
          })),
        }
        // Fire and forget; errors are logged to console only.
        await agentsApi.post('/api/v1/agents/clark-chat', payload)
      } catch (error) {
        console.error('Error persisting Clark last chat:', error)
      }
    },
    [userId, sessionId]
  )
  const submittingInterruptRef = useRef(false)
  const shownInterruptIdsRef = useRef<Set<string>>(new Set())
  const queryQueueRef = useRef<Array<{ query: string }>>([])
  const [queueLength, setQueueLength] = useState(0)
  const [queueQueries, setQueueQueries] = useState<string[]>([])
  const txEventsRef = useRef<Map<string, any>>(new Map())
  const txWaitersRef = useRef<Map<string, Array<(event: any | null) => void>>>(new Map())


  // Time of day, read on the client where the operator actually is.
  useEffect(() => {
    const h = new Date().getHours()
    setHourBand(h < 12 ? 'morning' : h < 18 ? 'afternoon' : 'evening')
  }, [])

  // The sidebar only exists at lg and up (`hidden lg:flex`), so the docked
  // composer's left offset has to track the breakpoint as well as the toggle.
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 1024px)')
    const sync = () => setIsWideViewport(mq.matches)
    sync()
    mq.addEventListener('change', sync)
    return () => mq.removeEventListener('change', sync)
  }, [])

  // Initialize session and user IDs on component mount
  useEffect(() => {
    // Get user data from localStorage (set during login)
    const storedUserData = localStorage.getItem('userData')
    if (storedUserData) {
      try {
        const parsedData = JSON.parse(storedUserData)
        setUserData(parsedData)
        if (parsedData.wallet_address) {
          setWalletAddress(parsedData.wallet_address)
        }
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
      setWalletAddress('')
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
        initializedFromExpansionRef.current = true

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

  const clarkWsUrl = useMemo(() => {
    if (!walletAddress) return ''
    const baseUrl =
      process.env.NEXT_PUBLIC_KRYPTON_WEB3_WS_URL ||
      (process.env.NEXT_PUBLIC_KRYPTON_WEB3_API_URL
        ? process.env.NEXT_PUBLIC_KRYPTON_WEB3_API_URL.replace('https://', 'wss://').replace('http://', 'ws://')
        : 'wss://web3.kryptonfund.com')
    return `${baseUrl}/ws?wallet_address=${encodeURIComponent(walletAddress)}`
  }, [walletAddress])

  const handleClarkTxWsMessage = useCallback((message: any) => {
    const eventType = String(message?.type || '')
    if (eventType !== 'transaction_update' && eventType !== 'transaction_confirmed') return
    const txId = String(message?.transaction_id || '').trim()
    if (!txId) return
    txEventsRef.current.set(txId, message)
    const waiters = txWaitersRef.current.get(txId) || []
    waiters.forEach((resolve) => resolve(message))
    txWaitersRef.current.delete(txId)
  }, [])

  useWebSocket(clarkWsUrl, { onMessage: handleClarkTxWsMessage })

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
      // Same streaming path as a typed message — a prompt tile should not be
      // a second-class way to ask a question.
      const streamBody = {
        query: routedPrompt,
        user_id: userId,
        username: userName || 'krypton',
        session_id: sessionId,
      }
      let payload: any
      liveTraceRef.current = []
      setLiveTrace([])
      setLiveText('')
      turnLogRef.current = []
      try {
        payload = await streamAgentQuery(streamBody, {
          onTrace: (steps) => { liveTraceRef.current = steps; setLiveTrace(steps) },
          onText: setLiveText,
          onLog: (lines) => {
            turnLogRef.current = lines
            setSessionLog(appendTurnLog(lines, sessionLogRef.current))
          },
        })
      } catch (streamErr) {
        console.warn('[Clark] stream unavailable, falling back to /query:', streamErr)
        setLiveTrace([])
        setLiveText('')
        const response = await agentsApi.post('/api/v1/agents/query', streamBody)
        payload = response.data
      }

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

      // Check for interrupts (even when the interrupt array is temporarily empty)
      if (payload.stop_reason === 'interrupt') {
        const seen = shownInterruptIdsRef.current
        const interruptItems = Array.isArray(payload.interrupts) ? (payload.interrupts as InterruptFromApi[]) : []
        const newInterrupts = interruptItems.filter((i) => {
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
        } else {
          setMessages(prev => [...prev, {
            id: (Date.now() + Math.random()).toString(),
            type: 'assistant',
            content: 'Approval is required, but no confirmation payload was returned. Please resend the payment request.',
            timestamp: new Date(),
            success: false,
          }])
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
      if (liveTraceRef.current.length > 0) {
        assistantMessage.provenance = provenanceFrom(liveTraceRef.current)
      }


      // Append Clark's response so ResultsDisplay can render results/backtests/etc.
      setMessages(prev => {
        const updated = [...prev, assistantMessage]
        void persistLastChat(updated)
        return updated
      })
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
      sessionLogRef.current = appendTurnLog(turnLogRef.current, sessionLogRef.current)
      setSessionLog(sessionLogRef.current)
      turnLogRef.current = []
      setLiveTrace([])
      setLiveText('')
    }
  }

  const handleSendMessage = async (interruptResponses?: any[], overrideQuery?: string): Promise<any | null> => {
    const queryText = overrideQuery ?? (interruptResponses ? (pendingInterruptResponse?.query || '') : inputValue)

    // For normal send: queue if already loading; otherwise need non-empty query. For HITL: only need not loading and pending context.
    if (interruptResponses?.length) {
      if (isLoading || !pendingInterruptResponse) return null
      if (submittingInterruptRef.current) return null
      submittingInterruptRef.current = true
    } else {
      // Normal send without override: if loading and user typed something, queue it and return
      if (!overrideQuery && isLoading && inputValue.trim()) {
        const q = inputValue.trim()
        queryQueueRef.current.push({ query: q })
        setQueueLength(prev => prev + 1)
        setQueueQueries(prev => [...prev, q])
        setInputValue('')
        return null
      }
      if (!queryText.trim() || isLoading) return null
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

      // Stream the turn. The `complete` payload is identical to what
      // /agents/query returns, so everything below this line is unchanged —
      // the stream only adds what the operator sees while they wait.
      //
      // Falls back to the blocking endpoint on any transport failure: a proxy
      // that mishandles SSE should cost a progress animation, not the answer.
      let payload: any
      liveTraceRef.current = []
      setLiveTrace([])
      setLiveText('')
      turnLogRef.current = []
      try {
        payload = await streamAgentQuery(requestBody, {
          onTrace: (steps) => { liveTraceRef.current = steps; setLiveTrace(steps) },
          onText: setLiveText,
          onLog: (lines) => {
            turnLogRef.current = lines
            setSessionLog(appendTurnLog(lines, sessionLogRef.current))
          },
        })
      } catch (streamErr) {
        console.warn('[Clark] stream unavailable, falling back to /query:', streamErr)
        setLiveTrace([])
        setLiveText('')
        const response = await agentsApi.post('/api/v1/agents/query', requestBody)
        payload = response.data
      }

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

      // Check for interrupts (even when the interrupt array is temporarily empty)
      if (payload.stop_reason === 'interrupt') {
        const seen = shownInterruptIdsRef.current
        const interruptItems = Array.isArray(payload.interrupts) ? (payload.interrupts as InterruptFromApi[]) : []
        const newInterrupts = interruptItems.filter((i) => {
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
        } else {
          setMessages(prev => [...prev, {
            id: (Date.now() + Math.random()).toString(),
            type: 'assistant',
            content: 'Approval is required, but no confirmation payload was returned. Please resend the payment request.',
            timestamp: new Date(),
            success: false,
          }])
        }
        setIsLoading(false)
        return payload
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
      if (liveTraceRef.current.length > 0) {
        assistantMessage.provenance = provenanceFrom(liveTraceRef.current)
      }

      // Always append Clark's response; ResultsDisplay will decide what to show,
      // including any transaction status cards for krypton_pay flows.
      setMessages(prev => {
        const updated = [...prev, assistantMessage]
        void persistLastChat(updated)
        return updated
      })
      return payload
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
      return null
    } finally {
      if (interruptResponses?.length) submittingInterruptRef.current = false
      setIsLoading(false)
      // Fold this turn into the session's log and make it the new base, so the
      // next turn appends after it instead of replacing it.
      sessionLogRef.current = appendTurnLog(turnLogRef.current, sessionLogRef.current)
      setSessionLog(sessionLogRef.current)
      turnLogRef.current = []
      // The live view hands off to the committed message; leaving it on screen
      // would show the same answer twice for a frame.
      setLiveTrace([])
      setLiveText('')
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

  const _sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

  const _extractTransactionIdFromPayload = (payload: any): string | undefined => {
    const direct = String(payload?.data?.transaction_id || '').trim()
    if (direct) return direct
    const nodes = Array.isArray(payload?.agent_flow?.nodes) ? payload.agent_flow.nodes : []
    for (const node of nodes) {
      const nodeTxId = String(node?.output?.data?.transaction_id || '').trim()
      if (nodeTxId) return nodeTxId
    }
    return undefined
  }

  const _waitForTransactionEvent = async (txId: string, timeoutMs = 8000): Promise<any | null> => {
    if (!txId) return null
    const existing = txEventsRef.current.get(txId)
    if (existing) return existing
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        const waiters = txWaitersRef.current.get(txId) || []
        txWaitersRef.current.set(txId, waiters.filter((r) => r !== resolve))
        resolve(null)
      }, timeoutMs)
      const wrappedResolve = (event: any | null) => {
        clearTimeout(timer)
        resolve(event)
      }
      const waiters = txWaitersRef.current.get(txId) || []
      txWaitersRef.current.set(txId, [...waiters, wrappedResolve])
    })
  }

  const _appendCanonicalActiveTransaction = async (operationHint?: string) => {
    const username = userName || 'krypton'
    if (!username) return
    try {
      let tx: any = null
      for (let attempt = 0; attempt < 4; attempt++) {
        if (attempt > 0) await _sleep(1500)
        const response = await kryptonWeb3Api.get(
          `/circle/active-transactions/${encodeURIComponent(username)}`
        )
        const txs = Array.isArray(response?.data?.transactions) ? response.data.transactions : []
        if (!txs.length) continue
        tx = txs
          .slice()
          .sort((a: any, b: any) => Number(b?.created_at || 0) - Number(a?.created_at || 0))[0]
        if (tx?.transaction_id) break
      }
      if (!tx?.transaction_id) return

      const txOperation = operationHint || tx.operation || (tx.tx_type === 'swap' ? 'swap_and_transfer' : 'direct_transfer')
      const txData = {
        transaction_id: tx.transaction_id,
        status: String(tx.status || 'SUBMITTED').toUpperCase(),
        operation: txOperation,
        token: tx.to_token || tx.from_token || tx.token_symbol,
        amount: tx.amount,
        received_amount: tx.received_amount,
        to_address: tx.to_address,
        to_username: tx.to_username,
        tx_hash: tx.tx_hash,
        created_at: tx.created_at,
        kind: tx.kind,
        tx_type: tx.tx_type,
      }
      const payload = {
        success: true,
        message: 'Transaction submitted.',
        parsed_intent: {
          agent_ids: ['krypton_pay'],
          operation: txOperation,
          // Include transaction fields so ResultsDisplay can extract inlineTxData
          transaction_id: tx.transaction_id,
          status: txData.status,
          token: txData.token,
          amount: txData.amount,
          received_amount: tx.received_amount,
          from_address: tx.from_address,
          to_address: tx.to_address,
          tx_hash: tx.tx_hash,
          created_at: tx.created_at,
        },
        data: txData,
        // Include synthetic agent_flow so ResultsDisplay can detect the krypton_pay transaction node
        agent_flow: {
          nodes: [{
            id: 'krypton_pay',
            name: 'Krypton Pay Agent',
            type: 'specialized',
            tool_name: 'consult_krypton_pay',
            status: 'completed',
            output: { success: true, data: txData },
          }],
          edges: [],
          execution_order: ['krypton_pay'],
          flow_type: 'single',
        },
      }
      const assistantMessage = createAssistantMessage(payload)
      if (liveTraceRef.current.length > 0) {
        assistantMessage.provenance = provenanceFrom(liveTraceRef.current)
      }
      setMessages((prev) => {
        const alreadyRendered = prev.some((m) => {
          const nodes = (m.agentFlow && 'nodes' in (m.agentFlow as any))
            ? (m.agentFlow as any).nodes
            : (Array.isArray(m.agentFlow) ? m.agentFlow : [])
          return Array.isArray(nodes) && nodes.some((n: any) => n?.output?.data?.transaction_id === tx.transaction_id)
        })
        if (alreadyRendered) return prev
        return [...prev, assistantMessage]
      })
    } catch (err) {
      console.warn('Clark reconcile: failed to fetch active transactions', err)
    }
  }

  const handleInterruptApprove = async (interruptId: string, reason?: Record<string, unknown>) => {
    const fallbackReason =
      reason ??
      (interrupts.find((i) => String(i?.id ?? '') === String(interruptId))?.reason as Record<string, unknown> | undefined) ??
      { operation: 'direct_transfer' }
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

    const payload = await handleSendMessage(interruptResponses)
    const txId = _extractTransactionIdFromPayload(payload)
    if (txId) {
      await _waitForTransactionEvent(txId, 8000)
    }
    await _appendCanonicalActiveTransaction(fallbackReason?.operation as string | undefined)
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

  /** Nothing has happened yet: no messages, nothing loading. The layout
   *  centres itself in this state instead of reserving a screen of empty
   *  feed under the tiles. */
  const isLanding =
    showCategoryTiles && messages.length === 0 && !isLoading && !isHistoryLoading

  const firstName = userName ? userName.split(' ')[0] : ''
  const greeting = !hourBand
    ? firstName
      ? `Hello, ${firstName}.`
      : 'Hello.'
    : firstName
      ? `Good ${hourBand}, ${firstName}.`
      : `Good ${hourBand}.`

  const resetClarkSessionState = useCallback(() => {
    // New conversation — the persisted terminal log belongs to the old one.
    sessionLogRef.current = []
    turnLogRef.current = []
    setSessionLog([])
    try { sessionStorage.removeItem(TERMINAL_LOG_KEY) } catch { /* nothing to clear */ }
    shownInterruptIdsRef.current.clear()
    setInterrupts([])
    setIsInterruptModalOpen(false)
    setPendingInterruptResponse(null)
    queryQueueRef.current = []
    setQueueLength(0)
    setQueueQueries([])
    submittingInterruptRef.current = false
    const newSessionId = `session_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`
    setSessionId(newSessionId)
    setMessages([])
    setSessionCost(0)
    setInputValue('')
    initializedFromExpansionRef.current = false
  }, [])

  const handleNewChat = useCallback(async () => {
    if (messages.length > 0 && userId) {
      await persistLastChat(messages)
    }
    resetClarkSessionState()
    setHistoryRefreshKey((k) => k + 1)
  }, [messages, userId, persistLastChat, resetClarkSessionState])

  const handleActiveSessionDeleted = useCallback(() => {
    resetClarkSessionState()
    setHistoryRefreshKey((k) => k + 1)
  }, [resetClarkSessionState])

  const handleLoadConversationFromHistory = async (
    historySessionId: string,
    historyMessages: ChatMessage[],
    sessionCondensedMemory?: unknown[],
    sessionCondensedSummary?: string
  ) => {
    // When loading a conversation from history, restore its session memory and summary
    // on the backend so subsequent queries and the Memories tab have that context.
    // For older conversations without stored session_condensed_memory, send messages so
    // the backend can build and summarize session memory from them.
    if (userId) {
      try {
        const hasStoredMemory = Array.isArray(sessionCondensedMemory) && sessionCondensedMemory.length > 0
        const payload: Record<string, unknown> = {
          user_id: userId,
          session_id: historySessionId,
          session_condensed_memory: sessionCondensedMemory ?? [],
          session_condensed_summary: sessionCondensedSummary ?? undefined,
        }
        if (!hasStoredMemory && historyMessages.length > 0) {
          payload.messages = historyMessages.map((m) => ({
            id: m.id,
            type: m.type,
            content: m.content,
            timestamp: m.timestamp instanceof Date ? m.timestamp.toISOString() : m.timestamp,
          }))
        }
        await agentsApi.post('/api/v1/agents/restore-session-memory', payload)
      } catch (err) {
        console.error('Error restoring session memory for conversation:', err)
      }
    }
    initializedFromExpansionRef.current = true
    setSessionId(historySessionId)
    setMessages(historyMessages)
  }

  const handleMobileLoadConversation: typeof handleLoadConversationFromHistory = async (
    historySessionId,
    historyMessages,
    sessionCondensedMemory,
    sessionCondensedSummary
  ) => {
    await handleLoadConversationFromHistory(
      historySessionId,
      historyMessages,
      sessionCondensedMemory,
      sessionCondensedSummary
    )
    setIsMobileHistoryOpen(false)
  }

  return (
    <div className="min-h-screen w-full bg-[var(--kt-bg)] overflow-x-hidden">
      {/* Navbar */}
      <header className="fixed top-0 left-0 right-0 z-50 border-b border-[var(--kt-border)] bg-[var(--kt-bg)]/90 backdrop-blur-md">
        {/* Full width, not max-w-6xl. This is chrome: it spans the shell, and
         *  a centred 1152px box inside a viewport that also holds a left
         *  sidebar put the mark nowhere in particular. Mark left, actions
         *  right — the bar now has two ends instead of a floating middle. */}
        <div className="px-4 sm:px-6">
          <div className="flex items-center justify-between gap-3 py-2.5">
            <div className="flex min-w-0 items-center gap-2">
              <button
                type="button"
                onClick={() => setIsMobileHistoryOpen((open) => !open)}
                className="lg:hidden flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--kt-border)] text-[var(--kt-text-muted)] transition-colors hover:bg-[var(--kt-hover)] hover:text-[var(--kt-text)]"
                title={isMobileHistoryOpen ? 'Hide conversation history' : 'Show conversation history'}
                aria-expanded={isMobileHistoryOpen}
                aria-label={isMobileHistoryOpen ? 'Hide conversation history' : 'Show conversation history'}
              >
                {isMobileHistoryOpen ? (
                  <PanelLeft className="h-4 w-4" />
                ) : (
                  <PanelRight className="h-4 w-4" />
                )}
              </button>
              <img src="/Krypton Clark.svg" alt="Krypton Clark" className="h-7 w-auto" />
            </div>
            <div className="flex items-center gap-1">
              {/* The provider already wraps /clark (see clark/layout.tsx), so
                  every token here has a light value — only the control was
                  missing. Same component as the Studio uses, deliberately:
                  two toggles that set the same key would drift. */}
              <ThemeToggle />
              <button
                onClick={() => setShowMenu(!showMenu)}
                className="flex h-9 w-9 items-center justify-center rounded-lg text-[var(--kt-text-muted)] transition-colors hover:bg-[var(--kt-hover)] hover:text-[var(--kt-text)]"
                aria-label="Open menu"
              >
                <img src="/Burger.svg" alt="" aria-hidden className="h-5 w-auto opacity-80" />
              </button>
            </div>
          </div>
        </div>
      </header>
      {/* Spacer for fixed navbar height */}

      {/* Main Content Area - full width so past conversations can sit flush left */}
      <div className="w-full flex relative">
        {/* Sidebar Toggle Button - floating to the left of the divider, animates with sidebar */}
        <motion.button
          initial={false}
          animate={{ left: isSidebarOpen ? 212 : 16 }}
          transition={{ type: 'spring', damping: 25, stiffness: 200 }}
          onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          className="hidden lg:flex fixed top-2 z-[100] items-center justify-center w-8 h-8 rounded-lg bg-[var(--kt-bg)]/80 backdrop-blur-md hover:bg-[var(--kt-hover)] text-[var(--kt-text-muted)] hover:text-[var(--kt-text-strong)] transition-colors border border-[var(--kt-border)]"
          title={isSidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
        >
          {isSidebarOpen ? <PanelLeft className="h-5 w-5" /> : <PanelRight className="h-5 w-5" />}
        </motion.button>

        {/* Left: Past conversations column - collapsible on desktop, hidden on mobile */}
        <AnimatePresence initial={false}>
          {isSidebarOpen && (
            <motion.aside
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 260, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              className="hidden lg:flex lg:flex-col lg:w-[260px] lg:flex-shrink-0 lg:pl-4 lg:pr-3 lg:pt-6 lg:pb-6 lg:border-r border-[var(--kt-border)] overflow-hidden relative z-[90] bg-[var(--kt-surface)]"
            >
              <PastConversationsTab
                userId={userId}
                refreshTrigger={historyRefreshKey}
                onLoadConversation={handleLoadConversationFromHistory}
                onHistoryLoadingChange={setIsHistoryLoading}
                onOpenDevtools={() => setIsDevtoolsOpen(true)}
                activeSessionId={sessionId}
                activeMessages={messages}
                onNewChat={handleNewChat}
                onActiveSessionDeleted={handleActiveSessionDeleted}
              />
            </motion.aside>
          )}
        </AnimatePresence>

        {/* Right: Centered main content (tiles + feed).
         *
         * Two states, not one. On an empty session the feed used to render
         * anyway at a hard `h-[calc(100vh-10rem)]`, so the tiles sat jammed
         * under the header with a full screen of reserved-but-empty scroll
         * area beneath them — the void. Landing centres what little there is
         * and reserves nothing; the conversation state gets the tall feed. */}
        <div
          className={`flex-1 min-w-0 flex flex-col px-6 relative items-center ${
            isLanding ? "justify-center pb-28 pt-16" : "pt-20"
          }`}
        >
          <div className="w-full max-w-[820px] min-w-0 relative">
            {/* Category Tiles - hidden when prompt modal is open so a single card click doesn't fire both modal and tiles */}
            {showCategoryTiles && (
              <>
                {isLanding && (
                  <div className="mb-6">
                    <h1 className="text-[22px] font-medium tracking-tight text-[var(--kt-text)]">
                      {greeting}
                    </h1>
                    <p className="mt-1 text-sm text-[var(--kt-text-muted)]">
                      Ask about the fund, or start from one of these.
                    </p>
                  </div>
                )}
                <CategoryTiles
                  categories={categories}
                  selectedCategory={selectedCategory}
                  onCategorySelect={(categoryId) => setSelectedCategory(categoryId || null)}
                  onPromptClick={handlePromptClick}
                  isLoading={isLoading}
                />
              </>
            )}

            {/* Continuous Feed: scrollable area bounded by navbar (top) and chat input (bottom) */}
            <div className={`dark w-full ${isLanding ? "hidden" : "mt-12"}`}>
              <div
                ref={feedRef}
                className="scrollbar-minimal min-h-[200px] h-[calc(100vh-10rem)] overflow-y-auto scroll-smooth"
              >
                <div className="pb-32">
                  {isHistoryLoading ? (
                    <div className="w-full flex flex-col items-center justify-center py-16 min-h-[calc(100vh-10rem)]">
                      <div className="w-12 h-12 flex items-center justify-center flex-shrink-0">
                        <img src="/clark process.svg" alt="Clark" className="h-12 w-12 animate-pulse" />
                      </div>
                      <div className="mt-4 rounded-2xl px-6 py-3 bg-[var(--kt-inset)] border border-[var(--kt-border)] text-[var(--kt-text-dim)] text-sm">
                        Loading past conversation…
                      </div>
                    </div>
                  ) : (
                    <>
                      {/* Loading with no messages yet: show "Thinking…"; once messages exist, ResultsDisplay shows "Processing your request..." */}
                      <ResultsDisplay
                        messages={messages}
                        isLoading={isLoading && liveTrace.length === 0 && !liveText}
                        username={userName}
                      />

                      {/* The live turn sits after the committed history, where
                          the answer will land — so nothing jumps when the turn
                          finishes and the real message takes its place. It
                          replaces the old "Thinking…" pill, which told the
                          operator only that something was happening. */}
                      {isLoading && (liveTrace.length > 0 || liveText) && (
                        <LiveTurn steps={liveTrace} text={liveText} />
                      )}


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
                            <div className="max-w-[85%] rounded-2xl p-4 bg-[var(--kt-inset)] border border-[var(--kt-border)] text-[var(--kt-text-strong)] backdrop-blur-sm">
                              <div className="text-[10px] uppercase tracking-[0.2em] text-[var(--kt-text-dim)] mb-2">
                                Payment confirmation
                              </div>
                              <p className="text-sm text-[var(--kt-text)] mb-3">
                                Please review and confirm the payment details below.
                              </p>
                              <div className="bg-[var(--kt-inset)] rounded-lg p-3 border border-[var(--kt-border)] space-y-2 text-sm">
                                {reason.operation === 'swap_and_transfer' && reason.from_token && (
                                  <div className="flex justify-between items-center">
                                    <span className="text-[var(--kt-text-dim)]">Swap From:</span>
                                    <span className="text-[var(--kt-text-strong)] font-medium">
                                      {reason.from_token}
                                    </span>
                                  </div>
                                )}
                                <div className="flex justify-between items-center">
                                  <span className="text-[var(--kt-text-dim)]">Send Amount:</span>
                                  <span className="text-[var(--kt-text-strong)] font-semibold">
                                    {reason.received_amount} {toToken}
                                  </span>
                                </div>
                                <div className="flex justify-between items-center">
                                  <span className="text-[var(--kt-text-dim)]">To:</span>
                                  <span className="text-[var(--kt-text-strong)] font-medium">
                                    @{reason.receiver_username}
                                  </span>
                                </div>
                                <div className="flex justify-between items-center">
                                  <span className="text-[var(--kt-text-dim)]">Operation:</span>
                                  <span className="text-[var(--kt-text-strong)] font-medium">{operation}</span>
                                </div>
                              </div>
                              <div className="flex gap-3 pt-3 mt-2">
                                <button
                                  type="button"
                                  onClick={() => handleInterruptReject(paymentInterrupt.id)}
                                  className="flex-1 inline-flex items-center justify-center px-3 py-2 rounded-xl border border-red-700/60 bg-[var(--kt-down)]/10 text-red-100 hover:bg-[var(--kt-down)]/10 text-sm font-medium transition-colors"
                                >
                                  Cancel
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleInterruptApprove(paymentInterrupt.id, reason)}
                                  className="flex-1 inline-flex items-center justify-center px-3 py-2 rounded-xl bg-[var(--kt-hover)] hover:bg-white/30 text-[var(--kt-text-strong)] text-sm font-medium transition-colors border border-[var(--kt-border)]"
                                >
                                  Confirm
                                </button>
                              </div>
                            </div>
                          </div>
                        )
                      })()}
                    </>
                  )}
                </div>
              </div>
            </div>
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

      {/* Chat Input Bar - docked at the bottom of the content area, not the window */}
      <ChatInputBar
        offsetLeft={isWideViewport && isSidebarOpen ? SIDEBAR_WIDTH : 0}
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

      {/* Mobile: past conversations sheet (desktop uses left sidebar) */}
      <AnimatePresence>
        {isMobileHistoryOpen && (
          <>
            <motion.button
              type="button"
              aria-label="Close conversation history"
              className="lg:hidden fixed inset-0 z-40 bg-black/60 backdrop-blur-[2px]"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onClick={() => setIsMobileHistoryOpen(false)}
            />
            <motion.aside
              className="lg:hidden fixed left-0 top-16 bottom-0 z-50 w-[min(100vw-2.5rem,300px)] max-w-[88vw] bg-[var(--kt-bg)] border-r border-[var(--kt-border)] shadow-[8px_0_32px_rgba(0,0,0,0.35)] flex flex-col overflow-hidden"
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: 'spring', damping: 28, stiffness: 320 }}
            >
              <div className="flex-1 overflow-y-auto overscroll-contain px-2 pt-3 pb-8 scrollbar-minimal">
                <PastConversationsTab
                  variant="mobileSheet"
                  onRequestClose={() => setIsMobileHistoryOpen(false)}
                  userId={userId}
                  refreshTrigger={historyRefreshKey}
                  onLoadConversation={handleMobileLoadConversation}
                  onHistoryLoadingChange={setIsHistoryLoading}
                  onOpenDevtools={() => {
                    setIsMobileHistoryOpen(false)
                    setIsDevtoolsOpen(true)
                  }}
                  activeSessionId={sessionId}
                  activeMessages={messages}
                  onNewChat={async () => {
                    await handleNewChat()
                    setIsMobileHistoryOpen(false)
                  }}
                  onActiveSessionDeleted={handleActiveSessionDeleted}
                />
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>

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
        userId={userId}
        userName={userName}
        sessionId={sessionId}
        sessionLog={sessionLog}
        isStreaming={isLoading}
        sessionCost={sessionCost}
        overallCost={overallCost}
        messages={messages}
      />
    </div>
  )
}
