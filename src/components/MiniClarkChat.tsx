"use client"

import React, { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import agentsApi from '@/lib/agents_api'
import { ChatMessage } from '@/app/clark/types'
import ResultsDisplay from '@/app/clark/components/ResultsDisplay'
import PromptGuideModal from '@/app/clark/components/PromptGuideModal'
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
  const [userName, setUserName] = useState<string>('')
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

  // Match /clark page: same payload parsing so ResultsDisplay shows backtest, price history, balance, etc.
  const createAssistantMessage = (payload: any): ChatMessage => {
    const messageId = (Date.now() + Math.random()).toString()
    let responseMessage: string =
      payload?.message ??
      (payload?.data?.markdown as string | undefined) ??
      "Sorry, I'm unable to process your request at the moment."
    const rawData = payload?.data

    let backtestResult = rawData?.backtest_result ?? rawData?.backtestResult
    if (!backtestResult && rawData) {
      if (rawData.technical?.backtest_result) backtestResult = rawData.technical.backtest_result
      else if (rawData.backtest?.backtest_result) backtestResult = rawData.backtest.backtest_result
      else if (rawData.data_fetcher && (rawData.backtest_result || rawData.backtest?.backtest_result)) {
        backtestResult = rawData.backtest_result || rawData.backtest?.backtest_result
      }
    }

    const priceHistoryData = rawData?.price_history ?? rawData?.priceHistory
    let dataPoints = priceHistoryData?.data_points ?? priceHistoryData?.data
    if (!dataPoints && Array.isArray(priceHistoryData)) dataPoints = priceHistoryData
    const hasValidPricePoints = Array.isArray(dataPoints) && dataPoints.length > 0 &&
      dataPoints.some((p: { price?: number }) => typeof p?.price === 'number')
    const rawToken = rawData?.token || priceHistoryData?.token || payload?.parsed_intent?.token_name || ''
    const displayTokenForHistory = (rawToken || '').replace(/^k/i, '') || rawToken
    const priceHistoryResult = priceHistoryData && hasValidPricePoints && Array.isArray(dataPoints)
      ? {
          token: displayTokenForHistory,
          lookback_days: priceHistoryData?.lookback_days || payload?.parsed_intent?.lookback_days || 30,
          count: priceHistoryData?.count || dataPoints.length || 0,
          data_points: dataPoints,
        }
      : undefined

    const balanceSource = rawData?.balances != null || rawData?.dailyBalances != null || rawData?.intradayBalances != null
      ? rawData
      : (rawData?.krypton_pay && typeof rawData.krypton_pay === 'object' ? rawData.krypton_pay : null)
    const balanceOp = balanceSource?.operation ?? rawData?.operation ?? payload?.parsed_intent?.operation
    const balancesArr = balanceSource?.balances ?? rawData?.balances
    const dailyArr = balanceSource?.dailyBalances ?? balanceSource?.daily_balances ?? rawData?.dailyBalances ?? rawData?.daily_balances
    const intradayArr = balanceSource?.intradayBalances ?? balanceSource?.intraday_balances ?? rawData?.intradayBalances ?? rawData?.intraday_balances
    const hasBalances = Array.isArray(balancesArr) && balancesArr.length > 0
    const hasDailyBalances = Array.isArray(dailyArr) && dailyArr.length > 0
    const hasIntradayBalances = Array.isArray(intradayArr) && intradayArr.length > 0
    const isBalanceOp = balanceOp === 'balances' || balanceOp === 'balances_daily' || balanceOp === 'balances_intraday'
    const hasBalanceKeys = rawData && (rawData.balances !== undefined || rawData.dailyBalances !== undefined || rawData.intradayBalances !== undefined || rawData.krypton_pay != null)
    const hasKryptonPayBalance = (payload?.parsed_intent?.agent_ids as string[] | undefined)?.includes?.('krypton_pay') && isBalanceOp
    const balanceResult = isBalanceOp && (hasBalances || hasDailyBalances || hasIntradayBalances || hasKryptonPayBalance || (hasBalanceKeys && balanceOp != null))
      ? {
          username_or_address: balanceSource?.username_or_address ?? rawData?.username_or_address ?? payload?.parsed_intent?.username_or_address ?? '',
          operation: (balanceOp as 'balances' | 'balances_daily' | 'balances_intraday') || 'balances',
          ...(Array.isArray(balancesArr) && { balances: balancesArr }),
          ...(Array.isArray(dailyArr) && { dailyBalances: dailyArr }),
          ...(Array.isArray(intradayArr) && { intradayBalances: intradayArr }),
        }
      : undefined

    const regulationResult = rawData?.regulation_result ?? rawData?.regulationResult
    if (regulationResult) responseMessage = ''

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
      balanceResult,
      screenerResult: undefined,
      economicResult: undefined,
      regulationResult,
      source: payload?.source ?? rawData?.source,
      capabilitiesSummary: payload?.capabilities_summary ?? rawData?.capabilities_summary,
      parameterRequest,
      agentFlow: payload?.agent_flow,
    }
  }

  /** Single path for API call, callbacks, and response handling. */
  const runQuery = async (query: string, userMessage?: ChatMessage) => {
    setIsLoading(true)
    try {
      const response = await agentsApi.post('/api/v1/agents/query', {
        query,
        user_id: userId,
        username: userName,
        session_id: sessionId,
      })
      const payload = response.data
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
          content: "Sorry, I'm unable to process your request at the moment.",
          timestamp: new Date(),
          success: false,
        },
      ])
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

  // Clark UI: single set of class names and one input bar definition
  const inputBarClasses = "flex items-center gap-2"
  const promptBtnClasses = "h-10 w-10 flex items-center justify-center rounded-xl bg-teal-900/60 border border-teal-700/50 shadow-sm hover:bg-teal-800/60 flex-shrink-0 transition-colors"
  const inputClasses = "flex-1 bg-teal-900/40 border border-teal-700/50 text-white placeholder:text-teal-200/60 focus:border-teal-400 focus:ring-1 focus:ring-teal-400/30 rounded-xl h-10 text-sm transition-colors"
  // Match /clark ChatInputBar: minimal send button (no gradient), blends with bar, icon only
  const sendBtnClasses =
    "flex items-center justify-center h-10 w-10 min-w-10 min-h-10 flex-shrink-0 rounded-xl " +
    "bg-transparent hover:bg-teal-800/50 border-0 transition-colors " +
    "disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-400/50"

  const inputBar = (
    <div className={inputBarClasses}>
      <button
        type="button"
        aria-label="Open prompt library"
        onClick={() => setIsPromptModalOpen(true)}
        className={promptBtnClasses}
      >
        <img src="/clark process.svg" alt="Prompts" className="h-5 w-5 drop-shadow-[0_0_8px_rgba(94,234,212,0.3)]" />
      </button>
      <Input
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyPress={handleKeyPress}
        placeholder="Ask Clark..."
        disabled={isLoading}
        className={inputClasses}
      />
      <button
        type="button"
        onClick={handleSendMessage}
        disabled={!inputValue.trim() || isLoading}
        className={sendBtnClasses}
        aria-label="Send message"
      >
        {isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin text-teal-200 shrink-0" />
        ) : (
          <img src="/send button.svg" alt="" className="h-7 w-7 sm:h-10 sm:w-10 pointer-events-none shrink-0" />
        )}
      </button>
    </div>
  )

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

  if (shouldShowInputOnly) {
    return (
      <>
        {inputBar}
        {promptsModal}
      </>
    )
  }

  return (
    <>
      <div className="relative w-full rounded-2xl border border-teal-700/40 bg-[#001C1B]/95 backdrop-blur-sm overflow-hidden shadow-[0_8px_32px_rgba(0,0,0,0.4)]">
        <Button
          onClick={handleExpand}
          variant="ghost"
          size="sm"
          className="absolute top-2 right-2 z-10 h-8 w-8 p-0 text-teal-200/80 hover:text-white hover:bg-teal-700/30 bg-teal-900/60 backdrop-blur-sm rounded-full border border-teal-700/40 transition-colors"
          aria-label="Expand to full Clark view"
        >
          <img src="/maximize.svg" alt="Maximize" className="h-4 w-4" />
        </Button>
        <div
          ref={feedRef}
          className="overflow-y-auto px-4 py-3 scrollbar-thin scrollbar-thumb-teal-600/50 scrollbar-track-transparent"
          style={{ height: `${containerHeight}px`, transition: 'height 0.3s ease-in-out', maxHeight: `${MAX_HEIGHT}px` }}
        >
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full text-teal-200/70">
              <div className="text-center">
                <img src="/clark.svg" alt="Clark" className="h-14 w-14 mx-auto mb-2 opacity-90" />
              </div>
            </div>
          ) : (
            <div className="dark">
              <div className="space-y-3">
                <ResultsDisplay messages={messages} isLoading={isLoading} username={userName} />
              </div>
            </div>
          )}
        </div>
        <div className="px-4 py-3 border-t border-teal-700/50 bg-gradient-to-b from-teal-900/40 to-[#0b1515]/80">
          {inputBar}
        </div>
      </div>
      {promptsModal}
    </>
  )
}

