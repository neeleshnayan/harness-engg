"use client"

import React, { useState, useEffect } from 'react'
import { Menu } from 'lucide-react'
import agentsApi from '@/lib/agents_api'
import { useRouter } from 'next/navigation'
import { ChatMessage } from './types'
import { categories } from './constants'
import CategoryTiles from './components/CategoryTiles'
import ChatInputBar, { ChatMessages } from './components/ChatInterface'
import ResultsDisplay from './components/ResultsDisplay'



export default function BacktestPage() {
  const router = useRouter()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [showMenu, setShowMenu] = useState(false)
  
  // Session management for mem0 integration
  const [userId, setUserId] = useState<string>('')
  const [sessionId, setSessionId] = useState<string>('')
  

  // Initialize session and user IDs on component mount
  useEffect(() => {
    // Generate or retrieve user ID (persistent across sessions)
    let storedUserId = localStorage.getItem('clark_user_id')
    if (!storedUserId) {
      storedUserId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
      localStorage.setItem('clark_user_id', storedUserId)
    }
    setUserId(storedUserId)

    // Generate session ID (new for each browser session)
    const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    setSessionId(newSessionId)
  }, [])


  const handlePromptClick = async (prompt: string) => {
    setSelectedCategory(null)
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
        query: prompt,
        user_id: userId,
        session_id: sessionId
      })

      const data = response.data
      
      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: data.message,
        timestamp: new Date(),
        parsedIntent: data.parsed_intent,
        success: data.success,
        backtestResult: data.data?.backtest_result,
        screenerResult: data.data?.screener_type && data.data.screener_type !== 'economic' ? data.data : undefined,
        economicResult: data.data?.screener_type === 'economic' ? data.data : undefined
      }

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

      const data = response.data
      
      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: data.message,
        timestamp: new Date(),
        parsedIntent: data.parsed_intent,
        success: data.success,
        backtestResult: data.data?.backtest_result,
        screenerResult: data.data?.screener_type && data.data.screener_type !== 'economic' ? data.data : undefined,
        economicResult: data.data?.screener_type === 'economic' ? data.data : undefined
      }

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

      {/* Fixed Chat Box just below navbar; overlays results on scroll (visible when user has started) */}
      {(messages.some(m => m.type === 'user') || messages.some(m => m.backtestResult || m.screenerResult || m.economicResult)) && (
        <div className="fixed top-20 left-0 right-0 z-50">
          <div className="container mx-auto px-4 max-w-6xl">
            <div className="h-[8.5rem]">
              <ChatMessages messages={messages} isLoading={isLoading} />
            </div>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className={`container fixed top-0 sm:top-32 mx-auto px-4 py-0 sm:py-2 max-w-6xl relative z-0 ${
        (messages.some(m => m.type === 'user') || messages.some(m => m.backtestResult || m.screenerResult || m.economicResult)) ? 'pt-[8.5rem]' : ''
      }`}>
        {/* Clark Logo - Show only when no user messages or results */}
        {!messages.some(m => m.type === 'user') && !messages.some(m => m.backtestResult || m.screenerResult || m.economicResult) && (
          <div className="flex items-center justify-center mb-2 mt-20 sm:mt-0">
            <img src="/clark.svg" alt="Clark" className="h-[7.28rem] w-[7.28rem] sm:h-[9.1rem] sm:w-[9.1rem] drop-shadow-[0_4px_16px_rgba(162,89,247,0.3)]" />
          </div>
        )}

        {/* Category Tiles - Show only when no user messages or results */}
        {!messages.some(m => m.type === 'user') && !messages.some(m => m.backtestResult || m.screenerResult || m.economicResult) && (
          <CategoryTiles
            categories={categories}
            selectedCategory={selectedCategory}
            onCategorySelect={setSelectedCategory}
            onPromptClick={handlePromptClick}
            isLoading={isLoading}
          />
        )}

        {/* Results Display - bounded scroll between top chat and bottom input */}
        <div className="dark">
          <div
            className={
              (messages.some(m => m.type === 'user') || messages.some(m => m.backtestResult || m.screenerResult || m.economicResult))
                ? 'max-h-[calc(100vh-6rem-8.5rem-6.5rem)] overflow-y-auto'
                : 'max-h-[calc(100vh-6rem-6.5rem)] overflow-y-auto'
            }
          >
            <ResultsDisplay messages={messages} />
          </div>
        </div>
                    </div>

      {/* Chat Input Bar - fixed at bottom */}
      <ChatInputBar
        inputValue={inputValue}
        setInputValue={setInputValue}
        isLoading={isLoading}
        onSendMessage={handleSendMessage}
        onKeyPress={handleKeyPress}
      />
    </div>
  )
}
